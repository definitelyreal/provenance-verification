# Adapter — <project name>

**Optional.** Only write one if this project binds the standard to domain-specific structures (a fact ledger, a CRM field layout, a do-not-autoresolve list). Most projects just use the defaults and need no adapter.

Place this file inside the project it adapts (e.g. `<project>/.provenance/adapter.md`) and reference it from your `user.local.md` `adapters:` list. The adapter lives with the project, not in this repo.

## Mapping
How this project's representation maps to the canonical `type:status`:
- `<project's "AI draft" field / table column / generated file>` → `ai-suggestion:unverified`
- `<AI compilation of real source data>` → `ai-processed:unverified`
- `<human-edited / confirmed>` → `verified <name> <date>`

## Verification overlay
Where and how status flips to `verified` in this project (the event log, the field, the verification file). Remember: machines never self-promote.

## Do-not-autoresolve
High-stakes pairs the adversarial gate must flag rather than merge.

## Independent voters
Which engines/modalities count as independent for this project's gate (e.g. a vision model refuted by a true-OCR modality).

## Required fixes (optional)
Concrete gaps to close to meet the gate contract — bind verdicts onto artifacts, treat abstention as failure, reserve an absent/illegible verdict, etc.

<!-- ai-suggestion:unverified | template -->
