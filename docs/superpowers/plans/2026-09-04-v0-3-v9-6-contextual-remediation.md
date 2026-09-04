# V0.3 v9.6 Contextual Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed v9.6 contextual planner/runtime policy that routes harmonic analysis through the contextual Tool in contextual modes and reliably closes existing Evidence requirements without weakening clipping behavior.

**Architecture:** Preserve the v9.5 prompt and causal behavior as historical identities. Add `v9_6_contextual` as an opt-in policy, reject incompatible ordinary harmonic Tool calls before execution, and wire a narrowly revised v9.6 prompt at the product composition root. Reuse all existing deterministic finish gates; do not change DSP, profiles, data, or scoring.

**Tech Stack:** Python 3.11/3.12, Pydantic v2, pytest, Ruff, mypy, existing deterministic runtime and OpenAI-compatible `RealLLMPlanner` boundary.

**Spec:** `docs/superpowers/specs/2026-09-04-v0-3-v9-6-contextual-remediation-design.md`

## Global Constraints

- Work on `codex/v0.2-real-world-validation`.
- Do not modify V0.2 official/Demo bundles, v8.1, v9.4, v9.5 prompt bytes, profile thresholds, scoring identities, or tag `v0.2.0`.
- Preserve commit `95bb19122815f2348cfda853b0e7e95c88e037e4` and cleanup commit `acca1ef4e9444cfcae40b22d32f80fd8cc5b056c` as append-only Task 13 evidence.
- Use TDD: demonstrate each new test failing for the intended reason, implement the smallest change, and rerun focused tests.
- Do not access `docs/evaluations/v0_3/validation/`, run a real model, download data, alter manifests/WAVs, or use `ScriptedPlanner` as a product fallback.
- Do not add dependencies or perform unrelated refactors.
- The existing untracked `docs/evaluations/v0_2_external_wav/investigation_report_2026-09-02.md` and `docs/evaluations/v0_3/validation/` are user-owned and excluded from every commit.
- Commit steps require explicit user authorization. Without it, leave changes uncommitted and stop at the requested review gate.

## File Structure

Documentation and registry changes:

- `docs/CONTRACTS_V0_3_CONTEXTUAL.md`: append the v9.6 policy and compatibility contract.
- `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`: allocate T-CX146–T-CX165.
- `docs/evaluations/v0_3/contextual/V9_6_CODE_ACCEPTANCE_REPORT.md`: record frozen identities and offline gate results after implementation.

Product changes:

- `src/signal_diag/agent/diagnosis.py`: add `v9_6_contextual` identity while reusing v9.5 finish gates.
- `src/signal_diag/agent/runtime.py`: reject the ordinary harmonic Tool in contextual modes only under v9.6.
- `src/signal_diag/agent/prompts_v03.py`: add immutable `_S1_PROMPT_V9_6` derived from v9.5.
- `src/signal_diag/agent/planner.py`: wire `RealLLMPlanner` and `PROMPT_VERSION` to v9.6.
- `src/signal_diag/app/composition.py`: wire the product causal policy to `v9_6_contextual`.

Test changes:

- `tests/evaluation/external/test_v03_contextual_preservation.py`: pin v9.5 prompt and Task 13 evidence identities.
- `tests/agent/test_v03_contextual_routing_v9_6.py`: new mode-aware routing tests.
- `tests/agent/test_v03_prompt_v9_6.py`: new prompt/composition identity and semantic tests.
- `tests/agent/test_v03_v9_6_regressions.py`: deterministic reproductions of recorded failure families and clipping preservation.
- Existing composition assertions in `tests/app/test_service.py` and `tests/app/test_contextual_service.py`: update only expectations for the active product policy.

---

### Task 1: Register and preserve the v9.6 contract

**Files:**
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md`
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`
- Modify: `tests/evaluation/external/test_v03_contextual_preservation.py`

**Interfaces:**
- Consumes: frozen v9.5 SHA `a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02` and preserved Task 13 commits `95bb191` / `acca1ef`.
- Produces: normative `v9_6_contextual` contract and T-CX146–T-CX165 ownership.

- [ ] **Step 1: Add failing preservation assertions T-CX146–T-CX148**

Extend the existing preservation test with literal SHA-256 identities for the
v9.5 prompt and selected small Task 13 control artifacts. Pin
`AUDIT_CORRECTION.md`, both status files, the diagnostic `preflight.json`,
`disposition.json`, and `run_summary.json`; do not pin every multi-thousand-line
trace independently.

```python
def test_t_cx146_v9_5_prompt_remains_frozen() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_5.system_prompt.encode("utf-8")).hexdigest()
    assert digest == "a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02"


def test_t_cx147_task13_control_artifacts_are_preserved() -> None:
    for relative, expected_sha256 in TASK13_CONTROL_SHA256.items():
        assert sha256_path(REPO_ROOT / relative) == expected_sha256


def test_t_cx148_v9_6_ids_are_registered_once() -> None:
    registry = (REPO_ROOT / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    for number in range(146, 166):
        assert registry.count(f"T-CX{number}") >= 1
```

Before writing `TASK13_CONTROL_SHA256`, calculate each digest from the committed
`acca1ef` tree with `Get-FileHash`; paste the resulting literal values into the
test. Never derive expected hashes from the files during the assertion.

- [ ] **Step 2: Run the new preservation tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/external/test_v03_contextual_preservation.py -k "t_cx146 or t_cx147 or t_cx148" -v
```

Expected: FAIL because the new registry/contract entries and v9.6 identity do
not exist yet. Existing preservation tests must remain green when run without
the new assertions.

- [ ] **Step 3: Append the contract and test registry**

Add `v9_6_contextual` as an additive policy. State explicitly that v9.5 behavior
is frozen, v9.6 reuses v9.5 finish gates, and only v9.6 rejects ordinary harmonic
Tool calls in paired/nominal modes. Register the exact ranges:

```text
T-CX146..148  preservation and version compatibility
T-CX149..154  mode-aware Tool routing
T-CX155..162  v9.6 prompt and composition
T-CX163..165  recorded-failure regressions
```

- [ ] **Step 4: Run the preservation tests and verify GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/external/test_v03_contextual_preservation.py -v
```

Expected: all tests in the module PASS with no skip/xfail.

- [ ] **Step 5: Stop for review or commit if separately authorized**

Stage only the three files listed in this task. Suggested commit message:

```text
docs: register v9.6 contextual remediation contract
```

---

### Task 2: Add the v9.6 mode-aware Tool routing guard

**Files:**
- Modify: `src/signal_diag/agent/diagnosis.py`
- Modify: `src/signal_diag/agent/runtime.py`
- Create: `tests/agent/test_v03_contextual_routing_v9_6.py`

**Interfaces:**
- Consumes: `DiagnosisState["stimulus_context"]`, `CallToolDecision.call.tool_name`, and `CausalPolicyVersion`.
- Produces: `v9_6_contextual` routing behavior through the existing `_reject_decision(...)` retry path.

- [ ] **Step 1: Write failing routing tests T-CX149–T-CX154**

Use a recording Tool service and a scripted sequence of planner decisions. The
tests must assert:

```python
def test_t_cx149_v96_rejects_plain_harmonic_tool_in_paired_mode() -> None: ...
def test_t_cx150_v96_rejects_plain_harmonic_tool_in_nominal_mode() -> None: ...
def test_t_cx151_v96_allows_contextual_tool_in_paired_mode() -> None: ...
def test_t_cx152_v96_allows_plain_harmonic_tool_in_single_mode() -> None: ...
def test_t_cx153_rejected_route_consumes_retry_not_tool_budget() -> None: ...
def test_t_cx154_v95_routing_behavior_is_unchanged() -> None: ...
```

For T-CX149/T-CX150, verify the Tool service never receives
`analyze_harmonic_distortion`, the trace contains the sanitized recoverable
error, and the next planner context names `analyze_contextual_distortion`.

- [ ] **Step 2: Run routing tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_contextual_routing_v9_6.py -v
```

Expected: collection or assertion failure because `v9_6_contextual` and its
routing guard do not exist.

- [ ] **Step 3: Add the new policy identity without changing v9.5 gates**

In `diagnosis.py`, extend the literal and centralize contextual-policy reuse:

```python
CausalPolicyVersion = Literal[
    "v9_4_legacy",
    "v9_5_contextual",
    "v9_6_contextual",
]
_CONTEXTUAL_CAUSAL_POLICIES = frozenset({"v9_5_contextual", "v9_6_contextual"})
```

Replace direct `== "v9_5_contextual"` finish checks with membership in
`_CONTEXTUAL_CAUSAL_POLICIES`. Error messages may include the active policy
value, but existing v9.5 tests must retain their expected behavior.

- [ ] **Step 4: Reject the incompatible Tool decision before execution**

Add a private runtime helper with this behavior:

```python
def _contextual_tool_routing_error(
    *,
    causal_policy_version: CausalPolicyVersion,
    stimulus_context: StimulusContext,
    tool_name: ToolName,
) -> str | None:
    if causal_policy_version != "v9_6_contextual":
        return None
    if (
        stimulus_context.mode in {"paired_reference", "nominal_single_tone"}
        and tool_name == "analyze_harmonic_distortion"
    ):
        return (
            f"{stimulus_context.mode} harmonic closure requires "
            "analyze_contextual_distortion"
        )
    return None
```

Call the helper in `_handle_call_tool_decision` after task assessment is
accepted but before argument normalization, equivalent-call checks, or Tool
execution. Route rejection through `_reject_decision` so it consumes one
planner retry and zero Tool calls.

- [ ] **Step 5: Run routing and existing contextual runtime tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_contextual_routing_v9_6.py tests/agent/test_v03_contextual_runtime.py -v
```

Expected: T-CX149–T-CX154 and all existing T-CX056–T-CX075 tests PASS.

- [ ] **Step 6: Stop for review or commit if separately authorized**

Stage only the three files listed in this task. Suggested commit message:

```text
feat: enforce v9.6 contextual tool routing
```

---

### Task 3: Freeze and wire the v9.6 prompt

**Files:**
- Modify: `src/signal_diag/agent/prompts_v03.py`
- Modify: `src/signal_diag/agent/planner.py`
- Modify: `src/signal_diag/app/composition.py`
- Modify: `tests/app/test_service.py`
- Modify: `tests/app/test_contextual_service.py`
- Create: `tests/agent/test_v03_prompt_v9_6.py`

**Interfaces:**
- Consumes: frozen `_S1_PROMPT_V9_5`, `PROMPT_VERSION`, and `ApplicationDependencies.causal_policy_version`.
- Produces: immutable `_S1_PROMPT_V9_6`, active product prompt `v0.3-s1-planner-9.6`, and active policy `v9_6_contextual`.

- [ ] **Step 1: Write failing prompt/composition tests T-CX155–T-CX162**

The tests must cover these exact properties:

```python
def test_t_cx155_product_prompt_version_is_v9_6() -> None: ...
def test_t_cx156_v9_5_sha_remains_frozen() -> None: ...
def test_t_cx157_contextual_modes_require_contextual_tool() -> None: ...
def test_t_cx158_no_fault_names_exact_negative_mechanism_evidence() -> None: ...
def test_t_cx159_natural_even_no_growth_closes_no_fault() -> None: ...
def test_t_cx160_nominal_mismatch_requires_inconclusive() -> None: ...
def test_t_cx161_combined_requires_two_independent_gates() -> None: ...
def test_t_cx162_composition_wires_v96_without_fallback_or_thresholds() -> None: ...
```

T-CX158 must assert that the prompt says `clipping_mechanism=false` and that
`clipping_detected=false` is not a substitute. T-CX162 must retain the existing
numeric-threshold scan and `ScriptedPlanner` absence check.

- [ ] **Step 2: Run the new prompt tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_prompt_v9_6.py -v
```

Expected: FAIL because `_S1_PROMPT_V9_6` is not defined and product composition
still uses v9.5.

- [ ] **Step 3: Add a narrow v9.6 prompt section**

Build `_S1_PROMPT_V9_6` from `_S1_SYSTEM_PROMPT_V9_5`; do not edit v9.5
constants. The replacement section must contain the mode-to-tool rule,
no-fault Evidence distinction, natural-even relative conclusion, nominal
mismatch outcome, combined independent gate checklist, clipping independence,
and instruction for responding to recoverable gate errors. Do not include
numeric thresholds or hidden injection provenance.

After the bytes are final, calculate the literal SHA with:

```powershell
.venv\Scripts\python.exe -c "import hashlib; from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_6; print(hashlib.sha256(_S1_PROMPT_V9_6.system_prompt.encode('utf-8')).hexdigest())"
```

Paste that exact digest into `test_v03_prompt_v9_6.py` and later into the code
acceptance report. The test must compare against the literal, not recompute its
expected value dynamically.

- [ ] **Step 4: Wire the new prompt and policy**

Update `planner.py` to import/use `_S1_PROMPT_V9_6`. Update the composition root
to `causal_policy_version="v9_6_contextual"`. Change only assertions that inspect
the active product identity; retain explicit v9.5 construction tests.

- [ ] **Step 5: Run prompt, composition, and contextual app tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_prompt_v9_5.py tests/agent/test_v03_prompt_v9_6.py tests/app/test_service.py tests/app/test_contextual_service.py -v
```

Expected: all tests PASS; v9.5 SHA remains
`a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02`.

- [ ] **Step 6: Stop for review or commit if separately authorized**

Stage only the six files listed in this task. Suggested commit message:

```text
feat: freeze and wire contextual planner v9.6
```

---

### Task 4: Add deterministic regressions for recorded v9.5 failures

**Files:**
- Create: `tests/agent/test_v03_v9_6_regressions.py`
- Modify only if a test exposes a contract mismatch: `src/signal_diag/agent/prompts_v03.py`
- Modify only if a test exposes a routing mismatch: `src/signal_diag/agent/runtime.py`

**Interfaces:**
- Consumes: v9.6 prompt/routing contract and frozen deterministic Evidence/rule fixtures modeled on the preserved v9.5 traces.
- Produces: T-CX163–T-CX165 regression coverage without calling a provider.

- [ ] **Step 1: Add T-CX163 no-fault citation replay**

Construct the recorded failure shape: `clipping_detected=false` and
`clipping_mechanism=false` both exist, but the first finish cites only
`clipping_detected=false`. Assert rejection with `missing
clipping_mechanism=false`; then provide a second finish citing the mechanism and
all mode-required PASS rules and assert acceptance.

- [ ] **Step 2: Add T-CX164 combined routing and causal closure replay**

Start with valid clipping Evidence, attempt the ordinary harmonic Tool in paired
mode, and assert deterministic route rejection. Then supply contextual
comparison Evidence and assert a combined finish succeeds only when the
clipping and harmonic claims each cite their complete independent gate.

- [ ] **Step 3: Add T-CX165 natural-even and clipping preservation replay**

Assert both branches in one parameterized regression:

- valid paired comparison + harmonic-growth PASS + clipping-mechanism false
  accepts `no_supported_fault` relative to the reference;
- sufficient clipping remains `supported_fault` even when contextual harmonic
  comparison is invalid.

- [ ] **Step 4: Run regression and focused Workstream tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_v9_6_regressions.py tests/agent/test_v03_contextual_routing_v9_6.py tests/agent/test_v03_contextual_runtime.py tests/agent/test_v03_prompt_v9_6.py -v
```

Expected: all new tests PASS with no network access and no skip/xfail.

- [ ] **Step 5: Stop for review or commit if separately authorized**

Stage only files changed by this task. Suggested commit message:

```text
test: cover v9.6 contextual failure regressions
```

---

### Task 5: Run offline cumulative acceptance and record the new identity

**Files:**
- Create: `docs/evaluations/v0_3/contextual/V9_6_CODE_ACCEPTANCE_REPORT.md`
- Modify only for newly allocated IDs: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`

**Interfaces:**
- Consumes: completed Tasks 1–4 and frozen v9.6 prompt SHA.
- Produces: `v9_6_harness_complete` or an honest failing gate report.

- [ ] **Step 1: Run the focused v9.6 and contextual suites**

Run all new T-CX146–T-CX165 tests plus the existing contextual signal, DSP,
Tool, rule, agent, application, and evaluation tests. Use explicit paths rather
than shell wildcards so the command is reproducible in PowerShell.

- [ ] **Step 2: Run cumulative quality gates**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q -rxXs -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check --no-cache .
.venv\Scripts\python.exe -m mypy --no-incremental src
.venv\Scripts\python.exe -m pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py -q -p no:cacheprovider
git diff --check 605c8a8
```

Expected: zero failures, zero required skip/xfail, Ruff clean, mypy clean, and
no diff-hygiene errors.

- [ ] **Step 3: Run packaging gates when product files changed**

Force official PyPI rather than the user-level mirror and run the existing wheel
smoke. Then execute the existing CPython 3.11/3.12 clean-environment matrix.

```powershell
$env:PIP_CONFIG_FILE='NUL'
$env:PIP_INDEX_URL='https://pypi.org/simple'
.venv\Scripts\python.exe scripts/verify_phase5_wheel.py
$py311 = (uv python find 3.11).Trim()
$py312 = (uv python find 3.12).Trim()
.venv\Scripts\python.exe scripts/verify_phase5_local_matrix.py --python-3.11 $py311 --python-3.12 $py312
```

Resolve the two interpreter paths with `uv python find 3.11` and `uv python
find 3.12` immediately before the command; pass the returned absolute paths.
Missing interpreters or dependency-install failures are gate failures, not
skips.

- [ ] **Step 4: Verify preservation directly**

Confirm the v9.5 prompt SHA and selected Task 13 control hashes still match
T-CX146/T-CX147. Confirm `git diff --name-only 95bb191..HEAD` contains no files
inside any Task 13 run directory.

- [ ] **Step 5: Write the code acceptance report**

Record exact code HEAD, v9.6 prompt version/SHA, active causal policy, focused
and cumulative counts, wheel contents, matrix interpreters, warnings, and
preservation hashes. The only successful verdict permitted here is:

```text
v9_6_harness_complete
```

Explicitly state that no real model was run and development/validation targets
are not evaluated.

- [ ] **Step 6: Stop for review or commit if separately authorized**

Stage only the acceptance report and any test-registry update made in this
task. Suggested commit message:

```text
docs: record v9.6 contextual code acceptance
```

Do not start a real-model remediation campaign, access validation, push, or
claim `development_confirmed` without a new explicit authorization.
