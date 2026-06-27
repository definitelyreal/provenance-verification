# provenance-verification

A portable standard + reference tooling for marking and verifying the **provenance** of AI-, human-, and tool-produced content. One spec, importable into any Claude Code setup or project; owned by none.

It answers three questions about any artifact:
1. **Provenance** — what produced this (human / `ai-suggestion` / `ai-processed` / a tool), and has it been verified?
2. **Freshness** — is the source (or tool) it rests on still current, or stale?
3. **Verification** — what did it take to call it verified? (An adversarial refute-pass, never a rubber stamp.)

## Why
AI output gets laundered into "fact" when its origin and check-status aren't tracked. Prose rules drift; this ships a *canonical marker grammar* plus *enforcement* so the discipline actually holds.

## What's in the box
- `spec/SPEC.md` — the standard (canonical `type:status` marker, three axes, tool-trust tiers). *CC-BY-4.0.*
- `spec/adversarial-gate.md` — the verification contract (six requirements, each earned by a documented real-world failure).
- `reference/provenance.py` — the canonical marker recognizer/normalizer (stdlib only). Use it in CI / pre-commit.
- `reference/hooks/` — optional Claude Code hooks (marker nudge, surface reminder, update notifier). Warn-only by default.
- `claude/RULES.md` — the behavioral subset you `@import` into CLAUDE.md.
- `adapters/TEMPLATE.md` — optional, co-located, per-project adapter.

## Install (Claude Code)
```
git clone <repo-url> ~/.claude/provenance-verification
bash ~/.claude/provenance-verification/install.sh
```
This adds one `@import` line to your `~/.claude/CLAUDE.md`, registers the optional hooks, and seeds a gitignored `claude/user.local.md` for your personal settings. On first run the standard asks you about your setup, then records it so it never asks again.

## Use in another repo
- **Behavioral rules:** add `@~/.claude/provenance-verification/claude/RULES.md` to that repo's CLAUDE.md (or just rely on the global import).
- **Validator in CI:** `reference/provenance.py check <file>` (PyPI package planned).
- **Pinning a version:** add as a git submodule.

## Updating
`bash install.sh --update` (git pull + re-register hooks). A SessionStart hook checks once a day and **notifies** — it never silently pulls executable code. That is a deliberate supply-chain choice: a provenance tool should not auto-run unreviewed code.

## Customization
Your personal config lives in `claude/user.local.md` (gitignored). It **extends**, never replaces, `RULES.md`, so you keep receiving standard updates while your overrides survive. Per-project domain specifics go in optional, co-located adapters (see `adapters/TEMPLATE.md`).

## License
Code: **MIT** (`LICENSE`). Spec text under `spec/`: **CC-BY-4.0** (`LICENSE-spec.md`).
