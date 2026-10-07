# Test guide acceptance run (D057 4A, D059): instructions for the live run

Run this from the repository root on the merged branch. Never commit or print
the API key. `live_1` (prompt 1.0) is recorded and must not be rewritten. The
next run is `live_2`, with prompt `v0.3-s1-guide-1.1`, on both scenario sets:

```bash
python -m signal_diag.app.guide_eval --cases heldout --out /tmp/guide_heldout_offline  # expect cases 20, model_calls 0, accuracy 1.0
python -m signal_diag.app.guide_eval --cases dev --out /tmp/guide_dev_offline          # expect cases 40, model_calls 0, accuracy 1.0
python -m signal_diag.app.guide_eval --live --cases heldout \
  --out docs/evaluations/v0_3/guide/live_2_heldout
python -m signal_diag.app.guide_eval --live --cases dev \
  --out docs/evaluations/v0_3/guide/live_2_dev
```

Each `summary.json` gives `case_set`, `prompt_version`, `plan_accuracy`,
`parameter_accuracy`, `number_rejections`, `fallback_reasons`,
`rejection_details`, `by_expected_plan`, `unnecessary_question_cases` and
`meets_bar`. `results.jsonl` holds each draft and, for a rejected model
output, `rejection_detail` and `rejected_draft`.

The held-out set decides (D059 3A): the model draft may be enabled by default
(`SIGNAL_DIAG_GUIDE_MODEL=enabled`) only when the held-out run has plan
accuracy ≥ 0.9, parameter accuracy ≥ 0.9 and `number_rejections` = 0. The
development run is reported for comparison with `live_1`.

Commit both output directories with a short report (no trailing whitespace),
and record the decision as an amendment to D057/D059. Do not change the
scenarios, the prompt or the bars after seeing the results.
