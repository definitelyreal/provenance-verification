<!-- ai-processed:unverified | session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 | date:2026-06-28 -->
# backfill-provenance v0.6 — known limitations (honest status)

A 3-round adversarial review (2 Opus + 2 Codex per round; repros under `build/redteam/`)
drove this design. The headline outcome was a **reframing**, not just bug fixes.

## The model: marking is a QUARANTINE (recall-biased, fallible, reversible)
`ai-origin:backfilled` is an **unverified, reversible** flag meaning "a human didn't write
this file," so AI output isn't mistaken for human-verified truth. The asymmetry that matters:
- **Over-flagging a human file is cheap** — it's an `:unverified` flag; a human glances and
  clears it. Acceptable.
- **Missing an AI file is the expensive error** — it then reads as human-written and trusted.

So the gate is biased toward **recall**: it marks on **origin** (an AI creation event for the
file), at `high` confidence (current bytes still match what AI wrote) or `medium` (AI created
it but it changed since — a human may have rewritten part). git and file-history *raise
confidence*; they do not gate. A file a human created and AI only edited stays **report-only**
(its origin is human; backfill can't auto-produce a correct partial marker — a human adapts it
later).

## "Laundering" findings, reframed (acceptable over-quarantine, not bugs)
The review found several ways a human file could be marked AI. Under the quarantine model
these are tolerated false-positives (a human clears them), not failures:
- Reversion trap (human reverts a file to byte-identical AI output).
- A file under a git tree whether or not it's tracked / ignored.
- AI-created-then-human-rewritten (caught as `medium` confidence by design, flagged for review).

These would only matter if `ai-origin:backfilled` were ever read as authoritative truth — it
must not be (spec: unverified AI markers are never citable facts; a human or the gate clears them).

## Safety net (FIXED in v0.6 — these make generous, reversible marking safe)
Because the safety argument is "mark freely, it's undoable and never harms anything else,"
the data-integrity bugs were the real prerequisites and are fixed + tested:
- **Write-race:** the report-time content-sha is persisted in `state.json`; `apply` compares
  the file to *that* and skips `changed-since-classify` if it differs (was a no-op before).
- **Restore fails loud:** a hash mismatch or a missing backup blob returns nonzero and reports
  the file as not restored (was silently rc 0).
- **No write-through a link:** symlinks (final or via a parent dir) and hardlinked files
  (`st_nlink > 1`) are skipped; writes use `O_NOFOLLOW`.
- **Placeholder guard** runs unconditionally (a nonzero Dropbox placeholder is not read).
- **Secret files skipped** by glob + whole-file content scan (known prefixes, JWTs,
  secret-named assignments); tuned to skip credentials without over-quarantining ordinary
  docs (commit hashes / checksums no longer trip it).
- **Unique `run_id`** (random suffix) + refuse to overwrite an existing manifest.
- **`unmark` is structural** — removes only a line that is *itself* a marker comment, never a
  line that also carries content.
- **Codex relative paths** resolve against the cwd in effect *at that call* (per-item), not
  the session's final cwd (was a wrong-file bug).
- verify-after-write requires **exactly one** backfill marker.

## Still absent / not implemented (marked absent, not assumed-done)
- **§3.6 delete/recreate segmentation** — not implemented. A creation body from before a
  delete can still match disk. Under the quarantine model this only risks over-flagging
  (acceptable); still worth doing for precision.
- **§3.4 move/copy survival** — `mv`/`cp` edges are parsed but origin is not propagated
  across a rename, so a renamed AI file can be missed (a recall gap — the one error type the
  model actually cares about; flagged for a follow-up).
- **§0 grammar-drift guard** (vs a `trust-kernel` copy), **§8.8 resume-shows-prior-choices**,
  **§7.1 scan-before-hash ordering** (secret scan still runs in the apply path, not the report
  pipeline), **§3.5 multi-session append marker block** — not implemented.
- **Abstention classes** named in `classify.PLAIN` / DESIGN but never emitted:
  `missing_prior_state`, `result_ambiguous`, `quarantined`, `duplicate_content`, `log_gap`,
  `partially_corrupt_log`, `cwd_unresolved`.
- **Coverage gaps:** Gemini has no adapter; `~/.codex` memories/ambient/computer-use aren't
  audited; flat-legacy is globbed non-recursively. The report prints these as NOT COVERED.
- **Lower-severity, deferred:** duplicate Claude `tool_use_id` (crafted-only on real logs);
  Codex success still inferred from output text not exit code; same-session replay matches
  session but not engine; cross-log `seq` global tiebreaker; `is_marked` still matches bare
  marker vocabulary in prose (so this standard's own docs read as already-marked and are skipped).

## Dogfood integrity
The engine's own source files carry `ai-processed:unverified` from creation, and several
match secret prefixes (so the tool quarantines them) or marker vocabulary (so it skips them).
A self-run therefore skips part of its own corpus — expected, not a clean sweep. The unit
suite (38 tests) covers the gate, the safety net, replay, and the CLAUDE.md trap, but is not a
proof of the absent features above.

---
_Claude · 2026-06-28 · Session: 6ab1c2ae-25dd-40bf-9ca2-05072ee58b83_
