<!-- ai-processed:unverified | session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 | date:2026-06-28 -->
# backfill-provenance v2 — implementation notes & evidence-backed deviations from the original design

> **v0.6 model update (supersedes the original design's §2.6 gate philosophy, now in `DESIGN.history.md`).**
> A 3-round adversarial review showed that precision-first gate optimized the wrong asymmetry. The marker
> `ai-origin:backfilled` is an **unverified, reversible quarantine flag**, so the tool should
> be **recall-biased**: over-flagging a human file is a cheap, reversible false positive, while
> MISSING an AI file (it then reads as human-trusted) is the expensive error. v0.6 therefore
> marks on **origin** (an AI creation event) at `high`/`medium` confidence; git + file-history
> are confidence annotations, not gates. The old two-signal/inversion gate is gone. What makes
> this safe is the **data-integrity safety net** (reversibility + never harming other files),
> not authorship precision — see `KNOWN_LIMITATIONS.md`. Deviation 1 below still stands;
> Deviation 2 was retracted in v0.5.1 and is moot under this model.

`DESIGN.history.md` is the original spec. While verifying its disk-fact ledger against this
machine before writing parsers (Claim=Evidence), two findings **refined** the evidence model. They are
recorded here so the divergence is auditable, not silent.

## Deviation 1 — `file-history @vN` snapshots are PATH-attributed BASE states, not opaque content-hash AI-origin signals

DESIGN.history §2.1 / §2.4 say the `<hash>@vN` snapshot file name is "an opaque content hash,
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
  (the named human-authored trap, DESIGN.history §2.4a) has snapshots — they are human content.
  Treating "disk == some snapshot" as AI-origin would launder exactly the trap the spine
  exists to protect. PROOF: `CLAUDE.md @v1` sha `c4a2fb76…` (33,759 B) ≠ on-disk
  `50c0d9f4…` (35,896 B) — the snapshot is an older state, and its *content* is the human
  file, not an AI creation.

**v2 role for file-history (corrected):** a path-attributed **recoverable base-state and
content-continuity store** (DESIGN.history §2.4b base-source #2) and a **path-touch / second-signal
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
no Codex equivalent. So the non-VCS two-signal gate did not provide independence. It was
disabled in v0.5.1 and **removed entirely in v0.6**, which abandoned the precision-first
"prove the file is still untouched" framing for the recall-biased quarantine model in the
banner above (the marker is fallible and reversible, so a second signal isn't needed to mark;
git/file-history only raise confidence).

Deviation 1 (file-history is a path-attributed *base/continuity* store, not an origin
signal) stands and is in fact the correct framing — Deviation 2 was the inconsistent half.

## Status vs the original design (what is and isn't implemented)
Implemented: strict `tool_use_id`/`call_id` success-join (§2.2, with the known bugs in
`KNOWN_LIMITATIONS.md`); creation + replay-to-disk as the positive gate (§2.4a, no fragment
matching); narrow Bash-heredoc eligibility (§2.1); Codex nested/flat-legacy/archived adapters
(§3.2); subagent transcripts (§3.2); backups outside the synced tree + restore + unmark
(§4, §7); Dropbox placeholder guard (§6); report-primary, dry-run default (§8.2);
`ai-origin:backfilled` constant (§4, open-q #1).

Also implemented in v0.6: the origin gate with `high`/`medium` confidence; the write-race
sha guard, restore-fail-loud, symlink/hardlink skip, unique run-id, structural unmark, and
secret-file skip (the data-integrity safety net that makes reversible marking safe); Codex
per-call cwd resolution.

**NOT implemented / removed — see `KNOWN_LIMITATIONS.md` for the full list:** §3.6
delete/recreate segmentation (absent; an earlier draft wrongly claimed it was done), §3.4
move/copy survival (parsed, not propagated — the one gap that can *miss* an AI file), the §2.6
two-signal/inversion gate (removed in v0.6), §0 grammar-drift guard, §8.8 resume-shows-choices,
§7.1 scan-before-hash ordering, §3.5 append marker block, several named-but-never-emitted
abstention classes, Gemini coverage, and the reconciliation BLOCKER (balance-only).

---
_Claude · 2026-06-28 · Session: 6ab1c2ae-25dd-40bf-9ca2-05072ee58b83_
