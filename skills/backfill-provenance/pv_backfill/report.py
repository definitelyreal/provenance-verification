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


# Sources DESIGN names but the v0.5.x engine does NOT mine (marked absent, never hidden).
NOT_COVERED = [
    "Gemini history (~/.gemini) — no adapter in v0.5.x",
    "~/.codex memories / ambient-suggestions / computer-use — not audited (read-only suggestions, but coverage is NOT proven)",
    "Google Sheets / Docs / Slack / Airtable / action-queue — designed, not wired",
]


def render_text(rep):
    L = []
    cov = rep.get("coverage", {})
    L.append("=" * 70)
    L.append("backfill-provenance v2 — REPORT (read-only inventory). Marking is FROZEN in v0.5.x.")
    L.append("=" * 70)
    L.append("")
    L.append("!! AUTO-MARKING IS DISABLED (KNOWN_LIMITATIONS.md). The rows below are an")
    L.append("   ADVISORY inventory, not a list of files that will be marked. A 3-round")
    L.append("   adversarial review found the mark gate can launder human content; the gate")
    L.append("   is held until re-founded on git-history authorship (v0.6).")
    L.append("")
    L.append("CAVEATS (this report is provisional):")
    L.append("  - Coverage is INCOMPLETE, not 'complete' — see NOT COVERED below.")
    L.append("  - Reconciliation below is bucket balance only, NOT a proof every file was covered.")
    L.append("  - 'marking candidate' rows are advisory: git/cwd attribution can be wrong, and")
    L.append("    a content hash-match alone cannot prove a file is still human-untouched.")
    L.append("")
    L.append("COVERAGE (pre-flight):")
    for k, v in (cov.get("log_counts") or {}).items():
        L.append(f"  {k:24s} {v} logs")
    L.append(f"  events parsed: {cov.get('events_total', 0)}  in-scope: {cov.get('events_in_scope', 0)}"
             f"  bad-lines: {cov.get('bad_lines', 0)}")
    L.append(f"  file-history: {cov.get('fh_snapshots_indexed', 0)} snapshots, "
             f"{cov.get('fh_paths_attributed', 0)} paths attributed")
    if cov.get("unparseable"):
        L.append(f"  UNPARSEABLE sources (NOT mined): {len(cov['unparseable'])}")
    L.append("  NOT COVERED by v0.5.x (absent, not assumed-clean):")
    for s in NOT_COVERED:
        L.append(f"    - {s}")
    L.append("")
    L.append("EXECUTIVE SUMMARY:")
    L.append(f"  files scanned (with AI evidence in scope): {rep['scanned']}")
    L.append(f"  marking candidates (NOT applied — frozen):  {rep['mark']}")
    L.append(f"  report-only (not eligible even when unfrozen): {rep['report_only']}")
    L.append("")
    L.append("  report-only, by reason:")
    for klass, n in sorted(rep["by_class"].items(), key=lambda x: -x[1]):
        if klass in ("ai_origin",):
            continue
        L.append(f"    {n:5d}  {klass}")
    L.append("")
    L.append(f"  Of the {rep['mark']} candidates, {rep['higher_risk_count']} are higher-risk"
             " (non-git or multi-session).")
    L.append("")
    L.append("BY WORKSPACE:")
    for ws, acts in sorted(rep["workspaces"].items()):
        L.append(f"  {ws}")
        L.append(f"      candidate={acts.get('mark',0)}  report-only={acts.get('report-only',0)}")
    L.append("")
    L.append("SAMPLE marking candidates (advisory only — NOT auto-marked in v0.5.x):")
    for c in [x for x in rep["classifications"] if x["action"] == "mark"][:10]:
        L.append(f"  [{'git' if c['vcs'] else 'non-git'}] {c['path']}")
        L.append(f"        why: {c['reason']}")
    L.append("")
    L.append("bucket balance (not a coverage proof): " + ("OK" if rep["balanced"] else "FAILED"))
    return "\n".join(L)
