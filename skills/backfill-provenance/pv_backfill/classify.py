#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# backfill-provenance v2 / classify.py
# Turn per-path evidence (graph.py) into a classification + action under the v0.6 QUARANTINE
# model: mark on ORIGIN (an AI creation event), biased toward recall. high confidence when
# current bytes still match what AI wrote, medium when AI created the file but it changed
# since. git + file-history raise confidence, they do NOT gate. Mixed (AI edited a human
# file) -> report-only. (Supersedes DESIGN.history §2.6's inversion gate; see IMPLEMENTATION_NOTES.md.)

import os
import time
import calendar

# Human-legible labels for every abstention/decision class (DESIGN.history §8.3; machine names
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
    """Nearest ancestor that looks like a project root, for report grouping (DESIGN.history §8.4)."""
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
    """ev = graph evidence for the path. Returns classification dict.

    QUARANTINE MODEL (v0.6): the marker is `ai-origin:backfilled` (unverified, fallible) — it
    flags "a human didn't write this," to be cleared/confirmed by a human or the gate later.
    So we bias toward RECALL: mark on ORIGIN. An AI-*created* file is marked; over-marking a
    human file is a cheap, reversible false-positive. The expensive error is MISSING an AI file
    (it then reads as human-trusted). git + file-history are CONFIDENCE annotations, not gates.
    Mixed (AI edited a human-created file) -> report-only: origin is human, and backfill cannot
    auto-produce a correct partial marker; a human adapts it later."""
    path = ev["path"]
    vcs = in_vcs(path)
    out = {
        "path": path, "workspace": workspace_of(path), "vcs": vcs,
        "engines": ev["engines"], "sessions": ev["sessions"],
        "klass": None, "action": None, "marker_type": None,
        "confidence": None, "content_sha": ev.get("disk_sha"),
        "machine_reason": None, "reason": None,
        "signals": [], "origin_event": ev.get("origin_event"),
        "fh_signal": ev.get("fh_signal"), "match_kind": ev.get("match_kind"),
    }
    # confidence annotations (do not gate)
    if vcs:
        out["signals"].append("git-tracked tree")
    if ev.get("fh_signal"):
        out["signals"].append("file-history holds these exact bytes")

    if ev["matched"]:
        # current on-disk bytes provably are an AI creation (direct body or same-session replay)
        out["signals"].insert(0, f"whole-file {ev['match_kind']} hash-match to disk")
        out.update(klass="ai_origin", action="mark", marker_type="ai-origin",
                   confidence="high", machine_reason="origin_bytes_on_disk",
                   reason="AI created this file and the current bytes still match what AI wrote.")
        return out

    if ev.get("has_successful_creation"):
        # AI created the file, but current bytes diverge (edited since, or human-rewritten).
        # Origin is still AI -> quarantine at MEDIUM confidence (fallible; human clears it).
        out["signals"].insert(0, "AI creation event for this path (current bytes diverged)")
        out.update(klass="ai_origin", action="mark", marker_type="ai-origin",
                   confidence="medium", machine_reason="ai_created_diverged",
                   reason="AI originally created this file; it has changed since, so a human may have rewritten part or all of it. Flagged unverified for review.")
        return out

    # no AI creation event -> not AI-origin. Report-only (mixed/edited/indirect/etc.).
    reason = ev.get("abstain_reason") or "no_match"
    if ev["indirect_only"]:
        reason = "indirect_write"
    elif any(e["kind"] == "edit" for e in events_for_path):
        reason = "mixed_authorship"   # AI edited a human-created file
    out.update(klass=reason, action="report-only", marker_type=None, confidence=None,
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
