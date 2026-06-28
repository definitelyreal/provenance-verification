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

    by_conf = Counter(c.get("confidence") for c in classifications if c["action"] == "mark")

    return {
        "scanned": scanned, "mark": mark, "report_only": report_only, "leave": leave,
        "by_action": dict(by_action), "by_class": dict(by_class),
        "conf_high": by_conf.get("high", 0), "conf_medium": by_conf.get("medium", 0),
        "balanced": balanced, "coverage": coverage,
        "workspaces": {ws: {a: len(v) for a, v in acts.items()} for ws, acts in by_ws.items()},
        "classifications": classifications,
    }


# Sources DESIGN names but the engine does NOT mine (marked absent, never hidden).
NOT_COVERED = [
    "Gemini history (~/.gemini) — no adapter yet",
    "~/.codex memories / ambient-suggestions / computer-use — not audited (read-only suggestions, but coverage is NOT proven)",
    "Google Sheets / Docs / Slack / Airtable / action-queue — designed, not wired",
]


def render_text(rep):
    L = []
    cov = rep.get("coverage", {})
    L.append("=" * 70)
    L.append("backfill-provenance — provenance QUARANTINE report (AI-origin inventory)")
    L.append("=" * 70)
    L.append("")
    L.append("The marker `ai-origin:backfilled` is an UNVERIFIED, REVERSIBLE quarantine flag: it")
    L.append("says 'a human did not write this file' so AI output isn't mistaken for human-")
    L.append("verified truth. It can be wrong (over-flagging a human file is cheap; a human")
    L.append("clears it). Marking is biased toward catching AI files, not toward precision.")
    L.append("")
    L.append("CAVEATS:")
    L.append("  - Coverage is INCOMPLETE — see NOT COVERED below.")
    L.append("  - The balance line is bucket arithmetic, NOT a proof every file was covered.")
    L.append("  - 'medium' confidence = AI created the file but it changed since (a human may")
    L.append("    have rewritten part of it). git / file-history raise confidence; they don't gate.")
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
    L.append("  NOT COVERED (absent, not assumed-clean):")
    for s in NOT_COVERED:
        L.append(f"    - {s}")
    L.append("")
    L.append("EXECUTIVE SUMMARY:")
    L.append(f"  files scanned (with AI evidence in scope): {rep['scanned']}")
    L.append(f"  AI-origin (markable):  {rep['mark']}   "
             f"[high confidence: {rep['conf_high']}, medium: {rep['conf_medium']}]")
    L.append(f"  report-only (not AI-origin — mixed/edited/indirect): {rep['report_only']}")
    L.append("")
    L.append("  report-only, by reason:")
    for klass, n in sorted(rep["by_class"].items(), key=lambda x: -x[1]):
        if klass in ("ai_origin",):
            continue
        L.append(f"    {n:5d}  {klass}")
    L.append("")
    L.append("  Apply marks HIGH confidence by default; `--min-confidence medium` includes the rest.")
    L.append("")
    L.append("BY WORKSPACE:")
    for ws, acts in sorted(rep["workspaces"].items()):
        L.append(f"  {ws}")
        L.append(f"      ai-origin={acts.get('mark',0)}  report-only={acts.get('report-only',0)}")
    L.append("")
    L.append("SAMPLE AI-origin candidates:")
    for c in [x for x in rep["classifications"] if x["action"] == "mark"][:10]:
        L.append(f"  [{c.get('confidence','?'):6s}|{'git' if c['vcs'] else 'non-git'}] {c['path']}")
        L.append(f"        why: {c['reason']}")
    L.append("")
    L.append("bucket balance (not a coverage proof): " + ("OK" if rep["balanced"] else "FAILED"))
    return "\n".join(L)
