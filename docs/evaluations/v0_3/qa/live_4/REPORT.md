# D060 phase C result Q&A live acceptance run 4 (last round)

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-08T01:37:42Z |
| Finished (UTC) | 2026-10-08T01:38:11Z |
| Base commit (`origin/main`) | `7ebe880` (#109) |
| Prompt | `v0.3-s1-qa-1.3` |
| Check / QA version | `result-qa-1.3` |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Command | `python -m signal_diag.app.qa_eval --cases heldout_4 --live --out docs/evaluations/v0_3/qa/live_4` |
| Case set | heldout_4 (20 questions) |
| Model calls | 20 (one per question) |

No product code, prompts, validators, or questions were changed. The heldout_4 set was run once; there was no mid-run network failure and no full re-run.

## Summary numbers (`summary.json`)

Automatic bars: validation pass rate ≥ 0.9, and model decline rate on expected-decline questions ≥ 0.9.

| Metric | Value |
| --- | --- |
| `cases` / `model_calls` | 20 / 20 |
| `validation_pass_rate` | **0.9** |
| `model_decline_rate` | **1.0** |
| `declined_when_answerable` | 7 |
| `meets_validation_bar` | **true** |
| `meets_decline_bar` | **true** |
| `fallback_reasons` | `illegal_output`: 1; `validation_failed:fault_mismatch`: 1 |
| `rejection_details` | 1 validation error for QAAnswer: 1; mentions harmonic_distortion without citing it: 1 |
| `qa_version` | `result-qa-1.3` |
| `validator_version` | `explain-validator-1.1` |

## Automatic gate result

- Validation pass rate ≥ 0.9: **met** (0.9).
- Expected-decline model decline rate ≥ 0.9: **met** (1.0).

## Human review and last-round rule

这是最后一轮（§33.3）：任一门槛未过则 AI 问答保持关闭。人工审核待运营者完成（review.md，20 条中 0 条错误）。
