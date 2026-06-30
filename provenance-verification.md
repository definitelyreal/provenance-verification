# provenance-verification — the standard

The complete, canonical standard for marking the **trust state** of any artifact: what produced it, whether it has been verified, and whether the source it rests on is still current. This single file is self-contained and authoritative; where any other doc disagrees, this file wins. It is loaded into agent instructions (Claude via `@import` in CLAUDE.md; Codex `AGENTS.md` and Gemini `GEMINI.md` via an installer-managed block) and applies to **every** AI agent, not just Claude. Personal settings live in `user.local.md` (gitignored) and **extend** this file, never replace it. The narrative rationale ("why each rule exists") is in [README.md](README.md).

## First-run onboarding
If `user.local.md` does not exist, or it contains `customized: false`: before acting under this standard in a session where provenance matters, ask the user what the standard cannot know — their verifier name (for `verified <name> <date>`), which surfaces/mediums they use, which paths to enforce markers on, any do-not-autoresolve pairs, and which projects need adapters. Then write `user.local.md` with `customized: true`. Ask once; never nag.

## The marker: `type:status`
Every AI-touched artifact carries a marker — two parts joined by a colon, `<type>:<status>`.

**`type`** — what produced it (the origin; **immutable**, never changes after creation):
| type | meaning |
|---|---|
| *(no marker)* | a human authored it directly. Absence of a marker means human. |
| `ai-processed` | an AI compiled/transformed *real source data* (extraction, transcript, dedup, enrichment, a tool run over real inputs). |
| `ai-suggestion` | an AI's own ideas, judgment, inference, hypotheses, generated lists. |

A suggestion that later gets confirmed stays `ai-suggestion` — only its *status* changes. (This is why the old colon form `ai:verified` was wrong: it discarded the origin.)

**`status`** — the verification state (**mutable**; only this part flips):
| status | meaning |
|---|---|
| `unverified` | default at birth for any `ai-*` artifact. Not yet human- or gate-confirmed. |
| `verified <who> <YYYY-MM-DD>` | a human, or a passing adversarial gate, confirmed it. Carries who and when. |
| `disputed <YYYY-MM-DD>` | an adversarial pass or a source conflict produced an unresolved disagreement. Surfaced, not dropped. |
| `stale <YYYY-MM-DD>` | the source or tool it rests on changed since last trusted; needs re-verification. |

Examples: `ai-suggestion:unverified` · `ai-processed:verified michael 2026-06-25` · `ai-suggestion:disputed 2026-06-25`.

### Invariants (never violate)
- **Machines never self-promote to `verified`.** Only a human, or a passing adversarial gate (see below), flips status to verified.
- **AI output is never read back as ground truth.** An `ai-*:unverified` artifact is input to thinking, never a citable fact. Never present it as fact — caveat it ("according to a prior AI session…").
- **`verified` is removed, never silently.** Re-verification on a changed source produces `stale`, not a silent downgrade.

## Grammar rules (how to write the marker)
- **The marker is always a value, comment, or cell — never a filename or path component.** macOS Finder and Dropbox silently rewrite `:` to `/` in paths. The only filename-level marker is the colon-free `.ai.md` extension.
- **In YAML frontmatter, no space after the colon** (`ai-suggestion:unverified`, not `ai-suggestion: unverified`) — YAML reads colon-space as a key/value split. Quote if a space is unavoidable.
- **The `.ai` infix is soft.** Treat `name.ai.<ext>` and `name.<ext>` as the same logical file; when resolving a reference to one, also try the other. A user may drop `.ai` (e.g. on taking ownership) without breaking any reference. Any code that touches `.ai` files must check both forms (see `provenance.py` `resolve()`).

## Marker by medium
| Medium | Marker |
|---|---|
| Markdown file | `.ai.md` extension + frontmatter `<!-- ai-suggestion:unverified \| session:<full-uuid> \| date:YYYY-MM-DD \| asof:YYYY-MM-DD -->` |
| Inline section in a mixed file | `<!-- ai-suggestion:unverified -->` … `<!-- /ai -->` |
| Code file | top comment `# ai-processed:unverified · session:<full-uuid> · YYYY-MM-DD` |
| Google Sheets | `:Provenance` companion column, cell value `ai-suggestion:unverified <YYYY-MM-DD> <short-id>`; touched cells highlighted `#e3dfec` |
| Google Docs | literal `<!-- ai-suggestion:unverified -->` above the block; `#e3dfec` on the block; attached comment with full session id + URL |
| Slack / messages | prefix `<!-- ai-suggestion:unverified -->`; short-id in line |
| Notion / Coda / rich text | `<!-- ai-suggestion:unverified -->` prefix; `#e3dfec` if available |

- **Highlight:** `#e3dfec` (light purple) = AI, not yet verified. Removed when status → `verified` (no color = human-trusted). Legacy colors (green `#4dff4d`, pink `#feb4dc`) are read and rewritten to it.
- **Session id:** full 36-char UUID in files; first-8 short-id on Docs/Slack/Sheets.

## Verifying (the flip)
- Frontmatter / inline / code: `ai-suggestion:unverified` → `ai-suggestion:verified <name> <YYYY-MM-DD>`; remove the `#e3dfec` highlight.
- Sheets `:Provenance` cell → `ai-processed:verified <name> <YYYY-MM-DD>`. Docs → `<!-- ...:verified -->`, resolve the comment, drop the highlight.
- The `type` is never touched in a flip — only the status.

## Freshness
Any artifact resting on an external source or a tool carries an **as-of** stamp (`asof:YYYY-MM-DD` — when the source was last known live) and, for tool-derived artifacts, a fingerprint (`via:<tool>@<version>#<source-sha>`).

A source that is down, expired, served from cache, or changed since `asof` is a **blocker** — lead with it, never bury it; state the as-of date of non-live data. A tool that got an upstream update since it was vetted is `stale`, exactly like a cached source. **Stale ≠ wrong**; it means "re-run the verification before trusting." Any staleness trigger flips status to `stale`.

## Adversarial gate — the only machine path to `verified`
A claim reaches machine-`verified` only by surviving a **refute-pass**: independent reviewers prompted to *break* the claim, defaulting to "disputed unless forced to agree." A human may always verify or override directly; a machine may not. Six requirements, each earned by a documented real-world failure:

- **R1 — Bind the verdict onto the artifact**, never a sibling file. Write the result onto the fact/row/claim it judges as structured fields (`gate: {verdict, voter_count, voters[], reason, evidence_ref, at}`). A verdict only in a side-file is not a verdict.
- **R2 — Abstention is failure, not pass.** A value seen by fewer than two independent voters is `under_verified:single_source` — never `verified`. `voter_count < 2` can never produce a pass.
- **R3 — Independent, fresh-context, cross-modality reviewer.** The refuter cannot see the first pass's reasoning or conclusion, only the artifact and the claim; use a different model and, where possible, a different modality/engine. A reviewer sharing the author's context/modality is a weak voter, flagged as such.
- **R4 — Re-read and quote the artifact** to justify a pass (Claim = Evidence applied to the gate). Cite the re-extracted evidence (the quoted line, the recomputed value), not a re-run of a self-test. No quote, no pass.
- **R5 — Default to `disputed`; honor hard do-not-autoresolve guardrails.** When in doubt, emit `disputed` and an open question. Recency never wins automatically. Each domain registers a do-not-autoresolve list its adapter enforces.
- **R6 — First-class absent/illegible verdict.** "Expected but unreadable/absent" is a reserved verdict, logged, never collapsed into "not present" — it is the class the whole system exists to surface.

The gate is **required** for: any image/vision-derived claim on first pass (Codex + Gemini refute, after confirming each model actually sees the image); any value a downstream decision rests on, before it may reach `verified`; any tool-derived finding where the tool is below `tool:validated`. A passing gate may write `<type>:verified gate <YYYY-MM-DD>` plus the bound `gate{}` block; a human may upgrade or override at any time.

## Tool trust
A tool is itself an artifact with a trust tier. A finding **inherits the lower of {data trust, tool trust}**.
| tier | meaning |
|---|---|
| `tool:unvetted` | pulled, never checked. Output is `ai-suggestion:unverified` at best; may never skip the human/gate. |
| `tool:sanity-checked` | run against known inputs with expected outputs; basic smoke test passed. |
| `tool:validated` | published/peer-reviewed validation, or validated against a gold set. |
| `tool:cleared` | externally cleared for its use (FDA/CLIA for clinical, etc.). |

Trust signals are *consumed, not built* — stars, citations, clearances are recorded, not re-derived. Run the bleeding-edge tool, but surface its output at its true tier ("an experimental tool flagged X, confidence: experimental"), never suppressed and never laundered into fact.

## Transition / legacy
The reference recognizer (`provenance.py`) accepts, and maps to canonical, all of: old colon form (`ai:suggestion`→`ai-suggestion:unverified`, `ai:processed`→`ai-processed:unverified`, `ai:verified`→`ai-*:verified`, type inferred else `ai-processed`); bare hyphen forms (`ai-suggestion`, `ai-generated`→`ai-suggestion:unverified`); legacy highlights (green/pink → light purple); and pre-2026-04-12 unmarked files (treated as `ai-suggestion:unverified` unless clearly human). A mass rewrite is **not** required; old and new coexist until files are touched naturally.

## Domain adapters
Domain-specific rules do **not** live in this standard — they go in a per-project adapter co-located with the project (template: [adapter-template.md](adapter-template.md)), referenced from `user.local.md`. An adapter maps the project's structures to `type:status`, defines where status flips, supplies the do-not-autoresolve list, and names which engines/modalities count as independent voters. Examples of the *kind* of thing that is domain-specific: a clinical system's clinician-as-verifier and consent gating; a personal knowledge graph's cross-source entity resolution; a CRM's field-naming conventions.

## Backfilling existing files
To retroactively mark provenance on a project adopted before this standard, follow the `backfill-provenance` skill ([backfill-provenance/SKILL.md](backfill-provenance/SKILL.md)): a human-gated, reversible **process** (not a tool) where an agent reconstructs what AI authored from chat/git history and file evidence, shows the user, then marks the provable subset reversibly. Backfill writes only `ai-*:unverified` — a recall-biased quarantine flag — and never `verified`.

<!-- ai-suggestion:unverified | session:715279ef-4d0d-4864-ba13-20b0a5801ec3 | date:2026-06-29 -->
