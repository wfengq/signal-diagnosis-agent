# AGENTS.md

## Project

This repository implements a Signal Test and Fault Diagnosis Agent.

The current phase is **Phase 5 written-design review**. Phase 4.3.1 is accepted
on the merged baseline `36ae7c9`. The interactive Phase 5 design was approved
on 2026-08-31 and is recorded in
`docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md`,
draft `CONTRACTS_V0_2.md` §§55–§64, draft `TEST_PLAN_V0_2.md` §28
(T224–T285), D026–D030, and open OQ-010. These written assets are awaiting
explicit final review. Do not implement Phase 5 source/tests, create its
detailed plan, run a Phase 5 model Demo, push, or merge until the corresponding
separate gates pass.

Phase 4 accepted at `b68ec5e` (`completed/below_target` official v1.0.0 benchmark
remains immutable). Phase 4.1 v5 deterministic implementation is complete at
`cadc15d`; its 40-slot development gate1 at `f9392c2` is honest
`completed/below_target`. The additive prompt v6 correction (§51, T196–T200,
D022) is approved and Task 2–8 completed. The v1.1.0 held-out split remains
sealed. The v6 deterministic gate passed. Real-model
development gate2 `bench_phase4_1_dev_v6_gate2` is honest
`completed/below_target`, so official v6 held-out stays sealed. Report
`harness_status=pending` is CLI semantics, not a harness failure. Independent
review rejected a prompt-only v7 retry because v1.1.0 exposes semantic signal
IDs and contains hidden first-Tool/causal-identifiability requirements. A
revised Phase 4.2 evaluation-integrity plus planner-v7 design proposes dataset
1.2.0, opaque Agent signal IDs, T201–T208, and D023. Revised OQ-007, §52,
T201–T208, and D023 were approved on 2026-08-30. Tasks 2–7 deterministic
implementation is complete; the T208 cumulative gate is green. Real-model
development gate3 `bench_phase4_2_dev_v7_v12_gate3` at `71293a3` is honest
`completed/below_target`, so official v1.2.0 held-out stays sealed. Task 10
records that honest stop. Phase 4.1 is not accepted. Phase 4.2 is not
accepted. The written Phase 4.3 planner-v8 design is approved and frozen under
§53, T209–T215, D024, and OQ-008. Its detailed task-level plan is complete at
`docs/superpowers/plans/2026-08-30-phase4-3-planner-v8-behavior-calibration.md`.
Deterministic T001–T215 are green at `1c70568`; that is not a live-model pass.
Real-model development gate4 `bench_phase4_3_dev_v8_v12_gate4` at `48dfb89` is
honest `completed/below_target` (40 unique Agent slots; missed
evidence_grounding 0.849, timely_stopping 0.75, unsupported_claim 0.211).
Official v1.2.0 held-out was not run. Phase 4.3 is not accepted. Independent
review then found that T210 globally prohibited a legal clipping-specific
finish and that legacy scoring mishandles the required invalid Evidence ->
NOT_APPLICABLE rule transition. The user-approved Phase 4.3.1 compliance
correction is frozen under §54, T216–T223, D025, and OQ-009. Deterministic
Tasks 2–7 are complete at `083b6d9`. Real-model development gate5
`bench_phase4_3_1_dev_v8_1_v12_gate5` is honest `completed/meets_target`
(40 unique Agent slots; all TargetBands pass). Official v1.2.0 held-out
(Task 9) is honest `completed/meets_target` on 80 Agent held-out slots (all
TargetBands pass; 2/80 Agent slots carry non-blocking behavioral failure codes
on `case_v12_held_noise_02` (slot 1: `redundant_rule;inappropriate_replan`,
outcome correct; slot 5: `required_knowledge_omitted;outcome_mismatch`, the
sole wrong outcome at 1/80); aggregate remains `completed/meets_target`). Phase 4.3.1 is
accepted at Task 10 (development and official both `completed/meets_target`;
terminal evidence at `99e0bdc`).
This is a one-time v8.1
conformance exception to D024, not an
unrestricted v9. Phase 5 implementation, push, and merge remain unauthorized. The detailed
plan is
`docs/superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md`.

The Phase 4 written specification was approved on 2026-08-29; §§41–§49 and
T125–T183 are frozen and implemented. Deterministic status is
`harness_accepted` after T001–T183, Ruff, mypy, and `git diff --check` passed
on branch `phase4-evaluation-design`. Real-model status is
`benchmark_completed` with honest `target_status=below_target` after the
official live 80-slot DeepSeek run `bench_official_s1_20260829t162243z` wrote
the six-file bundle under `docs/evaluations/phase4/`. That first official
benchmark is complete and honestly below target; it is not a harness failure
and is not accepted as product-quality behavior.

Phase 4.1 authority is additive `CONTRACTS_V0_2.md` §§50–§51,
`TEST_PLAN_V0_2.md` §§23–§24 (T184–T200), and D021–D022. It does not change
frozen §§41–§49 or T125–T183 semantics. Phase 5 is now interactively designed,
but its written contract, detailed plan, and explicit execution choice remain
separate gates. Phase 4.3.1 acceptance is the final product-behavior gate; it
does not auto-authorize Phase 5 implementation.

Phase 4.2 design authority is
`docs/superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md`,
frozen `CONTRACTS_V0_2.md` §52, `TEST_PLAN_V0_2.md` §25 (T201–T208), and
D023. Deterministic Tasks 2–7 are implemented. Real-model Task 8
development gate3 at `71293a3` is honest `completed/below_target`. Task 9
official v1.2.0 held-out was not run (unauthorized after the development
miss). Task 10 records that honest stop. Phase 4.2 is not accepted.

Phase 4.3 design authority is
`docs/superpowers/specs/2026-08-30-phase4-3-planner-v8-behavior-calibration-design.md`,
frozen `CONTRACTS_V0_2.md` §53, `TEST_PLAN_V0_2.md` §26 (T209–T215), D024,
and resolved OQ-008. Deterministic Tasks 1–4 are implemented and T215 is green
at `1c70568`; that is not a live-model pass. Task 5 development gate4 at
`48dfb89` is honest `completed/below_target`. Task 6 official was not run.
No v9. Phase 4.3 is not accepted. Phase 5 implementation is unauthorized. Further behavior
work normally requires a new written choice between model capability and
PlannerContext. Phase 4.3.1 is the sole approved compliance exception because
the v8 implementation and scorer did not faithfully enforce §53.

Phase 4.3.1 design authority is
`docs/superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md`,
frozen `CONTRACTS_V0_2.md` §54, `TEST_PLAN_V0_2.md` §27 (T216–T223), D025,
and resolved OQ-009. It preserves dataset 1.2.0 and every v4–v8 asset, adds
prompt `v0.2-s1-planner-8.1` and versioned scoring policy
`signal_diag.scoring=2.0.0`. Deterministic Tasks 2–7 are complete at
`083b6d9`. Development gate5 is honest `completed/meets_target`. Official
held-out (Task 9) is honest `completed/meets_target` on 80 Agent held-out
slots. Phase 4.3.1 is accepted at Task 10 (terminal evidence at `99e0bdc`).
Phase 5 implementation remains unauthorized pending OQ-010, a detailed plan,
and an explicit execution choice.

Phase 1 (T001–T063), Phase 2 (T064–T092), and Phase 3 (T093–T124) are complete
and accepted. Phase 3 passed Codex final acceptance at commit `a820b7f` on
branch `phase3-rules-knowledge`.

## Required reading

Before modifying code, read:

- `docs/README.md`
- `docs/ARCHITECTURE_V0_2.md` (especially §13–§18)
- `docs/CONTRACTS_V0_2.md` (Phase 1–4 frozen; Phase 4 §41–§49; additive Phase 4.1 §§50–§51; Phase 4.2 §52; Phase 4.3 §53; Phase 4.3.1 §54; draft Phase 5 §§55–§64)
- `docs/TEST_PLAN_V0_2.md` (Phase 1–4 required; Phase 4 §22; additive Phase 4.1 §§23–§24 T184–T200; Phase 4.2 §25 T201–T208; Phase 4.3 §26 T209–T215; Phase 4.3.1 §27 T216–T223; draft Phase 5 §28 T224–T285)
- `docs/DECISIONS.md`
- `docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md`
- `docs/superpowers/specs/2026-08-29-phase4-evaluation-design.md`
- `docs/superpowers/plans/2026-08-29-phase4-evaluation.md`
- `docs/superpowers/specs/2026-08-30-phase4-1-agent-behavior-improvement-design.md`
- `docs/superpowers/plans/2026-08-30-phase4-1-agent-behavior-improvement.md`
- `docs/superpowers/specs/2026-08-30-phase4-1-prompt-v6-correction-design.md`
- `docs/superpowers/plans/2026-08-30-phase4-1-prompt-v6-correction.md`
- `docs/superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md`
- `docs/superpowers/plans/2026-08-30-phase4-2-prompt-v7-correction.md`
- `docs/superpowers/specs/2026-08-30-phase4-3-planner-v8-behavior-calibration-design.md`
- `docs/superpowers/plans/2026-08-30-phase4-3-planner-v8-behavior-calibration.md`
- `docs/superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md`
- `docs/superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md`
- `docs/superpowers/plans/2026-08-28-phase1-deterministic-foundation.md`
- `docs/superpowers/plans/2026-08-29-phase3-rules-knowledge.md`

Phase 2 has no separate implementation plan under `docs/superpowers/plans/`.
Use `ARCHITECTURE_V0_2.md` §12 and the accepted Phase 2 contracts as the
implementation authority for Agent runtime work.

Phase 3 implementation authority remains `ARCHITECTURE_V0_2.md` §13, revised
`CONTRACTS_V0_2.md` §32–§40, and `TEST_PLAN_V0_2.md` §21 (T093–T124).
OQ-001 and OQ-003 were approved. Phase 3 passed final acceptance at `a820b7f`.
Phase 4 is accepted at `b68ec5e`; that Phase 3 acceptance did not itself
complete Phase 4.

Phase 4 design authority is the user-approved written design captured in
`docs/superpowers/specs/2026-08-29-phase4-evaluation-design.md`, frozen
`CONTRACTS_V0_2.md` §41–§49, `TEST_PLAN_V0_2.md` §22 (T125–T183), and
D017–D020. Phase 4 is accepted at `b68ec5e`. Deterministic implementation is
`harness_accepted`. Real-model status is `benchmark_completed`
(`below_target`).

Phase 4.1 design authority is the original behavior-improvement design plus
`docs/superpowers/specs/2026-08-30-phase4-1-prompt-v6-correction-design.md`,
additive `CONTRACTS_V0_2.md` §§50–§51, `TEST_PLAN_V0_2.md` §§23–§24
(T184–T200), and D021–D022. v5 deterministic implementation is complete at
`cadc15d`; its development gate1 is `completed/below_target` at `f9392c2`.
Prompt v6 Task 2–8 implementation is authorized. Official held-out remains
development-gated. Phase 4.1 is not accepted.

Phase 4.2 design authority is frozen under §52, T201–T208, and D023. It
supersedes the rejected prompt-only v7 draft by requiring dataset 1.2.0,
opaque Agent signal IDs, visible first-Tool fairness, and single-signal
combined identifiability. Deterministic Tasks 2–7 are complete and T208 is
green. Real-model Task 8 development is honest `completed/below_target`.
Official v1.2.0 held-out (Task 9) was not run because development missed
target. Task 10 records that honest stop; it does not authorize Phase 5.

Phase 4.3 design authority is frozen under §53, T209–T215, D024, and OQ-008.
It permitted one final prompt-only candidate with unchanged v1.2 dataset,
Runtime, PlannerContext, scoring, targets, provider, and model. Deterministic
Tasks 1–4 are complete and T215 is green at `1c70568` (not a live-model pass).
v8 development is honest `completed/below_target` at `48dfb89`. Official was
not run. No prompt-only v9 is authorized. The next design choice is model
capability versus PlannerContext. Phase 5 implementation remains unauthorized.

These documents describe approved architecture and frozen interfaces.

Files under `docs/archive/v0.1/` are historical references only. Files under
`docs/context/` are non-normative background context.

## Source of truth

The Phase 1–4 interfaces in `docs/CONTRACTS_V0_2.md` are frozen. Phase 3
implementation conforms to §32–§40 and the T093–T124 acceptance gate. Phase 4
§41–§49 is implementation authority for the accepted deterministic harness.
Additive Phase 4.1 §§50–§51 are frozen. v5 deterministic implementation is
complete at `cadc15d`, and v5 development gate1 is immutable
`completed/below_target` at `f9392c2`. v6 implementation is authorized under
T196–T200; official held-out and Phase 4.1 acceptance are not done.

Additive Phase 4.2 §52 and T201–T208 are frozen design authority.
Deterministic implementation satisfies T001–T208, Ruff, mypy, architecture,
and `git diff --check aefccba..HEAD`. That deterministic gate is not a
real-model claim. Task 8 development already ran and is honest
`completed/below_target`. Task 9 official/held-out was not legally run
(historical v6/v7 official campaigns were never executed). v1.1.0 held-out
remains unexecuted. v1.2.0 held-out was first executed only by the authorized
Phase 4.3.1 v8.1 official gate5. Phase 4.3.1 acceptance supersedes earlier
failed candidates as the final product-behavior gate. Phase 5 remains
unauthorized until separately designed, frozen, and explicitly authorized.

Additive Phase 4.3 §53 and T209–T215 are frozen. Deterministic implementation
satisfies T001–T215, Ruff, mypy, architecture, and
`git diff --check eb47237..HEAD` at `1c70568`. That deterministic gate is not
a live-model pass. Task 5 development already ran and is honest
`completed/below_target` at `48dfb89` (40 unique Agent slots; 0 held-out).
Task 6 official/held-out was not legally run (historical v8 official was never
executed). v1.2.0 held-out is inspectable only via the committed Phase 4.3.1
official bundle. Do not create v9. Phase 5 implementation remains unauthorized
until OQ-010, the detailed plan, and an explicit execution choice pass. Further work requires a written choice
between changing the model and changing PlannerContext.

Additive Phase 4.3.1 §54 and T216–T223 are frozen design/test authority. They
record the T210 clipping-specific scope defect and the invalid-Evidence scoring
defect. Deterministic Tasks 2–7 are complete at `083b6d9`. T001–T223, Ruff,
mypy, architecture guards, and `git diff --check 1b94194..HEAD` are green with
zero required skip/xfail. T211–T212 retarget to `_Phase4V8RealLLMPlanner`
preserves frozen v8 bytes. v8.1 development gate5 is honest
`completed/meets_target` (40 development slots; all bands pass; development
split; not official held-out evidence). Official held-out (Task 9) is honest
`completed/meets_target` on 80 Agent held-out slots. Phase 4.3.1 is accepted
at Task 10 (terminal evidence at `99e0bdc`). Push, merge, and Phase 5 remain
unauthorized.

Do not redesign or rename public models, functions, modules, arguments, return
values, or package boundaries unless the user explicitly requests a contract
change.

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
- `rules/` owns versioned deterministic thresholds and PASS/FAIL/NOT_APPLICABLE
  judgments over Evidence.
- `knowledge/` owns curated corpus storage and deterministic keyword/tag retrieval.
- `agent/` owns Planner integration and deterministic runtime control.
- `evaluation/` owns deterministic and real-model evaluation.
- `app/` will later own CLI/API/UI/report adapters.
- `signal/`, `dsp/`, `tools/`, `rules/`, and `knowledge/` must not depend on
  Agent or LLM frameworks.
- `rules/` and `knowledge/` must not depend on `agent/`.
- Raw waveform arrays must never be passed to an LLM.
- Full FFT arrays must never be passed to an LLM.
- Repository waveforms use `float32` with shape `(num_samples, channels)`.
- Repository data is immutable.
- DSP algorithms receive one-dimensional numeric arrays.
- Integer PCM is converted to full-scale floating point.
- Do not peak-normalize individual signals.
- Numerical metrics are produced only by deterministic DSP code.
- Pass/fail thresholds are not invented by an LLM; they come from versioned rule
  profiles in `rules/`.
- Tool adapters create compact deterministic Evidence.
- Every supported diagnosis claim must cite valid Evidence from the same run.
- Rule conclusions must cite valid rule-evaluation IDs from the same run.
- Knowledge citations explain claims; they do not substitute for signal Evidence.
- The product Agent will use `RealLLMPlanner`; `ScriptedPlanner` is only a test
  double and is never a silent product fallback.

## Gated next phases

Do not add:

- Phase 5 WAV loader, `app/` package, FastAPI, web frontend, CLI/report
  adapters, T224–T285 implementation, or product Demo artifacts before OQ-010,
  the detailed-plan gate, and an explicit execution choice
- LangGraph (unless explicitly requested and contract-approved)
- vector databases or embedding retrieval (initial Phase 3 uses keyword/tag only;
  see D011)
- large-scale knowledge ingestion or network search
- multi-agent architecture
- database persistence
- Docker infrastructure
- LLM-generated thresholds or standards

unless that later phase is explicitly authorized.

Phase 4 dual acceptance is satisfied at `b68ec5e`: `harness_accepted` and
`benchmark_completed` with honest `below_target`. Phase 4.1 v5 deterministic
implementation is complete at `cadc15d`; both v5 development gate1 and v6
development gate2 are immutable `completed/below_target` results. Phase 4.2
deterministic implementation is complete and T208 is green. v7 development
gate3 is honest `completed/below_target`. Official v1.2.0 held-out was
not run. Phase 4.1 is not accepted. Phase 4.2 is not accepted. Phase 5
implementation remains unauthorized. Its interactive design is complete, but
the written contract, plan, and execution gates remain pending.

Phase 4.3 deterministic implementation is complete and T215 is green at
`1c70568`; that is not a live-model pass. v8 development gate4 is honest
`completed/below_target` at `48dfb89`. Official v1.2.0 held-out was not run.
Phase 4.3 is not accepted. Phase 4.3.1 §54/T216–T223/D025/OQ-009 are frozen.
Deterministic Tasks 2–7 are complete at `083b6d9`. v8.1 development gate5 is
honest `completed/meets_target`. Official v1.2.0 held-out (Task 9) is honest
`completed/meets_target` on 80 Agent held-out slots. Phase 4.3.1 is accepted
at Task 10 (terminal evidence at `99e0bdc`). Phase 5 implementation remains unauthorized.
Do not create v8.2 or v9.

## Completed phases (reference)

### Phase 1 — deterministic signal-analysis foundation (accepted)

Signal models, repository, segmentation, synthetic generators, DSP algorithms,
Tool contracts, Evidence, and tests T001–T063.

### Phase 2 — minimal end-to-end distortion-diagnosis Agent (accepted)

`PlannerModel`, `ScriptedPlanner`, `RealLLMPlanner`, `DistortionDiagnosisRuntime`,
S1 deterministic acceptance T064–T092, and separate R001–R006 real-model checks.

### Phase 3 — deterministic rules and knowledge retrieval (accepted at `a820b7f`)

Versioned `profile_s1_distortion` `1.0.0-demo` rule profiles, `RuleEngine`,
curated local Markdown corpus, keyword/tag `KnowledgeIndex`, runtime rule and
knowledge actions, and T093–T124. Demo thresholds are not industry standards.
The deterministic implementation and its final fix wave passed independent
Codex acceptance at `a820b7f`. The product-path runner is
`scripts/run_phase3_real_model_eval.py`. The real-model observation in
`docs/reports/PHASE3_REAL_MODEL_BEHAVIOR_REPORT.md` **RAN** once (honest
DeepSeek run, not a CI gate) with 0 rule-evaluation and 0 knowledge-retrieval
actions. That Phase 3 acceptance did not itself complete Phase 4, which is now
accepted at `b68ec5e`.

### Phase 4 — evaluation harness (accepted at `b68ec5e`)

Versioned S1 evaluation package, scripted deterministic harness, honest
fixed-pipeline baseline, scoring, immutable report writer, official runner
CLI, and T125–T183. Official live DeepSeek benchmark
`bench_official_s1_20260829t162243z` is recorded at `b68ec5e`: provider
`deepseek`, model `deepseek-v4-flash`, prompt `v0.2-s1-planner-4`, 80
scoreable held-out Agent slots, `benchmark_status=completed`,
`target_status=below_target`. Bundle:
`docs/evaluations/phase4/bench_official_s1_20260829t162243z/`. That first
official result is honest `completed/below_target`; it is not a harness
failure and is not accepted as product-quality behavior.

### Phase 4.1 — agent behavior improvement (v5 development below target; v6 implementation authorized)

Additive §§50–§51, T184–T200, and D021–D022. v5 gate1 is immutable
`completed/below_target`; v6 is a coherent prompt-only correction using the
existing v1.1.0 development split before any held-out access. It does not
change frozen §§41–§49 or T125–T183. Phase 5 implementation remains gated.

### Phase 4.2 — evaluation integrity and planner v7 (development below target)

Additive §52, T201–T208, and D023. Dataset `1.2.0`, opaque Agent signal IDs,
coherent prompt `v0.2-s1-planner-7`, and canonical v7 campaigns are
implemented. Recorded statuses at `71293a3` (do not conflate them):

- deterministic: T001–T208 green (`harness_accepted` for the Phase 4.2
  integrity gate; not a real-model claim)
- development: `benchmark_status=completed` on 40 unique Agent slots
- official: not run; `docs/evaluations/phase4_2/official/` does not exist
- `target_status=below_target` (missed `first_tool_selection_rate` 0.75,
  `observation_driven_replan_rate` 0.719, `unnecessary_tool_action_rate`
  0.405, `required_knowledge_usage_rate` 0.2)
- CLI `harness_status=pending` (report-model semantics, not a harness failure)

Bundle:
`docs/evaluations/phase4_2/development/bench_phase4_2_dev_v7_v12_gate3/`.
No held-out Agent slots were executed. This is not Phase 4.2 acceptance
and is not product-quality behavior.

### Phase 4.3 — planner v8 behavior calibration (development below target)

Additive §53, T209–T215, and D024. Coherent prompt `v0.2-s1-planner-8` and
canonical v8 campaign routes are implemented. Recorded statuses at `48dfb89`
(do not conflate them):

- deterministic: T001–T215 green at `1c70568`; not a live-model pass
- development: `benchmark_status=completed` on 40 unique Agent slots
- official: not run; `docs/evaluations/phase4_3/official/` does not exist
- `target_status=below_target` (missed `evidence_grounding_rate` 0.849,
  `timely_stopping_rate` 0.75, `unsupported_claim_rate` 0.211)
- CLI `harness_status=pending` (report-model semantics, not a harness failure)
- Phase 4.3 acceptance: not accepted
- Phase 5 implementation: unauthorized

Bundle:
`docs/evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4/`.
No held-out Agent slots were executed. No v9. The prompt-only route is closed
by §53.4. The next written choice is model capability versus PlannerContext
(option 2), not more prompts. This is not Phase 4.3 product-quality acceptance.

### Phase 4.3.1 — v8.1 compliance correction (accepted at Task 10; terminal evidence at `99e0bdc`)

Additive §54, T216–T223, D025, and OQ-009 authorize a single written v8.1
conformance design because T210 over-banned clipping-specific finish and the
legacy scoring proxy mishandles invalid Evidence followed by NOT_APPLICABLE
rules. It preserves every v4–v8 asset and public boundary. Prompt
`v0.2-s1-planner-8.1`, scoring policy `signal_diag.scoring=2.0.0`, and gate5
campaign identities are implemented in Tasks 2–7 at `083b6d9`. Recorded
statuses (do not conflate them):

- deterministic: T001–T223 green at `083b6d9`; not official held-out evidence
- development: `benchmark_status=completed`, `target_status=meets_target` on
  40 unique Agent slots; all TargetBands pass
- official (Task 9): `benchmark_status=completed`, `target_status=meets_target`
  on 80 Agent held-out slots; all TargetBands pass; 2/80 Agent slots carry
  non-blocking behavioral failure codes on `case_v12_held_noise_02` (slot 1:
  `redundant_rule;inappropriate_replan`, outcome correct; slot 5:
  `required_knowledge_omitted;outcome_mismatch`, sole wrong outcome at 1/80);
  aggregate remains `completed/meets_target`
- CLI `harness_status=pending` (report-model semantics, not a harness failure)
- Task 9 official held-out: executed; honest `completed/meets_target`
- Phase 4.3.1 acceptance: accepted at Task 10 (development and official
  both `completed/meets_target`; terminal evidence at `99e0bdc`)
- Phase 5 implementation: unauthorized

Development bundle:
`docs/evaluations/phase4_3_1/development/bench_phase4_3_1_dev_v8_1_v12_gate5/`.
No held-out Agent slots. Warning: development split; not official held-out
evidence.

Official bundle:
`docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/`.
80 Agent held-out slots (16 cases × 5 reps). Phase 4.3.1 acceptance recorded
at Task 10; Phase 5 implementation remains unauthorized pending OQ-010.

### Phase 5 — presentation engineering (written design pending review)

The interactive design selects a native Web UI as the primary Demo, FastAPI and
argparse as thin adapters, one shared DiagnosisApplicationService, bounded
in-memory polling jobs, strict integer-PCM WAV ingestion, five public synthetic
presets, actual chronological Agent trace display, canonical JSON/self-contained
HTML reports, and an honest checksum-linked Phase 4.3.1 evaluation summary.

Draft authority is:

- `docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md`;
- `CONTRACTS_V0_2.md` §§55–§64;
- `TEST_PLAN_V0_2.md` §28 T224–T285;
- D026–D030 and open OQ-010.

No Phase 5 source, tests, implementation plan, real-model Demo, push, or merge
is authorized by the draft. Final written approval must close OQ-010; then a
Superpowers task-level plan and a separate execution choice are required.

## Development workflow

Use test-driven development.

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

Invalid Evidence must produce `not_applicable` rule judgments, not PASS.

## Change discipline

Keep changes narrowly scoped to the current task.

Do not perform unrelated refactors.

Do not add dependencies without a concrete need.

Do not add compatibility layers for hypothetical future requirements.

Do not commit or push unless explicitly requested.

## Verification

Before declaring a task complete:

- run the relevant focused tests;
- run the full pytest suite (Phase 1–4 tests must remain green);
- report exactly which tests were run;
- report any remaining warnings, failures, TODOs, or contract concerns.

Phase 3 final acceptance at `a820b7f` includes deterministic T001–T124 with zero
required skip/xfail, the OQ-003-approved `profile_s1_distortion` `1.0.0-demo`
profile, an honest real-model report, and closure of the final same-run trace
validation findings. The real-model run **RAN** once with 0 rule/knowledge
actions; do not treat that as a Phase 3 product-behavior pass.

Phase 4 deterministic `harness_accepted` requires T001–T183 with zero required
skip/xfail plus Ruff, mypy, and `git diff --check`. Real-model
`benchmark_completed` additionally requires the official 80-slot DeepSeek run
and immutable six-file bundle; a `below_target` result is honest completion.
Do not treat `benchmark_pending` or `incomplete` as `benchmark_completed`.
The first official benchmark at `b68ec5e` is `completed/below_target`; it is
not a product-quality behavior pass.

Phase 4.1 v5 deterministic implementation is complete at `cadc15d`; T184–T195
were green before its honest `completed/below_target` development gate1 at
`f9392c2`. v6 implementation must satisfy T001–T200, Ruff, mypy, architecture,
and `git diff --check f9392c2..HEAD`; its 40-slot development gate2 must meet
target before the one-shot 80-slot official run. Phase 4.1 acceptance requires
the v6 official result to be `completed/meets_target`. Phase 5 implementation remains gated.

Phase 4.2 deterministic implementation must satisfy T001–T208, Ruff, mypy,
architecture, and `git diff --check aefccba..HEAD` with zero required
skip/xfail. That gate is green. v7 development gate3 is honest
`completed/below_target`. Official v1.2.0 held-out was not run. Do not treat
either gate as Phase 4.2 acceptance.

Phase 4.3 deterministic implementation must satisfy T001–T215, Ruff, mypy,
architecture, and `git diff --check eb47237..HEAD` with zero required
skip/xfail. That gate is green at `1c70568` and is not a live-model pass.
v8 development gate4 is honest `completed/below_target` at `48dfb89`.
Official v1.2.0 held-out was not run. Do not treat either gate as Phase 4.3
acceptance. Phase 4.3.1 §54/T216–T223/D025/OQ-009 are frozen design/test
authority. Deterministic Tasks 2–7 are complete at `083b6d9`; T001–T223, Ruff,
mypy, architecture, and diff-check are green. v8.1 development gate5 is honest
`completed/meets_target`. Official held-out (Task 9) is honest
`completed/meets_target` on 80 Agent held-out slots. Phase 4.3.1 is accepted
at Task 10 (terminal evidence at `99e0bdc`). Do not create v8.2 or v9.
Phase 5 implementation is unauthorized.

Never say that a later phase is complete if required tests are failing.
