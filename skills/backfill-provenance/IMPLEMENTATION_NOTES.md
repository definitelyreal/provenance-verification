<!-- ai-processed:unverified | session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 | date:2026-06-28 -->
# backfill-provenance v2 — implementation notes & evidence-backed deviations from DESIGN.md

`DESIGN.md` is the source of truth. v2 implements it. While verifying the DESIGN's
disk-fact ledger against this machine before writing parsers (Claim=Evidence), two
findings **refined** the evidence model. Both make v2 *more* conservative than the
DESIGN, never less — the right direction for a provenance tool. They are recorded here
so the divergence is auditable, not silent.

## Deviation 1 — `file-history @vN` snapshots are PATH-attributed BASE states, not opaque content-hash AI-origin signals

DESIGN §2.1 / §2.4 say the `<hash>@vN` snapshot file name is "an opaque content hash,
not a path … attribution is content-hash-match only," and that a snapshot hash-match to
disk "**is** hash-continuity (§2.4) … the primary mechanism that lets the skill mark
Edit-heavy … files." Verified on disk, both halves are wrong in a way that matters:

- **The id is a stable PATH hash, not a content hash.** `3a95057e73af895f` is the id for
  `~/.claude/CLAUDE.md` in *every* session that touched it (8+ session dirs carry
  `3a95057e73af895f@v1..@vN`), and it is 16 hex chars, not a 64-char sha256. The `@vN`
  suffix is a per-session sequence. PROOF:
  `find ~/.claude/file-history -name '3a95057e73af895f@v*'` → same id across
  `dfa8692d…`, `0f1af029…`, `bc7f7136…`, etc.
- **Snapshots are path-attributable WITHOUT content matching.** Each project JSONL carries
  `file-history-snapshot` records whose `snapshot.trackedFileBackups` maps an **absolute
  path → {backupFileName:"<id>@vN", version, backupTime}**. PROOF:
  `…/CLAUDE.md → {backupFileName:'3a95057e73af895f@v1', version:1}`. So we resolve a
  snapshot to its real path via the log, not by guessing from a content hash.
- **A snapshot does NOT prove AI authorship.** file-history is Claude Code's pre-edit undo
  store: `@vN` is the state captured as the *base* before a tracked change. `CLAUDE.md`
  (the named human-authored trap, DESIGN §2.4a) has snapshots — they are human content.
  Treating "disk == some snapshot" as AI-origin would launder exactly the trap the spine
  exists to protect. PROOF: `CLAUDE.md @v1` sha `c4a2fb76…` (33,759 B) ≠ on-disk
  `50c0d9f4…` (35,896 B) — the snapshot is an older state, and its *content* is the human
  file, not an AI creation.

**v2 role for file-history (corrected):** a path-attributed **recoverable base-state and
content-continuity store** (DESIGN §2.4b base-source #2) and a **path-touch / second-signal
corroborator** (§2.6) — never, by itself, an origin signal. **AI-origin always requires a
creation event with a literal body** (`Write` / Codex `Add File` / static quoted-delimiter
heredoc) at the root of the matched chain. A chain rooted in a snapshot/human base routes to
`mixed_authorship` / report-only. This preserves the DESIGN's intent (recover Edit-heavy
files) via *creation-body + replay-to-disk*, without the laundering risk.

## Deviation 2 — second independent signal (§2.6) is grounded in file-history, consistent with Deviation 1

DESIGN §2.6 asks for two independent non-VCS signals: (i) a whole-file hash-match proving
AI emitted the bytes, AND (ii) a corroborator. v2 implements:

- **Signal A:** a §2.4 whole-file match — disk sha equals an AI **creation body** (direct),
  or equals the result of replaying the AI edit chain **from a creation body** to disk.
- **Signal B (independent store):** the same on-disk bytes are *independently* recorded in
  `~/.claude/file-history` as a snapshot of that same path (sha match), i.e. a second,
  separately-written store agrees the file currently holds AI-emitted bytes — **plus** an
  mtime-in-session-window check with no later-gap that would suggest a post-AI human save.

Signal A is the chat-log attestation; Signal B is the file-history attestation. They are
written by different subsystems, so agreement is genuinely two independent signals. One
alone in a treeless Dropbox tree never auto-marks (DESIGN §2.6) → `non_git_single_signal`.

## Everything else implements DESIGN.md as written
Strict `tool_use_id`/`call_id` success-join excluding `is_error:true` (§2.2); creation +
replay-to-disk as the sole positive gate (§2.4a, no fragment matching); per-path content
segments split on delete/recreate (§3.6); move/copy edges (§3.4); narrow Bash-heredoc
eligibility (§2.1); Codex nested `{timestamp,type,payload}` + flat-legacy whole-document +
archived adapters (§3.2); subagent transcripts as first-class (§3.2); abstention classes
named + counted (§2 table); reconciliation balance is a BLOCKER (§10); backups outside the
synced tree + restore + unmark (§4, §7); secret quarantine glob+content scan (§7.1);
Dropbox placeholder guard (§6); dry-run default, report-primary (§8.2); `ai-origin:backfilled`
creation-only marker (§4, open-q #1 — surfaced for confirmation, isolated as one constant).

---
_Claude · 2026-06-28 · Session: 6ab1c2ae-25dd-40bf-9ca2-05072ee58b83_
