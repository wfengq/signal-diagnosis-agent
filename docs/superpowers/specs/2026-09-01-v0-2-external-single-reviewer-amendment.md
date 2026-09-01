# V0.2 External Single-Reviewer Provenance Audit Amendment

**Date:** 2026-09-01  
**Status:** Approved by explicit user authorization on 2026-09-01  
**Baseline design:** `docs/superpowers/specs/2026-09-01-v0-2-real-world-validation-design.md`  
**Contracts:** additive EV-C025 in `docs/EXTERNAL_VALIDATION_CONTRACTS_V0_2.md`  
**Supersedes:** mandatory 14-day Round 2 gate for sealing and experiment completion

## 1. Problem statement

The original protocol required a 14-day delayed blind Round 2 re-review before
final sealing. The study has one human reviewer and cannot honestly claim
inter-rater reliability. Fabricating wait times or agreement statistics is
forbidden. Task 12 authorization explicitly cancels Round 2 as a mandatory gate.

## 2. Frozen unchanged

- transform `signal_diag.external_transform` `1.1.0` with frozen `alpha=0.50`,
  `q=0.03`, `post_gain=0.8`, `attenuation=0.85`;
- development and validation materialization (`7993f0c`);
- pilot v1–v4 failure/success reports;
- `delayed_blind_review` mode and `score_delayed_review` for historical tests;
- disagreement downgrade policy (EV-C016);
- write-once sealing, scoreability mask, and protected-asset audit.

## 3. New review mode

```text
review_mode: single_reviewer_provenance_audit
```

Round 1 records source/provenance review, independent measurements, confidence,
eligible outcome, causal set, and reason codes before any Agent result is
available. No Round 2 delay is required for sealing.

### 3.1 B `strong_ground_truth` provenance

B degraded cases may carry `strong_ground_truth` **only** when all of the
following hold:

- `source_group == "B"` and `external_class` in `{clipping, harmonic, combined}`;
- `transform` is present with frozen `transform_id`, `transform_version`,
  `parameters_identity`, `input_sha256`, and `output_sha256`;
- `transform.output_sha256 == case.wav_sha256`;
- `transform.input_sha256` matches the clean parent master digest in the same
  `parent_master_id` family;
- Round 1 review record cites transform provenance reason codes.

### 3.2 A/C confidence caps

- Group A must never be `strong_ground_truth`.
- Group C must never be `strong_ground_truth`.
- When reference analysis is insufficient, A/C remain `weak_observation` or
  `unknown`; they are never upgraded by review.

### 3.3 Agreement fields

Under `single_reviewer_provenance_audit`:

```text
review_agreement.evaluation_status: not_evaluated
raw_outcome_agreement:            null
causal_set_agreement:             null
outcome_cohen_kappa:              null
confidence_quadratic_kappa:       null
```

`evaluate_external_targets` must not require agreement statistics when
`evaluation_status == not_evaluated`.

### 3.4 Disclosure (report.md)

Append-only bundles must include:

```text
This study used a single reviewer with provenance audit only. No delayed blind
re-review was performed. Inter-rater agreement and Cohen kappa were not
evaluated.
```

## 4. Sealing gate changes

`seal_final_external_test` accepts `review_mode=single_reviewer_provenance_audit`
without Round 2 or elapsed delay. It runs `audit_single_reviewer_provenance`
instead of `score_delayed_review`. Agreement targets are not enforced when
`evaluation_status == not_evaluated`.

`delayed_blind_review` remains available for preservation tests; EV-T037
14-day rejection applies only to that mode.

## 5. Process order (authorized Task 12)

1. Written design/contracts/test plan/decision record updates (this document).
2. TDD modify sealing/review logic.
3. Round 1 source/label evidence audit + Task 11 gate re-run.
4. If pass: materialize + write-once seal 28 `final_external_test` cases.
5. Frozen transform config (§2).
6. Run deterministic fixed pipeline on sealed final.
7. **STOP** — wait for real model authorization.

## 6. Explicit non-actions

- no fabricated 14-day wait or agreement/kappa statistics;
- no real model, `ScriptedPlanner` fallback, or tuning from final data;
- no modification of historical official/Demo/prompt/scoring/profile/v0.2.0 tag;
- no push.
