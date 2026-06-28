#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# backfill-provenance v2 / cli.py
# Phased orchestrator (DESIGN §8.1): pre-flight -> scan/graph -> classify -> report
# -> (opt-in) mark. Report-primary, dry-run by default. Checkpoints to state.json so a
# stopped run resumes at marking without re-mining. Run as a module:
#   python3 -m pv_backfill.cli <command> ...
# Commands: preflight | report | apply | restore | unmark | version

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))         # for `import pv_backfill`
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

from pv_backfill import adapters, graph, classify, report, mark
import provenance


def _state_path(workdir):
    return os.path.join(workdir, "state.json")


def _norm_roots(roots):
    return [os.path.abspath(os.path.expanduser(r)) for r in roots] if roots else None


def cmd_preflight(a):
    groups = adapters.discover_logs()
    print("PRE-FLIGHT source enumeration (DESIGN §8.1):")
    total = 0
    for k, v in groups.items():
        print(f"  {k:24s} {len(v)} logs")
        total += len(v)
    print(f"  TOTAL {total} candidate logs")
    cov = {}
    fh, idmap = adapters.build_filehistory_index(cov)
    print(f"  file-history: {cov['fh_snapshots_indexed']} snapshots, "
          f"{cov['fh_paths_attributed']} paths attributed, {cov['fh_ids_mapped']} ids mapped")
    grammar = f"{provenance.GRAMMAR_VERSION} {provenance.grammar_sha()[:16]}"
    print(f"  grammar: vendored@{grammar}")
    return 0


def run_pipeline(roots, workdir):
    roots = _norm_roots(roots)
    cov = {}
    print(f"[1/4] scanning history (roots={roots or 'ALL'}) ...", file=sys.stderr)
    events, fh_index, cov = adapters.scan_all(roots=roots, cov=cov,
                                              progress=lambda n: print(f"   ..{n} logs", file=sys.stderr))
    print(f"[2/4] reconstructing content state for "
          f"{len({e['path'] for e in events})} paths ...", file=sys.stderr)
    placeholders = set()

    def reader(p):
        return mark.read_bytes(p, placeholder_sink=placeholders)

    evidence = graph.build_path_evidence(events, fh_index, reader, mark.snap_bytes)
    print(f"[3/4] classifying ...", file=sys.stderr)
    classifications = classify.classify_all(evidence, events)
    # upgrade disk_unreadable -> cloud_placeholder where Dropbox placeholder detected
    for c in classifications:
        if c["machine_reason"] == "disk_unreadable" and c["path"] in placeholders:
            c["klass"] = c["machine_reason"] = "cloud_placeholder"
            c["reason"] = classify.PLAIN["cloud_placeholder"]
    print(f"[4/4] building report ...", file=sys.stderr)
    rep = report.build_report(classifications, cov)
    os.makedirs(workdir, exist_ok=True)
    # checkpoint: classifications minus heavy origin bodies
    slim = []
    for c in classifications:
        oe = c.get("origin_event") or {}
        slim.append({**c, "origin_event": {"session": oe.get("session"), "tool": oe.get("tool"),
                                           "engine": oe.get("engine")} if oe else None})
    with open(_state_path(workdir), "w") as f:
        json.dump({"roots": roots, "classifications": slim, "coverage": cov}, f, indent=2)
    return rep, classifications


def cmd_report(a):
    rep, _ = run_pipeline(a.root, a.workdir)
    txt = report.render_text(rep)
    print(txt)
    out = os.path.join(a.workdir, "report.json")
    with open(out, "w") as f:
        json.dump({k: v for k, v in rep.items() if k != "classifications"}, f, indent=2)
    with open(os.path.join(a.workdir, "report.txt"), "w") as f:
        f.write(txt + "\n")
    print(f"\nwrote {out} and report.txt + state.json under {a.workdir}", file=sys.stderr)
    return 0


MARKING_DISABLED_MSG = """\
AUTO-MARKING IS DISABLED IN v0.5.x.

A 3-round adversarial review (build/redteam/) showed the marking gate can launder
human content: the "two independent signals" premise is false (file-history is the
same engine's own pre-edit undo buffer, not an independent attestation), the git path
trusts mere presence of an ancestor .git (gitignored/stray repos included), the
apply-phase write-race guard is a no-op, and delete/recreate segmentation is not
implemented. See KNOWN_LIMITATIONS.md.

The REPORT is the deliverable for now. Marking is held until the gate is re-founded on a
genuinely independent signal (git-history authorship) in a deliberate v0.6.
To override for testing ONLY (unsafe, may mark human files): --experimental-unsafe-marking
"""


def cmd_apply(a):
    if not getattr(a, "experimental_unsafe_marking", False):
        print(MARKING_DISABLED_MSG)
        return 0
    print("!! --experimental-unsafe-marking: the gate is known-unsafe (KNOWN_LIMITATIONS.md) !!",
          file=sys.stderr)
    st = _state_path(a.workdir)
    if not os.path.exists(st):
        print("no state.json — run `report` first.", file=sys.stderr)
        return 1
    state = json.load(open(st))
    cls = state["classifications"]
    chosen = [c for c in cls if c["action"] == "mark"]
    if a.workspace:
        chosen = [c for c in chosen if c["workspace"] == a.workspace]
    if not a.include_non_git:
        held = [c for c in chosen if not c["vcs"]]
        chosen = [c for c in chosen if c["vcs"]]
        if held:
            print(f"holding {len(held)} non-git mark candidates (pass --include-non-git to apply)",
                  file=sys.stderr)
    session = os.environ.get("PV_SESSION", "backfill-v2")
    manifest, counts, run_id = mark.apply_markers(chosen, session, do_write=a.apply)
    print("apply result:", counts, "" if a.apply else "(DRY-RUN — add --apply to write)")
    if a.apply and any(m["op"] == "add-marker" for m in manifest):
        print(f"backups+manifest: {os.path.join(mark.BACKUP_ROOT, run_id)}")
        print(f"restore with: python3 -m pv_backfill.cli restore {run_id}")
    return 0


def cmd_restore(a):
    return mark.restore(a.run_id)


def cmd_unmark(a):
    session = os.environ.get("PV_SESSION", "backfill-v2")
    return mark.unmark(os.path.abspath(os.path.expanduser(a.path)), session, do_write=a.apply)


def cmd_version(a):
    print(f"backfill-provenance engine v{__import__('pv_backfill').__version__}")
    print(f"grammar: vendored@{provenance.GRAMMAR_VERSION} {provenance.grammar_sha()[:16]}")
    print(f"marker state: {mark.MARKER_STATE}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="pv_backfill", description="Backfill provenance v2.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_wd = os.path.join(os.getcwd(), "build", "backfill-run")

    p = sub.add_parser("preflight"); p.set_defaults(fn=cmd_preflight)
    p = sub.add_parser("report")
    p.add_argument("--root", action="append", help="restrict to this path (repeatable)")
    p.add_argument("--workdir", default=default_wd)
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("apply")
    p.add_argument("--workdir", default=default_wd)
    p.add_argument("--workspace", default=None, help="only this workspace group")
    p.add_argument("--include-non-git", action="store_true")
    p.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    p.add_argument("--experimental-unsafe-marking", action="store_true",
                   help="override the v0.5.x marking freeze (KNOWN-UNSAFE; may mark human files)")
    p.set_defaults(fn=cmd_apply)
    p = sub.add_parser("restore"); p.add_argument("run_id"); p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("unmark")
    p.add_argument("path"); p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_unmark)
    p = sub.add_parser("version"); p.set_defaults(fn=cmd_version)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
