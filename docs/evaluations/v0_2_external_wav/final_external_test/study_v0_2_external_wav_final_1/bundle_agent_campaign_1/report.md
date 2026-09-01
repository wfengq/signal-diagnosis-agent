# External WAV Validity Study Report

## Study
- study_id: v0.2-external-wav-validity-1
- dataset_id: s1-distortion-external-wav
- dataset_version: 1.0.0
- seal_id: bc22266e58076ab9c94ef76ed08e2d2fbba5efa62bcc42d1b1cfac290282f778
- manifest_sha256: 5d8e74437eac2fc856405ef2c3abd8b5288c965c37b0ee71f581e479f0e147a2
- case_count: 52
- external_scoring_id: signal_diag.external_scoring
- external_scoring_version: 1.0.0

## Acceptance Status
- harness_status: external_validation_completed/below_target
- target_status: below_target

## Aggregate Metrics
- outcome_accuracy: 30/48 (value=0.625)
- causal_exact_set_accuracy: 23/48 (value=0.4791666666666667)
- evidence_grounding: 21/61 (value=0.3442622950819672)
- unsupported_same_run_claim_rate: 21/41 (value=0.5121951219512195)
- unnecessary_tool_action_rate: 47/112 (value=0.41964285714285715)
- inconclusive_appropriateness: 4/12 (value=0.3333333333333333)
- positive_causal_claims_on_unscored: 8/8 (value=1.0)
- scoreable_coverage: 48/56 (value=0.8571428571428571)
- causal_macro_f1: 0.6212121212121212

## Stratification
- capture_configuration_key=cap_esc_src_file:17367: outcome_accuracy 1/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=cap_nsynth_instrument:flute_acoustic: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- capture_configuration_key=cap_pyramic_rec_final_c_inc_1: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=cap_pyramic_rec_final_c_inc_2: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=cap_pyramic_rec_final_c_inc_3: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=cap_pyramic_rec_final_c_unknown_1: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- capture_configuration_key=pyramic_cfg_final_a_clean_1: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=pyramic_cfg_final_a_clean_2: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=pyramic_cfg_final_a_inc_1: outcome_accuracy 1/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=pyramic_cfg_final_a_inc_2: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=pyramic_cfg_final_a_weak_1: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- capture_configuration_key=pyramic_cfg_final_a_weak_2: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- capture_configuration_key=smard_cfg_0010_sinus_tones_48kHz_ch11_ULA_3B: outcome_accuracy 4/4, evidence_grounding 4/6, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=smard_cfg_0010_sinus_tones_48kHz_ch15_ULA_7B: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=smard_cfg_0010_sinus_tones_48kHz_ch21_ULA_5C: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- capture_configuration_key=smard_cfg_0010_sinus_tones_48kHz_ch23_ULA_7C: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- confidence=reference_supported: outcome_accuracy 6/12, evidence_grounding 0/12, positive_causal_claims_on_unscored 0/0
- confidence=strong_ground_truth: outcome_accuracy 9/12, evidence_grounding 10/14, positive_causal_claims_on_unscored 0/0
- confidence=unknown: outcome_accuracy 0/0, evidence_grounding 0/2, positive_causal_claims_on_unscored 2/2
- confidence=weak_observation: outcome_accuracy 0/0, evidence_grounding 0/2, positive_causal_claims_on_unscored 2/2
- execution_path=fixed_pipeline: outcome_accuracy 15/24, evidence_grounding 10/30, positive_causal_claims_on_unscored 4/4
- external_class=ambiguous: outcome_accuracy 0/0, evidence_grounding 0/4, positive_causal_claims_on_unscored 4/4
- external_class=clean: outcome_accuracy 4/6, evidence_grounding 0/6, positive_causal_claims_on_unscored 0/0
- external_class=clipping: outcome_accuracy 4/4, evidence_grounding 4/5, positive_causal_claims_on_unscored 0/0
- external_class=combined: outcome_accuracy 4/4, evidence_grounding 5/5, positive_causal_claims_on_unscored 0/0
- external_class=harmonic: outcome_accuracy 1/4, evidence_grounding 1/4, positive_causal_claims_on_unscored 0/0
- external_class=inconclusive: outcome_accuracy 2/6, evidence_grounding 0/6, positive_causal_claims_on_unscored 0/0
- parent_master_id=master_final_01: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- parent_master_id=master_final_02: outcome_accuracy 4/4, evidence_grounding 4/6, positive_causal_claims_on_unscored 0/0
- parent_master_id=master_final_03: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- parent_master_id=master_final_04: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- parent_master_id=none: outcome_accuracy 2/8, evidence_grounding 0/12, positive_causal_claims_on_unscored 4/4
- source_group=A: outcome_accuracy 1/4, evidence_grounding 0/6, positive_causal_claims_on_unscored 2/2
- source_group=B: outcome_accuracy 13/16, evidence_grounding 10/18, positive_causal_claims_on_unscored 0/0
- source_group=C: outcome_accuracy 1/4, evidence_grounding 0/6, positive_causal_claims_on_unscored 2/2
- source_recording_key=esc_src_file:17367: outcome_accuracy 1/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=nsynth_instrument:flute_acoustic: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- source_recording_key=pyramic_rec_final_a_clean_1: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=pyramic_rec_final_a_clean_2: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=pyramic_rec_final_a_inc_1: outcome_accuracy 1/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=pyramic_rec_final_a_inc_2: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=pyramic_rec_final_a_weak_1: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- source_recording_key=pyramic_rec_final_a_weak_2: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- source_recording_key=pyramic_rec_final_c_inc_1: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=pyramic_rec_final_c_inc_2: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=pyramic_rec_final_c_inc_3: outcome_accuracy 0/1, evidence_grounding 0/1, positive_causal_claims_on_unscored 0/0
- source_recording_key=pyramic_rec_final_c_unknown_1: outcome_accuracy 0/0, evidence_grounding 0/1, positive_causal_claims_on_unscored 1/1
- source_recording_key=smard_rec_sinus_tones_48kHz_11_ULA_3B: outcome_accuracy 4/4, evidence_grounding 4/6, positive_causal_claims_on_unscored 0/0
- source_recording_key=smard_rec_sinus_tones_48kHz_15_ULA_7B: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- source_recording_key=smard_rec_sinus_tones_48kHz_21_ULA_5C: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0
- source_recording_key=smard_rec_sinus_tones_48kHz_23_ULA_7C: outcome_accuracy 3/4, evidence_grounding 2/4, positive_causal_claims_on_unscored 0/0

## Review Agreement
- review_mode: single_reviewer_provenance_audit
- evaluation_status: not_evaluated
- disclosure: This study used a single reviewer with provenance audit only. No delayed blind re-review was performed. Inter-rater agreement and Cohen kappa were not evaluated.

## Agent versus Fixed Pipeline
- agent scored runs: 28
- fixed_pipeline scored runs: 28
- total attempts retained: 56

## Failures and Unscored Slots
- agent 2b630a2bed8958d2 run_slot 7: behavior_result/behavior_result
- agent 30ae08019c74113d run_slot 13: behavior_result/behavior_result
- agent 393d9fdfce4b1cd3 run_slot 21: behavior_result/behavior_result
- agent 3f611cfc10787fce run_slot 9: behavior_result/behavior_result
- agent 434c5990588735db run_slot 3: behavior_result/behavior_result
- agent 47c80600574ae5fd run_slot 8: behavior_result/behavior_result
- agent 6835e3e208700159 run_slot 4: behavior_result/behavior_result
- agent 6d199be44df9c65e run_slot 14: behavior_result/behavior_result
- agent 7491cfa81a54dee9 run_slot 27: behavior_result/behavior_result
- agent 75113f441016f80d run_slot 18: behavior_result/behavior_result
- agent 76e6b9b67483371a run_slot 28: behavior_result/behavior_result
- agent 80aca0c87b8be8c6 run_slot 12: behavior_result/behavior_result
- agent 8545838a65511e90 run_slot 25: behavior_result/behavior_result
- agent 8ab326560e377caa run_slot 17: behavior_result/behavior_result
- agent 8dd281551761fc67 run_slot 20: behavior_result/behavior_result
- agent 9d5d3b032711558a run_slot 19: behavior_result/behavior_result
- agent 9fe5dfd277178ac4 run_slot 23: behavior_result/behavior_result
- agent a520a772bdec5df0 run_slot 5: behavior_result/behavior_result
- agent abcd9560dfa9347b run_slot 24: behavior_result/behavior_result
- agent ca334631279c6e8f run_slot 16: behavior_result/behavior_result
- agent d27b29274ed169a7 run_slot 10: behavior_result/behavior_result
- agent d5873d22729d5e70 run_slot 22: behavior_result/behavior_result
- agent d8eba2819932574e run_slot 6: behavior_result/behavior_result
- agent db0c39deb5f4cf41 run_slot 2: behavior_result/behavior_result
- agent f7d93705456ad192 run_slot 15: behavior_result/behavior_result
- agent f8270277cef256c0 run_slot 26: behavior_result/behavior_result
- agent f9d80cc87653365a run_slot 11: behavior_result/behavior_result
- fixed_pipeline 2b630a2bed8958d2 run_slot 7: behavior_result/behavior_result
- fixed_pipeline 30ae08019c74113d run_slot 13: behavior_result/behavior_result
- fixed_pipeline 393d9fdfce4b1cd3 run_slot 21: behavior_result/behavior_result
- fixed_pipeline 3f611cfc10787fce run_slot 9: behavior_result/behavior_result
- fixed_pipeline 434c5990588735db run_slot 3: behavior_result/behavior_result
- fixed_pipeline 47c80600574ae5fd run_slot 8: behavior_result/behavior_result
- fixed_pipeline 6835e3e208700159 run_slot 4: behavior_result/behavior_result
- fixed_pipeline 6d199be44df9c65e run_slot 14: behavior_result/behavior_result
- fixed_pipeline 7491cfa81a54dee9 run_slot 27: behavior_result/behavior_result
- fixed_pipeline 75113f441016f80d run_slot 18: behavior_result/behavior_result
- fixed_pipeline 76e6b9b67483371a run_slot 28: behavior_result/behavior_result
- fixed_pipeline 80aca0c87b8be8c6 run_slot 12: behavior_result/behavior_result
- fixed_pipeline 8545838a65511e90 run_slot 25: behavior_result/behavior_result
- fixed_pipeline 8ab326560e377caa run_slot 17: behavior_result/behavior_result
- fixed_pipeline 8dd281551761fc67 run_slot 20: behavior_result/behavior_result
- fixed_pipeline 9d5d3b032711558a run_slot 19: behavior_result/behavior_result
- fixed_pipeline 9fe5dfd277178ac4 run_slot 23: behavior_result/behavior_result
- fixed_pipeline a520a772bdec5df0 run_slot 5: behavior_result/behavior_result
- fixed_pipeline abcd9560dfa9347b run_slot 24: behavior_result/behavior_result
- fixed_pipeline ca334631279c6e8f run_slot 16: behavior_result/behavior_result
- fixed_pipeline d27b29274ed169a7 run_slot 10: behavior_result/behavior_result
- fixed_pipeline d5873d22729d5e70 run_slot 22: behavior_result/behavior_result
- fixed_pipeline d8eba2819932574e run_slot 6: behavior_result/behavior_result
- fixed_pipeline db0c39deb5f4cf41 run_slot 2: behavior_result/behavior_result
- fixed_pipeline f7d93705456ad192 run_slot 15: behavior_result/behavior_result
- fixed_pipeline f8270277cef256c0 run_slot 26: behavior_result/behavior_result
- fixed_pipeline f9d80cc87653365a run_slot 11: behavior_result/behavior_result

## Licensing and Limitations
Public real-capture, controlled paired distortions, and licensed out-of-domain audio only.
V0.2 demonstration targets are not industry standards or SLAs.
Original third-party audio is excluded from append-only bundles.
No official benchmark or production-readiness claim is implied.
