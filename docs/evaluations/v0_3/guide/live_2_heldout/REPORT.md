# D059 test guide live acceptance run 2

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-07T11:32:08Z |
| Finished (UTC) | 2026-10-07T11:33:17Z |
| Base commit (`origin/main`) | `7a7caf4f3aaeef21e5a2421d5e2df418f702dd67` (#94) |
| Prompt | `v0.3-s1-guide-1.1` |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Commands | `python -m signal_diag.app.guide_eval --live --cases heldout --out docs/evaluations/v0_3/guide/live_2_heldout` then `python -m signal_diag.app.guide_eval --live --cases dev --out docs/evaluations/v0_3/guide/live_2_dev` |
| Offline heldout | `/tmp/guide_heldout_offline` → cases 20, model_calls 0, plan_accuracy 1.0, parameter_accuracy 1.0 |
| Offline dev | `/tmp/guide_dev_offline` → cases 40, model_calls 0, plan_accuracy 1.0, parameter_accuracy 1.0 |

No product code, prompts, scenarios, or bars were changed. Each case set was run once (60 model calls total). `live_1/` and `heldout/` were not modified.

## Summary numbers

Bars for enabling the model path: plan_accuracy ≥ 0.9, parameter_accuracy ≥ 0.9, number_rejections = 0. **Acceptance is decided by the held-out set.**

### Held-out (`live_2_heldout/summary.json`)

| Metric | Value |
| --- | --- |
| `cases` / `model_calls` | 20 / 20 |
| `plan_accuracy` | **0.95** |
| `parameter_accuracy` | **0.95** |
| `number_rejections` | **0** |
| `unnecessary_question_cases` | 0 |
| `meets_bar` | **true** |
| `fallback_reasons` | *(empty)* |
| `rejection_details` | *(empty)* |
| `prompt_version` | `v0.3-s1-guide-1.1` |

`by_expected_plan` (plan_correct): existing_recording 4/4, nominal_tone 4/4, paired_reference 4/4, sweep_levels 7/8.

### Dev (`live_2_dev/summary.json`) — reference only

| Metric | Value |
| --- | --- |
| `cases` / `model_calls` | 40 / 40 |
| `plan_accuracy` | **0.975** |
| `parameter_accuracy` | **0.975** |
| `number_rejections` | **0** |
| `unnecessary_question_cases` | 0 |
| `meets_bar` | true |
| `fallback_reasons` | *(empty)* |
| `rejection_details` | *(empty)* |

`by_expected_plan`: existing_recording 7/7, nominal_tone 5/5, paired_reference 6/6, sweep_levels 21/22.

### vs `live_1` (dev set, prompt 1.0)

| | live_1 (dev) | live_2_dev | live_2_heldout (gate) |
| --- | --- | --- | --- |
| plan_accuracy | 0.775 | 0.975 | **0.95** |
| parameter_accuracy | 0.65 | 0.975 | **0.95** |
| number_rejections | 0 | 0 | 0 |
| unnecessary_question_cases | 11 | 0 | 0 |
| fallback `illegal_output` | 9 | 0 | 0 |
| meets_bar | false | true | **true** |

## Gate conclusion

Held-out meets all three bars. Operator decision to enable `SIGNAL_DIAG_GUIDE_MODEL` is still required and must be recorded as an amendment to D057/D059. This run does **not** turn the flag on.

## Cases with `plan_correct=false` or `parameters_correct=false`

No rows used questionnaire fallback; both misses are accepted model drafts with the wrong plan.

| set | case_id | tags | expected_plan | plan_id | source | fallback_reason | rejection_detail | plan_ok | param_ok | model parameters |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| heldout | h08 | conflict, sweep, line, en | sweep_levels | existing_recording | model | — | — | false | false | test_file=bench_clip.wav; connection=null; sample_rate_hz=null; level_labels=[]; defaults=[]; reference_file=null; nominal_fundamental_hz=null |
| dev | g38 | conflict, sweep, mic | sweep_levels | existing_recording | model | — | — | false | false | test_file=old.wav; connection=null; sample_rate_hz=null; level_labels=[]; defaults=[]; reference_file=null; nominal_fundamental_hz=null |

Both are conflict-style cases (an uploaded clip plus language that still allows a retest). The model chose `existing_recording` instead of `sweep_levels`.

## Rejected drafts

None. Every row has `fallback_reason`, `rejection_detail`, and `rejected_draft` null.

## Cases with `unnecessary_questions=true`

None in either set.

## Safety

- The provider API key stayed in the process environment only; it was not printed or written to outputs.
- Literal-key scan of both `summary.json` and `results.jsonl` files: no provider key material.
- No audio artifacts were produced or committed.
