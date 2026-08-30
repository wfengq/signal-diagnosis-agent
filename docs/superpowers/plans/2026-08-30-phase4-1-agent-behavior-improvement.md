# Phase 4.1 Agent Behavior Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the real DeepSeek S1 planner from the immutable `b68ec5e` `completed/below_target` baseline to a fresh v1.1.0 held-out benchmark with `completed/meets_target`, without changing frozen Phase 1–4 public interfaces or turning the Agent into a fixed controller.

**Architecture:** Preserve the legacy v4 prompt, v1.0 manifest, and Phase 4 runner as reproducible paths. Make v5 the active `RealLLMPlanner` prompt while a private v4 planner subclass keeps the old official campaign reproducible; add a new immutable v1.1.0 manifest and additive private Phase 4.1 development/official campaign wrappers over the existing runtime, scorer, trace, and six-file reporter. Deterministic CI uses a fake model transport through the real `RealLLMPlanner` and runtime; real DeepSeek behavior is a separate development gate followed by one no-tuning 80-slot official run.

**Tech Stack:** Python 3.12.13, Pydantic V2, PyYAML, NumPy, pytest/pytest-asyncio, Ruff, mypy, the existing OpenAI-compatible DeepSeek adapter, and standard-library `dataclasses`, `hashlib`, `json`, and `pathlib`.

**Spec:** `docs/superpowers/specs/2026-08-30-phase4-1-agent-behavior-improvement-design.md`

## Global Constraints

- Baseline is `b68ec5e`; its official six-file bundle remains immutable and traceable.
- Preserve the legacy v4 prompt, `_official_benchmark_config`, v1.0.0 manifest, and T001–T183 semantics.
- Phase 4.1 uses DeepSeek `deepseek-v4-flash`, prompt `v0.2-s1-planner-5`, dataset `s1-distortion-synthetic` `1.1.0`, and profile `profile_s1_distortion` `1.0.0-demo`.
- The v5 behavior is active in `RealLLMPlanner`; legacy v4 selection is private to the old campaign. Do not change the `RealLLMPlanner` constructor, `PlannerModel`, `AgentDecision`, `PlannerContext`, `DistortionDiagnosisRuntime`, public evaluation models, public scorer signatures, target bands, or termination semantics.
- `RealLLMPlanner` remains the real product path. A fake provider transport may feed it deterministic JSON in tests; no real-model failure may fall back to `ScriptedPlanner` or a fake.
- Do not force DSP, rule, or knowledge actions in the runtime controller. The v5 prompt supplies decision policy; Runtime keeps only its frozen validation, retry, no-progress, and budget roles.
- Raw waveforms, full FFT arrays, causal labels, split identity, knowledge policy, sufficient-Evidence sets, and scoring conditions never enter model context.
- DSP/Tools alone produce numbers. Rule thresholds come only from `profile_s1_distortion` `1.0.0-demo`; 1% clipping and 5% THD are demonstration limits, not standards.
- Prompt development may inspect only v1.1.0 development results. Once v5 and its SHA-256 are frozen, the v1.1.0 held-out benchmark runs once.
- A completed below-target development or official bundle is retained honestly. Do not tune against or overwrite the same held-out set.
- Required pytest never calls a real LLM. Missing credentials block only Tasks 6–7, not deterministic T184–T195 implementation.
- Use TDD per code task: focused RED, minimal GREEN, cumulative full pytest, local commit. Do not push, merge, delete `build/`, or begin Phase 5.
- Stop on a genuine frozen-contract conflict and record it in `docs/OPEN_QUESTIONS.md`; do not silently alter a frozen interface.

## File Structure

```text
src/signal_diag/agent/
├── prompts.py                   # private immutable v4/v5 prompt specifications
└── planner.py                   # active v5 RealLLMPlanner plus private v4 subclass

src/signal_diag/evaluation/
├── dataset.py                   # additive validation for v1.0.0 and v1.1.0
├── scoring.py                   # private split-aware aggregation; public API unchanged
├── runner.py                    # legacy runner plus Phase 4.1 dev/official wrappers
├── __main__.py                  # additive --campaign option; four subcommands unchanged
└── manifests/
    ├── s1_distortion_v1.yaml    # immutable legacy dataset
    └── s1_distortion_v1_1.yaml  # fresh 24-case Phase 4.1 dataset

tests/agent/
└── test_phase4_1_prompt.py      # T184–T186

tests/evaluation/
├── conftest.py                  # additive v1.1 fixture only
├── test_phase4_1_acceptance.py  # T187–T190 through fake model + real runtime
├── test_phase4_1_dataset.py     # T191–T193
└── test_phase4_1_runner.py      # T184/T194 and development gate plumbing

docs/evaluations/phase4_1/
├── development/bench_phase4_1_dev_v5_gate1/          # 40-slot evidence
└── official/bench_official_s1_v11_planner5_gate1/    # 80-slot evidence
```

Normative documentation changes stay in `AGENTS.md`, `docs/README.md`, `docs/CONTRACTS_V0_2.md`, `docs/TEST_PLAN_V0_2.md`, and `docs/DECISIONS.md`. No new dependency is required.

---

### Task 1: Freeze the Additive Phase 4.1 Normative Gate

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/CONTRACTS_V0_2.md`
- Modify: `docs/TEST_PLAN_V0_2.md`
- Modify: `docs/DECISIONS.md`

**Interfaces:**
- Consumes: approved Phase 4.1 design at `docs/superpowers/specs/2026-08-30-phase4-1-agent-behavior-improvement-design.md`.
- Produces: additive §50 behavior contract, additive test-plan §23 T184–T195, and D021. It does not modify §§41–§49 or T125–T183.

- [x] **Step 1: Add the exact additive contract text**

  Add `CONTRACTS_V0_2.md` §50 with these normative statements:

  ```text
  Phase 4.1 preserves the v4/v1.0.0 official campaign and adds a v5/v1.1.0 campaign.
  v5 changes planner instruction only; public Planner, Runtime, evaluation, scoring,
  and report interfaces remain unchanged.
  Causal distortion presence and configured rule acceptance are independent facts.
  Rule PASS never erases supported causal Evidence.
  Knowledge is selectively required by observable invalid/not-applicable state,
  never by planner-visible evaluation labels.
  Development uses 8 cases x 5 slots; official held-out uses 16 x 5 slots.
  Phase 4.1 acceptance requires completed/meets_target and T001–T195 green.
  ```

  Add `TEST_PLAN_V0_2.md` §23 with the approved T184–T195 wording verbatim from the spec. Add D021 recording prompt-only correction, immutable `b68ec5e`, fresh held-out data, and the no-controller/no-retuning rules.

- [x] **Step 2: Update current-stage navigation honestly**

  Set `AGENTS.md` and `docs/README.md` to “Phase 4 accepted at `b68ec5e`; Phase 4.1 design approved and implementation pending; Phase 5 gated.” Keep the first official benchmark described as `completed/below_target`, not failed and not accepted as product-quality behavior.

- [x] **Step 3: Verify the documentation-only gate**

  Run:

  ```powershell
  git diff --check b68ec5e..HEAD
  rg -n "§50|T184|T195|D021|b68ec5e|below_target|Phase 5" AGENTS.md docs
  ```

  Expected: diff-check exits 0; every new authority and gate is discoverable; §§41–§49 and T125–T183 have no semantic edits.

- [x] **Step 4: Commit the normative gate**

  ```powershell
  git add AGENTS.md docs/README.md docs/CONTRACTS_V0_2.md docs/TEST_PLAN_V0_2.md docs/DECISIONS.md
  git commit -m "docs: freeze Phase 4.1 behavior gate"
  ```

---

### Task 2: Add the Versioned v5 Prompt and Deterministic Product-Path Acceptance

**Files:**
- Create: `src/signal_diag/agent/prompts.py`
- Modify: `src/signal_diag/agent/planner.py`
- Create: `tests/agent/test_phase4_1_prompt.py`
- Create: `tests/evaluation/test_phase4_1_acceptance.py`

**Test IDs:** T184–T190

**Interfaces:**
- Consumes: existing `RealLLMPlanner`, `PlannerContext`, `AgentDecision`, real Runtime, Tools, RuleEngine, profile loader, and KnowledgeIndex.
- Produces: private `_PlannerPromptSpec`, `_S1_PROMPT_V4`, `_S1_PROMPT_V5`, and `_Phase4V4RealLLMPlanner`. The public `RealLLMPlanner` constructor remains unchanged; `PROMPT_VERSION` and `_SYSTEM_PROMPT` advance to active v5 as approved.

- [x] **Step 1: Write failing prompt identity and leakage tests**

  In `test_phase4_1_prompt.py`, import the private versioned specs and assert:

  ```python
  def test_t184_v4_and_v5_prompt_identities_are_distinct() -> None:
      assert _S1_PROMPT_V4.version == "v0.2-s1-planner-4"
      assert _S1_PROMPT_V5.version == "v0.2-s1-planner-5"
      assert _S1_PROMPT_V4.system_prompt != _S1_PROMPT_V5.system_prompt
      assert hashlib.sha256(_S1_PROMPT_V5.system_prompt.encode()).hexdigest()

  def test_t185_v5_prompt_contains_no_evaluation_truth() -> None:
      forbidden = {
          "causal_faults", "knowledge_policy", "sufficient_evidence_sets",
          "observable_conditions", "acceptable_outcomes", "held_out",
      }
      lowered = _S1_PROMPT_V5.system_prompt.lower()
      for token in forbidden:
          assert token not in lowered
  ```

  Capture the default `RealLLMPlanner` outbound user message and assert it identifies v5 and contains only `prompt_version` plus serialized `PlannerContext`; it must not contain samples, `frequencies_hz`, generator inputs, or any forbidden evaluation field. Separately assert `_Phase4V4RealLLMPlanner` sends the byte-identical v4 prompt and v4 user-message identity.

- [x] **Step 2: Write failing dual-truth and action-policy tests**

  Assert the v5 prompt explicitly states all of the following without fixing a Tool order:

  ```python
  required_meanings = (
      "distortion presence and configured acceptance are separate",
      "rule pass does not erase observed distortion",
      "evaluate_rules",
      "retrieve_knowledge",
      "invalid or not applicable",
      "stop when sufficient evidence exists",
  )
  for meaning in required_meanings:
      assert meaning in _S1_PROMPT_V5.system_prompt.lower()
  assert "detect_clipping then analyze_harmonic_distortion" not in lowered
  ```

  Feed the active `RealLLMPlanner` a fake response containing a supported harmonic claim with both Evidence refs and a PASS `ruleval_*` ref. T186 must parse it without rewriting the outcome to `no_supported_fault`.

- [x] **Step 3: Write failing full-runtime fake-model scenarios**

  In `test_phase4_1_acceptance.py`, implement `_PolicyFakeCompletions.create` by parsing `kwargs["messages"][1]["content"]`. It returns exactly one JSON decision from current context:

  ```python
  if not observations:
      return call_tool(first_tool)
  if route_requires_second_tool and len(observations) == 1:
      return call_tool(second_tool)
  if invalid_harmonic and not knowledge_retrievals:
      return retrieve_knowledge(tags=["inconclusive"])
  if evidence and not rule_evaluation_batches:
      return evaluate_rules(all_current_evidence_ids)
  return finish_with_only_live_evidence_rule_and_knowledge_ids()
  ```

  Execute the active `RealLLMPlanner` through `RecordingPlanner` and the unchanged `DistortionDiagnosisRuntime` with real generated signals and real Phase 1–3 dependencies. Cover:

  - T187: applicable Evidence → rule batch → next PlannerContext → final `rule_refs`;
  - T188: invalid harmonic Evidence → relevant retrieval → `inconclusive` claim with Evidence/Knowledge refs and non-empty limitation;
  - T189: all Evidence, Rule, and Knowledge refs resolve within the same run and assembled trace;
  - T190: one scenario is clipping-first and another harmonic-first, both finish without a fixed complete Tool sequence.

  Add required unnumbered regressions for two honest degradation paths: an
  empty/irrelevant retrieval must never be cited, and a not-applicable rule
  judgment must never be described as PASS. Both runs retain Evidence and an
  explicit limitation rather than fabricating content.

- [x] **Step 4: Run the RED suites**

  ```powershell
  $py = 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
  & $py -m pytest tests/agent/test_phase4_1_prompt.py tests/evaluation/test_phase4_1_acceptance.py -q
  ```

  Expected: collection fails because `signal_diag.agent.prompts` and `_Phase4V4RealLLMPlanner` do not exist.

- [x] **Step 5: Implement immutable prompt specifications**

  Create:

  ```python
  @dataclass(frozen=True, slots=True)
  class _PlannerPromptSpec:
      version: str
      system_prompt: str

  _S1_PROMPT_V4 = _PlannerPromptSpec(
      version="v0.2-s1-planner-4",
      system_prompt=_LEGACY_S1_SYSTEM_PROMPT,
  )
  _S1_PROMPT_V5 = _PlannerPromptSpec(
      version="v0.2-s1-planner-5",
      system_prompt=_S1_PROMPT_V4.system_prompt + _PHASE4_1_POLICY,
  )
  ```

  Use this exact policy addition:

  ```python
  _PHASE4_1_POLICY = """

  Phase 4.1 observation-driven decision policy:
  - Distortion presence and configured acceptance are separate facts. Rule PASS
    does not erase observed distortion. Report both facts when both are true.
  - Choose the first DSP Tool from the current request, metadata, hypotheses,
    and observations. There is no required universal Tool order.
  - Before finishing, when current S1 Evidence is relevant and has not yet been
    evaluated under the configured profile, evaluate profile_s1_distortion once.
  - Rule conclusions cite live ruleval_* IDs and never replace Evidence refs.
  - Before finishing inconclusive because a result is invalid or not applicable,
    retrieve curated explanatory knowledge when no relevant retrieval is already
    present. Finish with an inconclusive claim citing live Evidence and the used
    know_* ID, plus a non-empty limitation.
  - Do not retrieve knowledge merely to decorate a straightforward result.
  - Cite only IDs in the current context and stop when sufficient evidence exists.
  """
  ```

  Move the legacy literal without reformatting it; verify its SHA-256 against
  `b68ec5e`. The new policy must not mention dataset categories, evaluation
  policy fields, expected outcomes, case IDs, score targets, or held-out
  behavior.

- [x] **Step 6: Bind v5 without changing the public constructor**

  Define `_LEGACY_S1_SYSTEM_PROMPT` by moving the complete current
  `planner.py` `_SYSTEM_PROMPT` literal into `prompts.py` byte-for-byte; do not
  reflow or edit it.

  Refactor only the prompt lookup inside `RealLLMPlanner`:

  ```python
  class RealLLMPlanner:
      _prompt_spec = _S1_PROMPT_V5

      @property
      def prompt_version(self) -> str:
          return self._prompt_spec.version

  class _Phase4V4RealLLMPlanner(RealLLMPlanner):
      _prompt_spec = _S1_PROMPT_V4
  ```

  Change `_build_user_message` to require keyword-only `prompt_version`.
  `_decide_deepseek` uses `self._prompt_spec.system_prompt` and passes
  `self.prompt_version` to the user-message builder. Set the active aliases to:

  ```python
  PROMPT_VERSION = _S1_PROMPT_V5.version
  _SYSTEM_PROMPT = _S1_PROMPT_V5.system_prompt
  ```

  Existing callers constructing `RealLLMPlanner` therefore receive the approved
  v5 product prompt without a constructor change. The legacy Phase 4 runner is
  the only caller of `_Phase4V4RealLLMPlanner`.

- [x] **Step 7: Run GREEN, legacy regression, and commit**

  ```powershell
  & $py -m pytest tests/agent/test_real_llm_planner.py tests/agent/test_phase4_1_prompt.py tests/evaluation/test_phase4_1_acceptance.py -q
  & $py -m pytest -q
  & $py -m ruff check --no-cache src tests scripts
  & $py -m mypy --no-incremental src
  git diff --check b68ec5e..HEAD
  ```

  Expected: legacy v4 tests and T184–T190 all pass; no real network call occurs.

  ```powershell
  git add src/signal_diag/agent/prompts.py src/signal_diag/agent/planner.py tests/agent/test_phase4_1_prompt.py tests/evaluation/test_phase4_1_acceptance.py
  git commit -m "feat(agent): add Phase 4.1 planner policy"
  ```

---

### Task 3: Add the Fresh v1.1.0 Dataset

**Files:**
- Create: `src/signal_diag/evaluation/manifests/s1_distortion_v1_1.yaml`
- Modify: `src/signal_diag/evaluation/dataset.py`
- Modify: `tests/evaluation/conftest.py`
- Create: `tests/evaluation/test_phase4_1_dataset.py`

**Test IDs:** T191–T193

**Interfaces:**
- Consumes: existing `DatasetManifest`, generators, materializer, real Tools, RuleEngine, and v1.0.0 allocation validation.
- Produces: packaged v1.1.0 manifest and additive validator support. `load_dataset_manifest` and `validate_dataset` signatures remain unchanged.

- [x] **Step 1: Write the failing identity, natural-request, and isolation tests**

  Add a `PHASE4_1_MANIFEST` fixture path without changing `CANONICAL_MANIFEST`. Assert exact 8/16 allocation, exact category counts, unique IDs, deterministic reconstruction, and real-DSP validation. T192 rejects Tool names, `clipping`, `harmonic_distortion`, `causal_faults`, and order words such as `first`, `then`, or `pipeline` in every request. T193 compares v1.1 development and held-out cases and rejects equal case IDs, full signal-spec dumps, noise seeds, or exact request strings across splits; it also rejects exact v1.0.0 held-out signal-spec dumps in v1.1.0 held-out.

- [x] **Step 2: Run dataset RED**

  ```powershell
  & $py -m pytest tests/evaluation/test_phase4_1_dataset.py -q
  ```

  Expected: the v1.1 manifest path is absent and validator identity rejects version `1.1.0`.

- [x] **Step 3: Write the exact 24-case signal matrix**

  All cases use 48 kHz and 2.0 seconds. Sines use phase 0 and DC offset 0; noise uses RMS 0.1.

  ```text
  case_v11_dev_clean_01: sine 150 Hz, amplitude 0.53
  case_v11_dev_clean_02: sine 350 Hz, amplitude 0.61
  case_v11_dev_clipping_boundary: clipped 63 Hz, amplitude 0.95, clip 0.94999
  case_v11_dev_clipping_strong: clipped 150 Hz, amplitude 0.88, clip 0.64
  case_v11_dev_harmonic_boundary: harmonic 200 Hz, amplitude 0.48, {2: 0.04999999}
  case_v11_dev_harmonic_strong: harmonic 425 Hz, amplitude 0.48, {2: 0.085}
  case_v11_dev_combined_01: combined 150 Hz, amplitude 0.88, {3: 0.16}, clip 0.70, signature order 3, separation 0.08
  case_v11_dev_invalid_noise_01: white noise seed 101

  case_v11_held_clean_01: sine 175 Hz, amplitude 0.43
  case_v11_held_clean_02: sine 375 Hz, amplitude 0.57
  case_v11_held_clean_03: sine 475 Hz, amplitude 0.67
  case_v11_held_clipping_01: clipped 65 Hz, amplitude 0.88, clip 0.87999
  case_v11_held_clipping_02: clipped 80 Hz, amplitude 0.88, clip 0.87999
  case_v11_held_clipping_03: clipped 61 Hz, amplitude 0.88, clip 0.87999
  case_v11_held_clipping_04: clipped 425 Hz, amplitude 0.90, clip 0.70
  case_v11_held_harmonic_01: harmonic 225 Hz, amplitude 0.46, {2: 0.04}
  case_v11_held_harmonic_02: harmonic 350 Hz, amplitude 0.52, {2: 0.04999999}
  case_v11_held_harmonic_03: harmonic 475 Hz, amplitude 0.48, {2: 0.075}
  case_v11_held_harmonic_04: harmonic 300 Hz, amplitude 0.46, {2: 0.07, 3: 0.03}
  case_v11_held_combined_01: combined 225 Hz, amplitude 0.88, {3: 0.17}, clip 0.71, signature order 3, separation 0.05
  case_v11_held_combined_02: combined 350 Hz, amplitude 0.90, {2: 0.11, 3: 0.07}, clip 0.69, signature order 2, separation 0.06
  case_v11_held_combined_03: combined 400 Hz, amplitude 0.90, {2: 0.14}, clip 0.77, signature order 2, separation 0.10
  case_v11_held_invalid_noise_01: white noise seed 211
  case_v11_held_invalid_noise_02: white noise seed 307
  ```

  Calibration expectations from accepted DSP are: clipping ratios 0.009875 and 0.48125 for the two dev clipping cases; held clipping ratios 0.009375, 0.010000, 0.011625, and about 0.432292; harmonic THD about 5.0%, 8.5%, 4.0%, 5.0%, 7.5%, and 7.616%; combined signature separations exceed the declared 0.08/0.05/0.06/0.10 values. These are dataset-QA expectations, never product thresholds.

- [x] **Step 4: Assign natural requests without answer leakage**

  Alternate only these development phrasings:

  ```text
  Explain what is making this periodic signal sound distorted.
  Analyze the audible distortion in this waveform.
  ```

  Assign held-out cases among these four different phrasings:

  ```text
  Why does this signal sound distorted?
  What is causing the distortion I hear in this waveform?
  Diagnose the source of this signal's audible distortion.
  Analyze why this periodic waveform sounds wrong.
  ```

  Use the Phase 4 condition templates and dual truth. Harmonic cases below or at 5% still support a harmonic-distortion causal claim while their `lte 5.0` rule condition passes. Invalid/noise cases require `knowledge_tags: [inconclusive]`, an inconclusive outcome, and a limitation. Do not encode one complete Tool sequence.

- [x] **Step 5: Generalize dataset identity validation additively**

  Replace the single version constant with exact supported identities:

  ```python
  _SUPPORTED_DATASETS = frozenset({
      ("s1-distortion-synthetic", "1.0.0"),
      ("s1-distortion-synthetic", "1.1.0"),
  })
  ```

  Keep the same allocation counters for both. Unknown IDs/versions still produce `dataset_identity`; no caller chooses counts or bypasses validation.

- [x] **Step 6: Run GREEN, package check, cumulative tests, and commit**

  ```powershell
  & $py -m pytest tests/evaluation/test_dataset.py tests/evaluation/test_phase4_1_dataset.py -q
  & $py -m pip wheel . --no-deps --no-build-isolation --wheel-dir build/phase4_1_wheel
  & $py -m pytest -q
  & $py -m ruff check --no-cache src tests scripts
  & $py -m mypy --no-incremental src
  git diff --check b68ec5e..HEAD
  ```

  Confirm the wheel contains both YAML manifests. Do not add `build/`.

  ```powershell
  git add src/signal_diag/evaluation/dataset.py src/signal_diag/evaluation/manifests/s1_distortion_v1_1.yaml tests/evaluation/conftest.py tests/evaluation/test_phase4_1_dataset.py
  git commit -m "feat(evaluation): add fresh Phase 4.1 dataset"
  ```

---

### Task 4: Add Phase 4.1 Development and Official Campaign Runners

**Files:**
- Modify: `src/signal_diag/evaluation/scoring.py`
- Modify: `src/signal_diag/evaluation/runner.py`
- Modify: `src/signal_diag/evaluation/__main__.py`
- Create: `tests/evaluation/test_phase4_1_runner.py`

**Test IDs:** completion of T184 and T194; required unnumbered development-gate regressions

**Interfaces:**
- Consumes: `_S1_PROMPT_V5`, `_Phase41RealLLMPlanner`, v1.1.0 manifest, existing slot retry, trace, score, aggregate, and bundle code.
- Produces: private `_phase4_1_benchmark_config`, `_run_phase4_1_development_benchmark`, `_run_phase4_1_official_benchmark`, and additive CLI `--campaign`. Existing public functions and legacy private wrappers retain behavior.

- [x] **Step 1: Write failing legacy-preservation and campaign-config tests**

  Assert legacy `_official_benchmark_config` still records v4/v1.0.0 and its existing fingerprint. Assert Phase 4.1 config records exactly:

  ```python
  assert config.dataset_version == "1.1.0"
  assert config.provider == "deepseek"
  assert config.model == "deepseek-v4-flash"
  assert config.prompt_version == "v0.2-s1-planner-5"
  assert config.prompt_sha256 == sha256(_S1_PROMPT_V5.system_prompt.encode()).hexdigest()
  assert config.repetitions == 5
  assert config.max_infrastructure_retries == 2
  assert config.max_concurrency == 1
  ```

- [x] **Step 2: Write failing split and CLI tests**

  With a mini manifest containing two development and two held-out cases, assert the development wrapper schedules 2 x 5 Agent slots and the official wrapper schedules 2 x 5 held-out slots. The canonical v1.1.0 campaign must schedule 8 x 5 = 40 development slots and 16 x 5 = 80 official slots. Add `--campaign` choices while preserving exactly the four existing subcommand names:

  ```text
  phase4
  phase4.1-development
  phase4.1-official
  ```

  `run-real` defaults to `phase4` for backward compatibility. No credential argument is added.

  Parametrize the new Phase 4.1 wrappers with the existing fake timeout, 429,
  provider-5xx, authentication, invalid-output, no-progress, Tool-budget,
  rule-budget, and knowledge-budget handlers. Assert the exact frozen retry,
  attempt, completion, pending/incomplete, and no-fallback behavior. This
  proves the extracted shared loop did not preserve errors only for legacy v4.

- [x] **Step 3: Write failing split-aware aggregation tests**

  Verify the public `aggregate_benchmark` still scores held-out only. Verify a new private helper can calculate development metrics/status from development scores without mutating case splits or the manifest. The development report must add the warning `development split; not official held-out evidence`. A complete 40-slot dev report may be `meets_target`; missing slots are `incomplete`. The official path keeps frozen status semantics.

  Because `BenchmarkConfig` is frozen and has no split field, development and
  official runs with otherwise identical settings intentionally share one
  configuration fingerprint. Assert that scope remains unambiguous through
  the development warning and the exact split membership of recorded case IDs;
  do not overload provider `model_parameters` with evaluation metadata.

- [x] **Step 4: Run runner RED**

  ```powershell
  & $py -m pytest tests/evaluation/test_runner.py tests/evaluation/test_scoring.py tests/evaluation/test_phase4_1_runner.py -q
  ```

  Expected: Phase 4.1 config, wrappers, split aggregation, and campaign option are absent.

- [x] **Step 5: Refactor aggregation behind an unchanged public wrapper**

  Introduce private `_aggregate_benchmark_for_split` with the same six
  positional parameters as `aggregate_benchmark` and keyword-only
  `harness_status: HarnessStatus`, `score_split: EvaluationSplit`, and
  an empty-default tuple-of-strings named `extra_warnings`; it returns
  `BenchmarkReport`.

  `aggregate_benchmark` delegates with `score_split="held_out"` and no extra warning. Generalize only private score filtering and expected-slot status calculation to use `score_split`. Do not change rate formulas, target bands, fingerprint logic, or the public signature.

- [x] **Step 6: Add v5 config, preflight, and planner construction**

  Keep `_official_*` constants and functions semantically intact, but make their
  prompt hash and preflight checks read `_S1_PROMPT_V4` directly instead of the
  now-active module aliases. `_build_official_planner` constructs
  `_Phase4V4RealLLMPlanner`, preserving legacy execution. Add `_PHASE4_1_*`
  constants and hash the exact v5 prompt. Phase 4.1 preflight verifies v1.1.0,
  v5 hash/version, DeepSeek/model, profile, concurrency, credentials,
  dependency, and dataset validity. Build the Phase 4.1 planner as:

  ```python
  def _build_phase4_1_planner(inner_client: object) -> RealLLMPlanner:
      capture = _UsageCapturingClient(inner_client)
      return RealLLMPlanner(provider="deepseek", client=capture)
  ```

  Do not wrap either real planner in `_ContextBoundScriptedPlanner`.

- [x] **Step 7: Generalize only private execution plumbing**

  Extract the current official loop into private
  `_run_real_benchmark_for_split`, receiving `score_split`, `planner_builder`,
  `preflight`, and `baseline_case_ids` in addition to the existing manifest,
  config, output, client/error/import/clock inputs. Preserve
  `_run_official_benchmark` as a legacy held-out/v4 delegator. Add
  `_run_phase4_1_development_benchmark` for development Agent 8 x 5 plus one
  development baseline per case, and `_run_phase4_1_official_benchmark` for
  held-out Agent 16 x 5 plus the existing 24-case baseline schedule. Both
  return `BenchmarkReport` and retain the existing injectable client factory,
  error classifier, dependency importer, and clock keywords.

  Both reuse the frozen retry classifier, AttemptRecord semantics, trace assembly, scorer, and append-only writer. Do not catch behavioral failures as infrastructure retries.

- [x] **Step 8: Add additive CLI routing**

  `run-real --campaign phase4` selects legacy v4/v1.0.0. The two Phase 4.1 choices require the v1.1.0 manifest, construct the v5 config, and route to the corresponding wrapper. If `--manifest` conflicts with the selected campaign identity, return an invalid-configuration report; do not silently rewrite config identity.

- [x] **Step 9: Run GREEN, CLI smoke tests, cumulative tests, and commit**

  ```powershell
  & $py -m pytest tests/evaluation/test_runner.py tests/evaluation/test_scoring.py tests/evaluation/test_phase4_1_runner.py -q
  & $py -m signal_diag.evaluation run-real --help
  & $py -m pytest -q
  & $py -m ruff check --no-cache src tests scripts
  & $py -m mypy --no-incremental src
  git diff --check b68ec5e..HEAD
  ```

  ```powershell
  git add src/signal_diag/evaluation/scoring.py src/signal_diag/evaluation/runner.py src/signal_diag/evaluation/__main__.py tests/evaluation/test_phase4_1_runner.py
  git commit -m "feat(evaluation): add Phase 4.1 benchmark campaigns"
  ```

---

### Task 5: Enforce T195 and Obtain Independent Deterministic Review

**Files:**
- Modify: `tests/test_architecture_boundaries.py`
- Modify: `docs/superpowers/plans/2026-08-30-phase4-1-agent-behavior-improvement.md` only to check completed implementation boxes

**Test IDs:** T195 and cumulative T001–T195

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: deterministic Phase 4.1 implementation evidence. It does not claim real-model acceptance.

- [x] **Step 1: Add the T195 baseline check**

  Preserve T183's `9bd01f2` check and add a separate test:

  ```python
  _PHASE4_1_BASELINE = "b68ec5e"

  def test_t195_diff_check_against_phase4_1_baseline() -> None:
      result = subprocess.run(
          ["git", "diff", "--check", f"{_PHASE4_1_BASELINE}..HEAD"],
          cwd=PROJECT_ROOT,
          capture_output=True,
          text=True,
          check=False,
      )
      assert result.returncode == 0, result.stdout + result.stderr
  ```

- [x] **Step 2: Run all Phase 4.1 focused tests with skip details**

  ```powershell
  & $py -m pytest tests/agent/test_phase4_1_prompt.py tests/evaluation/test_phase4_1_acceptance.py tests/evaluation/test_phase4_1_dataset.py tests/evaluation/test_phase4_1_runner.py tests/test_architecture_boundaries.py -q -rxXs -p no:cacheprovider --basetemp .pytest_cache/phase4-1-focused
  ```

  Expected: T184–T195 pass; no required skip or xfail.

- [x] **Step 3: Run the complete deterministic quality gate**

  ```powershell
  & $py -m pytest -q -rxXs -p no:cacheprovider --basetemp .pytest_cache/phase4-1-full
  & $py -m ruff check --no-cache src tests scripts
  & $py -m mypy --no-incremental src
  git diff --check b68ec5e..HEAD
  ```

  Expected: T001–T195 pass, zero required skip/xfail, Ruff clean, mypy clean, and diff-check clean. Record exact counts and outputs; do not reuse the previous 451-pass result.

- [x] **Step 4: Commit the deterministic cumulative gate**

  ```powershell
  git add tests/test_architecture_boundaries.py docs/superpowers/plans/2026-08-30-phase4-1-agent-behavior-improvement.md
  git commit -m "test(evaluation): enforce Phase 4.1 deterministic gate"
  ```

- [x] **Step 5: Request independent code review**

  Use `superpowers:requesting-code-review` on `b68ec5e..HEAD`. Require separate checks for legacy v4 reproducibility, no evaluation leakage, no controller-forced actions, dual-truth language, same-run refs, v1.1 fixture fairness, split isolation, private split aggregation, retry honesty, append-only reports, and T001–T183 regression. Apply accepted findings with `superpowers:receiving-code-review`, rerun Step 3, and commit fixes separately.

---

### Task 6: Run and Freeze the 40-Slot Development Gate

**Files:**
- Create: `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/benchmark_manifest.json`
- Create: `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/runs.jsonl`
- Create: `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/metrics.json`
- Create: `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/case_summary.csv`
- Create: `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/report.md`
- Create: `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/checksums.sha256`

**Interfaces:**
- Consumes: frozen deterministic implementation, v5 prompt, v1.1.0 development cases, real DeepSeek credentials.
- Produces: one append-only 40-slot development bundle. It is tuning evidence, not official held-out proof.

- [ ] **Step 1: Verify the pre-run freeze and credential gate**

  Re-run Task 5 Step 3. Confirm `DEEPSEEK_API_KEY` exists without printing its value. Confirm the destination directory does not exist. Record v5 SHA-256, git HEAD, Python, OpenAI SDK, dataset, profile, provider, and model identities.

- [ ] **Step 2: Run exactly one development campaign**

  ```powershell
  & $py -m signal_diag.evaluation run-real --campaign phase4.1-development --benchmark-id bench_phase4_1_dev_v5_gate1 --output-dir docs/evaluations/phase4_1/development
  ```

  Do not use a fake client. Do not run any v1.1.0 held-out case in this task.

- [ ] **Step 3: Verify the development bundle independently**

  Validate exactly six files and their checksums. Parse all records through repository Pydantic models. Confirm 40 unique Agent slots over only the 8 development case IDs, no unscored slot, `benchmark_status=completed`, and `target_status=meets_target`. Recompute every RunScore and aggregate from stored traces and compare exact serialized values. Scan artifacts for credentials, raw provider bodies, waveform/sample arrays, evaluation-truth leakage, and platform paths.

  If the report is `below_target`, commit the honest bundle, report the failing metrics, and stop before Task 7. Do not inspect or run v1.1.0 held-out behavior. Prompt-only remediation requires a new approved prompt version and a new development benchmark ID.

- [ ] **Step 4: Commit the immutable development evidence**

  ```powershell
  git add docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1
  git commit -m "docs: record Phase 4.1 development benchmark"
  ```

---

### Task 7: Run the One-Shot 80-Slot Official Gate

**Files:**
- Create: `docs/evaluations/phase4_1/official/bench_official_s1_v11_planner5_gate1/benchmark_manifest.json`
- Create: `docs/evaluations/phase4_1/official/bench_official_s1_v11_planner5_gate1/runs.jsonl`
- Create: `docs/evaluations/phase4_1/official/bench_official_s1_v11_planner5_gate1/metrics.json`
- Create: `docs/evaluations/phase4_1/official/bench_official_s1_v11_planner5_gate1/case_summary.csv`
- Create: `docs/evaluations/phase4_1/official/bench_official_s1_v11_planner5_gate1/report.md`
- Create: `docs/evaluations/phase4_1/official/bench_official_s1_v11_planner5_gate1/checksums.sha256`

**Interfaces:**
- Consumes: a verified `completed/meets_target` development bundle and exactly the same frozen prompt/configuration.
- Produces: the only v1.1.0 held-out gate1 official bundle.

- [ ] **Step 1: Prove configuration identity before held-out execution**

  Compare provider, model, model parameters, prompt version/SHA, SDK versions, dataset/profile identities, repetitions, retry count, and concurrency against the development bundle. Only benchmark ID and timestamp may differ; the selected wrapper changes the executed split without changing `BenchmarkConfig`. Any other difference stops execution.

- [ ] **Step 2: Run the official held-out campaign once**

  ```powershell
  & $py -m signal_diag.evaluation run-real --campaign phase4.1-official --benchmark-id bench_official_s1_v11_planner5_gate1 --output-dir docs/evaluations/phase4_1/official
  ```

  Do not rerun this benchmark ID after results exist.

- [ ] **Step 3: Independently verify all official evidence**

  Confirm exactly 80 unique, scoreable Agent slots over 16 held-out cases, five slots per case, and the expected deterministic baseline artifacts. Verify six-file checksums, Pydantic validation, trace/config fingerprints, score recomputation, aggregate recomputation, failure-code coverage, no secrets/raw responses/waveforms, and append-only refusal.

  Required acceptance is:

  ```text
  benchmark_status = completed
  target_status = meets_target
  all 80 Agent slots scoreable
  every non-zero-denominator target passes
  b68ec5e baseline still present and unchanged
  ```

  If the report is `completed/below_target`, retain and commit it honestly, leave Phase 4.1 unaccepted, keep Phase 5 gated, and do not tune against or rerun these held-out cases.

- [ ] **Step 4: Commit the immutable official bundle**

  ```powershell
  git add docs/evaluations/phase4_1/official/bench_official_s1_v11_planner5_gate1
  git commit -m "docs: record official Phase 4.1 benchmark"
  ```

---

### Task 8: Record Final Phase 4.1 Acceptance Without Opening Phase 5

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/superpowers/plans/2026-08-30-phase4-1-agent-behavior-improvement.md`

**Interfaces:**
- Consumes: independently verified deterministic gate, development bundle, and official bundle.
- Produces: honest accepted or below-target project status. It does not authorize Phase 5 implementation.

- [ ] **Step 1: Re-run the complete post-benchmark deterministic gate**

  Run Task 5 Step 3 from the final HEAD. Revalidate both Phase 4.1 bundles and confirm the `b68ec5e` bundle checksums remain unchanged.

- [ ] **Step 2: Update status from actual evidence**

  Immediately before editing status docs, run `git rev-parse HEAD` and record
  that exact official-evidence commit in the sentence “Phase 4.1 accepted at
  SHA; Phase 5 remains gated pending written Phase 5 design.” Record exact test
  count, commands, prompt/dataset/config identities, development and official
  benchmark IDs, and target metrics. If official status is below target or
  incomplete, record that actual status and do not use “accepted.”

- [ ] **Step 3: Commit status documentation**

  ```powershell
  git add AGENTS.md docs/README.md docs/DECISIONS.md docs/superpowers/plans/2026-08-30-phase4-1-agent-behavior-improvement.md
  git commit -m "docs: record Phase 4.1 acceptance status"
  ```

- [ ] **Step 4: Request final independent acceptance review**

  Review `b68ec5e..HEAD`, rerun the full deterministic gate, recompute both report bundles, and verify no Phase 5 files exist. Do not merge or push until the user reviews that evidence.

## T184–T195 Mapping

```text
T184  Task 2 prompt identity + Task 4 campaign fingerprint
T185  Task 2 prompt/context no-leakage tests
T186  Task 2 dual causal/rule truth
T187  Task 2 rule action propagation through real runtime
T188  Task 2 invalid Evidence -> knowledge -> inconclusive path
T189  Task 2 same-run Evidence/Rule/Knowledge traceability
T190  Task 2 dynamic alternate S1 routes and no fixed Tool order
T191  Task 3 v1.1.0 manifest identity/allocation/reconstruction
T192  Task 3 natural non-leading user requests
T193  Task 3 development/held-out/v1.0-held-out isolation
T194  Task 4 frozen v5/v1.1 config and 16 x 5 official schedule
T195  Task 5 cumulative T001–T195 and quality gate
```

The 40-slot development runner is additionally required by the written spec and Task 4 tests even though it does not receive a separate public test ID. Tasks 6–7 are real-model behavior gates outside normal CI.

## Expected Local Commit Sequence

```text
docs: freeze Phase 4.1 behavior gate
feat(agent): add Phase 4.1 planner policy
feat(evaluation): add fresh Phase 4.1 dataset
feat(evaluation): add Phase 4.1 benchmark campaigns
test(evaluation): enforce Phase 4.1 deterministic gate
docs: record Phase 4.1 development benchmark
docs: record official Phase 4.1 benchmark
docs: record Phase 4.1 acceptance status
```

Do not squash, push, merge, delete worktrees, or start Phase 5 during this plan.
