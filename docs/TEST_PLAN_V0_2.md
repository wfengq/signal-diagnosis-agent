# Signal Diagnosis Agent — Test Plan V0.2

**Document:** `TEST_PLAN_V0_2.md`  
**Version:** `0.2`  
**Status:** Required and accepted through T223 on merged Phase 4.3.1 baseline
`36ae7c9`; Phase 5 §28 T224–T285 approved and frozen under OQ-010 on
2026-08-31; T284–T285 dual-interpreter input amended under OQ-011 / D031 on
2026-08-31
**Scope:** Deterministic and real-model acceptance through Phase 4.3.1, plus
frozen Phase 5 presentation and product-Demo acceptance
**Contracts:** `docs/CONTRACTS_V0_2.md`  
**Architecture:** `docs/ARCHITECTURE_V0_2.md`  

---

## 1. Purpose

This plan verifies three distinct layers:

1. deterministic system and presentation acceptance using real lower-layer
   execution with an explicitly injected `ScriptedPlanner` where Agent behavior
   must be reproducible;
2. real-model behavior evaluation using `RealLLMPlanner`, outside required CI;
3. a non-CI real-model Phase 5 product-integration Demo after deterministic
   presentation acceptance.

The deterministic suite proves contracts, numerical behavior, runtime routing,
state transitions, error handling, termination, and complete reproducible S1
paths. It does not claim that a real model will always make a good decision.

The real-model evaluation measures model behavior and records stochastic
variation. The product Demo verifies the public service/UI/report path but does
not replace that benchmark. Neither determines whether CI is green.

---

## 2. Test Principles

Required tests follow these rules:

- test behavior through public interfaces;
- use explicit seeds for random inputs;
- use real DSP and Tool implementations in Agent acceptance tests;
- never mock numerical DSP results in S1 acceptance;
- use `ScriptedPlanner` only as the planner test double;
- keep real LLM calls out of `pytest` required acceptance;
- do not weaken scientific requirements to make tests pass;
- do not use `skip` or `xfail` on required T001–T092 tests;
- do not use `skip` or `xfail` on required T093–T124 tests at the Phase 3
  completion gate; package-absence skips are allowed only during incremental
  pre-implementation migration;
- verify tests fail for the intended reason before implementing behavior;
- run focused tests and the full current suite after every logical unit.

---

## 3. Test Layout

```text
tests/
├── signal/
│   ├── test_factory.py
│   ├── test_repository.py
│   ├── test_segment.py
│   └── test_synthetic.py
├── dsp/
│   ├── test_preprocess.py
│   ├── test_clipping.py
│   ├── test_spectrum.py
│   ├── test_pitch.py
│   └── test_harmonics.py
├── tools/
│   ├── test_contracts.py
│   ├── test_evidence.py
│   └── test_service.py
└── agent/
    ├── test_models.py
    ├── test_scripted_planner.py
    ├── test_runtime.py
    ├── test_termination.py
    └── test_s1_acceptance.py
├── test_architecture_boundaries.py   # T093; Phase 3 gate migration
├── rules/                            # Phase 3
│   ├── test_models.py
│   └── test_engine.py
└── knowledge/                        # Phase 3
    ├── test_models.py
    └── test_index.py
```

Real-model evaluation is not stored as a required pytest module. Its Phase 2
entry point is invoked explicitly through the development runner or a dedicated
evaluation command introduced with the real adapter.

---

## 4. Numerical Tolerances

```python
FLOAT_ABS_TOL = 1e-6
AMPLITUDE_ABS_TOL = 1e-4
FREQ_ABS_TOL_HZ = 1.0
THD_ABS_TOL_PERCENT = 0.5
NOISE_RMS_REL_TOL = 0.03
```

These tolerances apply to the specified deterministic fixtures. A looser
tolerance requires a documented algorithmic reason and contract review.

F0 confidence is an uncalibrated quality score, not a probability.

---

## 5. Canonical Fixtures

### 5.1 Clean sine

```python
generate_sine(
    frequency_hz=200.0,
    sample_rate_hz=48_000,
    duration_s=2.0,
    amplitude=0.5,
)
```

### 5.2 Sub-full-scale clipped sine

```python
generate_clipped_sine(
    frequency_hz=200.0,
    sample_rate_hz=48_000,
    duration_s=2.0,
    amplitude=0.9,
    clip_level=0.5,
)
```

### 5.3 Full-scale clipped sine

```python
generate_clipped_sine(
    frequency_hz=200.0,
    sample_rate_hz=48_000,
    duration_s=2.0,
    amplitude=1.2,
    clip_level=1.0,
)
```

### 5.4 Harmonic-distortion signal

```python
generate_harmonic_sine(
    fundamental_hz=200.0,
    harmonic_ratios={2: 0.10, 3: 0.05},
    sample_rate_hz=48_000,
    duration_s=2.0,
    fundamental_amplitude=0.5,
)
```

Expected theoretical THD:

```text
100 * sqrt(0.10² + 0.05²) = 11.180339... percent
```

### 5.5 Combined fault

```python
generate_combined_distortion(
    fundamental_hz=200.0,
    harmonic_ratios={2: 0.10, 3: 0.05},
    clip_level=0.5,
    sample_rate_hz=48_000,
    duration_s=2.0,
    fundamental_amplitude=0.9,
)
```

### 5.6 Seeded noise

```python
generate_white_noise(
    sample_rate_hz=48_000,
    duration_s=2.0,
    rms=0.1,
    seed=1234,
)
```

---

## 6. Checkpoints

| Checkpoint | Scope | Required IDs |
|---|---|---|
| A | Signal models, factory, repository, segment, synthetic | T001–T024 |
| B | Deterministic DSP | T025–T052 |
| C | Tool, Observation-ready output, Evidence | T053–T063 |
| D | Agent contracts and scripted planner | T064–T070 |
| E | Runtime routing and termination | T071–T085 |
| F | Reproducible S1 state-machine acceptance | T086–T092 |
| G | Phase 3 rules, knowledge, runtime integration | T093–T124 |

Each checkpoint requires its focused tests and the complete suite accumulated so
far.

OQ-001 approval on 2026-08-28 authorizes Phase 3 checkpoint G. T093 updates the
architecture boundary gate; remaining T094–T124 are added during Phase 3
implementation.

---

## 7. Checkpoint A — Signal Foundation

### Factory

| ID | Behavior | Required result |
|---|---|---|
| T001 | Mono canonicalization | `(N,)` becomes contiguous `(N,1)` `float32` |
| T002 | Floating amplitude preservation | peak `0.5` remains `0.5`; no peak normalization |
| T003 | Signed int16 full-scale conversion | `-32768 → -1.0`, `32767 → 32767/32768` |
| T004 | Invalid signal rejection | empty, NaN, Inf, wrong rank, and non-positive sample rate fail explicitly |
| T005 | Unsigned PCM rejection | unsigned integer input raises `InvalidSignalError` |
| T006 | Metadata/record invariants and ID | derived fields and `sig_` ID are correct; inconsistent direct metadata/record construction fails |

T001–T003 preserve the essential V0.1 numerical behavior. T005 removes ambiguity
instead of guessing an unsigned PCM offset convention.

### Repository

| ID | Behavior | Required result |
|---|---|---|
| T007 | Put/Get integrity | samples and immutable metadata are preserved |
| T008 | Source ownership | mutating the caller array/record after `put()` cannot change storage |
| T009 | Strong snapshot immutability | direct mutation fails and flag manipulation cannot mutate internal storage |
| T010 | Missing ID | `get` and `remove` raise; `exists` returns `False` |
| T011 | Replace/list/remove | replacement is atomic, insertion order is stable, metadata only is listed |

T009 must check more than `writeable is False`. If a returned array can have its
flag re-enabled, mutation of that returned object must still leave a later
`repo.get()` unchanged.

### Segment and channels

| ID | Behavior | Required result |
|---|---|---|
| T012 | `[1.0,2.0)` extraction | exactly 48,000 samples at 48 kHz and correct reference slice |
| T013 | End clamp | an end beyond duration clamps to record end |
| T014 | Invalid ranges | reversed, empty, or start-at/after-end ranges raise `InvalidTimeRangeError` |
| T015 | Mono channel semantics | `left`/`mixdown` return mono; `right` raises |
| T016 | Stereo selection/mixdown | left, right, and arithmetic mean are numerically correct writable copies |

### Synthetic generation

| ID | Behavior | Required result |
|---|---|---|
| T017 | Clean 200 Hz sine | length, amplitude, metadata, empty fault labels, and ground truth are correct |
| T018 | Clipped sine | peak equals clip level and fault label is `clipping` |
| T019 | Seed reproducibility | equal noise seeds match exactly; different seeds differ |
| T020 | Noise distribution sanity | mean is near zero and RMS is within 3% for the canonical fixture |
| T021 | Harmonic waveform | 2nd/3rd harmonic amplitudes follow ratios without normalization |
| T022 | Harmonic ground truth | generator, required keys, string-keyed ratios, and `harmonic_distortion` label are correct |
| T023 | Combined fault | clipping is applied after harmonic construction and both labels are present in stable order |
| T024 | Generator validation | invalid duration/rate/frequency/RMS/clip level/order/ratio fail explicitly |

Checkpoint A acceptance command:

```bash
pytest tests/signal -q
```

---

## 8. Checkpoint B — Deterministic DSP

### Preprocessing

| ID | Behavior | Required result |
|---|---|---|
| T025 | DC removal | output mean is approximately zero and input is unchanged |
| T026 | RMS and peak | known arrays produce exact/expected deterministic values |
| T027 | Preprocess validation | empty, non-finite, and non-1D input fail explicitly |

### Clipping

| ID | Behavior | Required result |
|---|---|---|
| T028 | Clean sine | no clipping flags or events |
| T029 | Full-scale clipping | full-scale detection, sample count, and event count are positive |
| T030 | Sub-full-scale flat top | flat-top detection succeeds while full-scale detection is false |
| T031 | Union count | overlapping detection masks do not double-count clipped samples |
| T032 | Validation/mutation safety | invalid input fails; valid input is unchanged after analysis |

Exact event merging is not frozen, but results must be internally consistent:

```text
0 <= clipped_samples <= num_samples
0 <= clipping_ratio <= 1
clipping_ratio == clipped_samples / num_samples
```

### Spectrum

| ID | Behavior | Required result |
|---|---|---|
| T033 | 200 Hz dominant frequency | dominant frequency is within 1 Hz; resolution is 0.5 Hz |
| T034 | DC-offset robustness | DC removal preserves the 200 Hz dominant component |
| T035 | Relative magnitude | strongest finite spectral magnitude is 0 dB |
| T036 | Explicit `n_fft` | larger `n_fft` zero-pads; output length and resolution match real-FFT convention |
| T037 | Silence | no fabricated dominant frequency or centroid; no NaN escapes |
| T038 | Validation/mutation safety | invalid rate/window/length/rank or truncating `n_fft` fails; input is unchanged |

### Fundamental

| ID | Behavior | Required result |
|---|---|---|
| T039 | 200 Hz sine | voiced, `f0≈200 Hz`, method `autocorrelation` |
| T040 | Silence | unvoiced, `f0_hz=None`, finite non-negative confidence |
| T041 | Seeded noise | canonical seed is unvoiced with no numeric F0 |
| T042 | Invalid bounds | non-positive or reversed/equal bounds fail; bounds are not swapped |
| T043 | Mutation safety | input samples are unchanged |

### Harmonic distortion

| ID | Behavior | Required result |
|---|---|---|
| T044 | Known THD | canonical harmonic fixture returns `11.1803% ± 0.5` percentage point |
| T045 | Components | orders 2 and 3 are present, ordered, and frequencies are within 1 Hz |
| T046 | Supplied fundamental | a valid provided 200 Hz fundamental is used consistently |
| T047 | Estimated fundamental | omitted fundamental is estimated and produces valid canonical THD |
| T048 | Silence invalid | `valid=False`, THD/fundamental are `None`, reason is non-empty |
| T049 | Seeded noise invalid | no reliable harmonic metric is fabricated |
| T050 | Nyquist truncation | harmonic orders above Nyquist are omitted deterministically |
| T051 | Validation/mutation safety | invalid parameters fail and input is unchanged |
| T052 | Metric-only boundary | DSP result contains no PASS/FAIL or diagnostic fault label |

Checkpoint B acceptance commands:

```bash
pytest tests/dsp -q
pytest tests/signal tests/dsp -q
```

---

## 9. Checkpoint C — Tools and Evidence

| ID | Behavior | Required result |
|---|---|---|
| T053 | `detect_clipping` success | compact result and deterministic clipping evidence are returned |
| T054 | `analyze_spectrum` compactness | summary is correct and exposes no frequency/magnitude ndarray |
| T055 | `estimate_fundamental` success | voiced sine maps to `success` with F0 evidence |
| T056 | `estimate_fundamental` invalid | noise maps to `invalid`, no fabricated F0, warning present |
| T057 | `analyze_harmonic_distortion` success | valid THD result and fundamental/THD Evidence are returned |
| T058 | `analyze_harmonic_distortion` invalid | silence/noise maps to `invalid` with no numeric THD Evidence |
| T059 | Missing signal | every service method returns `error` with no Evidence |
| T060 | Segment/channel propagation | selected time/channel reaches DSP and changes the compact result as expected |
| T061 | Evidence linkage | unique `ev_` IDs reference the correct `call_`, tool, metric, segment, and channel |
| T062 | ToolResult invariants | success/invalid/error combinations violating Section 17 fail validation |
| T063 | `get_tool_descriptors` | exactly four Phase 1 tools appear with JSON-serializable schemas and no call order |

T054 additionally serializes Tool output and recursively asserts that no value is
an ndarray and no raw sample sequence is present.

Checkpoint C acceptance commands:

```bash
pytest tests/tools -q
pytest tests/signal tests/dsp tests/tools -q
```

---

## 10. Checkpoint D — Agent Contracts and Scripted Planner

| ID | Behavior | Required result |
|---|---|---|
| T064 | `AgentDecision` discrimination | each `ToolInvocation` parses to its matching typed call; invalid names/args fail |
| T065 | PlannerContext compactness | serialization contains metadata/observations only and no ndarray/full FFT arrays |
| T066 | Initial assessment requirement | runtime rejects an initial decision without `TaskAssessment` |
| T067 | Finish semantic validation | supported/no-fault claims require Evidence; inconclusive requires limitation |
| T068 | Script sequence | `ScriptedPlanner` returns decisions in order without producing DSP values |
| T069 | Script context assertions | expected observation count and evidence metrics are checked before returning a step |
| T070 | Script exhaustion | exhausted script raises `ScriptExhaustedError` deterministically |

Checkpoint D acceptance command:

```bash
pytest tests/agent/test_models.py tests/agent/test_scripted_planner.py -q
```

---

## 11. Checkpoint E — Runtime and Termination

| ID | Behavior | Required result |
|---|---|---|
| T071 | `DistortionDiagnosisRuntime` context loading | runtime retrieves only compact metadata before first planner decision |
| T072 | Selected Tool only | a call decision executes exactly the named real Tool, with runtime-injected signal ID |
| T073 | Observation propagation | the next planner context contains the prior Tool status and compact result |
| T074 | Evidence propagation | deterministic Tool Evidence appears unchanged in the next context |
| T075 | Scientific invalid flow | an `invalid` observation is recorded and the planner can legally replan |
| T076 | Tool error flow | an `error` observation contains no Evidence and reaches planner/error policy |
| T077 | Planner retry | a local protocol test double raising `PlannerOutputError` is retried within budget |
| T078 | Retry exhaustion | exhausted planner retries terminate with `max_planner_retries` |
| T079 | Tool-call limit | no Tool executes after `max_tool_calls`; termination is explicit |
| T080 | Equivalent-call rejection | same Tool plus canonical args is rejected even if purpose prose changes |
| T081 | No-progress termination | consecutive rejected/error iterations terminate at configured limit |
| T082 | Valid finish | valid Evidence references produce a successful structured diagnosis |
| T083 | Unknown Evidence reference | diagnosis validation fails and follows retry/termination policy |
| T084 | Unsupported task | initial unsupported assessment finishes with zero Tool calls |
| T085 | No silent fallback | failure from a real-planner protocol double never invokes `ScriptedPlanner` |

T077 uses a test-local object implementing `PlannerModel`; it does not mock DSP.
T085 verifies composition directly by giving the scripted planner a fail-fast
sentinel that would raise if called.

Checkpoint E acceptance commands:

```bash
pytest tests/agent/test_runtime.py tests/agent/test_termination.py -q
pytest -q
```

---

## 12. Checkpoint F — Deterministic S1 Acceptance

These tests use `ScriptedPlanner`, the real repository, real Tool Service, and
real DSP. A script defines one legal dynamic route; it does not freeze the route
that `RealLLMPlanner` must take.

| ID | Case | Required result |
|---|---|---|
| T086 | S1-CLIP-FS | clipping Tool provides sufficient evidence; planner finishes without unrelated calls |
| T087 | S1-CLIP-SUBFS | sub-full-scale flat-top evidence supports clipping diagnosis |
| T088 | S1-HARM after negative evidence | negative clipping observation is propagated, harmonic analysis is then selected, diagnosis cites THD evidence |
| T089 | S1-HARM alternate legal first Tool | runtime accepts a harmonic- or spectrum-first legal route; no hidden fixed order exists |
| T090 | S1-COMBINED | final diagnosis contains clipping and harmonic claims with distinct valid Evidence references |
| T091 | S1-CLEAN | sufficient negative evidence supports `no_supported_fault`; no fault is fabricated |
| T092 | S1-NOISE | invalid fundamental/harmonic evidence leads to justified `inconclusive` and no numeric fabrication |

### Required scripted-path assertions

Every T086–T092 test additionally asserts:

- the first `PlannerContext` contains no observations;
- each later context contains all earlier observations;
- only the Tool named by the scripted decision executes;
- every final Evidence reference exists in the run;
- the terminal reason is explicit;
- call counts equal the actual dynamic route;
- no waveform or full FFT array appears in serialized state or trace.

Checkpoint F acceptance command:

```bash
pytest tests/agent/test_s1_acceptance.py -q
pytest -q
```

---

## 13. Real-Model Behavior Evaluation

Real-model checks are labelled `R001–R006`; they are not pytest acceptance IDs
and never gate CI.

| ID | Measure | Recorded result |
|---|---|---|
| R001 | First-Tool selection | selected Tool, rationale, and whether it is relevant to S1 state |
| R002 | Observation-driven replanning | whether the next action changes appropriately after positive, negative, or invalid evidence |
| R003 | Unnecessary calls | number and identity of calls that add no new relevant evidence |
| R004 | Stopping timing | premature, appropriate, or late relative to available supported evidence |
| R005 | Final diagnosis quality | ground-truth label match, Evidence grounding, unsupported claims, limitations |
| R006 | Execution characteristics | Tool calls, planner calls, latency, model ID, prompt version, token/cost data when available |

### Phase 2 real-model protocol

For the initial product check:

1. run `RealLLMPlanner` explicitly on S1-CLIP-SUBFS, S1-HARM, S1-CLEAN, and
   S1-NOISE;
2. preserve the complete structured trace without waveform arrays;
3. score R001–R006;
4. report individual failures rather than retrying until a favorable example
   appears;
5. record model and prompt configuration;
6. keep the result outside required CI status.

Systematic repeated runs, confidence intervals, the combined-fault evaluation
set, and Agent-versus-fixed-pipeline comparison belong to Phase 4.

If credentials are absent, the command must stop with an explicit configuration
message. It must not silently use `ScriptedPlanner` and must not be represented as
a passed real-model evaluation.

---

## 14. Boundary and Architecture Tests

The following assertions are included in the nearest numbered tests rather than
creating a second untracked acceptance list:

- lower layers do not import `agent`, `rules`, `knowledge`, `evaluation`, or
  `app`;
- `signal` does not import `dsp` or `tools`;
- `dsp` does not import `tools` or `agent`;
- Tool/Agent serialized structures contain no ndarray;
- Agent code does not calculate FFT/F0/THD/clipping metrics;
- Tool input models do not contain `signal_id`;
- no product runtime fallback references `ScriptedPlanner`;
- required deterministic tests perform no network access.

An import-boundary test may inspect package imports mechanically after the
package exists. It supplements behavioral tests and does not replace them.

---

## 15. TDD Execution Order

Implementation proceeds in this order:

```text
T001–T006   factory and models
T007–T011   repository
T012–T016   segment/channels
T017–T024   synthetic generation
T025–T027   preprocessing
T028–T032   clipping
T033–T038   spectrum
T039–T043   fundamental
T044–T052   harmonics/THD
T053–T063   Tool/Evidence
T064–T070   Agent contracts/ScriptedPlanner
T071–T085   runtime/termination
T086–T092   S1 deterministic acceptance
R001–R006   explicit real-model behavior evaluation
```

For each behavior:

1. write the focused test;
2. run it and confirm the expected failure;
3. implement the smallest correct behavior;
4. run the focused test and confirm it passes;
5. run the accumulated checkpoint suite;
6. refactor only while green.

---

## 16. Required Verification Commands

After each checkpoint:

```bash
pytest tests/<checkpoint-area> -q
pytest -q
```

Before declaring Phase 1 or Phase 2 complete:

```bash
pytest -q
```

If configured in the project plan, also run:

```bash
ruff check .
mypy src
```

The exact real-model command is frozen with the selected provider adapter. It is
always separate from `pytest -q`.

---

## 17. Completion Gates

### Phase 1 completion

Phase 1 requires:

- T001–T063 passing;
- no required skip or xfail;
- no warnings that indicate numerical invalidity or array mutation;
- Signal, DSP, Tool, and Evidence contracts unchanged or explicitly revised;
- exact focused and full-suite commands reported.

### Phase 2 deterministic completion

Phase 2 deterministic acceptance requires:

- T064–T092 passing;
- all Phase 1 tests still passing;
- no network access in required tests;
- complete scripted S1 traces reproducible;
- termination and Evidence validation covered;
- no fallback from real to scripted planner in product composition.

### Phase 2 product-Demo readiness

Product-Demo readiness additionally requires:

- one configured `RealLLMPlanner` adapter;
- explicit R001–R006 results for the Phase 2 S1 cases;
- at least one retained failure/limitation analysis when failures occur;
- confirmation that the displayed trace came from the real model path;
- no claim that stochastic behavior is CI-certified.

### Phase 3 completion

Phase 3 requires:

- OQ-001 contract approval (§32–§40);
- T093–T124 passing with no skip or xfail;
- all Phase 1–2 tests (T001–T092) still passing;
- no network access in required tests;
- architecture boundary tests enforcing Phase 3 dependency direction;
- runtime integration using injected `RuleEngine`, `RuleProfileLoader`, and
  `KnowledgeIndex` (no implicit fixed-directory reads);
- scripted S1 traces with rule evaluation and knowledge retrieval branches;
- no fallback from real to scripted planner in product composition;
- OQ-003 resolved and an approved, versioned `profile_s1_distortion`
  demonstration profile included in the repository.

Test-local demonstration profiles may be used during RuleEngine and runtime TDD,
but they do not satisfy the Phase 3 completion gate.

---

## 18. Failure Handling Policy

When a required test fails:

1. determine whether the implementation violates the contract;
2. determine whether the test misstates the approved contract;
3. fix implementation when the contract is clear;
4. stop and report a genuine contract defect;
5. do not weaken assertions solely to produce green tests;
6. never replace failed DSP behavior with mocked values.

When real-model evaluation performs poorly:

1. retain the trace;
2. classify failure as selection, replanning, stopping, grounding, or diagnosis;
3. distinguish planner behavior from runtime/DSP defects;
4. improve prompt/model policy only against development cases;
5. rerun transparently and report variation;
6. never convert the product path into a hidden deterministic controller.

---

## 19. Required Development Report

Every checkpoint report includes:

```text
Files changed:
Tests added by ID:
Focused RED command and expected failure:
Focused GREEN command and result:
Accumulated/full suite command and result:
Warnings:
Unsupported cases:
Contract concerns:
Real-model evaluation run: yes/no/not applicable
```

No checkpoint or phase is described as complete if a required test is failing,
skipped, or xfailed.

---

## 20. Contract-to-Test Coverage Summary

| Contract area | Test IDs |
|---|---|
| Signal models/factory | T001–T006 |
| Repository | T007–T011 |
| Segment/channel | T012–T016 |
| Synthetic/ground truth | T017–T024 |
| DSP preprocessing | T025–T027 |
| Clipping | T028–T032 |
| Spectrum | T033–T038 |
| Fundamental | T039–T043 |
| Harmonic distortion | T044–T052 |
| Tool contracts/service/Evidence | T053–T063 |
| Agent models/Planner protocol | T064–T070 |
| Runtime/policies/termination | T071–T085 |
| S1 deterministic acceptance | T086–T092 |
| Architecture boundary migration | T093 |
| Rule profile and engine | T094–T105 |
| Knowledge corpus and retrieval | T106–T112 |
| Agent model and runtime extensions | T113–T120 |
| S1 rule/knowledge acceptance | T121–T124 |
| Real-model behavior | R001–R006, non-CI |

Together, T001–T092 form the required Phase 1–2 deterministic acceptance gate.
T093–T124 form the required Phase 3 deterministic acceptance gate once
implementation begins.

---

## 21. Phase 3 — Rules, Knowledge, and Runtime Integration

Phase 3 tests verify deterministic rule evaluation, keyword/tag knowledge
retrieval, injected runtime boundaries, and extended S1 scripted acceptance.
They use real rule-engine and knowledge-index execution; no mocked numerical
results.

Architecture boundary migration (T093) may land before `rules/` and
`knowledge/` packages exist; those tests skip until packages are created.

### Checkpoint G — Architecture and package boundaries

| ID | Behavior | Required result |
|---|---|---|
| T093 | Phase 3 architecture boundary migration | `rules/` and `knowledge/` are no longer deferred; when present, dependency direction matches §37; `evaluation/` and `app/` remain absent; agent may import rules/knowledge |

### Rule profile models

| ID | Behavior | Required result |
|---|---|---|
| T094 | RuleProfile duplicate-ID validation | rejects duplicate `rule_id` within profile |
| T095 | RuleProfile validation | rejects empty `rules` tuple |
| T096 | Comparator PASS semantics and approved profile boundaries | `lte`/`eq`/`neq` express PASS condition per §33; `profile_s1_distortion` tests values below, equal to, and above clipping ratio 0.01 and THD 5.0% |
| T097 | RuleProfileLoader injection | loader resolves profile by ID; no implicit directory reads in tests |

### Rule engine

| ID | Behavior | Required result |
|---|---|---|
| T098 | PASS on valid Evidence | observed value satisfies comparator → `pass` with evidence ref |
| T099 | FAIL on valid Evidence | observed value fails comparator → `fail` with evidence ref |
| T100 | No matching Evidence | one `not_applicable` per rule, empty `evidence_refs`, non-empty `reason` |
| T101 | Inapplicable Evidence | invalid validity, strict scalar-type mismatch (including bool/int), or unit mismatch produces one `not_applicable` citing the Evidence ID |
| T102 | Multiple matching Evidence | one evaluation per matching Evidence for the same rule |
| T103 | evidence_filter | only filtered Evidence IDs considered |
| T104 | Deterministic batch output | identical profile + Evidence → identical business fields |
| T105 | Engine isolation | RuleEngine may import `tools.evidence`/contracts, but imports no agent, DSP algorithms, SignalToolService/registry runtime callables, LLM clients, evaluation, or app modules |

### Knowledge corpus and retrieval

| ID | Behavior | Required result |
|---|---|---|
| T106 | Chunk model validation | deterministic chunk IDs and excerpts for fixed corpus |
| T107 | Empty query and result-limit validation | empty query returns `query_text=""` with empty matches/chunks; `max_results <= 0` raises `ValueError` |
| T108 | Keyword normalization | Unicode casefold, punctuation tokenization, dedup |
| T109 | Tag matching | exact tag match after whitespace strip |
| T110 | matches/chunks 1:1 | same order, every match chunk_id resolves |
| T111 | Ranking determinism | stable ordering for fixed corpus and query |
| T112 | Knowledge isolation | KnowledgeIndex imports no agent/rules/dsp/tools |

### Agent model extensions

| ID | Behavior | Required result |
|---|---|---|
| T113 | EvaluateRulesDecision validation | profile_id pattern, purpose required |
| T114 | RetrieveKnowledgeDecision validation | non-empty query_text in planner decision |
| T115 | PlannerContext snapshots | immutable tuples for batches and retrievals |
| T116 | DiagnosisState mutability | lists for `rule_evaluation_batches` and `knowledge_retrievals` |

### Runtime integration

| ID | Behavior | Required result |
|---|---|---|
| T117 | Rule evaluation budget | counter semantics are exact and exhaustion terminates with `max_rule_evaluations` |
| T118 | Knowledge retrieval budget | counter semantics are exact and exhaustion terminates with `max_knowledge_retrievals` |
| T119 | Diagnosis validation | `rule_refs` resolve to evaluation IDs within batches; knowledge refs resolve |
| T120 | Injected dependencies | runtime uses injected engine, loader, and index; Phase 2 construction remains valid; requesting a Phase 3 action with its dependency absent terminates as `runtime_error` |
| T121 | S1-CLEAN rules branch | scripted trace evaluates clean profile rules |
| T122 | S1-CLIP rules branch | clipping rules PASS/FAIL aligned with synthetic ground truth |
| T123 | S1-HARM rules branch | harmonic rules PASS/FAIL aligned with synthetic ground truth |
| T124 | S1 combined rules + knowledge | claims cite evidence, rule refs, and knowledge refs; invalid Evidence yields `not_applicable` rule judgments |

Every T121–T124 test additionally asserts:

- real Tool/DSP execution for Evidence;
- real rule-engine and knowledge-index execution;
- no numeric fabrication on invalid inputs;
- complete reproducible trace for the scripted planner path.

---

## 22. Phase 4 — Versioned Evaluation and Fixed Baseline

Phase 4 required tests are deterministic. They use the real synthetic
generators, repository, DSP, Tools, RuleEngine, profile loader, knowledge index,
and an injected scripted planner. They never call a real LLM.

The separate official real-model benchmark uses the same validated manifest and
scorers but runs outside required pytest. Its stochastic scores are reported,
not used as CI pass/fail conditions.

### Checkpoint H — Public evaluation models and manifest

| ID | Behavior | Required result |
|---|---|---|
| T125 | Manifest identity and immutability | DatasetManifest uses schema `1.0`, semantic dataset version, immutable tuples, and rejects mutation |
| T126 | SyntheticSignalSpec discrimination | all five generator variants parse by `generator`; unknown variants fail |
| T127 | Synthetic parameter validation | invalid frequency, sampling, duration, clipping, amplitude constraints, RMS, or non-finite values fail before generation |
| T128 | Harmonic ratio validation | non-empty ratios, at least one positive ratio, unique integer orders >=2, and finite non-negative values are required |
| T129 | EvidenceCondition strictness | Tool, metric, validity, strict scalar type, unit, and comparator semantics are enforced |
| T130 | Sufficient Evidence references | sets are non-empty, duplicate-free, and reference conditions within the same case |
| T131 | EvaluationCase consistency | category, generator, causal faults, outcomes, knowledge policy, and identifiability fields cannot contradict each other |
| T132 | Manifest identity/reference validation | case/condition/set IDs are unique; profile identity/version and all internal references resolve |

### Checkpoint I — Official synthetic dataset

| ID | Behavior | Required result |
|---|---|---|
| T133 | Official case allocation and packaging | `s1-distortion-synthetic` `1.0.0` contains 8 development and 16 held-out cases with frozen category counts and ships in the installed package |
| T134 | Reconstruction determinism | every case reconstructed twice from canonical parameters/seed has identical metadata and samples |
| T135 | Dual-ground-truth consistency | generator ground truth agrees with declared causal faults while remaining separate from observable/rule conditions |
| T136 | Observable-condition verification | real SignalToolService Evidence satisfies every declared observable condition |
| T137 | Boundary coverage | dataset covers values below, within numeric tolerance of, and above clipping ratio 0.01 and THD 5.0% |
| T138 | Invalid/noise behavior | harmonic/F0-style invalid results stay not-applicable and contain no fabricated numeric Evidence |
| T139 | Combined identifiability | every combined case exceeds its matched clipping-only control by the declared harmonic-signature separation; control/truth never enters planner input |
| T140 | Dataset gate | any allocation, DSP observation, profile, reconstruction, or identifiability failure makes validation non-valid and prevents evaluation start |

### Checkpoint J — RecordingPlanner and chronological trace

| ID | Behavior | Required result |
|---|---|---|
| T141 | Transparent planner delegation | RecordingPlanner passes the same PlannerContext to its delegate and returns the validated decision unchanged |
| T142 | Planner-call snapshot order | records are immutable, zero-based, monotonic, and preserve successful, invalid-output, and raised-error calls without changing retry behavior |
| T143 | Tool delta assembly | each Tool decision is followed by its exact Observation and Evidence before the next planner decision |
| T144 | Rule delta assembly | EvaluateRulesDecision aligns with exactly the newly appended RuleEvaluationBatch |
| T145 | Knowledge delta assembly | RetrieveKnowledgeDecision aligns with exactly the newly appended KnowledgeRetrievalResult |
| T146 | Final-result assembly | every result artifact and claim reference resolves within the same chronological trace |
| T147 | Ambiguity rejection | missing, duplicate, out-of-order, or otherwise ambiguous artifacts fail trace assembly; grouped fallback is forbidden |
| T148 | Trace safety and optional usage | raw waveform, full FFT, secrets, and raw provider responses are absent; unavailable token/cost fields remain null |

### Checkpoint K — Honest fixed-pipeline baseline

| ID | Behavior | Required result |
|---|---|---|
| T149 | Fixed Tool order | baseline calls detect_clipping then analyze_harmonic_distortion exactly once each |
| T150 | Shared dependencies | baseline uses the injected repository, SignalToolService, RuleEngine, loader, and official profile |
| T151 | Deterministic mapping and result type | clipping, harmonic, combined, and no-supported-fault mappings use only applicable profile judgments; result uses baseline models and no planner completion reason |
| T152 | Invalid/insufficient Evidence mapping | valid clipping survives invalid harmonic analysis with a limitation; otherwise insufficient Evidence yields justified inconclusive behavior without fabricated values |
| T153 | No privileged or redundant actions | baseline reads no manifest truth/matched control, retrieves no knowledge, and calls no FFT/F0 |
| T154 | Baseline reproducibility and honesty | repeated execution has identical business fields; clipping-induced high THD remains an exposed possible combined overclaim, not a fixture-specific patch |

### Checkpoint L — Deterministic scoring

| ID | Behavior | Required result |
|---|---|---|
| T155 | Causal exact-set scoring | exact-set correctness handles clean, clipping, harmonic, combined, and inconclusive cases |
| T156 | Causal macro-F1 | stored expected/predicted label sets produce macro-F1 over exactly clipping and harmonic multilabel truth with fixed formulas |
| T157 | Outcome scoring | allowed clean/inconclusive outcomes score correctly and disallowed outcomes fail |
| T158 | Semantic grounding | every ref must resolve and at least one cited Evidence condition must explicitly support the claim; unrelated valid refs do not pass |
| T159 | Unsupported-claim scoring | only predicted causal fault claims absent from causal truth count; zero denominator is preserved with value 0.0 |
| T160 | First-Tool scoring | first DSP action is checked against the acceptable set without prescribing the later sequence |
| T161 | Observable replanning scoring | every context-delta opportunity receives an appropriate/inappropriate reason code under the frozen proxy semantics |
| T162 | Unnecessary Tool scoring | calls that advance no viable Evidence set and are not error recovery count as unnecessary |
| T163 | Timely stopping scoring | any DSP call after first sufficient Evidence fails the per-run stopping metric |
| T164 | Applicable rule scoring | non-duplicate rule use with applicable current Evidence succeeds; omission, premature use, and redundant use fail |
| T165 | Knowledge selectivity scoring | required usage, manifest-tag relevance, not-needed retrieval, and final citation utilization use independent visible denominators |
| T166 | Aggregation and target status | rates, zero denominators, exact-set accuracy, macro-F1, latency/usage coverage, averages, non-applicable targets, and meets/below-target status are deterministic |

### Checkpoint M — Deterministic end-to-end evaluation and reports

| ID | Behavior | Required result |
|---|---|---|
| T167 | Scripted full-manifest execution | all 24 cases run through the real runtime, DSP, Tools, rules, and knowledge dependencies with ScriptedPlanner |
| T168 | Alternative legal routes | at least two cases use distinct sufficient Tool routes without changing expected outcome or requiring a fixed sequence |
| T169 | Same-run traceability | every Evidence, rule ref, and knowledge ref in scored diagnoses resolves in the same run/trace |
| T170 | Deterministic repeat | fixed manifest, scripted planner, injected IDs/clock, and dependencies produce identical normalized traces and scores |
| T171 | Baseline full-manifest execution | baseline runs once on each of the same 24 cases and never reads case truth |
| T172 | Agent/baseline comparison | aggregates are side by side; no test requires the Agent to beat the baseline |
| T173 | Report representation agreement | JSON/JSONL, CSV, and Markdown agree on case/run counts, metrics, statuses, and failures |
| T174 | Immutable report bundle | exact required files and checksums are written; existing benchmark directory is rejected; failed cases and repeated-run variation are retained |

### Checkpoint N — Official real-model runner controls

Tests in this checkpoint stub the provider boundary. They do not call the
network or assert stochastic diagnosis quality.

| ID | Behavior | Required result |
|---|---|---|
| T175 | Configuration fingerprint | dataset/profile identity, provider/model, prompt version/hash, model parameters, and SDK versions determine recorded configuration |
| T176 | Held-out slot schedule | official DeepSeek configuration schedules five sequential manifest-order rounds over 16 held-out cases; baseline schedules one manifest-order run per case |
| T177 | Development/held-out separation | development runs may tune config; a benchmark ID becomes append-only once held-out results are observed |
| T178 | Infrastructure retry policy | only timeout, 429, and provider 5xx retry, at most twice, with every attempt retained |
| T179 | Behavioral failures are not replaced | invalid model output, planner retry exhaustion, no-progress, budgets, and Runtime terminal errors keep their original slot |
| T180 | Acceptance status separation | missing credentials -> pending; exhausted infrastructure/evaluator failure -> incomplete; 80 scoreable slots -> completed; target miss -> below_target without CI failure |
| T181 | Credential and artifact safety | no plaintext credential CLI argument or report field exists; official bundles cannot overwrite earlier benchmark IDs |

### Checkpoint O — Architecture and regression

| ID | Behavior | Required result |
|---|---|---|
| T182 | Phase 4 dependency boundary | evaluation may import Phase 1–3 packages; signal/dsp/tools/rules/knowledge/agent do not import evaluation; app remains absent |
| T183 | Cumulative completion gate | T001–T183 pass with zero required skip/xfail; Phase 1–3 semantics, Ruff, mypy, and `git diff --check 9bd01f2..HEAD` (Phase 4 design baseline) remain green |

### Phase 4 acceptance states

`harness_accepted` requires T001–T183 and all deterministic quality gates.

`benchmark_completed` additionally requires the frozen DeepSeek configuration
to produce 80 scoreable held-out Agent slots and the immutable official report
bundle. Real-model target misses produce `below_target` and never fail CI.
Missing credentials leave `benchmark_pending`; exhausted infrastructure or an
invalid evaluator leaves `incomplete`. Phase 5 remains gated until both states
are satisfied.

---

## 23. Phase 4.1 — Additive Agent Behavior Calibration

Phase 4.1 required tests are deterministic and additive. They do not change
T125–T183 semantics. Deterministic tests may use `ScriptedPlanner` or a fake
provider transport, but they must exercise the real runtime, Tools, RuleEngine,
KnowledgeIndex, and trace assembly where those components are in scope.
Stochastic model behavior does not enter ordinary CI.

### Checkpoint P — Prompt, dual-truth, dataset, runner, and cumulative gate

| ID | Behavior | Required result |
|---|---|---|
| T184 | Prompt identity | prompt version, exact content hash, and benchmark configuration agree |
| T185 | No evaluation leakage | prompt and serialized PlannerContext omit causal truth, split, knowledge policy, sufficient-Evidence sets, and scoring conditions |
| T186 | Dual-truth expression | deterministic examples support a causal distortion claim and an independent PASS/FAIL configured judgment in the same final diagnosis |
| T187 | Rule action propagation | applicable Evidence can drive a fake model rule decision through the real runtime, and the resulting batch reaches the next planner context and final claim |
| T188 | Invalid knowledge path | invalid Evidence can drive knowledge retrieval, an inconclusive claim with valid references, and a non-empty limitation |
| T189 | Same-run traceability | every final Evidence, rule, and knowledge reference resolves within the same run |
| T190 | Dynamic route preservation | the prompt does not prescribe a fixed Tool order, and multiple scripted/fake S1 routes remain valid |
| T191 | v1.1.0 manifest | identity, category allocation, unique IDs, deterministic parameters, seeds, and reconstruction validate |
| T192 | Natural requests | v1.1.0 request text contains no Tool names, required order, or answer-bearing evaluation labels |
| T193 | Split isolation | development and held-out IDs, signal parameter combinations, random seeds, and request assignments do not overlap |
| T194 | Official runner freeze | the real runner binds the frozen prompt hash, v1.1.0 dataset, new benchmark ID, and exactly 16 x 5 held-out slots |
| T195 | Cumulative gate | T001-T195 pass with zero required skip/xfail; Ruff, mypy, architecture boundaries, and `git diff --check b68ec5e..HEAD` remain green |

### Phase 4.1 acceptance states

Phase 4.1 is accepted only when the new held-out benchmark has
`benchmark_status=completed` and `target_status=meets_target`, every existing
target with a non-zero denominator passes, all 80 held-out Agent slots are
scoreable, the append-only six-file official bundle validates and its checksums
match, failures and five-run variation remain visible, the `b68ec5e` v1.0.0
`below_target` baseline remains present and traceable, T001–T195 have no
required skip/xfail or regression, and Ruff, mypy, architecture tests, and
`git diff --check` pass.

The first official Phase 4 benchmark at `b68ec5e` remains
`completed/below_target`. That result is honest harness completion, not a
failure of the evaluator and not a product-quality behavior pass. Phase 5
remains gated until the Phase 4.1 gate is independently verified.

---

## 24. Phase 4.1 — Additive Prompt v6 Correction

T196–T200 are deterministic and additive. They preserve T001–T195 and the
recorded v4/v5 prompt, campaign, configuration, and report identities. Fake
provider transports may drive the real `RealLLMPlanner` boundary for ordinary
CI, but stochastic model behavior is evaluated only by the separately gated
development and official campaigns.

### Checkpoint Q — v6 identity, coherent policy, product path, and campaigns

| ID | Behavior | Required result |
|---|---|---|
| T196 | Prompt and legacy identity | exact v4/v5 prompt bytes, hashes, private builders, campaign routes, fingerprints, and committed bundles remain reproducible; v6 uses version `v0.2-s1-planner-6`, one coherent immutable prompt, and an exact SHA-256/configuration identity |
| T197 | Coherent v6 semantics | prompt policy and examples consistently preserve viable hypotheses, separate causal Evidence from configured acceptance, restrict `no_supported_fault` to a final empty cause set, require traceable inconclusive claims, and avoid a fixed Tool sequence |
| T198 | Product-boundary behavior | deterministic fake transport through the real `RealLLMPlanner` and real Runtime proves no evaluation leakage, same-run Evidence/rule/knowledge resolution, rule and knowledge propagation, and valid dynamic routes for boundary harmonic, combined, invalid/noisy, and strong-harmonic cases |
| T199 | Additive campaign freeze | existing Phase 4.1 choices remain v5; `phase4.1-v6-development` binds v6 to 8 × 5 v1.1.0 development slots and `bench_phase4_1_dev_v6_gate2`; `phase4.1-v6-official` binds the byte-identical candidate to 16 × 5 held-out slots and `bench_official_s1_v11_planner6_gate2`, with official execution rejected before a development `completed/meets_target` bundle |
| T200 | Cumulative gate | T001–T200 pass with zero required skip/xfail; Ruff, mypy, architecture boundaries, and `git diff --check f9392c2..HEAD` remain green; no Phase 5 code or controller-forced analysis action is introduced |

### Phase 4.1 v6 acceptance states

The 40-slot v6 development gate is tuning evidence, not official held-out
proof. It must use the v1.1.0 development split only. A result other than
`benchmark_status=completed` and `target_status=meets_target` is retained
honestly and forbids the official v1.1.0 held-out run.

After development meets target, the frozen candidate may run the official
80-slot held-out gate once. Phase 4.1 is accepted only when that official run
is `completed/meets_target`, all 80 Agent slots are scoreable, checksums and
six-file bundle validation pass, T001–T200 have zero required skip/xfail, Ruff,
mypy, architecture tests, and diff-check pass, and the v1.0.0 official plus v5
development below-target assets remain present and reproducible. A completed
official target miss remains honest evidence, leaves Phase 4.1 unaccepted, and
must not be tuned against or rerun on the same held-out set. Phase 5 remains
gated pending independent acceptance and a separate Phase 5 design approval.

---

## 25. Phase 4.2 — Evaluation Integrity and Planner v7 Calibration

T201–T208 are deterministic and additive. They preserve T001–T200, all
historical prompt/campaign/configuration identities, and committed report
bundles. They correct evaluation input integrity before any v7 real-model
campaign. Fake transports may exercise the real `RealLLMPlanner` boundary in
CI; stochastic behavior remains outside required pytest.

### Checkpoint R — v1.2 integrity, planner v7, campaigns, and cumulative gate

| ID | Behavior | Required result |
|---|---|---|
| T201 | Legacy and v7 identity | exact v4/v5/v6 prompt bytes, hashes, private planners, campaign routes, configurations, and committed bundles remain reproducible; v7 is one coherent `v0.2-s1-planner-7` prompt with an exact SHA-256/configuration identity and a private exact-v6 compatibility planner |
| T202 | Opaque identity and value-level leakage | every v1.2 Agent signal ID is deterministic `sig_eval_` plus 24 lowercase SHA-256 hex characters and contains no semantic label; serialized outbound keys and values omit case ID, split, category, generator, causal truth, policy, acceptable Tools, sufficient sets, scoring targets, raw waveform, and full FFT |
| T203 | v1.2 manifest freshness and request fairness | dataset `1.2.0` has the frozen 8/16 category allocation; IDs, complete parameter tuples, seeds, and request assignments are fresh and split-disjoint; reconstruction is deterministic; natural requests contain no Tool/answer labels; identical initial visible request/metadata cannot have disjoint acceptable first Tools |
| T204 | Observable conditions and single-signal identifiability | real generators and SignalToolService satisfy every v1.2 condition; invalid/noise alternative routes stay non-fabricated; every combined case exposes a reportable order-2 harmonic supporting the harmonic claim and passes its matched-control separation; only valid v1.2 matched controls may treat an absent filtered order-2 component as zero; historical validation semantics do not change |
| T205 | Coherent v7 policy | prompt policy treats signal IDs as opaque, chooses from visible symptoms, keeps dynamic hypotheses without a fixed pipeline, emits pure traceable inconclusive claims, separates configured acceptance from observed distortion, distinguishes odd clipping-induced content from v1.2 even-order combined Evidence, and qualifies arbitrary-WAV independence |
| T206 | Product-boundary behavior | deterministic fake transport through active RealLLMPlanner and real Runtime, DSP Tools, RuleEngine, and KnowledgeIndex proves valid dynamic invalid/noise, clipping-only, combined, and harmonic-boundary routes; every final Evidence/rule/knowledge ref resolves in the same run and no evaluation truth leaks |
| T207 | Canonical campaigns and strict provenance | historical v5/v6 choices remain unchanged; `phase4.2-v7-development` binds canonical `bench_phase4_2_dev_v7_v12_gate3` to v1.2 development 8 x 5; `phase4.2-v7-official` binds canonical `bench_official_s1_v12_planner7_gate3` to v1.2 held-out 16 x 5; official scheduling rejects missing, unreadable, incomplete, non-canonical, or identity-mismatched development provenance before credentials/held-out, including the historical v6 missing-manifest regression |
| T208 | Cumulative gate | T001–T208 pass with zero required skip/xfail; Ruff, mypy, architecture boundaries, and `git diff --check aefccba..HEAD` remain green; no Phase 5 code, controller-forced action, target reduction, ScriptedPlanner fallback, or historical identity drift is introduced |

### Phase 4.2 real-model acceptance states

The canonical 40-slot v1.2 development gate is tuning evidence. It may run
once for the exact frozen v7 identity after T001–T208 and the static gates pass.
A status other than `benchmark_status=completed` and
`target_status=meets_target` is preserved honestly and forbids official
execution under that candidate.

Only a strict identity-matching development bundle authorizes the canonical
one-shot 80-slot v1.2 official held-out gate. Product-quality acceptance
requires official `completed/meets_target`, 80 scoreable Agent slots, a valid
append-only six-file bundle and checksums, and all deterministic/static gates.
An official miss remains honest evidence and cannot be tuned against or rerun.
The v1.1.0 held-out split remains unexecuted and is not a fallback official set.

Approval of this section freezes design and tests only. Phase 4.2 Tasks 2–10,
all code implementation, all real-model development execution, and every
held-out run require separate explicit authorization. Phase 5 remains gated.

Recorded Task 10 outcome (2026-08-30, bundle commit `71293a3`): T201–T208
deterministic tests are implemented and the T208 cumulative gate is green.
The canonical 40-slot development campaign is honest `completed/below_target`.
Official v1.2.0 held-out was not run. Phase 4.2 is not accepted. Phase 5
remains gated.

---

## 26. Phase 4.3 — Planner v8 Behavior Calibration

T209–T215 are deterministic and additive. They preserve T001–T208, dataset
`1.2.0`, frozen targets and scoring, all historical prompt/campaign identities,
and all committed bundles. Fake transports exercise the real RealLLMPlanner
boundary in required tests; stochastic provider behavior is never a pytest
gate.

### Checkpoint S — v8 behavior, campaigns, and cumulative gate

| ID | Behavior | Required result |
|---|---|---|
| T209 | Legacy and v8 identity | exact v4–v7 prompt bytes, hashes, private planners, campaign routes, configurations, and committed bundles remain reproducible; v8 is one complete `v0.2-s1-planner-8` prompt with an exact SHA-256/configuration identity and a private exact-v7 compatibility planner |
| T210 | Coherent v8 policy | prompt semantics require explicit viable hypotheses, symptom-driven first-Tool choice, direct harmonic analysis without mandatory spectrum/F0, minimal Tool use, broad combined continuation, invalid-result rule/knowledge handling, and immediate stopping after all viable hypotheses close |
| T211 | Outbound non-leakage | serialized v8 Planner messages contain no case ID, category, split, generator truth, causal truth, policy, acceptable Tools, sufficient sets, observable conditions, scoring targets, raw waveform, or full FFT and never infer behavior from opaque signal IDs |
| T212 | Product-boundary behavior | deterministic fake transport through active RealLLMPlanner and real Runtime, DSP Tools, RuleEngine, and KnowledgeIndex proves clean, harmonic, combined, and noise routes with same-run Evidence/rule/knowledge resolution; clean avoids default spectrum/F0, harmonic starts directly, combined closes both hypotheses, and noise performs required knowledge retrieval without clipping/spectrum detours |
| T213 | Dynamic controller boundary | Runtime does not construct, force, or reorder Tool/rule/knowledge/finish decisions; no universal pipeline or ScriptedPlanner product fallback is introduced; existing retry, invalid-decision, no-progress, max-action, and termination semantics remain unchanged |
| T214 | Canonical campaigns and provenance | `phase4.3-v8-development` binds `bench_phase4_3_dev_v8_v12_gate4` to v1.2 development 8 x 5; `phase4.3-v8-official` binds `bench_official_s1_v12_planner8_gate4` to v1.2 held-out 16 x 5; strict preflight rejects missing, unreadable, incomplete, non-canonical, or mismatched provenance before credentials/held-out |
| T215 | Cumulative gate | T001–T215 pass with zero required skip/xfail; Ruff, mypy, architecture boundaries, and `git diff --check eb47237..HEAD` remain green; dataset/scorer/targets, public boundaries, historical identities, Phase 5, and held-out state do not drift |

### Phase 4.3 real-model acceptance states

The exact v8 development identity may run once only after T001–T215 and all
static gates pass. Development is tuning evidence. Every applicable frozen
target must pass simultaneously before official is legal.

A development miss is retained honestly, forbids official, forbids a
prompt-only v9, and requires a new written choice between model change and
PlannerContext change. A passing byte-identical candidate may run the official
80-slot held-out campaign once. Phase 4.3 is accepted only when official is
`completed/meets_target`, all slots and provenance validate, and no held-out
tuning or rerun occurred. Phase 5 remains gated pending separate authorization.

Approval of this section freezes design and tests only. It does not authorize
implementation or any real-model campaign.

---

## 27. Phase 4.3.1 — Planner v8.1 Compliance Correction

T216–T223 are deterministic and additive. They preserve T001–T215, dataset
`1.2.0`, all public models, frozen targets, historical scoring behavior,
prompt/campaign identities, and committed bundles. Stochastic provider behavior
is never a pytest gate.

### Checkpoint T — v8.1 compliance, scoring provenance, and cumulative gate

| ID | Behavior | Required result |
|---|---|---|
| T216 | Historical and v8.1 identity | exact v4–v8 prompt bytes, hashes, private planners, routes, configurations, fingerprints, trace scores, and committed bundles remain reproducible; v8.1 is one complete `v0.2-s1-planner-8.1` prompt with independent exact SHA-256/configuration identity |
| T217 | Request scope | existing TaskAssessment hypotheses start with clipping only for clipping-specific requests, harmonic only for harmonic-specific requests, and both for generic broad requests; clipping-specific finish is legal after its family closes, while broad/combined early finish is prohibited while another requested family remains viable |
| T218 | Affirmative causal claims | causal fault types represent supported causes only; negative, ruled-out, absent, or limitation prose does not use a causal clipping/harmonic fault type; no-supported-fault and inconclusive semantics remain distinct |
| T219 | Clipping attribution | real deterministic strong clipping with high THD and odd-order-only Evidence remains clipping-only; independent harmonic distortion requires reportable order-2 Evidence; combined cases retain separate clipping and order-2 support |
| T220 | Versioned scoring policy | legacy configurations reproduce legacy results; `signal_diag.scoring=2.0.0` recognizes valid and invalid/not-applicable structured Evidence as eligible RuleEngine input, scores a following applicable NOT_APPLICABLE rule/replan appropriately, and leaves all other formulas, failure codes, targets, and public signatures unchanged |
| T221 | Product-boundary behavior | deterministic fake transport through active RealLLMPlanner and real Runtime, DSP Tools, RuleEngine, and KnowledgeIndex proves clipping-specific, broad/combined, and invalid/noise routes; same-run Evidence/rule/knowledge references resolve and no ScriptedPlanner fallback or Runtime-forced action occurs |
| T222 | Canonical campaigns and preflight | `phase4.3.1-v8.1-development` / `bench_phase4_3_1_dev_v8_1_v12_gate5` and conditional `phase4.3.1-v8.1-official` / `bench_official_s1_v12_planner8_1_gate5` bind dataset 1.2.0 and scoring 2.0.0; strict identity, destination, development-before-official, manifest, metrics, and checksum validation occurs before credentials, SDK construction, or held-out access |
| T223 | Cumulative gate | T001–T223 pass with zero required skip/xfail; Ruff, mypy, architecture boundaries, and `git diff --check 1b94194..HEAD` remain green; public boundaries, dataset, targets, historical identities/assets, Phase 5, and held-out state do not drift |

### Phase 4.3.1 real-model acceptance states

The exact v8.1 development identity may run once only after T001–T223 and all
static gates pass. All applicable frozen targets must pass simultaneously.

A development miss is preserved honestly, forbids official and v8.2/v9, and
requires a new written model-capability versus PlannerContext decision. A
passing byte-identical candidate may run the official 80-slot held-out campaign
once. Phase 4.3.1 is accepted only when official is
`completed/meets_target`, all 80 slots are scoreable, all provenance validates,
and no held-out tuning or rerun occurred. Phase 5 remains gated pending separate
design and authorization.

Approval of this section freezes design and tests only. It does not authorize
implementation or any real-model campaign.

---

## 28. Phase 5 — Presentation Engineering

**Frozen status:** T224–T285 were approved under OQ-010 on 2026-08-31. OQ-011 /
D031 on 2026-08-31 amends only T284–T285 and the deterministic acceptance
state: the dual-interpreter input is local clean-environment full verification
on Python 3.11 and 3.12. Hosted GitHub Actions is not required. No other
T224–T283 result is reduced.

All T224–T285 tests are deterministic. Tests that exercise the Agent use an
explicit scripted/fake planner or fake transport while retaining real Signal,
DSP, Tools, RuleEngine, KnowledgeIndex, Runtime, service, API, and report
components. Required pytest never calls DeepSeek or depends on stochastic
behavior.

### Checkpoint U — WAV ingestion

| ID | Behavior | Required result |
|---|---|---|
| T224 | Standard PCM containers | valid little-endian RIFF/WAVE mono and stereo fixtures for 8-, 16-, 24-, and 32-bit integer PCM load successfully with correct metadata |
| T225 | Extensible PCM | WAVE_FORMAT_EXTENSIBLE with PCM subtype and matching valid/container bits loads; float, non-PCM subtype, RIFX, RF64, compressed, or mismatched valid bits is rejected as unsupported |
| T226 | Full-scale conversion | 8-bit unsigned offset, 16-/24-/32-bit signed extrema, 24-bit sign extension, interleaving, and zero map to the frozen full-scale float32 values without peak normalization |
| T227 | Canonical record | loader output is finite, C-contiguous, immutable after repository insertion, shaped (frames, channels), source_type wav, opaque-ID, and consistent with source metadata |
| T228 | RIFF traversal | legal unknown chunks, odd-size padding, and legal chunk ordering work; chunk sizes are checked before allocation |
| T229 | Structural corruption | missing/duplicate-conflicting fmt or data, truncation, invalid RIFF size, inconsistent byte rate/block alignment, partial frame, and non-finite/overflow paths fail deterministically as invalid_wav |
| T230 | Unsupported shape/encoding | more than two channels and every unsupported encoding fail as unsupported_wav without partial Signal insertion |
| T231 | Upload-byte limit | exactly 20 MiB is eligible for parsing; the next byte stops bounded reading and maps to payload_too_large without retaining bytes or a run |
| T232 | Signal resource limits | inclusive sample-rate bounds work; out-of-range rate, more than 2,000,000 frames, or duration above 30 seconds maps to signal_limit_exceeded with no truncation/resampling |
| T233 | Filename and file hygiene | only a basename of at most 255 Unicode code points is retained, traversal text cannot influence paths, input is never written to a temp file, and repeated loads never reuse semantic IDs |

### Checkpoint V — Demo presets and visualization preview

| ID | Behavior | Required result |
|---|---|---|
| T234 | Catalog identity | exactly five versioned preset IDs and stable public descriptors exist: clean_periodic, clipping, harmonic_distortion, combined_distortion, noise_inconclusive |
| T235 | Evaluation isolation | preset modules do not import evaluation manifests or copy development/held-out case IDs; outbound PlannerContext never contains preset ID, label, or generator truth |
| T236 | Deterministic materialization | each preset reproduces identical float32 sample bytes and explicit seed behavior while each record receives a fresh opaque non-semantic Signal ID |
| T237 | Canonical registration | all presets satisfy accepted SignalRecord/repository contracts and use the same downstream application registration path as WAV |
| T238 | Preview | short signals retain each sample; long signals use deterministic time-ordered min/max buckets, preserve extrema, return at most 1,000 points, reject max_points outside 2–1,000, and create no Tool call or Evidence |

### Checkpoint W — Application models and bounded execution

| ID | Behavior | Required result |
|---|---|---|
| T239 | Frozen DTO validation | every Phase 5 model validates finite numeric fields, field bounds, exact opaque ID patterns, UTC timestamps, source/preset exclusivity, and immutable serialization |
| T240 | Lifecycle invariants | only queued→running→completed/failed transitions are legal; timestamps, result, error, and trace fields satisfy status-specific invariants |
| T241 | Scheduling | a FIFO executor runs at most one diagnosis, admits at most four queued runs, and starts the next run only after the active run reaches a terminal state |
| T242 | Terminal retention | the latest twenty terminal runs remain queryable; admission evicts the oldest terminal run deterministically when required |
| T243 | Active-run safety and cleanup | queued/running runs are never evicted; terminal eviction removes only that run's owned Signal records and never another run's data |
| T244 | Capacity and lookup errors | no safe slot maps to capacity_exceeded; unknown IDs map to run_not_found; illegal internal state changes fail without corrupting stored snapshots |
| T245 | In-memory scope and shutdown | independent service/store instances share no runs; restart semantics are empty; idempotent aclose stops admission, fails queued records safely, and awaits the active run; no database, filesystem persistence, user cancellation, or recovery claim is present |

### Checkpoint X — Shared application service and composition

| ID | Behavior | Required result |
|---|---|---|
| T246 | WAV submission path | valid WAV submission performs validation, source/analysis registration, preview, atomic run reservation, and background execution through DiagnosisApplicationService |
| T247 | Synthetic submission path | every preset reaches the same private registration/queue/execution path as WAV and produces the same application model shape |
| T248 | Channel realization | mono/mixdown, stereo left/right/mixdown use accepted extract_segment values and a run-owned mono analysis record; mono right is rejected before queueing |
| T249 | Request integrity | trimming and the 2,000-character limit are enforced; only factual channel context may be appended; no preset truth, expected Tool/outcome, score target, raw samples, or full FFT reaches PlannerContext |
| T250 | Per-run isolation | each run receives fresh planner, RecordingPlanner, and Runtime instances; counters, records, observations, and references never cross run IDs |
| T251 | Product planner boundary | product composition uses public RealLLMPlanner with DeepSeek/v8.1 defaults, records actual overrides, rejects missing credentials before reservation, and never silently constructs ScriptedPlanner |
| T252 | Complete S1 service path | injected deterministic Planner plus real DSP, Tools, RuleEngine, KnowledgeIndex, and Runtime completes representative WAV and synthetic S1 paths with all Evidence/rule/knowledge refs resolvable in the same run |

### Checkpoint Y — Generic trace and reports

| ID | Behavior | Required result |
|---|---|---|
| T253 | Public Agent event assembly | assemble_agent_events exposes strict chronological Planner, Observation, Rule, and Knowledge events without EvaluationCase, truth, config, slot, or scoring input |
| T254 | Strict ordering and errors | empty-delta Planner decisions and planner errors remain recorded; non-append-only contexts, mismatched artifacts, unknown refs, grouped histories, and forbidden payloads are rejected |
| T255 | Phase 4 compatibility | assemble_evaluation_trace delegates to the public helper and all historical Phase 4 serialized traces, fingerprints, scores, reports, and bundle checksums remain unchanged |
| T256 | Trace projection boundary | app projection produces compact ordered TraceEventView links without duplicating chronology, exposing full PlannerContext snapshots, or inventing Tool progress |
| T257 | Report construction | only completed snapshots with valid AgentRunResult and strict trace create schema 1.0.0 DiagnosisReport with explicit completed lifecycle, source, channel, planner identity, preview, result, warnings/errors, and references |
| T258 | Same-run integrity | unknown Evidence, Rule, or Knowledge refs produce trace_integrity_error before JSON/HTML; valid supported, no-fault, and inconclusive reports retain every reference |
| T259 | Canonical JSON | injected time yields stable sorted UTF-8 JSON that round-trips through DiagnosisReport without semantic loss |
| T260 | Safe offline HTML | HTML is rendered only from the report model, is self-contained/no-CDN/no-script, escapes filename/question/LLM/Knowledge/error text, and links stable same-run anchors |
| T261 | Forbidden data | JSON/HTML/API models contain no credentials, authorization values, stack traces, raw provider bodies, full waveform, or full FFT; existing sanitizer remains effective |
| T262 | Honest identity and limits | report records actual provider/model/prompt, labels non-default model as uncertified by Phase 4.3.1, and labels the 1%/5% profile only as 1.0.0-demo settings |
| T263 | Preview/report separation | report includes no more than 1,000 visualization-only points; changing preview cannot change diagnosis, Evidence, rules, Tool history, or trace ordering |

### Checkpoint Z — HTTP API

| ID | Behavior | Required result |
|---|---|---|
| T264 | Read-only endpoints | health, five presets, accepted evaluation summary, root UI, and OpenAPI load without credentials; health reports configured=false without exposing key/base-url secrets |
| T265 | WAV submission | bounded multipart parsing plus valid fields returns 202 queued RunSubmission; byte/format/structure/signal errors use the frozen envelope and status mapping without retaining a Signal/run |
| T266 | Synthetic submission | valid preset JSON returns 202; unknown preset, invalid channel, empty/oversize question, and malformed body use the frozen envelope |
| T267 | Polling lifecycle | GET run exposes monotonic queued/running/completed/failed snapshots and adds actual result/strict trace only when terminal; simultaneous polling does not mutate the run |
| T268 | Report endpoints | completed Agent results download canonical JSON and UTF-8 HTML with opaque safe filenames; queued/running use run_not_terminal, application-failed uses report_unavailable, and unknown runs use run_not_found |
| T269 | HTTP security defaults | CORS is off, CSP is same-origin, root/static paths cannot traverse package assets, errors have no traceback, and content types/status codes match §62 |
| T270 | Missing credentials/provider failure | unconfigured submission returns 503 before run reservation with no fallback; provider/runtime failures after 202 appear in the polled terminal Agent result or sanitized application error, not a retroactive synchronous HTTP failure, and never change to ScriptedPlanner |

### Checkpoint AA — CLI

| ID | Behavior | Required result |
|---|---|---|
| T271 | Command grammar | argparse exposes serve, presets, diagnose wav, and diagnose synthetic with the frozen defaults/options and rejects invalid combinations as usage errors |
| T272 | WAV command | CLI WAV reads through the bounded path, calls the shared service, waits for terminal state, and does not require an HTTP server |
| T273 | Synthetic command | CLI preset uses the shared service/catalog and never sends preset labels/truth to PlannerContext |
| T274 | Output, reports, and exits | text/JSON and optional HTML derive from the canonical result; exit 0/1/2 exactly distinguishes valid diagnosis, execution failure, and usage/input/configuration failure |
| T275 | Serve defaults | serve composes the same product service, binds 127.0.0.1 by default, accepts explicit host/port, emits the no-auth warning, and exposes no scripted planner switch |

### Checkpoint AB — Web UI and evaluation presentation

| ID | Behavior | Required result |
|---|---|---|
| T276 | Packaged no-build UI | wheel contains native index.html/styles.css/app.js; the page uses no Node artifact, CDN, framework, analytics, or browser credential field |
| T277 | Complete interaction | UI supports WAV/preset, question, legal channel choices, submit/poll, actual lifecycle, diagnosis, preview, trace, observations, Evidence, rules, knowledge, limitations/errors, and report downloads |
| T278 | Safe rendering | external strings are rendered through text-safe DOM operations, no LLM/upload text reaches innerHTML, and queued/running UI never fabricates specific Tool progress |
| T279 | Evaluation snapshot integrity | frozen AcceptedEvaluationSummary validates exact identities/counts/five source checksums against the immutable Phase 4.3.1 official manifest/metrics/report data, and wheel installation can load it without docs/ |
| T280 | Honest evaluation panel | UI shows completed/meets_target, 80 held-out Agent slots, targets and actual Agent/fixed comparison, 2/80 behavioral-failure slots, 1/80 outcome error, and demonstration-target disclaimer without hiding failures |

### Checkpoint AC — Packaging, architecture, CI, and cumulative gate

| ID | Behavior | Required result |
|---|---|---|
| T281 | Package metadata | explicit app/llm/dev extras and signal-diag console entry exist; core installation does not require FastAPI; static/report/evaluation assets are declared as package data |
| T282 | Wheel smoke | sdist/wheel build cleanly; a fresh environment installs the wheel with app+llm extras, imports core/app without source-tree paths, loads assets, runs presets, and starts API composition without credentials |
| T283 | Architecture boundary | dependency direction includes evaluation→app; signal/dsp/tools/rules/knowledge/agent do not import app; WAV imports no app/evaluation/Agent/LLM framework; API/UI do not duplicate DSP/rule/diagnosis logic |
| T284 | Secret-free dual-version verification | a committed local verifier creates a fresh venv for CPython 3.11 and for CPython 3.12, installs `.[app,llm,dev]` with no provider secret, and runs deterministic pytest, architecture, Ruff, mypy, build, and wheel smoke in each environment; it uses no network model call, required skip, or stochastic gate. Hosted GitHub Actions is optional and is not an acceptance input |
| T285 | Phase 5 cumulative gate | T001–T285 pass with zero required skip/xfail; Ruff, mypy, architecture, wheel, clean-install, Python 3.11/3.12 local clean-environment full verification, and git diff --check 36ae7c9..HEAD pass; Phase 1–4.3.1 contracts, prompts, datasets, scores, reports, and bundle checksums do not drift |

### Phase 5 acceptance states

The deterministic state is `presentation_harness_accepted`. It requires the
entire T001–T285 gate, static quality checks, package smoke, and both supported
Python local clean-environment jobs (3.11 and 3.12). Missing credentials do
not block this state. Hosted GitHub Actions is not required. ScriptedPlanner is
legal only through explicit dependency injection in deterministic tests; the
test still uses real deterministic lower layers.

After that state is accepted, separate non-CI checks are:

```text
P5-R001  one public synthetic preset runs once through public RealLLMPlanner
         and DiagnosisApplicationService and writes a sanitized strict Trace,
         canonical JSON, and self-contained HTML report.

P5-R002  one public Demo signal encoded as a supported PCM WAV runs once
         through the same product path and writes the same artifact set.

P5-R003  the primary Web UI displays an actual completed product run, its
         trace/evidence/rules/knowledge/report links, and the honest accepted
         evaluation summary; sanitized screenshots are retained.
```

These checks prove presentation integration, not stochastic behavior quality.
Their individual diagnoses are retained honestly whether right or wrong.
Phase 4.3.1 official remains the real-model behavior evidence. A failure never
falls back to ScriptedPlanner. Missing credentials leave
`real_demo_pending`; complete sanitized artifacts make it
`real_demo_completed`.

Phase 5 and V0.2 are fully accepted only when:

```text
presentation_harness_accepted
real_demo_completed
```

Only after both may project documentation describe V0.2 as a
complete demonstrable vertical slice.

Approval of §28 freezes tests and design only. It does not authorize
implementation, real-model execution, push, merge, worktree deletion, or
cleanup of the pre-existing untracked `build/`. A detailed implementation
plan and separate execution choice remain required.
