# Test guide acceptance run (D057 4A): instructions for the live run

Run this from the repository root on the merged branch. It calls the real model
40 times, once per authored scenario. Never commit or print the API key.

```bash
python -m signal_diag.app.guide_eval --out /tmp/guide_offline   # expect cases 40, model_calls 0
python -m signal_diag.app.guide_eval --live \
  --out docs/evaluations/v0_3/guide/live_1
```

`summary.json` gives:

- `plan_accuracy` and `parameter_accuracy`;
- `number_rejections`;
- `fallback_reasons`;
- `by_expected_plan`;
- `unnecessary_question_cases`;
- `meets_bar`.

`results.jsonl` holds each draft. The model draft may be enabled by default
(`SIGNAL_DIAG_GUIDE_MODEL=enabled`) only when plan accuracy ≥ 0.9, parameter
accuracy ≥ 0.9 and `number_rejections` = 0. Otherwise the questionnaire stays
the only default.

Commit the output directory with a short report, and record the decision as an
amendment to D057. Do not change the scenarios, the prompt or the bars after
seeing the results.
