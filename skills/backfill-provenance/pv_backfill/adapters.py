#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# backfill-provenance v2 / adapters.py
# Discover AI history logs, prefix-sniff each against a known adapter, and parse into
# normalized touch EVENTS with a STRICT tool_use_id / call_id success-join (DESIGN §2.2:
# failed writes are excluded). Also builds the file-history snapshot index (DESIGN §2.1,
# corrected per IMPLEMENTATION_NOTES.md: snapshots are PATH-attributed base states, not
# opaque content hashes). Read-only. Stdlib only.

import glob
import json
import os
import re

HOME = os.path.expanduser("~")
CLAUDE_PROJECTS = os.path.join(HOME, ".claude/projects")
CLAUDE_FILE_HISTORY = os.path.join(HOME, ".claude/file-history")
CODEX_SESSIONS = os.path.join(HOME, ".codex/sessions")
CODEX_ARCHIVED = os.path.join(HOME, ".codex/archived_sessions")

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# ---------------------------------------------------------------------------
# Event constructor
# ---------------------------------------------------------------------------
def _event(engine, session, source_log, ts, seq, kind, tool, path,
           body=None, edits=None, patch=None, src_path=None, tuid=None,
           success=False, eligible=False, reason=None, cwd=None):
    return {
        "engine": engine, "session": session, "source_log": source_log,
        "ts": ts or "", "seq": seq, "kind": kind, "tool": tool,
        "path": path, "src_path": src_path,
        "body": body, "edits": edits, "patch": patch,
        "tuid": tuid, "success": success, "eligible": eligible,
        "reason": reason, "cwd": cwd,
    }


def _abspath(p, cwd):
    if not p:
        return p
    p = os.path.expanduser(p)
    if not os.path.isabs(p) and cwd:
        p = os.path.normpath(os.path.join(cwd, p))
    return os.path.abspath(p) if os.path.isabs(p) else p


# ---------------------------------------------------------------------------
# Bash command analysis — narrow heredoc eligibility (DESIGN §2.1)
# ---------------------------------------------------------------------------
# Exactly one `cat > PATH <<'DELIM' ... DELIM` with a QUOTED delimiter (no shell
# expansion), a literal target path, no loop/subshell/sudo/xargs/pipe wrapping. A leading
# `cd "abs"` / `mkdir -p` prefix is allowed (it only fixes cwd; it does not alter bytes).
_HEREDOC = re.compile(
    r"""(?:^|\n)\s*cat\s*>\s*(?P<q>["']?)(?P<path>[^"'\n<>|&;]+?)(?P=q)\s*<<\s*'(?P<delim>[A-Za-z0-9_]+)'\s*\n"""
    r"""(?P<body>.*?)\n(?P=delim)\b""",
    re.DOTALL,
)
_UNSAFE_BASH = re.compile(r"(?:\bfor\b|\bwhile\b|\$\(|`|\bxargs\b|\bsudo\b|\beval\b|\|\s*sh\b|\|\s*bash\b)")
_CD = re.compile(r"""(?:^|\n)\s*cd\s+(?P<q>["']?)(?P<dir>[^"'\n;&|]+?)(?P=q)\s*(?:\n|$)""")


def analyze_bash(cmd):
    """Return list of (kind, dict) writes recovered from a Bash command.
    Eligible heredocs -> ('create', {...}); mv/cp -> ('move'/'copy', {...}); any other
    write redirection -> ('indirect', {reason})."""
    out = []
    if not isinstance(cmd, str):
        return out
    # establish a literal cwd override if the command starts with `cd "literal"`
    local_cwd = None
    m = _CD.search(cmd)
    if m and "$" not in m.group("dir") and "*" not in m.group("dir"):
        local_cwd = m.group("dir")

    heredocs = list(_HEREDOC.finditer(cmd))
    if len(heredocs) == 1 and not _UNSAFE_BASH.search(cmd.replace(heredocs[0].group("body"), "")):
        h = heredocs[0]
        path = h.group("path").strip()
        if "$" not in path and "*" not in path and "?" not in path:
            out.append(("create", {"path": path, "body": h.group("body") + "\n",
                                    "local_cwd": local_cwd, "tool": "Bash-heredoc"}))
            return out
    # multiple heredocs or unsafe context -> report-only indirect for each heredoc target
    for h in heredocs:
        out.append(("indirect", {"path": h.group("path").strip(), "local_cwd": local_cwd,
                                 "reason": "expanded_heredoc", "tool": "Bash-heredoc-unsafe"}))
    # other write redirections (>, >>, tee, sed -i) -> indirect, path best-effort
    for rm in re.finditer(r"(?:>>?|tee\s+|sed\s+-i[^ ]*\s+[^>]*?)\s*(?P<q>[\"']?)(?P<path>[^\s\"'<>|&;]+\.[A-Za-z0-9]{1,8})(?P=q)", cmd):
        p = rm.group("path")
        if not p.startswith("/dev/") and "heredoc" not in p:
            out.append(("indirect", {"path": p, "local_cwd": local_cwd,
                                     "reason": "indirect_write", "tool": "Bash-redirect"}))
    # mv / cp of path-ish args -> evidence-propagating edges (DESIGN §3.4)
    for verb, kind in (("mv", "move"), ("cp", "copy")):
        for rm in re.finditer(rf"(?:^|\n|;|&&)\s*{verb}\s+(?P<a>[^\s;&|]+)\s+(?P<b>[^\s;&|]+)", cmd):
            a, b = rm.group("a").strip("'\""), rm.group("b").strip("'\"")
            if re.search(r"\.[A-Za-z0-9]{1,8}$", a) and "*" not in a and "$" not in a:
                out.append((kind, {"src_path": a, "path": b, "local_cwd": local_cwd,
                                   "tool": f"Bash-{verb}"}))
    return out


# ---------------------------------------------------------------------------
# Codex apply_patch parsing
# ---------------------------------------------------------------------------
def parse_apply_patch(patch_text):
    """Yield (op, relpath, body_or_hunk) for each file section in an apply_patch input.
    op in {'add','update','delete'}. For 'add', body is the literal added content."""
    if not isinstance(patch_text, str):
        return
    sections = re.split(r"(?=\*\*\* (?:Add|Update|Delete) File: )", patch_text)
    for sec in sections:
        m = re.match(r"\*\*\* (Add|Update|Delete) File: (.+)", sec)
        if not m:
            continue
        op = m.group(1).lower()
        relpath = m.group(2).strip()
        rest = sec[m.end():]
        if op == "add":
            # Added lines are prefixed with '+'; strip the first leading '+'.
            lines = []
            for ln in rest.splitlines():
                if ln.startswith("*** End Patch"):
                    break
                lines.append(ln[1:] if ln.startswith("+") else ln)
            body = "\n".join(lines).strip("\n")
            yield (op, relpath, (body + "\n") if body else "")
        else:
            yield (op, relpath, rest)


# ---------------------------------------------------------------------------
# Claude projects / subagents adapter — strict id-join
# ---------------------------------------------------------------------------
def _iter_jsonl(path):
    try:
        with open(path, errors="ignore") as f:
            for i, ln in enumerate(f):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    yield i, json.loads(ln), None
                except Exception:
                    yield i, None, "bad-json"
    except OSError:
        return


def parse_claude_log(path, cov):
    """Parse one Claude projects/subagent JSONL. Returns list of events.
    Strict success-join: a tool_use is emitted with success only when its tool_result
    (matched by tool_use_id) is present and not is_error (DESIGN §2.2)."""
    session = os.path.basename(path)[:-6]  # strip .jsonl
    # subagent files are agent-*.jsonl under <parent>/subagents/
    if session.startswith("agent-"):
        parent = os.path.basename(os.path.dirname(os.path.dirname(path)))
        session = f"{parent}/{os.path.basename(path)[:-6]}"
    pending = {}   # tuid -> partial event dict (kind/tool/path/body/...)
    results = {}   # tuid -> success bool (may arrive before or after)
    events = []
    cwd = None
    relevant = 0
    bad = 0

    def finalize(tuid, ev):
        ev["success"] = bool(results.get(tuid, False)) if tuid in results else False
        if tuid not in results:
            ev["reason"] = ev.get("reason") or "result_missing"
        events.append(ev)

    for seq, d, err in _iter_jsonl(path):
        if err:
            bad += 1
            continue
        t = d.get("type")
        if t == "file-history-snapshot":
            cov["fh_snapshot_records"] = cov.get("fh_snapshot_records", 0) + 1
            continue
        if d.get("cwd"):
            cwd = d.get("cwd")
        ts = d.get("timestamp", "")
        msg = d.get("message") if isinstance(d.get("message"), dict) else None
        content = msg.get("content") if msg else None
        if t == "assistant" and isinstance(content, list):
            for b in content:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                name = b.get("name")
                tuid = b.get("id")
                inp = b.get("input") or {}
                if name == "Write":
                    relevant += 1
                    pending[tuid] = _event("claude", session, path, ts, seq, "create", "Write",
                                           _abspath(inp.get("file_path"), cwd), body=inp.get("content"),
                                           tuid=tuid, eligible=True, cwd=cwd)
                elif name == "Edit":
                    relevant += 1
                    pending[tuid] = _event("claude", session, path, ts, seq, "edit", "Edit",
                                           _abspath(inp.get("file_path"), cwd),
                                           edits=[{"old": inp.get("old_string", ""), "new": inp.get("new_string", ""),
                                                   "replace_all": bool(inp.get("replace_all"))}],
                                           tuid=tuid, eligible=True, cwd=cwd)
                elif name == "MultiEdit":
                    relevant += 1
                    es = [{"old": e.get("old_string", ""), "new": e.get("new_string", ""),
                           "replace_all": bool(e.get("replace_all"))} for e in (inp.get("edits") or [])]
                    pending[tuid] = _event("claude", session, path, ts, seq, "edit", "MultiEdit",
                                           _abspath(inp.get("file_path"), cwd), edits=es,
                                           tuid=tuid, eligible=True, cwd=cwd)
                elif name == "NotebookEdit":
                    relevant += 1
                    pending[tuid] = _event("claude", session, path, ts, seq, "edit", "NotebookEdit",
                                           _abspath(inp.get("notebook_path") or inp.get("file_path"), cwd),
                                           tuid=tuid, eligible=False, reason="notebook_unreplayable", cwd=cwd)
                elif name == "Bash":
                    for kind, info in analyze_bash(inp.get("command", "")):
                        relevant += 1
                        lc = info.get("local_cwd") or cwd
                        ev = _event("claude", session, path, ts, seq, kind, info.get("tool", "Bash"),
                                    _abspath(info.get("path"), lc),
                                    body=info.get("body"), src_path=_abspath(info.get("src_path"), lc) if info.get("src_path") else None,
                                    tuid=tuid, eligible=(kind == "create"),
                                    reason=info.get("reason"), cwd=lc)
                        # several writes can share one Bash tuid; index list under tuid
                        pending.setdefault(("bash", tuid), []).append(ev)
        elif t == "user" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    tuid = b.get("tool_use_id")
                    results[tuid] = not bool(b.get("is_error"))

    # finalize: results may have arrived; join
    for tuid, ev in list(pending.items()):
        if isinstance(tuid, tuple) and tuid[0] == "bash":
            real = tuid[1]
            ok = bool(results.get(real, False))
            for e in ev:
                e["success"] = ok
                if real not in results:
                    e["reason"] = e.get("reason") or "result_missing"
                events.append(e)
        else:
            finalize(tuid, ev)
    cov["relevant_events"] = cov.get("relevant_events", 0) + relevant
    cov["bad_lines"] = cov.get("bad_lines", 0) + bad
    return events


# ---------------------------------------------------------------------------
# Codex adapters (nested jsonl, archived jsonl, flat-legacy whole-doc)
# ---------------------------------------------------------------------------
def _codex_emit_from_items(items, session, source_log, cwd, cov):
    """Shared item walker for nested-line payloads and flat-legacy items[].
    items: list of (seq, ts, payload) tuples."""
    events = []
    call_ok = {}     # call_id -> success
    pending = {}     # call_id -> [events]
    for seq, ts, p in items:
        if not isinstance(p, dict):
            continue
        ptype = p.get("type")
        if ptype in ("custom_tool_call_output", "function_call_output"):
            cid = p.get("call_id")
            out = p.get("output")
            ok = True
            if isinstance(out, str):
                ok = "failed" not in out.lower() and "error" not in out.lower()[:40]
            call_ok[cid] = ok
            continue
        if ptype in ("custom_tool_call", "function_call") and (p.get("name") == "apply_patch" or "apply_patch" in str(p.get("name") or "")):
            cid = p.get("call_id")
            patch = p.get("input") or p.get("arguments") or ""
            if isinstance(patch, str) and patch.startswith("{"):
                try:
                    patch = json.loads(patch).get("input", patch)
                except Exception:
                    pass
            cov["relevant_events"] = cov.get("relevant_events", 0) + 1
            for op, rel, payload in parse_apply_patch(patch):
                ap = _abspath(rel, cwd)
                if op == "add":
                    ev = _event("codex", session, source_log, ts, seq, "create", "apply_patch:Add",
                                ap, body=payload, tuid=cid, eligible=True, cwd=cwd)
                elif op == "update":
                    ev = _event("codex", session, source_log, ts, seq, "edit", "apply_patch:Update",
                                ap, patch=payload, tuid=cid, eligible=True, cwd=cwd)
                else:
                    ev = _event("codex", session, source_log, ts, seq, "delete", "apply_patch:Delete",
                                ap, tuid=cid, eligible=False, reason="delete", cwd=cwd)
                pending.setdefault(cid, []).append(ev)
    for cid, evs in pending.items():
        ok = bool(call_ok.get(cid, False))
        for e in evs:
            e["success"] = ok
            if cid not in call_ok:
                e["reason"] = e.get("reason") or "result_missing"
            events.append(e)
    return events


def parse_codex_nested(path, cov):
    session = None
    cwd = None
    items = []
    bad = 0
    for seq, d, err in _iter_jsonl(path):
        if err:
            bad += 1
            continue
        p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        if d.get("type") == "session_meta":
            session = p.get("id") or session
            cwd = p.get("cwd") or cwd
        elif d.get("type") == "turn_context":
            cwd = p.get("cwd") or cwd
        items.append((seq, d.get("timestamp", ""), p))
    if session is None:
        m = re.search(r"-([0-9a-f]{8}-[0-9a-f-]+)\.jsonl$", os.path.basename(path))
        session = m.group(1) if m else os.path.basename(path)
    cov["bad_lines"] = cov.get("bad_lines", 0) + bad
    return _codex_emit_from_items(items, session, path, cwd, cov)


def parse_codex_flat_legacy(path, cov):
    """Single pretty-printed JSON document {session, items} (DESIGN §3.2). Whole-doc read;
    exempt from per-line corruption budget."""
    try:
        with open(path, errors="ignore") as f:
            d = json.load(f)
    except Exception:
        cov["unparseable"] = cov.get("unparseable", []) + [path]
        return []
    sess = d.get("session", {}) if isinstance(d, dict) else {}
    session = sess.get("id") or os.path.basename(path)
    cwd = sess.get("cwd")
    raw_items = d.get("items", []) if isinstance(d, dict) else []
    items = []
    for seq, it in enumerate(raw_items):
        if isinstance(it, dict):
            p = it.get("payload") if isinstance(it.get("payload"), dict) else it
            items.append((seq, it.get("timestamp", ""), p))
    return _codex_emit_from_items(items, session, path, cwd, cov)


# ---------------------------------------------------------------------------
# file-history index (DESIGN §2.1, corrected per IMPLEMENTATION_NOTES.md)
# ---------------------------------------------------------------------------
def build_filehistory_index(cov):
    """Map abs_path -> [snapshot records]. Path attribution comes from trackedFileBackups
    in the project logs (backupFileName '<id>@vN' -> abs path); the snapshot bytes live at
    file-history/<session>/<id>@vN. id is a stable PATH hash, so one id->path map attributes
    every snapshot. Returns (path_to_snaps, id_to_path)."""
    id_to_path = {}
    for log in (glob.glob(os.path.join(CLAUDE_PROJECTS, "*", "*.jsonl"))
                + glob.glob(os.path.join(CLAUDE_PROJECTS, "*", "*", "subagents", "*.jsonl"))):
        for _seq, d, err in _iter_jsonl(log):
            if err or d.get("type") != "file-history-snapshot":
                continue
            tfb = (d.get("snapshot") or {}).get("trackedFileBackups") or {}
            for abspath, meta in tfb.items():
                bfn = meta.get("backupFileName")
                if bfn and "@" in bfn:
                    id_to_path[bfn.split("@")[0]] = os.path.abspath(os.path.expanduser(abspath))
    path_to_snaps = {}
    n = 0
    for snap in glob.glob(os.path.join(CLAUDE_FILE_HISTORY, "*", "*@v*")):
        base = os.path.basename(snap)
        if "@v" not in base:
            continue
        sid_dir = os.path.basename(os.path.dirname(snap))
        fid, ver = base.split("@v", 1)
        path = id_to_path.get(fid)
        try:
            ver_n = int(re.match(r"\d+", ver).group())
        except Exception:
            ver_n = 0
        rec = {"session": sid_dir, "version": ver_n, "snapshot_file": snap, "path": path}
        n += 1
        if path:
            path_to_snaps.setdefault(path, []).append(rec)
    cov["fh_snapshots_indexed"] = n
    cov["fh_paths_attributed"] = len(path_to_snaps)
    cov["fh_ids_mapped"] = len(id_to_path)
    return path_to_snaps, id_to_path


# ---------------------------------------------------------------------------
# Discovery + orchestration
# ---------------------------------------------------------------------------
def discover_logs():
    """Enumerate every candidate log, classified by adapter (DESIGN §8.1 pre-flight)."""
    groups = {
        "claude:projects": sorted(glob.glob(os.path.join(CLAUDE_PROJECTS, "*", "*.jsonl"))),
        "claude:subagents": sorted(glob.glob(os.path.join(CLAUDE_PROJECTS, "*", "*", "subagents", "*.jsonl"))),
        "codex:nested": sorted(glob.glob(os.path.join(CODEX_SESSIONS, "**", "rollout-*.jsonl"), recursive=True)),
        "codex:flat-legacy": sorted(glob.glob(os.path.join(CODEX_SESSIONS, "rollout-2025-*.json"))),
        "codex:archived": sorted(glob.glob(os.path.join(CODEX_ARCHIVED, "**", "rollout-*.jsonl"), recursive=True)),
    }
    return groups


def _under_roots(path, roots):
    if not roots:
        return True
    ap = os.path.abspath(os.path.expanduser(path)) if path else ""
    return any(ap == r or ap.startswith(r + os.sep) for r in roots)


def scan_all(roots=None, cov=None, progress=None):
    """Run every adapter, returning (events_filtered_to_roots, fh_index, coverage).
    roots: list of abs path prefixes to keep events for (None = all). Logs are still fully
    parsed so cross-project logs can attribute in-scope files (DESIGN §3.3)."""
    cov = cov if cov is not None else {}
    roots = [os.path.abspath(os.path.expanduser(r)) for r in roots] if roots else None
    groups = discover_logs()
    cov["log_counts"] = {k: len(v) for k, v in groups.items()}
    events = []
    parsers = {
        "claude:projects": parse_claude_log, "claude:subagents": parse_claude_log,
        "codex:nested": parse_codex_nested, "codex:archived": parse_codex_nested,
        "codex:flat-legacy": parse_codex_flat_legacy,
    }
    done = 0
    for group, files in groups.items():
        parser = parsers[group]
        for f in files:
            try:
                evs = parser(f, cov)
            except Exception as e:  # a single bad log never aborts the run
                cov["unparseable"] = cov.get("unparseable", []) + [f"{f}: {e}"]
                continue
            events.extend(evs)
            done += 1
            if progress and done % 250 == 0:
                progress(done)
    cov["events_total"] = len(events)
    if roots:
        events = [e for e in events if _under_roots(e.get("path"), roots) or _under_roots(e.get("src_path"), roots)]
    cov["events_in_scope"] = len(events)
    fh_index, _ = build_filehistory_index(cov)
    return events, fh_index, cov
