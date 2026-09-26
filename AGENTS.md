# AGENTS.md

## Project status

This repository implements the V0.2 Signal Test and Fault Diagnosis Agent for
Scenario S1: “Why does this periodic signal sound distorted?”

V0.2 is complete and accepted locally from terminal evidence at `b48790c`:

```text
presentation_harness_accepted
real_demo_completed
Phase 5 accepted; V0.2 complete demonstrable vertical slice
```

Phase 1–5 contracts are frozen. Repository curation after `b48790c` is
documentation and release hygiene only; it does not authorize product behavior
changes, new model runs, or rewriting accepted evaluation/Demo assets.

## Required reading

Before modifying product code, read:

- `docs/README.md`
- `docs/ARCHITECTURE_V0_2.md` (especially §§12–18)
- `docs/CONTRACTS_V0_2.md` (frozen §§1–64)
- `docs/TEST_PLAN_V0_2.md` (required T001–T285)
- `docs/DECISIONS.md` (D001–D031)
- the relevant specification and plan under `docs/superpowers/`

For final presentation work, also read:

- `docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md`
- `docs/superpowers/plans/2026-08-31-phase5-presentation-engineering.md`
- `docs/PROJECT_CASE_STUDY.md`

Files under `docs/archive/v0.1/` are historical only. Files under
`docs/context/` are non-normative background.

## Source of truth

Priority when active documents disagree:

```text
explicit current user instruction
    -> AGENTS.md
    -> CONTRACTS_V0_2.md
    -> ARCHITECTURE_V0_2.md
    -> TEST_PLAN_V0_2.md
    -> approved implementation plan
```

Public interfaces, package boundaries, model fields, actions, arguments, and
return values are frozen. For a genuine contract defect:

1. do not silently change it;
2. explain the problem;
3. record the proposal in `docs/OPEN_QUESTIONS.md`;
4. continue only if the existing contract still permits a correct result.

## Architectural boundaries

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

- `signal/`: representation, immutable repositories, segmentation, synthetic
  generation, and bounded WAV decoding.
- `dsp/`: deterministic numerical algorithms.
- `tools/`: compact structured DSP adapters and Evidence.
- `rules/`: versioned thresholds and PASS/FAIL/NOT_APPLICABLE judgments.
- `knowledge/`: curated Markdown corpus and deterministic keyword/tag retrieval.
- `agent/`: planner boundary and deterministic runtime control.
- `evaluation/`: datasets, trace recording, fixed baseline, scoring, campaigns,
  and immutable bundles.
- `app/`: shared application service, CLI, API, Web UI, and reports.

The following rules remain mandatory:

- lower layers must not depend on Agent or LLM frameworks;
- `rules/` and `knowledge/` must not depend on `agent/`;
- raw waveform and full FFT arrays must never be sent to an LLM;
- waveforms are immutable `float32` with shape `(num_samples, channels)`;
- integer PCM converts to full-scale float without per-signal peak normalization;
- numerical metrics come only from deterministic DSP;
- thresholds come only from versioned rule profiles;
- supported claims cite valid same-run Evidence;
- rule conclusions cite valid same-run rule-evaluation IDs;
- knowledge explains claims but never substitutes for signal Evidence;
- `RealLLMPlanner` is the product path;
- `ScriptedPlanner` is a deterministic test double and never a silent fallback.

## Preserved evidence

Do not delete or rewrite:

- historical `below_target` bundles under `docs/evaluations/`;
- accepted v8.1 development and official bundles;
- `docs/demo/phase5/v0_2_acceptance/` artifacts;
- v4–v8 prompt identities or scoring identities;
- V0.1 archive, design specs, plans, decisions, or Git history.

Rule profile `profile_s1_distortion` 1.0.0-demo uses 1% clipping and 5% THD
demonstration thresholds. Never describe them as industry standards or SLAs.

## Scope gates

V0.2 completion does not authorize:

- additional live-model runs or replacement of recorded runs;
- wider diagnosis domains;
- LangGraph or multi-agent product architecture;
- vector databases, network knowledge search, or large-scale ingestion;
- database persistence, Docker, authentication, or public deployment;
- LLM-generated metrics, thresholds, or standards.

Any V0.3 behavior or architecture change requires a new written design,
contract additions, test IDs, and explicit implementation authorization.

## Development workflow

Use test-driven development for behavior changes:

1. add or identify the relevant test;
2. confirm the expected failure when appropriate;
3. implement the smallest correct change;
4. run focused tests;
5. run the cumulative suite;
6. refactor only while green.

Keep random test data seeded. Do not weaken tests, perform unrelated refactors,
or add dependencies without a concrete requirement. Preserve user changes.
Do not commit or push unless explicitly authorized.

## Verification

Before completion claims, run and report:

- focused tests for changed behavior;
- full pytest with zero required skip/xfail;
- Ruff;
- mypy;
- architecture tests;
- `git diff --check` against the applicable baseline;
- wheel smoke for packaging changes;
- local CPython 3.11/3.12 clean-environment matrix for a release gate.

Real-model behavior is a separate non-CI gate. Missing credentials must not
cause fallback to `ScriptedPlanner`.
