# Changelog

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
