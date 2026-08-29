# Signal Diagnosis Agent — Test Plan V0.2

**Document:** `TEST_PLAN_V0_2.md`  
**Version:** `0.2`  
**Status:** Approved and required for Phase 1–4
**Scope:** Phase 1 deterministic foundation, Phase 2 hybrid Agent runtime, and
Phase 3 rules/knowledge acceptance; frozen Phase 4 evaluation acceptance
**Contracts:** `docs/CONTRACTS_V0_2.md`  
**Architecture:** `docs/ARCHITECTURE_V0_2.md`  

---

## 1. Purpose

This plan verifies two distinct layers:

1. deterministic system acceptance using real DSP/Tool execution and an injected
   `ScriptedPlanner`;
2. real-model behavior evaluation using `RealLLMPlanner`, outside required CI.

The deterministic suite proves contracts, numerical behavior, runtime routing,
state transitions, error handling, termination, and complete reproducible S1
paths. It does not claim that a real model will always make a good decision.

The real-model evaluation measures model behavior and records stochastic
variation. It never determines whether CI is green.

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
| T183 | Cumulative completion gate | T001–T183 pass with zero required skip/xfail; Phase 1–3 semantics, Ruff, mypy, and diff-check remain green |

### Phase 4 acceptance states

`harness_accepted` requires T001–T183 and all deterministic quality gates.

`benchmark_completed` additionally requires the frozen DeepSeek configuration
to produce 80 scoreable held-out Agent slots and the immutable official report
bundle. Real-model target misses produce `below_target` and never fail CI.
Missing credentials leave `benchmark_pending`; exhausted infrastructure or an
invalid evaluator leaves `incomplete`. Phase 5 remains gated until both states
are satisfied.
