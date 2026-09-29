# OQ-014 — Single-signal clipping mechanism semantics

**Status:** proposed design (awaiting explicit operator choice)

**Date:** 2026-09-29

**Open question:** `docs/OPEN_QUESTIONS.md` OQ-014

**Related:** D032–D035 (HEAD vs V0.2 identity); ARCHITECTURE_V0_2.md §17
S1-CLIP-SUBFS; `src/signal_diag/dsp/clipping.py`;
`src/signal_diag/agent/diagnosis.py` `_validate_clipping_supported`

## 1. Decision summary

HEAD cannot finish `supported_fault/clipping` on sub-full-scale flat-top
signals that V0.2 Architecture §17 and the retained Phase 5 Demo require.
The blocker is the shared DSP field `clipping_mechanism`, which is true only
for full-scale saturation or flat-top with `peak >= 0.99`, while finish gates
require `clipping_mechanism=true`.

This design offers three options. **Recommended: Option C** — keep the strict
DSP `clipping_mechanism` label for contextual / over-attribution control, and
restore single-signal clipping finish gates so flat-top Evidence plus a
substantial clipping-rule FAIL satisfies ARCH §17.

No option rewrites sealed v8.1 / Demo / v9.11 bundles. No option changes the
1% / 5% demonstration rule profile. Implementation starts only after the
operator picks one option in writing.

## 2. Context

### 2.1 Frozen V0.2 expectation

Architecture §17:

| Case | Ground truth | Required final behavior |
|------|--------------|-------------------------|
| S1-CLIP-SUBFS | sub-full-scale flat top | clipping claim with flat-top evidence; threshold-only detection is insufficient |

Phase 1 DSP still detects sub-full-scale flat tops (`detected` /
`flat_top_detected`). T030 remains green. The regression is in the **causal
finish gate**, not in flat-top detection itself.

Retained Demo inputs (peak ≈ 0.65 flat-top) finished as clipping at `b48790c`.
On HEAD they yield `clipping_mechanism=false`, so a clipping claim cannot
validate.

### 2.2 Why `clipping_mechanism` exists

V0.3 Workstream C introduced `clipping_mechanism` as a stricter causal label
than `detected`, so harmonic-rich / flat-looking material is not automatically
treated as a clipping *cause*. Gold labels in
`tests/dsp/test_v03_workstream_c_mechanism_labels.py` explicitly require
peak≈0.50 flat-top → `clipping_mechanism is False`, and peak≈0.99 full-scale →
`True`.

Contextual finish gates (`test_clipping_mechanism`) depend on that strict
label. Blindly equating `clipping_mechanism` with any `flat_top_detected`
would reopen over-attribution on contextual / external material.

### 2.3 What is broken on HEAD today

For product policy `v9_11_mode_aware_no_fault_recovery` (and earlier v9.x
gates that call `_validate_clipping_supported`):

```text
clipping supported_fault requires clipping_mechanism=true Evidence
+ substantial rule FAIL (rule_clipping_ratio_acceptable | rule_flat_top_absent)
```

Sub-full-scale flat-top produces `flat_top_detected=true` and often a
`rule_flat_top_absent` FAIL, but never `clipping_mechanism=true`. The claim is
rejected. Scripted S1 acceptance stays green because T087 tolerates
`max_planner_retries` / inconclusive-style terminals.

## 3. Goals

- Make the operator choice explicit and recorded (OQ-014 disposition + D036).
- Either restore ARCH §17 on the live `single_signal` path, or formally retire
  it with honest Demo/docs wording.
- Preserve contextual mode discipline against clipping over-attribution.
- Keep thresholds in versioned rule profiles; do not invent a new numeric
  industry SLA.
- Keep sealed bundles immutable; do not re-run official 79/80 or v9.11 to
  “fix” history.

## 4. Non-goals

- Reverting public `RealLLMPlanner` to v8.1 (rejected in the drift review).
- Changing `profile_s1_distortion` 1.0.0-demo 1% / 5% numbers.
- Rewriting Demo reports, official bundles, or external `below_target` packs.
- Adding new fault types, pitch trackers, or deployment features.
- Mode-filtered tool descriptor lists (OQ-016; separate).

## 5. Options

### Option A — Widen DSP `clipping_mechanism`

```text
clipping_mechanism = full_scale_detected OR flat_top_detected
```

**Pros:** One field; finish gates unchanged; S1-CLIP-SUBFS works everywhere
the field is consumed.

**Cons:** Breaks Workstream C gold labels; likely increases contextual /
external false clipping causes; couples “observable flat-top” to “causal
mechanism” again, which is what V0.3 tried to separate.

### Option B — Retire S1-CLIP-SUBFS on HEAD

Keep DSP and finish gates as-is. Amend Architecture honesty text (additive
note, not a silent §17 rewrite), Demo README, and AGENTS.md: HEAD
`single_signal` only supports near-full-scale / full-scale clipping causes;
sub-full-scale flat-top may be `detected` but not `supported_fault/clipping`.
V0.2 acceptance remains true at `b48790c`.

**Pros:** Zero product code risk; matches current v9.11 sealed behavior.

**Cons:** HEAD Demo presets / retained WAV story diverge permanently from
Architecture §17; weakens the “compatibility path” claim for `single_signal`.

### Option C — Mode-aware finish gate (recommended)

Keep DSP `clipping_mechanism` definition unchanged (strict).

Change **single_signal** clipping supported-fault validation to accept either:

1. current rule: `clipping_mechanism=true` **and** substantial clipping-rule
   FAIL; or
2. ARCH §17 path: `flat_top_detected=true` (valid Evidence) **and** substantial
   clipping-rule FAIL (`rule_flat_top_absent` or `rule_clipping_ratio_acceptable`),
   without requiring `clipping_mechanism=true`.

`paired_reference` / `nominal_single_tone` keep requiring
`test_clipping_mechanism=true` (+ contextual rule FAIL family).

`no_supported_fault` on `single_signal` must still prove cleanliness via
`clipping_mechanism=false` **and** flat-top / ratio PASS rules (already the
v9.11 single_signal no-fault family). Sub-full-scale flat-top therefore cannot
claim `no_supported_fault` while flat-top FAIL Evidence exists — it must claim
clipping or stay inconclusive.

**Pros:** Restores ARCH §17 on the one-WAV path; preserves V0.3 strict
mechanism for contextual modes and Workstream C labels; smallest semantic
diff.

**Cons:** Two acceptance predicates for clipping claims by mode; prompts may
need a one-line clarification so the planner cites `flat_top_detected` when
mechanism is false.

## 6. Recommendation

**Choose Option C.**

Reasons:

1. Architecture §17 and Phase 5 Demo honesty still bind the product story for
   one-WAV clipping; Option B abandons them on HEAD without necessity.
2. Option A undoes a deliberate V0.3 separation that contextual validation
   depends on.
3. Option C localizes the fix to `single_signal` finish validation (and tests /
   prompt note), which is exactly where ARCH §17 applies.

## 7. Contract and decision updates (after choice)

| Artifact | Option A | Option B | Option C |
|----------|----------|----------|----------|
| OQ-014 | resolved — A | resolved — B | resolved — C |
| DECISIONS D036 | new | new | new |
| CONTRACTS_V0_3 additive § | DSP field redefine | honesty / non-goal note | single_signal finish predicate |
| CONTRACTS_V0_2 §§1–64 | do not edit | do not edit | do not edit |
| ARCH §17 | unchanged meaning | additive supersession note for HEAD | unchanged meaning (HEAD restored) |
| TEST_PLAN_V0_3 | new T-CX ids | docs-only T ids optional | new T-CX ids |

## 8. Implementation sketch (Option C only)

Authoritative task list lands in
`docs/superpowers/plans/2026-09-29-oq014-option-c-single-signal-clipping.md`
after Option C is approved. Sketch:

1. **TDD:** strengthen T087 (or add T-CX) so scripted sub-full-scale flat-top
   must finish `supported_fault` with clipping claim citing `flat_top_detected`
   (and rule FAIL), not merely terminate on retries.
2. **Diagnosis:** extend `_validate_clipping_supported` (or a v9.11+ single_signal
   wrapper) with the flat-top alternate predicate; leave contextual validators
   untouched.
3. **Prompt:** one clarification in v9.11 (or a new v9.12 identity if byte-freeze
   of 9.11 is required) that single_signal clipping may cite `flat_top_detected`
   when `clipping_mechanism` is false.
4. **DSP:** no change under Option C.
5. **Preservation:** Workstream C mechanism gold labels stay green; sealed
   bundles untouched; no live-model campaign without separate authorization.
6. **Verify:** focused diagnosis/S1 tests; architecture tests; optional
   ScriptedPlanner CLI verify skill on synthetic clipping preset (not RealLLM
   unless authorized).

If Option A or B is chosen instead, replace this sketch with a matching plan
before any code lands.

## 9. Operator choice (required)

Reply with exactly one of:

```text
OQ-014: Option A
OQ-014: Option B
OQ-014: Option C
```

or `OQ-014: defer` to leave the open question open and stop.

Implementation, commits that change product behavior, and any real-model run
are **not** authorized by this design document alone.
