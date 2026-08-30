# Phase 4.1 Prompt v6 Correction Implementation Plan

> **For implementation agents:** Use `superpowers:executing-plans` in a
> dedicated implementation session. For every code task, also use
> `superpowers:test-driven-development`; before completion claims, use
> `superpowers:verification-before-completion`. Repository specifications and
> `AGENTS.md` take precedence.

**Goal:** Correct the repeatable v5 prompt contradictions exposed by the
immutable 40-slot development gate while preserving all v4/v5 identities and
evidence, then admit a one-shot v1.1.0 held-out run only after a new v6
development candidate meets the frozen target bands.

**Architecture:** Keep `RealLLMPlanner` as the product planner and make v6 one
coherent, versioned prompt rather than another appendix. Preserve v4 and v5
through private compatibility planners and unchanged campaign choices. Reuse
the existing runtime, DSP tools, rules, knowledge index, dataset, scorer, and
report models; add only versioned prompt/config/campaign identities and
deterministic tests. No runtime action is forced and no evaluation truth enters
the planner context.

**Baseline:** `f9392c2` on `phase4-evaluation-design`.

**Status:** Task 1 contract gate approved and frozen on 2026-08-30; Task 2–8
implementation authorized; official held-out remains development-gated.

**Design authority:**
`docs/superpowers/specs/2026-08-30-phase4-1-prompt-v6-correction-design.md`.
Implementation must follow frozen CONTRACTS §51, TEST_PLAN §24/T196–T200, and
D022.

---

## Global constraints

- Do not modify code before §51, TEST_PLAN §24/T196–T200, and D022 are approved.
- Do not rewrite, delete, or redirect v4/v5 prompts, hashes, builders, CLI
  campaign choices, or committed evaluation bundles.
- Do not overwrite
  `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/`.
- Do not run or inspect the v1.1.0 held-out split before the v6 development
  gate is `completed/meets_target`.
- Do not change public Planner, Runtime, DSP, Tool, Rule, Knowledge, evaluation,
  scoring, target-band, or reporting contracts.
- Do not force Tool, rule, or knowledge actions in the controller.
- Do not pass raw waveforms, full FFT arrays, generator truth, expected faults,
  case policies, or score targets to the LLM.
- The product path remains `RealLLMPlanner`; scripted/fake behavior is only a
  deterministic test double and never a product fallback.
- Preserve `build/` and any unrelated user changes. Do not push or merge.

## Expected files

```text
docs/
├── CONTRACTS_V0_2.md
├── TEST_PLAN_V0_2.md
├── DECISIONS.md
├── OPEN_QUESTIONS.md
├── README.md
└── superpowers/
    ├── specs/2026-08-30-phase4-1-prompt-v6-correction-design.md
    └── plans/2026-08-30-phase4-1-prompt-v6-correction.md
src/signal_diag/
├── agent/
│   ├── prompts.py
│   └── planner.py
└── evaluation/
    ├── __main__.py
    └── runner.py
tests/
├── agent/
│   ├── test_phase4_1_prompt_v6.py
│   └── test_phase4_1_v6_runtime.py
├── evaluation/test_phase4_1_v6_runner.py
└── test_architecture_boundaries.py
docs/evaluations/phase4_1/
├── development/bench_phase4_1_dev_v6_gate2/   # conditional Task 6 output
└── official/bench_official_s1_v11_planner6_gate2/  # conditional Task 7 output
```

---

### Task 1: Freeze the additive v6 contract gate

**Files:**

- Modify: `docs/CONTRACTS_V0_2.md`
- Modify: `docs/TEST_PLAN_V0_2.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/OPEN_QUESTIONS.md`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Review: `docs/superpowers/specs/2026-08-30-phase4-1-prompt-v6-correction-design.md`

**Step 1: Obtain written approval**

Present the design for review. Require explicit approval of OQ-006, additive
§51, T196–T200, and D022. Stop if the user requests a materially different
contract.

**Step 2: Record §51 without altering §50**

Freeze:

- prompt version `v0.2-s1-planner-6` with an implementation-derived exact
  SHA-256;
- a complete coherent prompt, not a v4/v5 appendix;
- exact preservation of v4/v5 prompt bytes and campaign behavior;
- new development/official campaign identities and benchmark IDs;
- the gate2 protocol and held-out prohibition;
- no public model, scorer, target, or runtime semantic changes.

**Step 3: Add TEST_PLAN §24**

Freeze T196–T200 exactly:

- T196: v4/v5 immutability plus exact v6 identity/hash;
- T197: coherent dual-truth, combined-hypothesis, no-fault, and inconclusive
  semantics;
- T198: no leakage, same-run references, rule/knowledge propagation, and
  dynamic routes;
- T199: additive v6 campaign identity and split scheduling;
- T200: cumulative T001–T200 gate plus Ruff, mypy, architecture, and
  diff-check.

**Step 4: Record D022 and close OQ-006**

State why v5 remains immutable historical evidence, why v6 is additive, and
why the v1.1.0 development split may be reused while held-out remains sealed.

**Step 5: Synchronize phase status documents**

Set Phase 4.1 to “v6 implementation authorized; held-out gated” only after the
written approval. Do not claim acceptance.

**Step 6: Verify documentation**

Run:

```powershell
git diff --check
rg -n "§51|T196|T197|T198|T199|T200|D022|OQ-006|planner-6" `
  AGENTS.md docs
```

Expected: no whitespace errors; all additive identities agree; §50 and
T184–T195 remain unchanged.

**Step 7: Commit locally**

```powershell
git add AGENTS.md docs
git commit -m "docs: freeze Phase 4.1 prompt v6 correction gate"
```

Do not push.

---

### Task 2: Add the coherent v6 prompt with immutable legacy identities

**Files:**

- Create: `tests/agent/test_phase4_1_prompt_v6.py`
- Modify: `src/signal_diag/agent/prompts.py`
- Modify: `src/signal_diag/agent/planner.py`

**Step 1: Write the T196 identity tests**

Assert the accepted exact v4 and v5 bytes and hashes remain unchanged. Assert
v6 has version `v0.2-s1-planner-6`, has a stable exact hash, and is not formed
by appending text to v4 or v5. Assert default `RealLLMPlanner` selects v6 while
private legacy planners select their exact historical prompt identities.

**Step 2: Run RED**

```powershell
python -m pytest tests/agent/test_phase4_1_prompt_v6.py -q
```

Expected: fail because v6 does not exist and the active product prompt is v5.

**Step 3: Write the T197 semantic tests before implementation**

Inspect the complete v6 prompt as policy text and require mutually consistent
instructions/examples for:

- keeping each viable clipping/harmonic hypothesis open until supported,
  ruled out, or explicitly unobservable;
- distinguishing observed harmonic distortion from rule-profile acceptance;
- using `no_supported_fault` only when the final supported cause set is empty;
- requiring an inconclusive claim with same-run Evidence, applicable rule or
  explicit non-applicability, knowledge citation when retrieval was used, and
  a limitation;
- treating clean negative evidence as supporting context rather than an extra
  no-fault diagnosis beside a supported fault;
- dynamically choosing actions without a fixed clipping/FFT/F0/THD pipeline.

**Step 4: Implement the smallest coherent prompt**

Add `_S1_PROMPT_V6` as one complete prompt. Do not concatenate v4 or v5. Keep
v4/v5 constants byte-for-byte unchanged. Add a private v5 planner class if the
current code has only v4 compatibility. Bind public `RealLLMPlanner` to v6
without changing its constructor or request/response schemas.

**Step 5: Run GREEN**

```powershell
python -m pytest tests/agent/test_phase4_1_prompt_v6.py -q
python -m pytest tests/agent/test_phase4_1_prompt_policy.py `
  tests/agent/test_real_llm_planner.py -q
```

Expected: pass; all historical prompt identity tests remain green.

**Step 6: Commit locally**

```powershell
git add src/signal_diag/agent/prompts.py src/signal_diag/agent/planner.py `
  tests/agent/test_phase4_1_prompt_v6.py
git commit -m "feat(agent): add coherent Phase 4.1 planner v6 prompt"
```

---

### Task 3: Prove v6 behavior through the real planner boundary and runtime

**Files:**

- Create: `tests/agent/test_phase4_1_v6_runtime.py`
- Modify only if required by the frozen contract:
  `src/signal_diag/agent/prompts.py`

**Step 1: Write T198 product-boundary tests**

Use a deterministic fake transport behind the real `RealLLMPlanner`, then run
the real `DistortionDiagnosisRuntime`, Tools, RuleEngine, and KnowledgeIndex.
Do not replace the planner with `ScriptedPlanner` for these tests.

Cover four independent traces:

1. harmonic evidence near 5% plus a PASS rule still yields a supported harmonic
   observation and separately states configured acceptance;
2. a combined clipping/harmonic signal does not finish after resolving only
   clipping when harmonic remains viable;
3. invalid/noisy harmonic evidence produces traceable inconclusive output and
   uses retrieved knowledge in a claim when retrieval occurred;
4. strong harmonic evidence may cite clean clipping evidence as context but
   does not add `no_supported_fault` to the causal set.

For every trace, assert all Evidence, rule, and knowledge references resolve in
the same run.

**Step 2: Add no-leakage assertions**

Capture every outbound planner message. Reject raw waveform values, full FFT
arrays, generator inputs, case IDs, expected outcomes/faults, target metrics,
manifest policy fields, and held-out metadata.

**Step 3: Run RED**

```powershell
python -m pytest tests/agent/test_phase4_1_v6_runtime.py -q
```

Expected: fail only on missing/incoherent v6 policy behavior represented by
the fake transport decisions, never because the runtime forces an action.

**Step 4: Make prompt-only corrections if needed**

Change only v6 prompt wording/examples. Do not change PlannerContext,
Runtime routing, Tool selection enforcement, rule thresholds, knowledge
retrieval, or scoring.

**Step 5: Run GREEN and regression tests**

```powershell
python -m pytest tests/agent/test_phase4_1_v6_runtime.py -q
python -m pytest tests/agent tests/test_phase3_diagnosis.py -q
```

**Step 6: Commit locally**

```powershell
git add src/signal_diag/agent/prompts.py `
  tests/agent/test_phase4_1_v6_runtime.py
git commit -m "test(agent): enforce planner v6 runtime semantics"
```

---

### Task 4: Add reproducible v6 campaign routes without redirecting v5

**Files:**

- Create: `tests/evaluation/test_phase4_1_v6_runner.py`
- Modify: `src/signal_diag/evaluation/runner.py`
- Modify: `src/signal_diag/evaluation/__main__.py`

**Step 1: Write T199 route and identity tests**

Assert existing campaign choices remain byte-for-byte/behaviorally mapped to
v5. Add exactly:

- `phase4.1-v6-development` → v1.1.0 development split, v6, 8 × 5 slots;
- `phase4.1-v6-official` → v1.1.0 held-out split, v6, 16 × 5 slots.

Assert canonical benchmark IDs are:

- `bench_phase4_1_dev_v6_gate2`;
- `bench_official_s1_v11_planner6_gate2`.

Assert config validation rejects mismatched prompt version/hash, dataset,
profile, provider/model, split, or campaign identity rather than rewriting it.

**Step 2: Run RED**

```powershell
python -m pytest tests/evaluation/test_phase4_1_v6_runner.py -q
```

**Step 3: Implement additive private helpers**

Add v6 config/planner/preflight/development/official wrappers that reuse the
existing real benchmark executor and six-file reporting path. If needed, add a
private v5 planner used by the two existing Phase 4.1 routes. Do not alter
public evaluation models or scorer signatures.

**Step 4: Enforce append-only and split gates**

The development route must refuse an existing destination. The official route
must require an explicitly validated development `completed/meets_target`
bundle and refuse an existing official destination. Unit tests must not call a
real provider.

**Step 5: Run GREEN and legacy regression**

```powershell
python -m pytest tests/evaluation/test_phase4_1_v6_runner.py -q
python -m pytest tests/evaluation/test_runner.py `
  tests/evaluation/test_phase4_1_runner.py -q
```

**Step 6: Commit locally**

```powershell
git add src/signal_diag/evaluation/runner.py `
  src/signal_diag/evaluation/__main__.py `
  tests/evaluation/test_phase4_1_v6_runner.py
git commit -m "feat(evaluation): add additive planner v6 campaigns"
```

---

### Task 5: Enforce T200 and obtain deterministic review

**Files:**

- Modify: `tests/test_architecture_boundaries.py`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`

**Step 1: Add the cumulative acceptance test**

Add a T200 architecture/gate test using baseline `f9392c2`. Require v6 changes
to remain inside agent/evaluation/tests/docs boundaries; preserve the complete
dependency direction and reject Phase 5 adapters or controller-forced actions.

**Step 2: Run the focused Phase 4.1 suite**

```powershell
python -m pytest tests/agent/test_phase4_1_prompt_v6.py `
  tests/agent/test_phase4_1_v6_runtime.py `
  tests/evaluation/test_phase4_1_v6_runner.py `
  tests/test_architecture_boundaries.py -q -rxXs
```

Expected: all pass, zero required skip/xfail.

**Step 3: Run the cumulative deterministic gate**

```powershell
python -m pytest -q -rxXs -p no:cacheprovider `
  --basetemp .pytest_cache/phase4-1-v6
python -m ruff check --no-cache src tests scripts
python -m mypy --no-incremental src
git diff --check f9392c2..HEAD
```

Expected: T001–T200 pass, no required skip/xfail, Ruff/mypy/diff-check clean.

**Step 4: Review before real-model use**

Use `superpowers:requesting-code-review`. Review specifically for prompt
contradictions, evaluation leakage, v5 route drift, hidden fixed pipelines,
controller action forcing, held-out access, and same-run reference validity.
Fix Critical/Important findings with RED/GREEN evidence, then repeat Step 3.

**Step 5: Synchronize implementation status**

Record “v6 deterministic gate passed; real development gate pending.” Do not
claim Phase 4.1 accepted and do not open Phase 5.

**Step 6: Commit locally**

```powershell
git add tests/test_architecture_boundaries.py AGENTS.md docs/README.md
git commit -m "test(evaluation): enforce Phase 4.1 planner v6 gate"
```

---

### Task 6: Run and freeze the 40-slot v6 development gate2

**Prerequisite:** Task 5 is independently green and real DeepSeek credentials
exist. Missing credentials block only this real-model task.

**Files:**

- Create only:
  `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v6_gate2/`

**Step 1: Preflight without exposing credentials**

Confirm the output directory does not exist. Validate git SHA, Python and SDK
versions, DeepSeek/`deepseek-v4-flash`, v1.1.0 development split, approved rule
profile, v6 version/hash, concurrency, repetitions, and credential presence.

**Step 2: Run exactly one 40-slot development campaign**

```powershell
python -m signal_diag.evaluation run-real `
  --campaign phase4.1-v6-development `
  --benchmark-id bench_phase4_1_dev_v6_gate2 `
  --output-dir docs/evaluations/phase4_1/development
```

Do not use a fake client and do not access held-out cases.

**Step 3: Verify the immutable six-file bundle**

Require 40 unique, scoreable Agent slots, 8 cases × 5; validate checksums,
schemas, fingerprints, score and aggregate recomputation, failure coverage,
redaction, and append-only refusal. Confirm the v5 gate1 directory remains
byte-identical.

**Step 4: Apply the stop gate**

- If `completed/meets_target`: freeze prompt v6/hash and authorize Task 7 only.
- If `below_target`, `incomplete`, or `pending`: preserve the honest bundle,
  stop before Task 7, keep Phase 5 gated, and request a new design decision.
  Do not automatically create v7, change context/model/runtime, or rerun gate2.

**Step 5: Commit the evidence locally**

```powershell
git add docs/evaluations/phase4_1/development/bench_phase4_1_dev_v6_gate2
git commit -m "docs: record Phase 4.1 planner v6 development benchmark"
```

---

### Task 7: Conditionally run the one-shot official 80-slot gate2

**Prerequisite:** Task 6 is verifiably `completed/meets_target`. Otherwise this
task is forbidden.

**Files:**

- Create only:
  `docs/evaluations/phase4_1/official/bench_official_s1_v11_planner6_gate2/`

**Step 1: Revalidate the frozen candidate**

Confirm the code SHA, prompt version/hash, dataset fingerprint, profile,
provider/model, and development bundle exactly match the accepted Task 6
candidate. Confirm the official destination does not exist.

**Step 2: Run the official held-out campaign once**

```powershell
python -m signal_diag.evaluation run-real `
  --campaign phase4.1-v6-official `
  --benchmark-id bench_official_s1_v11_planner6_gate2 `
  --output-dir docs/evaluations/phase4_1/official
```

No tuning or rerun is permitted after seeing held-out behavior.

**Step 3: Independently verify**

Require 80 unique scoreable Agent slots, 16 cases × 5, the deterministic
baseline artifacts, six-file checksums, schema validation, fingerprint and
aggregate recomputation, redaction, append-only refusal, and unchanged v4/v5
evidence.

**Step 4: Record the honest result**

- `completed/meets_target`: Phase 4.1 is eligible for final acceptance review.
- `completed/below_target`: keep the bundle, leave Phase 4.1 unaccepted, keep
  Phase 5 gated, and do not rerun or tune on this held-out set.

**Step 5: Commit locally**

```powershell
git add docs/evaluations/phase4_1/official/bench_official_s1_v11_planner6_gate2
git commit -m "docs: record Phase 4.1 planner v6 official benchmark"
```

---

### Task 8: Record final Phase 4.1 status

**Prerequisite:** Independent verification of Tasks 1–7.

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: the Phase 4.1 status/report document selected by the frozen contract

**Step 1: Re-run all quality gates**

Repeat Task 5 Step 3 from the final HEAD and verify both real-model bundles
against their checksums and recorded identities.

**Step 2: Record status without overclaiming**

Only if official gate2 is `completed/meets_target`, state “Phase 4.1 accepted;
Phase 5 remains gated pending written design.” Otherwise state the precise
blocking result and leave Phase 4.1/Phase 5 gated.

**Step 3: Commit locally**

```powershell
git add AGENTS.md docs/README.md docs
git commit -m "docs: record Phase 4.1 planner v6 acceptance status"
```

Do not push, merge, or begin Phase 5.

---

## T196–T200 mapping

```text
T196  Task 2: v4/v5 byte and route immutability; exact v6 version/hash
T197  Task 2: coherent v6 prompt policy and examples
T198  Task 3: real planner boundary, runtime routes, no leakage, same-run refs
T199  Task 4: additive v6 campaigns and exact development/official scheduling
T200  Task 5: cumulative T001–T200 and static/architecture/diff quality gates
```

## Mandatory stop/report conditions

Stop and report rather than broadening scope when:

- OQ-006 or the additive written contract is not approved;
- a frozen public contract appears to require modification;
- v4/v5 bytes, hashes, routes, or evidence cannot remain reproducible;
- a correct prompt-only implementation would require PlannerContext, Runtime,
  scorer, targets, model, or dataset changes;
- deterministic T001–T200 or static checks fail;
- real credentials are absent;
- development gate2 is not `completed/meets_target`;
- the official gate has already been executed or its destination exists;
- official gate2 is below target.

Every stop report must include the current branch/HEAD, `git status`, commands
run, exact failing metric/test, affected contract section, and confirmation
that held-out data and historical assets were not overwritten.
