#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# backfill-provenance v2 / graph.py
# Content-state reconstruction + the sole positive gate: hash-continuity of a WHOLE-FILE
# byte stream reconstructed from a creation event (DESIGN §2.4a — never a fragment match).
# Replay is per-source-ordered within ONE session only (DESIGN §2.3: timestamps order
# events only within a single source). Cross-session edit chains cannot be reliably ordered
# in a treeless tree -> abstain. file-history snapshots are bases / second-signal corroborators,
# never origin (IMPLEMENTATION_NOTES.md deviation 1). Stdlib only.

import hashlib


class ReplayError(Exception):
    pass


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest() if b is not None else None


def _norm_newlines(s):
    return s.replace("\r\n", "\n").replace("\r", "\n")


def apply_edit(text, old, new, replace_all=False):
    """Apply one Edit. Exact match required; a small CRLF/LF tolerance is allowed because
    that is a faithful re-encoding, not a fragment guess. Missing match -> ReplayError."""
    if old == "":
        # Edit with empty old_string = prepend/insert at start (Claude semantics: only on new files)
        return new + text
    if old in text:
        return text.replace(old, new) if replace_all else text.replace(old, new, 1)
    # CRLF/LF tolerance
    nt, no = _norm_newlines(text), _norm_newlines(old)
    if no in nt:
        nn = _norm_newlines(new)
        return nt.replace(no, nn) if replace_all else nt.replace(no, nn, 1)
    raise ReplayError("old_string not found")


def apply_multiedit(text, edits):
    """Atomic ordered chain (DESIGN §5.2): any sub-edit miss fails the whole chain."""
    for e in edits:
        text = apply_edit(text, e.get("old", ""), e.get("new", ""), e.get("replace_all", False))
    return text


def apply_patch_update(text, hunk_text):
    """Best-effort apply_patch unified-diff applier. Each hunk: context lines (' '),
    removals ('-'), additions ('+'). Locate the (context+removed) block and splice. Any
    ambiguity -> ReplayError (abstain). Conservative by construction."""
    lines = text.split("\n")
    out = lines
    # split into hunks on @@ markers; if none, treat whole body as one hunk
    raw = hunk_text.split("\n")
    # build (removed_block, added_block) pairs sequentially
    removed, added = [], []
    blocks = []
    for ln in raw:
        if ln.startswith("@@"):
            if removed or added:
                blocks.append((removed, added)); removed, added = [], []
            continue
        if ln.startswith("*** "):
            continue
        if ln.startswith("-"):
            removed.append(ln[1:])
        elif ln.startswith("+"):
            added.append(ln[1:])
        elif ln.startswith(" "):
            # context line: belongs to both sides as an anchor
            removed.append(ln[1:]); added.append(ln[1:])
    if removed or added:
        blocks.append((removed, added))
    for removed, added in blocks:
        if not removed:
            raise ReplayError("hunk without removable anchor")
        joined = "\n".join(out)
        target = "\n".join(removed)
        if target not in joined:
            raise ReplayError("hunk context not found")
        replacement = "\n".join(added)
        joined = joined.replace(target, replacement, 1)
        out = joined.split("\n")
    return "\n".join(out)


def _to_bytes(s):
    return s.encode("utf-8", "surrogatepass") if isinstance(s, str) else s


def reconstruct_session_chain(create_ev, edit_evs):
    """Reconstruct whole-file bytes from a creation body + this session's ordered edits.
    edit_evs already filtered to same path+session+success, sorted by seq. Raises on any
    replay miss."""
    text = create_ev.get("body")
    if text is None:
        raise ReplayError("creation body absent")
    for e in edit_evs:
        if e.get("edits"):
            if e["tool"] == "MultiEdit":
                text = apply_multiedit(text, e["edits"])
            else:
                ed = e["edits"][0]
                text = apply_edit(text, ed["old"], ed["new"], ed["replace_all"])
        elif e.get("patch") is not None:
            text = apply_patch_update(text, e["patch"])
        else:
            raise ReplayError(f"uneditable event {e['tool']}")
    return _to_bytes(text)


def build_path_evidence(events, fh_index, read_bytes, snap_bytes):
    """Assemble per-path evidence. read_bytes(path)->bytes|None for on-disk (Dropbox-guarded
    by the caller); snap_bytes(snapshot_file)->bytes|None for file-history (always local).
    Returns dict: path -> evidence."""
    by_path = {}
    for e in events:
        by_path.setdefault(e["path"], []).append(e)

    out = {}
    for path, evs in by_path.items():
        evs_sorted = sorted(evs, key=lambda e: (e.get("ts", ""), e.get("seq", 0)))
        creations = [e for e in evs_sorted if e["kind"] == "create" and e["eligible"]]
        successful_creations = [e for e in creations if e.get("success")]
        any_touch = [e for e in evs_sorted if e["kind"] in ("create", "edit")]
        engines = sorted({e["engine"] for e in evs_sorted})
        sessions = sorted({e["session"] for e in evs_sorted})
        indirect_only = bool(evs_sorted) and all(
            (e["kind"] in ("indirect", "move", "copy", "delete")) or (not e["eligible"] and e["kind"] != "create")
            for e in evs_sorted) and not creations

        disk = read_bytes(path)
        disk_sha = sha_bytes(disk) if disk is not None else None

        ev = {
            "path": path, "engines": engines, "sessions": sessions,
            "n_events": len(evs_sorted),
            "has_creation": bool(creations),
            "has_successful_creation": bool(successful_creations),
            "disk_readable": disk is not None,
            "disk_sha": disk_sha,
            "indirect_only": indirect_only,
            "matched": False, "match_kind": None, "origin_event": None,
            "fh_signal": False, "fh_sessions": [],
            "later_human_suspected": False,
            "abstain_reason": None,
        }

        # --- positive gate: creation-rooted whole-file hash-continuity to disk ---
        if disk_sha and successful_creations:
            for c in successful_creations:
                cb = _to_bytes(c.get("body"))
                # (1) direct creation match
                if sha_bytes(cb) == disk_sha:
                    ev["matched"] = True; ev["match_kind"] = "direct-creation"; ev["origin_event"] = c
                    break
                # (2) creation + same-session ordered replay
                same = [e for e in evs_sorted
                        if e["session"] == c["session"] and e["kind"] == "edit"
                        and e.get("success") and (e.get("ts", ""), e.get("seq", 0)) > (c.get("ts", ""), c.get("seq", 0))]
                if same:
                    try:
                        recon = reconstruct_session_chain(c, same)
                        if sha_bytes(recon) == disk_sha:
                            ev["matched"] = True; ev["match_kind"] = "creation+replay"; ev["origin_event"] = c
                            break
                    except ReplayError:
                        pass
            if not ev["matched"]:
                ev["abstain_reason"] = "edit_chain_missing_base" if any(e["kind"] == "edit" for e in evs_sorted) else "diverged"

        # --- second independent signal: file-history snapshot of these exact disk bytes ---
        if disk_sha:
            for rec in fh_index.get(path, []):
                sb = snap_bytes(rec["snapshot_file"])
                if sb is not None and sha_bytes(sb) == disk_sha:
                    ev["fh_signal"] = True
                    ev["fh_sessions"].append(rec["session"])
            ev["fh_sessions"] = sorted(set(ev["fh_sessions"]))

        # --- abstention bookkeeping for the non-matched cases ---
        if not ev["matched"] and ev["abstain_reason"] is None:
            if not disk_sha:
                ev["abstain_reason"] = "disk_unreadable"
            elif indirect_only:
                ev["abstain_reason"] = "indirect_write"
            elif creations and not successful_creations:
                ev["abstain_reason"] = "result_missing"
            elif not creations and any_touch:
                ev["abstain_reason"] = "edit_chain_missing_base"
            else:
                ev["abstain_reason"] = "no_match"

        out[path] = ev
    return out
