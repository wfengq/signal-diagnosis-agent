# Signal Diagnosis Agent — Project Specification

**Document:** `PROJECT_SPEC.md`  
**Version:** `0.1`  
**Status:** Phase 1 specification  
**Project name:** Signal Test and Fault Diagnosis Agent  
**Chinese name:** 智能信号测试与故障诊断 Agent

---

# 1. Purpose

This repository implements a signal test and fault diagnosis system in which:

- deterministic DSP code performs numerical signal analysis;
- an Agent later understands the user's diagnostic objective;
- the Agent dynamically selects appropriate DSP tools;
- structured observations are returned to the Agent;
- deterministic rules evaluate configured limits;
- the Agent produces an evidence-based diagnosis;
- the system produces a traceable structured report.

The intended long-term workflow is:

```text
User diagnostic request
        ↓
Task understanding
        ↓
Agent planning
        ↓
DSP tool selection
        ↓
Tool execution
        ↓
Structured observation
        ↓
Replan if needed
        ↓
Rule evaluation
        ↓
Diagnosis
        ↓
Structured report
```

Conceptually:

```text
Plan
↓
Tool
↓
Observation
↓
Replan
↓
Diagnosis
↓
Report
```

Phase 1 does **not** implement the Agent loop.

Phase 1 establishes the deterministic signal-processing foundation on which the Agent will later depend.

---

# 2. Core Design Principle

The most important architectural rule is:

> The Agent decides how to analyze; deterministic DSP code calculates the numerical results.

The LLM must not calculate or guess:

- FFT values;
- RMS;
- F0;
- SNR;
- THD;
- harmonic levels;
- clipping ratios;
- frequency drift;
- test thresholds;
- Pass/Fail numerical comparisons.

These values must come from deterministic Python code or explicitly configured test rules.

The Agent may later:

- interpret the user's request;
- select a tool;
- choose valid tool parameters;
- inspect structured results;
- decide whether more evidence is needed;
- form an evidence-based diagnostic explanation;
- provide recommendations.

---

# 3. Project Scope

The project is intended to support sampled time-domain signals.

The architecture should remain general enough for:

```text
Signal
├── Audio
├── Sensor
└── Generic sampled waveform
```

However, the initial implementation should use simple audio/test-waveform cases because they provide controllable ground truth.

Initial signal sources include:

- WAV;
- PCM;
- CSV waveform data;
- synthetically generated signals.

Phase 1 only needs the internal signal representation and synthetic signal generation.

File loaders may be added after the Phase 1 contracts are stable.

---

# 4. Phase 1 Objective

Phase 1 establishes the deterministic execution chain:

```text
Synthetic Signal
        ↓
SignalRecord
        ↓
SignalRepository
        ↓
Segment / Channel Selection
        ↓
DSP Algorithm
        ↓
SignalToolService
        ↓
Structured ToolResult
```

Phase 1 must implement:

1. canonical signal data models;
2. signal construction/factory logic;
3. in-memory signal repository;
4. time-range extraction;
5. channel selection and mixdown;
6. synthetic sine generation;
7. synthetic clipped-sine generation;
8. deterministic seeded white-noise generation;
9. clipping analysis;
10. FFT analysis;
11. autocorrelation F0 estimation baseline;
12. compact Tool input/output contracts;
13. `SignalToolService` wrappers;
14. deterministic unit and integration tests.

---

# 5. Phase 1 Non-Goals

The following must **not** be implemented during Phase 1 unless explicitly requested:

- LangGraph;
- LangChain Agent runtime;
- OpenAI Agents SDK;
- Claude API;
- other LLM APIs;
- RAG;
- embeddings;
- vector databases;
- MCP;
- multi-Agent architecture;
- FastAPI;
- SSE;
- React;
- frontend UI;
- authentication;
- PostgreSQL;
- Redis;
- persistent database storage;
- Docker orchestration;
- Kubernetes;
- cloud deployment;
- PDF reporting;
- HTML reporting;
- semiconductor ATE integration;
- real oscilloscope integration;
- real instrument control.

The project must not expand merely to make the résumé look more sophisticated.

---

# 6. What the MVP Is Not

The MVP is not:

```text
an LLM chatbot that comments on audio;
```

it is not:

```text
a RAG demo with signal-processing vocabulary;
```

it is not:

```text
a semiconductor tester;
```

it is not:

```text
a speech recognition product;
```

and it is not:

```text
a fixed pipeline disguised as an Agent.
```

The long-term target is:

> A Signal Diagnosis Agent that dynamically selects deterministic DSP tools according to the user's objective and previous observations.

---

# 7. Architectural Layers

The repository is divided into four conceptual layers.

## 7.1 `signal/`

Responsibilities:

- canonical waveform representation;
- metadata;
- signal construction;
- repository storage;
- synthetic signal generation;
- time-range extraction;
- channel selection.

The `signal/` package must not depend on:

- LangGraph;
- LLM SDKs;
- Agent code.

---

## 7.2 `dsp/`

Responsibilities:

- deterministic numerical analysis;
- clipping detection;
- spectrum analysis;
- pitch/F0 estimation;
- later:
  - statistics;
  - SNR;
  - THD;
  - harmonic analysis;
  - frequency drift.

The `dsp/` package:

- receives numeric arrays;
- returns deterministic Python result models;
- may return large numeric arrays internally;
- must be independently unit-testable.

The `dsp/` package must not know:

- what an Agent is;
- what LangGraph is;
- what the user's natural-language question was.

---

## 7.3 `tools/`

Responsibilities:

- expose compact structured interfaces suitable for Agent tool calling;
- retrieve the selected signal from the repository;
- extract the requested segment/channel;
- call the DSP implementation;
- convert DSP results into compact Pydantic outputs;
- return standardized `ToolResult` objects.

The Tool layer must not expose raw waveforms to an LLM.

The Tool layer must not return full FFT arrays to an Agent.

---

## 7.4 `agent/`

Not part of Phase 1.

Later responsibilities:

- task understanding;
- planning;
- tool selection;
- observation processing;
- replanning;
- diagnosis;
- evidence references;
- termination decisions.

Expected future execution model:

```text
load_context
      ↓
planner
      ↓
execute_tool
      ↓
process_observation
      ↓
rule_check
      ↓
control_gate
      ↓
planner
      ↓
...
      ↓
diagnosis
      ↓
validate_diagnosis
      ↓
build_report
```

Only `planner` and `diagnosis` are expected to require an LLM.

---

# 8. Dependency Direction

The conceptual dependency direction is:

```text
signal
  ↓
dsp
  ↓
tools
  ↓
agent
```

More precisely:

- DSP may use signal-domain shared models only where necessary.
- Tools may use both Signal and DSP packages.
- Agent may use Tool contracts.
- Signal and DSP must never import Agent modules.

Circular dependencies are not allowed.

---

# 9. Canonical Signal Representation

Repository waveform storage must use:

```text
dtype:
float32

shape:
(num_samples, channels)
```

Examples:

Mono:

```text
(96000, 1)
```

Stereo:

```text
(96000, 2)
```

Signals must not use inconsistent representations such as sometimes `(N,)` and sometimes `(N, 1)` inside the repository.

DSP algorithms normally receive a one-dimensional extracted waveform:

```text
(N,)
```

Channel/segment conversion happens before DSP execution.

---

# 10. Amplitude Representation

Integer PCM data is converted into floating-point full-scale representation.

For signed 16-bit PCM, approximately:

```text
-32768 → -1.0
32767  → +0.99997
```

The implementation must **not** peak-normalize individual signals.

For example:

```text
input peak = 0.5
```

must remain approximately:

```text
output peak = 0.5
```

It must not automatically become:

```text
1.0
```

because peak normalization would destroy information needed for amplitude and clipping analysis.

---

# 11. Signal Immutability

Signals stored in the repository are treated as immutable source data.

A DSP function must not modify repository data in place.

Repository-owned arrays should therefore be:

- copied when inserted;
- configured as non-writeable.

DSP code that needs mutable working data must operate on a copy or newly created array.

---

# 12. Synthetic Data

Synthetic signals are a first-class part of the project.

They serve two purposes:

1. deterministic DSP verification;
2. later Agent evaluation with known ground truth.

Phase 1 generators:

```text
generate_sine
generate_clipped_sine
generate_white_noise
```

Future generators may include:

```text
generate_noisy_sine
generate_harmonic_distortion
generate_frequency_drift
generate_amplitude_abnormality
```

Synthetic generation must record ground-truth parameters.

Example:

```json
{
  "generator": "clipped_sine",
  "fault_type": "clipping",
  "parameters": {
    "frequency_hz": 200.0,
    "input_amplitude": 0.9,
    "clip_level": 0.5
  }
}
```

Random generation must always be reproducible through an explicit seed.

---

# 13. Clipping Analysis

Phase 1 clipping analysis must detect at least two cases.

## 13.1 Near-full-scale saturation

Example:

```text
abs(x) >= 0.99 FS
```

for consecutive samples.

## 13.2 Flat-top clipping

The algorithm should also identify repeated or nearly repeated high-amplitude samples that form flat tops, even when clipping occurs below full scale.

Example:

```text
input sine amplitude = 0.9
clip level = 0.5
```

A detector based only on `abs(x) >= 0.99` would miss this failure.

Therefore Phase 1 clipping detection combines:

```text
full-scale saturation
+
flat-top detection
```

The algorithm does not need to solve every clipping morphology.

Future improvements may include:

- asymmetric clipping;
- soft clipping;
- derivative-based saturation analysis;
- more robust plateau merging.

---

# 14. FFT Analysis

Phase 1 FFT analysis must provide:

- frequency resolution;
- dominant frequency;
- relative spectral magnitude;
- spectral centroid;
- strongest spectral peaks.

Full FFT arrays may remain inside the DSP result for plotting or internal analysis.

Tool outputs must only expose compact summaries.

Phase 1 uses relative magnitude:

```text
strongest FFT bin = 0 dB
```

Other bins are relative to the strongest component.

This is not claimed to be calibrated dBFS or physical SPL.

The output field should therefore use language such as:

```text
relative_magnitude_db
```

instead of ambiguous absolute-level terminology.

---

# 15. F0 Baseline

Phase 1 F0 estimation uses:

```text
autocorrelation
```

with:

- DC removal;
- windowing;
- FFT-based autocorrelation;
- lag-range restriction using `fmin_hz` and `fmax_hz`;
- normalized autocorrelation confidence;
- optional parabolic lag interpolation;
- voicing threshold.

This is explicitly a **baseline**, not the final pitch algorithm.

Expected strengths:

- pure sine waves;
- stable periodic test signals.

Expected weaknesses:

- complex speech;
- noisy speech;
- octave errors;
- strong harmonic interference;
- rapidly changing pitch.

Future comparisons may include:

- YIN;
- pYIN;
- research pitch-detection methods.

The algorithm must be allowed to return:

```text
unvoiced / invalid
```

instead of fabricating an F0 value.

---

# 16. Tool Contract Philosophy

DSP results and Agent Tool results are intentionally different.

Example:

```text
DSP FFT result
```

may contain:

```text
100,000 frequency bins
100,000 spectral values
```

while:

```text
Agent FFT Tool output
```

should contain only:

```text
frequency resolution
dominant frequency
spectral centroid
top spectral peaks
```

The LLM does not need raw arrays.

The Tool interface should remain:

- compact;
- structured;
- typed;
- traceable.

---

# 17. Standard Tool Status

Every Tool result uses one of:

```text
success
invalid
error
```

## `success`

The computation succeeded and the result is meaningful.

## `invalid`

The software operated correctly, but the metric is not meaningfully applicable.

Examples:

- no reliable periodic component for F0;
- THD requested on a signal without a stable fundamental.

## `error`

The operation failed because of:

- invalid parameters;
- missing signal;
- internal execution failure;
- corrupted data;
- unrecoverable numerical error.

A scientifically invalid metric must not be mislabeled as a software error.

---

# 18. Numerical Honesty

The system must not claim greater precision than its algorithms support.

Examples:

Bad:

```text
The exact fundamental frequency is 200.000000 Hz.
```

when FFT resolution is 1 Hz.

Better:

```text
Estimated dominant frequency ≈ 200 Hz.
```

Similarly:

- estimated SNR must be identified as estimated;
- autocorrelation F0 confidence must not be interpreted as a probability unless explicitly calibrated;
- relative FFT magnitude must not be called absolute dBFS unless calibrated.

---

# 19. Rule Engine Boundary

The future Rule Engine is separate from DSP and the Agent.

Example:

```text
DSP:
THD = 5.7 %

Rule profile:
THD <= 5.0 %

Rule Engine:
FAIL
```

The Agent may explain this result but must not invent the threshold.

Initial thresholds used for demonstrations are project configuration values unless explicitly sourced from a documented external standard.

They must not be described as industry-standard requirements without evidence.

---

# 20. Agent Safety Boundary

Future Agent rules:

- never receive raw waveform arrays;
- never compute DSP values itself;
- never invent thresholds;
- never claim unsupported hardware causes;
- never repeat tools without a changed purpose or parameter set;
- use structured output;
- terminate when evidence is sufficient;
- return inconclusive when evidence is insufficient.

A later diagnosis should be traceable to structured evidence.

---

# 21. Evaluation Philosophy

The long-term project should evaluate both DSP and Agent behavior.

DSP evaluation may include:

- Accuracy;
- Precision;
- Recall;
- F1;
- numerical estimation error.

Agent evaluation may include:

- tool-selection correctness;
- parameter-extraction correctness;
- diagnosis correctness;
- task-completion rate;
- average tool calls;
- invalid tool-call rate.

A future experiment should compare:

```text
Agent dynamic analysis
vs
Fixed analysis pipeline
```

The goal is not to guarantee that the Agent always wins.

A valid engineering conclusion may be:

- a fixed pipeline is more predictable in a closed task;
- an Agent better supports open natural-language goals and selective tool execution.

---

# 22. Phase 1 Definition of Done

Phase 1 is complete only when:

1. the package structure exists;
2. canonical signal models are implemented;
3. repository behavior is implemented;
4. synthetic generators are implemented;
5. clipping analysis is implemented;
6. FFT analysis is implemented;
7. autocorrelation F0 baseline is implemented;
8. Tool wrappers exist;
9. all required Phase 1 tests pass;
10. no required test is skipped or marked xfail;
11. deterministic test data uses explicit seeds;
12. frozen public contracts remain unchanged unless explicitly approved;
13. no Agent/LLM functionality has been added accidentally.

---

# 23. Recommended Phase 1 Implementation Order

```text
1. project structure
2. signal models
3. signal factory
4. repository
5. segment/channel extraction
6. synthetic sine
7. clipped sine
8. white noise
9. clipping DSP
10. clipping Tool
11. FFT DSP
12. FFT Tool
13. autocorrelation F0 DSP
14. F0 Tool
15. complete deterministic validation suite
```

Recommended incremental commit structure:

```text
chore: initialize project structure

feat(signal): add canonical signal models and repository

feat(signal): add synthetic signal generators

feat(dsp): implement clipping analysis

feat(tools): expose clipping analysis tool

feat(dsp): implement FFT analysis

feat(tools): expose FFT analysis tool

feat(dsp): implement autocorrelation F0 baseline

feat(tools): expose F0 estimation tool

test: add deterministic DSP validation suite
```

Commits are optional and should not be created automatically without user permission.

---

# 24. Phase 2 Preview

Phase 2 may add deterministic tools for:

```text
signal_statistics
calculate_snr
calculate_thd
harmonic_analysis
detect_frequency_drift
```

and synthetic generators for:

```text
noisy sine
harmonic distortion
frequency drift
amplitude abnormality
```

The Agent layer still does not need to be implemented until the deterministic tools are sufficiently reliable.

---

# 25. Phase 3 Preview

Later Agent implementation may use LangGraph with a graph similar to:

```text
START
  ↓
load_context
  ↓
planner
  ↓
execute_tool
  ↓
process_observation
  ↓
rule_check
  ↓
control_gate
  ↓
planner / diagnosis
  ↓
validate_diagnosis
  ↓
build_report
  ↓
END
```

The planned control limits are approximately:

```text
MAX_TOOL_CALLS = 8
MAX_RETRIES = 2
MAX_NO_PROGRESS = 2
```

These values are not part of Phase 1.

---

# 26. Project Principle

When choosing between:

```text
more impressive-looking architecture
```

and:

```text
a smaller implementation that is correct,
testable, explainable and reproducible
```

choose the second.

Every implemented capability should be understandable from:

- source code;
- tests;
- deterministic inputs;
- reproducible outputs.