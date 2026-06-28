#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# backfill-provenance v2 / classify.py
# Turn per-path evidence (graph.py) into a classification + action, applying the
# inversion-avoidance spine (DESIGN §4) and the two-independent-signals gate (§2.6).
# Conservative by default: mark ONLY a creation-rooted whole-file hash-match to disk that
# clears the inversion threshold; everything else is report-only or leave-alone.

import os
import time
import calendar

# Human-legible labels for every abstention/decision class (DESIGN §8.3; machine names
# stay in the appendix only).
PLAIN = {
    "edit_chain_missing_base": "Could see edits but not the original file to rebuild it from.",
    "codex_update_no_base": "Codex changed the file but the starting version wasn't recoverable.",
    "missing_prior_state": "No recoverable earlier version to rebuild from.",
    "indirect_write": "AI wrote this through a script or shell, so the exact bytes aren't in the log.",
    "expanded_heredoc": "Written via a shell heredoc that the shell would expand, so the literal bytes aren't certain.",
    "non_git_single_signal": "No version control here, so a human edit can't be ruled out from one signal alone.",
    "mixed_authorship": "Human-written file that AI later edited; can't be whole-file marked as AI.",
    "diverged": "The file's current contents don't match what AI is recorded as writing.",
    "result_missing": "The tool ran but no success result was found, so the write isn't confirmed.",
    "result_ambiguous": "The success result couldn't be matched to this write.",
    "disk_unreadable": "The file couldn't be read (missing, or a cloud-only placeholder).",
    "cloud_placeholder": "Cloud-only Dropbox placeholder; needs hydration to classify.",
    "notebook_unreplayable": "Notebook edit; cell-level changes aren't whole-file replayable in v1.",
    "no_match": "AI touched this path but the current bytes couldn't be tied to an AI write.",
    "no_ai_evidence": "No AI evidence for this file.",
    "quarantined": "Looks like a secret/credential path; left untouched on purpose.",
}

GRACE_SECONDS = 2 * 86400


def _iso_to_epoch(ts):
    if not ts:
        return None
    try:
        t = ts.replace("Z", "").split(".")[0]
        return calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return None


_git_cache = {}


def in_vcs(path):
    """True if path is inside a git work tree (a .git exists in an ancestor)."""
    d = os.path.dirname(os.path.abspath(path))
    seen = []
    while True:
        if d in _git_cache:
            res = _git_cache[d]
            for s in seen:
                _git_cache[s] = res
            return res
        seen.append(d)
        if os.path.exists(os.path.join(d, ".git")):
            for s in seen:
                _git_cache[s] = True
            return True
        parent = os.path.dirname(d)
        if parent == d:
            for s in seen:
                _git_cache[s] = False
            return False
        d = parent


def workspace_of(path):
    """Nearest ancestor that looks like a project root, for report grouping (DESIGN §8.4)."""
    markers = (".git", "package.json", "pyproject.toml", ".planning", "SKILL.md", ".claude")
    d = os.path.dirname(os.path.abspath(path))
    best = d
    cur = d
    while True:
        if any(os.path.exists(os.path.join(cur, m)) for m in markers):
            best = cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return best


def _mtime_in_window(path, events):
    """Signal-B helper: the file's mtime must sit within the AI activity window (no later
    gap suggesting a post-AI human save). Returns (in_window, later_human_suspected)."""
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return False, False
    epochs = [e for e in (_iso_to_epoch(ev.get("ts")) for ev in events) if e]
    if not epochs:
        return True, False  # no usable timestamps -> don't penalize, rely on fh hash-match
    last = max(epochs)
    first = min(epochs)
    later_human = mt > last + GRACE_SECONDS
    in_window = (first - GRACE_SECONDS) <= mt <= (last + GRACE_SECONDS)
    return in_window, later_human


def classify_path(ev, events_for_path):
    """ev = graph evidence for the path. Returns classification dict."""
    path = ev["path"]
    vcs = in_vcs(path)
    out = {
        "path": path, "workspace": workspace_of(path), "vcs": vcs,
        "engines": ev["engines"], "sessions": ev["sessions"],
        "klass": None, "action": None, "marker_type": None,
        "machine_reason": None, "reason": None,
        "signals": [], "origin_event": ev.get("origin_event"),
        "fh_signal": ev.get("fh_signal"), "match_kind": ev.get("match_kind"),
    }

    if ev["matched"]:
        # creation-rooted whole-file match -> pure-AI creation (mixed authorship can't match,
        # since mixed has no AI creation root). Apply the inversion gate.
        out["signals"].append(f"whole-file {ev['match_kind']} hash-match to disk")
        if vcs:
            out.update(klass="ai_origin", action="mark", marker_type="ai-origin",
                       machine_reason="vcs_lineage",
                       reason="AI created these exact bytes and they're unchanged; version control records any human edits.")
            out["signals"].append("under version control (2nd signal)")
            return out
        # non-VCS: need a 2nd independent signal
        in_window, later_human = _mtime_in_window(path, events_for_path)
        if ev["fh_signal"] and in_window:
            out["signals"].append("file-history independently stored these exact bytes")
            out.update(klass="ai_origin", action="mark", marker_type="ai-origin",
                       machine_reason="two_signal_non_vcs",
                       reason="AI created these exact bytes; a second independent store (file-history) agrees, and nothing edited it later.")
            return out
        out.update(klass="non_git_single_signal", action="report-only", marker_type=None,
                   machine_reason="non_git_single_signal",
                   reason=PLAIN["non_git_single_signal"])
        if later_human:
            out["signals"].append("file modified after last AI touch (possible human edit)")
        return out

    # not matched -> report-only or leave-alone
    reason = ev.get("abstain_reason") or "no_match"
    if ev["indirect_only"]:
        reason = "indirect_write"
    out.update(klass=reason, action="report-only", marker_type=None,
               machine_reason=reason, reason=PLAIN.get(reason, reason))
    return out


def classify_all(evidence, events):
    by_path_events = {}
    for e in events:
        by_path_events.setdefault(e["path"], []).append(e)
    results = []
    for path, ev in evidence.items():
        results.append(classify_path(ev, by_path_events.get(path, [])))
    return results
