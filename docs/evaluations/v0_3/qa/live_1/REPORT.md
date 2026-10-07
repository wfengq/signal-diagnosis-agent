# D060 phase C result Q&A live acceptance run 1

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-07T15:35:57Z |
| Finished (UTC) | 2026-10-07T15:36:28Z |
| Base commit (`origin/main`) | `89992b7` (#102) |
| Prompt | `v0.3-s1-qa-1.0` |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Command | `python -m signal_diag.app.qa_eval --cases heldout --live --out docs/evaluations/v0_3/qa/live_1` |
| Case set | heldout (20 questions) |
| Model calls | 20 (one per question) |

No product code, prompts, validators, or questions were changed. The held-out set was run once; there was no mid-run network failure and no full re-run.

## Summary numbers (`summary.json`)

Automatic bars: validation pass rate ≥ 0.9, and model decline rate on expected-decline questions ≥ 0.9.

| Metric | Value |
| --- | --- |
| `cases` / `model_calls` | 20 / 20 |
| `validation_pass_rate` | **0.65** |
| `model_decline_rate` | **1.0** |
| `declined_when_answerable` | 2 |
| `meets_validation_bar` | **false** |
| `meets_decline_bar` | **true** |
| `fallback_reasons` | `validation_failed:fault_mismatch`: 7 |
| `rejection_details` | mentions clipping without citing it: 2; mentions harmonic_distortion without citing it: 3; mentions no_supported_fault without citing it: 2 |
| `qa_version` | `result-qa-1.0` |
| `validator_version` | `explain-validator-1.1` |

## Automatic gate result

- Validation pass rate ≥ 0.9: **not met** (0.65).
- Expected-decline model decline rate ≥ 0.9: **met** (1.0).

## Human review

人工审核待运营者完成（`review.md`，20 条中 0 条错误）。

`summary.json` records: `human_review`: `pending: operator scores review.md (no wrong statement in 20 samples)`.
