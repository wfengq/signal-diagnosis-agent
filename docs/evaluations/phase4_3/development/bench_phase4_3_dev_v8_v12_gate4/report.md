# Evaluation Report

## Configuration
- benchmark_id: bench_phase4_3_dev_v8_v12_gate4
- config_fingerprint_sha256: aa54a0bdd0e0082e6dc38651abb5c6c00ce19853fca30706bbab349093dec7c8
- provider: deepseek
- model: deepseek-v4-flash
- prompt_version: v0.2-s1-planner-8
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
- causal_macro_f1: 0.8947368421052632
- causal_exact_set_accuracy: 0.8
- outcome_accuracy: 1.0
- evidence_grounding_rate: 0.8490566037735849
- unsupported_claim_rate: 0.21052631578947367

## Baseline Metrics
- run_count: 8
- causal_macro_f1: 0.8333333333333333
- causal_exact_set_accuracy: 0.75
- outcome_accuracy: 0.875
- evidence_grounding_rate: 0.8
- unsupported_claim_rate: 0.16666666666666666

## Per-Case Variation
### case_v12_dev_clean_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_clean_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_clipping_01
- agent run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent run_slot 2: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent run_slot 3: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent run_slot 4: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent run_slot 5: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool
### case_v12_dev_clipping_02
- agent run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent run_slot 2: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent run_slot 3: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent run_slot 4: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent run_slot 5: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
### case_v12_dev_harmonic_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=false failure_codes=ungrounded_claim;exact_set_mismatch;outcome_mismatch
### case_v12_dev_harmonic_02
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_combo_01
- agent run_slot 1: outcome_correct=true failure_codes=
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=
- agent run_slot 5: outcome_correct=true failure_codes=
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=
### case_v12_dev_noise_01
- agent run_slot 1: outcome_correct=true failure_codes=premature_rule;inappropriate_replan
- agent run_slot 2: outcome_correct=true failure_codes=
- agent run_slot 3: outcome_correct=true failure_codes=
- agent run_slot 4: outcome_correct=true failure_codes=premature_rule;inappropriate_replan
- agent run_slot 5: outcome_correct=true failure_codes=premature_rule;inappropriate_replan
- fixed_pipeline run_slot 1: outcome_correct=true failure_codes=unnecessary_tool

## Failures
- agent case_v12_dev_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_clipping_02 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_noise_01 run_slot 1: premature_rule;inappropriate_replan
- agent case_v12_dev_clipping_01 run_slot 2: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clipping_02 run_slot 2: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_clipping_01 run_slot 3: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_clipping_02 run_slot 3: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_clipping_01 run_slot 4: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan
- agent case_v12_dev_clipping_02 run_slot 4: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_noise_01 run_slot 4: premature_rule;inappropriate_replan
- agent case_v12_dev_clipping_01 run_slot 5: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_clipping_02 run_slot 5: late_tool_after_sufficiency;unnecessary_tool;inappropriate_replan;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- agent case_v12_dev_noise_01 run_slot 5: premature_rule;inappropriate_replan
- fixed_pipeline case_v12_dev_clipping_01 run_slot 1: late_tool_after_sufficiency;unnecessary_tool
- fixed_pipeline case_v12_dev_clipping_02 run_slot 1: late_tool_after_sufficiency;unnecessary_tool;ungrounded_claim;exact_set_mismatch;unsupported_fault_claim
- fixed_pipeline case_v12_dev_harmonic_01 run_slot 1: ungrounded_claim;exact_set_mismatch;outcome_mismatch
- fixed_pipeline case_v12_dev_noise_01 run_slot 1: unnecessary_tool

## Limitations
V0.2 demonstration targets are not industry standards or SLAs.
Demo rule thresholds are not product pass criteria.
Official bundles are append-only and retain failures and run variation.
