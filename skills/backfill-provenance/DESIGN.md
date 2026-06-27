<!-- ai-suggestion:unverified | session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 | date:2026-06-27 -->
# backfill-provenance — skill design (v1, pre-adversarial-review)

A skill that retroactively marks provenance across a user's existing artifacts, reconstructing what AI did from chat history + file/git history, per the `provenance-verification` standard. Comprehensive by default, conservative by default, restorable by default.

> v1 seed for adversarial review. Will be hardened into `SKILL.md` + `history_scan.py`.

## 1. Purpose
Most of a user's existing files were written before any provenance discipline existed. This skill goes back through the record of what AI actually did and applies the standard's markers retroactively — so the un-marked backlog stops reading as human-verified truth.

## 2. Evidence sources (how it reconstructs "AI touched X")
Ranked by strength:
1. **Claude Code JSONL** — `~/.claude/projects/<encoded-cwd>/<session>.jsonl`. Each line has `sessionId` + `timestamp`. Mine `tool_use` events `Write`/`Edit` (→ `file_path`) and `file-history-snapshot` events. Yields `(file, session, engine=claude, tool, timestamp)` tuples. Strongest signal.
2. **Codex JSONL** — `~/.codex/archived_sessions/rollout-*.jsonl` (+ `history.jsonl`, `session_index.jsonl` id→thread). Mine file edits codex made. Yields the same tuple shape, `engine=codex`.
3. **Gemini** — `~/.gemini/` if present (optional).
4. **git history** — where a path is in a repo: `git log --follow` per file → commit authors (human vs AI co-author trailers like `Co-Authored-By: Claude`), commit times. Disambiguates human-vs-AI authorship and gives a verification anchor (a human commit ≈ human-touched).
5. **Filesystem mtimes** — weakest; only orders events when history is absent. (Dropbox version history is API-gated; out of scope v1, noted.)
6. **Existing markers** — files already carrying a marker / `.ai.md` / session-attribution footer are detected via `reference/provenance.py` and skipped.

## 3. Flow (user-directed, comprehensive by default)
1. **Announce** what it will do (visible progress; no silent work).
2. **Choose surfaces** — ask which surfaces to work on, or the user specifies. Defaults to *all configured surfaces* (comprehensive). Surfaces = filesystem dirs/repos, Google Sheets, Google Docs, Slack — per the standard's media table. Honors the user's `enforce_paths`/scope and skips quarantined/credential paths.
3. **Scope & estimate** — scan history to estimate candidate volume, then **suggest a number of agents and a token budget** and check with the user before any fan-out. Parallelize the inventory by surface/dir.
4. **Build inventory (READ-ONLY)** — cross-reference history tuples with files on disk. Classify each candidate:
   - `already-marked` → skip (via provenance.py)
   - `ai-authored, no human edit since` → `ai-processed:unverified` (compilation of source) or `ai-suggestion:unverified` (AI's own content) per the heuristic in §4
   - `ai-edited a human file` → inline/section marking or flag
   - `human-authored` (no AI session touched it) → no marker
   - `ambiguous` → load-bearing question
   Each candidate carries: path, evidence (session id(s), timestamps, engine, tool, git authors), proposed marker, confidence, surface.
5. **Show the inventory** — grouped by surface / proposed action / confidence, with counts. Nothing changes yet.
6. **Resolve load-bearing questions — but minimize prompts.** Check on every load-bearing question by default; BUT first propose 1–3 **universal rules** that cover the bulk (e.g. "every file written by a Claude/Codex session with no later human edit → `ai-processed:unverified`; apply to all 214?"). The user approves each universal rule; only residual items that don't fit get individual (batched yes/no) prompts.
7. **Execute as directed** — apply markers, offered **group-by-group** (folder by folder, by surface, by domain — whatever grouping fits the user's material) so they approve in digestible batches rather than all-at-once. Comprehensive by default.
8. **Report** — what changed, with the restore command.

## 4. Classification heuristic (origin type)
- A file whose content is a compilation/transform of real source data (extraction, transcript, dedup, enrichment, report over inputs) → `ai-processed`.
- A file that is the AI's own ideas/inference/draft/generated list → `ai-suggestion`.
- When unsure between the two → `ai-suggestion` (the lower-trust, more-conservative tier).
- **Status is ALWAYS `unverified` on backfill.** Backfill marks origin; it never verifies. Only a later human/gate flip can reach `verified` (a human-authored git commit may be surfaced as a *candidate* for human verification, never auto-applied).

## 4a. The marking operations per medium (what it actually does)
- **Markdown:** insert frontmatter `<!-- ai-processed:unverified | session:<original-session> | date:<YYYY-MM-DD> | asof:<mtime> -->` at the top. The standard's *filename* marker is the `.ai.md` extension, but renaming retroactively breaks inbound references (relative links, CLAUDE.md `@import`s, build scripts). **Default = frontmatter-only, NO rename.** Backfill **asks up front whether the user wants `.ai` renames at all**; it never renames without that yes. When yes, rename only where no inbound references exist (or the user accepts), and the soft `.ai` infix (SPEC §0) keeps even renamed files resolvable either way. Every rename is logged for restore.
- **Code files:** insert a top-of-file comment marker (`# ai-…:unverified · session:<id> · <date>`), placed after any shebang line.
- **Google Sheets:** **ask the user's marking preference and record it** in `user.local.md` (default: a `:Provenance` companion column vs. an alternative scheme). Then write `ai-…:unverified <date> <short-id>` on AI-touched rows per that preference; highlight touched cells `#e3dfec` (light purple).
- **Google Docs:** prepend `<!-- ai-…:unverified -->` above the AI block; highlight; attach a comment with the full session id.
- **Slack / messages:** generally not retroactively editable → **report-only** (list, never mutate).
- **Always:** content is otherwise untouched (marker only); the change is recorded to the backup + change-manifest.

## 5. Attribution (two distinct facts)
- **Original maker:** the historical `sessionId` (+ engine) that wrote the file, embedded in the marker (`session:<id>`).
- **Backfill marker:** the session that *added* the marker, recorded in the change-manifest (not conflated with the original). So the record never claims the backfill run authored the content.

## 6. Backup / restore (default on)
Before any write:
- Snapshot originals to a backup dir (`backfill-provenance/backups/<run-id>/`), AND
- Append to a **change-manifest** `changes.jsonl`: `{path, op, before_sha256, after_sha256, marker_added, original_session, backfill_session, surface, at}`.
- Provide a `--restore <run-id>` that reverts from the backup/manifest.
- For non-file surfaces (Sheets/Docs), the manifest records before/after cell/marker values for manual or API revert.
Default on; cannot be silently disabled.

## 7. Safety guardrails
- Read-only inventory first; **no writes until the user directs**.
- **Never** overwrite/clobber an existing marker; never downgrade a human or verified marker.
- **Never** write `verified` (backfill cannot verify).
- Conservative default (`ai-suggestion:unverified`) on ambiguity.
- **Idempotent** — re-runnable; skips already-marked; safe to resume.
- Skip credential/quarantined/sensitive paths and anything in `.gitignore` by default.
- Surface-scoped to user-approved surfaces only.

## 8. Agent / budget estimation
From the history scan, estimate candidate count, then propose: N agents (≈ one per surface or per ~K files), a token budget, and an ETA. Confirm before fan-out. Inventory and apply phases parallelize by surface/dir.

## 9. Components
- `history_scan.py` — parses Claude Code + Codex (+ Gemini) JSONL into a normalized `ai_touch_events` table `(file, session, engine, tool, timestamp)`; dedups; resilient to schema variation/corrupt lines.
- `inventory.py` — joins touch-events with on-disk files + git + existing markers → `inventory.json`.
- `SKILL.md` — orchestrates: announce → surfaces → estimate+confirm → inventory → show → universal-rules+questions → apply → report. Uses `reference/provenance.py` for detect/normalize/write.
- Installed via the repo `install.sh` (symlink into `~/.claude/skills/`).

## 10. Open questions for review
- Schema drift across Claude Code / Codex versions — how robust is the parser?
- Confidence calibration: when is "AI touched it" strong enough to mark vs. flag?
- Marking files inside git repos (does adding a marker create noisy diffs / churn)?
- Non-file surfaces (Sheets/Docs) backup/restore fidelity.
- Performance over 116 projects × many sessions.
