# D060 phase C result Q&A live acceptance run 2 (prompt 1.1 / heldout_2)

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-07T16:08:56Z |
| Finished (UTC) | 2026-10-07T16:09:26Z |
| Base commit (`origin/main`) | `bd9dffd` (#105) |
| Prompt | `v0.3-s1-qa-1.1` |
| Check / qa_version | `result-qa-1.1` |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Command | `python -m signal_diag.app.qa_eval --cases heldout_2 --live --out docs/evaluations/v0_3/qa/live_2` |
| Case set | heldout_2 (20 questions) |
| Model calls | 20 (one per question) |

No product code, prompts, validators, or questions were changed. The held-out set was run once; there was no mid-run network failure and no full re-run.

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
| `fallback_reasons` | `validation_failed:citation`: 1; `validation_failed:fault_mismatch`: 1; `validation_failed:wording`: 1 |
| `rejection_details` | forbidden wording '合格': 1; mentions harmonic_distortion without citing it: 1; unknown reference rerecord_quieter: 1 |
| `qa_version` | `result-qa-1.1` |
| `validator_version` | `explain-validator-1.1` |

## Automatic gate result

- Validation pass rate ≥ 0.9: **not met** (0.85).
- Expected-decline model decline rate ≥ 0.9: **met** (1.0).

## Human review

人工审核待运营者完成（review.md，20 条中 0 条错误）。

`summary.json` records: `human_review`: `pending: operator scores review.md (no wrong statement in 20 samples)`.
