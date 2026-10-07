# Explanation acceptance run (D055 4A, D058): instructions for the live run

Run this from the repository root on the merged branch. It calls the real model
50 times, once per case. Do not commit the API key, and do not paste it into
any output file.

`live_1` (validator 1.0) is recorded and must not be rewritten. The next run is
`live_2`, with validator `explain-validator-1.1` (D058):

```bash
export DEEPSEEK_API_KEY=...        # stays in the environment only
python -m signal_diag.app.explanation_eval --live \
  --out docs/evaluations/v0_3/explanation/live_2
```

The run writes three files:

- `summary.json`: `model_calls` (expected 50), `validation_pass_rate`,
  `fallback_reasons`, `rejection_details`, `validator_version`,
  `claims_covered` and `steps_on_menu`;
- `results.jsonl`: one row per case, including the draft that was shown and,
  for a rejected model output, `rejection_detail` and `rejected_draft`;
- `review.md`: 20 seeded samples for the operator to score (readable, wrong
  statement, next steps useful).

Before committing, scan all three files for key material.

The model button may be enabled by default (`SIGNAL_DIAG_EXPLAIN_MODEL=enabled`
in the deployment) only when both conditions hold:

- `summary.json` shows `validation_pass_rate` ≥ 0.9;
- the operator marks no wrong statement in `review.md`.

Otherwise the template stays the only default. Commit the output directory
with a short report of the result, listing each rejection's detail. Record the
decision as an amendment to D055/D058.
