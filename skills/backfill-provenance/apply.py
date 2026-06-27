#!/usr/bin/env python3
# ai-processed:unverified · session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 · 2026-06-27
# backfill-provenance / apply.py
# Apply provenance markers from an inventory, with backup + restorable manifest.
# DRY-RUN by default. Never writes 'verified'. Never clobbers an existing marker.

import json, os, sys, argparse, hashlib, datetime, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "reference"))
try:
    import provenance
except Exception:
    provenance = None
BACKUPS = os.path.join(HERE, "backups")


def sha(p):
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    except OSError:
        return None


def already(path):
    if provenance is None:
        return False
    try:
        return provenance.is_marked(open(path, errors="ignore").read())
    except OSError:
        return False


def bak_name(p):
    return hashlib.sha256(p.encode()).hexdigest() + os.path.splitext(p)[1]


def render(item, date):
    t = item["proposed_marker"].split(":")[0]            # ai-suggestion / ai-processed
    osession = (item.get("sessions") or ["unknown"])[0]   # original maker
    if item["medium"] == "markdown":
        return f"<!-- {t}:unverified | session:{osession} | date:{date} -->\n"
    return f"# {t}:unverified · session:{osession} · {date}\n"


def apply_one(item, session, run_dir, manifest, do_write):
    p = item["path"]
    if not os.path.exists(p) or already(p) or item["medium"] == "other":
        return "skip"
    date = datetime.date.today().isoformat()
    marker = render(item, date)
    txt = open(p, errors="ignore").read()
    if item["medium"] == "code" and txt.startswith("#!"):
        nl = txt.find("\n") + 1
        new = txt[:nl] + marker + txt[nl:]
    else:
        new = marker + txt
    if not do_write:
        return "would-mark"
    before = sha(p)
    os.makedirs(run_dir, exist_ok=True)
    shutil.copy2(p, os.path.join(run_dir, bak_name(p)))
    open(p, "w").write(new)
    manifest.append({"path": p, "op": "add-marker", "before_sha256": before, "after_sha256": sha(p),
                     "marker": marker.strip(), "original_session": (item.get("sessions") or ["unknown"])[0],
                     "backfill_session": session, "medium": item["medium"],
                     "at": datetime.datetime.now().isoformat()})
    return "marked"


def restore(run_id):
    run_dir = os.path.join(BACKUPS, run_id)
    man = os.path.join(run_dir, "changes.jsonl")
    if not os.path.exists(man):
        print("no manifest for", run_id); return 1
    n = 0
    for ln in open(man):
        rec = json.loads(ln); p = rec["path"]
        bak = os.path.join(run_dir, bak_name(p))
        if os.path.exists(bak):
            shutil.copy2(bak, p); n += 1
    print(f"restored {n} files from run {run_id}"); return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Apply provenance markers from an inventory.")
    ap.add_argument("--inventory", default=os.path.join(HERE, "inventory.json"))
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--confidence", default="high,med", help="comma list of confidences to mark")
    ap.add_argument("--restore", default=None, metavar="RUN_ID")
    a = ap.parse_args(argv)
    if a.restore:
        return restore(a.restore)
    session = os.environ.get("PV_SESSION", "backfill")
    run_id = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = os.path.join(BACKUPS, run_id)
    items = json.load(open(a.inventory))
    conf = set(a.confidence.split(","))
    manifest, counts = [], {}
    for it in items:
        if it["status"] != "candidate" or it["confidence"] not in conf:
            continue
        r = apply_one(it, session, run_dir, manifest, a.apply)
        counts[r] = counts.get(r, 0) + 1
    if a.apply and manifest:
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "changes.jsonl"), "w") as f:
            for m in manifest:
                f.write(json.dumps(m) + "\n")
        print("backup +manifest:", run_dir, "  (restore with: apply.py --restore", run_id + ")")
    print("result:", counts, "" if a.apply else "(DRY-RUN — re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
