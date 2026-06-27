# provenance-verification — behavioral rules

This is the provenance-verification behavioral standard, loaded into your agent instructions — Claude via `@import` in CLAUDE.md; Codex (`AGENTS.md`) and Gemini (`GEMINI.md`) via an installer-managed block. It applies to **every** AI agent, not just Claude. It is the behavioral subset of the standard; the full reference is in `../spec/SPEC.md` and `../spec/adversarial-gate.md`. Personal overrides live in `user.local.md` (gitignored) and **extend** this file — they do not replace it.

## First-run onboarding
If `user.local.md` does not exist alongside this file, or it contains `customized: false`: before acting under this standard in a session where provenance matters, ask the user about what the standard cannot know — their verifier name (for `verified <name> <date>`), which surfaces/mediums they use, which paths to enforce markers on, any do-not-autoresolve pairs, and which projects need adapters. Then write `user.local.md` and set `customized: true`. Ask once; do not nag.

## Marking provenance
Every AI-touched artifact carries a `type:status` marker.
- **type** ∈ `ai-suggestion` (AI's own ideas/inference) · `ai-processed` (AI compilation of real source data). Human-authored = no marker.
- **status** ∈ `unverified` · `verified <who> <date>` · `disputed <date>` · `stale <date>`.
- Markdown: `.ai.md` + frontmatter `<!-- ai-suggestion:unverified | session:<id> | date:<YYYY-MM-DD> -->`. Other media (Sheets, Docs, Slack, code): see SPEC §5. Light-purple `#e3dfec` highlight = AI/unverified; removed when verified.
- The marker is always a value/comment/cell, never a filename. In YAML, no space after the colon.
- **Soft `.ai` infix:** treat `name.ai.<ext>` and `name.<ext>` as the same file — when resolving a path, try both. Removing `.ai` (e.g. on taking ownership) must never break a reference; build that fallback into any code you write that touches `.ai` files.

## Invariants
- Machines never self-promote to `verified` — only a human, or a passing adversarial gate.
- AI output is never read back as ground truth.
- Never present `ai-*:unverified` content as fact; caveat it ("according to a prior AI session…").

## Freshness
A source that is down, expired, or served from cache, or that changed since it was last trusted, is a **blocker** — lead with it, never bury it; state the as-of date of non-live data. A tool updated upstream since it was vetted is `stale`, exactly like a cached source.

## Adversarial gate (full contract: ../spec/adversarial-gate.md)
The only machine path to `verified`. Refute, don't confirm. In brief:
- **Bind the verdict onto the artifact**, not a side-file.
- **Abstention is failure** — fewer than two independent voters → `under_verified:single_source`, never `verified`.
- **Fresh-context, cross-modality reviewer** (can't see the first pass's reasoning).
- **Re-read and quote the artifact** to justify a pass.
- **Default to `disputed`**; honor do-not-autoresolve lists; recency never wins silently.
- Vision/image claims always get an independent refute pass.

## Tool trust
A tool has a tier: `unvetted` < `sanity-checked` < `validated` < `cleared`. A finding inherits the **lower** of {data trust, tool trust}. Run bleeding-edge tools, but surface their output at its true tier — never suppressed, never laundered into fact.

<!-- ai-suggestion:unverified | session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 | date:2026-06-27 -->
