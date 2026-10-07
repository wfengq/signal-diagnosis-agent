# Documentation Index

This index is organized by what you are trying to do: review the project, check
a result, change the code, or trace its history. Files stay where they are,
because evaluation bundles and tests are bound to their paths.

## 1. Start here (five-minute reviewer path)

1. [Project README](../README.md): what the agent does, results at a glance,
   quick start and limitations.
2. [Agent-increment results report](evaluations/v0_3/agent_increment/STUDY_S1_AGENT_INCREMENT_1_REPORT.md):
   the latest study. It compares the agent with the strongest fixed pipeline on
   held-out cases, explains what drove each result, and lists the limits that
   bound it.
3. [Engineering case study](PROJECT_CASE_STUDY.md) ([中文](PROJECT_CASE_STUDY.zh-CN.md)):
   the difficult failures, corrections and lessons.
4. [Accepted V0.2 official evaluation](evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/):
   the immutable 80-run held-out bundle behind 79/80.
5. [Phase 5 Demo evidence](demo/phase5/v0_2_acceptance/README.md): the two
   retained real-model product runs, with sanitized artifacts.

## 2. Evaluations and results

Every result belongs to the identity it was measured on, and none replaces
another. Development misses and failed rounds are kept on purpose: they show
how calibration and held-out discipline were controlled.

| Line | Where | What it shows |
|---|---|---|
| V0.2 Phase 4, first official run | `evaluations/phase4/` | 80 runs, immutable `completed/below_target` |
| V0.2 Phase 4.1–4.3 | `evaluations/phase4_1/`, `phase4_2/`, `phase4_3/` | v5–v8 development-only misses; held-out stayed sealed |
| **V0.2 Phase 4.3.1 (accepted)** | `evaluations/phase4_3_1/` | v8.1 development gate, then the official held-out run: `completed/meets_target`, **79/80** |
| V0.2 external WAV | `evaluations/v0_2_external_wav/` | Incremental external-WAV study, including its retained `below_target` result |
| V0.3 contextual | `evaluations/v0_3/contextual/` and the [v9.11 acceptance report](evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md) | Contextual development history, sealed three-arm validation, independent audit, corrected `meets_target` |
| V0.3 planner-ablation | `evaluations/v0_3/planner_ablation/` | `dev_1` concluded `fixed_pipeline_dominance`. `dev_2` stopped before sealing with no live calls (D046). |
| V0.3 full-scale regression check | `evaluations/v0_3/full_scale_characterization/` | round_1 characterization, two-stage freeze and validation; method floor registered as D044 |
| **V0.3 agent increment** | `evaluations/v0_3/agent_increment/` and the [results report](evaluations/v0_3/agent_increment/STUDY_S1_AGENT_INCREMENT_1_REPORT.md) | Five dev rounds and one frozen held-out run. T1 **+5** (measurable increment); T2 **0** with 96 vs 824 tool calls; agent safety met on all 48 cases. |
| V0.3 intake product acceptance | `evaluations/v0_3/intake_product/acceptance_1/` and its [note](evaluations/v0_3/intake_product/acceptance_1/ACCEPTANCE_NOTE.md) | Six development T1 cases through `intake diagnose --yes`: the flow passed. Not a quality metric; its recorded `http_calls` are not real counts. |
| Real-model observations | `reports/` | Phase 2 and Phase 3 observations |

None of the V0.3 numbers changes the V0.2 completion statement or turns a study
into an official benchmark, an industrial validation, or a production-readiness
claim.

## 3. Sources of truth

Read these before changing behavior or public interfaces:

1. [ARCHITECTURE_V0_2.md](ARCHITECTURE_V0_2.md): Scenario S1, the hybrid agent,
   phase boundaries and dependency direction.
2. [CONTRACTS_V0_2.md](CONTRACTS_V0_2.md): frozen Phase 1–5 contracts, §§1–64.
3. [CONTRACTS_V0_3_CONTEXTUAL.md](CONTRACTS_V0_3_CONTEXTUAL.md): additive
   V0.3 surfaces.
   - §17–§18: contextual modes, `context_guidance` and the held-bytes upgrade.
   - §19–§21: planner-ablation study.
   - §22: regression workbench.
   - §23: full-scale regression check.
   - §24: agent-increment study.
   - §25: free-text intake product flow.
   - §26: opt-in F0 subharmonic guard (live product).
   - §27: product fault time localization (§27.1: paired reference).
   - §28: deterministic diagnosis engine (product default).
   - §29: sweep stimulus test (separate entry, D054); §29.1: pOD-set validation (D056).
   - §30: explanation layer (D055); §30.1: wording check 1.1 (D058).
   - §31: test guide (D057); §31.1: guide prompt 1.1 and held-out scenarios (D059).

   Do not edit frozen §§1–64.
4. [TEST_PLAN_V0_2.md](TEST_PLAN_V0_2.md) (T001–T285) and
   [TEST_PLAN_V0_3_CONTEXTUAL.md](TEST_PLAN_V0_3_CONTEXTUAL.md) (T-CX series,
   through T-CX501).
5. [DECISIONS.md](DECISIONS.md): D001–D059.
6. [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md): OQ-001–OQ-026.
   - OQ-013–OQ-018 resolve gaps between the current code and the frozen V0.2
     documents.
   - OQ-019 is the planner-ablation study; its `dev_2` was stopped by D046.
   - OQ-020–OQ-022 cover the full-scale check (D043, D044).
   - OQ-023 is the provider-telemetry SDK identity label (`httpx` vs `httpx2`); approved as D048.
   - OQ-024 is the octave-ambiguity flag missing subharmonic lock; deferred.
7. [EXTERNAL_VALIDATION_CONTRACTS_V0_2.md](EXTERNAL_VALIDATION_CONTRACTS_V0_2.md)
   and [EXTERNAL_VALIDATION_TEST_PLAN_V0_2.md](EXTERNAL_VALIDATION_TEST_PLAN_V0_2.md):
   the external-WAV study.

When active documents disagree, use this priority:

```text
explicit current user instruction
    -> AGENTS.md
    -> CONTRACTS_V0_2.md (frozen §§1–64)
    -> CONTRACTS_V0_3_CONTEXTUAL.md (additive HEAD/contextual)
    -> ARCHITECTURE_V0_2.md
    -> TEST_PLAN_V0_2.md / TEST_PLAN_V0_3_CONTEXTUAL.md
    -> approved implementation plan
```

A disagreement is a contract concern. Do not resolve it silently.

## 4. Offline acceptance records and proofs

These record what was verified without a live model, and when.

- **Agent increment:**
  [AGENT_INCREMENT_OFFLINE_ACCEPTANCE.md](AGENT_INCREMENT_OFFLINE_ACCEPTANCE.md)
- **Regression workbench:**
  - [offline acceptance](REGRESSION_WORKBENCH_OFFLINE_ACCEPTANCE.md)
  - [HTTP proof](REGRESSION_WORKBENCH_HTTP_PROOF_2026-10-04.md)
  - [browser proof](REGRESSION_WORKBENCH_BROWSER_PROOF_2026-10-04.md)
- **Full-scale check:**
  - [offline acceptance](REGRESSION_FULL_SCALE_CHECK_OFFLINE_ACCEPTANCE.md)
  - [layer-1 characterization tool](REGRESSION_LAYER1_CHARACTERIZATION_TOOL_OFFLINE_ACCEPTANCE.md)
- **OQ-020 full tool-path probe:**
  [report](OQ020_FULL_TOOLPATH_PROBE_2026-10-05.md) and
  [data](OQ020_FULL_TOOLPATH_PROBE_2026-10-05.json)
- **Product walkthrough:**
  [single-file usability notes, 2026-10-03](PRODUCT_WALKTHROUGH_S1_HEAD_2026-10-03.md).
  These are usability notes, not a quality certificate.

## 5. Code-review path

1. `src/signal_diag/app/composition.py` and `app/service.py`: application
   assembly and request orchestration.
2. `src/signal_diag/agent/models.py`, `planner.py` and `runtime.py`: the model
   boundary and the deterministic agent controller.
3. `src/signal_diag/tools/service.py` and `src/signal_diag/dsp/`: compact tool
   results backed by deterministic numerical code.
4. `src/signal_diag/rules/engine.py` and `src/signal_diag/knowledge/index.py`:
   profile-owned thresholds and curated retrieval.
5. `src/signal_diag/evaluation/`: campaign execution, trace assembly and
   scoring, including the `agent_increment/` study harness.
6. `tests/agent/test_s1_acceptance.py` and
   `tests/test_architecture_boundaries.py`: end-to-end and dependency gates.

## 6. Engineering history

Formal designs and plans live under `superpowers/specs/` and
`superpowers/plans/`. Product-round sequencing lives under
`superpowers/roadmaps/`; it is direction, not an implementation grant. Together
they keep the full reasoning trail without turning the README into a task
ledger.

- **Phase 1:** deterministic signal foundation (T001–T063).
- **Phase 2:** minimal agent runtime and the real/scripted planner boundary
  (T064–T092).
- **Phase 3:** rules and curated knowledge actions (T093–T124).
- **Phase 4:** evaluation harness and the first honest official `below_target`
  result (T125–T183).
- **Phases 4.1–4.3:** v5–v8 prompt development misses; dataset 1.2.0 and the
  evaluation-integrity correction (T184–T215).
- **Phase 4.3.1:** clipping-scope and invalid-Evidence scoring correction; v8.1
  development and official both `meets_target` (T216–T223).
- **Phase 5:** WAV, CLI/API/UI/reporting, packaging, dual-Python verification
  and the real product Demo (T224–T285).
- **V0.3 additive work on the current branch:**
  - contextual modes and the D037 single-file default (§17–§18);
  - the planner-ablation study (D038–D041, stopped by D046);
  - the regression workbench (D042) and full-scale check (D043–D044);
  - the agent-increment study (D045).

Historical documents: [archive/v0.1/](archive/v0.1/) holds the original V0.1
project, contracts and test plan, for reference only.

## 7. Status and identities

```text
presentation_harness_accepted
real_demo_completed
Phase 5 accepted; V0.2 complete demonstrable vertical slice
```

- **Accepted V0.2 product:** commit `b48790c`, prompt `v0.2-s1-planner-8.1`.
  The 79/80 belongs only to this anchor.
- **Current branch product default:** the additive V0.3 planner
  `v0.3-s1-planner-9.11`. This is a product-path fact, not a claim that 79/80
  was re-earned on it (see OQ-013–OQ-018, D032–D036).
- **Agent-increment study prompts:** `v0.3-s1-planner-9.15` and
  `v0.3-s1-intake-1.1` were evaluated in that study, but they are not the
  product default.
- **Package version:** `pyproject.toml` stays at `0.2.0` to preserve tag and
  wheel history until a release design chooses `0.3.0`.

The public product path is `RealLLMPlanner`, and required tests never call a
live model. Accepted Demo and official bundles must not be rewritten to improve
recorded outcomes.
