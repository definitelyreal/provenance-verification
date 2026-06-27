#!/usr/bin/env python3
# ai-processed:unverified · session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 · 2026-06-27
# backfill-provenance / history_scan.py
# Parse Claude Code + Codex (+ Gemini) chat history into normalized AI-touch events:
#   {file, session, engine, tool, timestamp}
# Read-only. Resilient to corrupt lines and schema drift. Stdlib only.

import json, os, re, sys, glob, argparse

CLAUDE_PROJECTS = os.path.expanduser("~/.claude/projects")
CODEX_SESS = os.path.expanduser("~/.codex/archived_sessions")
CODEX_SESS2 = os.path.expanduser("~/.codex/sessions")
GEMINI_HIST = os.path.expanduser("~/.gemini/history")

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
_PATHISH = re.compile(r"\.[A-Za-z0-9]{1,8}$")  # ends in an extension


def _looks_like_path(s):
    return isinstance(s, str) and ("/" in s) and bool(_PATHISH.search(s)) and len(s) < 1024


def _walk_paths(obj, out):
    """Recursively collect values of any 'path'/'file_path'/'filename' key that look like files."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("path", "file_path", "filename", "notebook_path") and _looks_like_path(v):
                out.add(v)
            else:
                _walk_paths(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_paths(v, out)


def scan_claude(events):
    for f in glob.glob(os.path.join(CLAUDE_PROJECTS, "*", "*.jsonl")):
        try:
            lines = open(f, errors="ignore").read().splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("type") != "assistant":
                continue
            sid = d.get("sessionId", "")
            ts = d.get("timestamp", "")
            msg = d.get("message", {})
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in WRITE_TOOLS:
                    inp = b.get("input", {}) or {}
                    fp = inp.get("file_path") or inp.get("notebook_path")
                    if fp:
                        events.append({"file": fp, "session": sid, "engine": "claude",
                                       "tool": b.get("name"), "timestamp": ts})


def scan_codex(events):
    files = []
    for d in (CODEX_SESS, CODEX_SESS2):
        files += glob.glob(os.path.join(d, "**", "rollout-*.jsonl"), recursive=True)
    for f in files:
        m = re.search(r"rollout-.*?-([0-9a-f]{8}-[0-9a-f-]+)\.jsonl$", os.path.basename(f))
        sid = m.group(1) if m else os.path.basename(f)
        try:
            lines = open(f, errors="ignore").read().splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("type") not in ("response_item", "event_msg"):
                continue
            ts = d.get("timestamp", "")
            paths = set()
            _walk_paths(d.get("payload", {}), paths)
            for p in paths:
                events.append({"file": p, "session": sid, "engine": "codex",
                               "tool": "edit", "timestamp": ts})


def scan_gemini(events):
    # Best-effort; Gemini history schema varies. Collect path-like values.
    for f in glob.glob(os.path.join(GEMINI_HIST, "**", "*.json"), recursive=True) + \
             glob.glob(os.path.join(GEMINI_HIST, "**", "*.jsonl"), recursive=True):
        try:
            raw = open(f, errors="ignore").read()
        except OSError:
            continue
        for ln in raw.splitlines() or [raw]:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            paths = set()
            _walk_paths(d, paths)
            for p in paths:
                events.append({"file": p, "session": os.path.basename(f), "engine": "gemini",
                               "tool": "edit", "timestamp": ""})


def scan(engines=("claude", "codex"), root=None):
    events = []
    if "claude" in engines:
        scan_claude(events)
    if "codex" in engines:
        scan_codex(events)
    if "gemini" in engines:
        scan_gemini(events)
    if root:
        root = os.path.abspath(os.path.expanduser(root))
        events = [e for e in events if os.path.abspath(e["file"]).startswith(root)]
    return events


def main(argv):
    ap = argparse.ArgumentParser(description="Scan AI chat history for file-touch events.")
    ap.add_argument("--engine", default="claude,codex", help="comma list: claude,codex,gemini")
    ap.add_argument("--root", default=None, help="only events under this path")
    ap.add_argument("--json", default=None, help="write events to this JSON file")
    a = ap.parse_args(argv)
    events = scan(tuple(a.engine.split(",")), a.root)
    files = {}
    for e in events:
        files.setdefault(e["file"], set()).add(e["engine"])
    print(f"events: {len(events)}   distinct files: {len(files)}")
    by_engine = {}
    for e in events:
        by_engine[e["engine"]] = by_engine.get(e["engine"], 0) + 1
    print("by engine:", by_engine)
    if a.json:
        json.dump(events, open(a.json, "w"), indent=2)
        print("wrote", a.json)
    else:
        for fp in list(files)[:15]:
            print("  ", "+".join(sorted(files[fp])), fp)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
