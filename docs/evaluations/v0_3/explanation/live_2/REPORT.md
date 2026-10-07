# D055 explanation live acceptance run 2

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-07T10:14:30Z |
| Finished (UTC) | 2026-10-07T10:16:04Z |
| Base commit (`origin/main`) | `57dc296007455534fbe40d10d4ea30cbbe1ce237` (#88) |
| Prompt | `v0.3-s1-explain-1.0` (unchanged) |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Validator | `explain-validator-1.1` |
| Command | `python -m signal_diag.app.explanation_eval --live --out docs/evaluations/v0_3/explanation/live_2` |
| Offline preflight | `/tmp/explain_offline` → `cases: 50`, `model_calls: 0`, `validator_version: explain-validator-1.1` |

No product code, prompts, or pass-rate bar were changed. The live suite was executed once. The `live_1/` directory was not modified (and is not present on this `main` tip).

## Summary numbers (`summary.json`)

| Metric | Value |
| --- | --- |
| `cases` | 50 |
| `model_calls` | 50 |
| `model_explanations` | 50 |
| `validation_pass_rate` | **1.0** |
| `pass_rate_bar` | 0.9 |
| `meets_validation_bar` | **true** |
| `claims_covered` | 50 |
| `steps_on_menu` | 50 |
| `validator_version` | `explain-validator-1.1` |
| Groups | contextual_dev 20 / contextual_validation 20 / sweep 10 |

### `fallback_reasons`

*(empty — no fallbacks)*

### `rejection_details`

*(empty — no rejections)*

## Rejected cases

None. Every row in `results.jsonl` has `source: model`, `fallback_reason: null`, `rejection_detail: null`, and `rejected_draft: null`.

## Comparison with `live_1`

| | `live_1` (PR #87, `f9fde48`, validator 1.0) | `live_2` (this run, `57dc296`, validator 1.1) |
| --- | --- | --- |
| `validation_pass_rate` | 0.82 | **1.0** |
| `meets_validation_bar` | false | **true** |
| `model_explanations` | 41 / 50 | 50 / 50 |
| Fallbacks | wording ×8, fault_mismatch ×1 | none |

`live_1` remains the historical record of the pre-D058 validator; this run does not alter that directory.

## Gate status

- Automatic bar (`validation_pass_rate` ≥ 0.9): **met** (1.0).
- Human review of the 20 seeded samples in `review.md` is **pending operator completion**.
- Until that human review shows no wrong statement, **do not enable** `SIGNAL_DIAG_EXPLAIN_MODEL`.

## Safety

- The provider API key stayed in the process environment only; it was not printed or written to outputs.
- Literal-key scan of `summary.json`, `results.jsonl`, and `review.md`: no provider key material and no provider key-prefix tokens.
- No audio artifacts were produced or committed.
