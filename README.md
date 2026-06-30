# provenance-verification

A portable standard for marking the **trust state** of any artifact — what produced it, whether it's been verified, and whether the source it rests on is still current. One standard, importable into any Claude Code setup or project; owned by none.

**👉 The standard itself is [provenance-verification.md](provenance-verification.md).** It is one self-contained file, and it is what an AI agent loads and follows. This README is the longer "why and how" around it; the standard is the tight, complete rulebook. If you only read one file, read that one.

## The problem

AI output gets laundered into "fact." An agent drafts a list, summarizes a transcript, or reads a number off an image, and three steps later that output is being cited as if a human had checked it. Nobody decided to trust it; the trust just accreted because nothing marked it as unverified. Prose reminders ("caveat AI content") drift and get forgotten. The failure is structural, so the fix has to be structural: a marker grammar that travels with the artifact, plus enforcement so the discipline actually holds.

This standard answers three questions about any artifact:

1. **Provenance** — what produced this (a human, `ai-suggestion`, `ai-processed`, or a tool), and has it been verified?
2. **Freshness** — is the source or tool it rests on still current, or has it gone stale?
3. **Verification** — what did it take to call it verified? (Surviving an adversarial refute-pass, never a rubber stamp.)

## How it works

Every AI-touched artifact carries a `type:status` marker — e.g. `ai-suggestion:unverified`. The **type** records origin and never changes; the **status** is the only part that flips. A machine can never promote its own output to `verified`: that takes a human, or a passing adversarial gate where independent reviewers are prompted to *break* the claim and it survives. A source that's down, cached, or changed since it was last trusted is a blocker, not a footnote. The marker is always a comment, cell, or value — never a filename (macOS and Dropbox rewrite `:` in paths) — except the colon-free `.ai.md` extension.

Every rule in the standard was earned by a real failure. The adversarial gate's six requirements, in particular, each trace to a specific incident on a real deployment (a cross-check that caught 67 OCR errors but never wrote them back to the ledger; a single-source read that sailed through as "agreed"; a verifier that never actually ran). The standard states the rules tightly; the rationale lives in the git history and in those incidents.

## What's in the repo

- **[provenance-verification.md](provenance-verification.md)** — the standard. The complete, canonical rulebook: marker grammar, the three axes, the adversarial gate, tool-trust tiers, the legacy/transition parser. *CC-BY-4.0.*
- **[provenance.py](provenance.py)** — the one marker recognizer/normalizer (stdlib only). The single place markers are recognized, so detection can't drift. Use it in CI / pre-commit.
- **[hooks/](hooks/)** — optional, warn-only Claude Code hooks (marker nudge on Write, surface reminder for Sheets/Docs/clipboard, daily update notifier).
- **[backfill-provenance/SKILL.md](backfill-provenance/SKILL.md)** — a process (not a tool) for retroactively marking provenance on a project that predates the standard: reconstruct what AI authored, show the user, mark the provable subset reversibly.
- **[adapter-template.md](adapter-template.md)** — optional per-project adapter for domain specifics (a fact ledger, a CRM field layout, a do-not-autoresolve list). Most projects need none.

## Install (Claude Code)

```
git clone <repo-url> ~/.claude/provenance-verification
bash ~/.claude/provenance-verification/install.sh
```

This adds one `@import` line for `provenance-verification.md` to your `~/.claude/CLAUDE.md`, wires the same standard into Codex (`AGENTS.md`) and Gemini (`GEMINI.md`), registers the optional hooks, and seeds a gitignored `user.local.md` for your personal settings. On first run the standard asks once about your setup (verifier name, surfaces, enforced paths) and records it.

## Use in another repo

- **Behavioral rules:** add `@~/.claude/provenance-verification/provenance-verification.md` to that repo's CLAUDE.md (or just rely on the global import).
- **Validator in CI:** `python3 provenance.py check <file>` (exit 1 if an AI file is unmarked).
- **Pinning a version:** add this repo as a git submodule.

## Updating

`bash install.sh --update` (git pull + re-register hooks). A SessionStart hook checks once a day and **notifies** — it never silently pulls executable code. That is deliberate: a provenance tool should not auto-run code you haven't reviewed.

## Customization

Personal config lives in `user.local.md` (gitignored). It **extends**, never replaces, the standard, so you keep receiving updates while your overrides survive. Per-project domain specifics go in optional, co-located adapters.

## License

Dual-licensed in one [LICENSE](LICENSE) file: code under **MIT**, the standard text (`provenance-verification.md`) under **CC-BY-4.0**.
