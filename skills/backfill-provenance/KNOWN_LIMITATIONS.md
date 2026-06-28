<!-- ai-processed:unverified | session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 | date:2026-06-28 -->
# backfill-provenance v0.5.x — known limitations (honest status)

A 3-round adversarial review (2 Opus + 2 Codex per round; repros under `build/redteam/`)
found that the **marking** path can launder human content. **Auto-marking is frozen in
v0.5.x.** The **report** is the deliverable; it is provisional and prints its own caveats.
This file marks absent features as absent so nothing here reads as more done than it is.

## Marking is DISABLED
`apply` refuses to write unless `--experimental-unsafe-marking` is passed, and that flag is
known-unsafe. Re-enabling marking is deferred to a deliberate v0.6 that re-founds the gate
(see "Why marking is unsafe" below). `restore` and `unmark` still work.

## Confirmed ways the OLD gate could mark a human file (all with running repros)
- **Two-signal independence is an illusion.** The non-git gate required (A) a chat-log
  creation body matching disk AND (B) a file-history snapshot of the same bytes. But
  file-history is Claude Code's *own pre-edit undo buffer*, emitted by the same engine and
  session as the write — A and B are two recordings of ONE operation, not independent
  attestations. (This retracts IMPLEMENTATION_NOTES "deviation 2".)
- **Git path over-trusts `.git`.** `in_vcs()` returns true for any file under an ancestor
  `.git`, including gitignored/untracked files, stray repos, bare repos, and `.git`-as-file
  (submodule/worktree). "Version control records human edits" is false for those.
- **Reversion trap.** A human who edits an AI-created file then reverts it to byte-identical
  AI output leaves no trace in the AI log; a log-only reconstruction is structurally blind
  to any human edit that round-trips the bytes.
- **Apply-phase write-race guard is a no-op.** It compared the current disk hash to itself,
  so a file a human rewrote between `report` and `apply` would be marked with the human's bytes.
- **Codex output has no second signal at all** (no file-history equivalent), so it could
  never be honestly marked under the two-signal rule.

## Features named in DESIGN.md but NOT implemented in v0.5.x (absent, not assumed-done)
- **§3.6 delete/recreate segmentation** — NOT implemented. A creation body from before a
  delete stays eligible. (IMPLEMENTATION_NOTES previously claimed this was implemented; that
  claim was wrong and has been corrected.)
- **§3.4 move/copy survival** — `mv`/`cp` edges are parsed but `graph` does not propagate
  origin across a rename, so renamed AI files are missed (false negative).
- **§0 grammar-drift guard** — only self-hashes; no compare against a `trust-kernel` copy.
- **§8.8 resume "shows prior choices"** — state is checkpointed, but prior approvals are not
  surfaced on resume.
- **§7.1 content secret-scan "before any byte/hash is persisted"** — the scan runs only in
  the (now frozen) apply path, after the report pipeline already hashed bytes. Order is wrong.
- **§3.5 multi-session append marker block** (`edit:` / `current-writer:` lines) — the
  renderer emits a single origin line only.
- **Abstention classes** named in `classify.PLAIN` / DESIGN but never emitted:
  `missing_prior_state`, `result_ambiguous`, `quarantined`, `duplicate_content`, `log_gap`,
  `partially_corrupt_log`, `cwd_unresolved` (the last four aren't even in `PLAIN`).

## Coverage gaps (the report says "NOT COVERED", never "complete")
- **Gemini** history has no adapter (it is named in the skill description).
- `~/.codex` `memories` / `ambient-suggestions` / `computer-use` are not audited.
- `codex:flat-legacy` is globbed non-recursively.

## Other confirmed correctness / safety bugs (apply path; relevant when unfrozen)
- Strict id-join: duplicate Claude `tool_use_id` overwrites pending (crafted-only on real
  logs); a missing `is_error` is treated as success.
- Codex success is inferred from output substrings, not the call's status/exit code.
- Codex relative paths resolve against the session's *final* cwd, not cwd-at-call-time.
- Same-session replay matches session but not engine (a Codex patch could chain onto a
  Claude creation); cross-log `seq` is used as a global tiebreaker.
- Restore returns success (rc 0) after a hash mismatch or a missing backup blob.
- `shutil.copy2` follows symlinks; hardlinks (`st_nlink > 1`) are unguarded → out-of-scope
  mutation that restore cannot undo.
- Secret scan misses short/JWT/low-entropy keys and anything past byte 20,000; a naive
  full-file scan instead over-quarantines ordinary docs (commit hashes, checksums).
- `run_id` is seconds-granular → a second apply in the same second can overwrite the first
  manifest.
- `is_marked` matches bare marker vocabulary in prose, so this standard's own docs read as
  already-marked.
- Reconciliation BLOCKER is unreachable-by-construction (bucket balance only; duplicate
  paths double-count).

## Dogfood integrity
The engine's own source files carry `ai-processed:unverified` markers added at creation, and
several would be quarantined (secret-like prefixes) or skipped (vocabulary) by the tool
itself. So a self-run "looks clean" while skipping part of its own corpus. Do not read the
green unit suite (32 tests) as coverage of the above: none of its tests exercised the
laundering paths.

---
_Claude · 2026-06-28 · Session: 6ab1c2ae-25dd-40bf-9ca2-05072ee58b83_
