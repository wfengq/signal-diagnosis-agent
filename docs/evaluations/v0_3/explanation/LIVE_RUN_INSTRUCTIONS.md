# Explanation acceptance run (D055 4A): instructions for the live run

Run this from the repository root on the merged branch. It calls the real model
50 times, once per case. Do not commit the API key, and do not paste it into
any output file.

```bash
export DEEPSEEK_API_KEY=...        # stays in the environment only
python -m signal_diag.app.explanation_eval --live \
  --out docs/evaluations/v0_3/explanation/live_1
```

The run writes three files:

- `summary.json`: `model_calls` (expected 50), `validation_pass_rate`,
  `fallback_reasons`, `claims_covered` and `steps_on_menu`;
- `results.jsonl`: one row per case, including the draft that was shown;
- `review.md`: 20 seeded samples for the operator to score (readable, wrong
  statement, next steps useful).

The model button may be enabled by default (`SIGNAL_DIAG_EXPLAIN_MODEL=enabled`
in the deployment) only when both conditions hold:

- `summary.json` shows `validation_pass_rate` ≥ 0.9;
- the operator marks no wrong statement in `review.md`.

Otherwise the template stays the only default. Commit the output directory
with a short report of the result, and record the decision as an amendment to
D055.
