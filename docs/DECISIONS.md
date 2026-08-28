# Architecture and Development Decisions

**Status:** Active  
**Current architecture version:** V0.2  
**Last updated:** 2026-08-28  

This file records approved decisions that affect implementation. Historical V0.1
documents are preserved under `docs/archive/v0.1/`.

## D001 — Use a modular monolith

**Decision:** Organize the project as one Python package with strict dependency
boundaries rather than graph-first scaffolding or separate services.

**Direction:**

```text
signal → dsp → tools → rules/knowledge → agent → evaluation → app
```

Only modules required by the current phase are created.

## D002 — Implement the project in five gated phases

**Decision:** Deliver in this order:

1. deterministic signal-analysis foundation;
2. minimal end-to-end distortion-diagnosis Agent;
3. deterministic rules and small knowledge/RAG;
4. evaluation and Agent-versus-fixed-pipeline comparison;
5. API, UI, and reporting.

Later phases do not begin before the previous phase passes its required tests.

## D003 — Freeze S1 as the first end-to-end scenario

**Decision:** Scenario S1 asks why a synthetic periodic signal, and later a WAV
file, sounds distorted.

The initial supported diagnosis space is clipping, harmonic distortion, combined
distortion, no supported fault, and inconclusive. Fundamental evidence is
collected only when it supports the diagnosis.

## D004 — Dynamic tool selection is required

**Decision:** S1 does not require a fixed clipping → FFT → F0 → THD pipeline. The
product Agent selects the first Tool, inspects structured observations, replans
when justified, and stops when evidence is sufficient.

A fixed pipeline exists only as the Phase 4 comparison baseline.

## D005 — Use a Hybrid planner boundary

**Decision:** `PlannerModel` is the explicit model boundary.

- `RealLLMPlanner` is the product Agent path.
- `ScriptedPlanner` is a deterministic test double for runtime acceptance.
- Product failure never silently falls back to `ScriptedPlanner`.
- Required CI does not depend on stochastic LLM behavior.

## D006 — Keep numerical computation deterministic

**Decision:** Raw waveform and full FFT arrays never enter model context. DSP
code alone calculates clipping, spectrum, fundamental, harmonic, and THD
metrics. LLM output cannot create numerical Evidence or invent thresholds.

## D007 — Make Evidence traceability a Phase 1 capability

**Decision:** Tool adapters create compact deterministic Evidence with source
Tool and call IDs. Every supported diagnosis claim must cite Evidence from the
same run.

## D008 — Add harmonic distortion to Phase 1

**Decision:** V0.2 Phase 1 includes harmonic and combined synthetic generators,
harmonic association, THD measurement, and an Agent-facing harmonic-distortion
Tool. Clipping, FFT, and F0 alone cannot accept S1.

## D009 — Separate deterministic acceptance from real-model evaluation

**Decision:**

- T001–T092 are deterministic required acceptance tests.
- T001–T063 define Phase 1 completion.
- T064–T092 define Phase 2 runtime/S1 deterministic completion.
- R001–R006 measure real-model behavior outside CI.

## D010 — V0.2 supersedes unreleased V0.1 public names

**Decision:** Preserve V0.1 documents as history, but implement only approved
V0.2 contracts. Do not add compatibility aliases for unreleased V0.1 Tool names
or the single-value `fault_type` model.

## D011 — Start knowledge retrieval small and deterministic

**Decision:** Phase 3 begins with curated local Markdown plus deterministic
keyword/tag retrieval. Embeddings and vector databases are optional later
changes, not initial requirements.

## D012 — Presentation engineering comes last

**Decision:** WAV upload, API, UI, and HTML reporting are Phase 5 adapters over
the validated core. They must not duplicate DSP, rules, or Agent runtime logic.

## D013 — Preserve truthfulness of project claims

**Decision:** The project remains planned or partially implemented until its
actual code, tests, evaluation, and Demo exist. Synthetic signals are described
as synthetic and must not be presented as real chip or production test data.

## D014 — Freeze Phase 3 rules and knowledge contracts

**Decision:** OQ-001 is approved. `CONTRACTS_V0_2.md` §32–§40 and
`TEST_PLAN_V0_2.md` T093–T124 are the frozen Phase 3 implementation and
acceptance authority.

Phase 3 uses deterministic rule profiles, keyword/tag knowledge retrieval,
optional injected runtime dependencies, and independent limits of four rule
evaluations and four knowledge retrievals per run. Phase 2-only runtime
construction remains compatible. The separate OQ-003 profile decision is
recorded in D015.

## D015 — Approve the S1 demonstration rule profile

**Decision:** OQ-003 is approved. The first profile is
`profile_s1_distortion`, version `1.0.0-demo`, with comparator expressions
interpreted as PASS conditions:

- `clipping_detected eq false`;
- `clipping_ratio lte 0.01`;
- `flat_top_detected eq false`;
- harmonic-analysis `valid eq true`;
- `thd_percent lte 5.0`, unit `%`.

These values separate the accepted synthetic S1 fixtures and are explicitly
demonstration limits, not industry standards. Changing any comparator or
threshold requires a new profile version. Boundary tests cover values below,
equal to, and above the 1% and 5% thresholds.

## D016 — Define V0.2 as the first resume-grade vertical slice

**Decision:** The long-term project vision remains an extensible Signal Test and
Fault Diagnosis Agent for audio, sensor, and generic sampled waveforms. V0.2 is
the first complete, resume-grade vertical slice of that platform; it does not
redefine the whole project as S1-only.

V0.2 completion includes the full S1 distortion-diagnosis path: Phase 3
deterministic rules and knowledge, Phase 4 versioned evaluation plus an
Agent-versus-fixed-pipeline comparison, and Phase 5 WAV/API/UI/reporting
adapters. The product path uses a real LLM; deterministic acceptance uses an
injected scripted/fake planner.

Within V0.2, supported diagnosis remains explicitly limited to clipping,
harmonic distortion, basic supporting frequency/fundamental evidence, no
supported fault, and inconclusive outcomes. Later versioned scenarios may add
noise/SNR, frequency drift, amplitude abnormalities, PCM/CSV inputs, and sensor
waveforms. Those later capabilities receive their own contracts and tests and
must not cause speculative compatibility code in V0.2.
