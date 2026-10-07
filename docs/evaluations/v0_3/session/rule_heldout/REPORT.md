# D060 phase A: rule-policy acceptance on the held-out session scenarios

## Run identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-10-07 14:22–14:23 |
| Base | `main` @ `abf02f3` (#98) with the held-out file from #97 |
| Policy | `session-rules-1.0` (`app/test_session.py`, `test-session-1.0`) |
| Scenarios | `docs/evaluations/v0_3/session/heldout/session_cases_heldout.json`, SHA-256 `669ee1098562a624942076d9c0341eabd83c436bd2bfb31200f20d48a2620ba9`, copied byte for byte to `evaluation/assets/session_cases_heldout.json` |
| Command | `python -m signal_diag.app.session_eval --cases heldout --out docs/evaluations/v0_3/session/rule_heldout` |
| Model calls | 0 |

The scenarios were written by Cursor from the format, device and condition
types and the distribution, without the rule policy (D060 item 5A), and frozen
in #97 before this run. The rule policy was not changed after the file was
seen; this is its only run on the set.

## Result

| Metric | Value | Bar |
| --- | --- | --- |
| Final correctness | **1.0** (20/20) | ≥ 0.9 |
| Mean rounds | 2.1 | — |
| Extra rounds (over each scenario's minimum) | 2 | — |
| Statuses | resolved 18, budget_exhausted 1, blocked_by_user 1 | — |

**The rule policy meets the bar and becomes the default policy for test
sessions (D060 3A).**

The two extra rounds:

- `h07` (clean device, maximum +9 dB): the first full-scale result at +6 dB
  was confirmed by checking the recorder's gain before it counted, one round
  more than the minimum.
- `h17` (wrong stimulus): the wrong file also failed the whole-stimulus check,
  so both fixes were tried before a valid result, one round more.

## What this means for phase B

On these 20 scenarios the rule policy is already at 100 % correctness and
0.1 rounds above the minimum on average. Under D060 3A a model policy must be
clearly better (+5 points correctness or −0.5 rounds), which is not possible
on scenarios of this kind. The sandbox's users answer fixed fields only; the
place where a model could still help is free-text replies and constraints
("I can only use a microphone, at most −3 dB"), which phase A does not model.
Whether to pursue phase B in that form is an operator decision (a D060
amendment), not part of this acceptance.

## Files

- `summary.json`: the numbers above.
- `results.jsonl`: one row per scenario, with each step (action, answer or
  per-level result) and the session summary.
