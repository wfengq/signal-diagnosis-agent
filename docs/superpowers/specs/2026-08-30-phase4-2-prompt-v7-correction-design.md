# Phase 4.2 Prompt v7 Correction Design

**Date:** 2026-08-30

**Status:** Draft pending approval; implementation is not authorized

**Baseline:** `aefccba` (`phase4-evaluation-design`)

**Scope:** Narrow Phase 4.2 prompt-and-gate calibration after the immutable
v6 development miss. This is not an architecture rewrite.

## 1. Purpose

The v6 development campaign is valid, complete, and below target. The
immutable bundle at
`docs/evaluations/phase4_1/development/bench_phase4_1_dev_v6_gate2/` contains
40 scoreable DeepSeek Agent slots over the eight v1.1.0 development cases and
eight deterministic baseline slots. It records:

```text
benchmark_status = completed
target_status = below_target
causal_macro_f1 = 0.96875
outcome_accuracy = 40 / 40
evidence_grounding_rate = 42 / 49
unsupported_claim_rate = 2 / 32
```

The deterministic system remains green (`523 passed`, Ruff, mypy, and
`git diff --check f9392c2..HEAD`). Runtime, Tools, rules, knowledge, scorer,
and v6 wiring are not the failing layer. The remaining misses are concentrated
in two prompt behaviors. Phase 4.2 adds one coherent prompt
`v0.2-s1-planner-7` and a new development verification identity before any
v1.1.0 held-out run.

This design does not weaken targets, change evaluation truth, modify DSP or
rule calculations, force actions in the Runtime, rerun v6 gate2, or open
held-out.

## 2. Verified remaining failures

v6 already corrected the v5 contradictions: harmonic-boundary dual truth,
combined-hypothesis coverage, empty inconclusive claims, and no-fault-as-extra-
cause. Those v5 5/5 outcome misses are gone. The leftover target misses are:

```text
evidence_grounding_min = 1.0          observed 0.857  (7 ungrounded claims)
unsupported_claim_rate_max = 0.05    observed 0.0625 (2 unsupported claims)
```

All seven ungrounded claims and both unsupported claims sit on two development
cases.

### 2.1 `case_v11_dev_invalid_noise_01` — 7 ungrounded claim slots

The case requires first-tool `analyze_harmonic_distortion`, an invalid harmonic
observation, required knowledge, and an `inconclusive` outcome. All five Agent
slots finished `inconclusive` and outcome-correct, but:

1. every slot started with `detect_clipping` (`first_tool_incorrect`);
2. slots 1, 3, and 5 then called `estimate_fundamental` (invalid) and mixed
   valid clipping Evidence into a single `inconclusive` claim, scoring `0 / 1`
   grounded;
3. slots 2 and 4 called `analyze_harmonic_distortion` second, then emitted a
   sibling `no_supported_fault` clipping claim plus a grounded inconclusive
   harmonic claim, scoring `1 / 2` grounded;
4. slot 5 omitted required knowledge.

Grounding requires each claim to cite same-run IDs **and** at least one
Evidence item whose case condition lists that `fault_type` in
`supports_claims`. This noise case only supports `inconclusive`. Valid clipping
Evidence therefore cannot ground an inconclusive claim, and a
`no_supported_fault` sibling is extra ungrounded structure when the diagnosis
is already inconclusive.

v6 §5.4 required a traceable inconclusive claim, but it did not forbid mixing
ruled-out-family Evidence or emitting `no_supported_fault` beside
`inconclusive`.

### 2.2 `case_v11_dev_clipping_strong` — 2 unsupported harmonic claims

The case causal set is clipping only. Slots 2, 3, and 5 finished with a
grounded clipping-only diagnosis. Slots 1 and 4 continued after sufficient
clipping Evidence into `analyze_harmonic_distortion`, observed THD ≈ 12.29%
(clipping-induced harmonics), and added an unsupported
`harmonic_distortion` claim.

v6 §5.1 said to keep every still-viable hypothesis open until resolved. That
fixed combined-case early stopping, but over-generalized: after clipping is
already supported, elevated THD is often a consequence of clipping rather than
an independent harmonic cause. Combined cases remain dual-fault only when a
separable signature exists. This case has no such signature.

The same unsupported pair appears on the deterministic fixed baseline for this
case, which confirms the scorer is applying the frozen causal set. The Agent
regression is prompt policy, not DSP or scoring.

### 2.3 What this is not

- Not a Runtime, Tool, RuleEngine, KnowledgeIndex, or scorer defect.
- Not a reason to lower `evidence_grounding_min` or
  `unsupported_claim_rate_max`.
- Not a reason to change PlannerContext, the DeepSeek model, or the dataset.
- Not permission to inspect or run v1.1.0 held-out cases.

## 3. Approaches considered

### 3.1 Lower the two missed target bands — rejected

The bands are frozen product-behavior gates. Changing them after seeing
development results would make the later official run uninterpretable.

### 3.2 Rerun v6 gate2 or retune v6 in place — rejected

The v6 version, hash, and gate2 bundle are committed evidence. Rewriting v6
bytes or repeating the same development identity as a new “pass” destroys
provenance. §51 already required a new written decision after a development
miss.

### 3.3 Open held-out now — rejected

Official 80-slot execution is one-shot and development-gated. Running it after
`below_target` would spend the sealed split on an unready candidate.

### 3.4 Change Runtime, force tools, or switch models — rejected

The failures are claim composition and hypothesis-viability judgments the
planner already has the information to make. Forcing a tool sequence would
violate the Hybrid Agent contract.

### 3.5 Add a coherent v7 prompt, harden official identity checks, and use a
new development asset — approved design

Create `v0.2-s1-planner-7` as one self-contained system prompt. Preserve v4,
v5, v6, their hashes, planners, CLI routes, and all committed bundles. Add
separate v7 development and official campaign identities. Fix the official
preflight so a missing `benchmark_manifest.json` is `invalid_configuration`,
not an identity skip. Reuse only the v1.1.0 development split under a **new**
benchmark ID.

## 4. Prompt identity and composition

```text
version: v0.2-s1-planner-7
composition: one complete prompt, not v6 + appendix
provider: deepseek
model: deepseek-v4-flash
dataset: s1-distortion-synthetic 1.1.0
profile: profile_s1_distortion 1.0.0-demo
```

Exact bytes and SHA-256 freeze during implementation before any real v7 slot.
`RealLLMPlanner` becomes the v7 product planner only after deterministic
tests pass. Private planners preserve v4, v5, and v6 campaign reproduction.
Product failure never falls back to ScriptedPlanner or a fake transport.

## 5. Coherent v7 decision policy

Keep the v6 policies that already work:

- no fixed Tool pipeline;
- observed distortion and configured rule acceptance remain independent;
- `no_supported_fault` is only a final empty-cause-set conclusion;
- combined cases still require separate harmonic Evidence;
- inconclusive results remain traceable, with knowledge when retrieval is used;
- same-run references only; no evaluation leakage into PlannerContext.

Add these v7 refinements.

### 5.1 Inconclusive citation purity

When the outcome is `inconclusive`, emit exactly the inconclusive claim set
needed to explain what could not be established. That claim cites only
invalid or not-applicable Evidence (and applicable `ruleval_*` /
used `know_*` IDs). It does not cite valid Evidence from a different fault
family. It does not add a sibling `no_supported_fault` claim.

Valid clipping observations may appear in the narrative of the limitation or
in earlier observations; they are not diagnosis claims when harmonic
invalidity already forces `inconclusive`.

### 5.2 Choose the observation that can resolve the blocking uncertainty

On an unreliable or non-periodic signal, the informative first observation is
the analysis that can produce the invalid/not-applicable Evidence, typically
harmonic analysis—not a generic clipping probe. This remains observation-
driven, not a hardcoded pipeline.

### 5.3 Clipping-induced harmonics are not a second cause by default

After clipping Evidence is sufficient for a clipping diagnosis, do not add
`harmonic_distortion` merely because THD or harmonic amplitudes are elevated.
Those readings are often consequences of clipping. A second harmonic claim
requires independent harmonic Evidence that is not explained by the already-
supported clipping observation (the separable-signature pattern used by
combined cases). If that independent signature is absent, stop with clipping
only.

This must not regress `case_v11_dev_combined_01`: when a separable harmonic
signature exists, both claims remain required.

## 6. Examples in the v7 prompt

Retain v6 example shapes for clipping support, harmonic-boundary dual truth,
combined dual claims, and clean `no_supported_fault`. Replace or add examples
so they cannot re-teach the leftover failures:

- inconclusive cites only invalid harmonic Evidence, NOT_APPLICABLE rule refs,
  a knowledge ref, and a limitation — no clipping Evidence refs and no
  `no_supported_fault` sibling;
- clipping-strong finish contains only a clipping claim after sufficient
  clipping Evidence, even if a later harmonic spectrum would show high THD;
- combined finish still contains both clipping and harmonic claims with
  separate Evidence.

Example IDs remain visibly illustrative placeholders.

## 7. Official identity-gate repair

`_require_v6_development_gate` currently returns successfully when
`metrics.json` is `completed/meets_target` but `benchmark_manifest.json` is
missing, skipping prompt/dataset/profile/provider identity comparison. That
bypass is a contract defect for any later official campaign.

The v7 official preflight, and the shared helper it reuses, must reject a
bundle when either file is missing, unreadable, or identity-mismatched. The
required identity fields remain:

```text
prompt_version, prompt_sha256, dataset_id, dataset_version,
rule_profile_id, rule_profile_version, provider, model
```

This repair does not authorize running held-out. v6 official stays bound to
the unmet v6 development gate.

## 8. Backward-compatible runner identities

Unchanged historical routes:

```text
phase4.1-development          → v5
phase4.1-official             → v5
phase4.1-v6-development       → v6
phase4.1-v6-official          → v6, still blocked by v6 below_target
```

Additive v7 routes:

```text
phase4.1-v7-development
phase4.1-v7-official
```

New verification assets, never a rerun of gate2:

```text
docs/evaluations/phase4_1/development/bench_phase4_1_dev_v7_gate3/
docs/evaluations/phase4_1/official/bench_official_s1_v11_planner7_gate3/
```

Development is 8 × 5 on the existing v1.1.0 development split only. Official
is 16 × 5 held-out, once, only after `completed/meets_target` on gate3, using
the byte-identical v7 candidate. Target bands are unchanged.

## 9. Deterministic acceptance extension

Keep T001–T200. Add:

```text
T201  v4/v5/v6 immutability plus exact v7 version/hash
T202  v7 inconclusive purity, first-observation choice, and clipping-vs-harmonic independence
T203  real planner boundary, runtime routes, no leakage, same-run refs, no v6/v5 regression
T204  additive v7 campaigns, new IDs, official identity-complete bundle requirement
T205  cumulative T001–T205 and static/architecture/diff quality gates against aefccba
```

## 10. Real-model gate protocol

Development gate3 runs exactly once after the deterministic gate is green.
If the result is not `completed/meets_target`, retain the honest bundle and
stop before held-out. Do not automatically create v8, change context/model/
runtime, or rerun gate3.

Official gate3 is forbidden until that development result exists. After an
official miss, keep the honest bundle and do not retune on the same held-out
set.

`harness_status=pending` in reports remains CLI semantics, not a repository
harness failure.

## 11. Proposed contract mapping

Pending user approval of OQ-007:

```text
CONTRACTS_V0_2.md  §52
TEST_PLAN_V0_2.md  §25 T201–T205
DECISIONS.md       D023
```

Do not treat these sections as frozen until that approval is explicit.

## 12. Stop conditions

Stop and report rather than broadening when:

- OQ-007 or §52/T201–T205/D023 is not approved;
- a frozen public contract appears to require modification;
- v4/v5/v6 bytes, hashes, routes, or evidence cannot remain reproducible;
- a correct prompt-only implementation would require PlannerContext, Runtime,
  scorer, targets, model, or dataset changes;
- development gate3 is not `completed/meets_target`;
- the official destination already exists or held-out has been inspected.

## 13. Non-goals

- Phase 5
- lowering target bands
- rewriting v6 or reusing `bench_phase4_1_dev_v6_gate2` as a new pass
- opening v1.1.0 held-out before v7 development meets target
- controller-forced DSP, rule, or knowledge actions
- changing DeepSeek / `deepseek-v4-flash`
