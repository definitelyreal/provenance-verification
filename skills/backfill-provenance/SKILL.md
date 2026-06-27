---
name: backfill-provenance
description: Retroactively mark provenance across existing files by reconstructing what AI did from Claude Code + Codex (+ Gemini) chat history, per the provenance-verification standard. Comprehensive, conservative, and restorable. Use when asked to "backfill provenance", "mark existing AI files", "tag what AI wrote", or before adopting the standard on an existing project.
---
<!-- ai-suggestion:unverified | session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 | date:2026-06-27 -->

# backfill-provenance

**Primary output is a report** — an inventory of un-provenanced AI artifacts with the evidence recovered for each. Marking is a conservative, hard-gated *subset* (auto-marking is the exception, not the headline: without version-control trees, a content hash-match cannot prove a file is still AI-untouched — see `DESIGN.md`). Reconstruct *what AI did* from chat history, classify, confirm with the user, then mark only the provable subset — reversibly.

**Status — v1 preview.** These scripts are a working preview; the authoritative, adversarially-hardened spec is `DESIGN.md` (3 rounds, 2 Opus + 2 Codex). Preview covers and has been proven: Claude `Write/Edit/MultiEdit/NotebookEdit` scanning, conservative `ai-suggestion:unverified` inventory, and apply with backup + `--restore` (dry-run default). **Not yet implemented (v2, per DESIGN.md):** the Bash-heredoc and `~/.claude/file-history/@vN` content channels (the *dominant* write sources on this machine), strict `tool_use_id` success-join (so failed writes aren't counted as touches), and the inversion / two-independent-signals gate. Until then, treat the inventory as **incomplete (under-counts)** and confidence as path-touch only.

Scripts live beside this file. The reference recognizer is at `../../reference/provenance.py`.

## Invariants (never violate)
- **Never write `verified`.** Backfill marks origin + `:unverified` only. A human/gate flips to verified later.
- **Conservative default:** ambiguous origin → `ai-suggestion:unverified` (lowest trust).
- **Never clobber** an existing marker; skip already-marked files.
- **Backup + manifest before any write; restorable.** Default is dry-run.
- **Two attributions, not one:** the marker records the *original* session that wrote the file; the manifest records *this* backfill session.

## Flow

1. **Announce** what you're about to do, in plain terms. Don't work silently.

2. **Choose surfaces.** Ask which surfaces to work on, or take what the user specifies. Default = comprehensive across approved paths. Skip credential/quarantined paths and `.gitignore`d files. (v1 surfaces: filesystem dirs/repos — markdown + code. Sheets/Docs are designed; wire when needed.)

3. **Scope & estimate.** Run the scanner read-only to size it:
   `python3 history_scan.py --root <SURFACE> --json scan.json`
   Report the candidate volume, then **propose a number of agents + a token budget + ETA and confirm before any fan-out.** Parallelize inventory by sub-directory/surface for large scopes.

4. **Build the inventory (read-only):**
   `python3 inventory.py --root <SURFACE> --json inventory.json`
   Each item: path, medium, status (`candidate` / `already-marked` / `missing` / `skip-other`), proposed marker, confidence, engines, original sessions, last touch.

5. **Show the inventory** to the user, grouped by status / confidence / sub-folder, with counts. Nothing has changed yet.

6. **Resolve load-bearing questions — but minimize prompts.** Check every load-bearing call by default, but FIRST propose 1–3 **universal rules** that cover the bulk, e.g. *"every `candidate` written by an AI session, high confidence → `ai-suggestion:unverified`; apply to all N?"* Get a yes per rule; only residual items get individual (batched) prompts. Also ask the two recorded preferences if relevant: **rename `.md`→`.ai.md`?** (default no; soft `.ai` infix keeps either resolvable) and **sheets marking scheme** (`:Provenance` column default).

7. **Apply, group-by-group.** Dry-run first, then apply per approved group (folder by folder / surface by surface):
   `PV_SESSION=<this-session> python3 apply.py --inventory inventory.json --confidence high`   (dry-run)
   add `--apply` to write. Each run creates `backups/<run-id>/` + `changes.jsonl`.

8. **Report** what changed per group, and the restore command:
   `python3 apply.py --restore <run-id>`

## Notes
- Idempotent: re-runnable; skips already-marked; safe to resume.
- `history_scan.py` mines Claude Code `tool_use` Write/Edit (session-attributed) and Codex rollout file-paths; Gemini best-effort.
- Confidence: `high` = an AI `Write` event exists; `med` = edits only. Default applies `high` first; review `med` before applying.
- A human-authored git commit after the last AI touch is a signal the file may be human-owned — surface such files as *candidates for human verification*, never auto-mark them.
