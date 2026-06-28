#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# backfill-provenance v2 / report.py
# The PRIMARY deliverable (DESIGN §8.2): a tiered inventory of un-provenanced AI artifacts
# with recovered evidence. Marking is the rare hard-gated subset. Enforces the reconciliation
# invariant (§10): a non-balancing run is a BLOCKER, never a warning.

from collections import Counter, defaultdict


class ReconciliationError(Exception):
    pass


def build_report(classifications, coverage):
    scanned = len(classifications)
    by_action = Counter(c["action"] for c in classifications)
    by_class = Counter(c["klass"] for c in classifications)
    dropped = [c for c in classifications if c["action"] not in ("mark", "report-only", "leave-alone")]

    # Reconciliation (DESIGN §10): every scanned path must land in exactly one bucket.
    mark = by_action.get("mark", 0)
    report_only = by_action.get("report-only", 0)
    leave = by_action.get("leave-alone", 0)
    balanced = (scanned == mark + report_only + leave) and not dropped
    if not balanced:
        raise ReconciliationError(
            f"BLOCKER: reconciliation failed — scanned={scanned} "
            f"mark={mark} report_only={report_only} leave={leave} dropped={len(dropped)}")

    by_ws = defaultdict(lambda: defaultdict(list))
    for c in classifications:
        by_ws[c["workspace"]][c["action"]].append(c)

    higher_risk = [c for c in classifications
                   if c["action"] == "mark" and (not c["vcs"] or len(c["sessions"]) > 1)]

    return {
        "scanned": scanned, "mark": mark, "report_only": report_only, "leave": leave,
        "by_action": dict(by_action), "by_class": dict(by_class),
        "balanced": balanced, "coverage": coverage,
        "workspaces": {ws: {a: len(v) for a, v in acts.items()} for ws, acts in by_ws.items()},
        "higher_risk_count": len(higher_risk),
        "classifications": classifications,
    }


def render_text(rep):
    L = []
    cov = rep.get("coverage", {})
    L.append("=" * 70)
    L.append("backfill-provenance v2 — report (primary deliverable; marking is the subset)")
    L.append("=" * 70)
    L.append("")
    L.append("COVERAGE (pre-flight):")
    for k, v in (cov.get("log_counts") or {}).items():
        L.append(f"  {k:24s} {v} logs")
    L.append(f"  events parsed: {cov.get('events_total', 0)}  in-scope: {cov.get('events_in_scope', 0)}"
             f"  bad-lines: {cov.get('bad_lines', 0)}")
    L.append(f"  file-history: {cov.get('fh_snapshots_indexed', 0)} snapshots, "
             f"{cov.get('fh_paths_attributed', 0)} paths attributed")
    if cov.get("unparseable"):
        L.append(f"  UNPARSEABLE sources (NOT marked): {len(cov['unparseable'])}")
    L.append("")
    L.append("EXECUTIVE SUMMARY:")
    L.append(f"  files scanned (with AI evidence in scope): {rep['scanned']}")
    L.append(f"  auto-mark-eligible:                        {rep['mark']}")
    L.append(f"  report-only (not eligible):                {rep['report_only']}")
    L.append("")
    L.append("  Realistic yield: only the auto-mark-eligible subset gets a marker. The rest")
    L.append("  are report-only because this tree is largely non-git or lacks a recoverable")
    L.append("  base — this is expected (DESIGN §1), not a failure.")
    L.append("")
    L.append("  report-only, by reason:")
    for klass, n in sorted(rep["by_class"].items(), key=lambda x: -x[1]):
        if klass in ("ai_origin",):
            continue
        L.append(f"    {n:5d}  {klass}")
    L.append("")
    L.append(f"HIGHER-RISK mark decisions (non-git or multi-session): {rep['higher_risk_count']}"
             "  — review individually before applying.")
    L.append("")
    L.append("BY WORKSPACE:")
    for ws, acts in sorted(rep["workspaces"].items()):
        L.append(f"  {ws}")
        L.append(f"      mark={acts.get('mark',0)}  report-only={acts.get('report-only',0)}")
    L.append("")
    L.append("SAMPLE auto-mark-eligible:")
    for c in [x for x in rep["classifications"] if x["action"] == "mark"][:10]:
        L.append(f"  [{'git' if c['vcs'] else 'non-git'}] {c['path']}")
        L.append(f"        why: {c['reason']}")
    L.append("")
    L.append("balanced reconciliation: " + ("OK" if rep["balanced"] else "FAILED"))
    return "\n".join(L)
