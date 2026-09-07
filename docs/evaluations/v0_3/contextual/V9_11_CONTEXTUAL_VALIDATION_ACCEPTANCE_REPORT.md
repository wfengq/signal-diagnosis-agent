# V0.3 v9.11 Contextual Validation Acceptance Report

**Study:** `study_v0_3_contextual_validation_1`

**Result:** `meets_target` after append-only scoring correction

**Scope:** small external/contextual validation for Scenario S1. This is not an
official benchmark, industrial validation, production certification or an
industry standard. It does not replace or rewrite any accepted V0.2 result.

## What was evaluated

The study tested whether the Agent could use either a clean reference or a
declared single-tone context to distinguish newly introduced harmonic
distortion from harmonic content already present in a real recording, while
preserving independent clipping detection and conservative outcomes on
unsupported inputs.

The frozen validation set contains 20 cases and three arms, executed once in
this order:

1. 20 `contextual_agent` slots;
2. 20 truth-free deterministic `fixed_pipeline` slots;
3. 20 `no_context_ablation` slots using the same test WAV identities without
   reference or nominal context.

The campaign used `RealLLMPlanner`, DeepSeek `deepseek-v4-flash`, prompt
`v0.3-s1-planner-9.11`, and causal policy
`v9_11_mode_aware_no_fault_recovery`. Raw WAVs, expected outcomes, labels,
credentials and final-test data were not sent to the provider.

## Frozen execution identity

| Item | Value |
|---|---|
| Validation seal | `validation_seal_v4` |
| Seal index SHA-256 | `67683f67ca6b0635392d58714adb0d43a136d2c5b933dee42b3b82f99f06b053` |
| Product tree SHA-256 | `626824f6bd2c4c04da566d77914648f2e2d629241d910cb56bcd086bd279c799` |
| Evaluation harness SHA-256 | `f4bdf9b2adefbe7e610b2687e8313aa81406604d73cbbcd9db3c9019947a8618` |
| Prompt SHA-256 | `ecd10554beef79afcf505bf788509f660eb933eaef72ed89693514009fe1134b` |
| Campaign evidence commit | `c46feff` |
| Scorer correction commit | `7daf43f` |
| Corrected evidence commit | `9fad84e` |

## Execution integrity

- All 60 frozen slots reached one terminal state in exact arm-major order.
- Every slot has one campaign attempt; there was no campaign retry.
- There was no infrastructure stop.
- The fixed pipeline made zero provider calls.
- No raw audio, waveform, credential, expected outcome, truth label or raw
  provider request payload is stored in the campaign artifacts.
- Historical seals, development runs and prior validation evidence remain
  unchanged.

## Contextual Agent results

| Metric | Result | Frozen target | Gate |
|---|---:|---:|---|
| Planner completion | 19/20 = 0.95 | at least 0.95 | pass |
| Outcome accuracy | 16/17 = 0.941 | at least 0.80 | pass |
| Causal exact-set accuracy | 16/17 = 0.941 | at least 0.75 | pass |
| Causal macro-F1 | 0.955 | at least 0.75 | pass |
| Harmonic precision | 5/5 = 1.00 | at least 0.80 | pass |
| Harmonic recall | 5/5 = 1.00 | at least 0.80 | pass |
| Clipping precision | 5/5 = 1.00 | at least 0.80 | pass |
| Clipping recall | 5/6 = 0.833 | at least 0.80 | pass |
| Evidence grounding | 21/21 = 1.00 | exactly 1.00 | pass |
| Unsupported positive claims | 0/10 = 0.00 | exactly 0.00 | pass |
| Inconclusive appropriateness | 6/6 = 1.00 | at least 5/6 | pass |
| Natural-even harmonic false positives | 0/2 | exactly 0 | pass |
| Unnecessary Tool-action rate | 0/17 = 0.00 | at most 0.20 | pass |
| Paired harmonic ablation delta | +4 | at least +3 | pass |

Every preregistered aggregate gate and role hard gate passed.

## Comparison arms

The deterministic fixed pipeline achieved 17/17 outcome and causal exact-set
accuracy. The no-context ablation achieved 10/17 outcome accuracy and 11/17
causal exact-set accuracy, with harmonic recall 0/5. The contextual Agent's
paired-harmonic causal advantage over ablation was +4, meeting the frozen gate.
These comparisons support the narrower conclusion that declared context added
diagnostic value on the preregistered paired cases; they do not establish
general superiority over all fixed pipelines or all audio domains.

## Scoring correction and evidence preservation

The generated campaign summary initially recorded `below_target`. Independent
review found that the scorer incorrectly used the fixed 17-case outcome
denominator for two claim-level metrics. It therefore counted the sole
diagnosis-less behavioral failure as an ungrounded and unsupported claim.

The implementation was corrected with TDD to use the preregistered populations:

- all claims on completed diagnoses for evidence grounding;
- all predicted positive fault claims for unsupported-claim rate.

The correction also added deterministic reconstruction from the immutable
`result.json` files and rejects impossible claim-count states. Replaying the
preserved campaign produces 21/21 grounded claims and 0/10 unsupported positive
claims. The original `run_summary.json`, `metrics.json`, `audit_report.json`,
`STATUS.md` and execution ledger retain their original bytes and hashes. The
append-only `corrected_scoring.json` is the authoritative corrected verdict.

## Retained failure

Case `675073735bc06f76` is the only contextual-Agent behavioral failure. It is a
strong-ground-truth clipping case. The model repeatedly proposed a supported
clipping claim together with an unsupported harmonic sibling; runtime correctly
rejected those finishes and the slot ended at the frozen retry limit without a
diagnosis. Failure-as-incorrect treatment remains in planner completion,
outcome, causal accuracy and clipping recall. It contributes no nonexistent
claim to claim-level populations.

## Acceptance conclusion

The complete one-shot v9.11 contextual validation meets every frozen aggregate
and role target after the documented scorer implementation correction. This
supports a bounded claim: on this 20-case external/contextual study, the product
used reference or declared-tone context to improve harmonic attribution while
remaining grounded and conservative.

The result does not erase the V0.2 incremental external-WAV study's
`below_target` result, does not create a contextual final external test, and
does not establish industrial robustness, production readiness or a general
audio-diagnosis benchmark.

## Evidence

- Preregistration: `validation/EV_CX_VALIDATION_PROTOCOL_PREREGISTRATION.md`
- Seal and construction: `validation/study_v0_3_contextual_validation_1/validation_seal_v4/`
- Original campaign: `validation/study_v0_3_contextual_validation_1/agent_v9_11_validation_run_1/`
- Independent audit: `agent_v9_11_validation_run_1/INDEPENDENT_AUDIT.md`
- Scoring correction: `agent_v9_11_validation_run_1/SCORING_CORRECTION.md`
- Corrected metrics: `agent_v9_11_validation_run_1/corrected_scoring.json`
