# D060 phase C result Q&A live acceptance run 3

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-08T01:07:15Z |
| Finished (UTC) | 2026-10-08T01:07:47Z |
| Base commit (`origin/main`) | `1c2affa` (#107) |
| Prompt | `v0.3-s1-qa-1.2` |
| Check / QA version | `result-qa-1.2` |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Command | `python -m signal_diag.app.qa_eval --cases heldout_3 --live --out docs/evaluations/v0_3/qa/live_3` |
| Case set | heldout_3 (20 questions) |
| Model calls | 20 (one per question) |

No product code, prompts, validators, or questions were changed. The heldout_3 set was run once; there was no mid-run network failure and no full re-run.

## Summary numbers (`summary.json`)

Automatic bars: validation pass rate ≥ 0.9, and model decline rate on expected-decline questions ≥ 0.9.

| Metric | Value |
| --- | --- |
| `cases` / `model_calls` | 20 / 20 |
| `validation_pass_rate` | **0.85** |
| `model_decline_rate` | **1.0** |
| `declined_when_answerable` | 3 |
| `meets_validation_bar` | **false** |
| `meets_decline_bar` | **true** |
| `fallback_reasons` | `validation_failed:fault_mismatch`: 1; `validation_failed:wording`: 2 |
| `rejection_details` | forbidden wording '合格': 1; forbidden wording '标准': 1; mentions harmonic_distortion without citing it: 1 |
| `qa_version` | `result-qa-1.2` |
| `validator_version` | `explain-validator-1.1` |

## Automatic gate result

- Validation pass rate ≥ 0.9: **not met** (0.85).
- Expected-decline model decline rate ≥ 0.9: **met** (1.0).

## Human review

人工审核待运营者完成（review.md，20 条中 0 条错误）。
