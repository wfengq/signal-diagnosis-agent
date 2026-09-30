# S1 planner-ablation utility study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Wave 0 revised; Wave 1 definitions landed; Wave 2 harness authorized
2026-09-30 (`授权 planner-ablation contracts+harness`) and implemented under
`evaluation/planner_ablation/` + `app/planner_ablation_adapter.py`. **Do not
execute Wave 3+** (protocol seal with frozen cases, RealLLM) without a later
bounded grant.

**Date:** 2026-09-30

**Goal:** Build an additive, attributable development study
`study_s1_planner_ablation_dev_1` that compares HEAD `product_agent`
(`RealLLMPlanner`) to a truth-free `fixed_pipeline` under matched claim gates,
D037 entry, and deterministic report processing, without mutating sealed V0.2 /
v9.11 identities.

**Architecture:** Create study-owned modules under
`evaluation/planner_ablation/`. Historical
`ContextualFixedPipelineBaseline` and the v9.11 contextual campaign path stay
unchanged as reference candidates only. Product-slot execution goes through an
**app-level study adapter** that calls
`DiagnosisApplicationService.submit_contextual_wav` /
`wait_for_contextual_terminal`. Evaluation consumes an injected executor
protocol and study-owned result fields. It must not import app composition,
service, or report modules. Scoring and preregistration live under
`docs/evaluations/v0_3/planner_ablation/`.

**Tech Stack:** Python 3.11/3.12, Pydantic, pytest, existing
`signal_diag.evaluation.contextual` as a read-only reference for copy-forward
into the study package, `signal_diag.app` only via the app-level adapter,
ScriptedPlanner for harness-only dry-run, RealLLMPlanner only under a later
campaign grant.

**Spec:** `docs/superpowers/specs/2026-09-30-s1-planner-ablation-utility-study-design.md`
(D038 / OQ-019 study-shape approved)

## Global Constraints

- Frozen V0.2 §§1–64 stay byte-stable.
- Sealed v9.11 / V0.2 official bundles stay immutable.
- Historical `evaluation/contextual/baseline.py` and sealed campaign entry
  behavior stay unchanged. Study baseline is a new module.
- `ScriptedPlanner` never substitutes for scored `product_agent`.
- Missing credentials must stop, not fall back to Scripted.
- Demonstration thresholds (1% clipping / 5% THD) are not industry standards.
- Study results do not authorize product planner replacement or gate softening.
- `evaluation/planner_ablation` consumes an injected executor interface only.
  Real application-service composition and product-slot execution belong in an
  app-level study adapter. Evaluation must not import app composition, service,
  or report modules.
- Definitions precede implementation: Wave 1 is documentation only.
- No post-hoc sample, denominator, success-band, or retry changes after seeing
  scored results.
- Commit steps below mean "stage a commit message and stop" unless the operator
  has explicitly authorized commits for that wave.

## Authorization waves

| Wave | Contents | Requires |
|------|----------|----------|
| 0 | This revised plan document | Current revise grant |
| 1 | Additive CONTRACTS §19 + TEST_PLAN ID text only | Authorized and landed 2026-09-30 |
| 2 | Tests, study baseline/runner/scorer/sealing code, Scripted dry-run, full verification | Authorized and landed 2026-09-30 |
| 3 | Preregistration record + seal using already-reviewed Wave 2 sealing tools | Authorized 2026-09-30; additive seal under `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/protocol_seal/` |
| 4 | RealLLM `product_agent` campaign | Operator: `批准 RealLLM 战役` or equivalent |
| 5 | Result review write-up | After campaign artifacts |
| 6 | Product change (if any) | Separate behavior design + auth |

## File map

| File | Responsibility |
|------|----------------|
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` | Additive §19 (Wave 1 text): study identity, arms, matching matrix, report parity, scoring identity |
| `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | Register proposed T-CX276–T-CX288 (Wave 1 text; confirm IDs free at registration) |
| `src/signal_diag/evaluation/planner_ablation/baseline.py` | **New** study fixed-pipeline baseline with matched gates; do not mutate historical contextual baseline |
| `src/signal_diag/evaluation/planner_ablation/` | Study models, injected-executor runner, scoring, sealing wrappers |
| `src/signal_diag/app/planner_ablation_adapter.py` (create, Wave 2) | App-level adapter: contextual submit/wait, snapshot to study result fields |
| `src/signal_diag/app/context_guidance.py` | Unchanged templates; study scoring treats output as deterministic product behavior |
| `tests/evaluation/planner_ablation/` | Wave 2 only: matching, D037 entry, scoring, Scripted dry-run, seal offline tests |
| `docs/evaluations/v0_3/planner_ablation/` | Wave 3+ preregistration, seals, additive evidence |

Do **not** edit sealed trees under
`docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/`.
Do **not** change DSP thresholds or soften D037 harmonic gates.
Do **not** "modify historical baseline while keeping historical bytes unchanged".
Use a new study baseline file instead.

## Matching matrix (Wave 1 must define; Wave 2 must test)

Both frozen modes (`single_signal`, `paired_reference`) × claim families:

| Mode | Clipping support | Harmonic support | `no_supported_fault` | Valid `inconclusive` |
|------|------------------|------------------|----------------------|----------------------|
| `single_signal` | OQ-014 Option C: (a) valid `clipping_mechanism=true` Evidence + substantial legacy FAIL, or (b) valid `flat_top_detected=true` Evidence + same substantial FAIL when `clipping_mechanism` is false. Mechanism alone is not enough. | Absolute/harmonic description only; no unsupported harmonic `supported_fault` | Legacy clipping clean family + single no-fault rules as product path | Correct when evidence insufficient; may carry deterministic `context_guidance` |
| `paired_reference` | Contextual test family only (`test_clipping_mechanism` + test-side FAILs); no family mixing | Mode-specific contextual harmonic gate | Contextual test clean family (not legacy-only clean) | Correct when context invalid/insufficient per oracle |

Acceptance for "matched gates" requires positive and negative cases, valid
Evidence, mode-specific rule families, and same-run references on **both**
arms. Copy-forward of the historical baseline does not establish equivalence.

## Deterministic report parity (both arms)

Wave 2 must verify, for study-owned result fields derived without disguising
arm identity:

- guidance emission when §17 rules apply;
- guidance omission when they do not;
- reason codes and required-input names;
- scoring labels guidance as non-planner on every arm that carries it;
- fixed arm receives equivalent deterministic report processing (study-owned
  fields or shared pure helpers living outside app composition imports).

Never relabel a baseline run as `product_agent` to reuse a product report
helper.

## Proposed contract sketch (Wave 1, documentation only)

Append additive `## 19. Planner-ablation utility study (D038)` to
`CONTRACTS_V0_3_CONTEXTUAL.md` with these normative bullets:

```text
study_id: study_s1_planner_ablation_dev_1
evidence_root: docs/evaluations/v0_3/planner_ablation/
scored_arms: product_agent, fixed_pipeline
harness_only_arm: scripted_agent (optional; never scored vs product_agent)
modes_first_freeze: single_signal, paired_reference
single_signal_entry: submit_contextual_wav + wait_for_contextual_terminal only
matching_matrix: both modes × clipping/harmonic/no_supported_fault/valid inconclusive
report_parity: deterministic guidance emission/omission/reason/required_inputs on both arms
guidance_attribution: context_guidance is not planner skill
historical_files: contextual baseline/campaign unchanged; study modules are additive
scoring_identity: independent seal/scorer identity and denominator derivation
  (not a ban on the numeric values 17 or 6)
decision_language: planner_advantage | fixed_pipeline_dominance | insufficient_evidence
unmatched_comparison: cannot claim planner attribution
product_change: not authorized by study completion
```

## Proposed T-CX IDs (Wave 1 text; confirm free at registration)

| ID | Behavior |
|----|----------|
| T-CX276 | Study product slots use complete `submit_contextual_wav` keyword arguments and `wait_for_contextual_terminal`; legacy `submit_wav` / `wait_for_terminal` fail if called; real Scripted integration returns a contextual snapshot. |
| T-CX277 | Study `fixed_pipeline` `single_signal` clipping finish accepts OQ-014 Option C equivalently to product gates. |
| T-CX278 | Study `fixed_pipeline` paired clipping requires contextual test-family evidence; no family mixing. |
| T-CX279 | Deterministic report parity across both arms for guidance emission, omission, reason codes, and required inputs; guidance never scored as planner skill. |
| T-CX280 | Study seal/scorer rejects foreign study identities and wrong denominator **derivation**; does not forbid coincidental numeric equality with historical rates. |
| T-CX281 | `evaluation/planner_ablation` does not import app composition/service/report modules; product diagnosis unchanged for non-study callers. |
| T-CX282 | Scripted dry-run covers both modes for Scripted executor and fixed baseline (four executor×mode paths), with fail-on-call provider spy proving zero provider calls. |
| T-CX283 | Scorer keeps diagnosis-less terminals in completion/outcome denominators when required; claim-level metrics use claim populations; zero-denominator rules explicit. |
| T-CX284 | Offline labels `context_obtainable`, `context_valid`, `context_sufficient` never appear in execution-arm inputs. |
| T-CX285 | Upgrade success reports both full pre-fixed population and conditional-success denominators. |
| T-CX286 | Parameterized decision function: dominance allowed under equal 100% completion only when all other required conditions hold; negative cases forbid dominance/advantage. |
| T-CX287 | Full matching-matrix tests for both frozen modes (clipping, harmonic, no-fault, valid inconclusive) on study baseline vs product gates. |
| T-CX288 | Scored-input validator rejects Scripted/harness-only artifacts even if arm label is rewritten to `product_agent`. |

ID registration in Wave 1 is not evidence that the behavior has passed.

## Proposed protocol defaults for Wave 3 seal (numeric draft)

These numbers are **plan proposals for seal review**, not frozen until Wave 3
approval. Passing synthetic scorer tests does not freeze them.

| Item | Proposed default |
|------|------------------|
| Cases | 12 development WAVs (paired across arms/modes) |
| Modes | each case × `{single_signal, paired_reference}` |
| Scored slots | 12 × 2 modes × 2 arms = 48 slots (not 48 independent sources) |
| Arm order | all `product_agent` then all `fixed_pipeline` (arm-major) |
| LLM repetitions | 1 attempt per slot; no campaign retry; behavioral failure occupies denominator |
| Primary quality metric | causal exact-set accuracy on preregistered outcome population |
| Safety constraints | unsupported positive claim rate = 0 on claim population; evidence grounding = 1.0 on completed-diagnosis claims only |
| Non-inferiority | draft: fixed arm within 1/N of product on primary quality and usefulness; **N's unit must be frozen at seal** (source vs case vs mode-stratum vs scorable population); report mode-level bands so default-path regression cannot hide in aggregates |
| Material improvement | draft ≥20% relative latency or tool-action reduction on fixed arm under shared timing boundary |
| Useful terminal | `supported_fault` clipping, `supported_fault` harmonic under upgraded mode, or justified `no_supported_fault` |
| Stop rule | infrastructure failure stops campaign; behavioral failure continues |

### Seal blockers (must be approved before Wave 3)

Missing any item blocks sealing. Plan approval does not freeze these.

1. **Meaning of N.** Distinguish 48 slots from independent samples; define what
   `1/N` divides.
2. **Inference scope and uncertainty.** Frozen development-set description
   versus statistical inference; one run cannot measure multi-run model
   stability unless repetitions are sealed.
3. **Non-inferiority rationale.** "One case worse" needs an accepted loss
   rationale; mode-level reporting required.
4. **Safety and zero denominators.** No positive claims ≠ proven safety; no
   completed diagnosis ≠ perfect grounding.
5. **Full resource comparison.** Timing boundary, aggregation, failure and
   runtime-retry cost, allowed regressions on other metrics; campaign attempt
   versus model-internal retry kept separate.
6. **Evaluable population and identity.** Case/source list, oracle, context
   labels, input hashes, budgets, stop rules, scorer identity; behavior when
   no evaluable population exists.

---

### Task 0: Plan gate (Wave 0)

**Files:**
- Modify: `docs/superpowers/plans/2026-09-30-s1-planner-ablation-utility-study.md`

- [x] Write initial Wave 0 plan.
- [x] Revise after Codex review (`739e214` critique): service signatures, Wave
  boundaries, matching matrix, report parity, Scripted isolation, seal blockers.
- [ ] Stop for operator / strong-model re-review. Do not start Wave 1.

### Task 1: Contract and test-ID definitions (Wave 1, documentation only)

**Files:**
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` (append §19)
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` (register reviewed T-CX IDs)
- Modify: `docs/README.md` only if the entry path must cite §19

**Interfaces:**
- Consumes: D038 study-shape names and this plan's matching/report/seal text
- Produces: normative §19 text and T-CX acceptance matrix for Wave 2 to cite

- [x] **Step 1: Draft additive §19 and the test-ID acceptance matrix from D038.**
  Wave 1 edits documentation only. Do not create or execute Python tests.

- [x] **Step 2: Review matching obligations for both frozen modes**, including
  clipping, harmonic, `no_supported_fault`, valid inconclusive, same-run
  references, and equivalent deterministic report processing.

- [x] **Step 3: Register the reviewed test definitions.** Confirm T-CX276–T-CX288
  are unused after T-CX275. ID registration is not evidence that the
  corresponding behavior has passed.

- [x] **Step 4: Review the documentation diff and stop at the Wave 1 boundary.**
  Move `test_ids.py`, executable tests, and red/green runs to Wave 2.

- [x] **Step 5: Commit under the Wave 1 definitions grant.**

```bash
git add docs/CONTRACTS_V0_3_CONTEXTUAL.md docs/TEST_PLAN_V0_3_CONTEXTUAL.md
git commit -m "docs: add planner-ablation study contract §19 and T-CX IDs"
```

### Task 2: D037 entry via app adapter + injected executor (Wave 2)

**Files:**
- Create: `src/signal_diag/app/planner_ablation_adapter.py`
- Create: `src/signal_diag/evaluation/planner_ablation/executor.py` (protocol)
- Create: `src/signal_diag/evaluation/planner_ablation/runner.py`
- Test: `tests/evaluation/planner_ablation/test_d037_entry.py`
- Test: `tests/app/test_planner_ablation_adapter.py`

**Interfaces:**
- Consumes: `DiagnosisApplicationService.submit_contextual_wav`,
  `wait_for_contextual_terminal`
- Produces: app adapter implementing study `ProductSlotExecutor`; evaluation
  runner depends only on that protocol

Required contextual submit shape (keyword args must match service.py):

```python
submission = await service.submit_contextual_wav(
    test_bytes,
    test_filename="input.wav",
    mode="single_signal",
    reference_data=None,
    reference_filename=None,
    nominal_fundamental_hz=None,
    stimulus_kind=None,
    user_request="Diagnose supported S1 distortion conservatively.",
)
snapshot = await service.wait_for_contextual_terminal(submission.run_id)
```

Paired mode adds `reference_data` / `reference_filename` and keeps
`nominal_fundamental_hz=None`, `stimulus_kind=None`, same `user_request`.

- [ ] **Step 1: Write signature-constrained unit test** where calling
  `submit_wav` or `wait_for_terminal` fails immediately. Do not use a
  permissive `**kwargs` fake that fabricates guidance on the legacy waiter.

- [ ] **Step 2: Write real application-service integration test** using
  `ScriptedPlanner`, valid WAV fixtures, and the contextual terminal snapshot.
  Assert `context_guidance` comes from the real snapshot path when expected.

- [ ] **Step 3: Implement app adapter + evaluation protocol runner**

- [ ] **Step 4: Run focused tests green**

- [ ] **Step 5: Commit only with explicit authorization**

```bash
git commit -m "feat: planner-ablation D037 contextual entry via app adapter"
```

### Task 3: Study baseline matched finish gates (Wave 2)

**Files:**
- Create: `src/signal_diag/evaluation/planner_ablation/baseline.py`
- Test: `tests/evaluation/planner_ablation/test_matched_gates.py`

**Interfaces:**
- Consumes: same Tools / profiles as product; truth-free study request
- Produces: `PlannerAblationFixedPipelineBaseline.run(...)` covering the
  matching matrix rows for both frozen modes

- [ ] **Step 1: Write failing matrix tests** for clipping (including flat-top
  single_signal), harmonic, `no_supported_fault` (paired contextual clean
  family), and valid inconclusive. Include negative cases.

- [ ] **Step 2: Document that historical `ContextualFixedPipelineBaseline`
  remains unchanged and may still diverge; study baseline is authoritative for
  this study**

- [ ] **Step 3: Implement study baseline mapping; keep truth-free request surface**

- [ ] **Step 4: Green T-CX277, T-CX278, T-CX287-focused tests**

- [ ] **Step 5: Commit only with explicit authorization**

```bash
git commit -m "feat(evaluation): study baseline matched gates for planner ablation"
```

### Task 4: Deterministic report parity and scoring labels (Wave 2)

**Files:**
- Create: `src/signal_diag/evaluation/planner_ablation/scoring.py`
- Create: `src/signal_diag/evaluation/planner_ablation/labels.py`
- Create: `src/signal_diag/evaluation/planner_ablation/report_fields.py`
- Test: `tests/evaluation/planner_ablation/test_guidance_scoring.py`

**Interfaces:**
- Consumes: study-owned report fields from both arms (adapter maps product
  snapshots; baseline maps study fields without impersonating product_agent)
- Produces: parity checks + `planner_attributed=False` scoring treatment

- [ ] **Step 1: Failing tests for both-arm guidance emission, omission, reason
  codes, and required inputs**

- [ ] **Step 2: Failing tests that offline context labels are rejected on
  execution-arm inputs**

- [ ] **Step 3: Implement pure report-field helpers and scoring labels**

- [ ] **Step 4: Green T-CX279 / T-CX284 tests; commit only with authorization**

```bash
git commit -m "feat(evaluation): planner-ablation report parity and non-planner guidance"
```

### Task 5: Scripted / harness-only dry-run isolation (Wave 2)

**Files:**
- Create: `src/signal_diag/evaluation/planner_ablation/campaign.py`
- Create: `src/signal_diag/evaluation/planner_ablation/identity.py`
- Test: `tests/evaluation/planner_ablation/test_scripted_dry_run.py`

**Interfaces:**
- Consumes: Scripted-backed app adapter; study baseline; fail-on-call provider spy
- Produces: dry-run artifacts with `execution_identity=harness_only` and actual
  planner provenance; never scored campaign evidence

- [ ] **Step 1: Write failing dry-run covering four executor×mode paths**
  (Scripted × `{single_signal, paired_reference}` and fixed × same modes)

- [ ] **Step 2: Assert fail-on-call provider spy sees zero calls** (do not trust
  a summary counter alone)

- [ ] **Step 3: Assert scored-input validator rejects dry-run/Scripted artifacts
  even when arm label is rewritten to `product_agent` (T-CX288)**

- [ ] **Step 4: Implement campaign dry-run + identity guards**

- [ ] **Step 5: Commit only with authorization**

```bash
git commit -m "test(evaluation): planner-ablation harness-only dry-run isolation"
```

Synthetic scorer unit fixtures remain allowed in Task 6. They are not campaign
evidence and must not be published as study conclusions.

### Task 6: Independent scoring identity and decision language (Wave 2)

**Files:**
- Modify: `src/signal_diag/evaluation/planner_ablation/scoring.py`
- Create: `src/signal_diag/evaluation/planner_ablation/decision.py`
- Test: `tests/evaluation/planner_ablation/test_decision_language.py`

```python
class StudyConclusion(str, Enum):
    PLANNER_ADVANTAGE = "planner_advantage"
    FIXED_PIPELINE_DOMINANCE = "fixed_pipeline_dominance"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
```

- [ ] **Step 1: Write failing unit tests first (TDD)** for all three
  conclusions, negative cases that must not yield advantage or dominance
  (safety failure; unacceptable regression on another constrained metric;
  missing evaluable population; incomplete protocol; failed matching
  prerequisites; unmatched comparison), equal-completion dominance only when
  every other required condition holds (T-CX286), and identity/denominator
  derivation (T-CX280).

- [ ] **Step 2: Run the focused tests and confirm they fail for the missing
  decision function**

- [ ] **Step 3: Implement the parameterized decision function** that reads an
  approved protocol object. Do not hard-code draft `1/N` or `20%` as live
  acceptance gates inside library defaults used outside a sealed protocol.

- [ ] **Step 4: Re-run focused tests green**

- [ ] **Step 5: Commit only with authorization**

```bash
git commit -m "feat(evaluation): planner-ablation decision language and identity guards"
```

### Task 7: Sealing implementation + cumulative Wave 2 verification

**Files:**
- Create: `src/signal_diag/evaluation/planner_ablation/sealing.py`
- Test: `tests/evaluation/planner_ablation/test_seal.py` (offline tooling tests)

- [ ] Implement and test sealing helpers in Wave 2 (before any protocol-seal grant)
- [ ] Run: `pytest tests/evaluation/planner_ablation tests/app/test_planner_ablation_adapter.py -v`
- [ ] Run full pytest with zero required skip/xfail
- [ ] Run project Ruff and mypy on touched paths
- [ ] Run architecture tests
- [ ] Run `git diff --check` against the applicable baseline
- [ ] Run wheel smoke for packaging changes and the clean CPython 3.11/3.12
  matrix when this is a release gate (`AGENTS.md`)
- [ ] Confirm no RealLLM calls, no sealed-tree edits, no credentials in artifacts
- [ ] Stop for operator review before Wave 3

### Task 8: Preregistration and seal (Wave 3)

**Files:**
- Create: `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/preregistration.md`
- Create: seal directory + checksums using **already-reviewed** Wave 2 sealing code
- Create: `scripts/seal_planner_ablation_protocol.py`
- Create: `tests/evaluation/planner_ablation/test_protocol_seal_bundle.py`

Wave 3 uses already-reviewed sealing code. This grant does not authorize new
harness or sealing implementation.

- [x] Before sealing, approve every item in **Seal blockers** above
  (recorded in `preregistration.md`)
- [x] Freeze case list, arm order, populations, numeric bands, identities
  (10 dual-mode cases; 20 schedule keys; 40 scorable slots; gap `0.025`)
- [x] Verify seal with Wave 2 helpers and
  `study_input_from_verified_manifest` (foreign-identity rejection remains
  covered by Wave 2 sealing tests)
- [x] Commit additive seal under operator protocol-seal grant
- [x] Stop. Do not run RealLLM

### Task 9: RealLLM campaign (Wave 4) — separate grant only

Operator grant received: `批准 RealLLM 战役`.

- [x] Campaign runner added:
  `scripts/run_planner_ablation_realllm_campaign.py`
  (arm-major RealLLM then fixed; seal verify; no Scripted fallback;
  infrastructure failure stops campaign)
- [x] Preflight: seal identity, credentials present, RealLLMPlanner,
  `scripted_fallback=false`
- [x] Execute arm-major campaign once (40/40 terminal slots)
- [x] Persist additive artifacts under
  `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/agent_realllm_campaign_1/`
- [x] Do not rewrite historical bundles / protocol_seal
- [x] Emit `StudyConclusion` from sealed scorer:
  **`fixed_pipeline_dominance`**
  (quality/usefulness/completion tied; fixed ~99.8% faster; both safety_ok)
- [x] Stop for result review; do not change product planner

### Task 10: Result review (Wave 5)

- [ ] Write acceptance/review report citing sealed metrics and conclusion enum
- [ ] List matching caveats if any residual system-effect confounds remain
- [ ] Explicitly state that product changes remain unauthorized

## Self-review (Wave 0 revise)

1. **Spec coverage:** §4.1 matching → Matching matrix + Tasks 3–4 / T-CX287;
   D037 entry → Task 2 with real service signatures; report parity → Task 4 /
   T-CX279; Scripted isolation → Task 5 / T-CX288; decision language → Task 6;
   seal prerequisites → Seal blockers + Task 8; auth layers → waves table.
2. **Wave boundary:** Wave 1 has no Python tests; Wave 2 owns code/tests/sealing
   implementation; Wave 3 only seals.
3. **Codex P1:** `submit_contextual_wav` kwargs and
   `wait_for_contextual_terminal` corrected; permissive fake banned.

## Stop conditions

Wave 3 protocol seal is generated and verified under
`docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/`.
Stop before RealLLM campaign execution.

Suggested next operator phrase:

- Wave 4: `批准 RealLLM 战役`
