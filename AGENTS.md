# AGENTS.md

## Project

This repository implements a Signal Test and Fault Diagnosis Agent.

The current development phase is V0.2 Phase 1: deterministic signal-analysis
foundation for Scenario S1.

Do not implement Phase 2 Agent/LLM runtime until all required Phase 1 tests
T001–T063 pass and Phase 1 is explicitly accepted.

## Required reading

Before modifying code, read:

- `docs/README.md`
- `docs/ARCHITECTURE_V0_2.md`
- `docs/CONTRACTS_V0_2.md`
- `docs/TEST_PLAN_V0_2.md`
- `docs/DECISIONS.md`
- `docs/superpowers/plans/2026-08-28-phase1-deterministic-foundation.md`

These documents describe approved architecture and frozen interfaces.

Files under `docs/archive/v0.1/` are historical references only. Files under
`docs/context/` are non-normative background context.

## Source of truth

The Phase 1–2 interfaces in `docs/CONTRACTS_V0_2.md` are frozen.

Do not redesign or rename public models, functions, modules, arguments, return values, or package boundaries unless the user explicitly requests a contract change.

If you discover a problem with a frozen contract:

1. Do not silently change it.
2. Explain the problem.
3. Record the proposed change in `docs/OPEN_QUESTIONS.md`.
4. Continue only when the existing contract still permits a correct implementation.

## Architectural boundaries

The complete V0.2 dependency direction is:

`signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app`

Rules:

- `signal/` owns signal representation, repositories, segmentation, and synthetic generation.
- `dsp/` owns deterministic numerical algorithms.
- `tools/` adapts DSP functions into compact structured tool results.
- `rules/` and `knowledge/` will later own deterministic thresholds and compact
  explanatory retrieval.
- `agent/` will later own Planner integration and deterministic runtime control.
- `evaluation/` will later own deterministic and real-model evaluation.
- `app/` will later own CLI/API/UI/report adapters.
- `signal/`, `dsp/`, and `tools/` must not depend on Agent or LLM frameworks.
- Raw waveform arrays must never be passed to an LLM.
- Full FFT arrays must never be passed to an LLM.
- Repository waveforms use `float32` with shape `(num_samples, channels)`.
- Repository data is immutable.
- DSP algorithms receive one-dimensional numeric arrays.
- Integer PCM is converted to full-scale floating point.
- Do not peak-normalize individual signals.
- Numerical metrics are produced only by deterministic DSP code.
- Pass/fail thresholds are not invented by an LLM.
- Tool adapters create compact deterministic Evidence.
- Every supported diagnosis claim must cite valid Evidence from the same run.
- The product Agent will use `RealLLMPlanner`; `ScriptedPlanner` is only a test
  double and is never a silent product fallback.

## Phase 1 scope

Implement only:

1. Signal models and factory.
2. `InMemorySignalRepository`.
3. Signal segmentation/channel selection.
4. Synthetic sine generation.
5. Synthetic clipped-sine generation.
6. Synthetic harmonic-distortion generation.
7. Synthetic combined clipping/harmonic generation.
8. Seeded white-noise generation.
9. Deterministic preprocessing, clipping, FFT, and autocorrelation F0 baseline.
10. Harmonic association and THD measurement.
11. Compact Tool contracts, deterministic Evidence, Tool registry, and
    `SignalToolService` wrappers for the four approved Tools.
12. Required tests T001–T063 in `docs/TEST_PLAN_V0_2.md`.

Do not add:

- LangGraph
- LLM APIs
- Phase 2 Agent runtime
- RAG
- vector databases
- FastAPI
- web frontend
- multi-agent architecture
- database persistence
- Docker infrastructure

unless explicitly requested.

The complete project architecture is approved, but that approval does not waive
the current Phase 1 gate.

## Development workflow

Use test-driven development for Phase 1.

For each behavior:

1. Add or confirm the relevant test.
2. Run the test and confirm the expected failure when appropriate.
3. Implement the smallest correct solution.
4. Run the focused test.
5. Run the complete test suite after the logical unit is complete.
6. Refactor only while tests remain green.

Do not weaken tests merely to make an implementation pass.

Tests must be deterministic. Random test data must use an explicit seed.

## Numerical correctness

Prefer simple, explainable DSP implementations over unnecessary abstractions.

Do not claim precision unsupported by the algorithm.

F0 V0.2 is explicitly an autocorrelation baseline and is not expected to solve
every pitch-tracking problem.

A metric may return an invalid/not-applicable result instead of fabricating a numeric answer.

## Change discipline

Keep changes narrowly scoped to the current task.

Do not perform unrelated refactors.

Do not add dependencies without a concrete need.

Do not add compatibility layers for hypothetical future requirements.

Do not commit or push unless explicitly requested.

## Verification

Before declaring a task complete:

- run the relevant focused tests;
- run the full Phase 1 pytest suite;
- report exactly which tests were run;
- report any remaining warnings, failures, TODOs, or contract concerns.

Phase 1 is complete only when T001–T063 pass with no required skip or xfail.

Never say that implementation is complete if required tests are failing.
