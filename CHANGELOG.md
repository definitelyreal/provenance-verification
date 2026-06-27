# Changelog

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
