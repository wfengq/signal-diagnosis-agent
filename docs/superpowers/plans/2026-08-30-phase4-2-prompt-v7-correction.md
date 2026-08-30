# Phase 4.2 Evaluation Integrity and Planner v7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Every code task also uses
> `superpowers:test-driven-development`; completion claims require
> `superpowers:verification-before-completion`.

**Goal:** Produce an integrity-corrected v1.2 S1 evaluation campaign and one
coherent real-model planner v7 candidate without changing the accepted Agent
runtime or consuming held-out data prematurely.

**Architecture:** Preserve all v4/v5/v6 identities and bundles. Add a fresh
v1.2 manifest above the existing deterministic DSP stack, materialize only v1.2
Agent cases with opaque signal IDs, make combined causes observable through
even-order harmonic Evidence, and bind a coherent v7 prompt to additive Phase
4.2 campaign routes. The Runtime remains decision-driven and never forces a
Tool, rule, or knowledge action.

**Tech Stack:** Python 3.12, Pydantic v2, NumPy/SciPy DSP already in the
repository, PyYAML, pytest, Ruff, mypy, DeepSeek OpenAI-compatible transport.

**Spec:**
`docs/superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md`

**Implementation baseline:** `aefccba` on `phase4-evaluation-design`

**Status:** Revised design approved on 2026-08-30. Task 1 documentation freeze
is authorized; Tasks 2–10, all code changes, and all real-model/held-out runs
remain unauthorized.

## Global Constraints

- Do not implement until OQ-007, CONTRACTS §52, TEST_PLAN §25/T201-T208, and
  D023 are explicitly approved and frozen.
- Keep v4/v5/v6 prompt bytes, hashes, private planners, routes, configurations,
  and committed bundles unchanged.
- Keep both v1.1.0 development bundles unchanged and its held-out split
  unexecuted.
- Do not run any v1.2 real-model slot until the exact manifest, prompt bytes,
  deterministic tests, and cumulative static gates are committed.
- Do not change public Planner, Runtime, DSP, Tool, Rule, Knowledge, scoring,
  target, or reporting models.
- Do not add a Tool, force a Runtime action, lower targets, change the provider
  or model, push, merge, or start Phase 5.
- RealLLMPlanner is the product path. Fake transports and ScriptedPlanner are
  deterministic test doubles only.
- Raw waveform, full FFT, generator truth, case truth, acceptable Tools,
  sufficient Evidence sets, split, and scoring policy never enter outbound LLM
  messages.
- Preserve the untracked `build/` directory and unrelated user changes.

---

### Task 1: Freeze the revised additive contract after approval

**Files:**

- Modify: `docs/CONTRACTS_V0_2.md`
- Modify: `docs/TEST_PLAN_V0_2.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/OPEN_QUESTIONS.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`
- Retain: `docs/superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md`
- Retain: `docs/superpowers/plans/2026-08-30-phase4-2-prompt-v7-correction.md`

**Interfaces:**

- Consumes: accepted §§41-§51, T001-T200, D017-D022.
- Produces: frozen §52, T201-T208, D023, and resolved OQ-007.

- [x] **Step 1: Confirm the exact approval gate**

  Require an explicit user decision approving OQ-007, §52, T201-T208, and D023.
  Stop if any item is not approved.

- [x] **Step 2: Add §52 without rewriting historical sections**

  Freeze dataset `1.2.0`, opaque signal identity, Planner-visible first-Tool
  fairness, even-order combined identifiability, prompt v7, canonical campaigns,
  strict provenance preflight, unchanged targets, and held-out protocol exactly
  as specified by the design.

- [x] **Step 3: Add TEST_PLAN §25**

  Add T201-T208 with the exact meanings from the design. State explicitly that
  development is tuning evidence and official held-out is the generalization
  gate.

- [x] **Step 4: Record D023 and resolve OQ-007**

  D023 must say that Phase 4.2 is an evaluation-integrity correction, not a
  prompt-only retry. OQ-007 records the approval date and exact authority.

- [x] **Step 5: Check and commit the documentation gate**

  Run:

  ```powershell
  git diff --check
  rg -n "TBD|TODO|prompt-only v7|v1.1.0 development split" `
    AGENTS.md docs/README.md docs/CONTRACTS_V0_2.md `
    docs/TEST_PLAN_V0_2.md docs/DECISIONS.md docs/OPEN_QUESTIONS.md `
    docs/superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md `
    docs/superpowers/plans/2026-08-30-phase4-2-prompt-v7-correction.md
  ```

  Expected: diff-check exit 0; no stale statement authorizes v7 on v1.1.0.

  Commit:

  ```powershell
  git add AGENTS.md docs
  git commit -m "docs: freeze Phase 4.2 evaluation integrity gate"
  ```

---

### Task 2: Add and validate dataset 1.2.0

**Files:**

- Create: `src/signal_diag/evaluation/manifests/s1_distortion_v1_2.yaml`
- Modify: `src/signal_diag/evaluation/dataset.py`
- Create: `tests/evaluation/test_phase4_2_dataset.py`

**Interfaces:**

- Consumes: `DatasetManifest`, existing synthetic generators,
  `SignalToolService`, `validate_dataset`.
- Produces: package manifest `s1-distortion-synthetic` `1.2.0` and valid
  single-signal combined fixtures.

- [ ] **Step 1: Write T203 allocation/freshness tests**

  Tests load v1.0, v1.1, and the expected v1.2 path, then assert:

  ```python
  assert manifest.version == "1.2.0"
  assert counts["development"] == {
      "clean": 2, "clipping": 2, "harmonic": 2,
      "combined": 1, "invalid_noise": 1,
  }
  assert counts["held_out"] == {
      "clean": 3, "clipping": 4, "harmonic": 4,
      "combined": 3, "invalid_noise": 2,
  }
  assert not v12_case_ids & (v10_case_ids | v11_case_ids)
  assert not v12_parameter_tuples & (v10_parameter_tuples | v11_parameter_tuples)
  ```

  Also assert development/held-out disjointness for IDs, complete signal
  parameter tuples, seeds, and complete request strings.

- [ ] **Step 2: Write T203 request-fairness tests**

  Build each case's initial visible key from `user_request` plus generated
  `SignalMeta.model_dump(exclude={"signal_id"})`. Cases with equal keys must
  have equal `acceptable_first_tools`. Assert request strings contain none of:

  ```python
  {
      "detect_clipping", "analyze_harmonic_distortion", "estimate_fundamental",
      "causal_faults", "acceptable_first_tools", "development", "held_out",
      "clipping_strong", "invalid_noise", "combined_01",
  }
  ```

  Assert invalid/noise cases accept both `estimate_fundamental` and
  `analyze_harmonic_distortion` and carry an unstable-pitch/non-periodic symptom
  cue without naming the answer.

- [ ] **Step 3: Write T204 combined-identifiability tests**

  For every combined case assert the generator injects order 2, the observable
  conditions include `harmonic_order_2_relative_amplitude` supporting
  `harmonic_distortion`, and a sufficient set includes clipping, harmonic
  validity, THD, and that component. Use real `validate_dataset` and require
  `report.valid is True`.

  Add a focused v1.2 validator regression where the valid matched clipping-only
  control omits order 2 after Tool filtering; this must be treated as zero.
  A control with invalid harmonic analysis must still fail identifiability.
  Assert v1.0/v1.1 and arbitrary non-v1.2 manifests retain their previous
  missing-component behavior.

- [ ] **Step 4: Run RED**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_2_dataset.py -q
  ```

  Expected: failure because the v1.2 manifest and absent-control semantics do
  not exist.

- [ ] **Step 5: Implement the minimal validator correction**

  Keep `_materialize_case` behavior unchanged in this task. In
  `_identifiability_issues`, add an explicit private flag supplied by
  `validate_dataset` only for dataset version `1.2.0`. Under that flag, treat an
  absent configured order-2 component as `0.0` only when the matched-control
  `analyze_harmonic_distortion` result is valid. Do not change historical
  semantics and do not treat invalid results, missing calls, or arbitrary
  metrics as zero.

- [ ] **Step 6: Create and freeze the exact v1.2 manifest**

  Use fresh case IDs, parameters, seeds, and requests satisfying the spec.
  Combined cases use symmetric clipping plus injected order-2 harmonics. Do not
  copy v1.1 parameter tuples or request assignments. Run real deterministic
  validation while calibrating fixtures; never call an LLM.

- [ ] **Step 7: Run GREEN and cumulative dataset tests**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_2_dataset.py -q
  python -m pytest tests/evaluation/test_dataset.py `
    tests/evaluation/test_phase4_1_dataset.py `
    tests/evaluation/test_phase4_2_dataset.py -q
  ```

  Expected: all pass with no skip/xfail.

- [ ] **Step 8: Commit**

  ```powershell
  git add src/signal_diag/evaluation/dataset.py `
    src/signal_diag/evaluation/manifests/s1_distortion_v1_2.yaml `
    tests/evaluation/test_phase4_2_dataset.py
  git commit -m "feat(evaluation): add integrity-corrected S1 dataset v1.2"
  ```

---

### Task 3: Remove semantic signal identity from v1.2 PlannerContext

**Files:**

- Modify: `src/signal_diag/evaluation/dataset.py`
- Modify: `src/signal_diag/evaluation/runner.py`
- Create: `tests/evaluation/test_phase4_2_identity.py`

**Interfaces:**

- Consumes: private `_materialize_case`, `BenchmarkConfig`, real Runtime and
  RecordingPlanner.
- Produces:

  ```python
  def _opaque_evaluation_signal_id(
      dataset_id: str, dataset_version: str, case_id: str
  ) -> str: ...

  def _materialize_case(
      case: EvaluationCase,
      repository: SignalRepository,
      *,
      signal_id: str | None = None,
  ) -> SignalRecord: ...
  ```

  Historical callers omit `signal_id` and retain legacy behavior.

- [ ] **Step 1: Write T202 opaque-ID unit tests**

  Assert determinism, 24 lowercase hexadecimal characters, uniqueness, and the
  exact SHA-256 algorithm. Assert no output contains any case ID token, split,
  category, generator, `fault`, `noise`, `clip`, `harmonic`, `clean`, or
  `combined`.

- [ ] **Step 2: Write T202 outbound-message test**

  Call the private real-runner slot path with a capture planner builder and the
  opaque `signal_id_factory`; do not depend on the not-yet-created v7 campaign.
  Parse the captured PlannerContext serialization and assert that its
  `signal_id` is opaque and the complete payload contains no manifest case ID,
  category, split, generator name, causal truth, acceptable Tools, sufficient
  sets, or scoring target. The trace outside PlannerContext may retain
  `case_id` for scoring.

- [ ] **Step 3: Run RED**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_2_identity.py -q
  ```

  Expected: failure because semantic IDs still reach PlannerContext.

- [ ] **Step 4: Implement private identity injection**

  Implement:

  ```python
  def _opaque_evaluation_signal_id(
      dataset_id: str, dataset_version: str, case_id: str
  ) -> str:
      raw = f"{dataset_id}\0{dataset_version}\0{case_id}".encode("utf-8")
      return f"sig_eval_{hashlib.sha256(raw).hexdigest()[:24]}"
  ```

  Add the keyword-only `_materialize_case` override. Thread a private
  `signal_id_factory` callback through `_execute_agent_slot` and
  `_run_real_benchmark_for_split`; all existing callers use the default. The
  Phase 4.2 v7 caller added later supplies the opaque factory.

- [ ] **Step 5: Run GREEN and legacy regression**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_2_identity.py -q
  python -m pytest tests/evaluation/test_dataset.py `
    tests/evaluation/test_runner.py `
    tests/evaluation/test_phase4_1_v6_runner.py -q
  ```

  Expected: all pass; legacy materialized IDs and bundles are unchanged.

- [ ] **Step 6: Commit**

  ```powershell
  git add src/signal_diag/evaluation/dataset.py `
    src/signal_diag/evaluation/runner.py `
    tests/evaluation/test_phase4_2_identity.py
  git commit -m "fix(evaluation): hide case semantics from planner signal IDs"
  ```

---

### Task 4: Add coherent planner v7 and preserve v6

**Files:**

- Modify: `src/signal_diag/agent/prompts.py`
- Modify: `src/signal_diag/agent/planner.py`
- Create: `tests/agent/test_phase4_2_prompt_v7.py`

**Interfaces:**

- Consumes: `_PlannerPromptSpec`, RealLLMPlanner transport and validation.
- Produces: `_S1_PROMPT_V7`, active `PROMPT_VERSION`, and private
  `_Phase4V6RealLLMPlanner`.

- [ ] **Step 1: Write T201 legacy and v7 identity tests**

  Copy the already-recorded exact v4/v5/v6 versions, hashes, and byte lengths
  into regression assertions. Assert v7 is one standalone prompt,
  `RealLLMPlanner._prompt_spec is _S1_PROMPT_V7`, and
  `_Phase4V6RealLLMPlanner._prompt_spec is _S1_PROMPT_V6`.

- [ ] **Step 2: Write T205 semantic tests**

  Assert the prompt explicitly covers opaque-ID non-use, symptom-driven first
  choice, inconclusive claim purity, odd clipping-induced harmonics,
  reportable even-order combined Evidence, arbitrary-WAV ambiguity, dual truth,
  same-run refs, no fixed pipeline, and no Runtime-forced action.

  Reject dataset IDs, case IDs, benchmark IDs, numeric combined thresholds,
  acceptable-first-Tool labels, and live-looking evidence/rule/knowledge IDs.

- [ ] **Step 3: Run RED**

  ```powershell
  python -m pytest tests/agent/test_phase4_2_prompt_v7.py -q
  ```

  Expected: failure because v7 and the v6 compatibility planner do not exist.

- [ ] **Step 4: Implement v7 as one coherent prompt**

  Do not append to v6. Keep JSON decision shapes and field names compatible with
  existing `AgentDecision`. Examples use only illustrative placeholder IDs.
  Make v7 active and add the private v6 compatibility planner.

- [ ] **Step 5: Run GREEN and all prompt regressions**

  ```powershell
  python -m pytest tests/agent/test_phase4_2_prompt_v7.py -q
  python -m pytest tests/agent/test_phase4_1_prompt.py `
    tests/agent/test_phase4_1_prompt_v6.py `
    tests/agent/test_real_llm_planner.py -q
  ```

  Expected: all pass and historical hashes remain exact.

- [ ] **Step 6: Commit**

  ```powershell
  git add src/signal_diag/agent/prompts.py src/signal_diag/agent/planner.py `
    tests/agent/test_phase4_2_prompt_v7.py
  git commit -m "feat(agent): add integrity-aware planner v7 prompt"
  ```

---

### Task 5: Prove v7 behavior through the real product boundary

**Files:**

- Create: `tests/agent/test_phase4_2_v7_runtime.py`

**Interfaces:**

- Consumes: active RealLLMPlanner, fake provider transport, real
  DistortionDiagnosisRuntime, Tools, RuleEngine, and KnowledgeIndex.
- Produces: deterministic T206 traces; no production implementation.

- [ ] **Step 1: Add invalid/noise alternative-route tests**

  Drive one fake response sequence through harmonic-invalid and one through
  unvoiced-fundamental Evidence. Each final result is `inconclusive`, contains a
  non-empty limitation, cites only appropriate invalid/not-applicable Evidence,
  cites used knowledge, and has no sibling `no_supported_fault` claim.

- [ ] **Step 2: Add clipping-only induced-harmonic test**

  Use a real symmetric clipped sine. The fake model may inspect harmonic
  Evidence, but its final fault set contains only `clipping`; odd harmonic
  components appear only in explanatory text/limitations and are not an
  independent fault claim.

- [ ] **Step 3: Add combined even-harmonic test**

  Use a real v1.2 combined fixture. Require clipping and harmonic claims with
  separate same-run Evidence, including the order-2 component for the harmonic
  claim. Rule refs resolve in the same run.

- [ ] **Step 4: Add boundary harmonic and no-leakage tests**

  Preserve the 5% dual-truth behavior and assert all outbound contexts omit raw
  waveform, full FFT, generator truth, case policy, and semantic signal IDs.

- [ ] **Step 5: Run focused and cumulative Agent tests**

  ```powershell
  python -m pytest tests/agent/test_phase4_2_v7_runtime.py -q
  python -m pytest tests/agent -q
  ```

  Expected: all pass. A RED failure is acceptable only when it demonstrates a
  missing v7 behavior; do not weaken existing v6 tests.

- [ ] **Step 6: Commit**

  ```powershell
  git add tests/agent/test_phase4_2_v7_runtime.py
  git commit -m "test(agent): enforce planner v7 product-boundary behavior"
  ```

---

### Task 6: Add canonical v7 campaigns and strict provenance preflight

**Files:**

- Modify: `src/signal_diag/evaluation/runner.py`
- Modify: `src/signal_diag/evaluation/__main__.py`
- Create: `tests/evaluation/test_phase4_2_v7_runner.py`

**Interfaces:**

- Consumes: v1.2 manifest, `_S1_PROMPT_V7`, active planner, opaque signal-ID
  factory, existing report writer.
- Produces: `phase4.2-v7-development`, `phase4.2-v7-official`, canonical configs,
  and a shared identity-complete development-gate validator.

- [ ] **Step 1: Write T207 config and CLI RED tests**

  Assert exact provider/model/profile, dataset `1.2.0`, prompt v7/hash,
  repetitions 5, concurrency 1, and canonical IDs:

  ```text
  bench_phase4_2_dev_v7_v12_gate3
  bench_official_s1_v12_planner7_gate3
  ```

  Assert both acceptance campaigns reject a non-canonical `--benchmark-id`.
  Historical campaign choices still bind v5/v6 exactly.

- [ ] **Step 2: Write provenance-gate RED tests**

  Parameterize missing metrics, missing manifest, invalid JSON, wrong status,
  wrong target, missing config, and mismatch of each identity field including
  benchmark ID and repetitions. Every case must yield
  `invalid_configuration` before credentials or held-out scheduling.

  Include the historical v6 missing-manifest regression so the shared repair
  closes the known bypass without making v6 eligible.

- [ ] **Step 3: Run RED**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_2_v7_runner.py -q
  ```

  Expected: failures for absent campaigns and the missing-manifest bypass.

- [ ] **Step 4: Implement configs, builders, and shared gate**

  Add private v7 prompt/config/planner builders. v7 development passes the
  opaque signal-ID factory into the existing real-runner loop. Refactor
  `_require_v6_development_gate` into a version-neutral private helper that
  requires both files and exact identity; retain a thin v6 wrapper if tests or
  readability benefit. Do not export a new public runner API.

- [ ] **Step 5: Implement CLI scheduling without running a model**

  Add the two choices, load `s1_distortion_v1_2.yaml`, use the canonical IDs,
  and enforce development-before-official. This step exercises only fake
  clients/tests.

- [ ] **Step 6: Run GREEN and runner regressions**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_2_v7_runner.py -q
  python -m pytest tests/evaluation/test_runner.py `
    tests/evaluation/test_phase4_1_v6_runner.py `
    tests/evaluation/test_phase4_2_v7_runner.py -q
  ```

  Expected: all pass; no network call and no held-out destination.

- [ ] **Step 7: Commit**

  ```powershell
  git add src/signal_diag/evaluation/runner.py `
    src/signal_diag/evaluation/__main__.py `
    tests/evaluation/test_phase4_2_v7_runner.py
  git commit -m "feat(evaluation): add Phase 4.2 planner v7 campaigns"
  ```

---

### Task 7: Enforce T208 and obtain independent deterministic review

**Files:**

- Modify: `tests/test_architecture_boundaries.py`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`

**Interfaces:**

- Consumes: Tasks 1-6.
- Produces: deterministic Phase 4.2 gate status only; no real-model claim.

- [ ] **Step 1: Add architecture/cumulative assertions**

  Enforce `signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation`, no
  app package, no lower-layer evaluation imports, no controller-forced action,
  no ScriptedPlanner product fallback, and T201-T208 presence.

- [ ] **Step 2: Run focused Phase 4.2 tests**

  ```powershell
  python -m pytest tests/agent/test_phase4_2_prompt_v7.py `
    tests/agent/test_phase4_2_v7_runtime.py `
    tests/evaluation/test_phase4_2_dataset.py `
    tests/evaluation/test_phase4_2_identity.py `
    tests/evaluation/test_phase4_2_v7_runner.py `
    tests/test_architecture_boundaries.py -q
  ```

- [ ] **Step 3: Run the complete deterministic gate**

  ```powershell
  python -m pytest -q -rxXs -p no:cacheprovider `
    --basetemp .pytest_cache/phase4-2-v7
  python -m ruff check --no-cache src tests scripts
  python -m mypy --no-incremental src
  git diff --check aefccba..HEAD
  ```

  Expected: all T001-T208 pass, zero required skip/xfail, Ruff/mypy/diff-check
  clean.

- [ ] **Step 4: Request two-stage review**

  Use Superpowers subagent-driven review: first verify spec conformance, then
  review code quality. Fix only findings inside frozen Phase 4.2 scope and rerun
  Step 3.

- [ ] **Step 5: Record deterministic status and commit**

  State that deterministic Phase 4.2 is green while real-model development and
  official status remain pending.

  ```powershell
  git add tests/test_architecture_boundaries.py AGENTS.md docs/README.md
  git commit -m "test(evaluation): enforce Phase 4.2 integrity gate"
  ```

---

### Task 8: Run and freeze the v7 development gate

**Files:**

- Conditionally create:
  `docs/evaluations/phase4_2/development/bench_phase4_2_dev_v7_v12_gate3/`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`

**Interfaces:**

- Consumes: exact committed v7/v1.2 candidate, green Task 7, DeepSeek
  credentials.
- Produces: one immutable 40-slot tuning bundle.

- [ ] **Step 1: Verify prerequisites without exposing credentials**

  Confirm Task 7 HEAD and clean tracked workspace, destination absence, exact
  prompt/manifest hashes, and the presence (not value) of `DEEPSEEK_API_KEY`.
  Missing credentials stops honestly without creating a bundle.

- [ ] **Step 2: Run exactly one canonical development campaign**

  ```powershell
  python -m signal_diag.evaluation run-real `
    --campaign phase4.2-v7-development `
    --benchmark-id bench_phase4_2_dev_v7_v12_gate3 `
    --output-dir docs/evaluations/phase4_2/development
  ```

- [ ] **Step 3: Verify the six-file bundle**

  Require 40 unique scoreable Agent slots, 8 baseline slots, exact candidate
  identity, no semantic Planner signal IDs, valid checksums, and unchanged
  historical bundles. Record all metrics and failure codes honestly.

- [ ] **Step 4: Apply the development stop gate**

  If status is not `completed/meets_target`, commit the honest bundle/status and
  stop before Task 9. Do not rerun or edit prompt, data, scorer, or targets under
  the same identity.

- [ ] **Step 5: Commit**

  ```powershell
  git add docs/evaluations/phase4_2/development `
    AGENTS.md docs/README.md
  git commit -m "docs: record Phase 4.2 planner v7 development benchmark"
  ```

---

### Task 9: Conditionally run the one-shot v1.2 official gate

**Files:**

- Conditionally create:
  `docs/evaluations/phase4_2/official/bench_official_s1_v12_planner7_gate3/`

**Interfaces:**

- Consumes: verified Task 8 `completed/meets_target` bundle with exact identity.
- Produces: one immutable 80-slot official held-out bundle.

- [ ] **Step 1: Verify the official preflight**

  Confirm the canonical destination does not exist and the development bundle
  contains matching `metrics.json`, `benchmark_manifest.json`, and checksums.
  Any mismatch must stop as `invalid_configuration` before held-out scheduling.

- [ ] **Step 2: Run exactly once**

  ```powershell
  python -m signal_diag.evaluation run-real `
    --campaign phase4.2-v7-official `
    --benchmark-id bench_official_s1_v12_planner7_gate3 `
    --output-dir docs/evaluations/phase4_2/official
  ```

- [ ] **Step 3: Verify and preserve the result**

  Require 80 unique scoreable Agent slots for `completed`; verify checksums and
  identity. If `below_target`, keep it honestly, forbid rerun/tuning on the same
  held-out, and leave Phase 5 gated.

- [ ] **Step 4: Commit the official bundle**

  ```powershell
  git add docs/evaluations/phase4_2/official
  git commit -m "docs: record Phase 4.2 official planner v7 benchmark"
  ```

---

### Task 10: Record final Phase 4.2 status

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/README.md`

**Interfaces:**

- Consumes: actual Task 7-9 evidence.
- Produces: honest phase gate and Cursor handoff report.

- [ ] **Step 1: Write only the status actually achieved**

  Distinguish deterministic acceptance, development status, official status,
  target status, and CLI `harness_status`. Never call a below-target or unrun
  official campaign product-quality acceptance.

- [ ] **Step 2: Rerun final verification**

  ```powershell
  python -m pytest -q -rxXs -p no:cacheprovider `
    --basetemp .pytest_cache/phase4-2-final
  python -m ruff check --no-cache src tests scripts
  python -m mypy --no-incremental src
  git diff --check aefccba..HEAD
  git status --short --branch
  ```

- [ ] **Step 3: Commit status, without push or merge**

  ```powershell
  git add AGENTS.md docs/README.md
  git commit -m "docs: record Phase 4.2 planner v7 acceptance status"
  ```

- [ ] **Step 4: Report the handoff evidence**

  Include Task SHAs, T201-T208 file mapping, focused RED/GREEN commands, complete
  quality outputs, bundle paths/checksums, warnings, unsupported cases, contract
  concerns, and whether official was legally run. Preserve branch/worktree.

## Mandatory stop conditions

Stop rather than broadening scope when:

- the written gate is unapproved;
- a public Agent/Runtime/DSP/Tool/rule/knowledge contract must change;
- historical identities or bundles drift;
- outbound v1.2 values reveal evaluation semantics;
- real DSP validation cannot establish the v1.2 observable conditions;
- deterministic/static gates fail;
- credentials are unavailable;
- development is not `completed/meets_target`;
- an acceptance destination already exists;
- official is below target.

No stop permits a target reduction, truth edit after seeing model behavior,
same-identity rerun, ScriptedPlanner fallback, held-out inspection, push, merge,
or Phase 5 work.
