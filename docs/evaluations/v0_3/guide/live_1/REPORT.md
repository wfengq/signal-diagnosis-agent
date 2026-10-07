# D057 test guide live acceptance run 1

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-07T10:41:10Z |
| Finished (UTC) | 2026-10-07T10:41:54Z |
| Base commit (`origin/main`) | `cbc889b702aeabf947208d4849c5592618d47716` |
| Prompt | `v0.3-s1-guide-1.0` |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Command | `python -m signal_diag.app.guide_eval --live --out docs/evaluations/v0_3/guide/live_1` |
| Offline preflight | `/tmp/guide_offline` → `cases: 40`, `model_calls: 0`, `plan_accuracy: 1.0`, `parameter_accuracy: 1.0` |

No product code, prompts, scenarios, or bars were changed. The live suite was executed once.

## Summary numbers (`summary.json`)

| Metric | Value |
| --- | --- |
| `cases` | 40 |
| `model_calls` | 40 |
| `plan_accuracy` | **0.775** |
| `parameter_accuracy` | **0.65** |
| `number_rejections` | 0 |
| `unnecessary_question_cases` | 11 |
| `meets_bar` | **false** |

Bars required for enabling the model path: `plan_accuracy` ≥ 0.9, `parameter_accuracy` ≥ 0.9, `number_rejections` = 0.

### `fallback_reasons`

| Reason | Count |
| --- | --- |
| `illegal_output` | 9 |

### `by_expected_plan` (plan_correct / cases)

| Expected plan | Score |
| --- | --- |
| `existing_recording` | 2/7 |
| `nominal_tone` | 3/5 |
| `paired_reference` | 5/6 |
| `sweep_levels` | 21/22 |

## Cases with `plan_correct=false` or `parameters_correct=false`

For `illegal_output` rows the eval stores `draft: null` (rejected model text is not retained).

| case_id | tags | expected_plan | plan_id | source | fallback_reason | plan_ok | param_ok | model parameters (if draft present) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| g06 | sweep, line | sweep_levels | sweep_levels | model | — | true | false | connection=null; sample_rate_hz=48000; level_labels=[低于平时, 平时音量, 出问题的音量]; defaults=[sample_rate_hz, level_labels]; test_file=null; reference_file=null; nominal_fundamental_hz=null |
| g08 | sweep, line, en | sweep_levels | sweep_levels | model | — | true | false | connection=null; sample_rate_hz=48000; level_labels=[低于平时, 平时音量, 出问题的音量]; defaults=[sample_rate_hz, level_labels]; test_file=null; reference_file=null; nominal_fundamental_hz=null |
| g15 | sweep, digital | sweep_levels | sweep_levels | model | — | true | false | connection=line_loopback; sample_rate_hz=48000; level_labels=[低于平时, 平时音量, 出问题的音量]; defaults=[sample_rate_hz, level_labels, connection]; test_file=null; reference_file=null; nominal_fundamental_hz=null |
| g18 | sweep, digital, rate | sweep_levels | sweep_levels | model | — | true | false | connection=null; sample_rate_hz=48000; level_labels=[低于平时, 平时音量, 出问题的音量]; defaults=[level_labels]; test_file=null; reference_file=null; nominal_fundamental_hz=null |
| g22 | existing | existing_recording | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g23 | existing, en | existing_recording | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g24 | existing | existing_recording | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g25 | existing | existing_recording | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g26 | existing | existing_recording | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g28 | paired, en | paired_reference | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g31 | paired | paired_reference | paired_reference | model | — | true | false | test_file=dry.wav; reference_file=wet.wav; sample_rate_hz=null; defaults=[]; level_labels=[]; connection=null; nominal_fundamental_hz=null |
| g34 | nominal | nominal_tone | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g37 | nominal | nominal_tone | null | questionnaire | illegal_output | false | false | *(no draft)* |
| g38 | conflict, sweep, mic | sweep_levels | null | questionnaire | illegal_output | false | false | *(no draft)* |

## Cases with `unnecessary_questions=true`

| case_id | Model questions |
| --- | --- |
| g02 | 你能提供一个测试文件，或让我用默认的扫频信号吗？ |
| g03 | Which test file should I play through the preamp? |
| g13 | 你打算播放哪个测试文件？ |
| g18 | 设备输出是怎么录回来的（线路回环、麦克风拾音，还是数字采集）？ / 用哪个测试文件播放？ |
| g21 | 这段录音的采样率是多少赫兹？ |
| g27 | 这两段录音的采样率是多少赫兹？ |
| g29 | 这两段录音的采样率是多少赫兹？ |
| g30 | 这两个录音的采样率是多少赫兹？ |
| g31 | 这两个文件的采样率是多少赫兹？ |
| g33 | 这段录音的采样率是多少赫兹？ |
| g35 | What sample rate is the recording at? |

## Gate status

- Automatic bars: **not met** (plan_accuracy 0.775 below 0.9; parameter_accuracy 0.65 below 0.9; number_rejections 0 meets its bar alone).
- Do **not** enable `SIGNAL_DIAG_GUIDE_MODEL`. Whether to enable is an operator decision after reviewing these results, recorded as an amendment to D057.

## Safety

- The provider API key stayed in the process environment only; it was not printed or written to outputs.
- Literal-key scan of `summary.json` and `results.jsonl`: no provider key material.
- No audio artifacts were produced or committed.
