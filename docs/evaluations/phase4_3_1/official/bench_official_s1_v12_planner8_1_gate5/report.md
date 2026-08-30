# Evaluation Report

## Configuration
- benchmark_id: bench_official_s1_v12_planner8_1_gate5
- config_fingerprint_sha256: 48400b3a39d21b51663c746ef2303d1e3905c585d3d286611462a5ab71c46cf3
- provider: deepseek
- model: deepseek-v4-flash
- prompt_version: v0.2-s1-planner-8.1
- repetitions: 5
- max_concurrency: 1

## Dataset
- dataset_id: s1-distortion-synthetic
- version: 1.2.0
- case_count: 24

## Acceptance Status
- harness_status: pending
- benchmark_status: completed
- target_status: meets_target

## Agent Metrics
- run_count: 80
- causal_macro_f1: 1.0
- causal_exact_set_accuracy: 1.0
- outcome_accuracy: 0.9875
- evidence_grounding_rate: 1.0
- unsupported_claim_rate: 0.0

## Baseline Metrics
- run_count: 16
- causal_macro_f1: 0.8571428571428572
- causal_exact_set_accuracy: 0.75
- outcome_accuracy: 0.875
- evidence_grounding_rate: 0.8095238095238095
- unsupported_claim_rate: 0.14285714285714285

## Per-Case Variation
### case_v12_held_clean_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_clean_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_clean_03
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_clipping_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_v12_held_clipping_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_v12_held_clipping_03
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_v12_held_clipping_04
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_v12_held_harmonic_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_v12_held_harmonic_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_v12_held_harmonic_03
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_harmonic_04
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_combo_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_combo_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_combo_03
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_held_noise_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool
### case_v12_held_noise_02
- agent run_slot 1: outcome_correct=true failure_codes=redundant_rule;inappropriate_replan
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=false failure_codes=required_knowledge_omitted;outcome_mismatch
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool
### case_v12_dev_clean_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_clean_02
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_clipping_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_v12_dev_clipping_02
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_v12_dev_harmonic_01
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_v12_dev_harmonic_02
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_combo_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_noise_01
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool

## Failures
- agent case_v12_held_noise_02 run_slot 1: redundant_rule;inappropriate_replan
- agent case_v12_held_noise_02 run_slot 5: required_knowledge_omitted;outcome_mismatch
- fixed_pipeline case_v12_dev_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_v12_dev_clipping_02 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_v12_dev_harmonic_01 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_v12_dev_noise_01 run_slot 1: unnecessary_tool
- fixed_pipeline case_v12_held_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_v12_held_clipping_02 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_v12_held_clipping_03 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_v12_held_clipping_04 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_v12_held_harmonic_01 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_v12_held_harmonic_02 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_v12_held_noise_01 run_slot 1: unnecessary_tool
- fixed_pipeline case_v12_held_noise_02 run_slot 1: unnecessary_tool

## Limitations
V0.2 demonstration targets are not industry standards or SLAs.
Demo rule thresholds are not product pass criteria.
Official bundles are append-only and retain failures and run variation.
