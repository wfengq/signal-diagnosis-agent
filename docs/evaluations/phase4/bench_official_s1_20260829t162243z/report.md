# Evaluation Report

## Configuration
- benchmark_id: bench_official_s1_20260829t162243z
- config_fingerprint_sha256: 7bda4adae9f27643e6070f56f25f0a7bd38e3bec7e9959f3b59b828578f3c8ef
- provider: deepseek
- model: deepseek-v4-flash
- prompt_version: v0.2-s1-planner-4
- repetitions: 5
- max_concurrency: 1

## Dataset
- dataset_id: s1-distortion-synthetic
- version: 1.0.0
- case_count: 24

## Acceptance Status
- harness_status: pending
- benchmark_status: completed
- target_status: below_target

## Agent Metrics
- run_count: 80
- causal_macro_f1: 0.8396226415094339
- causal_exact_set_accuracy: 0.7875
- outcome_accuracy: 0.9
- evidence_grounding_rate: 0.8947368421052632
- unsupported_claim_rate: 0.0

## Baseline Metrics
- run_count: 16
- causal_macro_f1: 0.8846153846153846
- causal_exact_set_accuracy: 0.8125
- outcome_accuracy: 0.875
- evidence_grounding_rate: 0.85
- unsupported_claim_rate: 0.07692307692307693

## Per-Case Variation
### case_held_clean_01
- agent run_slot 1: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 2: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 3: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 4: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 5: outcome_correct=true failure_codes=omitted_rule
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_clean_02
- agent run_slot 1: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 2: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 3: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 4: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 5: outcome_correct=true failure_codes=omitted_rule
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_clean_03
- agent run_slot 1: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 2: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 3: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 4: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 5: outcome_correct=true failure_codes=omitted_rule
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_clipping_01
- agent run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;omitted_rule
- agent run_slot 2: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent run_slot 3: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent run_slot 4: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;omitted_rule
- agent run_slot 5: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_held_clipping_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 4: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;omitted_rule
- agent run_slot 5: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_held_clipping_03
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_held_clipping_04
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_held_harmonic_01
- agent run_slot 1: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 2: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 3: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 4: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 5: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_held_harmonic_02
- agent run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 2: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 3: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 4: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent run_slot 5: outcome_correct=true failure_codes=omitted_rule
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_held_harmonic_03
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_harmonic_04
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 5: outcome_correct=true failure_codes=omitted_rule
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_combined_01
- agent run_slot 1: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 2: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 3: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 4: outcome_correct=true failure_codes=inappropriate_replan;omitted_rule;exact_set_mismatch
- agent run_slot 5: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_combined_02
- agent run_slot 1: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 2: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- agent run_slot 5: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_combined_03
- agent run_slot 1: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 4: outcome_correct=true failure_codes=omitted_rule
- agent run_slot 5: outcome_correct=true failure_codes=inappropriate_replan;exact_set_mismatch
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_held_invalid_noise_01
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool
### case_held_invalid_noise_02
- agent run_slot 1: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 2: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 3: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 4: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent run_slot 5: outcome_correct=true failure_codes=unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool
### case_dev_clean_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_dev_clean_02
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_dev_clipping_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_dev_clipping_boundary
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_dev_harmonic_boundary
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_dev_harmonic_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_dev_combined_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_dev_invalid_noise_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool

## Failures
- agent case_held_clean_01 run_slot 1: omitted_rule
- agent case_held_clean_02 run_slot 1: omitted_rule
- agent case_held_clean_03 run_slot 1: omitted_rule
- agent case_held_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;omitted_rule
- agent case_held_harmonic_01 run_slot 1: omitted_rule
- agent case_held_harmonic_02 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_combined_01 run_slot 1: inappropriate_replan;exact_set_mismatch
- agent case_held_combined_02 run_slot 1: inappropriate_replan;exact_set_mismatch
- agent case_held_combined_03 run_slot 1: omitted_rule
- agent case_held_invalid_noise_01 run_slot 1: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_invalid_noise_02 run_slot 1: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_clean_01 run_slot 2: omitted_rule
- agent case_held_clean_02 run_slot 2: omitted_rule
- agent case_held_clean_03 run_slot 2: omitted_rule
- agent case_held_clipping_01 run_slot 2: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent case_held_harmonic_01 run_slot 2: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_harmonic_02 run_slot 2: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_harmonic_03 run_slot 2: omitted_rule
- agent case_held_combined_01 run_slot 2: omitted_rule
- agent case_held_combined_02 run_slot 2: inappropriate_replan;exact_set_mismatch
- agent case_held_invalid_noise_01 run_slot 2: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_invalid_noise_02 run_slot 2: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_clean_01 run_slot 3: omitted_rule
- agent case_held_clean_02 run_slot 3: omitted_rule
- agent case_held_clean_03 run_slot 3: omitted_rule
- agent case_held_clipping_01 run_slot 3: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent case_held_clipping_02 run_slot 3: omitted_rule
- agent case_held_harmonic_01 run_slot 3: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_harmonic_02 run_slot 3: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_combined_01 run_slot 3: inappropriate_replan;exact_set_mismatch
- agent case_held_combined_03 run_slot 3: omitted_rule
- agent case_held_invalid_noise_01 run_slot 3: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_invalid_noise_02 run_slot 3: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_clean_01 run_slot 4: omitted_rule
- agent case_held_clean_02 run_slot 4: omitted_rule
- agent case_held_clean_03 run_slot 4: omitted_rule
- agent case_held_clipping_01 run_slot 4: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;omitted_rule
- agent case_held_clipping_02 run_slot 4: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;omitted_rule
- agent case_held_harmonic_01 run_slot 4: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_harmonic_02 run_slot 4: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_harmonic_04 run_slot 4: omitted_rule
- agent case_held_combined_01 run_slot 4: inappropriate_replan;omitted_rule;exact_set_mismatch
- agent case_held_combined_02 run_slot 4: inappropriate_replan;exact_set_mismatch
- agent case_held_combined_03 run_slot 4: omitted_rule
- agent case_held_invalid_noise_01 run_slot 4: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_invalid_noise_02 run_slot 4: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_clean_01 run_slot 5: omitted_rule
- agent case_held_clean_02 run_slot 5: omitted_rule
- agent case_held_clean_03 run_slot 5: omitted_rule
- agent case_held_clipping_01 run_slot 5: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent case_held_clipping_02 run_slot 5: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent case_held_harmonic_01 run_slot 5: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- agent case_held_harmonic_02 run_slot 5: omitted_rule
- agent case_held_harmonic_04 run_slot 5: omitted_rule
- agent case_held_combined_01 run_slot 5: inappropriate_replan;exact_set_mismatch
- agent case_held_combined_02 run_slot 5: inappropriate_replan;exact_set_mismatch
- agent case_held_combined_03 run_slot 5: inappropriate_replan;exact_set_mismatch
- agent case_held_invalid_noise_01 run_slot 5: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- agent case_held_invalid_noise_02 run_slot 5: unnecessary_tool;omitted_rule;required_knowledge_omitted;first_tool_incorrect
- fixed_pipeline case_dev_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_dev_clipping_boundary run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_dev_harmonic_boundary run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_dev_invalid_noise_01 run_slot 1: unnecessary_tool
- fixed_pipeline case_held_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_held_clipping_02 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_held_clipping_03 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_held_clipping_04 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_held_harmonic_01 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_held_harmonic_02 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_held_invalid_noise_01 run_slot 1: unnecessary_tool
- fixed_pipeline case_held_invalid_noise_02 run_slot 1: unnecessary_tool

## Limitations
V0.2 demonstration targets are not industry standards or SLAs.
Demo rule thresholds are not product pass criteria.
Official bundles are append-only and retain failures and run variation.
