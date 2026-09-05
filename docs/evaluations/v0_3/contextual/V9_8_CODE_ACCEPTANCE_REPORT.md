# V9.8 Claim-Reference Recovery Code Acceptance

**Date:** 2026-09-05
**Branch:** `codex/v0.2-real-world-validation`
**Baseline HEAD:** `da3d4eca3be83a57381936b2121d27d42353fda8`
**Result:** `v9_8_harness_complete`

This is a code/offline-harness conclusion only. No real model was run and no
validation asset was accessed. It does not establish `development_confirmed`
or measured performance improvement.

## Scope implemented

- Added prompt `v0.3-s1-planner-9.8` and causal policy
  `v9_8_claim_reference_recovery`.
- Inherited v9.7 mode routing, automatic Tool-to-profile closure, manual
  `evaluate_rules` rejection, causal gates, and retry limits.
- For nominal single-tone harmonic positives, one claim must cite contextual
  validity PASS, F0 compatibility PASS, even-order series Evidence, nominal
  THD FAIL, and the `test_thd_percent` Evidence evaluated by that FAIL rule.
- A v9.8 rejection reports all current nominal-harmonic citation deficits with
  available same-run IDs. The runtime does not insert references into a claim.
- Added T-CX186–T-CX190 and two audit-found boundary regressions: an actual
  signal/context ID match in the runtime inheritance test, and fail-closed
  behavior when the Evidence inventory is absent.

## Frozen identities

| Identity | SHA-256 |
|---|---|
| v9.7 prompt (preserved) | `fc50d82fc7b5701388f5d35c7f50a157ed1c88f050e6057cd8f11caf280b982a` |
| v9.8 prompt | `6d7e18dae4bc1b7e19e3430a9266e7d2c10496df194d3571390df025c6f7bf41` |
| `profile_s1_distortion` | `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` |
| `profile_s1_contextual_comparison` | `c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58` |

The v9.8 prompt is 24,339 UTF-8 bytes. Historical v9.7 run artifacts, V0.2
official/Demo assets, thresholds, labels, and scoring were not rewritten.

## Verification evidence

| Gate | Result |
|---|---|
| Focused v9.8 + v9.7 + app/preservation regressions | **61 passed** |
| Full pytest | **1386 passed**, 1 existing Pydantic serializer warning |
| Ruff | pass |
| mypy `src` | pass, 97 source files |
| Architecture + preservation | **67 passed** |
| `git diff --check 605c8a8` | pass |

The warning originates from
`tests/evaluation/external/test_manifest.py::test_canonical_json_bytes_rejects_nan`
and is unchanged/non-blocking. No required skip or xfail occurred.

No packaging metadata or package-data boundary changed, so this bounded harness
gate did not repeat the release-only CPython 3.11/3.12 clean-environment matrix.

## Honest next gate

A new append-only 20-slot RealLLMPlanner development confirmation is required
before any performance claim. It requires separate authorization, frozen v9.8
identities, one attempt per slot, no validation access, and no replacement of
the preserved v9.7 `below_target` result.
