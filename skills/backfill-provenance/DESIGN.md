<!-- ai-processed:unverified | session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 | date:2026-06-28 -->
# backfill-provenance — design (v0.6, current)

What the tool actually is today. For *why the model changed* see `IMPLEMENTATION_NOTES.md`;
for *what isn't built / is fallible* see `KNOWN_LIMITATIONS.md`; for *how to run it* see
`SKILL.md`. The original pre-build design (the 3-round adversarial record + the verified
disk-fact ledger) is kept verbatim in `DESIGN.history.md` — its gate philosophy (a "two
independent signals / inversion threshold") was **superseded** and should be read as history.

## 1. Purpose
Retroactively flag already-existing files that **AI authored**, by reconstructing what AI did
from Claude Code + Codex chat history, so AI output isn't later mistaken for human-verified
truth. Two outputs: a **report** (inventory of AI-origin artifacts with the evidence for each)
and an opt-in, reversible **mark** of the AI-origin subset.

## 2. The model: marking is a recall-biased QUARANTINE
`ai-origin:backfilled` is an **unverified, reversible** flag meaning "a human didn't write
this." It is allowed to be wrong, in one direction on purpose:
- Over-flagging a human file is **cheap** — it's `:unverified`; a human glances and clears it.
- **Missing** an AI file is the **expensive** error — it then reads as human-written and trusted.

So the gate is biased toward recall and marks on **origin**, not on a proof the file is still
untouched. git and file-history *raise confidence*; they do not gate.

| Evidence | Action |
|---|---|
| AI **creation** event for the file (`Write` / Codex `Add File` / static quoted-delim heredoc), current bytes still match what AI wrote | mark, **high** confidence |
| AI creation event, but current bytes diverged (edited since / partly human-rewritten) | mark, **medium** confidence |
| AI only **edited** a human-created file (mixed authorship) | **report-only** (a human marks the AI section later) |
| AI touched the path only via a script / indirect write (no literal body) | report-only |
| no AI evidence | leave alone |

`high` = whole-file hash-continuity: the on-disk bytes equal a stream reconstructed from an AI
creation event (direct body, or same-session Edit/MultiEdit/apply_patch replay — never a
fragment match). `medium` = an AI creation event exists but the bytes changed since.

## 3. Architecture (the `pv_backfill/` pipeline)
`preflight → scan(adapters) → graph → classify → report → (opt-in) apply`, checkpointed to
`state.json`. One streaming pass over all history; report-primary; dry-run by default.

- **adapters.py** — discover + prefix-sniff every log; parse to normalized touch events with a
  **strict `tool_use_id`/`call_id` success-join** (a write counts only when its result is
  present and not `is_error`). Channels: Claude `Write/Edit/MultiEdit/NotebookEdit`, narrow
  Bash heredocs + `mv`/`cp` edges, `~/.claude/file-history/@vN` snapshots; Codex `apply_patch`
  (Add full-body / Update replay) across nested + flat-legacy whole-doc + archived sessions;
  subagent transcripts as first-class. Codex relative paths resolve against the cwd in effect
  **at that call**.
- **graph.py** — per-path content reconstruction + the hash-continuity check (replay is
  same-session only; cross-session chains abstain). file-history is a *base/continuity* store
  and confidence corroborator, **never an origin signal** (a snapshot can be human content —
  e.g. CLAUDE.md).
- **classify.py** — the §2 table; emits confidence + a plain-language reason.
- **report.py** — tiered report led by the quarantine caveats; confidence tiers; a `NOT COVERED`
  list (absent sources stated, never assumed clean).
- **mark.py** — the only mutator. See §4.
- **lib/provenance.py** — vendored marker grammar with `GRAMMAR_VERSION`.

## 4. Why marking is safe: reversibility + no collateral damage
Generous marking is safe only because it is undoable and never harms anything else, so the
mutator enforces:
- backup + manifest **outside** the synced tree; **restore fails loud** on any hash-mismatch or
  missing backup blob;
- a real **write-race guard** (report-time content-sha persisted in `state.json`, compared at
  apply; a file changed since the report is skipped);
- **never write through a link** — symlinks (final or via a parent dir) and hardlinks are
  skipped; writes use `O_NOFOLLOW`;
- **skip secrets** (glob + whole-file scan) and **Dropbox placeholders** (unconditional);
- **unique run-ids** (no manifest overwrite); **structural `unmark`** (own-line markers only);
- verify-after-write requires **exactly one** marker; marks `high` by default (`--min-confidence
  medium` opts in to the rest).

## 5. Invariants
Never write `verified`. Mark only `ai-origin:backfilled` (unverified), only on AI-created files.
Human-origin files are never auto-marked. Two attributions: the marker records the *origin*
session, the manifest records *this* backfill session. On any doubt about origin → report-only.

## 6. Verified disk facts (this machine, 2026-06-28; counts drift)
These shape the adapters and are re-checked, not assumed:
- `~/.claude/file-history/<session>/<id>@vN`: ~3k snapshots; the `<id>` is a stable **path
  hash** (so a snapshot is path-attributable via the project log's `trackedFileBackups`
  map), not a content hash; a snapshot is a **pre-edit base**, so it proves "Claude held these
  bytes," not authorship.
- Claude `tool_use` results omit `is_error` on success, set `is_error:true` on failure → strict
  id-join, failures excluded.
- Codex sessions: nested `{timestamp,type,payload}` jsonl + a flat-legacy single-document json
  + archived; `apply_patch` is `custom_tool_call name=apply_patch`, joined to its output by
  `call_id`; relative paths resolve against per-turn cwd.
- Only ~1 `.git` exists across `Code/local` — which is exactly why marking is a recall-biased
  quarantine rather than a git-gated assertion.

Full evidence ledger + the adversarial design history: `DESIGN.history.md`.

---
_Claude · 2026-06-28 · Session: 6ab1c2ae-25dd-40bf-9ca2-05072ee58b83_
