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

## Deviation 2 — RETRACTED (the two-signal non-VCS gate was unsound)

The original v0.5.0 version of this section claimed file-history could serve as a second
*independent* signal: Signal A = a chat-log creation body matching disk, Signal B = a
file-history snapshot of the same bytes. **A 3-round adversarial review (build/redteam/)
proved this false and the claim is withdrawn.** file-history is Claude Code's *own pre-edit
undo buffer*, emitted by the same engine and session as the write — Signal A and Signal B
are two recordings of ONE operation, not two independent attestations. file-history also has
no Codex equivalent. So the non-VCS two-signal gate does not provide independence, and it is
**disabled** in v0.5.x along with all auto-marking (see `KNOWN_LIMITATIONS.md`). The only
genuinely independent second signal identified is git-history authorship; re-founding the
gate on it is deferred to v0.6.

Deviation 1 (file-history is a path-attributed *base/continuity* store, not an origin
signal) stands and is in fact the correct framing — Deviation 2 was the inconsistent half.

## Status vs DESIGN.md (what is and isn't implemented)
Implemented: strict `tool_use_id`/`call_id` success-join (§2.2, with the known bugs in
`KNOWN_LIMITATIONS.md`); creation + replay-to-disk as the positive gate (§2.4a, no fragment
matching); narrow Bash-heredoc eligibility (§2.1); Codex nested/flat-legacy/archived adapters
(§3.2); subagent transcripts (§3.2); backups outside the synced tree + restore + unmark
(§4, §7); Dropbox placeholder guard (§6); report-primary, dry-run default (§8.2);
`ai-origin:backfilled` constant (§4, open-q #1).

**NOT implemented / unsound — see `KNOWN_LIMITATIONS.md` for the full list:** §3.6
delete/recreate segmentation (absent; an earlier draft wrongly claimed it was done), §3.4
move/copy survival (parsed, not propagated), the §2.6 two-signal gate (unsound, disabled),
§0 grammar-drift guard, §8.8 resume-shows-choices, §7.1 scan-before-hash ordering, §3.5
append marker block, several named-but-never-emitted abstention classes, Gemini coverage,
and the reconciliation BLOCKER (balance-only). Auto-marking is frozen until v0.6.

---
_Claude · 2026-06-28 · Session: 6ab1c2ae-25dd-40bf-9ca2-05072ee58b83_
