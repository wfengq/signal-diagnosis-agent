# V0.3 v9.10 Contextual Clipping Recovery Design

**Status:** approved design; implementation not yet authorized by a written plan

## 1. Purpose

Repair the two independent clipping failures exposed by the diagnostic-only
reconstruction of the interrupted v9.9 contextual validation campaign:

- `7fd4173cde11c0e3`: `nominal_single_tone` contextual analysis exposed
  test-side clipping ratio and flat-top observations, but automatic closure
  created no test-side clipping rule evaluations and exposed no test-side
  clipping-mechanism Evidence. A legal clipping claim therefore could not be
  assembled.
- `675073735bc06f76`: `single_signal` analysis already contained valid
  `clipping_mechanism=true` Evidence and three clipping rule FAIL evaluations.
  The planner nevertheless retained an unsupported sibling harmonic claim for
  three rejected finishes and ended at `max_planner_retries`.

The first failure is deterministic evidence/rule coverage. The second is
finish-recovery behavior. Neither justifies changing validation labels,
transforms, scoring, or the existing 1% clipping and 5% THD demonstration
thresholds.

## 2. Chosen approach

Introduce prompt identity `v0.3-s1-planner-9.10` and causal policy
`v9_10_contextual_clipping_recovery`.

The contextual analysis path becomes self-contained for test-side clipping:

1. deterministic DSP propagates the already-computed test clipping mechanism;
2. the contextual Tool emits compact `test_clipping_mechanism` Evidence;
3. a new contextual profile identity
   `profile_s1_contextual_comparison_v9_10` version `1.0.0` adds test-side
   clipping-ratio and flat-top rules using the unchanged 1% and Boolean
   demonstration limits;
4. automatic contextual closure evaluates those rules in the existing single
   batch;
5. v9.10 finish validation accepts either one complete legacy clipping family
   or one complete contextual test-side clipping family, never a mixture.

Finish recovery remains planner-owned. Runtime does not insert, delete, or
rewrite claims. When a finish contains a complete clipping claim plus an
unsupported harmonic sibling, v9.10 returns one recoverable error that
identifies the already-supported clipping subset and instructs the next finish
to preserve that claim while removing the unsupported sibling. The v9.10
prompt contains the same rule explicitly.

## 3. Rejected alternatives

### 3.1 Require an additional `detect_clipping` Tool call

This reuses the existing distortion profile but adds an avoidable Tool call,
depends on stochastic routing, and leaves the contextual Tool's existing
test-side clipping observations unusable as causal Evidence.

### 3.2 Runtime silently projects a valid subset

Automatically deleting the unsupported harmonic claim could make the case
finish, but it would rewrite the model's diagnosis and weaken provenance. It
conflicts with the established rule that Runtime validates rather than authors
claim content.

### 3.3 Prompt-only remediation

Prompt wording can address the repeated sibling claim but cannot manufacture
the absent test-side clipping-mechanism Evidence or rule evaluations in the
nominal case.

## 4. Contract additions

### 4.1 Contextual DSP and Tool Evidence

`ContextualDistortionAnalysis` and `ContextualDistortionResult` add:

```text
test_clipping_mechanism: bool
```

The value comes only from the existing deterministic clipping analysis of the
test waveform. It is serialized as one compact, valid Evidence item with
metric `test_clipping_mechanism`. No waveform or FFT payload crosses the Tool
boundary.

### 4.2 Additive contextual profile identity

The existing `profile_s1_contextual_comparison` version `1.0.0` file and bytes
remain unchanged. Add
`profile_s1_contextual_comparison_v9_10` version `1.0.0`, copying the six
existing rule semantics and adding exactly:

```text
rule_test_clipping_ratio_acceptable
    test_clipping_ratio <= 0.01

rule_test_flat_top_absent
    test_flat_top_detected == false
```

All inherited rules and thresholds remain semantically unchanged. The distinct
profile ID, new file, and new profile SHA prevent an active loader mapping from
silently changing the historical profile. v9.7 through v9.9 continue mapping
contextual Tool observations to `profile_s1_contextual_comparison` version
`1.0.0`; only v9.10 maps them to the additive profile.

### 4.3 Coherent clipping families

A v9.10 clipping claim is supported by exactly one coherent family:

- legacy family: valid `clipping_mechanism=true` plus FAIL of
  `rule_clipping_ratio_acceptable` or `rule_flat_top_absent`;
- contextual test family: valid `test_clipping_mechanism=true` plus FAIL of
  `rule_test_clipping_ratio_acceptable` or
  `rule_test_flat_top_absent`.

Evidence and rules from different families cannot be combined to satisfy the
gate. Older policy versions retain their exact historical behavior.

For `no_supported_fault` in paired or nominal contextual modes, v9.10 may use
a complete contextual test-side clean family: valid
`test_clipping_mechanism=false` plus PASS of both new test-side clipping rules.
The existing mode-specific harmonic/contextual requirements remain mandatory.

### 4.4 Supported-subset recovery

Only under v9.10, if a proposed `supported_fault` finish contains:

- a clipping claim that independently satisfies one complete coherent family;
- `StimulusContext.mode=single_signal`, where the contextual causal policy
  categorically does not support an independent harmonic claim;
- a sibling harmonic claim; and
- no other invalid positive claim,

the recoverable error states that the clipping claim is already independently
supported and that the next finish must preserve its same-run references and
drop the unsupported harmonic sibling. It must not claim the Runtime accepted
or rewrote the finish.

If clipping itself is incomplete, ordinary clipping validation errors remain.
Paired-reference and nominal-single-tone harmonic recovery retain their v9.9
and v9.8 behavior; no subset instruction is emitted for those modes. If a
combined harmonic gate is complete, both claims remain required.

## 5. Data flow

```text
local WAV
  -> deterministic contextual DSP
  -> compact contextual Evidence, including test_clipping_mechanism
  -> one automatic profile_s1_contextual_comparison_v9_10 1.0.0 rule batch
  -> RealLLMPlanner finish
  -> v9.10 coherent-family validation
  -> accept, or ID-bearing recoverable guidance without claim mutation
```

No label, expected outcome, confidence tier, transform provenance, raw WAV, or
full FFT enters PlannerContext.

## 6. Test allocation

Add T-CX231 through T-CX240 without changing T-CX001 through T-CX230:

- T-CX231: preserve v9.9 prompt/policy bytes and all recorded development and
  validation evidence; register T-CX231–T-CX240 exactly once.
- T-CX232: contextual DSP propagates the deterministic test clipping mechanism
  across valid and invalid contextual outcomes.
- T-CX233: contextual Tool emits exactly one compact
  `test_clipping_mechanism` Evidence item and no forbidden payload.
- T-CX234: the additive contextual profile adds only the two test-side rules
  with unchanged 1%/Boolean limits and preserves the original profile bytes.
- T-CX235: automatic contextual closure emits the new test-side PASS/FAIL
  evaluations from the triggering Observation's exact Evidence suffix.
- T-CX236: v9.10 accepts a complete contextual clipping family and rejects
  cross-family or mechanism-only claims.
- T-CX237: v9.10 contextual no-fault accepts a complete test-side clean family
  while retaining every mode-specific harmonic/contextual gate.
- T-CX238: complete clipping plus unsupported harmonic produces supported-
  subset recovery guidance; Runtime does not mutate the decision.
- T-CX239: v9.10 prompt freezes the supported-subset instruction and product
  composition selects the new prompt, policy, and profile identity without
  embedding thresholds in Agent code.
- T-CX240: deterministic replay reproduces both diagnosed failures, verifies
  their corrected legal paths, and runs cumulative architecture, preservation,
  packaging, and registry gates.

Every behavior change follows RED-GREEN TDD. Tests use deterministic fixtures
or preserved observation-level artifacts and never call a real model.

## 7. Evidence and evaluation boundaries

- The original v9.9 validation campaign remains
  `infrastructure_stopped` at 47/60.
- The 13-slot continuation remains diagnostic-only and cannot complete or
  replace the original campaign.
- Historical v9.9 development/validation artifacts and `validation_seal_v3`
  are immutable.
- Because product/profile identity changes, `validation_seal_v3` cannot be
  reused for v9.10 performance claims.
- The strongest implementation conclusion is `v9_10_harness_complete`.
- A v9.10 real-model development confirmation requires separate authorization
  and a new append-only directory.
- Any later validation requires a new preregistration and seal after successful
  development confirmation. Final test remains out of scope.

## 8. Non-goals

- no threshold, transform, label, expected-outcome, scoring, or dataset change;
- no runtime-authored or runtime-rewritten diagnosis;
- no retry-budget or Tool-budget increase;
- no new diagnostic domain;
- no ScriptedPlanner fallback;
- no real-model execution, validation reuse, final-test access, push, or claim
  of performance improvement during implementation.

## 9. Stop gates

Implementation stops if the new contextual clipping family changes any
historical profile identity, requires mixing evidence families, or causes a
previously valid harmonic/combined/no-fault deterministic regression. After
focused tests, the cumulative pytest, Ruff, mypy, architecture, preservation,
`git diff --check 605c8a8`, wheel smoke, and required Python matrix must pass
before `v9_10_harness_complete` may be recorded.
