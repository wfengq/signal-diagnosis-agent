# S1 planner-ablation utility study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** plan written under documentation-only grant after D038. **Do not
execute Wave 1+** until the operator issues a bounded
contracts/harness grant. This document alone does not authorize CONTRACTS
edits, harness code, Scripted dry-run, RealLLM, commit of campaign evidence,
or product planner changes.

**Date:** 2026-09-30

**Goal:** Build an additive, attributable development study
`study_s1_planner_ablation_dev_1` that compares HEAD `product_agent`
(`RealLLMPlanner`) to a truth-free `fixed_pipeline` under matched claim gates,
D037 entry, and deterministic report processing, without mutating sealed V0.2 /
v9.11 identities.

**Architecture:** Reuse `evaluation/contextual/` as a candidate library behind a
new study identity and seal. Product diagnosis behavior stays on existing
`app` / `agent` paths. Matching gaps (baseline clipping predicate, campaign
`single_signal` entry, guidance report parity) are closed with additive study
adapters or additive product-compatible evaluation wiring, never by rewriting
historical baseline/campaign bytes. Scoring and preregistration live under
`docs/evaluations/v0_3/planner_ablation/`.

**Tech Stack:** Python 3.11/3.12, Pydantic, pytest, existing
`signal_diag.evaluation.contextual`, `signal_diag.app` contextual service,
ScriptedPlanner for dry-run only, RealLLMPlanner only under a later campaign
grant.

**Spec:** `docs/superpowers/specs/2026-09-30-s1-planner-ablation-utility-study-design.md`
(D038 / OQ-019 study-shape approved)

## Global Constraints

- Frozen V0.2 §§1–64 stay byte-stable.
- Sealed v9.11 / V0.2 official bundles stay immutable.
- `ScriptedPlanner` never substitutes for scored `product_agent`.
- Missing credentials must stop, not fall back to Scripted.
- Demonstration thresholds (1% clipping / 5% THD) are not industry standards.
- Study results do not authorize product planner replacement or gate softening.
- Evaluation must not invert dependency direction by importing app composition
  as a permanent product dependency. Study adapters stay evaluation-owned.
- Definitions precede implementation inside any contracts/harness grant.
- No post-hoc sample, denominator, success-band, or retry changes after seeing
  scored results.

## Authorization waves

| Wave | Contents | Requires |
|------|----------|----------|
| 0 | This plan document | Done (current grant) |
| 1 | Additive CONTRACTS + TEST_PLAN IDs (definitions only) | Operator: contracts/harness grant |
| 2 | Matching harness + Scripted dry-run tests | Same grant after Wave 1 lands, or follow-on |
| 3 | Preregistration record + seal (no RealLLM) | Operator: protocol-seal grant |
| 4 | RealLLM `product_agent` campaign | Operator: `批准 RealLLM 战役` or equivalent |
| 5 | Result review write-up | After campaign artifacts |
| 6 | Product change (if any) | Separate behavior design + auth |

## File map

| File | Responsibility |
|------|----------------|
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` | Additive §19 (proposed) study identity, arms, matching rules, scoring populations |
| `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | Register T-CX276–T-CX286 (proposed) |
| `src/signal_diag/evaluation/contextual/baseline.py` | Additive matched clipping/harmonic finish mapping for study arm, or parallel study baseline module if historical identity must stay untouched |
| `src/signal_diag/evaluation/planner_ablation/` (create) | Study-specific models, runner, scoring, sealing wrappers |
| `src/signal_diag/app/contextual_campaign.py` | Study path: `single_signal` via `submit_contextual_wav`; keep legacy v9.11 campaign path behavior for sealed studies |
| `src/signal_diag/app/context_guidance.py` | Unchanged templates; study scoring treats output as deterministic product behavior |
| `tests/evaluation/planner_ablation/` (create) | Matching, D037 entry, scoring population, Scripted dry-run tests |
| `docs/evaluations/v0_3/planner_ablation/` (create) | Preregistration, seals, additive evidence |
| `docs/DECISIONS.md` / design status | Record wave completions; never auto-authorize product change |

Do **not** edit sealed trees under
`docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/`.
Do **not** change DSP thresholds or soften D037 harmonic gates.

## Proposed contract sketch (Wave 1)

Append additive `## 19. Planner-ablation utility study (D038)` to
`CONTRACTS_V0_3_CONTEXTUAL.md` with these normative bullets:

```text
study_id: study_s1_planner_ablation_dev_1
evidence_root: docs/evaluations/v0_3/planner_ablation/
scored_arms: product_agent, fixed_pipeline
harness_only_arm: scripted_agent (optional; never scored vs product_agent)
modes_first_freeze: single_signal, paired_reference
single_signal_entry: submit_contextual_wav / contextual single_signal only
matching_required: claim gates, D037 entry, deterministic report processing
guidance_attribution: context_guidance is not planner skill
historical_reuse: ContextualFixedPipelineBaseline and v9.11 campaign are candidates only
scoring_identity: independent; reject sealed v9.11 seal/denominators
decision_language: planner_advantage | fixed_pipeline_dominance | insufficient_evidence
product_change: not authorized by study completion
```

## Proposed T-CX IDs (Wave 1)

| ID | Behavior |
|----|----------|
| T-CX276 | Planner-ablation `single_signal` slots submit via contextual `single_signal` (`submit_contextual_wav`), not legacy `submit_wav`. |
| T-CX277 | Study `fixed_pipeline` `single_signal` clipping finish accepts OQ-014 Option C (`flat_top_detected` path) equivalently to product gates. |
| T-CX278 | Study `fixed_pipeline` paired clipping still requires contextual test-family evidence; no family mixing. |
| T-CX279 | Completed study `single_signal` inconclusive attaches deterministic `context_guidance` on the product arm path; scoring labels guidance as non-planner. |
| T-CX280 | Study runner rejects sealed v9.11 seal identity and fixed 17/6 denominators as this study's scoring identity. |
| T-CX281 | Architecture: `evaluation/planner_ablation` does not import app composition; product diagnosis behavior unchanged for non-study callers. |
| T-CX282 | Scripted dry-run executes one `single_signal` and one `paired_reference` slot end-to-end without provider calls. |
| T-CX283 | Scorer keeps diagnosis-less terminals in completion/outcome denominators when preregistration requires it; claim-level metrics use claim populations. |
| T-CX284 | Offline labels `context_obtainable`, `context_valid`, `context_sufficient` never appear in execution-arm inputs. |
| T-CX285 | Upgrade success reports both full pre-fixed population and conditional-success denominators. |
| T-CX286 | Equal 100% completion still allows `fixed_pipeline_dominance` when quality/safety/usefulness are non-inferior and a preregistered cost/experience metric improves materially. |

## Proposed protocol defaults for Wave 3 seal (numeric draft)

These numbers are **plan proposals for seal review**, not frozen until Wave 3
approval. Do not treat them as live gates before the seal.

| Item | Proposed default |
|------|------------------|
| Cases | 12 development WAVs (paired across arms/modes) |
| Modes | each case × `{single_signal, paired_reference}` |
| Scored slots | 12 × 2 modes × 2 arms = 48 |
| Arm order | all `product_agent` then all `fixed_pipeline` (arm-major) |
| LLM repetitions | 1 attempt per slot; no campaign retry; behavioral failure occupies denominator |
| Primary quality metric | causal exact-set accuracy on preregistered outcome population |
| Safety constraints | unsupported positive claim rate = 0 on claim population; evidence grounding = 1.0 on completed-diagnosis claims |
| Non-inferiority | fixed arm within 1/N of product on primary quality and on usefulness; completion non-inferior |
| Material improvement | ≥20% relative latency reduction or ≥20% relative tool-action reduction on fixed arm, measured with shared timing boundary |
| Useful terminal | `supported_fault` clipping, `supported_fault` harmonic under upgraded mode, or justified `no_supported_fault` |
| Stop rule | infrastructure failure stops campaign; behavioral failure continues |

---

### Task 0: Plan gate (Wave 0) — current grant

**Files:**
- Create: `docs/superpowers/plans/2026-09-30-s1-planner-ablation-utility-study.md`
- Modify: design status / plan pointer only

- [x] Write this plan under the documentation-only grant.
- [ ] Stop. Do not edit CONTRACTS, TEST_PLAN, or product/evaluation code until
  Wave 1 is authorized.

### Task 1: Contract and test-ID definitions (Wave 1)

**Files:**
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` (append §19)
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` (register T-CX276–T-CX286)
- Modify: `docs/README.md` index note if §19 is referenced from the entry path

**Interfaces:**
- Consumes: D038 study-shape names (`study_s1_planner_ablation_dev_1`, arms, modes)
- Produces: normative §19 text and T-CX ID table for Wave 2 tests to cite

- [ ] **Step 1: Write failing doc-linked architecture/test stubs that reference T-CX276–T-CX286 by ID string in `tests/evaluation/planner_ablation/test_ids.py`**

```python
REQUIRED_PLANNER_ABLATION_TEST_IDS = (
    "T-CX276",
    "T-CX277",
    "T-CX278",
    "T-CX279",
    "T-CX280",
    "T-CX281",
    "T-CX282",
    "T-CX283",
    "T-CX284",
    "T-CX285",
    "T-CX286",
)

def test_test_plan_registers_planner_ablation_ids() -> None:
    text = Path("docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text(encoding="utf-8")
    for test_id in REQUIRED_PLANNER_ABLATION_TEST_IDS:
        assert test_id in text
```

- [ ] **Step 2: Run the stub and confirm it fails because IDs are absent**

Run: `pytest tests/evaluation/planner_ablation/test_ids.py -v`
Expected: FAIL with missing `T-CX276` (or collection fail if path absent; create the test file first so the assertion fails)

- [ ] **Step 3: Append §19 and the T-CX table exactly as sketched above**

- [ ] **Step 4: Re-run Step 2 green**

- [ ] **Step 5: Commit**

```bash
git add docs/CONTRACTS_V0_3_CONTEXTUAL.md docs/TEST_PLAN_V0_3_CONTEXTUAL.md \
  tests/evaluation/planner_ablation/test_ids.py
git commit -m "docs: add planner-ablation study contract §19 and T-CX276–T-CX286"
```

### Task 2: D037 entry matching for study runner (Wave 2)

**Files:**
- Create: `src/signal_diag/evaluation/planner_ablation/runner.py`
- Modify: `src/signal_diag/app/contextual_campaign.py` only if a study-specific
  executor hook is required; prefer a study runner that calls
  `DiagnosisApplicationService.submit_contextual_wav` directly
- Test: `tests/evaluation/planner_ablation/test_d037_entry.py`

**Interfaces:**
- Consumes: `DiagnosisApplicationService.submit_contextual_wav`,
  `wait_for_terminal`
- Produces: `run_planner_ablation_product_slot(service, slot) -> snapshot`
  where `slot.mode == "single_signal"` never calls `submit_wav`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_single_signal_slot_uses_contextual_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeService:
        async def submit_wav(self, *args: object, **kwargs: object) -> object:
            calls.append("submit_wav")
            raise AssertionError("legacy submit_wav must not run for study single_signal")

        async def submit_contextual_wav(self, *args: object, **kwargs: object) -> object:
            calls.append("submit_contextual_wav")
            return SimpleNamespace(run_id="run_test")

        async def wait_for_terminal(self, run_id: str) -> object:
            return SimpleNamespace(run_id=run_id, mode="single_signal", context_guidance=object())

    slot = SimpleNamespace(mode="single_signal", test_wav_path=Path("x.wav"), reference_wav_path=None)
    await run_planner_ablation_product_slot(FakeService(), slot, test_bytes=b"RIFF")
    assert calls == ["submit_contextual_wav"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/evaluation/planner_ablation/test_d037_entry.py::test_single_signal_slot_uses_contextual_submit -v`
Expected: FAIL (`run_planner_ablation_product_slot` missing)

- [ ] **Step 3: Implement minimal study runner function**

```python
async def run_planner_ablation_product_slot(service, slot, *, test_bytes: bytes, reference_bytes: bytes | None = None):
    if slot.mode == "single_signal":
        submission = await service.submit_contextual_wav(
            test_bytes,
            test_filename="input.wav",
            mode="single_signal",
        )
    elif slot.mode == "paired_reference":
        if reference_bytes is None:
            raise ValueError("paired_reference requires reference_bytes")
        submission = await service.submit_contextual_wav(
            test_bytes,
            test_filename="input.wav",
            mode="paired_reference",
            reference_data=reference_bytes,
            reference_filename="reference.wav",
        )
    else:
        raise ValueError(f"unsupported study mode: {slot.mode}")
    return await service.wait_for_terminal(submission.run_id)
```

- [ ] **Step 4: Run test green; add regression that legacy
  `ContextualCampaignExecutor` sealed path remains unchanged for v9.11 callers**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(evaluation): planner-ablation single_signal uses D037 contextual entry"
```

### Task 3: Matched fixed_pipeline finish gates (Wave 2)

**Files:**
- Prefer Create: `src/signal_diag/evaluation/planner_ablation/baseline.py`
  (copy-forward from `ContextualFixedPipelineBaseline`, then align gates)
- Or Modify: `src/signal_diag/evaluation/contextual/baseline.py` only if an
  additive, identity-preserving branch can keep historical v9.11 baseline
  bytes/behavior unchanged for sealed studies
- Test: `tests/evaluation/planner_ablation/test_matched_gates.py`

**Interfaces:**
- Consumes: same Tools / profiles as product; `StimulusContext`
- Produces: `PlannerAblationFixedPipelineBaseline.run(request) -> BaselineRunResult`
  with `single_signal` clipping support when either:
  - valid `clipping_mechanism=true` + substantial legacy FAIL; or
  - valid `flat_top_detected=true` + substantial legacy FAIL when mechanism is false
  Paired mode still requires `test_clipping_mechanism` family.

- [ ] **Step 1: Write failing fixture test for sub-full-scale flat-top single_signal**

```python
@pytest.mark.asyncio
async def test_study_baseline_supports_flat_top_single_signal_clipping() -> None:
    result = await run_study_baseline_on_flat_top_fixture(mode="single_signal")
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert any(claim.fault_type == "clipping" for claim in result.diagnosis.claims)
```

- [ ] **Step 2: Confirm historical `ContextualFixedPipelineBaseline` still
  fails/omits that path (documents the mismatch being fixed only for the study arm)**

- [ ] **Step 3: Implement study baseline mapping; keep truth-free request surface**

- [ ] **Step 4: Add paired-mode family-mixing rejection test (T-CX278)**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(evaluation): match planner-ablation fixed_pipeline single_signal clipping gates"
```

### Task 4: Deterministic guidance parity and scoring labels (Wave 2)

**Files:**
- Create: `src/signal_diag/evaluation/planner_ablation/scoring.py`
- Create: `src/signal_diag/evaluation/planner_ablation/labels.py`
- Test: `tests/evaluation/planner_ablation/test_guidance_scoring.py`

**Interfaces:**
- Consumes: product snapshot `context_guidance`; offline label records
- Produces:
  - `GuidanceScoreFields(present: bool, names_required_inputs: bool, planner_attributed: Literal[False])`
  - `OfflineContextLabels(obtainable: bool, valid: bool, sufficient: bool)` excluded from arm inputs

- [ ] **Step 1: Failing test that product inconclusive single_signal yields
  guidance present with `planner_attributed is False`**

- [ ] **Step 2: Failing test that offline labels are rejected if attached to
  `ContextualBaselineRequest` / product execution input models**

- [ ] **Step 3: Implement scoring helpers and label boundary checks**

- [ ] **Step 4: Green tests; commit**

```bash
git commit -m "feat(evaluation): score context_guidance as non-planner in ablation study"
```

### Task 5: Scripted dry-run harness acceptance (Wave 2)

**Files:**
- Create: `src/signal_diag/evaluation/planner_ablation/campaign.py`
- Test: `tests/evaluation/planner_ablation/test_scripted_dry_run.py`

**Interfaces:**
- Consumes: `ScriptedPlanner` via app composition test double already used in
  D037 tests; study runner from Task 2; study baseline from Task 3
- Produces: dry-run artifact directory under `tmp_path` with two slots and zero
  provider calls

- [ ] **Step 1: Write failing dry-run test (T-CX282)**

```python
@pytest.mark.asyncio
async def test_scripted_dry_run_two_slots(tmp_path: Path) -> None:
    summary = await run_planner_ablation_scripted_dry_run(output_dir=tmp_path)
    assert summary.provider_calls == 0
    assert summary.slot_count == 2
    assert {slot.mode for slot in summary.slots} == {"single_signal", "paired_reference"}
```

- [ ] **Step 2: Implement minimal campaign loop for Scripted only**

- [ ] **Step 3: Assert architecture test T-CX281 still passes**

- [ ] **Step 4: Commit**

```bash
git commit -m "test(evaluation): Scripted dry-run for planner-ablation harness"
```

### Task 6: Independent scoring identity and decision language (Wave 2)

**Files:**
- Modify: `src/signal_diag/evaluation/planner_ablation/scoring.py`
- Test: `tests/evaluation/planner_ablation/test_decision_language.py`

- [ ] **Step 1: Reject v9.11 seal id and hard-coded 17/6 denominators (T-CX280)**

- [ ] **Step 2: Implement conclusion enum**

```python
class StudyConclusion(str, Enum):
    PLANNER_ADVANTAGE = "planner_advantage"
    FIXED_PIPELINE_DOMINANCE = "fixed_pipeline_dominance"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
```

- [ ] **Step 3: Unit-test T-CX286: both arms 100% completion, equal quality,
  fixed latency materially better => `FIXED_PIPELINE_DOMINANCE`**

- [ ] **Step 4: Unit-test that equal metrics with no material cost/experience
  delta => `INSUFFICIENT_EVIDENCE`, not equivalence**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(evaluation): planner-ablation decision language and identity guards"
```

### Task 7: Cumulative Wave 2 verification

- [ ] Run:
  `pytest tests/evaluation/planner_ablation -v`
- [ ] Run focused architecture tests touching evaluation/app boundaries
- [ ] Run `ruff` and `mypy` on touched paths
- [ ] Run `git diff --check` against the Wave 1 base
- [ ] Confirm no RealLLM calls, no sealed-tree edits, no provider credentials in artifacts
- [ ] Stop for operator review before Wave 3

### Task 8: Preregistration and seal (Wave 3)

**Files:**
- Create: `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/preregistration.md`
- Create: seal directory + checksums via existing sealing helpers adapted for the study
- Test: `tests/evaluation/planner_ablation/test_seal.py`

- [ ] Freeze case list, arm order, populations, numeric bands from the draft
  table above (or operator-amended values)
- [ ] Freeze code identity digests (product tree, prompt, harness, study runner)
- [ ] Verify seal rejects mutation of sealed v9.11 paths
- [ ] Commit additive seal only
- [ ] Stop. Do not run RealLLM

### Task 9: RealLLM campaign (Wave 4) — separate grant only

- [ ] Preflight: seal identity, credentials present, no Scripted fallback
- [ ] Execute arm-major campaign once
- [ ] Persist additive artifacts under
  `docs/evaluations/v0_3/planner_ablation/...`
- [ ] Do not rewrite historical bundles
- [ ] Emit `StudyConclusion` from sealed scorer
- [ ] Stop for result review; do not change product planner

### Task 10: Result review (Wave 5)

- [ ] Write acceptance/review report citing sealed metrics and conclusion enum
- [ ] List matching caveats if any residual system-effect confounds remain
- [ ] Explicitly state that product changes remain unauthorized

## Self-review (Wave 0)

1. **Spec coverage:** §4.1 matching → Tasks 2–4; §5 preregistration → Task 8;
   §6 metrics / guidance attribution → Tasks 4 and 6; §7 decision language →
   Task 6; §8 auth layers → Authorization waves table; D037 entry → Task 2;
   historical identity → Tasks 2, 6, 8.
2. **Placeholder scan:** numeric bands are labeled "proposed for Wave 3 seal",
   not silent TBD.
3. **Type consistency:** study runner / baseline / conclusion enum names are
   stable across tasks.

## Stop conditions

After Wave 0 (this commit): update PR and wait.

Next operator grant phrases (suggested):

- Wave 1–2: `授权 planner-ablation contracts+harness`
- Wave 3: `授权 planner-ablation protocol seal`
- Wave 4: `批准 RealLLM 战役`
