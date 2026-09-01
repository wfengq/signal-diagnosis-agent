# Signal Diagnosis Agent — External Validation Test Plan V0.2

**Document:** `EXTERNAL_VALIDATION_TEST_PLAN_V0_2.md`  
**Version:** `external-validation-0.2`  
**Status:** Approved for Phase A protocol freeze on branch
`codex/v0.2-real-world-validation`  
**Scope:** Deterministic external WAV validity study acceptance  
**Contracts:** `docs/EXTERNAL_VALIDATION_CONTRACTS_V0_2.md`  
**Design:** `docs/superpowers/specs/2026-09-01-v0-2-real-world-validation-design.md`  
**Frozen product contracts:** `docs/CONTRACTS_V0_2.md`, `docs/TEST_PLAN_V0_2.md`

---

## 1. Purpose

This plan verifies the additive external WAV validity study in isolation from
required V0.2 product acceptance. It proves:

1. accepted V0.2 historical assets remain unchanged;
2. external study models, manifests, derivation, transforms, review, sealing,
   scoring, runner, and reporting behave deterministically;
3. network access, real-model calls, and `ScriptedPlanner` fallback remain
   explicitly gated outside ordinary pytest.

Required external tests follow the same principles as `TEST_PLAN_V0_2.md`:

- test behavior through public interfaces;
- use explicit seeds for random inputs;
- never mock numerical DSP results in external reference acceptance;
- keep real LLM calls out of required pytest;
- verify tests fail for the intended reason before implementing behavior;
- do not use `skip` or `xfail` on required EV-T001–EV-T048 tests once
  implemented.

---

## 2. Test Layout

```text
tests/evaluation/external/
├── conftest.py
├── test_preservation.py
├── test_models.py
├── test_manifest.py
├── test_source.py
├── test_pcm.py
├── test_transforms.py
├── test_reference.py
├── test_validation.py
├── test_review.py
├── test_sealing.py
├── test_scoring.py
├── test_runner.py
├── test_reporting.py
└── test_cli.py
```

Phase A implements only `test_preservation.py`. Later tasks add the remaining
modules under test-driven development.

---

## 3. Checkpoints

| Checkpoint | Scope | Required IDs |
|---|---|---|
| A | Preservation, architecture, and protocol freeze | EV-T001–EV-T004 |
| B | Immutable external models and manifests | EV-T005–EV-T010 |
| C | Bounded source acquisition | EV-T011–EV-T014 |
| D | PCM derivation and loader compatibility | EV-T015–EV-T020 |
| E | Transforms and pairing | EV-T021–EV-T026 |
| F | Reference analysis | EV-T027–EV-T030 |
| G | Grouping, confidence, and final sealing | EV-T031–EV-T035 |
| H | Delayed blind review | EV-T036–EV-T039 |
| I | Scoring and stratification | EV-T040–EV-T043 |
| J | Agent/fixed execution and no fallback | EV-T044–EV-T046 |
| K | Append-only reporting and cumulative gate | EV-T047–EV-T048 |

---

## 4. Checkpoint A — Preservation and Architecture

| ID | Behavior | Required result |
|---|---|---|
| EV-T001 | Protected V0.2 asset checksum audit | every record in `protected_assets.sha256` matches current repo bytes or frozen Git tag/commit hashes |
| EV-T002 | External package dependency direction | `signal_diag.evaluation.external` does not depend on `app/`; lower layers do not depend on external study modules |
| EV-T003 | No protected drift after external work | `git diff --check 605c8a8` reports no changes under EV-C001 protected directories or EV-C002 identity files |
| EV-T004 | Preservation audit rejects malformed records | duplicate paths, absolute paths, `..`, missing files, hash mismatches, and out-of-repo paths raise clear errors |

Checkpoint A acceptance command:

```bash
pytest tests/evaluation/external/test_preservation.py -v
git diff --check 605c8a8
```

---

## 5. Checkpoint B — Immutable Model and Manifest Validation

| ID | Behavior | Required result |
|---|---|---|
| EV-T005 | External case extra-forbid and UTC timestamps | invalid extra fields fail; timestamps are timezone-aware UTC |
| EV-T006 | Weak/unknown cases forbid scoring truth | `weak_observation` and `unknown` reject causal faults and acceptable outcomes used for correctness |
| EV-T007 | Strong ground truth requires transform provenance | degraded B cases without transform metadata fail validation |
| EV-T008 | Truth-free analysis filenames | only `extwav_(development\|validation\|final_external_test)_[0-9a-f]{16}.wav` pass |
| EV-T009 | Canonical manifest identity | only frozen dataset/study/scoring identities deserialize |
| EV-T010 | Manifest fingerprint stability | sorted-key canonical JSON bytes produce stable SHA-256 |

---

## 6. Checkpoint C — Bounded Source Acquisition

| ID | Behavior | Required result |
|---|---|---|
| EV-T011 | Network is opt-in | `acquire_assets(..., allow_network=False)` raises `PermissionError` mentioning `--allow-network` |
| EV-T012 | Partial or oversize download is removed | aborted downloads leave destination empty |
| EV-T013 | Approved host policy | only frozen authoritative hosts pass catalog validation |
| EV-T014 | Existing digest/path is not overwritten | duplicate acquisition attempts fail without mutation |

---

## 7. Checkpoint D — PCM Derivation and WAV Loader Compatibility

| ID | Behavior | Required result |
|---|---|---|
| EV-T015 | 8/16/24/32-bit signed PCM conversion | full-scale integer PCM maps to expected float32 amplitudes without peak normalization |
| EV-T016 | Selected channel extraction | predeclared channel index returns the correct channel only |
| EV-T017 | Left-closed/right-open frame crop | crop boundaries match the frozen derivation spec |
| EV-T018 | Derived PCM24 loads without peak normalization | `load_wav_bytes` accepts output and preserves amplitudes within 24-bit roundoff |
| EV-T019 | Output bounds enforcement | crops beyond 30 s, 2,000,000 frames, or 20 MiB fail explicitly |
| EV-T020 | Immutable destination semantics | existing derived WAV paths are not overwritten |

---

## 8. Checkpoint E — Transforms and Pairing

| ID | Behavior | Required result |
|---|---|---|
| EV-T021 | Hard clipping quantile method | tail proportion maps to deterministic threshold `T` |
| EV-T022 | Second-harmonic formula | output matches frozen even-order nonlinearity identity |
| EV-T023 | Combined order is harmonic then clipping | combined output equals clip(harmonic(base)) |
| EV-T024 | Transforms do not normalize each master | lower-amplitude masters remain lower after identical parameters |
| EV-T025 | Four-variant B family completeness | each master yields clean, clipping, harmonic, and combined variants |
| EV-T026 | Transform digests are reproducible | identical inputs/parameters produce identical output digests |

---

## 9. Checkpoint F — Reference Analysis

| ID | Behavior | Required result |
|---|---|---|
| EV-T027 | Reference analyzer identity | reports stamp `signal_diag.external_reference` `1.0.0` |
| EV-T028 | Clean periodic fixture | valid F0, THD, and no flat-top/clipping flags on canonical sine |
| EV-T029 | Clipped and harmonic fixtures | clipping ratio, flat-top status, order-2 ratio, and THD match deterministic expectations |
| EV-T030 | Architecture isolation | reference module imports no Agent, planner, runner, scoring, or reporting code |

---

## 10. Checkpoint G — Grouping, Confidence, and Final Sealing

| ID | Behavior | Required result |
|---|---|---|
| EV-T031 | Planned split counts | whole study 14/10/28 and A/B/C 12/28/12 are enforced at final preflight |
| EV-T032 | Seven complete B families | four variants per master; missing variant fails the family |
| EV-T033 | Parent family cannot cross splits | parent/child lineage leakage is reported and blocks sealing |
| EV-T034 | Confidence distributions | whole 21/23/4/4 and final 12/12/2/2 distributions are validated at seal time |
| EV-T035 | Final seal is write-once | existing destination or run output blocks `seal_final_external_test` |

---

## 11. Checkpoint H — Delayed Blind Review

| ID | Behavior | Required result |
|---|---|---|
| EV-T036 | Blind package excludes truth and source fields | forbidden tokens such as source names, transforms, and split labels are absent |
| EV-T037 | Round 2 before fourteen days is rejected | review scoring enforces 14 complete-day delay |
| EV-T038 | Disagreement never upgrades confidence | unresolved disagreement downgrades to weak or unknown except transform-proven strong B labels |
| EV-T039 | Agreement statistics | raw outcome agreement and Cohen kappa values match deterministic fixtures; undefined kappa returns `None` with reason |

---

## 12. Checkpoint I — Scoring and Stratification

| ID | Behavior | Required result |
|---|---|---|
| EV-T040 | Unknown case has no correctness boolean | outcome and causal exact-set correctness are `None`; positive causal claims are counted separately |
| EV-T041 | Grounding is same-run even for unscored case | foreign Evidence references fail grounding regardless of confidence |
| EV-T042 | External scoring identity | scores stamp `signal_diag.external_scoring` `1.0.0` and do not mutate historical `signal_diag.scoring` `2.0.0` |
| EV-T043 | Stratified aggregates | path, A/B/C, confidence, class, source, and parent-master strata expose numerator/denominator/exclusions |

---

## 13. Checkpoint J — Agent/Fixed Execution and No Fallback

| ID | Behavior | Required result |
|---|---|---|
| EV-T044 | Shared WAV materialization | Agent and fixed paths load identical opaque signal bytes and digests |
| EV-T045 | Provider failure consumes slot without fallback | one infrastructure failure yields one attempt, no trace reuse, and no `ScriptedPlanner` construction |
| EV-T046 | Real-model gate is explicit | `run_external_agent` without authorization or credentials fails before provider construction |

---

## 14. Checkpoint K — Append-Only Reporting and Cumulative Gate

| ID | Behavior | Required result |
|---|---|---|
| EV-T047 | Append-only bundle verification | required files, sorted checksums, redaction rules, and destination-exists rejection pass deterministically |
| EV-T048 | Cumulative external gate | full pytest, Ruff, mypy, architecture tests, preservation audit, and `git diff --check 605c8a8` pass with zero required skip/xfail |

Cumulative gate command after full implementation:

```bash
pytest -v
ruff check .
mypy src tests
pytest tests/test_architecture_boundaries.py -v
pytest tests/evaluation/external/test_preservation.py -v
git diff --check 605c8a8
```

Real-model external behavior remains a separately recorded non-CI gate.

---

## 15. Relationship to Frozen V0.2 Test Plan

EV-T IDs are additive. They do not replace, weaken, or reinterpret required
T001–T285 product tests. External study tests must keep passing the full
historical suite at the cumulative gate.
