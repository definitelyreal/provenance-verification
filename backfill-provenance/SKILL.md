---
name: backfill-provenance
description: Retroactively mark AI provenance across a project's existing files by reconstructing what AI authored from chat/git history and file evidence, per the provenance-verification standard. A conservative, human-gated, reversible process — not a tool. Use when asked to "backfill provenance", "rescan and mark what AI wrote", "audit provenance", "tag existing AI files", or before adopting the standard on an existing project.
---
<!-- ai-suggestion:unverified | session:715279ef-4d0d-4864-ba13-20b0a5801ec3 | date:2026-06-29 -->

# backfill-provenance

A **process** an agent follows to retroactively mark provenance on a project that predates the standard. There is no tool to run — you do the work: enumerate the files, decide what AI authored, show the user, then mark the provable subset reversibly with the user's go-ahead. The full standard is [provenance-verification.md](../provenance-verification.md); read it first for the marker grammar.

This process is grounded in a real audit (RG Collab, 2026-05-24) that found AI-surfaced facts had drifted from human truth. Two principles came out of it and govern everything below:

1. **AI never marks its own work `verified`.** Backfill only ever writes `unverified`. Promotion to `verified` needs a human or the adversarial gate — never the agent doing the backfill.
2. **Provenance is context-scoped, not global.** A file can be canonical for one use and stale for another. Don't collapse "dropped from one deliverable" into "wrong everywhere." When you mark, mark what you actually know.

## Stance: marking is a recall-biased quarantine
The marker says "a human didn't write this," so AI output isn't mistaken for human-verified truth. It is allowed to be wrong: over-flagging a human file is cheap (a human clears it); the expensive error is *missing* an AI file, which then reads as trusted. So bias toward catching AI files. Mark generously on origin, but only `unverified`, and make every write reversible.

## The process

### 1. Announce and scope
Say what you're about to do, in plain terms. Confirm the roots to scan and the surfaces in play (filesystem markdown + code is the core; Sheets/Docs/Slack are report-only unless the user asks you to mark them by hand). Never work silently; never auto-mark without showing the user first.

### 2. Inventory (read-only)
Enumerate every artifact in scope. For a large project, fan out parallel sub-agents — one per workspace/root — each writing its findings to its own file so you don't blow context. For each file record: path, size, last-modified, and a one-line provenance note. **Do not hydrate cloud-sync 0-byte placeholders** (Dropbox/iCloud/OneDrive) — note them as "placeholder" from `ls`/`find` metadata only; only read files that are already hydrated. Sample and infer for big trees; don't read every byte. Write the inventory and any working files to a stable non-temp location (a `build/` dir or `~/.claude/tmp/`), **never `/tmp`** — it gets wiped and is invisible to later sessions.

### 3. Classify each file → `human` / `ai` / `mixed-or-unclear`
Use file evidence first, then corroborate with history. Signals that actually work:

**AI-authored:**
- `.ai.md` extension, or an existing marker (`ai-suggestion`, `ai-processed`, legacy `ai:suggestion`/`<!-- ai... -->`)
- Lives under a `build/`, `draft/`, or work-session path
- Filename carries a timestamp prefix or `draft` / `v1` / `ai-generated`
- A creation event for the file appears in chat/git history (Claude `Write`, Codex `Add File`) — the strongest origin signal

**Human-authored:**
- Press releases and other shipped deliverables (often PDFs)
- Files in `final/`, `approved/`, `delivered/`; names like `FINAL`, `LOCKED`, `v.shipped`
- Human-curated machine-readable lists (rosters, configs)
- An explicit human-confirm flag in the file

**Mixed / unclear (a real bucket — do not force a guess):**
- AI synthesis of real source data → this is `ai-processed`, not `ai-suggestion`
- A human-authored file an AI only *edited* → leave it for the human to mark; never auto-invent a partial marker

Evidence base: file content + extension + folder location + existing markers + last-modified, cross-checked against **chat/git history** and the user's memory (`MEMORY.md`, prior sessions). Where you can reconstruct it, attach a confidence: **high** = AI created the file and the current bytes still match what AI wrote; **medium** = AI created it but it changed since (a human may have rewritten part). git/history *raise* confidence; they don't gate.

### 4. Triangulate against live human truth
The current human truth often lives outside the filesystem (live Google Docs, a shipped PDF, a confirmed roster). Pull those and use them to resolve contradictions before you mark — a file that disagrees with the canonical human source is `ai-*` that drifted, and worth flagging `disputed` rather than silently marking `unverified`.

### 5. Show the user the report — change nothing yet
Lead with the caveats: coverage is incomplete (list what you did NOT cover — e.g. Gemini history, connected surfaces, anything not scanned), and the counts are an inventory, not a proof every file was covered. Then: AI-authored counts by confidence (high/medium), the mixed/unclear list with reasons, and the human-canonical set. **Claim = evidence:** every AI-authored entry cites what it rests on (the creation event found in history, an existing marker, the path/name heuristic) — assert nothing without it. Nothing has changed at this point.

### 6. Mark the provable subset — human-gated, reversible, dry-run first
With the user's go-ahead, mark only files classified AI-authored, only `unverified`, using the per-medium grammar in the standard:
- Markdown → `.ai.md` + frontmatter `<!-- ai-suggestion:unverified | session:<origin-id> | date:<YYYY-MM-DD> -->` (use `ai-processed` for compiled-from-source files). Record both the *origin* session (who created the file) and *this* backfill session — never conflate them.
- Code → top-comment marker. Sheets/Docs → `:Provenance` column / inline comment + `#e3dfec` highlight, by hand.

Safety rules (non-negotiable):
- **Back up before writing**, to a stable dir outside the synced tree (e.g. `~/.claude/tmp/`, never `/tmp`); keep the change reversible and report the restore path.
- **Never write `verified`.** Only a human or the gate does that.
- **Skip** symlinks, hardlinks, files containing secrets, Dropbox placeholders, and any file changed since you classified it.
- **Never touch already-shipped artifacts** (sent messages, published PDFs). Propose corrections; do not silently rewrite what's in the wild.
- **Already-marked files are skipped** (idempotent).

### 7. Quarantine stale/duplicate content — move, don't delete
Old `v1/v2/v3` versions, conflicted copies, superseded docs that AI keeps re-ingesting: move them to `_archive/` / `_superseded/` so they stop polluting future AI reads. Moved, never destroyed — reversible.

### 8. Report what changed
Per group: what was marked, what stayed report-only and why, the NOT-COVERED list, and the exact restore/unmark steps. Hand the mixed/unclear list to the user for human marking.

## Out of scope (state as absent, never assume clean)
Gemini history; `~/.codex` memories / ambient suggestions; connected surfaces (Google Sheets/Docs/Slack/Airtable) unless marked by hand; files behind unhydrated placeholders. Renamed/moved AI files can be missed — call that out rather than implying full coverage.
