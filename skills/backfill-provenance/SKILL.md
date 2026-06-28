---
name: backfill-provenance
description: Retroactively mark provenance across existing files by reconstructing what AI did from Claude Code + Codex (+ Gemini) chat history, per the provenance-verification standard. Comprehensive, conservative, and restorable. Use when asked to "backfill provenance", "mark existing AI files", "tag what AI wrote", or before adopting the standard on an existing project.
---
<!-- ai-suggestion:unverified | session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 | date:2026-06-28 -->

# backfill-provenance (v2)

> **v0.6 model: marking is a QUARANTINE, biased toward recall.** `ai-origin:backfilled` is
> an UNVERIFIED, REVERSIBLE flag meaning "a human didn't write this," so AI output isn't
> mistaken for human-verified truth. It is allowed to be wrong: over-flagging a human file is
> cheap (a human clears it); the expensive error is MISSING an AI file. So the gate marks on
> **origin** (AI created the file), at `high` (bytes still match) or `medium` (created by AI
> but changed since) confidence. git + file-history raise confidence; they don't gate. A
> 3-round adversarial review drove this design and the safety net below (see `KNOWN_LIMITATIONS.md`).

**The primary output is a report** — an inventory of AI-origin artifacts with the evidence
recovered for each. **Marking is the gated subset** — AI-origin files only; mixed/edited files
stay report-only for a human to mark. Marking is a recall-biased quarantine (`IMPLEMENTATION_NOTES.md`
explains the model; `KNOWN_LIMITATIONS.md` is the honest status). `DESIGN.md` is the original
adversarially-hardened spec and is kept for the record, but its §2.6 two-signal/inversion gate
was **superseded** by the v0.6 quarantine model — read DESIGN as history, not current behavior.

Reconstruct *what AI did* from chat history, classify, show the user, then mark only the
provable subset — reversibly, dry-run by default.

The engine is the `pv_backfill/` package; the vendored marker grammar is `lib/provenance.py`.

## Invariants (never violate)
- **Never write `verified`.** Backfill marks `ai-origin:backfilled` (unverified) and nothing higher.
- **Mark on ORIGIN, biased toward recall.** A file is marked when there's an AI **creation**
  event for it (`Write` / Codex `Add File` / static quoted-delim heredoc): `high` confidence
  if current bytes still match what AI wrote, `medium` if AI created it but it changed since.
  The marker is a fallible, reversible quarantine flag — over-flagging a human file is the
  cheap error; missing an AI file is the expensive one.
- **git + file-history raise confidence, they do not gate.** file-history is never an origin
  signal (a snapshot can be human content, e.g. CLAUDE.md); it's a confidence corroborator.
- **Human-origin files are not marked.** A human-created file an AI only *edited* → report-only
  (a human adapts the marker later); backfill never invents a partial marker automatically.
- **Backup + manifest before any write; restorable, and restore fails loud.** Backups live
  OUTSIDE the synced tree. Symlinks/hardlinks/secret files/placeholders are skipped; a file
  changed since the report is skipped.
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
   Writes `report.txt`, `report.json`, `state.json` under the workdir. The report leads with
   the quarantine-model caveats, then: AI-origin counts by confidence (high/medium), report-only
   reasons (plain language), the NOT-COVERED list, grouping by workspace, bucket balance.

5. **Show the report** to the user. Lead with the caveats and the high/medium split. Nothing has changed.

6. **Marker name (a preference, not a blocker):** the tool marks `ai-origin:backfilled` (only on
   AI-created files; makes no claim about human review). If the user prefers the existing grammar,
   switch the one constant `MARKER_STATE` in `pv_backfill/mark.py` to `ai-suggestion:unverified`.

7. **Apply, dry-run first** (marks `high` confidence by default; reversible):
   `PV_SESSION=<this-session> python3 -m pv_backfill.cli apply --workdir <BUILD_DIR>`   (dry-run)
   add `--apply` to write; `--min-confidence medium` to also mark AI-created-but-changed
   files; `--workspace <path>` to scope to one group. Each write run creates a backup +
   manifest outside the synced tree; symlinks/hardlinks/secret files/placeholders are skipped;
   a file changed since the report is skipped (`changed-since-classify`).

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
- Tests: `python3 tests/test_v2.py` (replay fixtures, the CLAUDE.md trap, the origin gate + confidence, the safety net,
  marker round-trip, secret quarantine).
