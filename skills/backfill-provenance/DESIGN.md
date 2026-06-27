<!-- ai:suggestion | session: 0f1af029-e60e-421a-9ad7-1fd0f887c8b5 | date: 2026-06-27 -->
# backfill-provenance — Skill Design (Revised, post-adversarial-round-3)

Status: `ai-suggestion:unverified`. Nothing here is built or decided; this is the design Michael reviews before any code. Hardened against round 3 (2 Opus + 2 Codex). Round-3 facts were re-checked on this machine before writing (see §12 verification ledger), and the round-2 ledger's two errors are corrected: subagent count was off ~27x (real: 248 under Parents-Health, 3,044 total), and `file-history` was mis-categorized as a timestamp source when it is actually the richest **content** store on this machine.

The single biggest change in round 3: **the value proposition inverts.** Verified on disk, only **1** `.git` exists across all of `Code/local`. Under the inversion-avoidance invariant, a hash-match in a treeless tree cannot distinguish "AI wrote it, untouched" from "human edited then reverted" / "Dropbox re-synced." So auto-marking is the rare exception, not the headline. **The primary deliverable is the report** (an inventory of un-provenanced AI artifacts, with recovered evidence); marking is a small, hard-gated subset. The non-git opt-in escape hatch is **removed** (it was a sanctioned bulk override of the spine), replaced by a **two-independent-signals** rule.

---

## 0. Reviewability precondition + dependency strategy

Verified: `Code/local/trust-kernel/` still does not exist; the target tree has no `.git`. A hard external gate would fail closed and the skill could never run.

**Mechanism — vendor, don't gate (unchanged from r2, plus drift check):**
- Marker grammar + read/write library is vendored at `skills/backfill-provenance/lib/provenance.py`, with `GRAMMAR_VERSION`.
- Startup runs a fail-closed dependency check: loads the vendored lib, asserts `GRAMMAR_VERSION` parses, prints `dependency: vendored@<ver>` or `trust-kernel@<ver> at <path>`. Missing/incompatible grammar → `BLOCKER: provenance grammar unavailable`, exit. Never silently proceeds.
- **Grammar-drift guard (resolves opus-safety missing #5):** if BOTH a vendored copy and a `trust-kernel` copy claim the same `GRAMMAR_VERSION`, startup computes a `sha256` of each grammar module's *canonical spec section* and compares. A version-equal-but-content-divergent pair is a `BLOCKER: grammar drift at version X` — two tools must never write markers both claiming the same version with different semantics.
- STATE.md corrected: `trust-kernel` is planned, not present.

---

## 1. Purpose & scope

A skill that walks already-existing artifacts and **inventories the provenance markers they should have had**, then **marks the conservative subset whose AI origin is provable beyond the inversion threshold.**

Backfill is **archaeology, not authorship.** It reconstructs origin from evidence and marks conservatively. It is the riskiest provenance operation because it asserts origin for content it did not write, so the whole design hangs on the inversion-avoidance rule (§4) and refusal-by-default.

**Realistic-yield statement (resolves opus-safety #3, opus-completeness med#5).** On this machine the auto-markable population is small. Drivers, all verified: (a) only 1 `.git` in all of `Code/local`, so nearly every file hits the non-VCS regime; (b) a large fraction of edited files have no recoverable Write base; (c) the dominant Bash-write channels (`python -c`, generated scripts) carry no literal body. **The skill's expected and intended primary output is the report.** Auto-marking is the exception, surfaced as such; the report is never framed as a runway to "flip a switch and mark everything."

**In scope (v1) — eligible for marking** only where a positive *content-origin* signal is recoverable AND the §2.6 inversion threshold is met: markdown/code files in local trees and build dirs, with content recovered from any AI write channel (Write, Edit/MultiEdit replay-from-recoverable-base, NotebookEdit, **file-history `@vN` snapshots**, **literal static heredocs**, **Codex `Add File` and replayable `Update File`**, **subagent transcripts**).
**Report-only in v1 (no mutation):** Google Sheets, Docs, Slack/Notion, Airtable CRM, action-queue ops; **all indirect writes** (`python -c`, generated scripts, expanded heredocs); **Codex `Update File` with no recoverable base**; **edit chains with no recoverable base**; **all non-VCS files lacking a second independent signal** (§2.6); mixed-authorship files (§2.7). Inventoried, never auto-marked.

---

## 2. Evidence model — what counts as proof of AI origin

A path-touch is necessary but not sufficient. A file is eligible to be marked AI-origin only when the content-continuity gate (§2.4) AND the inversion threshold (§2.6) both hold.

### 2.1 Path-touch — multi-channel
Verified: Bash 122 vs Write 44 vs Edit 85 tool_use events in one bucket — Bash is the dominant authoring channel. The path-touch detector parses all of:

- **Direct tool calls:** `Write`, `Edit`, `MultiEdit` (atomic ordered chain), `NotebookEdit`.
- **file-history `@vN` content adapter (NEW — resolves opus-completeness #1, the single richest channel):** `~/.claude/file-history/<session-uuid>/<opaque-hash>@vN` stores **verbatim write-time bytes** (verified: 3,767 files, versions v1..v47, a sampled `@v2` is a complete source module). Every snapshot is indexed by `content-sha256`. **The snapshot file name is an opaque content hash, not a path** (verified: no local path manifest in the session dir), so attribution is **content-hash-match only** — folded into §3.4 move-survival. When a snapshot's hash equals on-disk bytes, that **is** hash-continuity (§2.4) regardless of whether an Edit chain replays. Session is resolved from the parent-dir UUID. This is the primary mechanism that lets the skill mark Edit-heavy and Codex-`Update File` files it otherwise would abstain on.
- **Bash-write adapter — sharply narrowed (resolves codex-impl Bash-parse, opus-safety #3):** a Bash write is **eligible** ONLY when ALL hold: (1) a single literal static heredoc with a **quoted delimiter** (`<<'EOF'`, no shell expansion), (2) a literal target path (no variables/globs/substitution), (3) no compound-command/loop/subshell/`xargs`/`sudo sh -c` context. Everything else (`>`, `>>`, `tee`, expanded heredocs, `cp`/`mv` of generated sources, `sed -i`, `printf`/`awk`/`perl`/`python -c`) is **report-only, never eligible** — because the bytes written after shell expansion are not the literal command text and a raw-text reconstruction could accidentally hash-match a *different* artifact and stamp it. `cp`/`mv` remain evidence-*propagating* (§3.4) but never content-*eligible* on their own.
- **Codex apply_patch adapter:** `Add File` carries full body (eligible). `Update File` carries hunks → **replayed against a recoverable base** (§2.4a); report-only only when no base exists, not as a blanket rule (resolves codex-impl #2).
- **Indirect writes:** AI-touched-but-content-unverifiable → report-only, never "leave alone."

### 2.2 Success join — strict, by tool_use_id (resolves codex-impl join, opus-safety #2)
Verified: 26 `is_error:true` results in one bucket; failed lines look identical to successful ones. Join is **strictly by explicit `tool_use_id`** via a per-session pending-tool-use map — never "the next line," because results are not guaranteed adjacent, unique, or in-order across streamed/compacted logs, subagents, retries, and interrupts. Only `is_error:false` (or a successful shell exit for Bash) counts. Missing / duplicate / out-of-order / non-adjacent results are their own abstention states (`result_missing`, `result_ambiguous`), not silent successes. Failed Edits are excluded from replay so they cannot corrupt reconstructed bytes.

### 2.3 Last-writer — content-continuity, not cross-clock comparison (resolves codex-impl cross-source, opus-safety #1 ordering)
Timestamps are different clocks (JSONL ts, rollout ts, git committer date, backup ts, mtime) and Dropbox/cross-machine copies rewrite mtime. **Timestamps order events only WITHIN a single source.** Any cross-source last-writer claim must rest on the **content-state graph** (§2.4b), not "latest timestamp wins." If continuity cannot establish who wrote the current bytes, `current-writer: ambiguous` and the file degrades to report-only.

### 2.4 Hash-continuity — the sole positive gate
`sha256(reconstructed write-time bytes) == sha256(on-disk bytes today)`.

- **(a) Recovered-whole-file only (resolves opus-safety #2, the canonical inversion trap).** The ONLY admissible hash input is a **fully reconstructed whole-file byte stream from a known base state** — a `Write`/`Add File` body, a literal static heredoc body, or a **file-history `@vN` snapshot**. It is **forbidden** to hash or match any `Edit`/`Update File` `new_string` fragment, any partial reconstruction, or any "most of the file" guess. `CLAUDE.md` is the named trap: human-authored, AI-edited; a fragment match would falsely stamp it. If the base is not recoverable, the file routes to `edit_chain_missing_base` / `codex_update_no_base` with zero exception.
- **(b) Per-path content-state graph (resolves codex-impl #1, biggest codex risk).** State is NOT a flat index of final bodies. Each event consumes a prior version-hash and emits a new version-hash; `cp`/`mv` creates an explicit edge from a *specific source version* to a destination version. This is the prerequisite for trustworthy move-propagation (an `mv a→b` inherits a's hash *immediately before the mv*, not "any hash ever associated with a") and for the content-hash fallback.
- **Base-state sources, explicit and ordered (resolves codex-impl #4):** (1) literal `Write`/`Add File`/static-heredoc body in logs; (2) **file-history `@vN` snapshot** whose hash anchors a known version; (3) VCS blob where a repo exists; (4) file-history backup. Current disk is a base only for formally-supported backward replay. Else abstain. Replay fixtures mandatory (§5.2).

### 2.5 Codex `Update File` replay (resolves codex-impl #2)
`Update File` is replayed as a unified-diff/apply_patch against a recoverable base (per §2.4b ordering), with the same failure semantics as Edit/MultiEdit: a replay that does not hash-match disk → abstain. Report-only only when the base is genuinely unavailable.

### 2.6 Inversion threshold — TWO independent signals, no opt-in override (resolves opus-safety #1+biggest, opus-completeness med#5)
Verified: only 1 `.git` in all of `Code/local`, so a single hash-match in a non-VCS, Dropbox-synced tree cannot distinguish AI-untouched from human-edited-then-reverted or whitespace-identical re-save or cross-machine re-sync.

> **The group-level non-git opt-in from r2 is REMOVED.** It was a UI for overriding the spine (§4) in bulk, in exactly the environment where the spine matters most.

Replacement rule:
- **Under VCS:** a §2.4 hash-match against a VCS blob lineage is sufficient (the repo itself is the second signal — it records human edits).
- **Non-VCS:** marking requires **TWO independent positive signals**, e.g. (i) a §2.4 whole-file hash-match against a **file-history `@vN` snapshot** that proves AI emitted those exact bytes, AND (ii) an independent corroborator: the same `content-sha256` appears in the session write-log for that path, **and** the file's mtime falls within that session's active window with **no later mtime gap** suggesting a re-save. One signal alone in a treeless Dropbox tree never auto-stamps. Everything below threshold → report-only.

### 2.7 Mixed-authorship within a single file (resolves opus-safety missing #1)
The grammar is whole-file; there is no line-range marker. A file that is human-Written then AI-Edited (or human doc + AI-inserted section) cannot be truthfully whole-file-marked "AI authored." Such files:
- are detected when the recovered origin event is a human-base-then-AI-edit chain, OR when the earliest recoverable content version is not an AI write;
- route to a dedicated `mixed_authorship` class → **report-only**, never whole-file marked;
- v1 explicitly does not emit line-range markers (open-q #5).

### Decision table

| Path-touch (id-joined) | Origin event | Hash-continuity (whole-file) | VCS? | 2nd signal (§2.6) | Classification | Action |
|---|---|---|---|---|---|---|
| yes | AI Write/Add/static-heredoc/`@vN` snapshot | match | git | n/a (repo is signal) | AI-origin (pure-AI creation) | mark `ai-origin:backfilled` |
| yes | AI Write/Add/`@vN` snapshot | match | non-git | present | AI-origin, 2-signal | mark `ai-origin:backfilled` |
| yes | AI Write/Add/`@vN` snapshot | match | non-git | absent | undetectable human-edit risk | **report-only** |
| yes | AI Edit on **human** base | match (recovered) | any | — | mixed authorship | **report-only** (`mixed_authorship`) |
| yes | any | diverged | any | — | content changed, by whom unknown | report-only, load-bearing question |
| yes | later human/git edit is last-writer | n/a | git | — | human-rewritten | do not mark |
| yes | unrecoverable base (Edit/Update File / lost log) | n/a | any | — | content-unverifiable | report-only (named class) |
| yes (indirect / expanded heredoc / `python -c`) | — | n/a | any | — | AI-touched, body not literal | report-only |
| no | — | — | any | — | no AI evidence | leave alone |

**Abstention classes, named + counted:** `edit_chain_missing_base`, `codex_update_no_base`, `missing_prior_state`, `log_gap`, `indirect_write`, `expanded_heredoc`, `non_git_single_signal`, `mixed_authorship`, `diverged`, `partially_corrupt_log`, `result_missing`, `result_ambiguous`, `duplicate_content` (§5 missing), `cwd_unresolved`. Each carries a **human-legible label** for review screens (§8.3); machine labels live only in the appendix (resolves codex-ux abstention-jargon).

---

## 3. Session identity & resolution

### 3.1 Tool-qualified identity
```
origin: <tool>/<tool-version>/<native-session-id> | project:<bucket-or-cwd> | log:<resolver-key>
```

### 3.2 Per-tool adapters — discovery + bounded-prefix schema-sniff (resolves codex-impl schema-sniff, opus-completeness #2/#3)
Discovery-first: enumerate candidate logs, then **sniff each over a bounded PREFIX of records** (not the first line — JSONL logs often open with `summary`/`session_meta`/`queue-operation`/`compaction`, and tool events nest under message-content arrays or rollout `items`). Detection is **confidence-scored via structural predicates across several relevant records**, with per-adapter/version coverage emitted. No hardcoded path is load-bearing.

Verified shapes on this machine:
- **claude-code:projects** — `~/.claude/projects/<cwd-encoded>/<uuid>.jsonl`.
- **claude-code:subagents** — `~/.claude/projects/<bucket>/<parent-session>/subagents/agent-*.jsonl` (verified: **248** under Parents-Health, **3,044** total — a major source by volume, not a footnote; r2 said 9, off ~27x). Each transcript links to its parent session via the dir name; Write/Edit/Bash/apply_patch events are first-class.
- **claude:file-history** (NEW) — `~/.claude/file-history/<session-uuid>/<hash>@vN`, verbatim content store, content-hash-indexed (§2.1).
- **codex:sessions-nested** — `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, line schema `{timestamp,type,payload}` (verified).
- **codex:sessions-flat-legacy** (CORRECTED parser — resolves opus-completeness #2) — `~/.codex/sessions/rollout-2025-*.json` is a **single pretty-printed JSON document** (`{` then newline, ~153 lines of indentation of ONE object: `{"session":{…},"items":[…]}`), **NOT JSONL** (verified). Detected by extension + first-byte `{` with no newline-delimited records. Parsed by a **whole-document JSON reader** (read `session.id`, iterate `items[]`), entirely separate from the JSONL streaming path and **never subjected to the per-line corruption budget** (§5.3).
- **codex:archived_sessions** (NEW — resolves opus-completeness #3) — `~/.codex/archived_sessions/rollout-*.jsonl` (verified present, real cwd inside Dropbox). Added to discovery + pre-flight enumeration so coverage isn't falsely "clean."
- **codex:index** — `session_index.jsonl` + `history.jsonl` (index only).

**Corroboration-only sources (NEW — resolves opus-completeness missing):** `~/.codex/shell_snapshots/*.sh` and `~/.claude/shell-snapshots/` (verified present; 33 under Claude) and `~/.claude/history.jsonl` + `~/.codex/history.jsonl` are used **only to corroborate Bash-write commands**, never as a sole content source. Pre-flight walks `~/.codex` for any other content dirs (`memories`, `computer-use`, `ambient-suggestions`) and reports whether each carries file-write evidence before declaring Codex coverage complete.

Any log matching no adapter is **reported as an unparseable source; its artifacts are NOT marked** — never silently skipped.

### 3.3 Bucket association by carried-forward cwd (resolves opus-completeness med#6, codex-impl collision)
Verified collision: `.` and `/` both encode to `-`. Bucket names are hints only. **cwd is per-turn, not per-line** (verified: 163/265 lines carried cwd in a sample; it lives on session/turn lines, not every tool event). Resolution therefore **carries forward the session's most recent cwd** and records cwd-changes within a session, rather than requiring cwd on the tool event itself. Abstain (`cwd_unresolved`) only when no cwd is derivable for the session at that point in the timeline. The project-bucket union (this tree fragments across `…-Parents-Health`, `-Dad`, `-Michael`) is computed but membership is confirmed by carried-forward cwd, not prefix glob.

### 3.4 Move-survival incl. shell-level moves and opaque-hash snapshots
Marker stores `log:`+`project:` key AND `content-sha256:`. Resolution order: (1) direct key lookup; (2) content-hash search in the prebuilt **content-state graph** (§2.4b), which also indexes every file-history `@vN` snapshot by hash (the only attribution path for those opaque-named snapshots); (3) `origin:unresolved` + open question — never a silent "no source found."

- **Bash mv/cp as evidence-propagating edges:** verified 16 Bash `mv` of `.md/.py/.txt`. An `mv src→dst`/`cp src→dst` adds a graph edge from the *specific source version at that timestamp* to dst (not "any src hash ever").
- **One-pass run index → content-state graph:** a single streaming pass builds the graph; logs are never re-read per candidate. **Must absorb 3k+ subagent transcripts + 3.7k file-history snapshots in one pass** within the stated runtime (re-budgeted, §8.1). Reading on-disk bytes for the fallback is gated by §6.
- Move-survival is a first-class requirement with a test (rename + Bash-mv + opaque-snapshot-hash variants; assert recovery).

### 3.5 Multi-session / multi-engine append-log
```
<!-- ai-origin:backfilled
  origin: claude-code/1.x/359ed423-… | project:… | log:… | date:2026-06-24 | action:create
  edit:   claude-code/1.x/0f1af029-… | project:… | log:… | date:2026-06-25 | action:edit
  current-writer: 0f1af029-…   # LAST byte-writer only — NOT author
  content-sha256: <hash-of-file-bytes-EXCLUDING-this-marker>   # see §5.5 self-event
  marked-by: <backfill-session-id> | date:2026-06-27   # the BACKFILL session, never conflated with origin
-->
```
**`current-writer` is strictly "last byte-writer," never "author"** (verified 14/92 files touched by >1 session). Authorship lives in `origin`/`edit`. `current-writer: ambiguous` whenever the last writer is not provable.

### 3.6 Same-path-reused boundary
A `rm` or a `Write` that does not extend prior state ends the current content segment in the graph; replay never crosses a delete/recreate. Each contiguous segment is its own chain; only the segment whose tail hash-matches disk is eligible.

---

## 4. The inversion-avoidance invariant (the spine)

> **Never mark human-authored content as AI. On any doubt, abstain.**

A file is marked **only** on a §2.4 whole-file hash-continuity match **AND** the §2.6 inversion threshold (VCS lineage, OR two independent non-VCS signals). There is **no group-level opt-in override**. Everything else → report-only. Conservative default: no marker on human-suspected files; `ai-origin:backfilled` on confirmed-AI files. No machine self-promotion to verified, ever.

**`ai-origin:backfilled` is creation-only (resolves opus-safety med #4).** The state asserts "AI authored these bytes per recovered evidence." It is emitted ONLY when the recoverable origin event is a pure-AI creation (`Write`/`Add File`/static-heredoc/`@vN` snapshot anchoring the whole file). **AI-edited-on-human-base files never receive it** — they route to `mixed_authorship` report-only (§2.7). One state never conflates creation and modification.

**Read/endorse case:** a human who reads an AI file and agrees leaves no byte trace, so hash-match cannot distinguish "AI, untouched" from "human reviewed and blessed." `ai-origin:backfilled` deliberately makes **no claim about human review** (unlike `:unverified`, which would imply "no human has confirmed" — which backfill cannot know). Promotion `backfilled → verified` is human-only.

**Unmark / rollback (resolves opus-safety missing #4).** A defined safe `unmark` operation exists for a mark later proven wrong: it is itself a provenance mutation, so it goes through the same backup+manifest+restore path (§7), removes exactly the one backfill marker (structural, never substring), records `unmarked-by: <session> | reason:` in `audit.jsonl`, and verifies-after-write that zero backfill markers remain. Unmark never touches a human-authored marker.

---

## 5. Robustness of the mining pass

### 5.1 Tolerant, prefix-sniffed parse
Verified line types include `queue-operation`, attachment/hook-error, `session_meta`. Each line is structurally classified; unknown event types are explicitly ignored, **not** counted against the corruption budget. Only malformed JSON or malformed *relevant* tool events count. Flat-legacy single-doc JSON is parsed whole (§3.2) and exempt from the per-line budget (resolves opus-completeness #2).

### 5.2 Edit/MultiEdit/Update-File replay fixtures
Fixtures for: duplicate `old_string` with `replace_all=false` (first-match), CRLF vs LF, empty replacement, missing match (→ abstain), `replace_all=true`, MultiEdit as atomic ordered chain (whole chain fails on any sub-edit mismatch), and apply_patch unified-diff hunks. A replay not hash-matching disk → abstain, never a guessed mark. **No fragment-level matching, ever (§2.4a).**

### 5.3 Corruption budget + partial logs
If >N% of a log's relevant lines fail to parse → `partially-corrupt`; every artifact it would source downgrades to `partially_corrupt_log`. Zero-byte/truncated logs = "no evidence," not "human." Truncation/compaction where a tool body is absent but a later result exists → `log_gap`, report-only (resolves codex-impl missing).

### 5.4 Streaming
Logs streamed (multi-MB confirmed) into the single content-state graph; no slurp, no per-file rescan.

### 5.5 Self-event exclusion + duplicate content (resolves opus-safety missing #2, codex-impl missing)
- **Self-event:** backfill's own marker insertion changes a file's bytes and mtime. The marker's `content-sha256` is computed over **file bytes EXCLUDING the marker block**, and the run records its own writes as known-self events, so a later run (or the last-writer logic) never mistakes backfill's insertion for a "later human edit."
- **Duplicate content:** identical bytes written by multiple sessions cannot be origin-resolved by hash alone. Such cases → `duplicate_content`: origin is reported as a set, `current-writer: ambiguous`, marking only if every candidate writer is AI (so the *class* is provably AI even if the exact session isn't).

---

## 6. Dropbox Smart Sync handling

Whole tree is Smart Sync. Before reading any artifact OR any log/snapshot byte: check `com.dropbox.placeholder` xattr + logical size (`rclone lsl`). A placeholder is **never** read as empty (would mis-classify as human) and **never** auto-hydrated.
- Cloud placeholders → metadata-only (path + logical size + "needs hydration to classify"), listed in the report, never in the byte-reading path.
- Hydration is a separate, surfaced, opt-in, size-estimated step — never silent, bulk, or triggered by the move-survival fallback.

---

## 7. Safety primitives

### 7.1 First-class quarantine — glob AND content scan (resolves opus-safety med #5)
`quarantine_globs` in `user.local.md`, defaults: `.env*, *.pem, *.key, *_key, *secret*, *token*, *credential*, ~/.ssh/**, ~/.aws/**, ~/.config/**, ~/.brain-api-token, auth.json` (verified `~/.codex/auth.json` exists). Hard-refuse read/mutate on match.
**Plus a content secret-scan** (entropy + known-key-prefix patterns) on any file **before its bytes or hash are persisted** to `audit.jsonl`/manifest or stored in a marker. On a hit: classify `quarantined-by-content`, **store neither body nor hash**, report path-only. Filename globs alone never keep secrets out of the immutable record.

### 7.2 Backups outside the synced tree
Backups + manifest → `~/Library/Application Support/trust-kernel/backfill/<run-id>/`, `0700`/`0600`. Quarantined files never copied; borderline paths store hashes only (subject to §7.1 content scan). `backups/`+`changes.jsonl` gitignored regardless of location.
**Cross-project hash containment (resolves opus-safety missing #3):** `audit.jsonl` records content-sha256 ONLY for files inside the run's declared workspace scope (§8.4 grouping). Logs from other projects (CRM, voice patterns, tokens) are mined for *evidence about in-scope files* but their unrelated artifacts' hashes are **not** persisted into this run's audit record — a scope bound, not a privacy leak.

### 7.3 Structural marker detection — per-language grammar, detect-only (resolves codex-impl marker-position, opus-safety #6)
Verified: 41 `.ai.md` already carry markers in this tree. Idempotency uses **per-language insertion/detection grammars** honoring shebang / encoding declaration / license-header / YAML-frontmatter / docstring precedence — not a single "expected position" and not substring grep. A structurally valid marker in a legal-but-nonstandard position is recognized (no false-negative re-mark). **Unsupported file types are not mutated at all.** A present-but-malformed marker is **NEVER auto-repaired** (repair would mutate provenance a human may have authored); it routes to report-only as an open question. New insertion verifies-after-write that exactly one well-formed marker exists.

### 7.4 Non-file surfaces — one consolidated screen (resolves codex-ux drip-prompts)
Sheets/Docs/Slack/Airtable/action-queue: inventoried with detected gap, never mutated in v1. Presented as **one "connected surfaces" screen** (not drip-fed per-surface prompts): file tree now; optional Sheets/Docs/Slack later, each with what it unlocks, expected noise, whether it can mutate or read history, and required OAuth scopes (read alone can have side effects, e.g. Docs revision history). Restore for these surfaces applies **only to locally generated report files**, not remote surfaces (resolves codex-impl low).

### 7.5 Concurrency / write-race guard + conflicted-copy in the write path (resolves opus-safety low)
Each mutation: (1) re-read+re-hash immediately before write, abort if changed since classification; (2) per-file lock; (3) skip+log if Dropbox shows the file actively syncing; (4) **after write, re-confirm exactly-one-marker AND detect a `(conflicted copy)` sibling**; if found, the change is treated as failed and restored. Conflicted-copy detection is part of the per-file write path, not only the restore test.

### 7.6 Restore fidelity tested inside Dropbox, full-metadata (resolves codex-impl restore-fidelity)
Targets live inside Dropbox; overwrite-on-restore can spawn `(conflicted copy)` or stale resurrection. Restore is tested in a Dropbox-controlled fixture simulating concurrent-sync and stale-overwrite. The manifest records and the restore preserves **xattrs, file modes, symlink identity (no follow), timestamps**, detects **package/bundle boundaries**, refuses to descend into bundles as plain dirs, and does **atomic replace only after re-validating Dropbox sync state**. Manifest records `inode / path / pre-hash / post-restore-hash` and detects conflicted-copy artifacts, failing loudly if the tree did not return to prior state. Status surfaces as a one-line human-readable check (§8).

---

## 8. Execution model — phased, prompt-budgeted, renames deferred

### 8.1 Explicit phases with split estimates (resolves codex-ux estimate-realism)
Estimates are split into **pre-scan rough bounds (ranges, confidence-labeled)** and **measured-after-phase actuals**. No ambiguous-item % is displayed until classification has actually run.
1. **Pre-flight source enumeration:** list every candidate log under `~/.claude` and `~/.codex` (incl. file-history, subagents ×3,044, archived_sessions, flat-legacy, corroboration-only dirs); classify each against a known adapter or flag unknown; print a **coverage report** (sources matched/unmatched, events parsed/skipped). Completeness measurable before classification.
2. **Codex freshness probe:** verified `logs_2.sqlite` (178MB, schema `level/target/file/line`) is **telemetry, not content**. Probe compares latest content-bearing rollout ts (across nested + flat-legacy + archived) vs sqlite activity; if no current content source exists for recent Codex work → `under_verified:no_current_content_source`; the run **never reports a clean Codex backfill**.
3. **Evidence recovery + content-state-graph build** (one streaming pass; must absorb 3.7k snapshots + 3k subagent transcripts — runtime re-budgeted with measured actuals reported).
4. **Classification** (decision table + abstention classes).
5. **Human-review prep** (tiered packets).
6. **Mutation** (group-by-group, opt-in).

### 8.2 Tiered dry-run output; report is the primary deliverable (resolves codex-ux bulk-laundering, opus-safety #3)
Tiered, not a flat spreadsheet: **(a) executive summary** — counts per classification + per abstention class, AND an explicit **realistic-yield line** ("X of N files are auto-mark-eligible; the rest are report-only because this tree is non-git / lacks a recoverable base — this is expected, see §1"); **(b) higher-risk decisions** surfaced individually (anomalies, non-git, multi-engine, surprising paths); **(c) lower-risk candidates** summarized; **(d) full appendix**. The report itself is positioned as the value; marking is the rare safe subset. Approval requested only after a small decision packet.

### 8.3 Prompt budget — cap ACTIONS not VISIBILITY (resolves codex-ux silent-deferral, false-confidence, jargon, "ALL anomalies")
- **Max ~5 approval ACTIONS per run** — but deferral is never silent. Every run shows **`N additional decision groups deferred`** with names, counts, and whether each blocks current scope; deferring requires an **explicit "defer these" confirmation**. The backlog never silently absorbs scope.
- "routine auto-safe" is **renamed "lower-risk candidates"** — all "safe" wording dropped from machine-generated grouping. Each group screen shows: count, **all top-level directories**, exact mutation type, count by marker action, sampled files, and a compact plain-language "why this group is lower risk."
- **Anomalies are counted separately and excluded from any bulk apply** (resolves the "ALL anomalies vs budget" conflict): representative examples shown inline, full list in appendix, individually acted on only when explicitly chosen. Default action = "apply lower-risk only; hold anomalies."
- Abstention/decision language is **plain** ("Could see edits but not the original file," "Tool log lacks the full replacement content," "No version control here, so a human edit can't be ruled out"); machine class names live in the appendix only.

### 8.4 Grouping by human workspace, then risk
Primary grouping = human-facing workspace/repo/build folder; secondary = action type + risk. **Never group across unrelated parent projects in one approval.** (Also the scope bound for §7.2 hash containment.)

### 8.5 Two distinct operations: marker vs filename (resolves codex-impl/.ai.md, codex-ux rename-muddiness)
v1 separates and labels explicitly:
- **Inline marker insertion** (default; what v1 does).
- **Filename normalization to `.ai.md`** = a **rename**, off by default in v1, its own later phase (broken-reference risk, affected links/imports, old→new preview).
Every approval packet states verbatim: **"This run will / will not rename files."** v1 markdown backfill is explicitly **partial-compliance** unless the filename already carries `.ai` — stated up front, not implied.

### 8.6 Backup + manifest + restore mandatory; status surfaced simply
Restore verified before any apply: `Restore check passed using a temporary test file in a Dropbox fixture; no project files changed.`

### 8.7 Immutable, re-derivable audit record
`<run-id>/audit.jsonl` persists the §8.2 inventory + the evidence chain that cleared the bar for each marked file (which evidence, which sessions/snapshots, hash-match y/n, why-abstained, which signals satisfied §2.6). A future human can re-derive why any file was marked, and `unmark` (§4) appends to the same record. Subject to §7.2 cross-project containment.

### 8.8 Resume model (resolves codex-ux missing-resume)
Phase state is checkpointed to `<run-id>/state.json` after each phase. If Michael stops after phase 4, the next run reloads the content-state graph + classifications, **shows prior choices** ("you previously approved group 2, deferred non-git"), and resumes at the mutation phase without re-mining. Voice-friendly approval grammar (resolves codex-ux missing): **"approve group 2 only," "skip all non-git," "show deferred decisions," "defer these," "unmark <path>"** are recognized commands. A **"no silent scope reduction" banner** on every run states what was scanned, skipped, deferred, and why.

### 8.9 Post-apply summary
Human-readable: what changed, what was skipped, what needs later attention, what was intentionally left untouched, and the realistic-yield recap.

---

## 9. Inventory & legibility

Tiered (§8.2): per artifact → classification, evidence chain (channel incl. file-history snapshot, log/session, hash-match y/n, which §2.6 signals), proposed marker, plain-language abstention reason. Grouped by human workspace, countable, anomalies always elevated, lower-risk grouping carries no "safe" language. **A concrete approval-screen mockup is part of the build spec** (resolves codex-ux missing) — the UX lives or dies in that format. This is the "see each run/analysis, group by run-session/domain" interface Michael asked for, scoped to backfill and shaped so labels can't launder bulk approval.

## 10. Reconciliation invariants (resolves codex-impl missing)

The dry-run prints a balance that MUST add up: `files_scanned = leave_alone + report_only(by class) + auto_mark_candidates`, and `logs_parsed = matched_adapter + unparseable`, and `relevant_events = eligible_events + abstained_events(by class)`. A non-balancing run is a `BLOCKER`, not a warning — it means a code path silently dropped artifacts.

## 11. Open questions for Michael (genuine forks)

1. **Backfill marker state name** — §4 uses `ai-origin:backfilled` (creation-only; distinct from `:unverified`). Confirm the name, that it lives in the grammar, and that AI-edited-human-base files going to report-only (not a second `ai-touched:backfilled` state) is acceptable for v1.
2. **Two-signal non-VCS rule** — §2.6 replaces the removed opt-in with "two independent signals (file-history hash-match + log+mtime corroborator)." Confirm this is the right bar, or whether even two signals is too aggressive in a treeless tree (i.e. non-VCS = hard report-only, full stop).
3. **Codex recent-work recovery** — §8.1 probe flags recent Codex work unrecoverable if no content source exists outside telemetry sqlite. Confirm "flag and report-only, never assert."
4. **trust-kernel home** — name/location/remote when extracting the vendored grammar. Not a blocker (§0).
5. **Mixed-authorship granularity** — v1 sends mixed files to report-only with no line-range marker. Confirm whether a future line-range marker is wanted, or whole-file report-only is sufficient indefinitely.

---
_Claude · 2026-06-27 · Session: 0f1af029-e60e-421a-9ad7-1fd0f887c8b5_

## 12. Verification ledger (round-3 facts checked on disk this session)

- `~/.claude/file-history/` exists: 3,767 files, dirs are session UUIDs, snapshots `<opaque-hash>@vN` (v1..v47), content is verbatim file bytes (sampled `@v2` = complete source module). No path manifest → content-hash attribution only. CONFIRMED. (r2 mis-categorized this as timestamp-only — corrected.)
- Subagent transcripts: **248** under Parents-Health, **3,044** total. CONFIRMED. (r2 ledger said 9 — corrected, ~27x error.)
- `~/.codex/archived_sessions/` exists (rollout-*.jsonl, real cwd in Dropbox). CONFIRMED — added as adapter.
- Flat-legacy Codex `rollout-2025-*.json` = single pretty-printed JSON object (`{` then newline, 153 lines), NOT JSONL. CONFIRMED — whole-document parser required.
- Nested Codex `rollout-*.jsonl` line schema = `{timestamp,type,payload}`. CONFIRMED.
- `~/.codex/shell_snapshots/`, `~/.claude/shell-snapshots/` (33), `~/.claude/history.jsonl`, `~/.codex/history.jsonl` exist → corroboration-only sources. CONFIRMED.
- `~/.codex/auth.json` exists → quarantine glob justified. CONFIRMED.
- Only **1** `.git` across all of `Code/local` → non-VCS is the norm; auto-mark is the exception; opt-in override removed. CONFIRMED.
- (Carried from r2, still load-bearing) Bash 122 vs Write 44 vs Edit 85; 26 `is_error:true`; `logs_2.sqlite` = telemetry; 41 existing `.ai.md` markers; 14/92 multi-session files; 16 Bash `mv` of docs/code. CONFIRMED in prior session.