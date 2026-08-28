# Signal Diagnosis Agent — Architecture V0.2

**Document:** `ARCHITECTURE_V0_2.md`  
**Version:** `0.2`  
**Status:** Approved architecture  
**Primary acceptance scenario:** `S1 — Distortion Diagnosis`  
**Supersedes:** V0.1 architecture assumptions where this document explicitly differs  

---

## 1. Purpose

This document redesigns the project as a staged, end-to-end Signal Test and
Fault Diagnosis Agent while preserving the central engineering boundary:

> Deterministic signal-processing code calculates numerical facts; the Agent
> decides what evidence to collect and how to form a supported diagnosis.

The complete project is developed through five independently reviewable phases:

1. deterministic signal-analysis foundation;
2. minimal end-to-end distortion-diagnosis Agent;
3. deterministic rules and a small knowledge/RAG layer;
4. evaluation, including Agent versus fixed pipeline;
5. presentation engineering through API, UI, and reporting.

Planning the complete system does not authorize implementing later phases early.
Each phase freezes only the contracts needed by that phase and its immediate
consumer.

---

## 2. First Core Acceptance Scenario

### S1 — Distortion Diagnosis

A user provides a synthetic periodic waveform, or later a WAV file, and asks:

> “Why does this signal sound distorted?”

The system must:

1. load the signal context;
2. classify the task as distortion analysis;
3. dynamically choose an appropriate first DSP tool;
4. inspect the structured observation;
5. decide whether more evidence is needed;
6. selectively call additional DSP tools only when justified;
7. stop when sufficient evidence exists;
8. apply deterministic configured rules where applicable;
9. produce a structured diagnosis with traceable evidence references.

S1 does not require a fixed sequence such as clipping, FFT, F0, then THD. A
fixed sequence would fail to demonstrate observation-driven replanning.

The first supported diagnosis space is deliberately narrow:

- clipping;
- harmonic distortion;
- combined clipping and harmonic distortion;
- clean or no supported distortion found;
- inconclusive when available evidence is insufficient or invalid;
- basic frequency/fundamental evidence only when needed to support harmonic
  analysis.

Synthetic signals with known ground truth are the primary acceptance inputs.
WAV ingestion is added only after the deterministic path is stable.

---

## 3. Architecture Choice

The project uses a modular monolith with strict dependency boundaries:

```text
signal
  ↓
dsp
  ↓
tools
  ↓
rules / knowledge
  ↓
agent
  ↓
evaluation
  ↓
app
```

This structure is chosen over graph-first and service-first alternatives because
it keeps the numerical core independently testable, supports a genuine Agent
path, and avoids deployment infrastructure that is not needed for the first
complete demonstration.

The arrows describe allowed higher-layer dependencies. Lower layers must not
import higher layers. Shared public models belong to the lowest layer that owns
their meaning; they are not collected into an unbounded generic `common`
package.

---

## 4. Non-Negotiable Boundaries

The following rules apply across all phases:

1. Raw waveform arrays never enter an LLM prompt or model context.
2. Full FFT arrays never enter the Agent context.
3. Numerical metrics are produced only by deterministic DSP code.
4. The LLM does not invent clipping ratios, frequencies, THD values, thresholds,
   or Pass/Fail results.
5. Test thresholds come from versioned deterministic rule configuration.
6. Tool outputs are compact, structured, typed, and traceable.
7. A diagnosis claim must cite valid evidence IDs.
8. Scientifically inapplicable metrics return `invalid`, not a fabricated value
   and not an internal-error status.
9. Repository-owned waveform data is immutable.
10. DSP functions receive one-dimensional working arrays and do not mutate
    caller data.
11. The Agent may return `inconclusive` when evidence is insufficient.
12. A repeated tool call requires a changed purpose or parameters and must be
    capable of adding evidence.
13. Tool calls, planner retries, and no-progress iterations have deterministic
    limits enforced by the runtime.
14. Real-model behavior is evaluated separately from deterministic CI acceptance.

---

## 5. Proposed Package Boundaries

```text
src/signal_diag/
├── signal/
│   ├── models.py
│   ├── exceptions.py
│   ├── factory.py
│   ├── repository.py
│   ├── segment.py
│   ├── synthetic.py
│   └── wav.py                 # Phase 5
├── dsp/
│   ├── models.py
│   ├── preprocess.py
│   ├── clipping.py
│   ├── spectrum.py
│   ├── pitch.py
│   └── harmonics.py
├── tools/
│   ├── contracts.py
│   ├── results.py
│   ├── service.py
│   ├── registry.py
│   └── evidence.py
├── agent/                     # Phase 2
│   ├── models.py
│   ├── planner.py
│   ├── runtime.py
│   ├── state.py
│   ├── policies.py
│   ├── diagnosis.py
│   └── demo.py                # Phase 2 development runner
├── rules/                     # Phase 3
│   ├── models.py
│   ├── engine.py
│   └── profiles/
├── knowledge/                 # Phase 3
│   ├── models.py
│   ├── index.py
│   └── corpus/
├── evaluation/                # Phase 4
│   ├── datasets.py
│   ├── metrics.py
│   ├── fixed_pipeline.py
│   ├── deterministic.py
│   └── real_model.py
└── app/                       # Phase 5
    ├── cli.py
    ├── api.py
    ├── reporting.py
    └── web/
```

Only directories required by the current phase are created. The tree above
defines ownership, not a requirement to scaffold empty future modules.

---

## 6. Deterministic Signal and DSP Layer

### 6.1 Canonical signal representation

Repository waveforms retain the V0.1 representation:

```text
dtype: float32
shape: (num_samples, channels)
amplitude convention: floating-point full scale (FS)
```

Integer PCM is converted to full-scale floating point. Floating-point input is
not peak-normalized. Repository insertion owns a copy; returned repository data
must not permit mutation of internal storage.

DSP functions operate on one-dimensional arrays produced by segment and channel
selection.

### 6.2 Synthetic acceptance signals

Phase 1 supplies deterministic generators for:

- clean sine;
- clipped sine;
- harmonic-distortion signal with explicit harmonic amplitude ratios;
- combined clipping and harmonic distortion;
- seeded white noise.

Ground truth records the generator, fault labels, sample parameters, and fault
parameters. Synthetic generation must not hide clipping or distortion through
per-signal peak normalization.

### 6.3 Initial DSP capabilities

The deterministic foundation provides:

- peak, RMS, and DC preprocessing/statistics needed by other algorithms;
- full-scale and sub-full-scale flat-top clipping detection;
- real-FFT spectrum analysis with relative magnitude;
- autocorrelation fundamental estimation baseline;
- harmonic peak association relative to a supported fundamental;
- a clearly defined harmonic-distortion metric, including invalid behavior when
  a stable fundamental cannot be established.

DSP result objects may contain internal arrays. Tool-facing results must not.

---

## 7. Tool, Observation, and Evidence Contracts

### 7.1 Tool result status

All Tool results use:

```text
success  computation succeeded and the result is meaningful
invalid  computation completed but the metric is not applicable or reliable
error    execution failed due to parameters, missing data, or internal failure
```

### 7.2 Initial Agent-callable tools

Phase 1 exposes compact adapters for:

- `detect_clipping`;
- `analyze_spectrum`;
- `estimate_fundamental`;
- `analyze_harmonic_distortion`.

The registry describes each tool's purpose, input schema, output schema, and
conditions under which it is useful. It does not prescribe a call order.

### 7.3 Observation

An Observation represents one completed runtime action and contains:

- observation ID;
- tool call ID;
- tool name;
- normalized arguments;
- status;
- compact output;
- warnings or error information;
- evidence IDs produced by the observation.

### 7.4 Evidence

Evidence is created deterministically by Tool adapters from DSP outputs. Each
Evidence record contains:

- evidence ID;
- source tool and call ID;
- metric name;
- scalar or compact categorical value;
- unit where applicable;
- validity status;
- optional confidence or quality indicator;
- optional segment/channel provenance.

The LLM may cite Evidence but does not create numerical Evidence. Final diagnosis
validation rejects unknown evidence IDs.

---

## 8. Hybrid Agent Architecture

### 8.1 Explicit planner boundary

The runtime depends on a model/planner protocol rather than a concrete provider:

```python
class PlannerModel(Protocol):
    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        ...
```

Required implementations:

- `RealLLMPlanner`: the product Agent path;
- `ScriptedPlanner`: a deterministic test double for runtime acceptance.

The orchestration framework and LLM provider are implementation choices behind
these contracts. They must not leak provider-specific objects into Agent state.

### 8.2 Planner context

`PlannerContext` contains only compact information needed for the next decision:

- user request;
- signal metadata summary;
- current task assessment and hypotheses;
- available tool descriptions and schemas;
- observation summaries;
- evidence records;
- tool history and stated purposes;
- warnings and recoverable errors;
- remaining tool-call and retry budgets;
- no-progress state;
- Phase 3 rule and knowledge results when available.

It never contains raw waveform samples or full spectral arrays.

### 8.3 Decisions

Phase 2 uses a discriminated decision union:

```text
AgentDecision
├── CallToolDecision
│   ├── task_assessment        # required on the initial decision
│   ├── tool_name
│   ├── arguments
│   ├── purpose
│   └── expected_evidence
└── FinishDecision
    ├── diagnosis
    ├── evidence_refs
    ├── confidence_label
    └── limitations
```

Phase 3 extends the union with deterministic actions:

```text
EvaluateRulesDecision
RetrieveKnowledgeDecision
```

The runtime validates decisions before execution. It may reject an invalid
decision, but it must not replace that decision with a hidden fixed DSP pipeline.

### 8.4 Runtime responsibilities

The Agent runtime is deterministic infrastructure. It:

- loads signal context;
- builds `PlannerContext`;
- invokes the configured planner;
- validates structured decisions;
- executes approved Tool calls;
- converts results into observations and evidence;
- maintains state and trace;
- enforces retries, budgets, duplicate-call policy, and no-progress policy;
- validates final diagnosis references;
- returns a structured terminal result.

The runtime does not choose diagnostic tools on behalf of the product Agent.

### 8.5 Scripted planner boundary

`ScriptedPlanner` returns predefined decisions and may assert that the supplied
context contains expected prior observations. It drives real runtime and DSP
execution; it does not mock numerical outputs.

It is available only through explicit test/development configuration and is not
the production fallback when a real-model call fails.

### 8.6 Real LLM planner boundary

`RealLLMPlanner` is the product path for S1. It uses structured output to:

- classify the task;
- select the first tool;
- interpret compact observations;
- decide whether another tool is justified;
- stop when evidence is sufficient;
- form an evidence-grounded diagnosis.

The runtime treats malformed output, provider failure, and exhausted retries as
explicit terminal or recoverable states. It never silently switches to the
scripted planner.

---

## 9. Agent State and Control Flow

### 9.1 State ownership

The runtime owns mutable execution state. Planner inputs and decisions are
validated immutable snapshots. The state contains:

- run ID and signal ID;
- user request;
- signal metadata summary;
- task assessment;
- hypotheses;
- observations;
- evidence;
- rule results and knowledge references when available;
- tool-call history;
- planner attempt count;
- tool-call count;
- no-progress count;
- warnings and errors;
- termination reason;
- final structured diagnosis.

### 9.2 Phase 2 control flow

```text
load_context
    ↓
build_planner_context
    ↓
planner_decide
    ↓
validate_decision
    ├── invalid decision → retry policy / terminal error
    ├── call tool
    │      ↓
    │   execute_tool
    │      ↓
    │   record_observation_and_evidence
    │      ↓
    │   progress_check
    │      ↓
    │   build_planner_context
    └── finish
           ↓
       validate_diagnosis
           ↓
        terminal result
```

### 9.3 Progress definition

An iteration makes progress when it adds at least one of:

- a new successful or scientifically invalid observation from a non-equivalent
  call;
- new deterministic evidence;
- a new rule result;
- a new knowledge reference relevant to an identified explanation gap;
- a valid terminal diagnosis.

Malformed decisions, rejected equivalent calls, and repeated failures without a
changed purpose do not count as progress. A first scientifically invalid result
does count as information; repeating the same invalid call does not.

### 9.4 Required termination controls

Configuration defines finite values for:

- maximum Tool calls;
- maximum planner retries for malformed or failed model responses;
- maximum consecutive no-progress iterations.

Exhaustion returns an explicit termination reason. If evidence cannot support a
diagnosis, the terminal diagnosis is `inconclusive`, not a guessed fault.

---

## 10. Diagnosis Contract

A structured diagnosis contains:

- run ID;
- task type;
- outcome: `supported_fault`, `no_supported_fault`, or `inconclusive`;
- one or more diagnosis claims;
- evidence references for every claim;
- applicable deterministic rule references;
- knowledge references used only for explanation;
- confidence label with no probability interpretation unless calibrated;
- limitations;
- termination reason;
- Tool-call summary.

The validator enforces:

- every numerical claim is backed by deterministic evidence;
- every evidence reference exists in the current run;
- rule conclusions cite the rule evaluation that produced them;
- knowledge citations do not substitute for signal evidence;
- a diagnosis with unsupported claims cannot be returned as successful.

---

## 11. Phase 1 — Deterministic Signal-Analysis Foundation

### Objective

Build a trustworthy Signal → DSP → Tool execution chain for S1.

### Exact scope

- canonical signal models, construction, repository, segmentation, and channels;
- deterministic synthetic cases and ground truth;
- clipping, spectrum, fundamental, harmonics, and distortion analysis;
- compact Tool contracts;
- observation and evidence creation at the Tool boundary;
- deterministic unit and Tool integration tests.

### Non-goals

- Agent runtime or LLM;
- rules or RAG;
- WAV input;
- API, UI, reporting, deployment;
- unsupported fault families such as drift, transient noise, or hardware cause
  diagnosis.

### Acceptance criteria

- clean sine is not falsely identified as clipping;
- full-scale and sub-full-scale clipping are detected;
- harmonic components and the defined distortion metric match synthetic ground
  truth within documented tolerance;
- stable fundamental evidence is available when required;
- silence and seeded noise do not receive fabricated F0 or THD values;
- combined synthetic faults retain both ground-truth labels;
- DSP functions do not mutate input;
- Tool output contains no raw waveform or full FFT arrays;
- all Phase 1 required tests pass without skip or xfail.

### Dependency

None.

---

## 12. Phase 2 — Minimal End-to-End Distortion-Diagnosis Agent

### Objective

Complete S1 with a real-LLM product planner and a deterministic scripted planner
for runtime acceptance.

### Exact scope

- planner protocol and both implementations;
- typed context and decision union;
- deterministic Agent runtime and state;
- graph routing, Tool execution, observation propagation, evidence validation;
- retry, invalid, error, maximum-call, duplicate-call, and no-progress policies;
- a command-line development runner that prints the synthetic S1 trace;
- separate deterministic and real-model validation entry points.

### Non-goals

- rules and RAG;
- multi-Agent architecture;
- open-domain diagnosis;
- WAV upload;
- CI dependence on a real model;
- scripted planner as the product Agent or automatic fallback.

### Acceptance criteria

Deterministic system acceptance uses `ScriptedPlanner` to verify:

- graph routing and state transitions;
- real Tool and DSP execution;
- observation and evidence propagation;
- retry, invalid, and error handling;
- maximum Tool-call termination;
- no-progress termination;
- equivalent-call rejection;
- complete reproducible S1 paths for clipping, harmonic distortion, combined
  faults, clean input, and inconclusive input.

Small-scale real-model behavior checks use `RealLLMPlanner` on the initial S1
cases, without gating CI, to measure:

- first-tool selection;
- observation-driven replanning;
- unnecessary Tool calls;
- stopping timing;
- evidence grounding;
- final diagnosis quality.

The product demonstration must run through `RealLLMPlanner` and show its actual
trace. Systematic repeated-run evaluation across a versioned dataset belongs to
Phase 4.

### Dependency

Phase 1 Tool contracts, deterministic analyses, and synthetic acceptance cases.

---

## 13. Phase 3 — Deterministic Rules and Small Knowledge/RAG Layer

### Objective

Separate numerical observations, configured judgments, and explanatory knowledge.

### Exact scope

- versioned rule profiles for supported clipping and harmonic metrics;
- deterministic PASS, FAIL, and NOT_APPLICABLE results;
- rule outputs containing observed value, comparator, threshold, profile version,
  and evidence references;
- a small curated local Markdown corpus;
- deterministic keyword/tag retrieval with document and chunk references;
- planner decisions for rule evaluation and knowledge retrieval;
- diagnosis output that distinguishes evidence, rule judgment, and explanation.

The first knowledge implementation does not require embeddings or a vector
database. A later replacement may preserve the same retrieval-result contract.

### Non-goals

- large-scale knowledge ingestion;
- network search;
- automatic standards collection;
- LLM-generated thresholds;
- treating demonstration thresholds as industry standards;
- using RAG to calculate DSP metrics.

### Acceptance criteria

- identical observations and rule configuration produce identical results;
- invalid metrics produce NOT_APPLICABLE rather than PASS;
- rule decisions trace to configuration version and evidence IDs;
- knowledge results trace to document and chunk IDs;
- missing knowledge does not alter deterministic numerical conclusions;
- scripted tests reproduce rule and retrieval branches;
- real-model rule/retrieval behavior is evaluated outside CI.

### Dependency

Phase 2 runtime, decision, evidence, and diagnosis contracts; Phase 1 metrics.

---

## 14. Phase 4 — Evaluation and Agent Versus Fixed Pipeline

### Objective

Measure deterministic correctness and real-model behavior on reproducible ground
truth, then compare the Agent with an honest fixed-pipeline baseline.

### Exact scope

- a versioned synthetic evaluation manifest;
- clean, clipping, harmonic, combined, boundary-severity, and invalid/noise cases;
- separate development and held-out evaluation cases;
- DSP accuracy and invalid-result metrics;
- deterministic scripted-runtime coverage and trace validation;
- real-model behavioral metrics;
- a fixed pipeline using the same DSP Tools and rules;
- JSON, CSV, and human-readable evaluation reports.

Real-model metrics include:

- first-tool selection accuracy;
- observation-driven replanning success;
- unnecessary Tool-call rate;
- average Tool calls;
- stopping quality;
- final diagnosis accuracy/F1;
- evidence-grounding rate;
- unsupported-claim rate;
- latency, token usage, and estimated cost where available.

This phase expands the small Phase 2 real-model checks into a versioned,
repeatable evaluation campaign. It does not redefine the Phase 2 runtime.

### Non-goals

- assuming the Agent must beat the fixed pipeline;
- using stochastic LLM behavior as a CI gate;
- hiding failed cases;
- tuning repeatedly on held-out evaluation cases;
- claiming production-grade accuracy from synthetic data.

### Acceptance criteria

- the dataset can be reconstructed from its manifest and seeds;
- Agent and baseline use identical cases, DSP Tools, and rules;
- deterministic acceptance is reproducible in CI;
- real-model results report repeated-run variation and failure cases;
- the comparison reports both quality and execution efficiency;
- conclusions remain valid if the fixed pipeline is more stable or accurate.

### Dependency

Stable Phase 1–3 contracts and end-to-end diagnosis output.

---

## 15. Phase 5 — Presentation Engineering

### Objective

Package the validated system as a demonstrable application without duplicating
diagnostic logic.

### Exact scope

- WAV ingestion and PCM full-scale conversion;
- CLI, HTTP API, and a small Web UI as adapters to the same runtime;
- synthetic-case selector and WAV upload;
- real Agent execution trace display;
- observation, evidence, rule, and knowledge views;
- structured JSON and human-readable HTML reports;
- evaluation-summary presentation.

Product configuration defaults to `RealLLMPlanner`. `ScriptedPlanner` requires an
explicit test/development configuration and is never a silent production
fallback.

### Non-goals

- authentication, payment, or multi-tenancy;
- real-time streaming audio;
- microservices or Kubernetes;
- a complex frontend framework solely for appearance;
- reimplementing DSP or Agent decisions in the UI;
- PDF as a first presentation gate.

### Acceptance criteria

- synthetic and WAV S1 inputs use the same core diagnosis path;
- the product Demo calls a real LLM and displays the actual dynamic trace;
- CLI, API, and UI do not duplicate runtime logic;
- scripted API integration tests remain deterministic;
- raw waveform and full FFT data never enter model context;
- every report claim traces to evidence, rules, and optional knowledge sources;
- one documented local command sequence starts and demonstrates the system.

### Dependency

Phase 4 evaluation has established the supported behavior and known limitations.

---

## 16. Two Validation Layers

### 16.1 Deterministic system acceptance

This layer runs in CI and uses `ScriptedPlanner`. It verifies:

- routing;
- state transitions;
- real Tool execution;
- observation propagation;
- retry, invalid, and error handling;
- Tool-call and no-progress termination;
- evidence validation;
- complete reproducible S1 state-machine paths.

It proves the Agent infrastructure behaves correctly. It does not prove that a
real LLM makes good decisions.

### 16.2 Real-model behavior evaluation

This layer explicitly uses `RealLLMPlanner` and remains outside required CI. It
evaluates:

- first-tool choice;
- replanning after observations;
- unnecessary calls;
- stopping timing;
- final diagnosis quality;
- evidence grounding and unsupported claims.

It records model identity, configuration, prompt version, case version, and run
time so results are interpretable. Stochastic variation is reported, not hidden.

---

## 17. S1 Acceptance Matrix

The matrix freezes expected outcomes, not an exact Tool sequence.

| Case | Ground truth | Required final behavior | Dynamic-path expectation |
|---|---|---|---|
| S1-CLEAN | no supported fault | `no_supported_fault` or justified `inconclusive` | collect enough negative evidence; do not claim a fault |
| S1-CLIP-FS | full-scale clipping | clipping claim with clipping evidence | stop once sufficient clipping evidence exists; extra unrelated calls are penalized |
| S1-CLIP-SUBFS | sub-full-scale flat top | clipping claim with flat-top evidence | threshold-only detection is insufficient |
| S1-HARM | harmonic distortion | harmonic-distortion claim with fundamental/harmonic evidence | continue after irrelevant or negative evidence when justified |
| S1-COMBINED | clipping and harmonic distortion | both supported claims for full-credit evaluation | gather evidence for both without enforcing a fixed order |
| S1-NOISE | metric not reliably applicable | `inconclusive` without fabricated F0/THD | handle invalid observations and terminate safely |

Scripted acceptance provides at least one reproducible legal route for each case.
Real-model evaluation may take a different legal route and is scored on outcome,
evidence, efficiency, and stopping behavior.

---

## 18. Fixed Pipeline Baseline

The Phase 4 baseline is intentionally not an Agent. It executes a documented,
fixed set of applicable distortion-analysis Tools and applies the same rule
engine used by the Agent.

The comparison asks:

- Does dynamic selection preserve diagnosis quality?
- Does it reduce unnecessary Tool calls?
- Does it introduce stochastic failures or unsupported claims?
- In which closed cases is the fixed pipeline preferable?

No architecture decision assumes the Agent wins this comparison.

---

## 19. V0.1 to V0.2 Contract Changes

V0.2 preserves useful V0.1 decisions:

- canonical float32 `(N, C)` repository representation;
- no hidden peak normalization;
- immutable repository behavior;
- one-dimensional DSP inputs;
- compact Tool outputs;
- `success`, `invalid`, and `error` semantics;
- deterministic numerical computation.

V0.2 intentionally changes or extends the previous design:

1. Phase 1 adds harmonic-distortion synthetic data, DSP, and Tool support because
   S1 cannot be accepted with clipping, FFT, and F0 alone.
2. Tool results become observation/evidence-ready and receive traceable IDs.
3. Phase 2 explicitly adds the Agent runtime instead of postponing all Agent work
   until an unspecified later phase.
4. The model boundary supports a real product planner and a scripted test double.
5. The Agent is tested at the state-machine level without making CI depend on a
   stochastic model.
6. Rule and knowledge actions are separate from DSP actions.
7. Evaluation and a fixed baseline are first-class project phases.
8. WAV, API, UI, and reports remain presentation work after deterministic and
   Agent behavior are validated.

The detailed V0.2 public Python signatures are frozen in a subsequent contract
document after this architecture is approved. Existing V0.1 public names are not
silently changed during implementation.

---

## 20. Contract Freeze Strategy

The project does not freeze every future interface at once.

- Before Phase 1 implementation, freeze Signal, DSP, Tool, Observation, and
  Evidence contracts needed by Phase 1 and Phase 2.
- Before Phase 2 implementation, freeze Planner, Decision, State, Runtime, and
  Diagnosis contracts.
- Before Phase 3, freeze Rule and Knowledge result contracts.
- Before Phase 4, freeze dataset manifests and evaluation result schemas.
- Before Phase 5, freeze external CLI/API/report contracts.

Each contract revision records:

- reason for the change;
- affected modules;
- migration impact;
- test impact;
- approval status.

This strategy keeps the full direction coherent without creating speculative
interfaces for unimplemented UI, storage, or deployment concerns.

---

## 21. Delivery and Verification Discipline

Every implementation unit follows test-driven development:

1. write or confirm a focused behavioral test;
2. run it and confirm the expected failure;
3. implement the smallest correct behavior;
4. run the focused test;
5. run the complete current-phase suite;
6. refactor only while tests remain green;
7. review contract coverage before declaring the unit complete.

Completion reports state exactly which tests ran and list remaining warnings,
failures, unsupported cases, and contract concerns.

No Phase is reported complete when a required acceptance test is skipped, xfailed,
or failing.

---

## 22. Explicitly Deferred Decisions

The following decisions are deferred to the relevant phase contract because they
do not change the architecture boundary:

- the concrete LLM provider and model used by the first `RealLLMPlanner`;
- the orchestration library, provided it preserves the runtime and planner
  contracts;
- the exact harmonic integration method and numerical tolerances, which must be
  defined and verified in the Phase 1 DSP contract;
- the concrete HTTP/UI technology, selected only in Phase 5;
- optional embedding retrieval after deterministic local retrieval is evaluated.

These are deliberate phase-local choices, not permission to change cross-layer
responsibilities.

---

## 23. Architecture Definition of Done

This architecture is ready for implementation planning when:

1. S1 and its supported diagnosis space are approved;
2. the modular-monolith boundaries are approved;
3. the hybrid real/scripted planner boundary is approved;
4. the five phases and their acceptance criteria are approved;
5. V0.1-to-V0.2 changes are accepted;
6. Phase 1–2 public contracts are written and reviewed.

After approval, the next artifacts are:

1. `CONTRACTS_V0_2.md` for Phase 1–2 public contracts;
2. `TEST_PLAN_V0_2.md` for deterministic and real-model validation;
3. a task-level Phase 1 implementation plan.

Implementation code starts only after those artifacts are reviewed.
