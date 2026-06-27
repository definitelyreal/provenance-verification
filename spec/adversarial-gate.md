# Adversarial Gate — Contract v0.2 (evidence-grounded)

The **only machine path** by which an artifact may move to `verified`. A human may always verify or override directly; a machine may not. This contract is derived from a documented track record of when verification actually worked and failed in a real deployment, not from first principles.

Core stance: **refute, don't confirm.** Reviewers are prompted to break the claim and default to "disputed unless forced to agree." A claim survives only if independent refuters fail to refute it.

---

## The six requirements (each earned by a real failure)

### R1 — Bind the verdict onto the artifact, never a sibling file
The single highest-value failure observed: a multi-engine cross-check caught 67 real OCR errors, but the verdict lived in a markdown report and **the wrong values stayed in the fact ledger as `uncertain=False`** — laundered back into "truth" downstream.
**Contract:** the gate writes its result *onto the fact/claim/row it judges*, as structured fields:
```
gate: {
  verdict: pass | fail | disputed | under_verified,
  voter_count: <int>,
  voters: [{engine, modality, verdict}],
  reason: <string>,
  evidence_ref: <pointer to the refute-pass record>,
  at: <YYYY-MM-DD>
}
```
A reader of the fact must see the verdict without opening another file. No verdict in a side-file counts as a verdict.

### R2 — Abstention is failure, not pass
Every vote-based tool failed the same way: it only fired on *disagreement among ≥2 voters*, so a value only one engine read sailed through as settled. This caused the only confirmed real-world miss (a human later caught errors in single-source reads, including an engine "confidently filling in" values that were actually illegible).
**Contract:** a value seen by fewer than two independent voters is `under_verified:single_source` — **never** `verified`, never silently "agreed." `voter_count < 2` can never produce `pass`.

### R3 — Independent, fresh-context, cross-modality reviewer
What worked was Codex (Tesseract OCR — a *different modality* than Claude/Gemini vision) refuting a vision read, and Codex auditing the same questions *blind to Claude's reasoning*. What never ran at all: the proof system's claimed fresh-context-Haiku adversarial pass (zero instances on disk).
**Contract:** the refuter (a) cannot see the first pass's reasoning or conclusion, only the artifact and the claim; (b) should use a different model and, where the medium allows, a different modality/engine. A reviewer that shares the author's context or modality is a weak voter, flagged as such.

### R4 — Re-read the artifact and quote it (Claim = Evidence, applied to the gate)
The adversarial briefing review worked because round 2 **re-read the revised text and quoted the new language** as proof a fix was real. The proof ledgers failed the opposite way: they assert `passed: true` from scripts that test the proof system itself.
**Contract:** a `pass`/`verified` verdict must cite the re-extracted evidence from the artifact (the quoted line, the recomputed value), not a re-run of a self-test. No quote, no pass.

### R5 — Default to flag; hard "do-not-autoresolve" guardrails
The best-built tool encoded "a wrong merge is worse than a missed merge" and an explicit `DO_NOT_MERGE` list for high-stakes pairs (HDL/LDL, Direct/Total Bilirubin, Free/Total T4, eGFR variants).
**Contract:** when in doubt the gate emits `disputed` and an open question — never a silent auto-resolution. Recency never wins automatically. Each domain may register a do-not-autoresolve list its adapter enforces.

### R6 — First-class "absent / illegible" state
The most signal-rich category (ordered-but-absent, e.g. FHIR `dataAbsentReason`) was being silently `continue`'d past and dropped.
**Contract:** "expected but unreadable/absent" is a reserved verdict, logged, never collapsed into "not present." This is the class the whole system exists to surface.

---

## When the gate is required
- Any image/vision-derived claim, on first pass (Codex + Gemini refute, after confirming each model actually sees the image).
- Any value that a downstream decision rests on, before it may reach `verified`.
- Any tool-derived finding where the tool is below `tool:validated` (see SPEC §4).

## What a passing gate may write
`type:verified gate <YYYY-MM-DD>` on the artifact, plus the bound `gate{}` block. A human may upgrade `gate`-verified to human-verified, or override to `disputed`, at any time.

---

## Reference vs domain
This contract is standard-level. Each consumer's **adapter** supplies the domain specifics: which fields the verdict binds to, the do-not-autoresolve list, and which engines/modalities count as independent. See `adapters/`.

<!-- ai-suggestion:unverified | session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 | date:2026-06-25 -->
