# Changelog

## 0.2.0 — 2026-06-27
- First public structure. Standalone repo (renamed from the internal "trust-kernel").
- Canonical marker form: `type:status` (`ai-suggestion:unverified`).
- `spec/SPEC.md` (three axes, tool-trust tiers, transition parser) + `spec/adversarial-gate.md` (six evidence-grounded requirements).
- `reference/provenance.py` recognizer/normalizer (legacy colon + green-highlight forms accepted).
- Optional, warn-only Claude Code hooks: marker check, surface reminder, fetch-and-notify update check.
- `claude/RULES.md` (`@import` target) + `claude/user.local.example.md` (gitignored personal overrides, extends-not-replaces) + first-run onboarding.
- Co-located optional adapters (`adapters/TEMPLATE.md`); personal adapters kept private.
- Dual license: MIT (code) + CC-BY-4.0 (spec text).
