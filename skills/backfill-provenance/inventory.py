#!/usr/bin/env python3
# ai-processed:unverified · session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 · 2026-06-27
# backfill-provenance / inventory.py
# Join AI-touch events with on-disk files + existing markers -> inventory.json. READ-ONLY.

import json, os, sys, argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "reference"))
import history_scan
try:
    import provenance
except Exception:
    provenance = None

CODE_EXT = {".py", ".js", ".ts", ".tsx", ".sh", ".rb", ".go", ".rs", ".java", ".c", ".cpp", ".css", ".sql", ".yaml", ".yml"}


def is_marked(path):
    if provenance is None:
        return False
    try:
        return provenance.is_marked(open(path, errors="ignore").read())
    except OSError:
        return False


def medium_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".md":
        return "markdown"
    if ext in CODE_EXT:
        return "code"
    return "other"


def build(root, engines):
    events = history_scan.scan(engines, root)
    by_file = {}
    for e in events:
        f = os.path.abspath(os.path.expanduser(e["file"]))
        d = by_file.setdefault(f, {"sessions": set(), "engines": set(), "tools": set(), "last": ""})
        d["sessions"].add(e["session"]); d["engines"].add(e["engine"]); d["tools"].add(e["tool"])
        if e["timestamp"] > d["last"]:
            d["last"] = e["timestamp"]
    items = []
    for f, d in by_file.items():
        medium = medium_of(f)
        if not os.path.exists(f):
            status, marked = "missing", False
        elif is_marked(f):
            status, marked = "already-marked", True
        elif medium == "other":
            status, marked = "skip-other", False
        else:
            status, marked = "candidate", False
        conf = "high" if ("Write" in d["tools"]) else "med"
        items.append({
            "path": f, "medium": medium, "status": status,
            "proposed_marker": "ai-suggestion:unverified" if status == "candidate" else None,
            "confidence": conf, "engines": sorted(d["engines"]),
            "sessions": sorted(d["sessions"])[:5], "session_count": len(d["sessions"]),
            "last_touch": d["last"],
        })
    items.sort(key=lambda x: (x["status"], x["path"]))
    return items


def main(argv):
    ap = argparse.ArgumentParser(description="Build a provenance backfill inventory (read-only).")
    ap.add_argument("--root", required=True)
    ap.add_argument("--engine", default="claude,codex")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    items = build(a.root, tuple(a.engine.split(",")))
    print("inventory for", os.path.abspath(os.path.expanduser(a.root)))
    print("totals:", dict(Counter(i["status"] for i in items)))
    out = a.json or os.path.join(HERE, "inventory.json")
    json.dump(items, open(out, "w"), indent=2)
    print("wrote", out, f"({len(items)} items)")
    for i in [x for x in items if x["status"] == "candidate"][:12]:
        print("  CANDIDATE", i["confidence"], "+".join(i["engines"]), i["path"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
