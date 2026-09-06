# V9.11 Offline TDD and Replay Report

## Status

`v9_11_offline_tdd_replay_complete`

This is a code and deterministic replay result only. It is not a real-model
development confirmation, validation result, final-test result, or performance
improvement claim.

## Identity

- base HEAD: `a1c414af72fb9c6b8b2ddaf31c4a8e92398d8537`
- prompt: `v0.3-s1-planner-9.11`
- prompt SHA-256: `ecd10554beef79afcf505bf788509f660eb933eaef72ed89693514009fe1134b`
- causal policy: `v9_11_mode_aware_no_fault_recovery`
- contextual implementation SHA-256: `1dfc498e30bb5139eef2f8340aad2e2f3ea2aef5ceb51a633e040bf736065d42`
- product tree SHA-256: `626824f6bd2c4c04da566d77914648f2e2d629241d910cb56bcd086bd279c799`
- contextual profile: unchanged `profile_s1_contextual_comparison_v9_10` `1.0.0`
- selected contextual growth threshold: unchanged `5.0%`

## Root cause and change

V9.10 always required the contextual `test_clipping_mechanism=false` family
for no-fault finishes. That requirement is unavailable in single-signal mode.
For paired natural-even controls, the required IDs existed but rejection
messages did not enumerate them together, so three planner retries repeated the
same incomplete finish.

V9.11 selects the legacy clipping clean family for `single_signal` and the
test-side contextual clean family for `paired_reference` and
`nominal_single_tone`. A rejection reports every missing requirement together
with each available same-run Evidence or rule-evaluation ID. Runtime still does
not author or rewrite claims.

## TDD and replay evidence

- Initial fixture error was corrected before accepting RED evidence.
- Correct RED: 3 failed and 1 preserved-v9.10 test passed because v9.11 was not
  registered and incomplete evidence families were accepted.
- No-fault GREEN: 4 passed.
- Prompt/product RED: 2 failed and 1 v9.10 preservation test passed.
- Prompt/product GREEN plus replay focused gate: 11 passed.
- Pre-commit Bugbot review found and the implementation subsequently closed
  three gaps: outcome/claim-type coherence, the contradictory inherited prompt
  checklist, and empty-reference complete-deficit recovery. Three regression
  tests observed the defects before the fixes; the final focused gate is
  `13 passed`.
- Replay uses only retained `result.json` Evidence and rule evaluations for
  cases `393940e92c58cf0b`, `04f4068ec91d2621`, and `eabaecd422b2eeda`.
- Replay result: 3/3 incomplete finishes rejected with ID-bearing deficits;
  3/3 corrected complete finishes accepted.
- No WAV was opened by the replay and no provider was called.

## Cumulative offline gates

- full pytest: `1491 passed`, `1 warning`
- Ruff: passed
- mypy `src`: passed for 100 source files
- architecture plus preservation: `73 passed`
- `git diff --check 605c8a8`: passed
- wheel smoke: passed

The existing Pydantic serializer warning in
`test_canonical_json_bytes_rejects_nan` remains unchanged and is not associated
with v9.11.

## Explicit exclusions

- no real-model call;
- no validation or final-test access;
- no threshold, profile, DSP, Tool, WAV, dataset, label, scoring, or retry-budget
  change;
- no historical run rewrite;
- no commit or push in this implementation step.
