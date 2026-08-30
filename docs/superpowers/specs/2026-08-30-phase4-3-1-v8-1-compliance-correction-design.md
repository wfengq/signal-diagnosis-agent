# Phase 4.3.1 Planner v8.1 Compliance Correction Design

**Date:** 2026-08-30

**Status:** Approved in writing on 2026-08-30. §54, T216–T223, D025, and
OQ-009 are frozen as design/test authority. Implementation and every model run
remain gated pending a detailed plan and separate explicit instruction.

**Implementation baseline:** `1b94194` on `phase4-evaluation-design`

**Evidence baseline:**
`docs/evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4/`

## 1. Decision summary

Phase 4.3.1 is a narrow compliance correction for two defects discovered only
after the immutable Phase 4.3 v8 development campaign:

1. T210 was implemented with a global prohibition on clipping-only finish,
   even though frozen §53 permits symptom-specific requests to prioritize and
   close only the indicated fault family.
2. the legacy scoring proxy treats invalid Tool observations as if they had
   produced no Evidence, so the contract-required transition from invalid
   Evidence to a `not_applicable` rule evaluation is incorrectly scored as
   premature or inappropriate.

The selected correction keeps the public Agent and evaluation architecture
unchanged. It adds one coherent compliance prompt identity,
`v0.2-s1-planner-8.1`, and a versioned internal scoring policy for new Phase
4.3.1 campaigns. It does not change the dataset, model, Runtime,
PlannerContext, DSP, Tools, RuleEngine, knowledge system, target bands, or any
historical evaluation asset.

This is not an unrestricted v9 prompt attempt and does not reopen iterative
prompt tuning. D025 documents a one-time exception to D024 because v8 did
not faithfully implement its own frozen request-scope and invalid-Evidence
contracts. If the corrected v8.1 development campaign misses target, the
prompt-only route ends and the next design choice is model capability versus a
PlannerContext contract change.

## 2. Evidence and root cause

The Phase 4.3 deterministic gate passed, and the v8 development campaign ran
40 unique Agent slots on eight development cases with five repetitions per
case. The immutable result is:

```text
benchmark_status=completed
target_status=below_target
evidence_grounding_rate=45/53=0.8490566       target 1.0
timely_stopping_rate=30/40=0.75               target >=0.80
unsupported_claim_rate=8/38=0.2105263         target <=0.05
```

The same campaign passed the behavior bands that v8 was intended to repair,
including first-Tool selection, observation-driven replanning, unnecessary
Tool use overall, and required knowledge usage. The remaining misses cluster
in two deterministic contract-alignment failures.

### 2.1 T210 request-scope defect

The implemented T210 semantic test globally rejects any prompt example that
finishes after clipping-only Evidence. That assertion is too broad. Frozen
§53 says a symptom-specific request may prioritize the indicated family,
whereas a broad or combined request must continue until every viable requested
hypothesis closes.

Because v8 retained only the broad combined example, all ten clipping-case
runs began with both `clipping` and `harmonic_distortion` hypotheses even
though the visible requests were clipping-specific. After clipping was
supported, all ten copied the combined-example reasoning, called harmonic
analysis, and therefore produced the ten late Tool calls that reduced timely
stopping to 30/40.

The correction is not a Runtime keyword router. Request scope remains an LLM
Planner judgment recorded in the existing `TaskAssessment.hypotheses` field.

### 2.2 Claim-polarity and clipping-attribution defect

Eight clipping-case runs emitted an additional causal
`harmonic_distortion` claim:

- three used `fault_type="harmonic_distortion"` while the statement itself
  said that harmonic distortion was not supported or was ruled out;
- five treated clipping-generated odd-order harmonics and THD above the demo
  threshold as an independent harmonic fault.

The frozen deterministic scorer correctly interprets a causal `fault_type` as
an affirmative predicted cause. It intentionally does not perform natural
language negation analysis. A THD rule failure also means only that the
configured demo threshold failed; it does not by itself establish a cause
independent of clipping.

The correction therefore constrains Planner output rather than weakening the
causal scorer. Causal fault claims are affirmative only, and an independent
harmonic fault in the clipping/combined family requires reportable order-2
Evidence under the existing symmetric-synthetic contract.

### 2.3 Invalid Evidence scoring defect

Frozen §53 requires the invalid/noise path to:

1. obtain structured invalid or not-applicable harmonic Evidence;
2. evaluate the configured profile, producing applicable
   `not_applicable` rule judgments;
3. retrieve explanatory knowledge;
4. finish with a traceable inconclusive claim and limitation.

The legacy rule-timeliness scoring proxy currently recognizes prior Evidence
only when its Tool observation status is `success`. It therefore excludes the
invalid Evidence that RuleEngine is expressly required to consume, and can
label the following `not_applicable` rule action as `premature_rule` or
`inappropriate_replan`.

This did not directly create the three missed v8 target bands, but it makes the
evaluation internally inconsistent and must be corrected before another
campaign can be treated as acceptance evidence.

## 3. Scope

### 3.1 In scope

- record OQ-009 and D025 as a one-time compliance exception to D024;
- add frozen additive contract §54 and test-plan T216–T223 after separate
  approval of this written specification;
- add one complete prompt `v0.2-s1-planner-8.1` rather than appending a suffix
  to v8;
- correct request-scope, claim-polarity, and clipping-attribution examples and
  deterministic semantic tests;
- add a versioned internal scoring policy selected from existing
  `BenchmarkConfig.sdk_versions` provenance;
- preserve legacy scoring for v4–v8 configurations and historical trace
  re-scoring;
- add canonical v8.1 development and conditional official campaign identities;
- run one new development campaign and, only after a pass, one official
  campaign;
- preserve honest, immutable bundles and stop gates.

### 3.2 Frozen and unchanged

- dataset `s1-distortion-synthetic` `1.2.0`, including every case, request,
  parameter, seed, condition, policy, split, and held-out byte;
- all public fields and semantics of `PlannerModel`, `PlannerContext`,
  `AgentDecision`, `TaskAssessment`, `DiagnosisClaim`,
  `DistortionDiagnosisRuntime`, evaluation traces, scores, reports, and
  benchmark models;
- DSP algorithms, Tool interfaces, Evidence, RuleEngine, rule profiles,
  comparator behavior, demo thresholds, KnowledgeIndex, and corpus;
- `TargetBands`, causal exact-set semantics, outcome scoring, claim grounding,
  unsupported-claim semantics, first-Tool logic, stopping logic, and all
  denominators other than the versioned invalid-Evidence rule-timing
  correction described here;
- DeepSeek, `deepseek-v4-flash`, model parameters, repetition counts, and
  `profile_s1_distortion` `1.0.0-demo`;
- all v4–v8 prompt bytes, hashes, planners, routes, configurations, fingerprints,
  reports, and committed bundles;
- the sealed dataset-1.2 official held-out split.

### 3.3 Non-goals

- no PlannerContext field or public model change;
- no deterministic Runtime request classifier or forced Tool/rule/knowledge
  action;
- no fixed clipping/FFT/F0/THD pipeline;
- no ScriptedPlanner or fake transport product fallback;
- no threshold, target, dataset, causal truth, scoring-label, or held-out
  change;
- no natural-language negation inference in the deterministic scorer;
- no general scorer rewrite or retroactive migration of historical bundles;
- no v8 rerun, gate4 overwrite, v8.2, v9, or repeated gate5 tuning;
- no Phase 5 implementation, push, or merge.

## 4. Considered approaches

### 4.1 Narrow compliance correction with scoring provenance — selected

This approach corrects the test/prompt mismatch and invalid-Evidence proxy
without changing product architecture or historical results. Explicit scoring
provenance makes the evaluation reproducible and prevents a new scoring rule
from silently changing old benchmarks.

### 4.2 Change model or PlannerContext immediately — deferred

Changing the model or adding controller-visible hypothesis state may ultimately
be necessary, but the v8 evidence is confounded by a known implementation
non-conformance. Making the larger change first would prevent a fair conclusion
about whether the approved §53 behavior can work through the existing product
boundary.

### 4.3 Exempt invalid rule actions or lower targets — rejected

Removing the rule requirement would contradict RuleEngine semantics and would
hide a scorer defect. Lowering target bands after observing results would
invalidate the evaluation gate.

## 5. Planner v8.1 compliance policy

### 5.1 Request scope and hypotheses

The Planner uses the existing `TaskAssessment.hypotheses` field:

- a clipping-specific request begins with `clipping` only;
- a harmonic-specific request begins with `harmonic_distortion` only;
- a generic broad distortion request begins with both supported S1 families;
- a combined or broad request cannot finish after only one still-viable family
  is resolved;
- a symptom-specific request may finish once its requested family is resolved
  and required rule/knowledge work is complete;
- another family is reopened only when a concrete new observation makes it
  viable.

The prompt describes semantic examples, not a deterministic keyword-routing
table. Runtime continues to execute exactly the Planner's valid actions within
the existing limits.

### 5.2 Affirmative causal claims

A causal `DiagnosisClaim.fault_type` of `clipping` or
`harmonic_distortion` represents an affirmative supported cause only.

- Do not emit a causal fault type to express “not supported,” “ruled out,”
  “absent,” or a limitation.
- A clipping-only diagnosis emits only the supported clipping cause.
- When every requested cause is ruled out, use the existing
  `no_supported_fault` semantics.
- When a requested cause is unresolved or unobservable, use the existing
  `inconclusive` semantics with valid same-run references and limitations.

The deterministic scorer remains lexical-free: it scores the structured causal
field, not prose polarity.

### 5.3 Clipping versus independent harmonic distortion

Under the existing synthetic contract:

- a THD value above 5% produces a configured rule failure but does not by
  itself prove an independent harmonic cause;
- supported clipping with only clipping-associated odd orders, including
  orders 3 and 5, supports only `clipping`;
- an independent harmonic-distortion claim requires reportable order-2
  Evidence;
- a clipping-specific request does not call harmonic analysis by default;
- if harmonic analysis is legitimately called and exposes only odd-order
  clipping products, the final causal set remains clipping-only;
- a combined case still requires separate clipping Evidence and reportable
  order-2 harmonic Evidence.

Neither DSP output nor rule thresholds change. The distinction is diagnosis
attribution, not numerical manipulation.

### 5.4 Invalid and not-applicable path

Invalid or not-applicable structured Evidence is still scientific progress.
It can justify a RuleEngine call whose corresponding evaluations are
`not_applicable`. After that action, explanatory knowledge and a traceable
inconclusive finish are appropriate when required by the observable
limitation.

The Planner must not fabricate a numeric result, convert
`not_applicable` to PASS, or skip required same-run references.

## 6. Versioned scoring policy

No public scoring signature or model changes. The existing
`BenchmarkConfig.sdk_versions` map carries scoring provenance.

### 6.1 Identities

```text
legacy campaigns:                   existing legacy scoring semantics
Phase 4.3.1 campaigns:
  signal_diag.scoring = 2.0.0
```

Historical v4–v8 configurations continue to dispatch to legacy semantics, so
their fingerprints and re-scored trace results remain reproducible. A Phase
4.3.1 configuration must declare exactly `signal_diag.scoring=2.0.0`.

### 6.2 Scoring 2.0.0 correction

For rule timeliness and observation-driven replanning, the relevant question
is whether structured Evidence exists for RuleEngine, not whether the parent
Tool observation status was `success`:

- valid Evidence can produce PASS or FAIL under the frozen comparator;
- invalid or not-applicable Evidence can produce NOT_APPLICABLE;
- a rule action following either kind of new structured Evidence is not
  premature merely because the Tool observation was invalid;
- repeated equivalent rule work and rules invoked before any relevant
  structured Evidence remain inappropriate.

All other score formulas, failure codes, target bands, and denominators remain
unchanged.

### 6.3 Provenance and error handling

The scoring-policy identity participates in configuration fingerprinting,
`benchmark_manifest.json`, preflight comparison, reporting provenance, and
bundle checksums.

For Phase 4.3.1, a missing, unknown, malformed, or mismatched scoring version is
`invalid_configuration`. Missing or unreadable `benchmark_manifest.json` or
`metrics.json` is also `invalid_configuration`. These checks occur before
credential access, SDK construction, or held-out scheduling.

Legacy bundles are never rewritten to add a scoring version.

## 7. Components and data flow

The correction stays within existing boundaries:

1. `RealLLMPlanner` serializes the existing leakage-safe PlannerContext using
   the byte-frozen v8.1 prompt.
2. The model returns an existing `AgentDecision` and records request scope in
   existing task-assessment state.
3. Runtime validates and executes the decision without constructing or
   reordering an action.
4. DSP, Tools, RuleEngine, and KnowledgeIndex produce the same deterministic
   observations and references as before.
5. Evaluation assembles the same strict chronological trace.
6. Scoring dispatches internally by the configuration's scoring-policy
   provenance.
7. Writer records immutable, checksummed output using existing report models.

No evaluation label, case identity, scoring policy, causal truth, acceptable
Tool set, raw waveform, or full FFT enters PlannerContext or the outbound model
message.

## 8. Frozen Phase 4.3.1 identities

```text
prompt version:          v0.2-s1-planner-8.1
development campaign:   phase4.3.1-v8.1-development
development benchmark:  bench_phase4_3_1_dev_v8_1_v12_gate5
official campaign:      phase4.3.1-v8.1-official
official benchmark:     bench_official_s1_v12_planner8_1_gate5
scoring policy:          signal_diag.scoring 2.0.0
dataset:                 s1-distortion-synthetic 1.2.0
provider/model:          deepseek / deepseek-v4-flash
rule profile:            profile_s1_distortion 1.0.0-demo
development slots:       8 cases x 5 = 40 Agent slots
official slots:          16 cases x 5 = 80 Agent slots
```

The v8.1 prompt is a complete coherent prompt, not a suffix appended to v8.
The v1.2 development split is reused because it is already authorized tuning
data. No held-out content is inspected to construct v8.1.

## 9. Proposed deterministic acceptance contract

The approved additive contract is recorded in OQ-009,
`CONTRACTS_V0_2.md` §54, `TEST_PLAN_V0_2.md` T216–T223, and D025:

```text
T216  Historical v4–v8 prompt/planner/campaign/configuration/bundle identities
      remain immutable; v8.1 bytes, SHA-256, planner, and configuration are
      independently frozen.

T217  Request scope uses existing hypotheses: clipping-specific starts only
      clipping, harmonic-specific only harmonic, generic broad both; broad or
      combined paths cannot finish while a requested family remains viable.

T218  Causal DiagnosisClaim fields are affirmative only; negative, ruled-out,
      absent, and limitation prose cannot be represented by a causal fault
      type.

T219  Strong clipping with high THD and odd-order-only Evidence remains
      clipping-only; an independent harmonic cause requires reportable order-2
      Evidence.

T220  Legacy scoring is reproducible; scoring policy 2.0.0 recognizes invalid
      or not-applicable structured Evidence as sufficient input for a
      NOT_APPLICABLE rule and appropriate observation-driven replan.

T221  Deterministic fake transport through active RealLLMPlanner plus the real
      Runtime, DSP, Tools, RuleEngine, and KnowledgeIndex proves legal
      clipping-specific, combined, and invalid/noise paths without
      ScriptedPlanner fallback.

T222  Canonical v8.1 identities, scoring provenance, strict preflight,
      one-shot destinations, and development-before-official gates are
      enforced before credentials or held-out access.

T223  T001–T223 pass with zero required skip/xfail; Ruff, mypy, architecture,
      and `git diff --check 1b94194..HEAD` pass; frozen public boundaries,
      dataset, targets, historical assets, and held-out state do not drift.
```

T217 replaces the over-broad T210 implementation assertion with two explicit
requirements: a legal clipping-specific finish and a prohibited broad or
combined early finish. T221 uses real clipping request text and real
deterministic DSP cases, including strong clipping with high THD and odd-order
harmonics.

## 10. Real-model gates and phase acceptance

### 10.1 Development gate5

The exact v8.1 development identity may run once only after:

- prompt bytes and SHA-256 are committed;
- T001–T223 pass with zero required skip/xfail;
- Ruff, mypy, architecture, and baseline diff-check pass;
- strict identity and scoring-policy preflight passes;
- the canonical development destination does not exist;
- credentials are present without being exposed.

All frozen target bands must pass simultaneously. If development is
`completed/below_target` or otherwise does not meet the gate:

- preserve and commit the honest result;
- do not rerun or overwrite the identity;
- do not create v8.2 or v9;
- do not inspect or run official held-out;
- stop and make a new written choice between model capability and
  PlannerContext.

### 10.2 Official gate5

Official may run exactly once only when the byte-identical v8.1 development
campaign is `completed/meets_target` and all identity checks pass.

Phase 4.3.1 is accepted only when:

- deterministic T001–T223 and all static quality gates pass;
- development is `completed/meets_target`;
- official is `completed/meets_target`;
- all 80 official Agent slots are scoreable;
- every prompt, dataset, scoring, profile, provider/model, repetition,
  benchmark, and checksum identity is valid;
- no leakage, forced Runtime action, historical mutation, target reduction,
  or held-out rerun occurred.

An official miss is preserved and cannot be used for tuning or rerun. Phase 5
remains gated after any development or official miss. Passing Phase 4.3.1
authorizes only Phase 5 design and contract freezing, not Phase 5
implementation.

## 11. Implementation governance

Implementation remains assigned to Cursor after written contract and plan
approval. Each Task follows the approved seven-step sequence:

1. the Implementer performs TDD and leaves changes uncommitted;
2. an independent agent performs specification-compliance review;
3. all Critical or Important findings are fixed and independently re-reviewed;
4. an independent agent performs code-quality review;
5. all Critical or Important findings are fixed and independently re-reviewed;
6. the main controller independently verifies focused tests, cumulative tests,
   Ruff, mypy, architecture, and diff-check;
7. the main controller creates the local Task commit.

Tasks are strictly serial in one worktree. No agents concurrently modify that
worktree. Development and official model runs are separate one-shot Tasks and
never overlap implementation. Agent reports are leads, not acceptance evidence;
Git state, immutable assets, and main-controller command output decide status.

There is no push, merge, Phase 5 work, historical-bundle mutation, or cleanup
of the pre-existing untracked `build/` directory.

## 12. Documentation sequence and authority

The approved documentation sequence is:

1. record and approve OQ-009;
2. freeze additive §54, T216–T223, and D025;
3. use the Superpowers writing-plans workflow to create a task-level Cursor
   implementation plan;
4. obtain separate explicit implementation authorization.

Steps 1–2 are complete. Until steps 3–4 pass, this specification does not
authorize source or test changes, model execution, development or official
evaluation, held-out access, Phase 5, push, or merge.
