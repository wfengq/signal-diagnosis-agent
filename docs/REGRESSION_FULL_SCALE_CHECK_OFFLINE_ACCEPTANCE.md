# Regression full-scale check — offline acceptance (V0.3 §23)

**Branch:** `cursor/s1-full-scale-check`
**Baseline tip:** `16450ffe904c48294148418ddadfe87c04af6e74`
**Acceptance tip:** see `git rev-parse HEAD` on this branch after closeout commit.

## Verification commands (raw summaries)

### `python -m pytest -q -rxXs -p no:cacheprovider`

Full suite on closeout tip: **2019 passed**, 1 warning (`python3 -m pytest -q -rxXs -p no:cacheprovider`). Focused full-scale slice: **65 passed** (full-scale pytest files listed below; architecture gates T-CX369/T-CX351/T-CX363 included in full suite) (`tests/dsp/test_full_scale.py`, `tests/tools/test_regression_full_scale.py`, `tests/rules/test_full_scale_check.py`, `tests/app/test_full_scale_wording.py`, `tests/app/test_regression_full_scale_service.py`, architecture gates T-CX369/T-CX351/T-CX363).

Identity T-CX254: **3 passed** after append-only `d043_regression_full_scale_check_impl` (`product_tree_sha256` matches live `contextual_product_tree_sha256()` at closeout tip; `d042_regression_workbench_phase_c_task8_revise1` pinned to `e45c301d…`).

### `python -m ruff check --no-cache src tests scripts`

Repo-wide `python3 -m ruff check --no-cache src tests scripts`: **clean** (0 findings) at closeout tip.

### `python -m mypy --no-incremental src`

**Success: no issues found in 145 source files** (acceptance tip).

### `python scripts/verify_phase5_wheel.py`

**Blocked in this cloud image:** `python3-venv` / `python3.12-venv` not installable; script cannot create its temporary venv.

### `git diff --check 16450ffe904c48294148418ddadfe87c04af6e74..HEAD`

No whitespace errors (empty output).

## T-CX349–T-CX370 → tests

| ID | Test function(s) |
|---|---|
| T-CX349 | `test_t_cx349_counts_runs_and_isolated_samples`, `test_t_cx349_matches_existing_full_scale_mechanism`, `test_t_cx349_isolated_peaks_are_uncounted`, `test_t_cx349_rejects_bad_parameters`, `test_t_cx349_facts_follow_bundle_range_and_channel`, `test_t_cx349_facts_use_the_selected_channel` |
| T-CX350 | `test_t_cx350_ratio_difference_never_changes_status` |
| T-CX351 | `test_t_cx351_bundle_digest_unchanged_by_facts`, `test_t_cx351_comparison_record_unchanged_by_full_scale`, `test_t_cx351_frozen_surfaces_untouched_by_full_scale` |
| T-CX352 | `test_t_cx352_353_354_transition_table` |
| T-CX353 | `test_t_cx352_353_354_transition_table`, `test_t_cx353_increase_within_floor_is_not_called_no_increase` |
| T-CX354 | `test_t_cx352_353_354_transition_table`, `test_t_cx354_decrease_notice_is_on_the_status_line` |
| T-CX355 | `test_t_cx355_templates_never_say_clip`, `test_t_cx355_regression_lines`, `test_t_cx355_html_shows_current_and_superseded_checks` |
| T-CX356 | `test_t_cx356_359_362_366_each_gate_blocks_a_large_onset`, `test_t_cx356_periodic_declaration_is_read_from_the_anchor_only` |
| T-CX357 | `test_t_cx357_no_side_within_one_step_is_inside_zone`, `test_t_cx357_fixed_minimum_holds_without_floor`, `test_t_cx357_isolated_over_threshold_no_side_is_inside_zone` |
| T-CX358 | `test_t_cx358_counted_repeat_rules`, `test_t_cx358_other_reasons_and_byte_identical_marking`, `test_t_cx358_anchor_independence_declarations_are_ignored`, `test_t_cx358_359_uncounted_identical_and_inconsistent_lines` |
| T-CX359 | `test_t_cx356_359_362_366_each_gate_blocks_a_large_onset`, `test_t_cx358_359_uncounted_identical_and_inconsistent_lines` |
| T-CX360 | `test_t_cx360_product_profile_guard`, `test_t_cx363_product_builder_has_no_floor_and_no_judged_status` |
| T-CX361 | `test_t_cx361_sub_full_scale_pair_gets_no_regression_signal` |
| T-CX362 | `test_t_cx356_359_362_366_each_gate_blocks_a_large_onset` |
| T-CX363 | `test_t_cx363_no_floor_means_no_judged_status`, `test_t_cx363_unapproved_floor_fails_validation`, `test_t_cx363_product_builder_has_no_floor_and_no_judged_status`, `test_t_cx363_no_floor_values_under_src` |
| T-CX364 | `test_t_cx364_one_record_per_completed_comparison_with_superseding`, `test_t_cx364_replay_and_failure_produce_no_record`, `test_t_cx364_records_do_not_consume_submit_quota` |
| T-CX365 | `test_t_cx365_anchor_resolution` |
| T-CX366 | `test_t_cx356_359_362_366_each_gate_blocks_a_large_onset` |
| T-CX367 | `test_t_cx367_validation_recomputes_and_rejects_tampering`, `test_t_cx367_report_carries_and_validates_checks`, `test_t_cx367_report_rejects_dropped_repeat_and_fabricated_floor` |
| T-CX368 | `test_t_cx368_check_stays_out_of_diagnosis` |
| T-CX369 | `test_t_cx369_full_scale_layering` |
| T-CX370 | `test_t_cx370_fingerprint_covers_declarations`, `test_t_cx370_api_accepts_declarations_and_defaults_unknown`, `test_t_cx370_api_rejects_unknown_declaration_fields`, `test_report_json_has_no_lines` |

## Product and fixture semantics

- **No approved method floor on the product path:** `PRODUCT_APPROVED_FULL_SCALE_FLOORS` is empty; `build_regression_service()` passes `full_scale_floor=None`. Checks surface `floor_missing` and **`descriptive_only` / `not_comparable` only** — no judged regression status on the product path.
- **Fixture numeric values** in `tests/rules/full_scale_fixtures.py` (including `FIXTURE_FLOOR`) exercise logic only; they are **not** product tolerances or characterization results.
- **No layer-1 characterization, no RealLLM, no seal** were run for this offline record.
- This document is **not** product benefit evidence.

## Plan deviations

1. `shaped()` uses `isolated_peak = 1.0` when the requested peak is below `0.99` so isolated over-threshold samples match probe semantics (plan tuple `(0, 0.5)` + `baseline_isolated=40`).
2. `test_report_shows_record_status_beside_not_comparable_check` asserts clipping_ratio stays `descriptive_only` while THD may be `not_comparable` under the frozen comparison rules (plan expected a single-status set).
3. Task 4 commit is an **empty marker** (`c7fb811`); eligibility/judgment shipped in `ec8317a`.
