# Phase 4.3.1 Planner v8.1 Compliance Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task-by-task.
> Every implementation task also uses `superpowers:test-driven-development`;
> every review response uses `superpowers:receiving-code-review`; every
> completion claim uses `superpowers:verification-before-completion`. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the Phase 4.3 request-scope and invalid-Evidence scoring
non-conformances, prove the existing real-LLM product boundary deterministically,
and run one legally gated v8.1 development campaign plus a conditional official
campaign without changing public Agent contracts or historical evidence.

**Architecture:** Add one complete `v0.2-s1-planner-8.1` prompt while moving v8
behind a private historical planner. Keep the public scoring API legacy-stable,
but dispatch internally from `BenchmarkConfig.sdk_versions` to scoring policy
`signal_diag.scoring=2.0.0` for Phase 4.3.1. Add private runner/config/campaign
bindings above the existing v1.2 dataset and product Runtime; no action is
forced by deterministic control.

**Tech Stack:** Python 3.12, Pydantic v2, NumPy/SciPy deterministic DSP,
pytest/pytest-asyncio, Ruff, mypy, DeepSeek's OpenAI-compatible client, and the
existing immutable evaluation-bundle writer.

**Spec:**
`docs/superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md`

**Implementation baseline:** `1b94194` on `phase4-evaluation-design`

**Design baseline:** `c20a744` freezes §54, TEST_PLAN §27 T216–T223, D025,
OQ-009, and the Phase 4.3.1 stage documentation.

**Execution start:** Cursor begins at Task 2. Task 1 was completed by Codex.
Nothing in this plan authorizes implementation or model execution until the
user separately gives the Cursor execution instruction.

## Global Constraints

- Read `AGENTS.md` and every document it lists before Task 2.
- Start from committed `c20a744` on `phase4-evaluation-design`; preserve the
  existing untracked `build/` directory without staging, deleting, or moving it.
- Preserve dataset `s1-distortion-synthetic` `1.2.0` byte-for-byte, including
  requests, IDs, parameters, seeds, conditions, policies, and split membership.
- Preserve all v4–v8 prompt bytes, hashes, private planners, configurations,
  fingerprints, routes, reports, and committed evaluation bundles.
- Do not change public `PlannerModel`, `PlannerContext`, `AgentDecision`,
  `TaskAssessment`, `DiagnosisClaim`, `DistortionDiagnosisRuntime`,
  `BenchmarkConfig`, score/report models, or `score_evaluation_trace(case,
  trace)` signature.
- Do not change DSP, Tool, Evidence, RuleEngine, profile, KnowledgeIndex,
  corpus, demo thresholds, `TargetBands`, provider, model, model parameters,
  repetitions, or historical scoring semantics.
- `RealLLMPlanner` is the product path. ScriptedPlanner and fake transports are
  deterministic test doubles only and never runtime fallbacks.
- Runtime must not classify request text, construct an action, force/reorder an
  action, or encode a universal Tool pipeline.
- Never send raw waveform, full FFT, case/category/split, generator truth,
  causal truth, policies, acceptable Tools, sufficient sets, conditions,
  scoring versions, or targets to the model.
- Numerical values come only from deterministic DSP; thresholds come only from
  `profile_s1_distortion` `1.0.0-demo`. The 1% clipping and 5% THD values remain
  demonstration thresholds, not industry standards.
- Do not push, merge, delete the worktree, open Phase 5, create v8.2/v9, or
  inspect official held-out behavior before the exact development gate passes.
- The canonical v8.1 development identity runs once. A result other than
  `completed/meets_target` is preserved and stops before official.
- The official identity runs once only after a committed, checksum-valid,
  byte-identical development `completed/meets_target` result.

## Required Per-Task Review Protocol

For Tasks 2–7 and any code/document correction in Tasks 8–10, Cursor must use
this exact serial sequence:

1. A fresh Implementer agent performs RED → GREEN TDD and leaves changes
   uncommitted.
2. A separate agent reviews specification compliance against §54, the assigned
   T216–T223 IDs, D025, the approved spec, and this Task.
3. The Implementer fixes every Critical or Important spec finding; a separate
   agent re-reviews each fix to closure.
4. A separate agent performs code-quality review.
5. The Implementer fixes every Critical or Important quality finding; a
   separate agent re-reviews each fix to closure.
6. The main Cursor controller independently inspects the diff and reruns the
   Task's focused and cumulative verification.
7. Only the main Cursor controller creates the local Task commit.

Do not let agents modify the same worktree concurrently. Do not begin another
Task before the current Task is committed. A review narrative is not evidence;
Git state and independently rerun commands determine status.

Use this Python executable for all commands:

```powershell
& 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

---

### Task 1: Freeze Phase 4.3.1 design and acceptance contracts — complete

**Files:**

- Created:
  `docs/superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md`
- Modified: `AGENTS.md`, `docs/README.md`, `docs/CONTRACTS_V0_2.md`,
  `docs/TEST_PLAN_V0_2.md`, `docs/DECISIONS.md`,
  `docs/OPEN_QUESTIONS.md`

**Produces:** Frozen §54, T216–T223, D025, OQ-009, exact campaign identities,
and this plan's authority boundary.

Completed by Codex in local commits:

```text
45907ac  docs: design Phase 4.3.1 compliance correction
c20a744  docs: freeze Phase 4.3.1 compliance gate
```

Cursor must not redo, amend, squash, or reinterpret Task 1.

---

### Task 2: Add the complete v8.1 prompt and preserve v8 privately

**Files:**

- Modify: `src/signal_diag/agent/prompts.py`
- Modify: `src/signal_diag/agent/planner.py`
- Create: `tests/agent/test_phase4_3_1_prompt_v8_1.py`
- Modify: `tests/agent/test_phase4_3_prompt_v8.py`
- Modify: `tests/agent/test_real_llm_planner.py`

**Interfaces:**

- Consumes: `_PlannerPromptSpec`, `_S1_PROMPT_V8`, and existing
  `RealLLMPlanner` transport/normalization behavior.
- Produces: `_S1_PROMPT_V8_1`, active v8.1 `RealLLMPlanner`, and private
  `_Phase4V8RealLLMPlanner` for exact historical v8 campaigns.
- Keeps `RealLLMPlanner.__init__`, `decide`, `_build_user_message`, and all
  public model signatures unchanged.

- [ ] **Step 1: Re-establish historical prompt evidence**

  Run:

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/agent/test_phase4_3_prompt_v8.py tests/agent/test_real_llm_planner.py -q
  ```

  Expected: green before edits. Preserve the frozen v8 identity:

  ```text
  version  v0.2-s1-planner-8
  bytes    12275
  sha256   bf5355ef514574bd2ec4dfda0b3afd2e9810d6031fd1bb9fc13c54fc9fcb8b7e
  ```

- [ ] **Step 2: Write T216 identity RED tests**

  In `test_phase4_3_1_prompt_v8_1.py`, require:

  ```python
  assert _S1_PROMPT_V8_1.version == "v0.2-s1-planner-8.1"
  assert RealLLMPlanner._prompt_spec is _S1_PROMPT_V8_1
  assert PROMPT_VERSION == "v0.2-s1-planner-8.1"
  assert _SYSTEM_PROMPT == _S1_PROMPT_V8_1.system_prompt
  assert _Phase4V8RealLLMPlanner._prompt_spec is _S1_PROMPT_V8
  ```

  Keep literal hash/byte assertions for v4–v8. Require v8.1 to be distinct and
  not constructed by prefixing/appending v8. Update the old v8 test only so it
  verifies `_Phase4V8RealLLMPlanner`; do not remove its frozen assertions.

- [ ] **Step 3: Write T217–T219 semantic RED tests**

  Parse every embedded JSON object using the existing balanced-brace helper.
  Require these mutually consistent examples and policies:

  ```text
  clipping-specific initial hypotheses: ["clipping"]
  harmonic-specific initial hypotheses: ["harmonic_distortion"]
  generic broad initial hypotheses: ["clipping", "harmonic_distortion"]
  clipping-specific supported finish: exactly one clipping causal claim
  broad/combined after clipping: continue only while harmonic remains viable
  strong clipping + odd orders 3/5: clipping-only, even when THD rule is FAIL
  independent harmonic cause: requires reportable order-2 Evidence
  invalid/noise: invalid Evidence -> NOT_APPLICABLE rules -> knowledge ->
                 one inconclusive claim with Evidence/rule/knowledge refs
  ```

  Require affirmative-cause wording equivalent to:

  ```text
  A causal fault_type is emitted only for an affirmatively supported cause.
  Never use clipping or harmonic_distortion fault_type for not supported,
  ruled out, absent, or limitation statements.
  A rule FAIL does not create a causal fault without supporting Evidence.
  ```

  Explicitly reject the old global assertion `not clipping_only_finish`.
  Instead assert that a clipping-specific finish exists and no broad/combined
  example finishes while harmonic remains viable.

- [ ] **Step 4: Run RED**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/agent/test_phase4_3_1_prompt_v8_1.py tests/agent/test_phase4_3_prompt_v8.py tests/agent/test_real_llm_planner.py -q
  ```

  Expected: collection/assertion failures because v8.1 and the private v8
  planner do not exist and the public planner still binds v8.

- [ ] **Step 5: Implement one coherent v8.1 prompt**

  Add a complete `_S1_SYSTEM_PROMPT_V8_1` and `_S1_PROMPT_V8_1`; do not build
  it by string concatenation. Retain leakage, output schema, numerical-source,
  same-run-reference, rule, knowledge, retry, and no-fallback instructions.
  Replace the ambiguous v8 combined example with separately labeled
  clipping-specific and broad/combined examples. Include exact structured JSON
  examples for the behaviors in Step 3.

- [ ] **Step 6: Bind v8.1 publicly and v8 privately**

  In `planner.py`, import `_S1_PROMPT_V8_1`, make public constants and
  `RealLLMPlanner._prompt_spec` use it, and add:

  ```python
  class _Phase4V8RealLLMPlanner(RealLLMPlanner):
      _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V8
  ```

  Leave `_Phase4V4RealLLMPlanner` through `_Phase4V7RealLLMPlanner` unchanged.

- [ ] **Step 7: Freeze v8.1 bytes after semantic review**

  Run:

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -c "import hashlib; from signal_diag.agent.prompts import _S1_PROMPT_V8_1 as p; b=p.system_prompt.encode('utf-8'); print(len(b)); print(hashlib.sha256(b).hexdigest())"
  ```

  Copy the printed byte count and 64-character digest verbatim into T216. Do
  this only after spec review has stabilized prompt bytes.

- [ ] **Step 8: Run GREEN and historical regressions**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/agent/test_phase4_3_1_prompt_v8_1.py tests/agent/test_phase4_3_prompt_v8.py tests/agent/test_phase4_2_prompt_v7.py tests/agent/test_real_llm_planner.py -q
  ```

- [ ] **Step 9: Apply the seven-step review protocol and commit**

  Spec review must compare each example with §54.2–§54.4. Quality review must
  check contradiction-free wording, exact legacy hashes, and unchanged public
  signatures. After main-controller verification:

  ```powershell
  git add src/signal_diag/agent/prompts.py src/signal_diag/agent/planner.py tests/agent/test_phase4_3_1_prompt_v8_1.py tests/agent/test_phase4_3_prompt_v8.py tests/agent/test_real_llm_planner.py
  git commit -m "feat(agent): add Phase 4.3.1 planner v8.1 policy"
  ```

---

### Task 3: Add versioned invalid-Evidence scoring policy 2.0.0

**Files:**

- Modify: `src/signal_diag/evaluation/scoring.py`
- Create: `tests/evaluation/test_phase4_3_1_scoring.py`
- Retain unchanged: `src/signal_diag/evaluation/models.py`
- Retain unchanged: `src/signal_diag/evaluation/runner.py`
- Retain unchanged: `tests/evaluation/test_scoring.py`

**Interfaces:**

- Consumes: `BenchmarkConfig.sdk_versions`, `EvaluationCase`,
  `EvaluationTrace`, and current legacy `score_evaluation_trace`.
- Produces private constants `_SCORING_POLICY_KEY = "signal_diag.scoring"`,
  `_SCORING_POLICY_V2 = "2.0.0"`, and private policy selection from
  `trace.config.sdk_versions`.
- Public `score_evaluation_trace(case, trace) -> RunScore` remains exact legacy
  behavior for historical traces and keeps the same signature.

- [ ] **Step 1: Write legacy-compatibility RED tests**

  Import `inspect.signature` and assert the public signature is still exactly
  `(case, trace)`. Build the existing legal clipping and noise traces and assert
  public scores and failure codes equal the pre-change literals. Bind traces to
  configs with no `signal_diag.scoring` key, including `sdk_versions={}` and
  `sdk_versions={"openai": "1.0.0"}`, and require the public function to
  reproduce legacy results.

- [ ] **Step 2: Write scoring-2.0.0 RED tests**

  Construct one noise trace in strict chronological order:

  ```text
  Planner call analyze_harmonic_distortion
  Observation status=invalid carrying Evidence validity=not_applicable
  Planner evaluate_rules over that Evidence ID
  RuleEvaluation judgment=not_applicable citing the same Evidence ID
  Planner retrieve_knowledge
  Knowledge retrieval
  Planner finish inconclusive with same-run Evidence/rule/knowledge refs
  ```

  With `sdk_versions={"signal_diag.scoring": "2.0.0"}`, assert:

  ```python
  assert score.correct_rule_actions == 1
  assert score.rule_action_opportunities == 1
  assert "premature_rule" not in score.failure_codes
  assert "inappropriate_replan" not in score.failure_codes
  assert "omitted_rule" not in score.failure_codes
  ```

  Also assert a rule before any Evidence remains `premature_rule`, repeating the
  same rule-Evidence state remains `redundant_rule`, and an unknown scoring
  version raises `ValueError` rather than falling back. Build the equivalent
  fixed-pipeline invalid trace and require the same rule-eligibility result so
  Agent and baseline comparisons use one scoring policy.

- [ ] **Step 3: Run RED**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/evaluation/test_phase4_3_1_scoring.py -q
  ```

- [ ] **Step 4: Implement private policy dispatch**

  Refactor without changing public output:

  ```python
  _SCORING_POLICY_KEY = "signal_diag.scoring"
  _SCORING_POLICY_V2 = "2.0.0"

  def score_evaluation_trace(
      case: EvaluationCase,
      trace: EvaluationTrace,
  ) -> RunScore:
      policy = trace.config.sdk_versions.get(_SCORING_POLICY_KEY)
      if policy is None:
          include_invalid = False
      elif policy == _SCORING_POLICY_V2:
          include_invalid = True
      else:
          raise ValueError(f"unsupported scoring policy: {policy}")
      return _score_evaluation_trace_with_policy(
          case,
          trace,
          include_invalid_rule_evidence=include_invalid,
      )
  ```

  Pass `include_invalid_rule_evidence` into `_score_path`. Maintain two
  separate concepts: success Evidence continues to update causal
  satisfied/contradicted/sufficiency state; rule-eligible Evidence IDs include
  invalid/not-applicable Evidence only for policy 2.0.0. Feed the latter list to
  `_note_rule_decision` and omitted-rule logic. Pass the same flag into
  `_score_baseline_path` and apply the identical rule-eligibility distinction
  there. Do not let invalid Evidence satisfy a causal Evidence set in either
  execution path.

- [ ] **Step 5: Confirm runner and offline replay share the same dispatch**

  Do not modify `runner.py`: Agent and baseline paths already call the public
  scorer with traces whose `config` is the benchmark config. Assert both direct
  offline scoring and runner-produced scoring select policy 2.0.0 from the
  trace, while historical traces remain legacy.

- [ ] **Step 6: Run GREEN and all scoring regressions**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/evaluation/test_phase4_3_1_scoring.py tests/evaluation/test_scoring.py tests/evaluation/test_acceptance.py tests/evaluation/test_runner.py -q
  ```

- [ ] **Step 7: Apply the seven-step review protocol and commit**

  Spec review must trace the invalid Evidence ID into RuleEngine eligibility
  without causal sufficiency. Quality review must verify no global/mutable
  policy state and exact public-signature compatibility. Then:

  ```powershell
  git add src/signal_diag/evaluation/scoring.py tests/evaluation/test_phase4_3_1_scoring.py
  git commit -m "fix(evaluation): version invalid-evidence rule scoring"
  ```

---

### Task 4: Prove v8.1 behavior through the real product boundary

**Files:**

- Create: `tests/agent/test_phase4_3_1_v8_1_runtime.py`
- Modify only if deterministic tests expose a §54-permitted prompt defect:
  `src/signal_diag/agent/prompts.py`, `src/signal_diag/agent/planner.py`,
  `tests/agent/test_phase4_3_1_prompt_v8_1.py`
- Retain unchanged: `src/signal_diag/agent/runtime.py`

**Interfaces:**

- Consumes: active v8.1 `RealLLMPlanner`, fake OpenAI-compatible transport,
  real `DistortionDiagnosisRuntime`, `SignalToolService`, `RuleEngine`,
  `YamlRuleProfileLoader`, `KnowledgeIndex`, and dataset-1.2 materialization.
- Produces deterministic T221 paths and value-level no-leakage evidence without
  replacing the product Planner.

- [ ] **Step 1: Write outbound non-leakage tests**

  Capture the actual `messages` passed by `RealLLMPlanner`. Recursively reject
  keys and values for case ID, category, split, generator parameters/truth,
  causal truth, knowledge policy, acceptable Tools, sufficient sets, conditions,
  targets, scoring policy, dataset identity, samples, waveform, FFT frequencies,
  and magnitudes. Require opaque `sig_eval_` plus 24 lowercase hex characters.
  Changing only that opaque ID must not change the fake transport route.

- [ ] **Step 2: Implement an observation-driven fake transport in the test**

  The fake reads only the serialized `planner_context` and visible
  `user_request`. It returns one valid JSON `AgentDecision` per call. It may
  branch on visible symptom text and compact same-run Evidence/rule/knowledge
  fields, but never imports or reads `EvaluationCase`, manifest truth, case ID,
  category, split, acceptable Tools, or target bands.

- [ ] **Step 3: Write clipping-specific and broad odd-order tests**

  Use real dataset-1.2 clipping materialization and real DSP twice:

  1. clipping-specific visible request: initial hypotheses `['clipping']`,
     `detect_clipping -> evaluate_rules -> finish`; assert no harmonic Tool and
     exactly one clipping causal claim;
  2. broad request over strong symmetric clipping: clipping then legitimately
     harmonic analysis, odd orders 3/5 with high THD, rules, finish; assert the
     harmonic hypothesis is ruled out and the final causal set is exactly
     `{'clipping'}`.

- [ ] **Step 4: Write combined and invalid/noise tests**

  Combined uses one v1.2 signal containing order-2 harmonic injection plus
  symmetric clipping. Require both Tools, separate Evidence, order-2 support,
  one rule batch, and exactly two causal claims. Noise requires invalid harmonic
  Evidence, NOT_APPLICABLE rule refs, relevant knowledge, one inconclusive
  claim, and a non-empty limitation. Resolve every final reference within the
  same `AgentRunResult`.

- [ ] **Step 5: Run RED**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/agent/test_phase4_3_1_v8_1_runtime.py -q
  ```

  Runtime changes are prohibited as a way to make this GREEN.

- [ ] **Step 6: Make only prompt/planner corrections and re-freeze hash**

  If the fake transport exposes an ambiguity, correct only v8.1 prompt wording
  or examples, rerun Task 2 semantic tests, and replace the frozen v8.1 hash and
  byte literal with the newly computed exact values. Do not alter v8.

- [ ] **Step 7: Run GREEN and all Agent regressions**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/agent/test_phase4_3_1_v8_1_runtime.py tests/agent/test_phase4_3_1_prompt_v8_1.py -q
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/agent -q
  ```

- [ ] **Step 8: Apply the seven-step review protocol and commit**

  Spec review must confirm fake transport decisions use only product-visible
  context. Quality review must inspect same-run references and real dependency
  use. Then stage only files actually changed:

  ```powershell
  git add src/signal_diag/agent/prompts.py src/signal_diag/agent/planner.py tests/agent/test_phase4_3_1_prompt_v8_1.py tests/agent/test_phase4_3_1_v8_1_runtime.py
  git commit -m "test(agent): prove Phase 4.3.1 product behavior"
  ```

---

### Task 5: Add the private v8.1 benchmark identity and scorer provenance

**Files:**

- Modify: `src/signal_diag/evaluation/runner.py`
- Create: `tests/evaluation/test_phase4_3_1_v8_1_runner.py`
- Retain unchanged: `src/signal_diag/evaluation/models.py`
- Retain unchanged:
  `src/signal_diag/evaluation/manifests/s1_distortion_v1_2.yaml`

**Interfaces:**

- Consumes: active v8.1 prompt, private `_Phase4V8RealLLMPlanner`, v1.2 opaque
  signal-ID factory, scoring-policy constants, real split executor, and report
  writer.
- Produces private v8.1 hash/config/planner/preflight/development/official
  runner functions. Campaign registration is deferred to Task 6.

- [ ] **Step 1: Write T216 runner-compatibility RED tests**

  Assert all historical builders keep exact private planners: v4–v7 remain as
  before, `_build_phase4_3_v8_planner` now constructs
  `_Phase4V8RealLLMPlanner`, and its config/hash/sdk_versions remain identical
  to committed v8 provenance.

- [ ] **Step 2: Write v8.1 identity RED tests**

  Require the private config builder to return exactly:

  ```python
  assert config.dataset_id == "s1-distortion-synthetic"
  assert config.dataset_version == "1.2.0"
  assert config.rule_profile_id == "profile_s1_distortion"
  assert config.rule_profile_version == "1.0.0-demo"
  assert config.provider == "deepseek"
  assert config.model == "deepseek-v4-flash"
  assert config.prompt_version == "v0.2-s1-planner-8.1"
  assert config.sdk_versions == {"signal_diag.scoring": "2.0.0"}
  assert config.repetitions == 5
  assert config.max_concurrency == 1
  ```

  Require development/official configs to share a fingerprint after excluding
  benchmark ID and start time. Require 40 development and 80 held-out slots.

- [ ] **Step 3: Write v8.1 preflight RED tests**

  Parameterize wrong prompt bytes/hash/version, dataset/profile,
  provider/model, repetitions/concurrency, missing/unknown/additional/mismatched
  scoring-policy map, and manifest mismatch. Every error is
  `invalid_configuration` before environment credential lookup or SDK/client
  construction.

- [ ] **Step 4: Run RED**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/evaluation/test_phase4_3_1_v8_1_runner.py -q
  ```

- [ ] **Step 5: Implement private v8.1 identity functions**

  Add exact constants:

  ```python
  _PHASE4_3_1_PROMPT_VERSION = "v0.2-s1-planner-8.1"
  _PHASE4_3_1_SCORING_VERSIONS = {"signal_diag.scoring": "2.0.0"}
  _PHASE4_3_1_DEV_BENCHMARK_ID = "bench_phase4_3_1_dev_v8_1_v12_gate5"
  _PHASE4_3_1_OFFICIAL_BENCHMARK_ID = "bench_official_s1_v12_planner8_1_gate5"
  _PHASE4_3_1_DEV_BUNDLE = Path("docs/evaluations/phase4_3_1/development") / _PHASE4_3_1_DEV_BENCHMARK_ID
  ```

  Implement `_phase4_3_1_v8_1_prompt_sha256`,
  `_phase4_3_1_v8_1_benchmark_config`,
  `_build_phase4_3_1_v8_1_planner`, `_preflight_phase4_3_1_v8_1`, and direct
  development/official runners. Reuse the v1.2 manifest, opaque ID factory,
  existing dependencies, and `_run_real_benchmark_for_split`. V8 historical
  runner must explicitly use the private v8 planner.

- [ ] **Step 6: Run GREEN and historical runner regressions**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/evaluation/test_phase4_3_1_v8_1_runner.py tests/evaluation/test_phase4_3_v8_runner.py tests/evaluation/test_phase4_2_v7_runner.py -q
  ```

- [ ] **Step 7: Apply the seven-step review protocol and commit**

  Spec review must verify exact identity and scorer provenance. Quality review
  must reject duplicated product logic and environment-dependent config
  fingerprints. Then:

  ```powershell
  git add src/signal_diag/evaluation/runner.py tests/evaluation/test_phase4_3_1_v8_1_runner.py
  git commit -m "feat(evaluation): add Phase 4.3.1 v8.1 runner identity"
  ```

---

### Task 6: Register gate5 campaigns, strict official gate, and CLI routing

**Files:**

- Modify: `src/signal_diag/evaluation/runner.py`
- Modify: `src/signal_diag/evaluation/__main__.py`
- Modify: `tests/evaluation/test_phase4_3_1_v8_1_runner.py`

**Interfaces:**

- Consumes: Task 5 private config/runners and the existing campaign dataclass.
- Produces `_PHASE4_3_1_V8_1_CAMPAIGNS`,
  `_run_phase4_3_1_v8_1_campaign`, strict development-bundle gate, and additive
  `run-real --campaign` choices.

- [ ] **Step 1: Write T222 registry and CLI RED tests**

  Require one registry to provide exactly:

  ```python
  {
      "phase4.3.1-v8.1-development":
          "bench_phase4_3_1_dev_v8_1_v12_gate5",
      "phase4.3.1-v8.1-official":
          "bench_official_s1_v12_planner8_1_gate5",
  }
  ```

  Parser choices retain every historical route and append these two; default
  remains `phase4`. `__main__.py` imports the registry/dispatcher instead of
  duplicating IDs. Non-canonical benchmark IDs and conflicting manifests
  produce `invalid_configuration` without rewriting inputs.

- [ ] **Step 2: Write identity-complete official-gate RED tests**

  Parameterize missing/unreadable/invalid `metrics.json`, missing/unreadable/
  invalid `benchmark_manifest.json`, status other than
  `completed/meets_target`, missing/mismatched identity fields including the
  complete `sdk_versions` map, missing/invalid/mismatched checksums, changed
  prompt hash, and existing official destination. Assert rejection occurs
  before `DEEPSEEK_API_KEY` lookup, SDK import, client construction, or
  held-out slot scheduling.

- [ ] **Step 3: Run RED**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/evaluation/test_phase4_3_1_v8_1_runner.py -q
  ```

- [ ] **Step 4: Implement strict gate and campaign registry**

  Define a v8.1 gate identity-field tuple that extends the existing complete
  fields with `sdk_versions`. `_require_phase4_3_1_v8_1_development_gate`
  must call the existing identity-complete loader and checksum validator. The
  official runner must call this gate before wrapping provider preflight.
  Register both routes and dispatch them through one campaign function.

- [ ] **Step 5: Add CLI routing**

  Import the v8.1 registry/dispatcher in `__main__.py`, append its keys to
  choices, and dispatch the selected route before historical v8/v7 branches.
  Print only `benchmark_status`; never print credentials or transport payloads.

- [ ] **Step 6: Run GREEN and all campaign regressions**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/evaluation/test_phase4_3_1_v8_1_runner.py tests/evaluation/test_phase4_3_v8_runner.py tests/evaluation/test_phase4_2_v7_runner.py tests/evaluation/test_phase4_1_v6_runner.py tests/evaluation/test_phase4_1_runner.py -q
  ```

- [ ] **Step 7: Apply the seven-step review protocol and commit**

  Spec review must trace every official rejection before secrets/held-out.
  Quality review must verify single-source identities and no historical branch
  change. Then:

  ```powershell
  git add src/signal_diag/evaluation/runner.py src/signal_diag/evaluation/__main__.py tests/evaluation/test_phase4_3_1_v8_1_runner.py
  git commit -m "feat(evaluation): add Phase 4.3.1 gate5 campaigns"
  ```

---

### Task 7: Enforce T223 and record deterministic readiness

**Files:**

- Modify: `tests/test_architecture_boundaries.py`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: this plan to record exact deterministic evidence only

**Interfaces:**

- Consumes: T216–T222 implementation and all T001–T215 regressions.
- Produces the cumulative deterministic gate and honest
  `deterministic ready / development not run` status.

- [ ] **Step 1: Write T223 architecture guards**

  Require T216–T223 names. From baseline `1b94194`, allow only `AGENTS.md`,
  `docs/`, `src/signal_diag/agent/`, `src/signal_diag/evaluation/`, and
  `tests/`. Explicitly freeze `agent/runtime.py`, evaluation models/dataset/
  manifests, signal/DSP/Tools/Rules/Knowledge, and app. Permit
  `evaluation/scoring.py` only for the §54.4 versioned correction.

  AST guards must prove Runtime constructs no decision/action, branches on no
  prompt/campaign/case/split/target identity, and contains no universal S1 Tool
  list. Product v8.1 builders must construct `RealLLMPlanner`, not
  ScriptedPlanner or a context-bound scripted planner. TargetBands defaults and
  public model fields/signatures remain unchanged.

- [ ] **Step 2: Run focused RED/GREEN**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_architecture_boundaries.py -q
  ```

- [ ] **Step 3: Run the complete deterministic gate**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q -rxXs -p no:cacheprovider --basetemp .pytest_cache/phase4-3-1-deterministic
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m ruff check --no-cache src tests scripts
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m mypy --no-incremental src
  git diff --check 1b94194..HEAD
  ```

  Required: all tests pass, zero required skip/xfail, Ruff/mypy/diff-check
  clean. Record exact counts and outputs. This proves deterministic readiness,
  not live-model acceptance.

- [ ] **Step 4: Update status docs without claiming a model pass**

  Change `AGENTS.md`, `docs/README.md`, and this plan to say T001–T223 are
  green at the eventual Task 7 commit, while v8.1 development, official, Phase
  4.3.1 acceptance, and Phase 5 remain pending/gated. Do not edit frozen §54,
  T216–T223, D025, or OQ-009.

- [ ] **Step 5: Apply the seven-step review protocol and commit**

  Spec review maps every T216–T223 ID to a concrete test. Quality review
  inspects the full baseline diff and frozen paths. Then:

  ```powershell
  git add tests/test_architecture_boundaries.py AGENTS.md docs/README.md docs/superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md
  git commit -m "test(evaluation): enforce Phase 4.3.1 deterministic gate"
  ```

---

### Task 8: Execute the one-shot v8.1 development campaign

**Files:**

- Create once:
  `docs/evaluations/phase4_3_1/development/bench_phase4_3_1_dev_v8_1_v12_gate5/`
- Modify after the immutable result: `AGENTS.md`, `docs/README.md`, and this
  plan
- Do not modify source, tests, prompt, scorer, dataset, or targets after the run

**Interfaces:**

- Consumes: committed T001–T223 green tree, exact v8.1/config/scoring identity,
  dataset-1.2 development split, and `DEEPSEEK_API_KEY`.
- Produces exactly one immutable 40-Agent-slot development bundle.

- [ ] **Step 1: Re-establish legal preconditions**

  Freshly rerun all Task 7 gates. Then:

  ```powershell
  Test-Path 'docs/evaluations/phase4_3_1/development/bench_phase4_3_1_dev_v8_1_v12_gate5'
  ```

  Expected: `False`. If true, stop; do not overwrite, delete, rename, or rerun.
  Check credential presence without printing its value. Missing credentials
  pauses only this live Task.

- [ ] **Step 2: Run canonical development exactly once**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m signal_diag.evaluation run-real --campaign phase4.3.1-v8.1-development --benchmark-id bench_phase4_3_1_dev_v8_1_v12_gate5 --output-dir docs/evaluations/phase4_3_1/development
  ```

  Do not retry a stochastic metric miss.

- [ ] **Step 3: Validate the entire bundle**

  Require exactly the existing six-file contract:
  `benchmark_manifest.json`, `metrics.json`, `runs.jsonl`,
  `case_summary.csv`, `report.md`, and `checksums.sha256`. Verify all checksums,
  exact config/scoring identity, 40 unique scoreable Agent slots (8 x 5), no
  held-out slots, no secrets/raw arrays, and every TargetBands metric.

- [ ] **Step 4: Apply the terminal development gate**

  If the result is not exactly `completed/meets_target`, preserve and commit
  it, document every missed band, skip Task 9, do not create v8.2/v9, and go to
  Task 10. Only an exact pass permits Task 9.

- [ ] **Step 5: Review and commit the immutable result**

  Independent review checks identity, slots, checksums, metrics, and absence of
  held-out or secrets. Then:

  ```powershell
  git add AGENTS.md docs/README.md docs/superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md docs/evaluations/phase4_3_1/development/bench_phase4_3_1_dev_v8_1_v12_gate5
  git commit -m "eval(phase4.3.1): record v8.1 development gate5"
  ```

---

### Task 9: Conditionally execute the one-shot official held-out campaign

**Files:**

- Create once, only after legal development pass:
  `docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/`
- Modify after the immutable result: `AGENTS.md`, `docs/README.md`, and this
  plan

**Interfaces:**

- Consumes: committed checksum-valid development
  `completed/meets_target` bundle and byte-identical v8.1 candidate.
- Produces exactly one immutable 80-Agent-slot official bundle.

- [ ] **Step 1: Prove eligibility before credentials or held-out scheduling**

  Rerun T222 and Task 7 gates. Verify the development bundle is unchanged and:

  ```powershell
  Test-Path 'docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5'
  ```

  Expected: `False`. Any identity/checksum/status mismatch or existing
  destination stops as `invalid_configuration`.

- [ ] **Step 2: Run official exactly once**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m signal_diag.evaluation run-real --campaign phase4.3.1-v8.1-official --benchmark-id bench_official_s1_v12_planner8_1_gate5 --output-dir docs/evaluations/phase4_3_1/official
  ```

  Never tune from or rerun held-out results.

- [ ] **Step 3: Validate and retain the official outcome**

  Verify six files, checksums, exact identity, 80 unique scoreable Agent slots,
  every target, and no secrets/raw arrays. Phase 4.3.1 is accepted only for
  exact `completed/meets_target`; every other outcome remains immutable and
  keeps Phase 5 gated.

- [ ] **Step 4: Review and commit**

  Review must confirm there was no source/prompt/scorer/target/dataset change
  between development and official. Then:

  ```powershell
  git add AGENTS.md docs/README.md docs/superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5
  git commit -m "eval(phase4.3.1): record v8.1 official gate5"
  ```

---

### Task 10: Record terminal status and prepare independent handoff

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: this plan's status/checklist
- Do not change frozen contracts unless a genuine contradiction is first
  recorded in `docs/OPEN_QUESTIONS.md` and approved

**Interfaces:**

- Consumes: deterministic gate and only the legally executed campaigns.
- Produces an honest final status and independent-verification handoff; no
  merge, push, or automatic Phase 5 authorization.

- [ ] **Step 1: Record exactly one terminal state**

  Use one of:

  ```text
  development completed/below_target; official not run; Phase 4.3.1 not accepted
  development completed/meets_target; official completed/below_target; not accepted
  development completed/meets_target; official completed/meets_target; accepted
  infrastructure/configuration incomplete; preserve evidence and report blocker
  ```

  Never conflate deterministic T223, CLI `harness_status`, benchmark status,
  or target status.

- [ ] **Step 2: Run fresh final verification**

  ```powershell
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q -rxXs -p no:cacheprovider --basetemp .pytest_cache/phase4-3-1-final
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m ruff check --no-cache src tests scripts
  & 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m mypy --no-incremental src
  git diff --check 1b94194..HEAD
  git status --short --branch
  git log --oneline c20a744..HEAD
  ```

  Report exact counts, zero/nonzero skip/xfail, all warnings, and the unchanged
  untracked `build/` directory.

- [ ] **Step 3: Map acceptance IDs to evidence**

  Report at minimum:

  ```text
  T216–T219  tests/agent/test_phase4_3_1_prompt_v8_1.py
  T220       tests/evaluation/test_phase4_3_1_scoring.py
  T221       tests/agent/test_phase4_3_1_v8_1_runtime.py
  T222       tests/evaluation/test_phase4_3_1_v8_1_runner.py
  T223       tests/test_architecture_boundaries.py plus cumulative commands
  ```

- [ ] **Step 4: Apply final independent reviews and commit status docs**

  Review the complete `1b94194..HEAD` diff and all generated bundles. Close
  every Critical/Important finding before committing:

  ```powershell
  git add AGENTS.md docs/README.md docs/superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md
  git commit -m "docs: record Phase 4.3.1 terminal status"
  ```

- [ ] **Step 5: Deliver the handoff without integration**

  Provide branch, HEAD, per-Task commits, `git status`, focused RED/GREEN
  commands, final pytest/Ruff/mypy/diff-check output, T216–T223 mapping,
  campaign/bundle identities, exact metrics, warnings, unsupported cases, and
  contract concerns. Do not push, merge, delete the worktree, or start Phase 5.
