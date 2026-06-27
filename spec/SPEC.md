# provenance-verification — Specification v0.2

The canonical standard for marking the **trust state** of any artifact. One spec, imported by every project; owned by none. Three axes:

1. **Provenance** — what produced this, and has it been verified.
2. **Freshness** — is the source (or tool) it rests on still current.
3. **Adversarial gate** — what it takes to flip something to verified (never a rubber stamp).

This file is the single source of truth. Where a project's prose rules disagree with this file, this file wins; the project keeps only its *domain extensions* (see §8).

---

## 0. Design rules (why the grammar is shaped this way)

- **The marker is always a value, comment, or cell — never a filename or path component.** macOS Finder and Dropbox silently rewrite `:` to `/` in paths. The only filename-level marker is the colon-free `.ai.md` extension.
- **In YAML frontmatter, never put a space after the colon** (`ai-suggestion:unverified`, not `ai-suggestion: unverified`) — YAML reads colon-space as a key/value split. Quote if a space is unavoidable.
- **Origin and verification are two facts, so the marker carries both.** This is the core reason for the status form below.

---

## 1. The canonical token form: `type:status`

A trust marker is two parts joined by a colon: **`<type>:<status>`**.

### 1a. `type` — what produced the artifact (the origin, immutable)
| type | meaning |
|---|---|
| `human` | a person authored it directly. (No marker needed; absence of a marker means human.) |
| `ai-processed` | an AI compiled/transformed *real source data* (extraction, transcript, dedup, enrichment, a tool run over real inputs). |
| `ai-suggestion` | an AI's own ideas, judgment, inference, hypotheses, generated lists. |

`type` never changes after creation. A suggestion that gets confirmed stays `ai-suggestion` — only its *status* changes. (This is the flaw in the old colon form `ai:verified`, which threw away the origin.)

### 1b. `status` — the verification state (mutable; only this part flips)
| status | meaning |
|---|---|
| `unverified` | default at birth for any `ai-*` artifact. Not yet human- or gate-confirmed. |
| `verified <who> <YYYY-MM-DD>` | a human or a passing adversarial gate confirmed it. Carries who and when. |
| `disputed <YYYY-MM-DD>` | an adversarial pass or a source conflict produced an unresolved disagreement. Surfaced, not silently dropped. (Fills the gap where the old standard had no way to express "flagged but unresolved.") |
| `stale <YYYY-MM-DD>` | the source or tool this rests on changed since it was last trusted; needs re-verification. (See §2.) |

Examples:
- `ai-suggestion:unverified` — a fresh AI inference.
- `ai-processed:verified michael 2026-06-25` — Michael confirmed an extraction.
- `ai-suggestion:disputed 2026-06-25` — two sources disagree; an open question exists.

### 1c. Invariants
- **Machines may never self-promote to `verified`.** Only a human, or a passing adversarial gate per §3, flips status.
- **AI output is never read back as ground truth.** An `ai-*:unverified` artifact is input to thinking, never a citable fact.
- **`verified` is removed, never silently.** Re-verification on a changed source produces `stale`, not a silent downgrade.

---

## 2. Freshness (the axis the old standard barely had)

Any artifact that rests on an external source or a tool carries an **as-of** stamp and, where applicable, a source fingerprint:

- `asof:YYYY-MM-DD` — when the underlying source was last known live/current.
- For tool-derived artifacts: `via:<tool>@<version>#<source-sha>` — the exact tool, version, and content hash of the tool's source.

**Staleness triggers** (any flips status to `stale`):
- The source connector is down, expired, or fell back to cache (a **blocker** — lead with it, never bury it).
- The source's content changed since `asof`.
- For a tool: the tool got an upstream update since it was vetted (`version` or `source-sha` no longer matches the vetted one). *A tool that updated is stale exactly like a cached data source.*

Stale ≠ wrong. It means "re-run the verification before trusting."

---

## 3. The adversarial gate

The only machine path to `verified` is a **refute-pass**: independent reviewers prompted to *break* the claim, not confirm it. A claim survives only if the refuters fail to refute it. A human may always verify or override directly; a machine may not.

The full contract — six requirements, each earned by a documented real-world failure on this machine — lives in [`adversarial-gate.md`](adversarial-gate.md). In brief:
- **R1 Bind the verdict onto the artifact**, never a sibling file. (The 67-error cross-check catch that never reached the ledger.)
- **R2 Abstention is failure, not pass.** `voter_count < 2` → `under_verified:single_source`, never `verified`. (The single-source blind spot that caused the only confirmed miss.)
- **R3 Independent, fresh-context, cross-modality reviewer** — can't see the first pass's reasoning; different engine/modality where possible.
- **R4 Re-read and quote the artifact** to justify a pass (Claim = Evidence, applied to the gate).
- **R5 Default to `disputed`; hard do-not-autoresolve guardrails.** Recency never wins silently.
- **R6 First-class absent/illegible verdict** — never silently dropped.

A passing gate may write `verified gate <YYYY-MM-DD>` plus a bound `gate{}` block; a human may always override.

---

## 4. Tool trust (the "random GitHub package" problem)

A tool is itself an artifact with a trust tier. A finding produced by a tool **inherits the lower of {data trust, tool trust}**.

| tool tier | meaning |
|---|---|
| `tool:unvetted` | pulled, never checked. Output is `ai-suggestion:unverified` at best, and may never skip the human/gate. |
| `tool:sanity-checked` | run against known inputs with expected outputs; basic smoke test passed. |
| `tool:validated` | has published/peer-reviewed validation, or Michael validated it against a gold set. |
| `tool:cleared` | externally cleared for its use (FDA/CLIA for clinical, etc.). |

Trust signals are *consumed, not built* — stars, citations, clearances, validation studies are recorded, not re-derived. The bleeding-edge tool is run, but its output surfaces at its true tier ("an experimental tool flagged X, confidence: experimental, discuss with a doctor"), never suppressed and never laundered into truth.

---

## 5. Marker grammar by medium

| Medium | Marker |
|---|---|
| Markdown file | `.ai.md` extension + frontmatter `<!-- ai-suggestion:unverified \| session:<full-uuid> \| date:YYYY-MM-DD \| asof:YYYY-MM-DD -->` |
| Inline section in a mixed file | `<!-- ai-suggestion:unverified -->` … `<!-- /ai -->` |
| Code file | top comment `# ai-processed:unverified · session:<full-uuid> · YYYY-MM-DD` |
| Google Sheets | `:Provenance` companion column, cell value `ai-suggestion:unverified <YYYY-MM-DD> <short-id>`; touched cells highlighted `#FEB4DC` |
| Google Docs | literal `<!-- ai-suggestion:unverified -->` above the block; `#FEB4DC` on the block; attached comment with full session id + URL |
| Slack / messages | prefix `<!-- ai-suggestion:unverified -->`; short-id in line |
| Notion / Coda / rich text | `<!-- ai-suggestion:unverified -->` prefix; `#FEB4DC` if available |

- **Highlight:** `#FEB4DC` (pink) = AI, not yet verified. Removed when status → `verified` (no color = human-trusted). Pink is canonical; legacy green `#4dff4d` is read by the transition parser and rewritten to pink.
- **Session id:** full 36-char UUID in files; first-8 short-id on Docs/Slack/Sheets.

---

## 6. Verifying (the flip)
- Frontmatter / inline / code: `ai-suggestion:unverified` → `ai-suggestion:verified <name> <YYYY-MM-DD>`; remove the `#FEB4DC` highlight.
- Sheets `:Provenance` cell: → `ai-processed:verified <name> <YYYY-MM-DD>`.
- Docs: → `<!-- ...:verified -->`, resolve the comment, drop the highlight.
- The `type` is never touched in a flip — only the status.

---

## 7. Transition / legacy (nothing breaks during cutover)
The reference validator accepts, and maps to canonical, all of:
- Old global colon form: `ai:suggestion` → `ai-suggestion:unverified`; `ai:processed` → `ai-processed:unverified`; `ai:verified` → `ai-*:verified` (type inferred from context, else `ai-processed`).
- Status-suffixed hyphen form `ai-suggestion:unverified` — already canonical.
- Legacy green highlight `#4dff4d` → pink `#FEB4DC`.
- Pre-2026-04-12 unmarked files → treated as `ai-suggestion:unverified` unless clearly human.

A mass rewrite is **not** required; the dual-format parser lets old and new coexist until files are touched naturally.

---

## 8. What stays a domain extension (NOT in the standard)
These belong in a project's own adapter, not here. Examples of the *kind* of thing that is domain-specific:
- **A clinical / health knowledge system:** clinician-as-verifier carrying a `role` field; a decision-support-not-diagnosis framing; consent/insurance gating for genomics. (Domain law governs who may verify and what verification authorizes.)
- **A multi-source personal knowledge graph:** cross-source entity resolution; a source-role distinction (LLM-generated vs real communication); deletion/audit trails for privacy law.
- **A CRM / contact system:** structural field-naming conventions mapped to standard tags by its adapter — with no forced field rename.

---

## 9. Status of this spec
v0.2. The adversarial-gate contract (§3, full text in `adversarial-gate.md`) is grounded in a documented track record of real verification successes and failures. Reference validator and an adapter template live alongside this file under `reference/` and `adapters/`.

<!-- ai-suggestion:unverified | session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 | date:2026-06-27 -->
