# Regression workbench offline acceptance (Phase A)

Status: Phase A Tasks 1–4 + Task 9 closeout evidence (measurement + compare only).
Product comparison profiles enabled in production: **0**.
User-benefit and RealLLM retest claims: **unverified**.
Commit/push/draft PR authorized for Codex review. Merge/seal/RealLLM remain gated.

## Baseline

- Plan read-only baseline: `4b45f73997a3da89b19eb00846231c6bc84a7709`
- Branch tip at handoff import: `1f42677` (docs-only)
- Implementation commit: `0de53a269ff6fe0fed5f53dd90f15f4f3a22c3f3` on `cursor/s1-regression-workbench-impl-8b52`
- Authority: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §22, D042, design/plan documents
- Spec SHA256: `536b71ddb6e5f3b3369fa49a1aa4e7ad5471497d88b89977822600fa9a990fe4`
- Plan SHA256: `225e0ddfbd49281a1dd210726985db773b1e503b5133de90cb9ec8128bbd1b84`

## Scope covered in Phase A

| Layer | Covered | Notes |
|---|---|---|
| Definition (§22, T-CX329–348, D042) | Yes | Task 1 registration |
| Unit: `regression_measurement` | Yes | `tests/tools/test_regression_measurement.py` |
| Unit: `rules/regression` | Yes | `tests/rules/test_regression.py` + fixtures |
| Real-tool integration (PCM → load → measure → compare) | Yes | `tests/evaluation/test_regression_measurement_acceptance.py` |
| Architecture allowlist / identity tip | Yes (local) | exact paths + `d042_regression_workbench_phase_a` tip |
| App case service / Web UI / retest planner | **Not yet** | Tasks 5–8 |

## Product profile posture

- Approved product `ComparisonProfile` count under `src/signal_diag/rules/profiles`: **0**
- Fixture tolerances live only under `tests/rules/regression_fixtures.py` (e.g. clipping ratio ±0.001 for comparator mechanics). These are **not** product tolerances.

## AC / T-CX mapping (Phase A)

| Design AC | T-CX (plan) | Phase A evidence |
|---|---|---|
| AC01 same output | T-CX330 / T-CX332 | Acceptance identical sine + fixture profile no regression |
| AC02 tolerance boundary | T-CX332 | `test_fixture_profile_boundary` (fixture profile only) |
| AC03 added clipping | T-CX330 / T-CX335 | Acceptance added clipping + fixture regression |
| AC04 both clipped facts preserved | T-CX335 | `test_existing_fault_and_partial_coverage_are_preserved`, acceptance both clipped |
| AC05 input mismatch | T-CX331 | Range/channel/config negative tests in Task 2–3 |
| AC06 harmonic N/A | T-CX330 / T-CX331 | `test_invalid_harmonic_is_not_zero`, acceptance noise case |
| AC07 no profile descriptive | T-CX333 | `test_no_profile_is_descriptive`, acceptance descriptive path |
| AC08 instability declarations | T-CX329 | Declaration blocking in `compare_measurements` |
| AC10 partial coverage | T-CX335 | Coverage entries + overall pass blocked |
| AC11 reference integrity | T-CX334 | `validate_comparison_record` + admission parametrization |
| AC12 numeric/type | T-CX331 / T-CX332 | Relative denominator, bool/int rejection |
| AC16 frozen behavior | T-CX345 / T-CX346 | No changes to frozen V0.2 §§1–64; additive modules only |

Not covered in Phase A (later tasks): AC09, AC13–AC15 (case lifecycle, Web, planner), full T-CX336–348 product surfaces.

## Commands and results (measured)

| Command | Result |
|---|---|
| `python3 -m pytest tests/evaluation/test_regression_measurement_acceptance.py tests/tools/test_regression_measurement.py tests/rules/test_regression.py -q` | **22 passed** |
| `python3 -m pytest tests/agent/test_v03_prompt_v9_11.py tests/test_architecture_boundaries.py -q` (with focused suite) | **88 passed** combined with Phase A tests |
| `python3 -m ruff check .` | **All checks passed** |
| `python3 -m mypy src` | **Success** (after ToolName annotation fix) |
| `git diff --check 4b45f73997a3da89b19eb00846231c6bc84a7709` | **clean** |
| `python3 -m pytest -q` (full, after commit `0de53a2`) | **1841 passed**, 1 warning |
| Wheel / CPython matrix | **not executed** (not a release gate this round) |

## Identity (append-only)

- Amendment id: `d042_regression_workbench_phase_a`
- `current_implementation_sha256` unchanged: `9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3`
- Tip `product_tree_sha256`: `5d76201f9c6eaca3f0d3701510e44c46420cc28987453218ae816c04e16705a3`
- Prompt / causal policy unchanged (`v0.3-s1-planner-9.11` / `v9_11_mode_aware_no_fault_recovery`)
- `model_calls`: **0**
- New modules are **not** Phase 4.3.1-certified by this bridge; they are additive identity accounting only.

## Allowlist (T285 exact paths added)

- `src/signal_diag/tools/regression_measurement.py`
- `src/signal_diag/rules/regression.py`

Note: T285 inspects `baseline..HEAD` committed paths. Uncommitted new files do not yet appear in that diff; allowlist is prepared for a later authorized commit.

## Data shapes

- **MeasurementBundle**: `InputIdentity` + paired `ToolResult` clipping/harmonic + `measurement_version` + canonical JSON digest (excludes digest field).
- **ComparisonRecord**: both bundles, `ComparisonConditions`, optional `applied_profile`, per-metric `MetricComparison` rows, `coverage` / `clipping_facts`, optional `overall_regression_pass`, digest.

## Open / not verified / blocked gates

- Product tolerance calibration and approved comparison profiles
- Retest planner (`v0.3-s1-retest-1.0`) and RealLLM runs
- User time savings or planner benefit studies
- Tasks 5–8 (not granted)
- Merge, seal, RealLLM, product tolerances
