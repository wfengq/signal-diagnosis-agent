# D055 explanation live acceptance run 1

## Run identity

| Field | Value |
| --- | --- |
| Started (UTC) | 2026-10-07T09:10:37Z |
| Finished (UTC) | 2026-10-07T09:12:11Z |
| Base commit (`origin/main`) | `f9fde48ef044734f2a220c92719044fff9788de3` |
| Prompt | `v0.3-s1-explain-1.0` |
| Model | `deepseek-v4-flash` (default; `DEEPSEEK_MODEL` unset) |
| Command | `python -m signal_diag.app.explanation_eval --live --out docs/evaluations/v0_3/explanation/live_1` |
| Offline preflight | `/tmp/explain_offline` → `cases: 50`, `model_calls: 0` |

No product code, prompts, or pass-rate bar were changed. The live suite was executed once.

## Summary numbers (`summary.json`)

| Metric | Value |
| --- | --- |
| `cases` | 50 |
| `model_calls` | 50 |
| `model_explanations` | 41 |
| `validation_pass_rate` | **0.82** |
| `pass_rate_bar` | 0.9 |
| `meets_validation_bar` | **false** |
| `claims_covered` | 50 |
| `steps_on_menu` | 50 |
| Groups | contextual_dev 20 / contextual_validation 20 / sweep 10 |

### `fallback_reasons` distribution

| Reason | Count |
| --- | --- |
| `validation_failed:wording` | 8 |
| `validation_failed:fault_mismatch` | 1 |

Only two reason classes appeared (9 fallbacks total = 50 − 41). There is no third class in this run.

## Top fallback reasons (examples from `results.jsonl`)

Rejected model drafts are not retained in the eval artifact; each row stores the template fallback plus `fallback_reason`. The failing §30 check is the suffix of that reason.

1. **`validation_failed:wording` (8)** — case `857fac53e4d2e57e` (group `contextual_dev`, outcome `supported_fault`).
   Check: `wording` in `validate_explanation` / `_check_sentence`. Fails when the draft uses banned compliance language (`标准` / `合格` / `standard` / `SLA` / …) or mentions threshold language (`阈值` / `threshold` / …) without a demonstration qualifier (`演示` / `demo`). Source fell back to `template`.

2. **`validation_failed:fault_mismatch` (1)** — case `0b4fabbb2d7eae08` (group `contextual_validation`, outcome `inconclusive`).
   Check: `fault_mismatch` in `_check_sentence`. Fails when conclusion/meaning affirms a fault term (e.g. clipping / harmonic distortion / no-fault / inconclusive phrasing) whose supporting fault is not among the cited packet items’ `supports`. Source fell back to `template`.

## Gate status

- Automatic bar (`validation_pass_rate` ≥ 0.9): **not met** (0.82).
- Human review of the 20 seeded samples in `review.md` is **pending operator completion**.
- Until both the automatic bar and a clean human review are satisfied, **do not enable** `SIGNAL_DIAG_EXPLAIN_MODEL`.

## Safety

- The provider API key stayed in the process environment only; it was not printed or written to outputs.
- Literal-key scan of `summary.json`, `results.jsonl`, and `review.md`: no provider key material and no provider key-prefix tokens.
- No audio artifacts were produced or committed.
