# Phase 4.2 Evaluation Integrity and Planner v7 Calibration Design

**Date:** 2026-08-30

**Status:** Approved and frozen on 2026-08-30; Task 1 documentation freeze only;
Tasks 2–10 and all real-model execution are not authorized

**Implementation baseline:** `aefccba` on `phase4-evaluation-design`

**Revision basis:** independent review of draft `6ff7668`

**Scope:** Controlled evaluation-integrity correction plus one coherent planner
v7 calibration. This is not an Agent architecture rewrite and does not authorize
Phase 5.

## 1. Decision summary

The v6 development bundle remains immutable and honest:

```text
benchmark_status = completed
target_status = below_target
causal_macro_f1 = 0.96875
outcome_accuracy = 40 / 40
evidence_grounding_rate = 42 / 49
unsupported_claim_rate = 2 / 32
```

The first v7 draft treated the remaining misses as prompt-only. Independent
review found that this diagnosis was incomplete:

1. the LLM receives semantic evaluation labels through `signal_meta.signal_id`;
2. some v1.1.0 first-Tool expectations differ for cases whose initial
   Planner-visible request and metadata are otherwise indistinguishable;
3. the matched clipping-only control that proves combined-case identifiability
   is intentionally absent from PlannerContext, so the Agent cannot use that
   comparison to distinguish clipping-induced harmonics from an independently
   injected harmonic cause.

Phase 4.2 therefore does not run v7 on v1.1.0. It preserves all v4/v5/v6
evidence and the unexecuted v1.1.0 held-out split, adds dataset version `1.2.0`,
uses opaque evaluation signal IDs, makes first-Tool expectations depend only on
Planner-visible cues, and makes combined causes identifiable from the signal's
own structured Evidence. Only after those integrity corrections does it add
the coherent prompt `v0.2-s1-planner-7`.

## 2. Verified defects

### 2.1 Semantic signal-ID leakage

The initial v6 contexts include values such as:

```text
sig_eval_v11_dev_clipping_strong
sig_eval_v11_dev_invalid_noise_01
sig_eval_v11_dev_combined_01
```

These values expose category and split semantics even though T185/T198 correctly
exclude explicit manifest fields. A model could select a Tool or answer from the
identifier instead of the user request and observations. Checking only JSON key
names is insufficient; outbound values must also be non-semantic.

### 2.2 Hidden first-Tool distinctions

`case_v11_dev_clipping_strong` and `case_v11_dev_invalid_noise_01` have the same
user request and the same ordinary public metadata, but their acceptable first
Tools are disjoint. Once the leaking signal ID is removed, no planner can
reliably satisfy both before observing the waveform. Requiring a hidden
category-specific first Tool is not dynamic selection.

### 2.3 Latent-cause identifiability

D019 validates a combined case by comparing it with a matched clipping-only
control. CONTRACTS §42.4 correctly keeps that control and its separation
tolerance out of PlannerContext. The v6 Agent therefore sees only one signal's
clipping and harmonic observations. For the current third-harmonic development
fixture, elevated odd harmonics can be produced by clipping itself; a prompt
cannot honestly infer the unavailable counterfactual comparison.

Encoding a numeric separation threshold or case-specific answer in the prompt
would violate the rule/profile boundary and overfit development data. The
dataset must instead provide a structured observation whose qualitative form is
separable within the supported synthetic signal family.

### 2.4 Official bundle identity bypass

`_require_v6_development_gate` returns successfully when `metrics.json` says
`completed/meets_target` but `benchmark_manifest.json` is absent. Missing,
unreadable, or identity-mismatched development provenance must block every
official campaign as `invalid_configuration`.

## 3. Approaches considered

### 3.1 Prompt-only v7 on v1.1.0 — rejected

It can improve claim formatting but cannot remove signal-ID leakage or make an
unavailable counterfactual observable. Passing the same cases could reward
memorized evaluation labels rather than general behavior.

### 3.2 Add a new DSP independence estimator — deferred

A fitted clipping model or reference-signal comparison could estimate residual
harmonics, but that adds a new DSP/Tool contract and substantially expands the
S1 MVP. Phase 4.2 does not need it because the synthetic dataset can use
single-signal signatures already represented by harmonic-component Evidence.

### 3.3 New integrity-corrected dataset plus v7 — selected

Create `s1-distortion-synthetic` `1.2.0` with fresh IDs, parameter combinations,
seeds, request assignments, and held-out cases. Preserve the category allocation
and target bands. Use non-semantic signal IDs at the LLM boundary, natural
symptom cues for first-Tool scoring, and even-order harmonic Evidence to make
combined symmetric-clipping cases identifiable from one signal.

The v1.1.0 development and held-out assets remain byte-identical. Its held-out
split remains unexecuted and is not reused for Phase 4.2 acceptance.

## 4. Scope and non-goals

### 4.1 Exact scope

- dataset `s1-distortion-synthetic` `1.2.0`;
- 8 development and 16 held-out cases with the existing category allocation;
- deterministic opaque signal IDs for v1.2 Agent runs;
- first-Tool expectations justified by Planner-visible request/metadata;
- single-signal combined identifiability using reportable even-order harmonic
  Evidence under symmetric synthetic clipping;
- coherent prompt `v0.2-s1-planner-7`;
- additive v7 development and official campaigns;
- strict development-bundle identity preflight shared by v6 and v7;
- deterministic T201-T208 and separate stochastic development/official gates.

### 4.2 Non-goals

- Phase 5, WAV loading, API, UI, or reporting adapters;
- changing `PlannerModel`, `PlannerContext`, `AgentDecision`, Runtime, DSP,
  Tool, RuleEngine, KnowledgeIndex, scoring models, target bands, or report
  schemas;
- adding a new DSP algorithm or Tool;
- lowering grounding or unsupported-claim targets;
- forcing Tool, rule, or knowledge actions in Runtime;
- changing DeepSeek or `deepseek-v4-flash`;
- rewriting v4/v5/v6 prompt bytes, routes, hashes, or report bundles;
- running either v1.1.0 or v1.2.0 held-out before the authorized gate.

## 5. Dataset 1.2.0 contract

### 5.1 Allocation and freshness

The manifest remains `schema_version: "1.0"`, dataset ID
`s1-distortion-synthetic`, profile `profile_s1_distortion` `1.0.0-demo`, and
uses the existing public evaluation models.

```text
development: clean 2, clipping 2, harmonic 2, combined 1, invalid_noise 1
held_out:    clean 3, clipping 4, harmonic 4, combined 3, invalid_noise 2
```

All 24 case IDs, signal parameter combinations, random seeds, and request
assignments are new relative to versions 1.0.0 and 1.1.0. Exact manifest bytes
freeze before any real-model v7 slot. Development and held-out IDs, signal
parameter tuples, seeds, and complete request strings are disjoint.

### 5.2 Opaque Agent signal identity

For v1.2 Agent execution only, materialize each case with:

```text
sig_eval_<24 lowercase hexadecimal characters>
```

The suffix is the first 24 hexadecimal characters of SHA-256 over the UTF-8
bytes:

```text
dataset_id + "\0" + dataset_version + "\0" + case_id
```

The value is deterministic for reproducibility but contains no plain-text case
ID, split, category, generator, fault, or policy token. It is only a repository
lookup key. It must not appear in the v7 prompt or examples. Historical
v1.0/v1.1 runners keep their existing materialization behavior so committed
evidence remains reproducible.

### 5.3 Planner-observable first-Tool rationale

Request text may describe user-observable symptoms without naming a Tool,
generator, injected cause, expected outcome, dataset split, or scoring label.
Examples of legitimate cues are amplitude flattening, tonal overtones, unstable
pitch, or a generic request to inspect all plausible S1 causes.

The manifest must satisfy this mechanical fairness invariant:

```text
If two cases have identical initial Planner-visible request and SignalMeta
after signal_id is removed, their acceptable_first_tools tuples are identical.
```

The invalid/noise route uses a natural unstable-pitch or non-periodic cue and
accepts `estimate_fundamental` and `analyze_harmonic_distortion` as legal first
observations. It may declare alternative sufficient Evidence sets for an
unvoiced/invalid fundamental or invalid harmonic analysis. `detect_clipping`
is not required merely to discover the hidden case category.

Generic all-cause requests may accept both `detect_clipping` and
`analyze_harmonic_distortion`. More specific symptom requests may narrow the
acceptable set only when the narrowing is justified by visible wording.

### 5.4 Single-signal combined identifiability

Within the supported synthetic family, clipping-only fixtures use symmetric
hard clipping of a sinusoid. Symmetric clipping produces the expected odd-order
harmonic pattern. Every v1.2 combined fixture injects a reportable even-order
harmonic before the same symmetric clipping operation.

Each combined case therefore requires:

- valid clipping Evidence supporting `clipping`;
- valid harmonic Evidence supporting `harmonic_distortion`;
- an observable condition on
  `harmonic_order_2_relative_amplitude` supporting `harmonic_distortion`;
- a sufficient Evidence set containing the clipping result, valid harmonic
  result, THD, and second-harmonic component;
- a matched clipping-only control whose second-harmonic component is absent or
  whose value differs by at least the declared dataset-only separation.

For v1.2 identifiability validation only, a missing second-harmonic component
in an otherwise valid matched-control harmonic result is treated as zero
because the Tool deterministically filters components below its reporting
floor. Invalid harmonic analysis is never treated as zero. Historical v1.0 and
v1.1 validation semantics remain unchanged.

The control and numeric separation remain dataset-quality metadata and never
enter PlannerContext. The Agent needs only the structured presence of a
reportable even-order component. It must not invent or cite the hidden
separation threshold.

### 5.5 Clipping-only interpretation

If clipping is supported and any reported harmonic components are only the
odd-order pattern expected from symmetric clipping, the Agent may report that
harmonic content is observed as a consequence or limitation but must not add an
independent `harmonic_distortion` fault claim. A reportable even-order component
in the supported v1.2 synthetic family is separate Evidence for the combined
claim.

For future WAV inputs, v7 must state that harmonic independence may remain
unresolved without a known clipping model or reference. It must not generalize
the symmetric-synthetic assumption to arbitrary hardware clipping.

## 6. Planner v7 contract

```text
version: v0.2-s1-planner-7
composition: one complete prompt, not an appendix
provider: deepseek
model: deepseek-v4-flash
dataset: s1-distortion-synthetic 1.2.0
profile: profile_s1_distortion 1.0.0-demo
```

Exact UTF-8 bytes and SHA-256 freeze before any real-model v7 run.
`RealLLMPlanner` becomes the v7 product path. A private
`_Phase4V6RealLLMPlanner` preserves exact v6 routing. v4/v5 private planners and
all historical campaigns remain unchanged. No real-model failure falls back to
ScriptedPlanner.

The coherent v7 prompt must:

- treat `signal_id` as an opaque lookup identifier and never infer semantics
  from it;
- choose the first action from user-visible symptoms and public metadata;
- keep viable S1 hypotheses open without prescribing a universal pipeline;
- keep observed distortion separate from configured rule acceptance;
- use `no_supported_fault` only for an empty supported cause set;
- emit a pure inconclusive claim set: invalid/not-applicable Evidence, applicable
  rule refs or an explicit not-applicable limitation, used knowledge refs, and
  no sibling no-fault claim;
- distinguish an odd clipping-induced pattern from reportable even-order
  Evidence in the supported symmetric-synthetic family;
- qualify independence for arbitrary WAV or unknown clipping mechanisms;
- cite only same-run Evidence/rule/knowledge IDs;
- never receive raw waveform, full FFT, generator truth, case policy, acceptable
  Tools, sufficient Evidence sets, causal faults, split, or scoring targets.

Prompt examples remain illustrative and use placeholder IDs that cannot match a
live run. They cover pure inconclusive output, clipping-only with induced odd
harmonics, combined clipping plus an even-order component, harmonic-boundary
dual truth, and clean no-fault output.

## 7. Runner and provenance gates

Historical campaign choices remain unchanged. Add:

```text
phase4.2-v7-development
phase4.2-v7-official
```

Canonical benchmark IDs are:

```text
bench_phase4_2_dev_v7_v12_gate3
bench_official_s1_v12_planner7_gate3
```

The development campaign binds v7, dataset 1.2.0 development, 8 cases x 5
slots, the existing profile, provider/model, and unchanged target bands. The
official campaign binds the byte-identical candidate and 16 held-out cases x 5
slots.

Every official preflight requires both `metrics.json` and
`benchmark_manifest.json`. Both must parse, `metrics.json` must be
`completed/meets_target`, and these manifest identity fields must match the
candidate exactly:

```text
benchmark_id, prompt_version, prompt_sha256, dataset_id, dataset_version,
rule_profile_id, rule_profile_version, provider, model, repetitions
```

Missing, unreadable, incomplete, or mismatched provenance is
`invalid_configuration`. The shared correction also closes the v6 missing-
manifest bypass but does not make the below-target v6 gate eligible.

Non-canonical `--benchmark-id` values may be used only for explicitly marked
local exploratory runs outside official/development acceptance directories.
The two Phase 4.2 acceptance campaigns reject a benchmark ID that differs from
their canonical ID.

## 8. Deterministic acceptance extension

T001-T200 remain required and unchanged. Add:

```text
T201  legacy prompt/campaign/bundle immutability and exact v7 identity
T202  opaque v1.2 signal IDs and outbound value-level leakage rejection
T203  v1.2 allocation, freshness, reconstruction, split isolation, and request fairness
T204  v1.2 observable conditions and single-signal combined identifiability
T205  coherent v7 decision, inconclusive, clipping/harmonic, and WAV-limitation policy
T206  fake transport through RealLLMPlanner and real Runtime with same-run references
T207  additive canonical campaigns and identity-complete official preflight
T208  cumulative T001-T208, zero required skip/xfail, Ruff, mypy, architecture,
      and git diff --check against aefccba
```

T202 inspects serialized outbound values, not only key names. T203 proves that
identical initial visible inputs cannot carry disjoint first-Tool requirements.
T204 uses real generators, DSP Tools, and dataset validation; fake decisions do
not substitute for numerical evidence.

## 9. Real-model gate protocol

The 40-slot v1.2 development gate is tuning evidence, not generalization proof.
It runs once for the frozen v7 identity after T001-T208 and static gates pass.
If it is not `completed/meets_target`, preserve the six-file bundle and stop.
Do not rerun the same v7/benchmark identity or automatically create v8.

Only a verified v7 development `completed/meets_target` bundle authorizes one
80-slot v1.2 held-out run. If official is below target, preserve it honestly;
do not tune against or rerun that held-out split. Phase 4.1 product-quality
acceptance requires official `completed/meets_target`, 80 scoreable Agent slots,
valid checksums, and the deterministic/static gates.

The v1.1.0 held-out split remains unexecuted and is not a fallback official set.
`harness_status=pending` in a real-model report remains CLI semantics rather
than a deterministic harness failure.

## 10. Contract mapping

Pending explicit user approval:

```text
CONTRACTS_V0_2.md  §52
TEST_PLAN_V0_2.md  §25 T201-T208
DECISIONS.md       D023
OPEN_QUESTIONS.md  OQ-007 resolved by the approved integrity correction
```

Section 52 is additive but explicitly supersedes the proposed prompt-only v7
draft. It does not alter historical §§41-§51 evidence. The new dataset version,
private runner materialization behavior, and campaign identities apply only to
Phase 4.2.

## 11. Stop conditions

Stop and report when:

- OQ-007, §52, T201-T208, or D023 is not approved;
- implementation would require a public Agent/Runtime/DSP/Tool/rule/knowledge
  contract change;
- v4/v5/v6 identities or committed bundles cannot remain intact;
- any v1.2 PlannerContext exposes case, split, category, generator, fault, or
  scoring semantics through keys or values;
- combined cases cannot validate with real deterministic Evidence;
- deterministic/static gates fail;
- credentials are absent;
- development is not `completed/meets_target`;
- held-out has already been executed or its destination exists;
- official is below target.

No stop condition authorizes lowering targets, modifying truth after model
results, forcing Runtime actions, or starting Phase 5.
