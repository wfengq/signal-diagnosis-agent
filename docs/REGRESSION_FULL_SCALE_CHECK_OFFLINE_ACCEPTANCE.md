# Regression full-scale check — offline acceptance (V0.3 §23)

**Branch:** `cursor/s1-full-scale-check`
**Baseline tip:** `16450ffe904c48294148418ddadfe87c04af6e74`
**Task 9 content tip:** `0a2dd59055e6c7bdea5ecad80b983b3a55ace07e`
**Docs-only follow-ups after content tip:** `40cb82d09d4f0680cca9baa3abf949b034244bfb`, `a043d198b594226b97478f6fc7ffa6eb1361ba76` (SHA line / acceptance wording only)
**Branch tip at this revision:** see `git rev-parse HEAD` after the F1–F3 fix commit.

## Validation scope

Report validation guarantees **internal consistency** of a payload: digests match recomputation, facts match their bundles where checkable, check records match re-evaluation, anchors/repeats/`check_id` structure is complete, and applicable approved floors are not dropped.

It does **not** guarantee that a report was not **wholly rewritten**. Digests are unkeyed hashes. Per §23.5, `counted_samples` and `over_threshold_uncounted` cannot be recomputed after submit (samples are not retained) and are protected only by the facts digest.

**Not required to reject (accepted residual risk, plan revision 4 / 9B-1):** when the bundle has `flat_top_detected=true`, changing `counted_samples` to another positive value ≤ `clipped_samples` and redigesting all digests stays internally consistent. Covered by `test_9b1_flat_top_count_rewrite_within_clipped_is_accepted_residual_risk`.

## Verification commands (tip `a043d198b594226b97478f6fc7ffa6eb1361ba76`)

### `python -m pytest -q -rxXs -p no:cacheprovider`

```text
2042 passed, 1 warning in 109.54s (0:01:49)
```

### `python -m ruff check --no-cache src tests scripts`

```text
All checks passed!
```

### `python -m mypy --no-incremental src`

```text
Success: no issues found in 145 source files
```

### `python scripts/verify_phase5_wheel.py`

```text
Successfully built signal-diagnosis-agent-0.2.0.tar.gz and signal_diagnosis_agent-0.2.0-py3-none-any.whl
The virtual environment was not created successfully because ensurepip is not available.
...
Failing command: /tmp/signal-diag-phase5-wheel-*/venv/bin/python3
```

Wheel smoke **blocked** in this cloud image (no ensurepip/venv). **CI wheel job is authoritative.**

### `git diff --check 16450ffe904c48294148418ddadfe87c04af6e74..HEAD`

```text
(empty — exit 0)
```

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
| T-CX366 | `test_t_cx356_359_362_366_each_gate_blocks_a_large_onset`, `test_t_cx366_lists_all_unmet_when_one_side_has_no_facts` |
| T-CX367 | `test_t_cx367_validation_recomputes_and_rejects_tampering`, `test_t_cx367_report_carries_and_validates_checks`, `test_t_cx367_report_rejects_dropped_repeat_and_fabricated_floor` |
| T-CX368 | `test_t_cx368_check_stays_out_of_diagnosis` |
| T-CX369 | `test_t_cx369_full_scale_layering` |
| T-CX370 | `test_t_cx370_fingerprint_covers_declarations`, `test_t_cx370_api_accepts_declarations_and_defaults_unknown`, `test_t_cx370_api_rejects_unknown_declaration_fields`, `test_report_json_has_no_lines` |

## Product and fixture semantics

- **No approved method floor on the product path:** `PRODUCT_APPROVED_FULL_SCALE_FLOORS` is empty; `build_regression_service()` passes `full_scale_floor=None`. Checks surface `floor_missing` and **`descriptive_only` / `not_comparable` only** — no judged regression status on the product path. Later superseded for the live product path by D044 (round_1 floor YAML registration; T-CX381–T-CX386).
- **Fixture numeric values** in `tests/rules/full_scale_fixtures.py` (including `FIXTURE_FLOOR`) exercise logic only; they are **not** product tolerances or characterization results.
- **No layer-1 characterization, no RealLLM, no seal** were run for this offline record.
- This document is **not** product benefit evidence.

## Plan deviations

1. `shaped()` uses `isolated_peak = 1.0` when the requested peak is below `0.99` so isolated over-threshold samples match probe semantics (plan tuple `(0, 0.5)` + `baseline_isolated=40`).
2. `test_report_shows_record_status_beside_not_comparable_check` asserts clipping_ratio stays `descriptive_only` while THD may be `not_comparable` under the frozen comparison rules (plan expected a single-status set).
3. Task 4 commit is an **empty marker** (`c7fb811`); eligibility/judgment shipped in `ec8317a`.
4. Append-only code-identity tips: `d043_regression_full_scale_check_impl`, `d043_regression_full_scale_check_task9a`, `d043_regression_full_scale_check_task9` (each prior tip’s `product_tree_sha256` pinned to a literal when the live tree moved).
5. Task 9 (plan revisions 3–4): 9A–9D review fixes on this branch; 9B-1 residual flat-top count rewrite documented as not rejected per §23.5.
6. 9B-1 non-flat-top fixture uses runs of exactly two over-threshold samples (`_non_flat_top_samples`), not bare `sine(amplitude=0.9905)`. On PCM16 the plan’s sine construction triggers `flat_top_detected` (min flat-top length 3); short runs of length 2 keep flat-top false so the equality bound is testable. Plan wording was wrong for PCM16; this construction is intentional.
