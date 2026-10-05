# Layer-1 full-scale characterization tool — offline acceptance (T-CX371–T-CX380)

**Branch:** `cursor/s1-layer1-characterization-tool`
**Baseline:** `de08fe56eae7589a43f081c629a2b6756c7397b3`
**Content tip (Task 9 code):** `dc7da0265c49b23fa19e5a107b3408cd434e1f4a`
**Branch tip:** the commit that adds this document (see the PR description); it changes only this file.

Plan: `docs/superpowers/plans/2026-10-05-s1-regression-layer1-characterization.md` (revision 3), Tasks 0–9.

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

All commands were run in the worktree on the content tip
`dc7da0265c49b23fa19e5a107b3408cd434e1f4a` (the full pytest run used the identical
working tree immediately before that commit).

### `.venv/bin/python -m pytest -q -rxXs -p no:cacheprovider`

```text
1 failed, 2162 passed, 1 warning in 363.34s (0:06:03)
```

The single failure is
`tests/evaluation/test_dataset.py::test_t133_official_case_allocation_and_packaging`:
it runs `python -m pip wheel ...` and the local uv-created venv has no pip
(`/home/user/signal-diagnosis-agent/.wt-l1/.venv/bin/python: No module named pip`).
This is an environment limitation unrelated to this change; CI is authoritative for
it. No test was skipped, xfailed or xpassed.

### `.venv/bin/python -m pytest -q tests/test_architecture_boundaries.py`

```text
65 passed in 10.64s
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
sdist signal_diagnosis_agent-0.2.0.tar.gz sha256=b8cdfbb08a69f6db2960ece1c0defc2ec229383e88fabccfcd0303e9b515d5c5
wheel signal_diagnosis_agent-0.2.0-py3-none-any.whl sha256=cb9d0d0dde6d06e63ce6a731dd40b733f33fef2a4ef772e717e0f631eb56f5d1
```

### `git diff --check de08fe56eae7589a43f081c629a2b6756c7397b3..HEAD`

Run after the content-tip commit and again after this document's commit: no output,
exit status 0.

## Test IDs and test functions

Collected from the test files (`grep '^def test_'`).

### T-CX371

`tests/evaluation/full_scale_characterization/test_layering.py`:

- `test_t_cx371_package_does_not_import_rules_agent_app_or_knowledge`
- `test_t_cx371_product_layers_do_not_mention_characterization_package`
- `test_t_cx371_product_approved_full_scale_floors_stays_empty`

### T-CX372

`tests/evaluation/full_scale_characterization/test_pcm_encoding.py`:

- `test_t_cx372_round_trip_codes_16_24_8`
- `test_t_cx372_round_trip_32_matches_float32_decode`
- `test_t_cx372_pm_one_no_overflow_all_bit_depths`
- `test_t_cx372_one_step_perturbations_bounded_and_directional`
- `test_t_cx372_32bit_decode_offset_exactly_one_step_for_large_samples`
- `test_t_cx372_random_one_step_seed_deterministic_and_varies`
- `test_t_cx372_32bit_trunc_differs_from_round_not_p0`
- `test_t_cx372_does_not_import_app_pcm_wav`

`tests/evaluation/full_scale_characterization/test_synthesis.py`:

- `test_t_cx372_sine_amplitude_and_phase`
- `test_t_cx372_clipped_pre_clip_peak_and_output_bound`
- `test_t_cx372_clipped_m5_harmonics_before_scale_and_clip`
- `test_t_cx372_clipped_level_one_stays_within_full_scale`
- `test_t_cx372_harmonic_sine_m6_no_extra_scaling`

### T-CX373

`tests/evaluation/full_scale_characterization/test_t_cx373_manifest.py`:

- `test_round_1_manifest_hash_is_stable`
- `test_round_1_build_within_wall_budget`
- `test_constants_change_changes_manifest_hash`
- `test_round_1_planned_counts_only`
- `test_mini_sensitivity_pairs_single_perturbation`
- `test_mini_tolerance_codes_only_listed`
- `test_seed_sets_do_not_overlap`
- `test_calibration_has_no_combo_or_blind`

`tests/evaluation/full_scale_characterization/test_t_cx373_p4_p9_orientation.py`:

- `test_t_cx373_p4_p9_old_side_is_coarser_bit_depth`
- `test_t_cx373_p4_both_sides_round`
- `test_t_cx373_p9c_old_side_truncates_coarse_new_side_rounds_fine`
- `test_t_cx373_p9ab_fine_file_shifted_by_exactly_one_coarse_step`
- `test_t_cx373_p9a_review_counterexample_flips_on_full_tool_path`

### T-CX374

`tests/evaluation/full_scale_characterization/test_t_cx374_manifest.py`:

- `test_source_group_side_consistency`
- `test_calibration_only_calibration_range_lengths`
- `test_group_key_ignores_filename_seed_perturbation`
- `test_validation_has_each_family_combo_and_blind`
- `test_no_calibration_effective_params_match_validation_materials`
- `test_p3_result_phases_disjoint_from_validation_held_out`
- `test_onset_calibration_depths_exclude_0_9999`
- `test_scale_limit_raises_when_exceeded`
- `test_round_1_within_scale_limit_or_blocked`
- `test_near_duplicate_exclusions_listed_not_silent`
- `test_leakage_abort_on_forbidden_onset_depth`
- `test_a15_prefilter_matches_full_encode_on_m3_p5_hit`
- `test_prefilter_skips_distant_pairs`

### T-CX375

`tests/evaluation/full_scale_characterization/test_t_cx375_executor.py`:

- `test_facts_match_direct_measure_full_scale_facts`
- `test_identical_input_produces_identical_row_digests`
- `test_cache_returns_same_row_for_same_key`
- `test_m9_left_channel_matches_mono_same_params`
- `test_terminal_generation_failed`
- `test_terminal_invalid_wav_load`
- `test_terminal_invalid_clipping_tool`
- `test_terminal_invalid_measure_output`
- `test_assemble_pair_stays_in_denominator_with_terminal_states`

### T-CX376

`tests/evaluation/full_scale_characterization/test_t_cx376_checks.py`:

- `test_t_cx376_near_material_separates_the_three_thresholds`
- `test_t_cx376_all_checks_pass_on_legal_material`
- `test_t_cx376_p0_nonzero_count_diff_aborts`
- `test_t_cx376_p0_wav_sha256_mismatch_aborts`
- `test_t_cx376_sandwich_upper_bound_violation_aborts`
- `test_t_cx376_sandwich_lower_bound_violation_aborts`
- `test_t_cx376_p9_sandwich_uses_two_steps_and_still_aborts_outside`
- `test_t_cx376_p7a_equality_violation_aborts`
- `test_t_cx376_p7b_equality_violation_aborts`
- `test_t_cx376_p7_flip_outside_fixed_zone_aborts`
- `test_t_cx376_facts_verification_failure_aborts_with_pair_id`
- `test_t_cx376_p9_flip_outside_k1_zone_is_counted_not_aborted`

### T-CX377

`tests/evaluation/full_scale_characterization/test_t_cx377_fitting.py`:

- `test_t_cx377_candidate_tables_are_fixed`
- `test_t_cx377_stage1_emits_every_domain_and_k_row`
- `test_t_cx377_k2_k1_minimal_parameters_match_hand_calculation`
- `test_t_cx377_points_inside_fixed_minimum_are_removed`
- `test_t_cx377_k4_uses_two_sample_level_and_is_non_negative`
- `test_t_cx377_k3_rows_match_hand_calculation_and_use_or`
- `test_t_cx377_k0_label_only_counts_tolerance_pairs_of_main_conditions`
- `test_t_cx377_k1_k2_flip_counts_reported_separately`
- `test_t_cx377_shares_and_onset_tiers`
- `test_t_cx377_fitting_rejects_validation_records`
- `test_t_cx377_f1_f2_are_plain_maxima_without_margin`
- `test_t_cx377_f3_only_single_cut_on_n_or_periods`
- `test_t_cx377_stage2_accepts_only_stage1_selection`
- `test_t_cx377_row_limits`
- `test_t_cx377_reports_list_all_rows_without_ranking_language`
- `test_t_cx377_vectorised_zone_matches_scalar_predicate_for_every_row`

`tests/evaluation/full_scale_characterization/test_t_cx377_zone_parity.py`:

- `test_t_cx377_quantization_step_matches_product`
- `test_t_cx377_zone_k1_k2_k3_match_product_in_critical_zone`
- `test_t_cx377_f1_f2_match_product_judgment_status`
- `test_t_cx377_hard_condition_uses_absolute_difference`
- `test_t_cx377_domain_expressions_are_verbatim_with_product`

### T-CX378

`tests/evaluation/full_scale_characterization/test_t_cx378_freeze_store.py`:

- `test_t_cx378_store_refuses_to_overwrite_and_sums_match`
- `test_t_cx378_store_detects_tampering_and_unlisted_files`
- `test_t_cx378_store_rejects_paths_outside_layout`
- `test_t_cx378_gzip_shards_are_deterministic`
- `test_t_cx378_shard_size_limit`
- `test_t_cx378_validation_artifacts_need_validation_access`
- `test_t_cx378_identity_has_comparison_and_record_only_parts`
- `test_t_cx378_identity_mismatch_blocks_calibration_and_validation`
- `test_t_cx378_git_commit_unavailable_is_recorded_as_null`
- `test_t_cx378_freeze_two_parts_round_trip`
- `test_t_cx378_freeze_digest_is_self_checking`
- `test_t_cx378_stage1_rejects_upstream_hash_mismatch`
- `test_t_cx378_stage1_can_only_select_not_edit`
- `test_t_cx378_stage2_can_only_select_not_edit`
- `test_t_cx378_stage2_accepts_only_the_written_stage1`
- `test_t_cx378_no_freeze_record_locks_validation_entry_points`
- `test_t_cx378_stage1_only_still_locks_validation`
- `test_t_cx378_full_freeze_unlocks_validation_entry_points`
- `test_t_cx378_tampered_freeze_record_locks_validation`

### T-CX379

`tests/evaluation/full_scale_characterization/test_t_cx379_validation.py`:

- `test_t_cx379_frozen_fixture_values`
- `test_t_cx379_clean_population_meets_hard_conditions`
- `test_t_cx379_hard_condition_1_violation_is_listed`
- `test_t_cx379_hard_condition_2_uses_absolute_difference_and_f3_segment`
- `test_t_cx379_flip_in_zone_excluded_and_out_of_domain_listed`
- `test_t_cx379_minimum_detectable_change_by_tier`
- `test_t_cx379_disclosures_are_complete_and_kept_out_of_hard_conditions`
- `test_t_cx379_count_requires_validation_access`
- `test_t_cx379_finalize_writes_report_once`
- `test_t_cx379_sanity_abort_writes_abort_record_and_no_report`

### T-CX380

`tests/evaluation/full_scale_characterization/test_t_cx380_end_to_end.py`:

- `test_t_cx380_six_steps_end_to_end_reproducible`
- `test_t_cx380_freeze_accepts_only_row_ids_from_reports`
- `test_t_cx380_dry_run_writes_nothing_and_prints_fit_row_counts`

## `manifest --round round_1 --dry-run`

Command: `.venv/bin/python -m signal_diag.evaluation.full_scale_characterization manifest --round round_1 --dry-run`
(exit status 0). It wrote no file. The printed counts are a dry run only and do not
constitute R0 manifest approval.

```text
round_id=round_1
manifest_sha256=fa81f917d7b666dfe58847ae15338a9a935f0a2b6bcd25cc6f2ab22a6d90e26b
planned_pair_counts:
  calibration: 382032
  validation: 321900
by_side/family/perturbation:
  calibration/M1/ONSET: 192
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
  calibration/M9/P5: 576
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
  validation/M1/ONSET: 250
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
  validation/M2/COMBO_P1_P6: 910
  validation/M2/COMBO_P4_P5: 910
  validation/M2/COMBO_P6_DUAL: 910
  validation/M2/P0: 2730
  validation/M2/P1: 1820
  validation/M2/P3: 800
  validation/M2/P4: 2730
  validation/M2/P5: 3640
  validation/M2/P5t: 1820
  validation/M2/P6: 13650
  validation/M2/P7a: 2730
  validation/M2/P7b: 2730
  validation/M2/P7c: 2730
  validation/M2/P7d: 13650
  validation/M2/P8: 1820
  validation/M2/P9a: 2730
  validation/M2/P9b: 2730
  validation/M2/P9c: 2730
  validation/M3/AGGR: 8950
  validation/M3/BLIND_SINGLE: 10
  validation/M3/COMBO_P1_P6: 1790
  validation/M3/COMBO_P4_P5: 1790
  validation/M3/COMBO_P6_DUAL: 1790
  validation/M3/P0: 5370
  validation/M3/P1: 3580
  validation/M3/P3: 2080
  validation/M3/P4: 5370
  validation/M3/P5: 7160
  validation/M3/P5t: 3580
  validation/M3/P6: 26850
  validation/M3/P7a: 5370
  validation/M3/P7b: 5370
  validation/M3/P7c: 5370
  validation/M3/P7d: 26850
  validation/M3/P8: 3580
  validation/M3/P9a: 5370
  validation/M3/P9b: 5370
  validation/M3/P9c: 5370
  validation/M4/BLIND_SUB: 30
  validation/M4/COMBO_P1_P6: 660
  validation/M4/COMBO_P4_P5: 660
  validation/M4/COMBO_P6_DUAL: 660
  validation/M4/P0: 1980
  validation/M4/P1: 1320
  validation/M4/P3: 1320
  validation/M4/P4: 1980
  validation/M4/P5: 2640
  validation/M4/P5t: 1320
  validation/M4/P6: 9900
  validation/M4/P7a: 1980
  validation/M4/P7b: 1980
  validation/M4/P7c: 1980
  validation/M4/P7d: 9900
  validation/M4/P8: 1320
  validation/M4/P9a: 1980
  validation/M4/P9b: 1980
  validation/M4/P9c: 1980
  validation/M5/COMBO_P1_P6: 700
  validation/M5/COMBO_P4_P5: 700
  validation/M5/COMBO_P6_DUAL: 700
  validation/M5/P0: 2100
  validation/M5/P1: 1400
  validation/M5/P3: 560
  validation/M5/P4: 2100
  validation/M5/P5: 2800
  validation/M5/P5t: 1400
  validation/M5/P6: 10500
  validation/M5/P7a: 2100
  validation/M5/P7b: 2100
  validation/M5/P7c: 2100
  validation/M5/P7d: 10500
  validation/M5/P8: 1400
  validation/M5/P9a: 2100
  validation/M5/P9b: 2100
  validation/M5/P9c: 2100
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
estimated_measurement_rows=1407864
estimated_shard_gzip_bytes calibration/M1: 3492480
estimated_shard_gzip_bytes calibration/M2: 43231680
estimated_shard_gzip_bytes calibration/M3: 42823680
estimated_shard_gzip_bytes calibration/M4: 9139200
estimated_shard_gzip_bytes calibration/M5: 26634240
estimated_shard_gzip_bytes calibration/M6: 2284800
estimated_shard_gzip_bytes calibration/M9: 2284800
estimated_shard_gzip_bytes validation/M1: 7357600
estimated_shard_gzip_bytes validation/M2: 21001800
estimated_shard_gzip_bytes validation/M3: 44529800
estimated_shard_gzip_bytes validation/M4: 15493800
estimated_shard_gzip_bytes validation/M5: 16136400
estimated_shard_gzip_bytes validation/M6: 4222800
estimated_shard_gzip_bytes validation/M9: 703800
excluded_near_duplicates=336
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
