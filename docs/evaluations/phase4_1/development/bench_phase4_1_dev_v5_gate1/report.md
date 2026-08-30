# Evaluation Report

## Configuration
- benchmark_id: bench_phase4_1_dev_v5_gate1
- config_fingerprint_sha256: 98ae579bd8f9f147a553624a4e58fdf2d58c172fdfc21ac37fbb0bfb1ca8889c
- provider: deepseek
- model: deepseek-v4-flash
- prompt_version: v0.2-s1-planner-5
- repetitions: 5
- max_concurrency: 1

## Dataset
- dataset_id: s1-distortion-synthetic
- version: 1.1.0
- case_count: 24

## Acceptance Status
- harness_status: pending
- benchmark_status: completed
- target_status: below_target

## Agent Metrics
- run_count: 40
- causal_macro_f1: 0.75
- causal_exact_set_accuracy: 0.75
- outcome_accuracy: 0.875
- evidence_grounding_rate: 0.7894736842105263
- unsupported_claim_rate: 0.0

## Baseline Metrics
- run_count: 8
- causal_macro_f1: 0.8333333333333333
- causal_exact_set_accuracy: 0.75
- outcome_accuracy: 0.875
- evidence_grounding_rate: 0.8
- unsupported_claim_rate: 0.16666666666666666

## Per-Case Variation
### case_v11_dev_clean_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v11_dev_clean_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v11_dev_clipping_boundary
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=redundant_rule;inappropriate_replan
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_v11_dev_clipping_strong
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_v11_dev_harmonic_boundary
- agent run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 2: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 3: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 4: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 5: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_v11_dev_harmonic_strong
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=ungrounded_claim
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=ungrounded_claim
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v11_dev_combined_01
- agent run_slot 1: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 2: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 3: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 4: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 5: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v11_dev_invalid_noise_01
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;ungrounded_claim;first_tool_incorrect
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool

## Failures
- agent case_v11_dev_harmonic_boundary run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_v11_dev_combined_01 run_slot 1: inappropriate_replan;exact_set_mismatch
- agent case_v11_dev_invalid_noise_01 run_slot 1: unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent case_v11_dev_harmonic_boundary run_slot 2: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_v11_dev_harmonic_strong run_slot 2: ungrounded_claim
- agent case_v11_dev_combined_01 run_slot 2: inappropriate_replan;exact_set_mismatch
- agent case_v11_dev_invalid_noise_01 run_slot 2: unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent case_v11_dev_harmonic_boundary run_slot 3: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_v11_dev_combined_01 run_slot 3: inappropriate_replan;exact_set_mismatch
- agent case_v11_dev_invalid_noise_01 run_slot 3: unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent case_v11_dev_clipping_boundary run_slot 4: redundant_rule;inappropriate_replan
- agent case_v11_dev_harmonic_boundary run_slot 4: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_v11_dev_harmonic_strong run_slot 4: ungrounded_claim
- agent case_v11_dev_combined_01 run_slot 4: inappropriate_replan;exact_set_mismatch
- agent case_v11_dev_invalid_noise_01 run_slot 4: unnecessary_tool;uncited_knowledge;omitted_rule;first_tool_incorrect
- agent case_v11_dev_harmonic_boundary run_slot 5: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_v11_dev_combined_01 run_slot 5: inappropriate_replan;exact_set_mismatch
- agent case_v11_dev_invalid_noise_01 run_slot 5: unnecessary_tool;omitted_rule;ungrounded_claim;first_tool_incorrect
- fixed_pipeline case_v11_dev_clipping_boundary run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_v11_dev_clipping_strong run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_v11_dev_harmonic_boundary run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_v11_dev_invalid_noise_01 run_slot 1: unnecessary_tool

## Limitations
V0.2 demonstration targets are not industry standards or SLAs.
Demo rule thresholds are not product pass criteria.
Official bundles are append-only and retain failures and run variation.
