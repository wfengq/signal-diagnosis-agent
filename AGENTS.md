# AGENTS.md

## Project status

This repository implements Scenario S1: “Why does this periodic signal sound
distorted?”

**V0.2 acceptance anchor** (immutable evidence): commit `b48790c` (tag target
`ff16e2a` / `v0.2.0` when present). Dual state:

```text
presentation_harness_accepted
real_demo_completed
Phase 5 accepted; V0.2 complete demonstrable vertical slice
```

Accepted product identity at that anchor: DeepSeek `deepseek-v4-flash`, prompt
`v0.2-s1-planner-8.1`, official held-out **79/80**.

**HEAD live product** (this branch tip) is the V0.3 contextual path: public
`RealLLMPlanner` / `build_product_service` use prompt `v0.3-s1-planner-9.11`
and causal policy `v9_11_mode_aware_no_fault_recovery`. Reports are
**uncertified by Phase 4.3.1**. **Default user path is single-file**
(`single_signal`): clipping may be confirmed; harmonic attribution stays
conservative without reference/nominal context (D037). Optional upgrades:
`paired_reference` and `nominal_single_tone`. Do not cite HEAD quality numbers
in place of the V0.2 **79/80**. To demonstrate the accepted V0.2 product, check
out `ff16e2a` / `b48790c` rather than assuming HEAD matches those artifacts.

Phase 1–5 contracts (`CONTRACTS_V0_2.md` §§1–64) remain frozen byte-stable.
Additive V0.3 surfaces live in `docs/CONTRACTS_V0_3_CONTEXTUAL.md` and
`docs/TEST_PLAN_V0_3_CONTEXTUAL.md`. Do not rewrite accepted evaluation/Demo
assets or replace recorded runs. HEAD-vs-freeze documentation mappings
OQ-013–OQ-018 are resolved as hygiene (D032–D036); further **product-behavior**
changes still need a new written design, contract additions, test IDs, and
explicit authorization (see Scope gates).

**T285 note:** a green T285 with the `_V03_ADDITIVE_*` allowlist means those
paths had authorized V0.3 mutations relative to baseline `36ae7c9`, not that
they remain byte-identical to Phase 4.3.1. V0.2 behavioral preservation for
accepted Demo/bundles is enforced by sealed assets and dedicated preservation
tests, not by assuming T285 proves untouched V0.2 cores.

## Required reading

Before modifying product code, read:

- `docs/README.md`
- `docs/ARCHITECTURE_V0_2.md` (especially §§12–18)
- `docs/CONTRACTS_V0_2.md` (frozen §§1–64)
- `docs/TEST_PLAN_V0_2.md` (required T001–T285)
- `docs/DECISIONS.md` (D001–D037)
- `docs/CONTRACTS_V0_3_CONTEXTUAL.md` and `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`
  when touching contextual / HEAD live product paths
- the relevant specification and plan under `docs/superpowers/`

For final presentation work, also read:

- `docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md`
- `docs/superpowers/plans/2026-08-31-phase5-presentation-engineering.md`
- `docs/PROJECT_CASE_STUDY.md`

Files under `docs/archive/v0.1/` are historical only. Non-normative career or project-origin notes (local only, not in the public tree) do not override active engineering contracts.

## Source of truth

Priority when active documents disagree:

```text
explicit current user instruction
 -> AGENTS.md
 -> CONTRACTS_V0_2.md (frozen §§1–64; V0.2 slice)
 -> CONTRACTS_V0_3_CONTEXTUAL.md (additive; HEAD live / contextual only)
 -> ARCHITECTURE_V0_2.md
 -> TEST_PLAN_V0_2.md / TEST_PLAN_V0_3_CONTEXTUAL.md
 -> approved implementation plan
```

When V0.2 frozen text and V0.3 additive text disagree about the **live HEAD
default**, prefer `CONTRACTS_V0_3_CONTEXTUAL.md` for HEAD wiring (D032–D036);
do not silently edit frozen §§1–64. Implement only what the additive V0.3
contract already permits, or stop for a new design.

Public interfaces, package boundaries, model fields, actions, arguments, and
return values under the V0.2 freeze are frozen. For a genuine contract defect:

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
