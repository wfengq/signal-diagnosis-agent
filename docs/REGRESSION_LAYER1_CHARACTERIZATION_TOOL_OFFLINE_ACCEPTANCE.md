# Layer-1 full-scale characterization tool — offline acceptance (T-CX371–T-CX380)

**Branch:** `cursor/s1-layer1-characterization-tool`
**Baseline:** `de08fe56eae7589a43f081c629a2b6756c7397b3`
**Content tip (code after review fixes and A.16):** `c67017c432a8ce56d12bdee890bc0275deb9a837`
**Branch tip:** the commit that adds this revision (see the PR description); it changes only
this document and the plan text for A.16.

Plan: `docs/superpowers/plans/2026-10-05-s1-regression-layer1-characterization.md` (revision 3
plus A.16), Tasks 0–9.

## Scope statement

- No formal measurement was run: no `round_1` manifest, identity, calibration,
  freeze or validation artifact was written, and no
  `docs/evaluations/v0_3/full_scale_characterization/round_1/` directory exists.
- No floor, critical-zone or approved-domain value was produced or selected.
- The product registry is still empty (`PRODUCT_APPROVED_FULL_SCALE_FLOORS == ()`,
  asserted by `test_t_cx371_product_approved_full_scale_floors_stays_empty`).
- No RealLLM call and no seal.
- This document is not a manifest approval (R0) and is not evidence for any floor.

## Verification commands

Run in the worktree on the content tip `c67017c432a8ce56d12bdee890bc0275deb9a837` with the A.16 plan text
edit present (documentation only).

### `.venv/bin/python -m pytest -q -rxXs -p no:cacheprovider`

```text
1 failed, 2195 passed, 1 warning in 460.81s (0:07:40)
```

The single failure is
`tests/evaluation/test_dataset.py::test_t133_official_case_allocation_and_packaging`:
it runs `python -m pip wheel ...` and the local uv-created venv has no pip
(`No module named pip`). This is an environment limitation unrelated to this change;
CI is authoritative for it. No test was skipped, xfailed or xpassed.

### `.venv/bin/python -m pytest -q tests/test_architecture_boundaries.py`

```text
65 passed in 15.56s
```

### `.venv/bin/python -m ruff check --no-cache src tests scripts`

```text
All checks passed!
```

### `.venv/bin/python -m mypy --no-incremental src`

```text
Success: no issues found in 167 source files
```

### `.venv/bin/python scripts/verify_phase5_wheel.py`

Exit status 0; final lines:

```text
sdist signal_diagnosis_agent-0.2.0.tar.gz sha256=5982c196ca9f8f8b0711d4930e8e1fe6f88f670989082179d84cf0a0cd9bb413
wheel signal_diagnosis_agent-0.2.0-py3-none-any.whl sha256=5644b91df028cb83c123f81d04877c3b65197fe5b7ac05f857a45342af610f99
```

### `git diff --check de08fe56eae7589a43f081c629a2b6756c7397b3..HEAD`

Run after the content-tip commit and again after this revision's commit: no output,
exit status 0.

## Test IDs and test functions

Collected from the test files (`grep '^def test_'`); functions named `test_t_cxNNN_*`
are listed under that ID, the others under the ID of their file. 149 functions.

### T-CX371

- `test_layering.py::test_t_cx371_package_does_not_import_rules_agent_app_or_knowledge`
- `test_layering.py::test_t_cx371_product_layers_do_not_mention_characterization_package`
- `test_layering.py::test_t_cx371_product_approved_full_scale_floors_stays_empty`

### T-CX372

- `test_pcm_encoding.py::test_t_cx372_round_trip_codes_16_24_8`
- `test_pcm_encoding.py::test_t_cx372_round_trip_32_matches_float32_decode`
- `test_pcm_encoding.py::test_t_cx372_pm_one_no_overflow_all_bit_depths`
- `test_pcm_encoding.py::test_t_cx372_one_step_perturbations_bounded_and_directional`
- `test_pcm_encoding.py::test_t_cx372_32bit_decode_offset_exactly_one_step_for_large_samples`
- `test_pcm_encoding.py::test_t_cx372_random_one_step_seed_deterministic_and_varies`
- `test_pcm_encoding.py::test_t_cx372_32bit_trunc_differs_from_round_not_p0`
- `test_pcm_encoding.py::test_t_cx372_does_not_import_app_pcm_wav`
- `test_synthesis.py::test_t_cx372_sine_amplitude_and_phase`
- `test_synthesis.py::test_t_cx372_clipped_pre_clip_peak_and_output_bound`
- `test_synthesis.py::test_t_cx372_clipped_m5_harmonics_before_scale_and_clip`
- `test_synthesis.py::test_t_cx372_clipped_level_one_stays_within_full_scale`
- `test_synthesis.py::test_t_cx372_harmonic_sine_m6_no_extra_scaling`
- `test_t_cx372_followups.py::test_t_cx372_32bit_offset_clips_on_the_2_pow_24_grid`

### T-CX373

- `test_t_cx373_manifest.py::test_round_1_manifest_hash_is_stable`
- `test_t_cx373_manifest.py::test_round_1_build_within_wall_budget`
- `test_t_cx373_manifest.py::test_constants_change_changes_manifest_hash`
- `test_t_cx373_manifest.py::test_round_1_planned_counts_only`
- `test_t_cx373_manifest.py::test_mini_sensitivity_pairs_single_perturbation`
- `test_t_cx373_manifest.py::test_mini_tolerance_codes_only_listed`
- `test_t_cx373_manifest.py::test_seed_sets_do_not_overlap`
- `test_t_cx373_manifest.py::test_calibration_has_no_combo_or_blind`
- `test_t_cx373_p4_p9_orientation.py::test_t_cx373_p4_p9_old_side_is_coarser_bit_depth`
- `test_t_cx373_p4_p9_orientation.py::test_t_cx373_p4_both_sides_round`
- `test_t_cx373_p4_p9_orientation.py::test_t_cx373_p9c_old_side_truncates_coarse_new_side_rounds_fine`
- `test_t_cx373_p4_p9_orientation.py::test_t_cx373_p9ab_fine_file_shifted_by_exactly_one_coarse_step`
- `test_t_cx373_p4_p9_orientation.py::test_t_cx373_p9a_review_counterexample_flips_on_full_tool_path`

### T-CX374

- `test_t_cx372_followups.py::test_t_cx374_m7_marks_one_to_three_samples_per_peak_for_m2_m3_m5`
- `test_t_cx374_a15_leakage.py::test_t_cx374_a15_mini_excludes_known_p5_hit`
- `test_t_cx374_a15_leakage.py::test_t_cx374_a15_scan_reaches_p3_sides`
- `test_t_cx374_a15_leakage.py::test_t_cx374_a15_scan_reaches_change_pairs`
- `test_t_cx374_a15_leakage.py::test_t_cx374_a15_base_material_hit_aborts`
- `test_t_cx374_a15_leakage.py::test_t_cx374_param_leakage_is_checked_per_channel_including_m9`
- `test_t_cx374_a15_leakage.py::test_t_cx374_dry_run_prints_param_leakage_hits`
- `test_t_cx374_a15_leakage.py::test_t_cx374_round_1_exclusion_count_is_pinned`
- `test_t_cx374_manifest.py::test_source_group_side_consistency`
- `test_t_cx374_manifest.py::test_calibration_only_calibration_range_lengths`
- `test_t_cx374_manifest.py::test_group_key_ignores_filename_seed_perturbation`
- `test_t_cx374_manifest.py::test_validation_has_each_family_combo_and_blind`
- `test_t_cx374_manifest.py::test_no_calibration_effective_params_match_validation_materials`
- `test_t_cx374_manifest.py::test_p3_result_phases_disjoint_from_validation_held_out`
- `test_t_cx374_manifest.py::test_onset_calibration_depths_exclude_0_9999`
- `test_t_cx374_manifest.py::test_scale_limit_raises_when_exceeded`
- `test_t_cx374_manifest.py::test_round_1_within_scale_limit_or_blocked`
- `test_t_cx374_manifest.py::test_near_duplicate_exclusions_listed_not_silent`
- `test_t_cx374_manifest.py::test_leakage_abort_on_forbidden_onset_depth`
- `test_t_cx374_manifest.py::test_a15_prefilter_matches_full_encode_on_m3_p5_hit`
- `test_t_cx374_manifest.py::test_prefilter_skips_distant_pairs`
- `test_t_cx374_plan_b_grid.py::test_t_cx374_validation_groups_by_rule_match_hand_counts`
- `test_t_cx374_plan_b_grid.py::test_t_cx374_rule_1_includes_held_out_f0_with_fixed_subsets`
- `test_t_cx374_plan_b_grid.py::test_t_cx374_change_pairs_cover_three_bit_depths_at_phase_zero`
- `test_t_cx374_plan_b_grid.py::test_t_cx374_formula_counts_match_enumerated_pairs`
- `test_t_cx374_plan_b_grid.py::test_t_cx374_m9_calibration_layouts_swap_left_and_right`
- `test_t_cx374_plan_b_grid.py::test_t_cx374_blind_pairs_change_material_and_clip_new_side`

### T-CX375

- `test_t_cx372_followups.py::test_t_cx375_harmonic_input_carries_channel_and_range_only`
- `test_t_cx375_executor.py::test_facts_match_direct_measure_full_scale_facts`
- `test_t_cx375_executor.py::test_identical_input_produces_identical_row_digests`
- `test_t_cx375_executor.py::test_cache_returns_same_row_for_same_key`
- `test_t_cx375_executor.py::test_m9_left_channel_matches_mono_same_params`
- `test_t_cx375_executor.py::test_terminal_generation_failed`
- `test_t_cx375_executor.py::test_terminal_invalid_wav_load`
- `test_t_cx375_executor.py::test_terminal_invalid_clipping_tool`
- `test_t_cx375_executor.py::test_terminal_invalid_measure_output`
- `test_t_cx375_executor.py::test_assemble_pair_stays_in_denominator_with_terminal_states`

### T-CX376

- `test_t_cx376_checks.py::test_t_cx376_near_material_separates_the_three_thresholds`
- `test_t_cx376_checks.py::test_t_cx376_all_checks_pass_on_legal_material`
- `test_t_cx376_checks.py::test_t_cx376_p0_nonzero_count_diff_aborts`
- `test_t_cx376_checks.py::test_t_cx376_p0_wav_sha256_mismatch_aborts`
- `test_t_cx376_checks.py::test_t_cx376_sandwich_upper_bound_violation_aborts`
- `test_t_cx376_checks.py::test_t_cx376_sandwich_lower_bound_violation_aborts`
- `test_t_cx376_checks.py::test_t_cx376_p9_sandwich_uses_two_steps_and_still_aborts_outside`
- `test_t_cx376_checks.py::test_t_cx376_p7a_equality_violation_aborts`
- `test_t_cx376_checks.py::test_t_cx376_p7b_equality_violation_aborts`
- `test_t_cx376_checks.py::test_t_cx376_p7_flip_outside_fixed_zone_aborts`
- `test_t_cx376_checks.py::test_t_cx376_facts_verification_failure_aborts_with_pair_id`
- `test_t_cx376_checks.py::test_t_cx376_p9_flip_outside_k1_zone_is_counted_not_aborted`
- `test_t_cx376_checks.py::test_t_cx376_p9_deviation_beyond_two_steps_aborts`

### T-CX377

- `test_t_cx377_fitting.py::test_t_cx377_candidate_tables_are_fixed`
- `test_t_cx377_fitting.py::test_t_cx377_stage1_emits_every_domain_and_k_row`
- `test_t_cx377_fitting.py::test_t_cx377_k2_k1_minimal_parameters_match_hand_calculation`
- `test_t_cx377_fitting.py::test_t_cx377_points_inside_fixed_minimum_are_removed`
- `test_t_cx377_fitting.py::test_t_cx377_k4_uses_two_sample_level_and_is_non_negative`
- `test_t_cx377_fitting.py::test_t_cx377_k3_rows_match_hand_calculation_and_use_or`
- `test_t_cx377_fitting.py::test_t_cx377_k0_label_only_counts_tolerance_pairs_of_main_conditions`
- `test_t_cx377_fitting.py::test_t_cx377_k1_k2_flip_counts_reported_separately`
- `test_t_cx377_fitting.py::test_t_cx377_shares_and_onset_tiers`
- `test_t_cx377_fitting.py::test_t_cx377_fitting_rejects_validation_records`
- `test_t_cx377_fitting.py::test_t_cx377_f1_f2_are_plain_maxima_without_margin`
- `test_t_cx377_fitting.py::test_t_cx377_f3_only_single_cut_on_n_or_periods`
- `test_t_cx377_fitting.py::test_t_cx377_stage2_accepts_only_stage1_selection`
- `test_t_cx377_fitting.py::test_t_cx377_row_limits`
- `test_t_cx377_fitting.py::test_t_cx377_reports_list_all_rows_without_ranking_language`
- `test_t_cx377_fitting.py::test_t_cx377_vectorised_zone_matches_scalar_predicate_for_every_row`
- `test_t_cx377_zone_parity.py::test_t_cx377_quantization_step_matches_product`
- `test_t_cx377_zone_parity.py::test_t_cx377_zone_k1_k2_k3_match_product_in_critical_zone`
- `test_t_cx377_zone_parity.py::test_t_cx377_f1_f2_match_product_judgment_status`
- `test_t_cx377_zone_parity.py::test_t_cx377_hard_condition_uses_absolute_difference`
- `test_t_cx377_zone_parity.py::test_t_cx377_domain_expressions_are_verbatim_with_product`

### T-CX378

- `test_t_cx378_freeze_store.py::test_t_cx378_store_refuses_to_overwrite_and_sums_match`
- `test_t_cx378_freeze_store.py::test_t_cx378_store_detects_tampering_and_unlisted_files`
- `test_t_cx378_freeze_store.py::test_t_cx378_store_rejects_paths_outside_layout`
- `test_t_cx378_freeze_store.py::test_t_cx378_gzip_shards_are_deterministic`
- `test_t_cx378_freeze_store.py::test_t_cx378_shard_size_limit`
- `test_t_cx378_freeze_store.py::test_t_cx378_validation_artifacts_need_validation_access`
- `test_t_cx378_freeze_store.py::test_t_cx378_identity_has_comparison_and_record_only_parts`
- `test_t_cx378_freeze_store.py::test_t_cx378_identity_mismatch_blocks_calibration_and_validation`
- `test_t_cx378_freeze_store.py::test_t_cx378_git_commit_unavailable_is_recorded_as_null`
- `test_t_cx378_freeze_store.py::test_t_cx378_freeze_two_parts_round_trip`
- `test_t_cx378_freeze_store.py::test_t_cx378_freeze_digest_is_self_checking`
- `test_t_cx378_freeze_store.py::test_t_cx378_stage1_rejects_upstream_hash_mismatch`
- `test_t_cx378_freeze_store.py::test_t_cx378_stage1_can_only_select_not_edit`
- `test_t_cx378_freeze_store.py::test_t_cx378_stage2_can_only_select_not_edit`
- `test_t_cx378_freeze_store.py::test_t_cx378_stage2_accepts_only_the_written_stage1`
- `test_t_cx378_freeze_store.py::test_t_cx378_no_freeze_record_locks_validation_entry_points`
- `test_t_cx378_freeze_store.py::test_t_cx378_stage1_only_still_locks_validation`
- `test_t_cx378_freeze_store.py::test_t_cx378_full_freeze_unlocks_validation_entry_points`
- `test_t_cx378_freeze_store.py::test_t_cx378_tampered_freeze_record_locks_validation`
- `test_t_cx378_freeze_store.py::test_t_cx378_consistently_rewritten_freeze_record_is_rejected`
- `test_t_cx378_freeze_store.py::test_t_cx378_consistently_rewritten_floor_is_rejected`
- `test_t_cx378_gate_identity.py::test_t_cx378_frozen_report_json_is_built_in_the_comparison_set`
- `test_t_cx378_gate_identity.py::test_t_cx378_validation_access_issuer_is_private`
- `test_t_cx378_gate_identity.py::test_t_cx378_pair_enumeration_defaults_to_calibration_and_gates_validation`
- `test_t_cx378_gate_identity.py::test_t_cx378_manifest_pairs_hold_calibration_only`
- `test_t_cx378_gate_identity.py::test_t_cx378_measure_row_gates_validation_specs`
- `test_t_cx378_gate_identity.py::test_t_cx378_full_freeze_unlocks_measure_row`
- `test_t_cx378_gate_identity.py::test_t_cx378_manifest_expansion_is_explicit_not_by_round_name`
- `test_t_cx378_gate_identity.py::test_t_cx378_round_id_must_match_manifest`
- `test_t_cx378_gate_identity.py::test_t_cx378_package_digest_change_blocks_calibrate_and_validate`
- `test_t_cx378_sharding.py::test_t_cx378_range_key_round_trips_every_round_1_length`
- `test_t_cx378_sharding.py::test_t_cx378_store_accepts_only_the_a16_layout`
- `test_t_cx378_sharding.py::test_t_cx378_directory_digest_covers_nested_shards`
- `test_t_cx378_sharding.py::test_t_cx378_round_1_shards_fit_the_size_limit`

### T-CX379

- `test_t_cx379_validation.py::test_t_cx379_frozen_fixture_values`
- `test_t_cx379_validation.py::test_t_cx379_clean_population_meets_hard_conditions`
- `test_t_cx379_validation.py::test_t_cx379_hard_condition_1_violation_is_listed`
- `test_t_cx379_validation.py::test_t_cx379_hard_condition_2_uses_absolute_difference_and_f3_segment`
- `test_t_cx379_validation.py::test_t_cx379_flip_in_zone_excluded_and_out_of_domain_listed`
- `test_t_cx379_validation.py::test_t_cx379_minimum_detectable_change_by_tier`
- `test_t_cx379_validation.py::test_t_cx379_disclosures_are_complete_and_kept_out_of_hard_conditions`
- `test_t_cx379_validation.py::test_t_cx379_count_requires_validation_access`
- `test_t_cx379_validation.py::test_t_cx379_finalize_writes_report_once`
- `test_t_cx379_validation.py::test_t_cx379_sanity_abort_writes_abort_record_and_no_report`

### T-CX380

- `test_t_cx380_end_to_end.py::test_t_cx380_six_steps_end_to_end_reproducible`
- `test_t_cx380_end_to_end.py::test_t_cx380_freeze_accepts_only_row_ids_from_reports`
- `test_t_cx380_end_to_end.py::test_t_cx380_dry_run_writes_nothing_and_prints_fit_row_counts`
- `test_t_cx380_end_to_end.py::test_t_cx380_reruns_are_refused_before_any_measurement`

## `manifest --round round_1 --dry-run`

Command: `.venv/bin/python -m signal_diag.evaluation.full_scale_characterization manifest --round round_1 --dry-run`
(exit status 0). It wrote no file. The printed counts and estimates are a dry run only
and do not constitute R0 manifest approval. Shard sizes are estimates
(planned pairs x 2 rows x 170 B), not measured compressed sizes; the largest shard is
`validation/M3/<range>` at 14,152,160 B, under the 50,000,000 B limit.

```text
round_id=round_1
manifest_sha256=ca8cc28da6a37461a4959bf2ebe580f1f57ebdf07d570b79038e6f2a027e3c5c
planned_pair_counts:
  calibration: 382368
  validation: 553830
by_side/family/perturbation:
  calibration/M1/ONSET: 576
  calibration/M1/P0: 432
  calibration/M1/P1: 432
  calibration/M1/P3: 432
  calibration/M1/P4: 432
  calibration/M1/P5: 864
  calibration/M1/P5t: 288
  calibration/M1/P6: 2160
  calibration/M1/P7a: 432
  calibration/M1/P7b: 432
  calibration/M1/P7c: 432
  calibration/M1/P7d: 2160
  calibration/M1/P8: 288
  calibration/M1/P9a: 432
  calibration/M1/P9b: 432
  calibration/M1/P9c: 432
  calibration/M2/P0: 5616
  calibration/M2/P1: 5616
  calibration/M2/P3: 1872
  calibration/M2/P4: 5616
  calibration/M2/P5: 11088
  calibration/M2/P5t: 3744
  calibration/M2/P6: 28080
  calibration/M2/P7a: 5616
  calibration/M2/P7b: 5616
  calibration/M2/P7c: 5616
  calibration/M2/P7d: 28080
  calibration/M2/P8: 3744
  calibration/M2/P9a: 5616
  calibration/M2/P9b: 5616
  calibration/M2/P9c: 5616
  calibration/M3/AGGR: 8640
  calibration/M3/P0: 5184
  calibration/M3/P1: 5184
  calibration/M3/P3: 1728
  calibration/M3/P4: 5184
  calibration/M3/P5: 10176
  calibration/M3/P5t: 3456
  calibration/M3/P6: 25920
  calibration/M3/P7a: 5184
  calibration/M3/P7b: 5184
  calibration/M3/P7c: 5184
  calibration/M3/P7d: 25920
  calibration/M3/P8: 3456
  calibration/M3/P9a: 5184
  calibration/M3/P9b: 5184
  calibration/M3/P9c: 5184
  calibration/M4/P0: 1152
  calibration/M4/P1: 1152
  calibration/M4/P3: 1152
  calibration/M4/P4: 1152
  calibration/M4/P5: 2304
  calibration/M4/P5t: 768
  calibration/M4/P6: 5760
  calibration/M4/P7a: 1152
  calibration/M4/P7b: 1152
  calibration/M4/P7c: 1152
  calibration/M4/P7d: 5760
  calibration/M4/P8: 768
  calibration/M4/P9a: 1152
  calibration/M4/P9b: 1152
  calibration/M4/P9c: 1152
  calibration/M5/P0: 3456
  calibration/M5/P1: 3456
  calibration/M5/P3: 1152
  calibration/M5/P4: 3456
  calibration/M5/P5: 6912
  calibration/M5/P5t: 2304
  calibration/M5/P6: 17280
  calibration/M5/P7a: 3456
  calibration/M5/P7b: 3456
  calibration/M5/P7c: 3456
  calibration/M5/P7d: 17280
  calibration/M5/P8: 2304
  calibration/M5/P9a: 3456
  calibration/M5/P9b: 3456
  calibration/M5/P9c: 3456
  calibration/M6/P0: 288
  calibration/M6/P1: 288
  calibration/M6/P3: 288
  calibration/M6/P4: 288
  calibration/M6/P5: 576
  calibration/M6/P5t: 192
  calibration/M6/P6: 1440
  calibration/M6/P7a: 288
  calibration/M6/P7b: 288
  calibration/M6/P7c: 288
  calibration/M6/P7d: 1440
  calibration/M6/P8: 192
  calibration/M6/P9a: 288
  calibration/M6/P9b: 288
  calibration/M6/P9c: 288
  calibration/M9/P0: 288
  calibration/M9/P1: 288
  calibration/M9/P3: 288
  calibration/M9/P4: 288
  calibration/M9/P5: 528
  calibration/M9/P5t: 192
  calibration/M9/P6: 1440
  calibration/M9/P7a: 288
  calibration/M9/P7b: 288
  calibration/M9/P7c: 288
  calibration/M9/P7d: 1440
  calibration/M9/P8: 192
  calibration/M9/P9a: 288
  calibration/M9/P9b: 288
  calibration/M9/P9c: 288
  validation/M1/COMBO_P1_P6: 310
  validation/M1/COMBO_P4_P5: 310
  validation/M1/COMBO_P6_DUAL: 310
  validation/M1/ONSET: 750
  validation/M1/P0: 930
  validation/M1/P1: 620
  validation/M1/P3: 620
  validation/M1/P4: 930
  validation/M1/P5: 1240
  validation/M1/P5t: 620
  validation/M1/P6: 4650
  validation/M1/P7a: 930
  validation/M1/P7b: 930
  validation/M1/P7c: 930
  validation/M1/P7d: 4650
  validation/M1/P8: 620
  validation/M1/P9a: 930
  validation/M1/P9b: 930
  validation/M1/P9c: 930
  validation/M2/COMBO_P1_P6: 1510
  validation/M2/COMBO_P4_P5: 1510
  validation/M2/COMBO_P6_DUAL: 1510
  validation/M2/P0: 4530
  validation/M2/P1: 3020
  validation/M2/P3: 1400
  validation/M2/P4: 4530
  validation/M2/P5: 6040
  validation/M2/P5t: 3020
  validation/M2/P6: 22650
  validation/M2/P7a: 4530
  validation/M2/P7b: 4530
  validation/M2/P7c: 4530
  validation/M2/P7d: 22650
  validation/M2/P8: 3020
  validation/M2/P9a: 4530
  validation/M2/P9b: 4530
  validation/M2/P9c: 4530
  validation/M3/AGGR: 24600
  validation/M3/BLIND_SINGLE: 10
  validation/M3/COMBO_P1_P6: 2690
  validation/M3/COMBO_P4_P5: 2690
  validation/M3/COMBO_P6_DUAL: 2690
  validation/M3/P0: 8070
  validation/M3/P1: 5380
  validation/M3/P3: 3280
  validation/M3/P4: 8070
  validation/M3/P5: 10760
  validation/M3/P5t: 5380
  validation/M3/P6: 40350
  validation/M3/P7a: 8070
  validation/M3/P7b: 8070
  validation/M3/P7c: 8070
  validation/M3/P7d: 40350
  validation/M3/P8: 5380
  validation/M3/P9a: 8070
  validation/M3/P9b: 8070
  validation/M3/P9c: 8070
  validation/M4/BLIND_SUB: 60
  validation/M4/COMBO_P1_P6: 1610
  validation/M4/COMBO_P4_P5: 1610
  validation/M4/COMBO_P6_DUAL: 1610
  validation/M4/P0: 4830
  validation/M4/P1: 3220
  validation/M4/P3: 3220
  validation/M4/P4: 4830
  validation/M4/P5: 6440
  validation/M4/P5t: 3220
  validation/M4/P6: 24150
  validation/M4/P7a: 4830
  validation/M4/P7b: 4830
  validation/M4/P7c: 4830
  validation/M4/P7d: 24150
  validation/M4/P8: 3220
  validation/M4/P9a: 4830
  validation/M4/P9b: 4830
  validation/M4/P9c: 4830
  validation/M5/COMBO_P1_P6: 1400
  validation/M5/COMBO_P4_P5: 1400
  validation/M5/COMBO_P6_DUAL: 1400
  validation/M5/P0: 4200
  validation/M5/P1: 2800
  validation/M5/P3: 1560
  validation/M5/P4: 4200
  validation/M5/P5: 5600
  validation/M5/P5t: 2800
  validation/M5/P6: 21000
  validation/M5/P7a: 4200
  validation/M5/P7b: 4200
  validation/M5/P7c: 4200
  validation/M5/P7d: 21000
  validation/M5/P8: 2800
  validation/M5/P9a: 4200
  validation/M5/P9b: 4200
  validation/M5/P9c: 4200
  validation/M6/COMBO_P1_P6: 180
  validation/M6/COMBO_P4_P5: 180
  validation/M6/COMBO_P6_DUAL: 180
  validation/M6/P0: 540
  validation/M6/P1: 360
  validation/M6/P3: 360
  validation/M6/P4: 540
  validation/M6/P5: 720
  validation/M6/P5t: 360
  validation/M6/P6: 2700
  validation/M6/P7a: 540
  validation/M6/P7b: 540
  validation/M6/P7c: 540
  validation/M6/P7d: 2700
  validation/M6/P8: 360
  validation/M6/P9a: 540
  validation/M6/P9b: 540
  validation/M6/P9c: 540
  validation/M9/COMBO_P1_P6: 30
  validation/M9/COMBO_P4_P5: 30
  validation/M9/COMBO_P6_DUAL: 30
  validation/M9/P0: 90
  validation/M9/P1: 60
  validation/M9/P3: 60
  validation/M9/P4: 90
  validation/M9/P5: 120
  validation/M9/P5t: 60
  validation/M9/P6: 450
  validation/M9/P7a: 90
  validation/M9/P7b: 90
  validation/M9/P7c: 90
  validation/M9/P7d: 450
  validation/M9/P8: 60
  validation/M9/P9a: 90
  validation/M9/P9b: 90
  validation/M9/P9c: 90
estimated_measurement_rows=1872396
estimated_shard_gzip_bytes calibration/M1/L100000us: 905760
estimated_shard_gzip_bytes calibration/M1/L10000us: 905760
estimated_shard_gzip_bytes calibration/M1/L2000000us: 905760
estimated_shard_gzip_bytes calibration/M1/L5000us: 905760
estimated_shard_gzip_bytes calibration/M2/L100000us: 10807920
estimated_shard_gzip_bytes calibration/M2/L10000us: 10807920
estimated_shard_gzip_bytes calibration/M2/L2000000us: 10807920
estimated_shard_gzip_bytes calibration/M2/L5000us: 10807920
estimated_shard_gzip_bytes calibration/M3/L100000us: 10705920
estimated_shard_gzip_bytes calibration/M3/L10000us: 10705920
estimated_shard_gzip_bytes calibration/M3/L2000000us: 10705920
estimated_shard_gzip_bytes calibration/M3/L5000us: 10705920
estimated_shard_gzip_bytes calibration/M4/L100000us: 2284800
estimated_shard_gzip_bytes calibration/M4/L10000us: 2284800
estimated_shard_gzip_bytes calibration/M4/L2000000us: 2284800
estimated_shard_gzip_bytes calibration/M4/L5000us: 2284800
estimated_shard_gzip_bytes calibration/M5/L100000us: 6658560
estimated_shard_gzip_bytes calibration/M5/L10000us: 6658560
estimated_shard_gzip_bytes calibration/M5/L2000000us: 6658560
estimated_shard_gzip_bytes calibration/M5/L5000us: 6658560
estimated_shard_gzip_bytes calibration/M6/L100000us: 571200
estimated_shard_gzip_bytes calibration/M6/L10000us: 571200
estimated_shard_gzip_bytes calibration/M6/L2000000us: 571200
estimated_shard_gzip_bytes calibration/M6/L5000us: 571200
estimated_shard_gzip_bytes calibration/M9/L100000us: 567120
estimated_shard_gzip_bytes calibration/M9/L10000us: 567120
estimated_shard_gzip_bytes calibration/M9/L2000000us: 567120
estimated_shard_gzip_bytes calibration/M9/L5000us: 567120
estimated_shard_gzip_bytes validation/M1/L1000000us: 1505520
estimated_shard_gzip_bytes validation/M1/L2000000us: 1505520
estimated_shard_gzip_bytes validation/M1/L20000us: 1505520
estimated_shard_gzip_bytes validation/M1/L2000us: 1505520
estimated_shard_gzip_bytes validation/M1/L5000us: 1505520
estimated_shard_gzip_bytes validation/M2/L1000000us: 6974760
estimated_shard_gzip_bytes validation/M2/L2000000us: 6974760
estimated_shard_gzip_bytes validation/M2/L20000us: 6974760
estimated_shard_gzip_bytes validation/M2/L2000us: 6974760
estimated_shard_gzip_bytes validation/M2/L5000us: 6974760
estimated_shard_gzip_bytes validation/M3/L1000000us: 14152160
estimated_shard_gzip_bytes validation/M3/L2000000us: 14152160
estimated_shard_gzip_bytes validation/M3/L20000us: 14152160
estimated_shard_gzip_bytes validation/M3/L2000us: 14152160
estimated_shard_gzip_bytes validation/M3/L5000us: 14152160
estimated_shard_gzip_bytes validation/M4/L1000000us: 7558200
estimated_shard_gzip_bytes validation/M4/L2000000us: 7558200
estimated_shard_gzip_bytes validation/M4/L20000us: 7558200
estimated_shard_gzip_bytes validation/M4/L2000us: 7558200
estimated_shard_gzip_bytes validation/M4/L5000us: 7558200
estimated_shard_gzip_bytes validation/M5/L1000000us: 6484480
estimated_shard_gzip_bytes validation/M5/L2000000us: 6484480
estimated_shard_gzip_bytes validation/M5/L20000us: 6484480
estimated_shard_gzip_bytes validation/M5/L2000us: 6484480
estimated_shard_gzip_bytes validation/M5/L5000us: 6484480
estimated_shard_gzip_bytes validation/M6/L1000000us: 844560
estimated_shard_gzip_bytes validation/M6/L2000000us: 844560
estimated_shard_gzip_bytes validation/M6/L20000us: 844560
estimated_shard_gzip_bytes validation/M6/L2000us: 844560
estimated_shard_gzip_bytes validation/M6/L5000us: 844560
estimated_shard_gzip_bytes validation/M9/L1000000us: 140760
estimated_shard_gzip_bytes validation/M9/L2000000us: 140760
estimated_shard_gzip_bytes validation/M9/L20000us: 140760
estimated_shard_gzip_bytes validation/M9/L2000us: 140760
estimated_shard_gzip_bytes validation/M9/L5000us: 140760
shards_over_limit=0 (limit 50000000 B)
excluded_near_duplicates=384
param_leakage_hits=0
stage1_rows=756 (limit 1000)
stage2_rows_max=37 (limit 100)
```

## Deviations from the plan

From the Cursor PR description (Tasks 0–4):

1. Baseline text: the plan names `61cad20` as read-only baseline; the branch baseline
   is `de08fe56eae7589a43f081c629a2b6756c7397b3`. Only the Task 9
   `git diff --check` line of the plan was updated to the new baseline.
2. Manifest not expanded: the `round_1` manifest stores source groups, templates,
   formula counts, exclusions and a streamed `pairs_list_sha256`; it does not
   instantiate per-pair records (`pairs=()`). Run steps expand pairs on demand
   through `manifest.iter_side_pairs`.
3. Fitting row counts in `--dry-run` were deferred to Task 6; Task 9 adds them
   (`stage1_rows`, `stage2_rows_max`).

Later tasks:

4. P4/P9 orientation fix (`594e470`): the committed Task 3 enumeration had the finer
   depth as the old side and applied the P9 offset on the coarser file. Pairs are now
   coarse-old / fine-new per plan B.3 / C.1 (P9a/b offset one coarser step on the
   finer file; P9c coarser truncation vs finer rounding). The `round_1` dry-run
   `manifest_sha256` changed accordingly; planned counts did not.
5. ROUND_1 test wall budget is 120 s (`366406c`).
6. Validation gate placement: the gate covers run-time expansion
   (`iter_side_pairs`), row expansion (`row_specs_for_pair`, hence
   `measure_pair_checked`), sanity checks on validation pairs, validation artifacts in
   the store, and validation counting. `build_manifest` (R0) still reads validation
   descriptions and synthesizes validation waveforms for the A.15 near-duplicate scan,
   as the plan requires.
7. `measure_row` itself has no gate: `MeasurementRowSpec` carries no side;
   `row_specs_for_pair` is the guarded entry from pairs to specs.
8. Coverage is reported in two forms: domain share (in-domain tolerance pairs / all
   measured tolerance pairs) and judgeable share (both sides outside the zone /
   in-domain tolerance pairs), overall and by family.
9. Minimal zone parameters are minimal at the resolution of the predicate
   `thr -/+ z` (about one ulp of the threshold): computed as `max(0, gap)` and raised
   ulp by ulp only if floating-point rounding leaves a point uncovered.
10. Empty sets and F0: an F fit over no applicable pair is 0.0 with an applicable
    count of 0; F0 treats any positive increase as above the floor when counting
    aggravation pairs (the product model cannot express F0, plan A.2).
11. Primary conditions: M2, M11 and M3 always; M5 only with level at or above the
    threshold; M9 never.
12. Shard size limit 50 MB is 50,000,000 bytes (compressed).
13. `identity.py` imports `signal_diag.evaluation.contextual.calibration` lazily to
    record `contextual_product_tree_sha256()` (record-only item, plan D); this is
    outside the signal/dsp/tools set but not rules/agent/app/knowledge.
14. Identity: `manifest_sha256` in the freeze record is the sha256 of the
    `manifest.json` bytes; shard directories are hashed as a combined digest of sorted
    `path\0sha\n` lines. `floor_cut` is `{variable, cut, base}` for F3 only.
15. Minimum detectable change: the smallest tier from which every higher tier has
    judged pairs and none covered by the floor; `None` when the highest tier fails.
16. Flips unseen in calibration are keyed by (family, perturbation code) over all
    validation tolerance flips; k=1 / k=2 fixed-minimum counts cover all measured
    tolerance flips.
17. New modules not listed in plan D: `gate.py`, `identity.py`, `freeze.py`
    (Task 7) and `runs.py` (Task 9, run steps behind the CLI). All are part of the
    identity comparison set; `reporting.py` and `__main__.py` remain record-only.
    `manifest.json` written by the `manifest` command holds the constants, the
    manifest without per-pair expansion, and its `manifest_sha256`.

Independent review findings that the earlier revision did not disclose, and their fixes:

18. M-1 (`9c0fdd8`): change pairs were 16-bit only and aggravation pairs also came from
    phase 1.0 / 2.0 groups. Onset and aggravation pairs now come in 16, 24 and 32 bits
    (both sides at the same depth), phase 0 only; aggravation only from phase-0 M3
    groups.
19. M-2 (`9c0fdd8`): the validation sub-grid lacked B.2 rule 1 groups with a held-out
    f0 and fixed subsets for M2-M5, and part of rule 2. Groups are now generated per
    rule for M1-M6; T-CX374 checks per-family, per-rule counts against hand counts.
20. M-3 (`9c0fdd8`): the second calibration M9 layout was swapped twice and equalled the
    first; it now really exchanges the channels.
21. M-4 (`9c0fdd8`): blind pairs had identical sides and an inverted depth. See
    interpretation 29.
22. M-5 (`7728398`): the stage-1/stage-2 report JSON that freeze records select from was
    built in record-only `reporting.py`; it is now built in `fitting.py` (identity
    comparison set) and `reporting.py` renders Markdown only.
23. M-6 (`7728398`): the gate was looser than described. The access issuer is private
    to `freeze`; pair enumeration returns calibration pairs unless given
    `ValidationAccess`; `MeasurementRowSpec` carries the side and `measure_row` checks
    the gate; `manifest.pairs` holds calibration records only.
24. m-1 (`8efc112`): round_1 generation did not run the per-pair parameter leakage
    check and the check skipped M9. It now runs per channel (M9 split by layout); the R0
    `manifest` write aborts on a hit and `--dry-run` prints `param_leakage_hits`.
25. m-2 (`8efc112`): A.15 scanned only P5/P5t. It now scans every side of every
    calibration pair channel by channel (base material and P5t hits abort; P1, P3, P5,
    P6, onset and aggravation hits are excluded and listed); the ROUND_1 exclusion count
    is pinned at 384 (previously 336). See interpretation 33 for the prefilter.
26. m-3 (`b2f0e2e`): 32-bit offsets were clipped to the int32 range; they are now
    clipped on the 2^-24 grid to [-2^24 * 128, (2^24 - 1) * 128].
27. m-4 (`b2f0e2e`): the M7 marker covered M3/M4 only and counted per period; it now
    covers M2, M3 and M5 (M4 is never marked). See interpretation 32.
28. m-5 (`b2f0e2e`): the harmonic tool input also passed `fundamental_hz`; it now passes
    only `channel` and `time_range` (bundle digests change accordingly).
    Also: m-6 (`7728398`) adds a test that a package digest change refuses calibrate and
    validate; m-7 (`7728398`) binds `authorize_validation` to the manifest round and
    replaces the `round_id == "round_1"` branch with the `expand_pairs` constant
    (MINI True, ROUND_1 False). Surviving mutants (P9 d' = 4d, skipped
    `verify_freeze_record`, skipped `_require_absent`) now have killing tests
    (`8efc112`).

Interpretations made in this round:

29. Blind pairs: the single-sample pair's old side is an unclipped 997 Hz sine at
    amplitude 0.9 (as for onset pairs) and its new side is clipped at 0.9905 with
    pre-clip peak 0.991 (depth = level / pre-clip peak). The sub-full-scale pairs change
    depth 0.99 -> 0.9 at each of levels 0.9 and 0.98 (same level on both sides).
30. B.2 rule 2 uses every non-empty subset of held-out clipping dimensions (for example
    M3 level and depth both held out), with phase 0.
31. A.15 hits on change pairs (onset, aggravation) are excluded and listed like
    sensitivity pairs, not treated as an abort. In round_1 they do not occur (all 384
    exclusions are P5: M3 192, M2 144, M9 48).
32. M7 counts samples per peak as maximal runs of consecutive samples at or over the
    threshold (positive and negative peaks separately); a material is marked when any
    run has 1-3 samples.
33. A.15 prefilter: the first samples of the shortest calibration range are compared
    against every same-bucket validation material (2-code float bound, an exact
    necessary condition for every longer range); only survivors are synthesised in full
    and compared code by code over the pair's analysis range.

34. A.16 (operator decision, 2026-10-05): tables are sharded by side x family x
    analysis-range length, at `<side>_{measurements,pairs}/<family>/L<us>us.jsonl.gz`
    (integer microseconds; one encoder/decoder in `store.py`). Pair lines reference
    measurement rows as `{"shard": "<family>/<range key>", "row": n}`. Freeze-record
    directory digests cover the nested shards. `--dry-run` prints one estimate per shard
    and exits 2 when any shard exceeds 50,000,000 B (`c67017c`).
35. Build speed for the ROUND_1 test budget (hashes unchanged): cyclic GC is paused while
    streaming pair descriptions, the validation wave index only holds materials that
    share a calibration (f0, sr), side specs are memoised and perturbed full waves are
    cached per group (`c67017c`).
36. Second-round review follow-ups (`5e9b6f6`, after the content tip above; code only, no
    change to materials, hashes or dry-run output): `runs.py` now imports
    `stage1_report_json` / `stage2_report_json` from `fitting.py` (identity comparison
    set) instead of `reporting.py`, pinned by
    `test_t_cx378_runs_take_frozen_report_json_from_the_comparison_set`; and
    `test_t_cx380_pair_rows_resolve_to_the_measured_rows` asserts that pair-table row
    references resolve to the rows actually measured. Verified after the change:
    `tests/evaluation/full_scale_characterization` plus `tests/test_architecture_boundaries.py`
    216 passed; ruff `All checks passed!`; mypy `Success: no issues found in 167 source
    files`.

## Validation gate

The gate guards against accidental use; it does not defend against deliberate code
changes. Internal entry points that remain directly callable without `ValidationAccess`:
`pairs._r0_description_records` / `pairs._r0_description_batches` (pair descriptions of
both sides, used for the R0 hash, the A.15 scan and tests),
`materials.synthesize_side_waveform` (documented as internal to the executor and the
R0 scan) and `leakage.count_param_leakage`. Generating, measuring, sanity-checking or
writing validation material through the public entry points requires access issued by
`freeze.authorize_validation` after a complete, verified freeze record.
