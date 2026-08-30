# Evaluation Report

## Configuration
- benchmark_id: bench_phase4_2_dev_v7_v12_gate3
- config_fingerprint_sha256: c225b0a8ecda16a435e4ba62fc74e4ebd5b945b7bfcf6f2a339350729f272e2f
- provider: deepseek
- model: deepseek-v4-flash
- prompt_version: v0.2-s1-planner-7
- repetitions: 5
- max_concurrency: 1

## Dataset
- dataset_id: s1-distortion-synthetic
- version: 1.2.0
- case_count: 24

## Acceptance Status
- harness_status: pending
- benchmark_status: completed
- target_status: below_target

## Agent Metrics
- run_count: 40
- causal_macro_f1: 0.9
- causal_exact_set_accuracy: 0.875
- outcome_accuracy: 1.0
- evidence_grounding_rate: 1.0
- unsupported_claim_rate: 0.0

## Baseline Metrics
- run_count: 8
- causal_macro_f1: 0.8333333333333333
- causal_exact_set_accuracy: 0.75
- outcome_accuracy: 0.875
- evidence_grounding_rate: 0.8
- unsupported_claim_rate: 0.16666666666666666

## Per-Case Variation
### case_v12_dev_clean_01
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_clean_02
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_clipping_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_v12_dev_clipping_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=redundant_rule;inappropriate_replan
- agent run_slot 3: outcome_correct=true failure_codes=redundant_rule;inappropriate_replan
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_v12_dev_harmonic_01
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_v12_dev_harmonic_02
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;first_tool_incorrect
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_combo_01
- agent run_slot 1: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 2: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 3: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 4: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 5: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_noise_01
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;required_knowledge_omitted
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;required_knowledge_omitted
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;required_knowledge_omitted
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;inappropriate_replan;omitted_rule;required_knowledge_omitted
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool

## Failures
- agent case_v12_dev_clean_01 run_slot 1: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clean_02 run_slot 1: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_harmonic_01 run_slot 1: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_harmonic_02 run_slot 1: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_combo_01 run_slot 1: inappropriate_replan;exact_set_mismatch
- agent case_v12_dev_noise_01 run_slot 1: unnecessary_tool;inappropriate_replan;required_knowledge_omitted
- agent case_v12_dev_clean_01 run_slot 2: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clean_02 run_slot 2: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clipping_02 run_slot 2: redundant_rule;inappropriate_replan
- agent case_v12_dev_harmonic_01 run_slot 2: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_harmonic_02 run_slot 2: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_combo_01 run_slot 2: inappropriate_replan;exact_set_mismatch
- agent case_v12_dev_noise_01 run_slot 2: unnecessary_tool;inappropriate_replan;required_knowledge_omitted
- agent case_v12_dev_clean_01 run_slot 3: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clean_02 run_slot 3: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clipping_02 run_slot 3: redundant_rule;inappropriate_replan
- agent case_v12_dev_harmonic_01 run_slot 3: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_harmonic_02 run_slot 3: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_combo_01 run_slot 3: inappropriate_replan;exact_set_mismatch
- agent case_v12_dev_noise_01 run_slot 3: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clean_01 run_slot 4: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clean_02 run_slot 4: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_harmonic_01 run_slot 4: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_harmonic_02 run_slot 4: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_combo_01 run_slot 4: inappropriate_replan;exact_set_mismatch
- agent case_v12_dev_noise_01 run_slot 4: unnecessary_tool;inappropriate_replan;required_knowledge_omitted
- agent case_v12_dev_clean_01 run_slot 5: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clean_02 run_slot 5: unnecessary_tool;inappropriate_replan
- agent case_v12_dev_harmonic_01 run_slot 5: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_harmonic_02 run_slot 5: unnecessary_tool;inappropriate_replan;first_tool_incorrect
- agent case_v12_dev_combo_01 run_slot 5: inappropriate_replan;exact_set_mismatch
- agent case_v12_dev_noise_01 run_slot 5: unnecessary_tool;inappropriate_replan;omitted_rule;required_knowledge_omitted
- fixed_pipeline case_v12_dev_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_v12_dev_clipping_02 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_v12_dev_harmonic_01 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_v12_dev_noise_01 run_slot 1: unnecessary_tool

## Limitations
V0.2 demonstration targets are not industry standards or SLAs.
Demo rule thresholds are not product pass criteria.
Official bundles are append-only and retain failures and run variation.
