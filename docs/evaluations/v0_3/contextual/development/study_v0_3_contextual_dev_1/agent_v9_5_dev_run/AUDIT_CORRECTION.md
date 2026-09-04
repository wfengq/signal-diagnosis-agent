# Task 13 audit correction (read-only; awaiting review)

**target_status:** `below_target`
**protocol_deviation:** `true`
**development_confirmation_valid:** `false`

No model re-run. No product-code change. No validation access. Not committed.

## Dual real-model consumption for `825a759a0ea47bb7`

This case received **two** distinct `RealLLMPlanner` slot executions:

| Attempt | Directory | started_at_utc | finished_at_utc | decide_count | status |
|---|---|---|---|---|---|
| 1 | `agent_v9_5_dev_run_partial_aborted_misclassified_infra_2026-09-04/cases/825a759a0ea47bb7/` | `2026-09-04T13:23:16.112818+00:00` | `2026-09-04T13:23:31.113410+00:00` | 6 | `error` |
| 2 | `agent_v9_5_dev_run/cases/825a759a0ea47bb7/` | `2026-09-04T13:24:19.160640+00:00` | `2026-09-04T13:24:34.351729+00:00` | 6 | `error` (`max_planner_retries`) |

Both attempts are preserved. Neither directory was deleted or overwritten.

**Correction:** Prior wording that this case was “not retried” was **false**. Re-executing the case after the partial abort is a **protocol deviation** against the one-shot / no behavioral-retry authorization.

## Current run disposition

| Field | Value |
|---|---|
| `target_status` | `below_target` |
| `protocol_deviation` | `true` |
| `development_confirmation_valid` | `false` |

Reasons `development_confirmation_valid=false`:

1. Protocol deviation: case `825a759a0ea47bb7` consumed two real-model slot attempts across two run directories.
2. Campaign incomplete: stopped after slot 4 infrastructure exception; 16 slots never executed.
3. Fixed-denominator gates therefore cannot support a valid one-shot confirmation claim.

## Metric interpretation (2/17)

`aggregate.outcome_accuracy = 2/17` (and matching causal / grounding numerators) is the
**frozen scoreable denominator gate** (`denominator=17` for all scoreable cases), counting
unexecuted and infrastructure-failed scoreable slots as incorrect under the scoring helper.

It is **not** “accuracy among observed completed samples only.”
Observed completed behavioral/success outcomes in this run tree are a separate descriptive
count and must not be substituted for the 17-denominator gate.

## `APIConnectionError` read-only root-cause audit

**Observed facts only** (from `cases/a4a0853be9983f8c/attempts.json`):

- `error_type`: `APIConnectionError`
- `error_message_sanitized`: `Connection error.`
- wall time ~9.6 s between attempt start and finish
- no HTTP status, response body, DNS log, proxy log, or provider incident ID in artifacts

**root_cause:** `unknown`
Insufficient evidence to attribute network path, provider outage, client TLS, rate limit,
or local environment. No speculation recorded.

## Preserved trees

- `agent_v9_5_dev_run/` — current incomplete campaign + this correction
- `agent_v9_5_dev_run_partial_aborted_misclassified_infra_2026-09-04/` — first abort (misclassified behavioral stop)

## Subsequent options (require separate human decision)

### Option A — Close Task 13

Keep both directories as failure / deviation evidence. Do not resume slots.
Do not claim development confirmation.

### Option B — Diagnostic continuation (new written authorization required)

If newly authorized in writing: execute **only the remaining 16 never-run slots** as a
**diagnostic continuation**.

Hard constraints if Option B is chosen:

- do **not** re-run any of the four already-executed cases in `agent_v9_5_dev_run`
- do **not** treat continuation results as repairing the original one-shot confirmation
- original Task 13 one-shot confirmation remains `development_confirmation_valid=false`
- continuation artifacts must be labeled diagnostic and kept append-only relative to this failure evidence
