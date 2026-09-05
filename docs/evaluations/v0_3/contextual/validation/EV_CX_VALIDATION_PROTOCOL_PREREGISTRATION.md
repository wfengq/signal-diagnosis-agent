# V0.3 Contextual Validation Protocol Preregistration

**Status:** PRE-REGISTERED — reviewed and frozen

**Study ID:** `study_v0_3_contextual_validation_1`

**Protocol version:** `1.0.0-prereg`

**Recorded:** 2026-09-05

**Review acknowledgment:** approved 2026-09-05

**Review mode:** `single_reviewer_provenance_audit`

**Inter-review agreement / kappa:** `not_evaluated`

This protocol is prospective. At this stage it does not bind or open validation
audio, materialize cases, run any evaluation arm, or authorize final testing.
There is no delayed-review waiting requirement.

## 1. Purpose and claim boundary

The study evaluates whether the frozen V0.3 Scenario S1 product can use a clean
reference or declared single-tone context to distinguish newly introduced
harmonic distortion from pre-existing harmonic content while preserving
independent clipping detection and conservative behavior on unsupported input.

This is a small external/contextual validation. It is not an official benchmark,
industrial validation, production certification, or an industry standard. It
does not change any accepted V0.2 result.

## 2. Frozen product and development identity

| Item | Frozen value |
|---|---|
| Product code commit | `15c047ced6cbd46a4b4757abdfdacd11e0a12ea1` |
| Development evidence commit | `a45177574ad09d41b4c26c8bdf93e85ca6a7eed8` |
| Development result | 20/20 planner completion; 17/17 outcome, causal exact-set, and grounding |
| Planner | `RealLLMPlanner` |
| Prompt | `v0.3-s1-planner-9.9` |
| Prompt SHA-256 | `27a9315ad85a035c9cc9cbfe5f15ea26c49383d7fb23207989315ae0adb78dc9` |
| Causal policy | `v9_9_paired_reference_recovery` |
| Contextual implementation SHA-256 | `5bc2a3375d5fb5be5c7c77cb0ddba140c240635d549662c9d3221e64acb81ae2` |
| Development manifest SHA-256 | `cca0ee24d8574435761d2d057fd4341c5e015ee7d5337826f796ea832cf047dd` |
| Distortion profile | `profile_s1_distortion` `1.0.0-demo`, SHA `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` |
| Contextual profile | `profile_s1_contextual_comparison` `1.0.0`, SHA `c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58` |
| Scoring identity | `signal_diag.contextual_scoring@1.0.0-dev.1` |
| Intended provider/model | DeepSeek / `deepseek-v4-flash` |

Any drift in these identities before an evaluation arm runs requires a written
protocol amendment and renewed review. The 1% clipping, 5% THD, and 5% contextual
growth values are frozen demonstration thresholds, not SLAs.

## 3. Fixed validation composition

The validation contains exactly 20 cases. Case IDs and asset identities are
bound only during separately authorized construction and frozen before any arm
runs.

### 3.1 Mode distribution

| Mode | Required roles | Count |
|---|---|---:|
| `paired_reference` | clean 1, clipping 2, harmonic 2, combined 2, natural-even/no-growth 2, invalid comparison 1 | 10 |
| `nominal_single_tone` | clean 1, clipping 1, harmonic 1, frequency mismatch 1 | 4 |
| `single_signal` | clean 1, clipping 1, controlled inconclusive 1, domain-out 3 | 6 |

### 3.2 Expected-outcome and causal distribution

| Outcome role | Expected outcome | Expected causal set | Count |
|---|---|---|---:|
| clean / natural-even controls | `no_supported_fault` | `{}` | 5 |
| clipping-only | `supported_fault` | `{clipping}` | 4 |
| harmonic-only | `supported_fault` | `{harmonic_distortion}` | 3 |
| combined | `supported_fault` | `{clipping, harmonic_distortion}` | 2 |
| inconclusive | `inconclusive` | `{}` | 6 |

### 3.3 Confidence and scoring eligibility

| Confidence | Binding population | Count | Outcome/causal scoring |
|---|---|---:|---|
| `strong_ground_truth` | all nine positive cases | 9 | included |
| `reference_supported` | five no-fault controls plus three controlled inconclusive cases | 8 | included |
| `weak_observation` | two domain-out cases | 2 | excluded |
| `unknown` | one domain-out case | 1 | excluded |

The scoreable denominator is fixed at 17. Infrastructure or planner failure on
a scoreable case remains incorrect and never shrinks a denominator. All six
inconclusive roles, including the three unscored domain-out cases, remain in the
separate inconclusive-appropriateness denominator.

Confidence may not be silently downgraded. If construction cannot honestly
satisfy these bindings, construction stops and a reviewed amendment is required.

## 4. Source, license, and isolation requirements

1. Every source must have an authoritative page, license classification,
   attribution, upstream asset identifier, source-recording key, checksum, and
   a statement that upstream labels are not mapped to S1 fault truth.
2. All nine positive cases must derive from license-clear public real recording
   masters and use recorded, deterministic transforms for strong ground truth.
3. The nine positives must use at least five independent parent masters, with no
   more than two scoreable positives from one master.
4. At least 14 of 20 cases must derive from license-clear public real recordings.
5. Reference-supported and unscored cases must span at least three independent
   source/recording families.
6. Speech with unresolved personal information is excluded. Public speech, if
   ever considered, requires an explicit privacy decision; no speech is needed.
7. Noncommercial or redistribution-restricted assets may be reviewed privately
   but are not committed unless their exact license permits the intended use.

A validation case is rejected if it shares any of the following with the 20-case
contextual development set, the legacy 14-case V0.3 development set, or the
sealed V0.2 final external test:

- case ID or WAV SHA-256;
- `parent_master_id` or upstream asset identity;
- `source_recording_key`;
- capture/session/environment lineage;
- transform lineage that uses a forbidden master.

Different crops, channels, gains, or transforms of one recording remain one
lineage group. Use of the same public corpus is permitted only when the exact
recording/master/session identities are disjoint.

## 5. Construction and qualification gates

Construction is deterministic and offline after authorized source acquisition.
It must produce a manifest, source catalog, source decision record, build record,
WAV checksums, qualification report, arm plan, and empty execution ledger.

Hard construction stops:

- any count, mode, role, confidence, or source-composition mismatch;
- any collision on a forbidden identity axis;
- any missing or incompatible reference required by a paired slot;
- positive clipping without `clipping_mechanism=true` plus a substantial
  clipping-rule failure;
- positive paired harmonic without valid comparison plus contextual growth FAIL;
- positive nominal harmonic without a valid declared-tone contract plus the
  frozen affirmative harmonic path;
- combined positive without both independent causal paths;
- natural-even controls without valid comparison and no-growth qualification;
- license, attribution, checksum, provenance, or privacy uncertainty.

Qualification results may reject candidates but may not tune prompt, profiles,
thresholds, labels, expected outcomes, or scoring. Replacement candidates must
preserve the preregistered slot role and split isolation.

## 6. Three frozen evaluation arms

Each arm uses the same sealed test WAV bytes and frozen expected labels. No arm
receives expected outcome, expected causes, confidence truth, transform
provenance, or another arm's output.

Execution order is fixed:

1. `contextual_agent`: v9.9 `RealLLMPlanner` in each slot's preregistered mode;
2. `fixed_pipeline`: deterministic contextual baseline in the same mode;
3. `no_context_ablation`: v9.9 `RealLLMPlanner` in `single_signal` mode on the
   identical test WAV SHA, without reference or nominal stimulus context.

Every LLM invocation is stateless across slots and arms. `ScriptedPlanner` is
forbidden. Each slot/arm is attempted once. A behavioral failure is retained and
not retried. An infrastructure interruption stops the active campaign, preserves
partial artifacts, and requires new written authorization for any continuation;
it is never completed with a test double.

The fixed pipeline is a required comparison artifact. EV-CX pass/fail is decided
by the contextual Agent arm plus the paired-ablation delta gate.

## 7. Frozen metrics

All outcome and causal metrics use failure-as-incorrect treatment.

| Metric | Frozen denominator | Target |
|---|---:|---:|
| Planner/infrastructure completion | 20 | ≥19/20 |
| Outcome accuracy | 17 scoreable | ≥0.80 |
| Causal exact-set accuracy | 17 scoreable | ≥0.75 |
| Causal macro-F1 | labels `{clipping, harmonic_distortion}` over 17 scoreable | ≥0.75 |
| Harmonic precision | all predicted harmonic claims on scoreable cases | ≥0.80 |
| Harmonic recall | 5 harmonic-bearing scoreable cases | ≥4/5 |
| Clipping precision | all predicted clipping claims on scoreable cases | ≥0.80 |
| Clipping recall | 6 clipping-bearing scoreable cases | ≥0.80 |
| Evidence grounding | all claims on completed diagnoses | exactly 1.00 |
| Unsupported positive-claim rate | all predicted positive fault claims | exactly 0.00 |
| Natural-even harmonic false positives | 2 natural-even controls | exactly 0 |
| Inconclusive appropriateness | 6 frozen inconclusive roles | ≥5/6 |
| Unnecessary tool-action rate | all contextual Agent tool actions | ≤0.20 |
| Paired harmonic-bearing ablation delta | 4 paired harmonic/combined slots | contextual correct causal sets minus ablation correct causal sets ≥3 |

If the unsupported-claim denominator is zero, that metric is `not_evaluated`
and blocks `meets_target`. Grounding requires non-empty required evidence/rule
references and same-run resolution; empty required references do not pass.

Metrics must also be reported by mode, expected role, confidence, source family,
and parent master.

## 8. Role hard gates

- no-fault controls: at least 4/5 correct outcomes;
- clipping-only: at least 3/4 exact causal sets;
- harmonic-only: at least 2/3 exact causal sets;
- combined: exactly 2/2 exact causal sets;
- both natural-even controls: 2/2 `no_supported_fault` and zero harmonic claims;
- all six inconclusive roles: at least 5/6 appropriate inconclusive outcomes;
- paired harmonic-bearing slots: ablation delta at least +3/4.

Failure of any aggregate target or role hard gate yields `below_target`.

## 9. Seal and execution controls

Before any arm runs, an append-only seal must cover:

- manifest and all validation WAV SHA-256 values;
- source/license/provenance/build/qualification records;
- code, prompt, policy, implementation, profiles, and scoring identities;
- 20-slot three-arm plan and empty execution ledger;
- fixed case order and arm order.

The seal must be independently verified before separate model authorization is
requested. After sealing, no product code, prompt, rule, threshold, DSP, label,
confidence, asset, manifest, scoring definition, order, or identity may change.

No validation output may be used to tune the frozen system. Any later remediation
requires a new product version and a new disjoint study. Failed and unfavorable
results remain preserved.

## 10. Stop rules and current boundary

This preregistration phase stops for user review. It does not authorize:

- source download or validation materialization;
- opening validation WAV payloads;
- deterministic baseline, ablation, or Agent execution;
- real-model calls;
- final external test;
- presentation or resume claims based on an unexecuted protocol;
- commit or push without separate authorization.
