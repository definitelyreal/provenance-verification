# Changelog

## 0.6.0 — 2026-06-28
- **Re-founded marking as a recall-biased QUARANTINE and unfroze it.** The marker
  `ai-origin:backfilled` is an unverified, reversible flag ("a human didn't write this"). The
  v0.5.x freeze optimized the wrong asymmetry: over-flagging a human file is cheap (a human
  clears it), while MISSING an AI file — it then reads as human-trusted — is the expensive error.
  - **Gate is now on ORIGIN:** an AI creation event marks the file at `high` confidence (current
    bytes still match what AI wrote) or `medium` (AI-created but changed since). git +
    file-history *raise confidence*, they no longer gate. Mixed (human file AI edited) stays
    report-only. On real data this raised recall from 24 to 47 markable files (41 high / 6 medium).
  - `apply` works again, dry-run by default; marks `high` by default, `--min-confidence medium`
    includes the rest.
- **Data-integrity safety net (what makes generous, reversible marking safe), fixed + tested:**
  write-race now real (report-time sha persisted in `state.json`, compared at apply); restore
  fails loud on hash-mismatch or missing backup blob; symlinks (incl. via a parent dir) and
  hardlinks are skipped, writes use `O_NOFOLLOW`; placeholder guard unconditional; secret files
  skipped by glob + whole-file scan (JWT/prefix/secret-assignment, without over-quarantining
  commit hashes/checksums); unique `run_id` + no manifest overwrite; `unmark` is structural
  (own-line markers only); verify-after-write requires exactly one marker.
- **Codex wrong-file fix:** relative `apply_patch` paths resolve against the cwd in effect at
  that call (per-item), not the session's final cwd.
- Report reframed to the quarantine model with confidence tiers; keeps the honest NOT-COVERED
  list. `KNOWN_LIMITATIONS.md` and `IMPLEMENTATION_NOTES.md` updated; still-absent features
  (§3.6 segmentation, §3.4 move-survival, grammar-drift guard, etc.) marked absent. 38/38 tests.

## 0.5.1 — 2026-06-28
- **Marking frozen + honesty pass after a 3-round adversarial review** (2 Opus + 2 Codex per round; repros under `build/redteam/`). The review found the v0.5.0 mark gate could launder human content, so auto-marking is disabled; the **report** is the deliverable.
  - `apply` refuses to write unless `--experimental-unsafe-marking` (known-unsafe) is passed.
  - **Two-signal non-VCS gate retracted as unsound:** file-history is the same engine's own pre-edit undo buffer, not an independent attestation — Signal A and Signal B are one operation, and Codex has no file-history at all. IMPLEMENTATION_NOTES "deviation 2" withdrawn.
  - Report now leads with caveats (coverage INCOMPLETE; reconciliation is bucket-balance only, not a coverage proof; candidate rows advisory) and an explicit **NOT COVERED** list (Gemini, `~/.codex` memories/ambient/computer-use, connected surfaces).
  - New `KNOWN_LIMITATIONS.md` marks every absent feature as absent: §3.6 delete/recreate segmentation (was falsely claimed implemented — corrected), §3.4 move/copy survival, §0 grammar-drift guard, §8.8 resume-shows-choices, §7.1 scan-before-hash ordering, §3.5 append marker block, dead abstention classes, plus the confirmed apply-path bugs (write-race no-op, `in_vcs` over-trust, restore not fail-loud, symlink/hardlink write-through, secret-scan gaps, seconds-granular run_id, prose-vocabulary false `is_marked`).
  - The honest verdict: re-found marking on git-history authorship (the one genuinely independent signal) in a deliberate v0.6; non-git and Codex stay report-only.

## 0.5.0 — 2026-06-28
- **backfill-provenance v2** — implements the adversarially-hardened `DESIGN.md`. Report-primary (marking is a hard-gated subset). New `pv_backfill/` engine; v1 scripts (`history_scan.py`/`inventory.py`/`apply.py`) removed.
  - **Channels v1 missed:** narrow Bash heredocs (quoted-delim/literal-path/no-expansion only), `mv`/`cp` evidence edges, `~/.claude/file-history/@vN` snapshots, Codex `apply_patch` (Add full-body / Update replay) across nested + flat-legacy whole-doc + archived sessions, and subagent transcripts as first-class.
  - **Strict success-join** by `tool_use_id`/`call_id`, excluding `is_error:true` (failed writes never counted as touches).
  - **Sole positive gate:** whole-file hash-continuity of a stream reconstructed from an AI *creation* event (`Write`/`Add File`/static heredoc) to current disk — never a fragment match; Edit/MultiEdit/apply_patch replay with abstain-on-mismatch.
  - **Inversion / two-signal gate:** git lineage is the 2nd signal; non-git requires a creation match **plus** an independent file-history attestation in the AI activity window. One signal in a treeless tree never marks.
  - **`ai-origin:backfilled`** creation-only marker (vendored grammar `lib/provenance.py`, `GRAMMAR_VERSION` + drift sha). Backups outside the synced tree; restore + `unmark`; secret quarantine (glob + content); Dropbox placeholder guard; reconciliation balance as a BLOCKER.
  - **Two evidence-backed refinements to DESIGN** (see `IMPLEMENTATION_NOTES.md`): file-history snapshots are path-attributed *base* states (not opaque content-hash origin signals — they would launder the human-authored CLAUDE.md trap); the non-git 2nd signal is grounded in that corrected file-history model.
  - Proven on real data: 5,774 logs parsed in one streaming pass; correct git-lineage marks, `edit_chain_missing_base`/`diverged`/`indirect_write` report-only classes, balanced reconciliation; 32/32 unit tests (replay fixtures, CLAUDE.md trap, inversion gate, marker round-trip, secret quarantine).

## 0.4.0 — 2026-06-27
- backfill-provenance skill (v1 preview): `history_scan.py` (Claude Write/Edit scanner, session-attributed), `inventory.py` (conservative `ai-suggestion:unverified` classification, skips already-marked), `apply.py` (dry-run default, backup + restorable manifest, `--restore`). Proven: scan finds session-attributed events; apply+restore round-trips.
- Installer now symlinks skills into `~/.claude/skills/`.
- `DESIGN.md` hardened by a 3-round adversarial review (2 Opus + 2 Codex): report-primary value prop, + Bash-heredoc & `file-history @vN` channels, strict `tool_use_id` success-join, inversion / two-signal gate — the v2 spec.


## 0.3.0 — 2026-06-27
- Canonical highlight now light purple `#e3dfec` (legacy green `#4dff4d` + pink `#feb4dc` still parsed).
- Cross-engine: installer wires Codex (`AGENTS.md`) and Gemini (`GEMINI.md`), not just Claude; RULES is engine-agnostic.
- Soft `.ai` infix: `name.ai.<ext>` and `name.<ext>` resolve interchangeably (`provenance.py` `resolve()`); dropping `.ai` never breaks references.
- backfill-provenance design: renames opt-in (asked up front), apply runs group-by-group, sheets marking preference asked & recorded.


## 0.2.0 — 2026-06-27
- First public structure. Standalone repo (renamed from the internal "trust-kernel").
- Canonical marker form: `type:status` (`ai-suggestion:unverified`).
- `spec/SPEC.md` (three axes, tool-trust tiers, transition parser) + `spec/adversarial-gate.md` (six evidence-grounded requirements).
- `reference/provenance.py` recognizer/normalizer (legacy colon + green-highlight forms accepted).
- Optional, warn-only Claude Code hooks: marker check, surface reminder, fetch-and-notify update check.
- `claude/RULES.md` (`@import` target) + `claude/user.local.example.md` (gitignored personal overrides, extends-not-replaces) + first-run onboarding.
- Co-located optional adapters (`adapters/TEMPLATE.md`); personal adapters kept private.
- Dual license: MIT (code) + CC-BY-4.0 (spec text).
