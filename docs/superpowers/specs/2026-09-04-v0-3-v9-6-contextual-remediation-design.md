# V0.3 v9.6 Contextual Remediation Design

**Status:** proposed for user review

**Date:** 2026-09-04

**Scope:** bounded V0.3 Scenario S1 planner/runtime remediation after the
preserved v9.5 Task 13 failure and diagnostic continuation

**Branch:** `codex/v0.2-real-world-validation`

## 1. Decision summary

V0.3 will add a new product prompt identity,
`v0.3-s1-planner-9.6`, plus one deterministic tool-routing guard. The
remediation addresses four observed failure families:

1. contextual modes selected `analyze_harmonic_distortion` instead of
   `analyze_contextual_distortion`;
2. `no_supported_fault` attempts cited `clipping_detected=false` instead of the
   required `clipping_mechanism=false` Evidence;
3. paired natural-even controls with valid comparison and no material growth
   were conservatively but incorrectly finished as `inconclusive`;
4. combined cases did not close the independent contextual harmonic gate after
   correctly detecting clipping.

The change does not weaken any causal gate. It makes mode-to-tool routing
deterministic and makes the existing finish requirements explicit to the
planner. The existing v9.5 prompt, Task 13 `below_target` evidence, protocol
deviation, and diagnostic continuation remain immutable historical evidence.

## 2. Evidence motivating the change

The preserved v9.5 evidence contains 20 unique development cases across the
invalid one-shot run and its separately labeled diagnostic continuation. It is
not a valid development-confirmation campaign, but it is valid remediation
evidence.

Descriptive observations are:

- all four clipping positives completed with the correct clipping cause;
- the two behaviorally observed harmonic-only positives finished
  `inconclusive`; the third harmonic-only slot ended in an infrastructure error;
- both combined positives terminated after repeated `missing contextual
  analysis PASS` validation errors;
- five clean/natural-even controls produced no exact `no_supported_fault`
  outcomes;
- five of six inconclusive roles produced the expected conservative outcome;
- no natural-even control produced a harmonic-distortion false positive;
- accepted final claims resolved to same-run Evidence and rule evaluations.

The failures therefore localize to planner routing and finish construction,
not to clipping detection, the contextual DSP calculation, frozen thresholds,
or the expected labels.

## 3. Goals

The remediation must:

- make contextual harmonic closure use `analyze_contextual_distortion` in
  `paired_reference` and `nominal_single_tone` modes;
- prevent the ordinary harmonic tool from substituting for contextual analysis
  in those modes under the new v9.6 policy;
- tell the planner exactly which clipping Evidence is required for a
  `no_supported_fault` claim;
- distinguish a valid paired no-growth natural-even control from an
  identifiability failure;
- preserve `inconclusive` for invalid comparison and nominal-frequency
  mismatch;
- require combined diagnoses to close the clipping and contextual harmonic
  gates independently;
- retain the four observed correct clipping paths and all existing deterministic
  safety gates;
- create a distinct prompt and causal-policy identity that can be audited
  without changing v9.5 bytes or recorded runs.

## 4. Non-goals

This remediation will not:

- change any WAV, development label, confidence tier, source record, manifest,
  seal, or expected outcome;
- change `profile_s1_distortion`, the 1% clipping demonstration threshold, the
  5% THD demonstration threshold, or the contextual 5% growth threshold;
- change contextual DSP, alignment, harmonic estimation, or Evidence values;
- change scoring formulas or denominators;
- add a new fault domain, multi-agent architecture, dependency, or network
  retrieval;
- make `single_signal` harmonic structure causally sufficient;
- auto-attach Evidence or rule references to an LLM claim;
- convert provider/runtime errors into diagnostic outcomes;
- retry or replace historical Task 13 attempts;
- access validation data or run a real model during implementation;
- claim that v9.6 meets development or validation targets before a separately
  authorized real-model campaign.

## 5. Considered approaches

### 5.1 Prompt-only clarification

This is the smallest textual change, but it is insufficient by itself. The
v9.5 prompt already says that paired mode uses contextual analysis, while the
recorded model repeatedly selected the ordinary harmonic tool. Rephrasing the
same preference would not make routing reliable.

### 5.2 Mode-specific tool hiding

The runtime could remove `analyze_harmonic_distortion` from the planner's
descriptor list in contextual modes. This reduces ambiguity, but the planner's
typed decision schema would still admit the tool name, and a hidden tool would
produce a less explicit audit trail when a model emits it anyway.

### 5.3 Prompt clarification plus deterministic rejection

This is the selected approach. The prompt specifies the desired route and
finish checklist. Under `v9_6_contextual`, the runtime rejects an ordinary
harmonic tool call in a contextual mode before tool execution and returns a
recoverable error naming `analyze_contextual_distortion`. The rejected call
consumes a planner retry but does not consume a tool-call slot or create Tool
Evidence. This is small, observable, and fail-closed.

## 6. Versioning and compatibility

Add `v9_6_contextual` to `CausalPolicyVersion`. The policy matrix is:

- `v9_4_legacy`: unchanged legacy finish semantics and no contextual routing
  guard;
- `v9_5_contextual`: unchanged historical v9.5 finish semantics and no new
  routing guard;
- `v9_6_contextual`: reuses the v9.5 contextual finish gates and adds the
  mode-aware routing guard.

The product composition root switches to `v0.3-s1-planner-9.6` and
`v9_6_contextual`. Tests and explicit dependency injection may still construct
the older policy identities. No historical prompt constant is edited.

## 7. Deterministic tool-routing contract

Before executing a Tool decision, the runtime checks the active policy and
`StimulusContext.mode`.

Under `v9_6_contextual`:

- `paired_reference` + `analyze_harmonic_distortion` is rejected;
- `nominal_single_tone` + `analyze_harmonic_distortion` is rejected;
- the recoverable error states that the active mode requires
  `analyze_contextual_distortion` for harmonic closure;
- `single_signal` continues to allow `analyze_harmonic_distortion`;
- `detect_clipping`, rule evaluation, knowledge retrieval, and finish decisions
  remain governed by their existing policies;
- an independently complete clipping claim may finish without a successful
  contextual harmonic claim;
- invalid contextual analysis does not suppress independently sufficient
  clipping Evidence.

The guard does not execute, record, or fabricate the rejected Tool call. It
uses the existing planner-retry boundary and existing sanitized trace path.

## 8. v9.6 prompt contract

The v9.6 prompt is derived from the frozen v9.5 bytes by replacing only the
contextual policy section with a more explicit section. It adds no numerical
thresholds.

### 8.1 Mode-to-tool rules

- In `paired_reference` and `nominal_single_tone`, call
  `analyze_contextual_distortion` for harmonic closure. The ordinary harmonic
  tool is not a substitute.
- In `single_signal`, the ordinary harmonic tool remains descriptive and cannot
  alone establish causal harmonic distortion.
- Clipping remains independent in every mode.

### 8.2 `no_supported_fault` checklist

A no-fault claim must cite the same-run `clipping_mechanism=false` Evidence.
`clipping_detected=false` is not a substitute. It must also cite the existing
clipping PASS rules and the mode-specific harmonic/contextual PASS rules
required by the deterministic validator.

### 8.3 Paired natural-even control

When comparison validity, F0 compatibility, reference clipping checks, and the
harmonic-growth rule all PASS, and test clipping is excluded, existing harmonic
content in both signals does not by itself require `inconclusive`. The correct
relative conclusion is `no_supported_fault` with a limitation that the finding
is relative to the supplied reference.

### 8.4 Nominal mismatch

If nominal contextual qualification or F0 compatibility fails, finish
`inconclusive` with same-run grounding and a limitation describing the
declaration mismatch. Do not emit `no_supported_fault` merely because clipping
and absolute THD pass.

### 8.5 Combined outcome

A combined result contains two separately grounded positive claims:

- clipping cites `clipping_mechanism=true` plus a substantial clipping rule
  FAIL;
- harmonic distortion cites the complete mode-specific contextual gate,
  including contextual validity and the relevant harmonic FAIL rule.

Failure to close the harmonic gate must not erase an independently supported
clipping claim. It may yield clipping-only `supported_fault` with an explicit
limitation when the contextual harmonic conclusion remains unavailable.

## 9. Error handling

The new routing rejection is a recoverable planner error. It is not an
infrastructure error and must never stop a campaign under infrastructure-stop
policy. Repetition may still terminate at `max_planner_retries`; such a result
is a behavioral failure and is retained.

Provider exceptions retain the existing classification and no-fallback
behavior. The prior `APIConnectionError` remains `root_cause=unknown` and is not
used to justify product changes.

## 10. Test contract

Allocate T-CX146–T-CX165 without changing T-CX001–T-CX145 meanings:

- T-CX146–T-CX148: v9.5 prompt/run preservation and policy-version
  compatibility;
- T-CX149–T-CX154: v9.6 mode-aware Tool routing;
- T-CX155–T-CX162: v9.6 prompt bytes, wording, composition, and finish
  checklists;
- T-CX163–T-CX165: deterministic replay regressions for the observed failure
  families and preserved clipping behavior.

Tests must prove that the new policy fails closed while the legacy and v9.5
paths remain unchanged. Prompt bytes are frozen only after the final reviewed
text is constructed; the resulting SHA-256 is then pinned as a literal in the
test and acceptance record.

## 11. Acceptance and stop gates

Implementation is code-complete only when:

- each new behavior has a red test before implementation and a green test after;
- all new T-CX146–T-CX165 tests pass;
- the complete contextual suite passes;
- full pytest has zero required skip/xfail;
- Ruff, `mypy src`, architecture, preservation, and `git diff --check 605c8a8`
  pass;
- v9.5 prompt SHA and all three preserved Task 13 directories remain unchanged;
- v9.6 prompt version and SHA are recorded;
- no validation path is accessed and no real model is invoked.

Passing these gates means `v9_6_harness_complete`, not development success. A
new v9.6 remediation development confirmation requires separate authorization,
a new append-only run directory, preflight identity checks, and one attempt per
slot. It may use the development cases for remediation confirmation but must
not be described as blind validation or as repairing the original Task 13.
