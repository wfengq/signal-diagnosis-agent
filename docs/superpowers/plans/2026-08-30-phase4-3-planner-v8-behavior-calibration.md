# Phase 4.3 Planner v8 Behavior Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to execute this plan task-by-task.
> Every code task also uses `superpowers:test-driven-development`; every review
> response uses `superpowers:receiving-code-review`; every completion claim uses
> `superpowers:verification-before-completion`.

**Goal:** Add one coherent `v0.2-s1-planner-8` product Planner candidate,
prove its intended dynamic S1 behavior deterministically, and run the canonical
development and conditionally official campaigns without changing the accepted
Runtime or evaluation foundation.

**Architecture:** Keep dataset `s1-distortion-synthetic` `1.2.0`, all public
models, deterministic DSP/Tool/Rule/Knowledge layers, scoring, targets,
provider, and model unchanged. Move the public `RealLLMPlanner` to one complete
v8 prompt while adding a private exact-v7 compatibility planner for historical
routes. Add v8-only campaign registrations and strict provenance gates above the
existing evaluation runner. Fake transports test the real product boundary;
the Runtime remains purely decision-driven.

**Tech Stack:** Python 3.12, Pydantic v2, pytest/pytest-asyncio, Ruff, mypy,
DeepSeek's OpenAI-compatible client, and the repository's existing evaluation
bundle writer.

**Spec:**
`docs/superpowers/specs/2026-08-30-phase4-3-planner-v8-behavior-calibration-design.md`

**Implementation baseline:** `eb47237` on `phase4-evaluation-design`

**Design baseline:** `93d6d46` freezes CONTRACTS §53, TEST_PLAN §26
T209–T215, D024, and OQ-008.

**Status:** Deterministic Tasks 1–4 are implemented locally; T215 is green at
`1c70568` (not a live-model pass). Task 5 v8 development gate4 at `48dfb89` is
honest `completed/below_target`. Task 6 official/held-out was not run
(unauthorized after the development miss). Task 7 records that honest stop.
Phase 4.3 is not accepted. No v9. Phase 5 remains unauthorized. The next
written choice is model capability versus PlannerContext, not more prompts.

## Global Constraints

- Do not start implementation until the user separately authorizes this plan.
- Read `AGENTS.md` and every required document it lists before Task 1.
- Keep exact v4–v7 prompt bytes, hashes, private planners, campaign routes,
  configurations, and committed evaluation bundles reproducible.
- Keep dataset `1.2.0` byte-identical. Do not modify its manifest, case IDs,
  requests, parameters, seeds, policies, conditions, or split membership.
- Do not modify `PlannerContext`, `AgentDecision`,
  `DistortionDiagnosisRuntime`, DSP, Tools, Rules, Knowledge, scoring,
  `TargetBands`, failure codes, public evaluation models, provider, model,
  profile, or repetition counts.
- Do not force or reorder a Tool, rule, knowledge, or finish action in Runtime.
  Do not add a universal Tool pipeline or a ScriptedPlanner fallback.
- RealLLMPlanner is the product path. Scripted/fake behavior is test input only.
- Never send raw waveform, full FFT, dataset/case identity, category, split,
  generator truth, causal truth, acceptable Tools, sufficient sets, observable
  conditions, policies, or scoring targets to the model.
- Preserve untracked `build/` and all unrelated user changes.
- Do not push, merge, delete the worktree, open Phase 5, or access official
  held-out behavior before the development gate is legally satisfied.
- The canonical v8 development identity may execute once. If it is not
  `completed/meets_target`, preserve it, stop the prompt-only route, and do not
  create v9.
- The canonical v8 official identity may execute once only after the committed,
  byte-identical development candidate is `completed/meets_target`.

## Required Per-Task Review Protocol

For each implementation task, Cursor must use this exact seven-step sequence:

1. An implementer uses TDD and leaves the task changes uncommitted.
2. A separate agent performs specification-compliance review against §53,
   T209–T215, D024, the approved spec, and this plan.
3. The implementer fixes every Critical or Important spec finding; a separate
   agent re-reviews those fixes.
4. A separate agent performs code-quality review.
5. The implementer fixes every Critical or Important quality finding; a
   separate agent re-reviews those fixes.
6. The main Cursor agent independently inspects the diff and reruns focused and
   cumulative verification.
7. Only the main Cursor agent creates the local task commit.

Do not modify the same worktree concurrently. Do not begin the next task until
the current task has passed both reviews, independent verification, and a local
commit. A review narrative is not test evidence.

---

### Task 1: Add the complete v8 prompt and freeze planner identities

**Files:**

- Modify: `src/signal_diag/agent/prompts.py`
- Modify: `src/signal_diag/agent/planner.py`
- Create: `tests/agent/test_phase4_3_prompt_v8.py`
- Retain unchanged: `tests/agent/test_phase4_2_prompt_v7.py`

**Interfaces:**

- Consumes: `_PlannerPromptSpec`, existing v4–v7 prompt specs, and
  `RealLLMPlanner.decide` serialization.
- Produces: `_S1_PROMPT_V8`, public v8 `RealLLMPlanner`, and private
  `_Phase4V7RealLLMPlanner`.
- Does not change the `RealLLMPlanner.__init__` signature or any public model.

- [ ] **Step 1: Snapshot the historical identity before editing**

  Run:

  ```powershell
  python -m pytest tests/agent/test_phase4_2_prompt_v7.py -q
  ```

  Expected: green. Record the existing frozen v7 identity in the new tests:

  ```text
  version  v0.2-s1-planner-7
  bytes    9386
  sha256   008b0fee78a83ada11140b42596d0f0e1abed27e641d5107e53ba759db6bc82a
  ```

- [ ] **Step 2: Write T209 identity tests**

  In `tests/agent/test_phase4_3_prompt_v8.py`, assert:

  ```python
  assert _S1_PROMPT_V8.version == "v0.2-s1-planner-8"
  assert RealLLMPlanner._prompt_spec is _S1_PROMPT_V8
  assert PROMPT_VERSION == "v0.2-s1-planner-8"
  assert _SYSTEM_PROMPT == _S1_PROMPT_V8.system_prompt
  assert _Phase4V7RealLLMPlanner._prompt_spec is _S1_PROMPT_V7
  ```

  Also assert v4–v7 literal byte counts and SHA-256 values remain frozen, v8 is
  distinct from each historical prompt, is not prefixed by or appended to v7,
  and the public constructor signature remains unchanged. After v8 is written,
  freeze its exact byte count and SHA-256 as literals in this test file.

- [ ] **Step 3: Write T210 semantic tests before the prompt**

  Assert the complete v8 prompt contains mutually consistent policy and
  representative examples for all of the following:

  - broad requests begin with viable `clipping` and `harmonic_distortion`
    hypotheses and do not finish until both close;
  - visible symptoms, public metadata, hypotheses, and same-run observations
    drive the first Tool; `signal_id` is opaque;
  - harmonic analysis can be called directly without spectrum or standalone F0;
  - clean broad paths use clipping plus harmonic evidence, one relevant rule
    evaluation, no decorative spectrum/F0, and no knowledge;
  - harmonic-specific paths start with harmonic analysis and do not add
    clipping/spectrum/F0 without an observed reason;
  - combined broad paths continue after clipping and require separate order-2
    harmonic Evidence before claiming harmonic distortion;
  - invalid/noise paths obtain only the necessary invalid harmonic evidence,
    evaluate rules, retrieve explanatory knowledge, and finish with one
    evidence/rule/knowledge-grounded inconclusive claim plus a limitation;
  - once all viable hypotheses close, the next action is required
    rule/knowledge work or finish, not another unrelated Tool.

  Parse embedded JSON examples as the v7 tests do. Require every example to
  validate structurally and prohibit contradictory examples such as an empty
  hypothesis list for a broad initial assessment, spectrum as a mandatory THD
  prerequisite, or finish-after-clipping for a broad combined request.

- [ ] **Step 4: Run RED**

  ```powershell
  python -m pytest tests/agent/test_phase4_3_prompt_v8.py -q
  ```

  Expected: collection or assertions fail because `_S1_PROMPT_V8` and the
  private v7 planner do not exist and the public planner still binds v7.

- [ ] **Step 5: Implement one coherent v8 prompt**

  In `prompts.py`, add a new complete system prompt rather than concatenating
  v7. It must retain the accepted decision JSON schemas and same-run reference
  rules while replacing the behavior examples with the §53 policy. Include
  explicit instruction text equivalent to:

  ```text
  Keep task_assessment.hypotheses equal to the still-viable requested S1 causes.
  A positive result for one cause does not close another viable cause.
  Choose the shortest informative Tool from visible symptoms and observations.
  analyze_harmonic_distortion does not require spectrum or standalone F0 first.
  Never infer behavior from signal_id; it is an opaque repository key.
  Finish only after every viable hypothesis is supported, ruled out, or
  explicitly unobservable with a traceable limitation.
  ```

  Provide four consistent representative paths: clean broad, harmonic-specific,
  combined broad, and invalid/noise. Use symbolic same-run reference notation
  already accepted by the prompt tests; never include live-looking IDs or
  evaluation labels.

- [ ] **Step 6: Bind v8 publicly and preserve v7 privately**

  In `planner.py`, import `_S1_PROMPT_V8`, change only the public prompt
  constants and `RealLLMPlanner._prompt_spec` to v8, and add:

  ```python
  class _Phase4V7RealLLMPlanner(RealLLMPlanner):
      _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V7
  ```

  Do not change v4–v6 private planners or transport behavior.

- [ ] **Step 7: Run GREEN and historical regressions**

  ```powershell
  python -m pytest tests/agent/test_phase4_3_prompt_v8.py -q
  python -m pytest tests/agent/test_phase4_2_prompt_v7.py tests/agent/test_real_llm_planner.py -q
  ```

  Expected: all green. Freeze the final v8 byte count and SHA-256 in T209 only
  after the prompt text and reviews are stable.

- [ ] **Step 8: Apply the required review protocol and commit**

  The spec reviewer must specifically compare every prompt example to §53.2.
  The quality reviewer must check for duplicated/contradictory instructions and
  accidental v4–v7 drift. After independent verification:

  ```powershell
  git add src/signal_diag/agent/prompts.py `
    src/signal_diag/agent/planner.py `
    tests/agent/test_phase4_3_prompt_v8.py
  git commit -m "feat(agent): add Phase 4.3 planner v8 policy"
  ```

---

### Task 2: Prove v8 non-leakage and product-boundary behavior

**Files:**

- Create: `tests/agent/test_phase4_3_v8_runtime.py`
- Modify only if a test exposes a §53-permitted prompt defect:
  `src/signal_diag/agent/prompts.py`, `src/signal_diag/agent/planner.py`
- Retain unchanged: `src/signal_diag/agent/runtime.py`

**Interfaces:**

- Consumes: active `RealLLMPlanner`, fake chat-completions transport,
  `DistortionDiagnosisRuntime`, real `SignalToolService`, `RuleEngine`,
  `YamlRuleProfileLoader`, `KnowledgeIndex`, and synthetic repositories.
- Produces: deterministic T211–T212 acceptance without substituting a scripted
  controller for the product Planner.

- [ ] **Step 1: Write T211 outbound-value leakage tests**

  Capture exact messages sent by active `RealLLMPlanner`. Use an opaque
  `sig_eval_<sha256>` signal ID and adversarial hidden fixtures whose
  case/category/policy values are unique sentinels. Recursively inspect keys and
  values. Assert outbound JSON omits case/category/split, generator and causal
  truth, policies, acceptable Tools, sufficient sets, observable conditions,
  targets, samples, full FFT/frequencies, and manifest identity. Assert changing
  only the opaque signal ID does not change the fake transport decision path.

- [ ] **Step 2: Build an observation-driven fake transport**

  The fake transport receives real serialized v8 Planner messages and returns
  valid JSON based only on `user_request`, public metadata, current
  `task_assessment`, compact same-run Evidence, rule evaluations, and knowledge
  results. It must not read dataset truth or bypass `RealLLMPlanner.decide`.

- [ ] **Step 3: Write four T212 end-to-end paths**

  Drive the real Runtime and deterministic dependencies and assert:

  ```text
  clean broad: clipping + harmonic (either order) -> rules -> no-fault finish;
               no spectrum, standalone F0, or knowledge
  harmonic:    harmonic first -> rules -> harmonic finish;
               no unrelated Tool or knowledge
  combined:    clipping + harmonic (either order) -> rules -> two-cause finish;
               no early finish after clipping
  noise:       fundamental or harmonic -> required invalid harmonic Evidence ->
               rules -> knowledge -> inconclusive finish;
               no clipping/spectrum detour
  ```

  Resolve every Evidence/rule/knowledge reference in the same run. For noise,
  require one claim citing Evidence, NOT_APPLICABLE rule evaluation, and used
  knowledge plus a non-empty limitation.

- [ ] **Step 4: Run RED**

  ```powershell
  python -m pytest tests/agent/test_phase4_3_v8_runtime.py -q
  ```

  Do not edit Runtime to force GREEN.

- [ ] **Step 5: Make only §53-permitted prompt/planner corrections**

  Correct v8 wording/examples only. Re-freeze the v8 byte/hash literals whenever
  prompt bytes change before commit. Do not change deterministic layers,
  dataset, scoring, or targets.

- [ ] **Step 6: Run GREEN and agent regressions**

  ```powershell
  python -m pytest tests/agent/test_phase4_3_v8_runtime.py -q
  python -m pytest tests/agent -q
  ```

- [ ] **Step 7: Apply the required review protocol and commit**

  Spec review must confirm the fake transport is not a disguised product
  controller. Quality review must verify same-run references and absence of
  hidden evaluation truth. Then inspect status and commit only changed files:

  ```powershell
  git add src/signal_diag/agent/prompts.py `
    src/signal_diag/agent/planner.py `
    tests/agent/test_phase4_3_prompt_v8.py `
    tests/agent/test_phase4_3_v8_runtime.py
  git commit -m "test(agent): prove Phase 4.3 v8 product behavior"
  ```

---

### Task 3: Add canonical v8 campaigns, strict preflight, and CLI routing

**Files:**

- Modify: `src/signal_diag/evaluation/runner.py`
- Modify: `src/signal_diag/evaluation/__main__.py`
- Create: `tests/evaluation/test_phase4_3_v8_runner.py`
- Retain unchanged: `src/signal_diag/evaluation/models.py`
- Retain unchanged: `src/signal_diag/evaluation/scoring.py`
- Retain unchanged: `src/signal_diag/evaluation/manifests/s1_distortion_v1_2.yaml`
- Retain unchanged: all committed `docs/evaluations/**` bundles

**Interfaces:**

- Consumes: `_Phase4V7RealLLMPlanner`, public v8 `RealLLMPlanner`, existing
  v1.2 opaque signal-ID factory, report writer, identity-complete development
  gate, and benchmark models.
- Produces: `_PHASE4_3_V8_CAMPAIGNS`, v8 config/preflight/builders/runners, and
  additive CLI dispatch.

- [ ] **Step 1: Write T209 historical-runner compatibility tests**

  Assert `_build_phase4_2_v7_planner` constructs
  `_Phase4V7RealLLMPlanner`, so the public move to v8 does not mutate v7.
  Reassert v4–v6 builders, historical configurations, and bundle fingerprints.

- [ ] **Step 2: Write T214 canonical registration tests**

  Require exactly:

  ```python
  {
      "phase4.3-v8-development": "bench_phase4_3_dev_v8_v12_gate4",
      "phase4.3-v8-official": "bench_official_s1_v12_planner8_gate4",
  }
  ```

  Both bind dataset `1.2.0`, profile `1.0.0-demo`, DeepSeek
  `deepseek-v4-flash`, v8 version/hash, five repetitions, concurrency one, and
  the opaque ID factory. Development is 8 x 5; official is 16 x 5.

- [ ] **Step 3: Write strict official-gate tests**

  Parameterize missing/unreadable/invalid metrics or manifest, missing identity
  fields, any identity mismatch, invalid/missing checksums, changed v8 hash, and
  development status other than `completed/meets_target`. Each must become
  `invalid_configuration` before API-key lookup, OpenAI import, client creation,
  or held-out scheduling. Non-canonical IDs and custom manifests are rejected
  without rewriting them.

- [ ] **Step 4: Write additive CLI tests**

  Parser choices contain historical plus v8 routes, default remains `phase4`,
  one registry supplies choices and dispatch, IDs are not duplicated in
  `__main__.py`, and secrets never appear in help/reports.

- [ ] **Step 5: Run RED**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_3_v8_runner.py -q
  ```

- [ ] **Step 6: Implement the minimal additive runner**

  Add v8 constants/hash/config/preflight; change only the historical v7 builder
  to use the private v7 planner; add a public-v8 builder; reuse the existing real
  split executor and opaque-ID factory; add v8 development/official runners and
  a single v8 registry/dispatcher. Official must validate the canonical bundle
  at
  `docs/evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4`
  before credentials. Extend CLI choices/dispatch without altering historical
  branches or public models.

- [ ] **Step 7: Run GREEN and campaign regressions**

  ```powershell
  python -m pytest tests/evaluation/test_phase4_3_v8_runner.py -q
  python -m pytest tests/evaluation/test_phase4_2_v7_runner.py `
    tests/evaluation/test_phase4_2_identity.py `
    tests/evaluation/test_phase4_1_runner.py `
    tests/evaluation/test_phase4_1_v6_runner.py -q
  ```

- [ ] **Step 8: Apply the required review protocol and commit**

  Spec review exercises every failure before credential access. Quality review
  rejects duplicated identities and any v7 builder following public v8. Then:

  ```powershell
  git add src/signal_diag/evaluation/runner.py `
    src/signal_diag/evaluation/__main__.py `
    tests/evaluation/test_phase4_3_v8_runner.py
  git commit -m "feat(evaluation): add Phase 4.3 v8 campaigns"
  ```

---

### Task 4: Enforce T213–T215 and freeze deterministic readiness

**Files:**

- Modify: `tests/test_architecture_boundaries.py`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: this plan only to record deterministic evidence; do not rewrite §53
  or T209–T215

**Interfaces:**

- Consumes: T209–T214 implementation and T001–T208 regressions.
- Produces: T213 controller guard, T215 cumulative gate, and honest status
  `deterministic ready / real-model pending`.

- [x] **Step 1: Write T213 architecture guards**

  Assert Runtime constructs no Tool/rule/knowledge/finish decisions; no Runtime
  branch keys off prompt version, case identity, split, or targets; v8 product
  builders use RealLLMPlanner; no universal pipeline or scripted fallback was
  introduced; existing retry, invalid, no-progress, max-action, and termination
  tests remain present and green.

- [x] **Step 2: Write T215 scope and cumulative guards**

  From baseline `eb47237`, allow changes only under `AGENTS.md`, `docs/`,
  `src/signal_diag/agent/`, `src/signal_diag/evaluation/`, and `tests/`. Freeze
  `agent/runtime.py`, evaluation models/scoring/dataset/manifests, all upstream
  signal/DSP/Tool/Rule/Knowledge paths, and `app/`. Require T209–T215 test names,
  unchanged TargetBands, absent app package, and `git diff --check
  eb47237..HEAD`.

- [x] **Step 3: Run RED**

  ```powershell
  python -m pytest tests/test_architecture_boundaries.py -q
  ```

- [x] **Step 4: Complete the narrow gate and status docs**

  Add only tests/metadata needed for the frozen gate. Update `AGENTS.md` and
  `docs/README.md` to say deterministic Phase 4.3 implementation is ready,
  while development, official, acceptance, and Phase 5 remain pending/gated.

- [x] **Step 5: Run the complete deterministic gate**

  ```powershell
  python -m pytest -q -rxXs -p no:cacheprovider `
    --basetemp .pytest_cache/phase4-3-v8-deterministic
  python -m ruff check --no-cache src tests scripts
  python -m mypy --no-incremental src
  git diff --check eb47237..HEAD
  ```

  Expected: all tests pass, zero required skip/xfail, and no Ruff/mypy/diff
  output indicating failure. Record exact counts and output.

  Task 4 local evidence (uncommitted, HEAD `982e60a`, baseline `eb47237`):
  `695 passed in 33.02s`, zero required skip/xfail; Ruff including I001
  passed; mypy `Success: no issues found in 46 source files`;
  `git diff --check eb47237..HEAD` and `git diff --check eb47237` both
  exit 0. This is deterministic ready / real-model pending only.

- [ ] **Step 6: Apply the required review protocol and commit**

  Spec review maps T209–T215 to tests. Quality review inspects the full baseline
  diff and frozen paths. After main-agent verification:

  ```powershell
  git add AGENTS.md docs/README.md `
    docs/superpowers/plans/2026-08-30-phase4-3-planner-v8-behavior-calibration.md `
    tests/test_architecture_boundaries.py
  git commit -m "test(evaluation): enforce Phase 4.3 deterministic gate"
  ```

---

### Task 5: Execute the one-shot v8 development campaign

**Status:** complete — honest `completed/below_target` at `48dfb89`. Task 6
is not authorized. Bundle frozen; do not mutate.

**Files:**

- Create once:
  `docs/evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4/`
- Modify after the immutable result: `AGENTS.md`, `docs/README.md`, and this
  plan's status/checklist
- Do not modify implementation, prompt, dataset, scorer, targets, or historical
  assets after this run

**Interfaces:**

- Consumes: committed T001–T215 green tree, canonical v8 bytes/configuration,
  dataset `1.2.0` development split, and `DEEPSEEK_API_KEY`.
- Produces: one immutable six-file 40-Agent-slot development bundle.

- [ ] **Step 1: Re-establish legal preconditions**

  Rerun Task 4's full gate from a committed tree. Verify:

  ```powershell
  Test-Path docs/evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4
  ```

  Expected: `False`. If true, stop without overwrite/delete/rename/rerun.
  Confirm API-key presence without printing it. Missing credentials pause only
  the live campaign, not deterministic acceptance.

- [ ] **Step 2: Run canonical development exactly once**

  ```powershell
  python -m signal_diag.evaluation run-real `
    --campaign phase4.3-v8-development `
    --benchmark-id bench_phase4_3_dev_v8_v12_gate4 `
    --output-dir docs/evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4
  ```

  Do not retry stochastic metric misses.

- [ ] **Step 3: Validate all evidence, not selected headlines**

  Require the existing six files: `benchmark_manifest.json`, `metrics.json`,
  `traces.jsonl`, `failures.jsonl`, `report.md`, and `checksums.sha256`. Verify
  checksums, complete identity, 40 unique scoreable Agent slots, completed
  status, and every applicable frozen target.

- [ ] **Step 4: Apply the honest stop gate**

  If anything is not exactly `completed/meets_target`, preserve/commit it,
  document exact failures, do not run official, do not create v9, skip Task 6,
  and continue only to Task 7. Only an exact pass permits Task 6.

- [ ] **Step 5: Apply reviews and commit**

  Review identity, slots, checksums, all targets, absence of secrets/raw arrays,
  and immutability after generation. Then:

  ```powershell
  git add AGENTS.md docs/README.md `
    docs/evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4 `
    docs/superpowers/plans/2026-08-30-phase4-3-planner-v8-behavior-calibration.md
  git commit -m "eval(phase4.3): record v8 development gate4 result"
  ```

---

### Task 6: Conditionally execute the one-shot official held-out campaign

**Status:** skipped — development is `completed/below_target`, so official
v1.2.0 held-out was not legally run. `docs/evaluations/phase4_3/official/`
does not exist. Do not start.

**Files:**

- Create once, only after a legal development pass:
  `docs/evaluations/phase4_3/official/bench_official_s1_v12_planner8_gate4/`
- Modify after the result: `AGENTS.md`, `docs/README.md`, and this plan

**Interfaces:**

- Consumes: committed checksum-valid development `completed/meets_target`
  bundle and byte-identical v8 candidate.
- Produces: one immutable six-file 80-Agent-slot official bundle.

- [ ] **Step 1: Prove official eligibility before credentials/held-out**

  Rerun official preflight tests and static gates; verify the development bundle
  is unchanged and the official directory does not exist. Any mismatch,
  non-pass status, or existing destination stops as `invalid_configuration`.

- [ ] **Step 2: Run official exactly once**

  ```powershell
  python -m signal_diag.evaluation run-real `
    --campaign phase4.3-v8-official `
    --benchmark-id bench_official_s1_v12_planner8_gate4 `
    --output-dir docs/evaluations/phase4_3/official/bench_official_s1_v12_planner8_gate4
  ```

  Never tune from or rerun held-out results.

- [ ] **Step 3: Validate and retain the official outcome**

  Verify six files, checksums, identity, 80 unique scoreable Agent slots, every
  target, and no secrets/raw arrays. Phase 4.3 is accepted only for exact
  `completed/meets_target`; any other status remains immutable and gates Phase 5.

- [ ] **Step 4: Apply reviews and commit**

  Verify no source/prompt/target/dataset change between development and official:

  ```powershell
  git add AGENTS.md docs/README.md `
    docs/evaluations/phase4_3/official/bench_official_s1_v12_planner8_gate4 `
    docs/superpowers/plans/2026-08-30-phase4-3-planner-v8-behavior-calibration.md
  git commit -m "eval(phase4.3): record v8 official gate4 result"
  ```

---

### Task 7: Record final status and prepare independent handoff

**Status:** recording honest stop only. Task 5 committed the six-file bundle at
`48dfb89` but left `AGENTS.md` / `docs/README.md` / this plan saying
development pending. Remaining deltas are the five-way status distinction,
missed bands, Task 6-not-run, plan status line, T209–T215 mapping, and
independent handoff. Commit skipped by user override. Do not upgrade to
`meets_target`.

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: this plan's status/checklist
- Keep frozen contracts unchanged unless a genuine contradiction is recorded
  through `docs/OPEN_QUESTIONS.md`

**Interfaces:**

- Consumes: deterministic gate and only legally executed campaigns.
- Produces: honest status and independent-verification handoff; no merge/push or
  Phase 5 authorization.

- [x] **Step 1: Record exactly one state**

  Chosen: development `completed/below_target` with official not run.
  Deterministic T001–T215 green at `1c70568` is not a live-model pass.
  Never conflate deterministic harness, CLI `harness_status=pending`,
  `benchmark_status=completed`, and `target_status=below_target`.

- [x] **Step 2: Run final independent verification**

  ```powershell
  python -m pytest -q -rxXs -p no:cacheprovider `
    --basetemp .pytest_cache/phase4-3-final
  python -m ruff check --no-cache src tests scripts
  python -m mypy --no-incremental src
  git diff --check eb47237..HEAD
  git status --short --branch
  git log --oneline 93d6d46..HEAD
  ```

  This session: `695 passed in 29.89s`, zero required skip/xfail; Ruff all
  checks passed; mypy 46 source files clean; `git diff --check eb47237..HEAD`
  exit 0. Unrelated untracked: `build/` only. Paste counts, not megabytes.

- [x] **Step 3: Map acceptance IDs**

  Report:

  ```text
  T209–T210  tests/agent/test_phase4_3_prompt_v8.py
  T211–T212  tests/agent/test_phase4_3_v8_runtime.py
  T214       tests/evaluation/test_phase4_3_v8_runner.py
  T213/T215  tests/test_architecture_boundaries.py plus cumulative gates
  ```

- [ ] **Step 4: Apply final reviews and commit status docs if changed**

  **Skipped (user override).** Parent will review then commit. Do not stage
  `.superpowers`. Do not amend `48dfb89`.

- [x] **Step 5: Deliver the handoff**

  Handoff is `.superpowers/sdd/phase43-handover.md` (gitignored). Development
  missed; next design choice is model capability versus PlannerContext
  (option 2), not more prompts. No push/merge/Phase 5/v9.
