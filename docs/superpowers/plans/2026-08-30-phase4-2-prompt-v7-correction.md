# Phase 4.2 Prompt v7 Correction Implementation Plan

> **For implementation agents:** Use `superpowers:executing-plans` in a
> dedicated implementation session. For every code task, also use
> `superpowers:test-driven-development`; before completion claims, use
> `superpowers:verification-before-completion`. Repository specifications and
> `AGENTS.md` take precedence.

**Goal:** Calibrate the two remaining v6 development misses with one coherent
v7 prompt and a new development verification identity, while preserving all
Phase 1–4 / v4 / v5 / v6 assets and keeping v1.1.0 held-out sealed until the
new development gate meets target.

**Architecture:** Keep `RealLLMPlanner` as the product planner. Make v7 one
coherent versioned prompt, not a v6 appendix. Preserve v4/v5/v6 through private
compatibility planners and unchanged campaign choices. Reuse Runtime, DSP,
rules, knowledge, dataset, scorer, and report models. Add only versioned
prompt/config/campaign identities, the official identity-complete bundle check,
and deterministic tests. No runtime action is forced and no evaluation truth
enters the planner context.

**Baseline:** `aefccba` on `phase4-evaluation-design`.

**Status:** Design drafted 2026-08-30; implementation is **not** authorized
until OQ-007, §52, T201–T205, and D023 are approved.

**Design authority:**
`docs/superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md`.

---

## Global constraints

- Do not modify product code before §52, TEST_PLAN §25/T201–T205, and D023 are
  approved.
- Do not rewrite, delete, or redirect v4/v5/v6 prompts, hashes, builders, CLI
  campaign choices, or committed evaluation bundles.
- Do not overwrite
  `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/` or
  `docs/evaluations/phase4_1/development/bench_phase4_1_dev_v6_gate2/`.
- Do not rerun `bench_phase4_1_dev_v6_gate2` and treat it as a new pass.
- Do not run or inspect the v1.1.0 held-out split before the v7 development
  gate is `completed/meets_target`.
- Do not change public Planner, Runtime, DSP, Tool, Rule, Knowledge,
  evaluation, scoring, target-band, or reporting contracts.
- Do not force Tool, rule, or knowledge actions in the controller.
- Do not lower `evidence_grounding_min` or `unsupported_claim_rate_max`.
- Do not change provider/model (`deepseek` / `deepseek-v4-flash`).
- Preserve `build/` and any unrelated user changes. Do not push or merge.

## Expected files

```text
docs/
├── CONTRACTS_V0_2.md                         # Task 1: add §52 after approval
├── TEST_PLAN_V0_2.md                         # Task 1: add §25 T201–T205
├── DECISIONS.md                              # Task 1: add D023
├── OPEN_QUESTIONS.md                         # OQ-007
├── README.md
├── AGENTS.md
└── superpowers/
    ├── specs/2026-08-30-phase4-2-prompt-v7-correction-design.md
    └── plans/2026-08-30-phase4-2-prompt-v7-correction.md
src/signal_diag/
├── agent/
│   ├── prompts.py
│   └── planner.py
└── evaluation/
    ├── __main__.py
    └── runner.py
tests/
├── agent/
│   ├── test_phase4_2_prompt_v7.py
│   └── test_phase4_2_v7_runtime.py
├── evaluation/test_phase4_2_v7_runner.py
└── test_architecture_boundaries.py
docs/evaluations/phase4_1/
├── development/bench_phase4_1_dev_v7_gate3/   # conditional Task 6
└── official/bench_official_s1_v11_planner7_gate3/  # conditional Task 7
```

---

### Task 1: Freeze the additive v7 contract after approval

**Files:**

- Modify: `docs/CONTRACTS_V0_2.md`
- Modify: `docs/TEST_PLAN_V0_2.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/OPEN_QUESTIONS.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`

**Step 1: Confirm approval**

Stop if the user has not approved OQ-007, §52, T201–T205, and D023.

**Step 2: Record §52 without altering §§50–§51**

Add Phase 4.2 additive v7 correction text: preserve v4/v5/v6; one coherent
`v0.2-s1-planner-7`; official identity-complete bundle requirement; new
development/official IDs; development-before-held-out; unchanged target bands.

**Step 3: Freeze T201–T205**

- T201: v4/v5/v6 immutability plus exact v7 identity/hash
- T202: inconclusive purity, blocking first observation, clipping vs independent harmonic
- T203: product-boundary traces, no leakage, no v6 regression
- T204: additive campaigns and identity-complete official preflight
- T205: cumulative T001–T205 against baseline `aefccba`

**Step 4: Record D023 and resolve OQ-007**

**Step 5: Commit locally**

```powershell
git add docs/CONTRACTS_V0_2.md docs/TEST_PLAN_V0_2.md docs/DECISIONS.md `
  docs/OPEN_QUESTIONS.md docs/README.md AGENTS.md `
  docs/superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md `
  docs/superpowers/plans/2026-08-30-phase4-2-prompt-v7-correction.md
git commit -m "docs: freeze Phase 4.2 prompt v7 correction gate"
```

---

### Task 2: Add coherent v7 prompt and preserve legacy identities

**Files:**

- Modify: `src/signal_diag/agent/prompts.py`
- Modify: `src/signal_diag/agent/planner.py`
- Create: `tests/agent/test_phase4_2_prompt_v7.py`

Follow TDD. Public `RealLLMPlanner` selects v7. Private planners keep v4/v5/v6
bytes and historical campaigns. v7 is one full prompt, not an appendix.

Prompt must encode §5 of the design spec, especially inconclusive citation
purity and clipping-induced harmonics not becoming a second cause, without
regressing combined dual-fault coverage.

Commit: `feat(agent): add coherent Phase 4.2 planner v7 prompt`

---

### Task 3: Enforce T203 runtime semantics

**Files:**

- Create: `tests/agent/test_phase4_2_v7_runtime.py`

Fake transport through real `RealLLMPlanner` and real Runtime. Cover noise
inconclusive purity, clipping-strong stop-after-clipping, combined dual claims,
harmonic-boundary dual truth, and no leakage.

Commit: `test(agent): enforce planner v7 runtime semantics`

---

### Task 4: Add additive v7 campaigns and identity-complete official gate

**Files:**

- Create: `tests/evaluation/test_phase4_2_v7_runner.py`
- Modify: `src/signal_diag/evaluation/runner.py`
- Modify: `src/signal_diag/evaluation/__main__.py`

Keep existing campaign choices on v5/v6. Add:

- `phase4.1-v7-development` → `bench_phase4_1_dev_v7_gate3` (8 × 5)
- `phase4.1-v7-official` → `bench_official_s1_v11_planner7_gate3` (16 × 5)

Official requires a development bundle with `completed/meets_target` **and**
`benchmark_manifest.json` identity fields matching the candidate. Missing
manifest is `invalid_configuration`, never an early return.

Harden the shared official-bundle helper so v6 official cannot skip identity
either. Do not run held-out.

Commit: `feat(evaluation): add additive planner v7 campaigns`

---

### Task 5: Enforce T205 and obtain deterministic review

**Files:**

- Modify: `tests/test_architecture_boundaries.py`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`

Add T205 against baseline `aefccba`. Run focused then full:

```powershell
python -m pytest -q -rxXs -p no:cacheprovider --basetemp .pytest_cache/phase4-2-v7
python -m ruff check --no-cache src tests scripts
python -m mypy --no-incremental src
git diff --check aefccba..HEAD
```

Expected: T001–T205, 0 required skip/xfail, ruff/mypy/diff-check clean.

Commit: `test(evaluation): enforce Phase 4.2 planner v7 gate`

---

### Task 6: Run and freeze the 40-slot v7 development gate3

**Prerequisite:** Task 5 independently green and real DeepSeek credentials
exist. Destination must not exist. Do not reuse gate2.

```powershell
python -m signal_diag.evaluation run-real `
  --campaign phase4.1-v7-development `
  --benchmark-id bench_phase4_1_dev_v7_gate3 `
  --output-dir docs/evaluations/phase4_1/development
```

Verify 40 unique scoreable Agent slots, checksums, and that v5 gate1 and v6
gate2 remain byte-identical.

Stop before Task 7 unless `completed/meets_target`.

Commit: `docs: record Phase 4.2 planner v7 development benchmark`

---

### Task 7: Conditionally run the one-shot official 80-slot gate3

**Prerequisite:** Task 6 is verifiably `completed/meets_target`. Otherwise
forbidden.

```powershell
python -m signal_diag.evaluation run-real `
  --campaign phase4.1-v7-official `
  --benchmark-id bench_official_s1_v11_planner7_gate3 `
  --output-dir docs/evaluations/phase4_1/official
```

Once only. If `below_target`, keep honest; no retune/rerun of the same
held-out.

---

### Task 8: Record Phase 4.2 status

Update `AGENTS.md` and `docs/README.md` with the actual statuses. Distinguish
report `harness_status=pending` from repository deterministic acceptance. Do
not push, merge, or begin Phase 5.

Commit: `docs: record Phase 4.2 planner v7 acceptance status`

---

## T201–T205 mapping

```text
T201  Task 2: v4/v5/v6 byte and route immutability; exact v7 version/hash
T202  Task 2: coherent v7 inconclusive purity and clipping/harmonic independence
T203  Task 3: real planner boundary, runtime routes, no leakage, no v6 regression
T204  Task 4: additive v7 campaigns and identity-complete official preflight
T205  Task 5: cumulative T001–T205 and static/architecture/diff quality gates
```

## Mandatory stop/report conditions

Stop and report rather than broadening scope when:

- OQ-007 or the additive written contract is not approved;
- a frozen public contract appears to require modification;
- v4/v5/v6 bytes, hashes, routes, or evidence cannot remain reproducible;
- a correct prompt-only implementation would require PlannerContext, Runtime,
  scorer, targets, model, or dataset changes;
- deterministic T001–T205 or static checks fail;
- real credentials are absent;
- development gate3 is not `completed/meets_target`;
- the official gate has already been executed or its destination exists;
- official gate3 is below target.
