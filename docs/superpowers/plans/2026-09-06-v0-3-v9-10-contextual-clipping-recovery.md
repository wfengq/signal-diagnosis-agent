# V0.3 v9.10 Contextual Clipping Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make contextual test-side clipping independently traceable and make a single-signal planner recover to an already-supported clipping-only diagnosis without changing thresholds, data, labels, scoring, or historical evidence.

**Architecture:** Extend deterministic contextual DSP/Tool output with the already-computed test clipping mechanism, evaluate it through a new additive rule-profile identity, and add a v9.10-only coherent clipping-family validator. Runtime remains a validator: it returns precise recovery guidance but never edits a planner decision.

**Tech Stack:** Python 3.11/3.12, NumPy, Pydantic, YAML rule profiles, pytest, Ruff, mypy.

---

## File structure

- Modify `docs/CONTRACTS_V0_3_CONTEXTUAL.md`: additive v9.10 contracts.
- Modify `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`: register T-CX231–T-CX240.
- Modify `src/signal_diag/dsp/contextual.py`: propagate deterministic test clipping mechanism.
- Modify `src/signal_diag/tools/contracts.py`: expose the compact output field.
- Modify `src/signal_diag/tools/contextual.py`: convert and emit the new Evidence metric.
- Create `src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10.yaml`: additive profile; never overwrite the v1 file.
- Modify `src/signal_diag/agent/rule_closure.py`: policy-specific old/new profile mapping.
- Modify `src/signal_diag/agent/diagnosis.py`: v9.10 coherent-family and subset-recovery validation.
- Modify `src/signal_diag/agent/runtime.py`: include v9.10 in inherited routing/closure behavior.
- Modify `src/signal_diag/agent/prompts_v03.py`: frozen v9.10 prompt identity.
- Modify `src/signal_diag/agent/planner.py`: select v9.10 prompt.
- Modify `src/signal_diag/app/composition.py`: load both profile identities and select v9.10 policy.
- Create focused T-CX231–T-CX240 tests under `tests/dsp`, `tests/tools`, `tests/rules`, and `tests/agent`.
- Create `docs/evaluations/v0_3/contextual/V9_10_CODE_ACCEPTANCE_REPORT.md`: offline-only evidence.

No task modifies contextual manifests, WAVs, expected outcomes, transforms,
scoring, v9.9 run directories, validation seals, V0.2 official/Demo assets, or
the `v0.2.0` tag. Do not commit any task unless the user separately authorizes
commits.

### Task 1: Register the additive contract and preservation gate

**Files:**
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md`
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`
- Create: `tests/evaluation/external/test_v03_v9_10_preservation.py`

- [ ] **Step 1: Write RED preservation and registry tests**

Add T-CX231 assertions that pin the current v9.9 prompt SHA, original
contextual profile SHA, v9.9 development bundle files, both validation run
ledgers, and the diagnostic reconstruction. Parse only table rows matching:

```python
rows = re.findall(r"^\| (T-CX\d+) \|", test_plan, flags=re.MULTILINE)
for number in range(231, 241):
    assert rows.count(f"T-CX{number}") == 1
```

- [ ] **Step 2: Run RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/evaluation/external/test_v03_v9_10_preservation.py -q
```

Expected: FAIL because T-CX231–T-CX240 and v9.10 contract text are absent.

- [ ] **Step 3: Add the approved contract text and registry rows**

Append policy `v9_10_contextual_clipping_recovery`, the additive profile
identity, coherent-family semantics, single-signal supported-subset recovery,
and authorization gates to `CONTRACTS_V0_3_CONTEXTUAL.md`. Add the following
allocation and rows to `TEST_PLAN_V0_3_CONTEXTUAL.md`:

```text
T-CX231..240 | v9.10 contextual clipping recovery
```

Register these exact titles:

```text
T-CX231 | Preserve v9.9 identities and recorded evidence; register T-CX231–T-CX240 once
T-CX232 | Contextual DSP propagates deterministic test clipping mechanism
T-CX233 | Contextual Tool emits one compact test clipping-mechanism Evidence item
T-CX234 | Additive v9.10 profile preserves the original profile and threshold semantics
T-CX235 | v9.10 automatic closure evaluates test-side clipping rules from one Evidence suffix
T-CX236 | v9.10 clipping claims require one coherent evidence family
T-CX237 | v9.10 contextual no-fault accepts only a complete contextual clean family
T-CX238 | Single-signal unsupported harmonic sibling yields clipping-subset recovery guidance
T-CX239 | Product freezes and wires v9.10 prompt, policy, and additive profile identity
T-CX240 | Two-failure replay and cumulative offline acceptance gate
```

- [ ] **Step 4: Run GREEN**

Run the Task 1 pytest command again. Expected: PASS.

- [ ] **Step 5: Commit checkpoint**

Stop and report the diff. Commit only after explicit authorization.

### Task 2: Propagate test clipping mechanism through DSP and Tool Evidence

**Files:**
- Modify: `src/signal_diag/dsp/contextual.py`
- Modify: `src/signal_diag/tools/contracts.py`
- Modify: `src/signal_diag/tools/contextual.py`
- Modify: `tests/dsp/test_contextual.py`
- Modify: `tests/tools/test_contextual_tools.py`

- [ ] **Step 1: Write RED tests T-CX232 and T-CX233**

For clipped and clean test signals, assert:

```python
assert clipped.test_clipping_mechanism is True
assert clean.test_clipping_mechanism is False
```

Also exercise an invalid contextual comparison and assert that its test-side
mechanism still equals the deterministic clipping result. At the Tool boundary:

```python
items = [item for item in evidence if item.metric == "test_clipping_mechanism"]
assert len(items) == 1
assert items[0].source_tool == "analyze_contextual_distortion"
assert items[0].validity == "valid"
assert items[0].value is True
```

Assert serialized Tool output/Evidence contains no sample array or FFT field.

- [ ] **Step 2: Run RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/dsp/test_contextual.py tests/tools/test_contextual_tools.py -q
```

Expected: FAIL because the field and Evidence metric do not exist.

- [ ] **Step 3: Implement the minimal propagation**

Add to both result models:

```python
test_clipping_mechanism: bool
```

Populate it from `test_clip.clipping_mechanism` on every valid and invalid
return path. In `analysis_to_output`, copy the field. In
`build_contextual_evidence`, append exactly once:

```python
_append("test_clipping_mechanism", output.test_clipping_mechanism)
```

Keep `CONTEXTUAL_DSP_VERSION` at `1.0.0`: the numerical algorithm is unchanged;
this is an additive result field derived from an already-computed analysis.

- [ ] **Step 4: Run GREEN**

Run the Task 2 pytest command. Expected: PASS.

- [ ] **Step 5: Commit checkpoint**

Stop and report. Commit only after explicit authorization.

### Task 3: Add the v9.10 profile and policy-specific automatic closure

**Files:**
- Create: `src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10.yaml`
- Modify: `src/signal_diag/agent/rule_closure.py`
- Create: `tests/rules/test_contextual_profile_v9_10.py`
- Create: `tests/agent/test_v03_rule_closure_v9_10.py`

- [ ] **Step 1: Write RED tests T-CX234 and T-CX235**

Pin the original profile SHA before testing the new file. Assert the additive
profile has the six inherited rules plus exactly:

```text
rule_test_clipping_ratio_acceptable: test_clipping_ratio <= 0.01
rule_test_flat_top_absent: test_flat_top_detected == false
```

Assert v9.7/v9.8/v9.9 still return
`profile_s1_contextual_comparison`, while v9.10 returns
`profile_s1_contextual_comparison_v9_10` for paired/nominal contextual Tools.
Evaluate one observation and assert both new rule evaluations reference only
Evidence from that observation.

- [ ] **Step 2: Run RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/rules/test_contextual_profile_v9_10.py tests/agent/test_v03_rule_closure_v9_10.py -q
```

Expected: FAIL because the new profile and policy literal are absent.

- [ ] **Step 3: Implement the additive profile and mapping**

Extend `RuleClosureProfileId` with:

```python
"profile_s1_contextual_comparison_v9_10"
```

In `required_rule_profile`, select the new profile only when policy is
`v9_10_contextual_clipping_recovery`; preserve the existing branch for older
policies. Copy the original six YAML rules without editing their semantics and
append the two approved rules.

- [ ] **Step 4: Run GREEN**

Run the Task 3 pytest command. Expected: PASS.

- [ ] **Step 5: Commit checkpoint**

Stop and report. Commit only after explicit authorization.

### Task 4: Enforce coherent clipping and no-fault families

**Files:**
- Modify: `src/signal_diag/agent/diagnosis.py`
- Create: `tests/agent/test_v03_contextual_clipping_v9_10.py`

- [ ] **Step 1: Write RED tests T-CX236 and T-CX237**

Construct real `Evidence`, `RuleEvaluation`, and `FinishDecision` objects.
Cover:

```text
contextual mechanism=true + contextual ratio FAIL -> clipping accepted
contextual mechanism=true + contextual flat-top FAIL -> clipping accepted
contextual mechanism=true + legacy ratio FAIL -> rejected
legacy mechanism=true + contextual ratio FAIL -> rejected
contextual mechanism=true without substantial FAIL -> rejected
contextual mechanism=false + both contextual PASS + mode gates -> no-fault accepted
missing either contextual clean PASS -> no-fault rejected
```

Also assert v9.9 continues to reject the contextual family and accepts its
legacy family exactly as before.

- [ ] **Step 2: Run RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agent/test_v03_contextual_clipping_v9_10.py -q
```

Expected: FAIL because v9.10 policy and coherent-family validation are absent.

- [ ] **Step 3: Implement the minimal v9.10 validators**

Add the policy literal to `CausalPolicyVersion` and
`_CONTEXTUAL_CAUSAL_POLICIES`. Add helpers that return true only for one whole
family, for example:

```python
legacy_ok = has_legacy_mechanism and has_legacy_substantial_fail
contextual_ok = has_test_mechanism and has_test_substantial_fail
if not (legacy_ok or contextual_ok):
    raise DiagnosisValidationError("clipping claim lacks one coherent evidence family")
```

Dispatch these helpers only under v9.10. Do not alter
`_validate_clipping_supported` or v9.5–v9.9 no-fault validation.

- [ ] **Step 4: Run GREEN**

Run the Task 4 pytest command. Expected: PASS.

- [ ] **Step 5: Commit checkpoint**

Stop and report. Commit only after explicit authorization.

### Task 5: Add single-signal supported-subset recovery

**Files:**
- Modify: `src/signal_diag/agent/diagnosis.py`
- Modify: `src/signal_diag/agent/runtime.py`
- Create: `tests/agent/test_v03_supported_subset_recovery_v9_10.py`

- [ ] **Step 1: Write RED T-CX238 tests**

Use a decision containing a fully grounded clipping claim and an unsupported
single-signal harmonic sibling. Assert the first v9.10 validation raises one
recoverable error containing:

```text
clipping claim is independently supported
preserve the clipping claim and its same-run references
remove the unsupported harmonic_distortion sibling
```

Verify the input `FinishDecision` is byte-identical before and after rejection.
Use a deterministic planner sequence where the next finish contains only the
same clipping claim and assert Runtime accepts it. Add paired and nominal
controls that retain v9.9/v9.8 recovery rather than suggesting subset removal.

- [ ] **Step 2: Run RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agent/test_v03_supported_subset_recovery_v9_10.py -q
```

Expected: FAIL because v9.10 emits the old generic harmonic error.

- [ ] **Step 3: Implement validation-only recovery guidance**

Before emitting the categorical single-signal harmonic error under v9.10,
validate the sibling clipping claim with the coherent-family helper. If it is
complete, raise the approved recovery message. Do not construct a replacement
decision, do not modify references, and do not increase retry/Tool budgets.
Add v9.10 to Runtime's inherited contextual routing and deterministic closure
policy sets.

- [ ] **Step 4: Run GREEN**

Run the Task 5 pytest command. Expected: PASS.

- [ ] **Step 5: Commit checkpoint**

Stop and report. Commit only after explicit authorization.

### Task 6: Freeze and wire v9.10 prompt/profile identity

**Files:**
- Modify: `src/signal_diag/agent/prompts_v03.py`
- Modify: `src/signal_diag/agent/planner.py`
- Modify: `src/signal_diag/app/composition.py`
- Create: `tests/agent/test_v03_prompt_v9_10.py`

- [ ] **Step 1: Write RED T-CX239 tests**

Pin `_S1_PROMPT_V9_9` SHA. Assert v9.10 contains the exact single-signal
supported-subset recovery instruction, retains no-fallback/manual-rule guards,
and contains no numeric threshold. Assert:

```python
assert planner.PROMPT_VERSION == "v0.3-s1-planner-9.10"
assert dependencies.causal_policy_version == "v9_10_contextual_clipping_recovery"
assert loader.load("profile_s1_contextual_comparison").version == "1.0.0"
assert loader.load("profile_s1_contextual_comparison_v9_10").version == "1.0.0"
```

- [ ] **Step 2: Run RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agent/test_v03_prompt_v9_10.py tests/app/test_service.py -q
```

Expected: FAIL because product composition still selects v9.9.

- [ ] **Step 3: Implement frozen prompt and composition**

Derive `_S1_PROMPT_V9_10` from `_S1_SYSTEM_PROMPT_V9_9` using guarded
single-replacement helpers. Wire planner defaults to v9.10. Add a packaged path
and loader mapping for the new profile while retaining the old mapping. Select
the v9.10 causal policy. Do not alter the Phase 4 certified prompt marker.

- [ ] **Step 4: Run GREEN**

Run the Task 6 pytest command. Expected: PASS.

- [ ] **Step 5: Commit checkpoint**

Stop and report. Commit only after explicit authorization.

### Task 7: Replay both failures and complete the offline gate

**Files:**
- Create: `tests/evaluation/contextual/test_v9_10_clipping_replay.py`
- Create: `docs/evaluations/v0_3/contextual/V9_10_CODE_ACCEPTANCE_REPORT.md`

- [ ] **Step 1: Write RED T-CX240 replay**

Build deterministic observation-level fixtures from the two preserved cases,
without opening validation WAVs or reading expected labels in product code.
Assert:

```text
7fd fixture -> contextual mechanism Evidence + contextual clipping FAIL -> legal clipping
675 fixture -> first combined proposal rejected with subset guidance -> next clipping-only finish accepted
no Runtime claim/reference mutation
v9.9 behavior and every historical artifact hash unchanged
```

- [ ] **Step 2: Run the focused v9.10 suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/dsp/test_contextual.py tests/tools/test_contextual_tools.py tests/rules/test_contextual_profile_v9_10.py tests/agent/test_v03_rule_closure_v9_10.py tests/agent/test_v03_contextual_clipping_v9_10.py tests/agent/test_v03_supported_subset_recovery_v9_10.py tests/agent/test_v03_prompt_v9_10.py tests/evaluation/contextual/test_v9_10_clipping_replay.py tests/evaluation/external/test_v03_v9_10_preservation.py -q -rxXs
```

Expected: PASS with zero skip/xfail.

- [ ] **Step 3: Run cumulative verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rxXs
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py tests/evaluation/external/test_v03_v9_10_preservation.py -q
git -c safe.directory='C:/Users/wei/Desktop/招聘/signal-diagnosis-agent' diff --check 605c8a8
```

Run the wheel smoke and CPython 3.11/3.12 clean-environment verifier:

```powershell
.\.venv\Scripts\python.exe scripts/verify_phase5_wheel.py
.\.venv\Scripts\python.exe scripts/verify_phase5_local_matrix.py --python-3.11 'C:\Users\wei\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe' --python-3.12 'C:\Users\wei\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe'
```

Expected: wheel smoke passes and the matrix prints
`local 3.11/3.12 clean-environment verification passed`, with zero required
skip/xfail.

- [ ] **Step 4: Write the offline acceptance report**

Record exact HEAD, prompt/profile hashes, focused/full counts, static gates,
matrix results, and preservation checks. The conclusion may be only:

```text
v9_10_harness_complete
```

The report must explicitly deny `development_confirmed`, validation completion,
performance improvement, or final-test access.

- [ ] **Step 5: Final stop**

Report modified/untracked files and stop. Do not commit, push, or run a real
model without separate authorization.
