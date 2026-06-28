---
name: backfill-provenance
description: Retroactively mark provenance across existing files by reconstructing what AI did from Claude Code + Codex (+ Gemini) chat history, per the provenance-verification standard. Comprehensive, conservative, and restorable. Use when asked to "backfill provenance", "mark existing AI files", "tag what AI wrote", or before adopting the standard on an existing project.
---
<!-- ai-suggestion:unverified | session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 | date:2026-06-28 -->

# backfill-provenance (v2)

**The primary output is a report** — an inventory of un-provenanced AI artifacts with the
evidence recovered for each. **Marking is a small, hard-gated subset.** On a machine with
almost no version control, a content hash-match cannot prove a file is still AI-untouched,
so auto-marking is the exception, not the headline (see `DESIGN.md` — the authoritative,
adversarially-hardened spec, and `IMPLEMENTATION_NOTES.md` — the two evidence-backed
refinements v2 made to it).

Reconstruct *what AI did* from chat history, classify, show the user, then mark only the
provable subset — reversibly, dry-run by default.

The engine is the `pv_backfill/` package; the vendored marker grammar is `lib/provenance.py`.

## Invariants (never violate)
- **Never write `verified`.** Backfill marks `ai-origin:backfilled` (creation-only) and nothing higher.
- **Origin needs a creation event.** A file is marked only when its current on-disk bytes
  equal a reconstructed whole-file stream rooted in an AI **creation** (`Write` / Codex
  `Add File` / static quoted-delim heredoc), matched whole-file (never a fragment).
- **Inversion gate (the spine):** under git, the repo is the second signal. Non-git needs
  **two** independent signals (the creation match + an independent file-history attestation
  of the same bytes, in the AI activity window). One signal in a treeless tree never marks.
- **file-history is base/continuity, never origin** (a snapshot can be human content — e.g.
  CLAUDE.md). Edited-on-human-base files route to report-only, never whole-file marked.
- **Conservative on any doubt → report-only.** Never clobber an existing marker.
- **Backup + manifest before any write; restorable.** Backups live OUTSIDE the synced tree.
- **Two attributions:** the marker records the *origin* session; the manifest records *this*
  backfill session. Never conflated.

## Flow

1. **Announce** what you're about to do, in plain terms. Don't work silently.

2. **Pre-flight** — enumerate every history source and print coverage (no classification yet):
   `python3 -m pv_backfill.cli preflight`

3. **Choose surfaces / scope.** Default = comprehensive across approved roots. v1 surfaces:
   filesystem (markdown + code). Sheets/Docs/Slack/Airtable are *report-only* (designed, not
   wired to mutate). Skip credential/quarantined paths automatically.

4. **Build the report (read-only, dry-run):**
   `python3 -m pv_backfill.cli report --root <DIR> [--root <DIR> ...] --workdir <BUILD_DIR>`
   Writes `report.txt`, `report.json`, `state.json` under the workdir. The report is the
   deliverable: executive summary, realistic-yield line, report-only reasons (plain
   language), higher-risk decisions, grouping by workspace, reconciliation balance.

5. **Show the report** to the user. Lead with the realistic-yield line. Nothing has changed.

6. **Resolve the marker-name fork (open question #1, DESIGN §11)** before any real write:
   v2 emits `ai-origin:backfilled` (creation-only; makes no claim about human review).
   Confirm that, or switch the one constant `MARKER_STATE` in `pv_backfill/mark.py` to
   `ai-suggestion:unverified` if the user prefers the existing grammar. Surface it; don't decide it.

7. **Apply, group-by-group, dry-run first** (git-only by default; non-git held back):
   `PV_SESSION=<this-session> python3 -m pv_backfill.cli apply --workdir <BUILD_DIR>`   (dry-run)
   add `--apply` to write; `--workspace <path>` to scope to one group; `--include-non-git`
   to also apply the two-signal non-git marks. Each write run creates a backup + manifest.

8. **Report** what changed per group, and the restore / unmark commands:
   `python3 -m pv_backfill.cli restore <run-id>` · `python3 -m pv_backfill.cli unmark <path> [--apply]`

## Notes
- Idempotent: re-runnable; structurally skips already-marked files; safe to resume (state.json).
- Strict success-join: a write counts only when its `tool_use_id`/`call_id` result is present
  and not `is_error` (failed writes are never counted as touches).
- Channels mined: Claude `Write/Edit/MultiEdit/NotebookEdit`, narrow Bash heredocs, mv/cp
  edges, `~/.claude/file-history/@vN` snapshots; Codex `apply_patch` (Add/Update) across
  nested + flat-legacy + archived sessions; subagent transcripts as first-class.
- Reconciliation is a BLOCKER: every scanned path must land in exactly one bucket or the run aborts.
- Tests: `python3 tests/test_v2.py` (replay fixtures, the CLAUDE.md trap, the inversion gate,
  marker round-trip, secret quarantine).
