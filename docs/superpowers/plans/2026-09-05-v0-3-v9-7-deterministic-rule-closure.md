# V0.3 v9.7 Deterministic Rule Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Scenario S1 rule-profile selection and Evidence scoping deterministic after relevant Tool observations while retaining the LLM for measurement planning and final diagnostic synthesis.

**Architecture:** Add a pure Agent-layer Tool-to-profile mapper and let `DistortionDiagnosisRuntime` append exactly one fixed RuleEngine batch after each relevant non-error Tool observation. Extend trace assembly so the Observation and automatic rule batch share the triggering planner decision index, remove positive manual-rule instructions from a new frozen v9.7 prompt, and preserve every older policy and recorded run.

**Tech Stack:** Python 3.11/3.12, Pydantic v2, NumPy, PyYAML, pytest/pytest-asyncio, Ruff, mypy, the existing deterministic Tool/RuleEngine runtime, and the existing OpenAI-compatible `RealLLMPlanner` boundary.

**Spec:** `docs/superpowers/specs/2026-09-05-v0-3-v9-7-deterministic-rule-closure-design.md`

## Global Constraints

- Work only on `codex/v0.2-real-world-validation`; expected starting HEAD is `2f449646b90fc1d660147e1f17cc5df0a2cf4bf1`.
- Preserve V0.2 Phase 4.3.1 official bundles, the accepted V0.2 Demo, prompt identities v8.1/v9.4/v9.5/v9.6, rule/scoring identities, both rule-profile thresholds, and tag `v0.2.0`.
- Preserve the complete v9.5 Task 13 and v9.6 development-confirmation directories. New audit output is append-only in a distinct v9.7 directory.
- Do not change WAVs, manifests, labels, confidence tiers, expected outcomes, DSP, Tool schemas, rule YAML, scoring formulas, or denominators.
- Do not access `docs/evaluations/v0_3/validation/`, download data, call a real model, or use `ScriptedPlanner` as a product fallback.
- Use TDD for every behavior change: focused RED, smallest GREEN, focused regression, then cumulative gates.
- Do not add dependencies or perform unrelated refactors.
- Keep the user-owned untracked investigation report and `docs/evaluations/v0_3/validation/` unstaged and untouched.
- Every task stops for review. Commit only when separately authorized; never push during this plan.
- `v9_7_harness_complete` is the strongest permitted conclusion. It does not mean `development_confirmed`, validation passed, or performance improved.

## Preflight

Run before Task 1:

```powershell
git -c safe.directory=C:/Users/wei/Desktop/招聘/signal-diagnosis-agent status --short
git -c safe.directory=C:/Users/wei/Desktop/招聘/signal-diagnosis-agent rev-parse HEAD
git -c safe.directory=C:/Users/wei/Desktop/招聘/signal-diagnosis-agent branch --show-current
```

Stop if HEAD or branch differs, or tracked changes are present. The only expected untracked paths are the two user-owned paths plus the approved v9.7 spec and this plan.

## File Structure

- `src/signal_diag/agent/rule_closure.py`: pure policy/Tool/Observation mapping.
- `src/signal_diag/agent/runtime.py`: bounded automatic RuleEngine execution and manual-action rejection.
- `src/signal_diag/evaluation/recording.py`: chronological Tool-to-rule trace projection.
- `src/signal_diag/agent/prompts_v03.py`, `planner.py`, `app/composition.py`: frozen v9.7 prompt and active identity.
- `src/signal_diag/evaluation/contextual/shadow_replay.py`: read-only replay of preserved v9.6 Observation Evidence.
- `docs/evaluations/v0_3/contextual/V9_7_CODE_ACCEPTANCE_REPORT.md`: final offline gate record.

---

### Task 1: Register contracts and freeze v9.6 evidence

**Files:**
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md`
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`
- Modify: `tests/evaluation/external/test_v03_contextual_preservation.py`
- Include when committing: the approved spec and this plan

**Interfaces:**
- Consumes: frozen v9.6 prompt SHA `b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb`.
- Produces: normative `v9_7_deterministic_rule_closure` contract and unique T-CX166–T-CX185 registry.

- [ ] **Step 1: Add the failing T-CX166 preservation test**

Add literal hashes; never calculate expected values from the files under test:

```python
V96_CONTROL_SHA256 = {
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/run_summary.json":
        "3742f664ee7487d5ea320826bdec0596bb324a1340ca0644b6af88aeea62d3a0",
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/audit_report.json":
        "cef68d2845f9d062b73fbfd512ff6a9ab309704e9222d5a3f420a05e9c2be883",
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/STATUS.md":
        "fa2caf401804f5e4373cb7a4b58ee991d797d79b4973acefe2cb66b737a77a58",
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/AUDIT_CORRECTION.md":
        "76518206967c8381694bf947bea3cc3c9b06e0efa5a56f961be53feff06c1c95",
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/corrected_scoring.json":
        "f06563103f790a79007575130ed001548ff0b701ade014f0101a637c6c2ea870",
}

def test_t_cx166_v9_6_prompt_run_and_v9_7_registry_are_preserved() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_6.system_prompt.encode("utf-8")).hexdigest()
    assert digest == "b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb"
    for relative, expected in V96_CONTROL_SHA256.items():
        assert sha256_path(REPO_ROOT / relative) == expected
    registry = (REPO_ROOT / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    table_ids = re.findall(r"^\| (T-CX\d+) \|", registry, flags=re.MULTILINE)
    counts = Counter(table_ids)
    for number in range(166, 186):
        assert counts[f"T-CX{number}"] == 1
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/external/test_v03_contextual_preservation.py -k t_cx166 -v
```

Expected: FAIL only because T-CX166–T-CX185 are not yet registered.

- [ ] **Step 3: Append the approved contract and exact ID rows**

Add `v9_7_deterministic_rule_closure` to `CONTRACTS_V0_3_CONTEXTUAL.md` with the Tool/profile mapping, automatic Evidence suffix, manual-rule rejection, trace event order, legacy compatibility, and authorization gates. Add one table row per ID from the spec to `TEST_PLAN_V0_3_CONTEXTUAL.md`.

- [ ] **Step 4: Verify GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/external/test_v03_contextual_preservation.py -v
```

- [ ] **Step 5: Review or commit**

Suggested commit:

```text
docs: register v9.7 deterministic rule closure
```

### Task 2: Implement the pure closure mapping

**Files:**
- Create: `src/signal_diag/agent/rule_closure.py`
- Create: `tests/agent/test_v03_rule_closure_v9_7.py`
- Modify: `src/signal_diag/agent/diagnosis.py`
- Modify: `src/signal_diag/agent/runtime.py` only to let the v9.7 policy inherit the v9.6 Tool-routing guard

**Interfaces:**
- Produces: `RuleClosureProfileId`, `RuleClosureRequest`, `RuleClosureInvariantError`, `automatic_profile_for_tool(tool_name)`, `required_rule_profile(...)`, and `build_rule_closure_request(...)`.
- Depends only on typed Agent, signal-context, and Tool contracts; it must not import RuleEngine or loaders.

- [ ] **Step 1: Write RED tests T-CX167–T-CX174**

Use parameterization for all modes and statuses:

```python
def make_context(mode: DiagnosticMode) -> StimulusContext:
    if mode == "paired_reference":
        return StimulusContext(
            mode=mode,
            test_signal_id="sig_test",
            reference_signal_id="sig_reference",
            assertion_source="user_supplied",
        )
    if mode == "nominal_single_tone":
        return StimulusContext(
            mode=mode,
            test_signal_id="sig_test",
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            assertion_source="user_supplied",
        )
    return StimulusContext(
        mode=mode,
        test_signal_id="sig_test",
        assertion_source="user_supplied",
    )

def make_observation(
    *,
    tool_name: ToolName,
    status: ToolStatus,
    evidence_refs: tuple[str, ...],
) -> Observation:
    return Observation(
        observation_id="obs_closure_test",
        call_id="call_closure_test",
        tool_name=tool_name,
        normalized_arguments={},
        purpose="test deterministic closure",
        status=status,
        evidence_refs=evidence_refs,
        error_message="tool failed" if status == "error" else None,
    )

@pytest.mark.parametrize("mode", ["single_signal", "nominal_single_tone", "paired_reference"])
def test_t_cx168_clipping_maps_to_distortion_in_every_mode(
    mode: DiagnosticMode,
) -> None:
    assert required_rule_profile(
        causal_policy_version="v9_7_deterministic_rule_closure",
        stimulus_context=make_context(mode),
        tool_name="detect_clipping",
    ) == "profile_s1_distortion"

def test_t_cx174_request_keeps_complete_ordered_observation_refs() -> None:
    observation = make_observation(
        tool_name="analyze_contextual_distortion",
        status="success",
        evidence_refs=("ev_context_valid", "ev_growth", "ev_test_thd"),
    )
    request = build_rule_closure_request(
        profile_id="profile_s1_contextual_comparison",
        observation=observation,
    )
    assert request is not None
    assert request.evidence_refs == (
        "ev_context_valid", "ev_growth", "ev_test_thd"
    )
```

Cover: v9.7 policy literal and contextual finish-policy membership; contextual mapping in paired/nominal; ordinary harmonic mapping only in single-signal; spectrum/fundamental no mapping; error Observation returns no request; invalid Observation with Evidence returns a request; non-error empty Evidence raises `RuleClosureInvariantError`; v9.4/v9.5/v9.6 return no automatic profile.

- [ ] **Step 2: Run RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_rule_closure_v9_7.py -v
```

Expected: collection failure because `rule_closure.py` and the v9.7 literal do not exist.

- [ ] **Step 3: Implement the minimal pure unit**

Use these exact public signatures:

```python
RuleClosureProfileId = Literal[
    "profile_s1_distortion",
    "profile_s1_contextual_comparison",
]

@dataclass(frozen=True)
class RuleClosureRequest:
    profile_id: RuleClosureProfileId
    evidence_refs: tuple[str, ...]

class RuleClosureInvariantError(RuntimeError):
    pass

def automatic_profile_for_tool(tool_name: ToolName) -> RuleClosureProfileId | None:
    if tool_name == "detect_clipping":
        return "profile_s1_distortion"
    if tool_name == "analyze_harmonic_distortion":
        return "profile_s1_distortion"
    if tool_name == "analyze_contextual_distortion":
        return "profile_s1_contextual_comparison"
    return None

def required_rule_profile(
    *,
    causal_policy_version: CausalPolicyVersion,
    stimulus_context: StimulusContext,
    tool_name: ToolName,
) -> RuleClosureProfileId | None:
    if causal_policy_version != "v9_7_deterministic_rule_closure":
        return None
    if tool_name == "analyze_harmonic_distortion":
        return "profile_s1_distortion" if stimulus_context.mode == "single_signal" else None
    if tool_name == "analyze_contextual_distortion":
        return (
            "profile_s1_contextual_comparison"
            if stimulus_context.mode in {"paired_reference", "nominal_single_tone"}
            else None
        )
    return automatic_profile_for_tool(tool_name)

def build_rule_closure_request(
    *,
    profile_id: RuleClosureProfileId,
    observation: Observation,
) -> RuleClosureRequest | None:
    if observation.status == "error":
        return None
    if not observation.evidence_refs:
        raise RuleClosureInvariantError(
            "relevant non-error Tool observation requires Evidence"
        )
    return RuleClosureRequest(profile_id, observation.evidence_refs)
```

- [ ] **Step 4: Extend the policy identity and routing inheritance**

Add `v9_7_deterministic_rule_closure` to `CausalPolicyVersion` and `_CONTEXTUAL_CAUSAL_POLICIES`. Change the Tool-routing helper condition to membership in:

```python
{"v9_6_contextual", "v9_7_deterministic_rule_closure"}
```

- [ ] **Step 5: Run GREEN and legacy regressions**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_rule_closure_v9_7.py tests/agent/test_v03_contextual_runtime.py tests/agent/test_v03_contextual_routing_v9_6.py -v
```

- [ ] **Step 6: Review or commit**

Suggested commit:

```text
feat: add deterministic v9.7 rule closure mapping
```

### Task 3: Execute automatic closure in the runtime

**Files:**
- Modify: `src/signal_diag/agent/runtime.py`
- Create: `tests/agent/test_v03_runtime_rule_closure_v9_7.py`

**Interfaces:**
- Consumes: Task 2 mapping functions and existing `RuleEngine.evaluate_profile`.
- Produces: one automatic `RuleEvaluationBatch` per relevant `success` or `invalid` Observation, visible in the next `PlannerContext`.

- [ ] **Step 1: Write RED runtime tests T-CX175–T-CX176**

Tests must prove: clipping and contextual calls receive the mapped profile; the closure Evidence filter equals the Observation refs; `rule_evaluation_count` increments once; `max_rule_evaluations=0` stops before Tool execution; missing engine/loader, empty non-error Evidence, loader error, and engine error terminate as `runtime_error`; errored Tools append no rule batch and consume no rule slot.

Use a recording engine:

```python
class RecordingRuleEngine(RuleEngine):
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], frozenset[str] | None]] = []

    def evaluate_profile(self, profile, evidence, *, evidence_filter=None):
        self.calls.append(
            (profile.profile_id, tuple(item.evidence_id for item in evidence), evidence_filter)
        )
        return super().evaluate_profile(
            profile, evidence, evidence_filter=evidence_filter
        )
```

- [ ] **Step 2: Run RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_runtime_rule_closure_v9_7.py -k "automatic or bound or dependency" -v
```

Expected: no automatic batches are present.

- [ ] **Step 3: Return the recorded Observation**

Change `_record_tool_execution(...) -> Observation` and return the exact object appended to state. Existing callers continue to receive identical state mutations.

- [ ] **Step 4: Add capacity preflight and automatic execution**

Before Tool execution, call `required_rule_profile(...)`. If a profile is required and the existing count is already at the limit, set `termination_reason="max_rule_evaluations"` and do not execute the Tool.

After recording a non-error Tool result, call a private method with this shape:

```python
def _append_automatic_rule_closure(
    self,
    state: DiagnosisState,
    *,
    profile_id: RuleClosureProfileId,
    observation: Observation,
) -> bool:
    try:
        request = build_rule_closure_request(
            profile_id=profile_id,
            observation=observation,
        )
        if request is None:
            return True
        if self._rule_engine is None or self._rule_profile_loader is None:
            raise RuntimeError("automatic rule closure requires rule dependencies")
        profile = self._rule_profile_loader.load(request.profile_id)
        evidence_by_id = {item.evidence_id: item for item in state["evidence"]}
        exact_evidence = tuple(evidence_by_id[ref] for ref in request.evidence_refs)
        batch = self._rule_engine.evaluate_profile(
            profile,
            exact_evidence,
            evidence_filter=frozenset(request.evidence_refs),
        )
        if batch.profile_id != request.profile_id:
            raise RuntimeError("automatic rule closure profile mismatch")
        allowed = frozenset(request.evidence_refs)
        if any(
            ref not in allowed
            for evaluation in batch.evaluations
            for ref in evaluation.evidence_refs
        ):
            raise RuntimeError("automatic rule closure Evidence scope mismatch")
    except Exception as error:  # noqa: BLE001
        state["errors"].append(str(error))
        state["termination_reason"] = "runtime_error"
        return False
    state["rule_evaluation_count"] += 1
    state["rule_evaluation_batches"].append(batch)
    return True
```

If the helper returns false, return `terminated` from the Tool-decision handler. Do not convert failure to inconclusive and do not call a fallback planner.

- [ ] **Step 5: Run GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_runtime_rule_closure_v9_7.py tests/agent/test_v03_rule_closure_v9_7.py -v
```

- [ ] **Step 6: Review or commit**

Suggested commit:

```text
feat: close v9.7 rules after tool observations
```

### Task 4: Reject manual rule actions under v9.7

**Files:**
- Modify: `src/signal_diag/agent/runtime.py`
- Modify: `tests/agent/test_v03_runtime_rule_closure_v9_7.py`

**Interfaces:**
- Consumes: existing `_reject_decision(...)` retry boundary.
- Produces: T-CX177 manual-action rejection and T-CX178 legacy behavior compatibility.

- [ ] **Step 1: Add RED tests**

For v9.7, emit an `EvaluateRulesDecision` after Tool Evidence already exists.
Capture consecutive planner contexts and assert that the rejection creates no
new batch, consumes one planner retry, and consumes zero Tool calls. Assert the
recoverable message contains both `automatic` and `Tool observation`.

Run the same Tool/EvaluateRules sequence under v9.6 and assert the manual batch
is still created:

```python
ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="test manual rule policy",
)
PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
)

async def _run_manual_rule_policy(
    policy: CausalPolicyVersion,
) -> tuple[AgentRunResult, tuple[PlannerContext, ...]]:
    repository = InMemorySignalRepository()
    signal_id = store_synthetic_case(
        repository,
        generate_sine(
            frequency_hz=200.0,
            sample_rate_hz=48_000,
            duration_s=1.0,
            amplitude=0.5,
        ),
    )
    steps = (
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="obtain clipping Evidence",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=EvaluateRulesDecision(
                profile_id="profile_s1_distortion",
                evidence_refs=(),
                purpose="attempt manual rule evaluation",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("stop after rule-policy test",),
            ),
        ),
    )
    received: list[PlannerContext] = []

    class CapturePlanner(ScriptedPlanner):
        async def decide(self, context: PlannerContext) -> AgentDecision:
            received.append(context)
            return await super().decide(context)

    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=CapturePlanner(steps),
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
        causal_policy_version=policy,
        limits=AgentLimits(max_planner_retries=2),
    )
    result = await runtime.run(
        signal_id=signal_id,
        user_request="Why distorted?",
    )
    return result, tuple(received)

@pytest.mark.asyncio
async def test_t_cx177_v97_rejects_manual_rule_action() -> None:
    result, contexts = await _run_manual_rule_policy(
        "v9_7_deterministic_rule_closure"
    )
    assert any("automatic" in error for error in result.errors)
    assert len(result.rule_evaluation_batches) == 1
    assert contexts[1].remaining_planner_retries - 1 == contexts[2].remaining_planner_retries

@pytest.mark.asyncio
async def test_t_cx178_legacy_policies_keep_manual_rule_behavior() -> None:
    for policy in ("v9_4_legacy", "v9_5_contextual", "v9_6_contextual"):
        result, _ = await _run_manual_rule_policy(policy)
        assert result.rule_evaluation_batches
```

The v9.7 sequence already has one automatic batch. Its rejected manual action
must not create a second batch.

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_runtime_rule_closure_v9_7.py -k "manual or legacy" -v
```

- [ ] **Step 3: Add the v9.7-only rejection**

After task assessment and unsupported-task checks, but before the existing
manual rule budget/load/evaluate path, add:

```python
if self._causal_policy_version == "v9_7_deterministic_rule_closure":
    return self._reject_decision(
        state,
        message=(
            "rule batches are created automatically from relevant Tool "
            "observations; use existing rule_evaluation_batches or call "
            "the missing Tool"
        ),
        planner_retries_remaining=planner_retries_remaining,
        recoverable_errors=recoverable_errors,
    )
```

Do not change the remaining v9.4/v9.5/v9.6 code path.

- [ ] **Step 4: Run GREEN and the historical runtime suites**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_runtime_rule_closure_v9_7.py tests/agent/test_phase3_runtime.py tests/agent/test_v03_contextual_runtime.py tests/agent/test_v03_contextual_routing_v9_6.py -v
```

- [ ] **Step 5: Review or commit**

Suggested commit:

```text
feat: reject manual v9.7 rule actions
```

### Task 5: Extend chronological trace provenance

**Files:**
- Modify: `src/signal_diag/evaluation/recording.py`
- Modify: `tests/evaluation/test_recording.py`

**Interfaces:**
- Consumes: `automatic_profile_for_tool(tool_name)` from Task 2 and existing append-only artifact deltas.
- Produces: T-CX179 event order and T-CX180 old/new trace round-trip.

- [ ] **Step 1: Add the RED automatic-event test**

Reuse the existing `_empty_context`, `_clipping_observation`,
`_clipping_evidence`, `_rule_batch`, `_decision_record`, `_advance`, and
`_agent_result` helpers:

```python
def test_t_cx179_tool_delta_can_include_one_automatic_rule_batch() -> None:
    empty = _empty_context()
    observation = _clipping_observation()
    evidence = _clipping_evidence()
    batch = _rule_batch()
    after = _advance(
        empty,
        observations=(observation,),
        evidence=(evidence,),
        rule_evaluation_batches=(batch,),
    )
    claim = DiagnosisClaim(
        claim_id="claim_auto_rule",
        fault_type="no_supported_fault",
        statement="Automatic rule batch is traceable.",
        evidence_refs=("ev_clip_001",),
        rule_refs=("ruleval_clip_001",),
    )
    finish = FinishDecision(
        task_assessment=_task_assessment(),
        outcome="no_supported_fault",
        claims=(claim,),
        confidence_label="high",
    )
    records = (
        _decision_record(0, empty, _clipping_decision()),
        _decision_record(1, after, finish),
    )
    result = _agent_result(
        observations=(observation,),
        evidence=(evidence,),
        batches=(batch,),
        retrievals=(),
        claims=(claim,),
    )
    trace = _assemble_agent(records, result)
    assert [event.event_type for event in trace.events[:3]] == [
        "planner_call", "observation", "rule_evaluation"
    ]
    assert trace.events[1].caused_by_decision_index == 0
    assert trace.events[2].caused_by_decision_index == 0
```

Also add negative cases for two batches after one Tool, a batch after an errored
Tool, a batch after spectrum/fundamental, and a profile inconsistent with the
Tool. T-CX180 serializes and reparses both `_full_agent_chain()` and the new
automatic trace with `EvaluationTrace.model_validate_json`.

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/test_recording.py -k "t_cx179 or t_cx180" -v
```

Expected: `CallToolDecision produced unexpected artifacts`.

- [ ] **Step 3: Permit exactly one structurally valid automatic batch**

In the `CallToolDecision` branch:

```python
if knowledge_delta:
    raise ValueError("CallToolDecision produced unexpected knowledge artifacts")
if len(rule_delta) > 1:
    raise ValueError("CallToolDecision permits at most one automatic rule batch")
# Build and append ObservationEvent exactly as before.
if rule_delta:
    batch = rule_delta[0]
    expected_profile = automatic_profile_for_tool(observation.tool_name)
    if observation.status == "error":
        raise ValueError("errored Tool cannot produce automatic rules")
    if expected_profile is None or batch.profile_id != expected_profile:
        raise ValueError("automatic rule batch does not match Tool")
    events.append(
        RuleEvaluationEvent(
            event_index=event_index,
            caused_by_decision_index=record.decision_index,
            batch=batch,
        )
    )
    event_index += 1
continue
```

Do not load profiles or rerun RuleEngine inside trace assembly. Runtime tests
own semantic equality; recording tests own chronological structure.

- [ ] **Step 4: Run GREEN and all recording tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/test_recording.py tests/agent/test_v03_runtime_rule_closure_v9_7.py -v
```

- [ ] **Step 5: Review or commit**

Suggested commit:

```text
feat: trace automatic v9.7 rule closure
```

### Task 6: Freeze the v9.7 prompt and product wiring

**Files:**
- Modify: `src/signal_diag/agent/prompts_v03.py`
- Modify: `src/signal_diag/agent/planner.py`
- Modify: `src/signal_diag/app/composition.py`
- Modify active-identity assertions in: `tests/app/test_service.py`
- Modify active-identity assertions in: `tests/app/test_contextual_service.py`
- Create: `tests/agent/test_v03_prompt_v9_7.py`

**Interfaces:**
- Consumes: frozen `_S1_PROMPT_V9_6` and implemented v9.7 causal policy.
- Produces: `_S1_PROMPT_V9_7`, active `PROMPT_VERSION`, and product policy `v9_7_deterministic_rule_closure`.

- [ ] **Step 1: Write RED tests T-CX181–T-CX183**

```python
def test_t_cx181_v97_removes_positive_manual_rule_instructions() -> None:
    text = _S1_PROMPT_V9_7.system_prompt
    assert '"decision_type": "evaluate_rules"' not in text
    assert '"call_tool", "evaluate_rules"' not in text
    assert "Use profile_s1_distortion for configured S1" not in text
    assert "rule batches are created automatically" in text

def test_t_cx182_v97_retains_finish_and_safety_semantics() -> None:
    text = _S1_PROMPT_V9_7.system_prompt.lower()
    for phrase in (
        "paired_reference", "nominal_single_tone",
        "analyze_contextual_distortion", "clipping_mechanism=false",
        "natural", "combined", "independent", "no_supported_fault",
        "scriptedplanner",
    ):
        assert phrase in text
    assert _NUMERIC_THRESHOLD_PATTERN.search(text) is None

def test_t_cx183_product_wires_v97_identity() -> None:
    assert PROMPT_VERSION == "v0.3-s1-planner-9.7"
    service = build_product_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
    assert service._dependencies.causal_policy_version == (
        "v9_7_deterministic_rule_closure"
    )
    assert isinstance(service._dependencies.planner_factory(), RealLLMPlanner)
```

Also pin the existing v9.6 SHA literal in this module.

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_prompt_v9_7.py -v
```

- [ ] **Step 3: Build v9.7 without editing v9.6 bytes**

Add a checked replace helper:

```python
def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"v9.7 prompt build anchor mismatch: {label}")
    return text.replace(old, new, 1)
```

Start from `_S1_SYSTEM_PROMPT_V9_6`. Change only the version header and replace
each inherited positive manual-rule instruction: the global “Evaluate
profile” sentence, clipping-specific rule instruction, clean-broad
`evaluate_rules` JSON example, invalid/noise `evaluate_rules` example, output
decision list, and final “Use profile_s1_distortion” sentence. Replace them
with automatic-batch instructions. Replace the v9.6 contextual section with a
v9.7 section that says Tool observations produce rule batches before the next
turn and missing rule families require the corresponding Tool, not a profile
action.

The builder must finish with assertions:

```python
if '"decision_type": "evaluate_rules"' in text:
    raise RuntimeError("v9.7 prompt retains manual rule example")
if '"call_tool", "evaluate_rules"' in text:
    raise RuntimeError("v9.7 prompt advertises manual rule action")
```

- [ ] **Step 4: Wire planner and composition**

Import `_S1_PROMPT_V9_7` in `planner.py`, point `PROMPT_VERSION`,
`_SYSTEM_PROMPT`, and `RealLLMPlanner._prompt_spec` to it, and set composition
to `causal_policy_version="v9_7_deterministic_rule_closure"`. Update only tests
that assert the active product identity.

- [ ] **Step 5: Freeze the literal prompt SHA**

```powershell
.venv\Scripts\python.exe -c "import hashlib; from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_7; print(hashlib.sha256(_S1_PROMPT_V9_7.system_prompt.encode('utf-8')).hexdigest())"
```

Copy the emitted 64-character digest into `test_v03_prompt_v9_7.py` and the
later acceptance report. The expected value must be a literal.

- [ ] **Step 6: Run GREEN and prompt preservation**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_prompt_v9_5.py tests/agent/test_v03_prompt_v9_6.py tests/agent/test_v03_prompt_v9_7.py tests/agent/test_phase4_3_1_prompt_v8_1.py tests/app/test_service.py tests/app/test_contextual_service.py -v
```

- [ ] **Step 7: Review or commit**

Suggested commit:

```text
feat: freeze and wire contextual planner v9.7
```

### Task 7: Replay preserved v9.6 Evidence through v9.7 closure

**Files:**
- Create: `src/signal_diag/evaluation/contextual/shadow_replay.py`
- Modify: `src/signal_diag/evaluation/contextual/__main__.py`
- Create: `tests/evaluation/contextual/test_shadow_replay.py`
- Create by running the command: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/v9_7_rule_closure_shadow_replay_1/report.json`
- Create after verifying the JSON: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/v9_7_rule_closure_shadow_replay_1/STATUS.md`

**Interfaces:**
- Consumes: committed v9.6 `trace.json` files, existing `EvaluationTrace` models, both frozen profile YAMLs, and Task 2 mapping.
- Produces: `replay_rule_closure(run_dir, rule_engine, profile_loader) -> dict[str, object]` and offline CLI command `shadow-replay-rule-closure`.

- [ ] **Step 1: Write RED T-CX184**

The test runs only on the committed development directory:

```python
def profile_loader() -> YamlRuleProfileLoader:
    profile_root = (
        Path(__file__).resolve().parents[3]
        / "src/signal_diag/rules/profiles"
    )
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": profile_root / "s1_distortion_v1.yaml",
            "profile_s1_contextual_comparison":
                profile_root / "s1_contextual_comparison_v1.yaml",
        }
    )

def test_t_cx184_v96_observations_close_under_v97_without_labels() -> None:
    report = replay_rule_closure(
        V96_RUN_DIR,
        rule_engine=RuleEngine(),
        profile_loader=profile_loader(),
    )
    assert report["source_case_count"] == 20
    assert report["label_independent_mapping"] is True
    assert set(report["contextual_positive_fail_case_ids"]) == {
        "a4a0853be9983f8c",
        "2be730b9113701de",
        "6fb80bbda391c26c",
        "aa9b4a91b0253c33",
        "35967af7b71c5b75",
    }
    assert {
        "825a759a0ea47bb7",
        "393940e92c58cf0b",
        "04f4068ec91d2621",
        "ce8b413cf7382c3d",
    }.issubset(set(report["contextual_complete_pass_case_ids"]))
    assert "expected_outcome" not in json.dumps(report)
    assert "expected_causal" not in json.dumps(report)
```

Also assert that every automatic batch profile equals the pure mapping, every
evaluation Evidence ref belongs to its Observation event, all 20 source trace
SHA-256 values are recorded, and the v9.6 files have identical hashes before
and after replay.

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/contextual/test_shadow_replay.py -v
```

- [ ] **Step 3: Implement the read-only replay**

Use the trace events, never final expected labels:

```python
def replay_rule_closure(
    run_dir: Path,
    *,
    rule_engine: RuleEngine,
    profile_loader: RuleProfileLoader,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    trace_hashes: dict[str, str] = {}
    case_dirs = sorted((run_dir / "cases").iterdir())
    for case_dir in case_dirs:
        trace_path = case_dir / "trace.json"
        raw = trace_path.read_bytes()
        trace_hashes[case_dir.name] = hashlib.sha256(raw).hexdigest()
        trace = EvaluationTrace.model_validate_json(raw)
        planner_contexts = {
            event.record.decision_index: event.record.context
            for event in trace.events
            if isinstance(event, PlannerDecisionEvent)
        }
        for event in trace.events:
            if not isinstance(event, ObservationEvent):
                continue
            context = planner_contexts[event.caused_by_decision_index].stimulus_context
            if context is None:
                raise ValueError("contextual replay requires StimulusContext")
            profile_id = required_rule_profile(
                causal_policy_version="v9_7_deterministic_rule_closure",
                stimulus_context=context,
                tool_name=event.observation.tool_name,
            )
            if profile_id is None or event.observation.status == "error":
                continue
            request = build_rule_closure_request(
                profile_id=profile_id,
                observation=event.observation,
            )
            if request is None:
                continue
            if tuple(item.evidence_id for item in event.evidence) != request.evidence_refs:
                raise ValueError("Observation Evidence suffix mismatch")
            batch = rule_engine.evaluate_profile(
                profile_loader.load(profile_id),
                event.evidence,
                evidence_filter=frozenset(request.evidence_refs),
            )
            rows.append(build_replay_row(case_dir.name, context.mode, event, batch))
    return build_replay_report(rows, trace_hashes)
```

`build_replay_row` serializes case, mode, observation/call IDs, Tool, profile,
Evidence refs, batch ID, and each rule ID/judgment/ref. `build_replay_report`
derives contextual positive-FAIL cases from either
`rule_even_harmonic_growth_acceptable=fail` or
`rule_nominal_thd_acceptable=fail`. It derives complete-PASS cases using the
mode-specific rule sets from the frozen finish contract. Neither helper reads a
manifest, case summary, expected outcome, or expected causal set.

- [ ] **Step 4: Add the offline command**

Register:

```text
python -m signal_diag.evaluation.contextual shadow-replay-rule-closure \
  --run-dir PATH \
  --destination PATH
```

The command must reject an existing destination, create it once, load both
packaged profiles, write canonical indented JSON plus a final newline, print
`shadow_replay_complete`, and return zero. It must not import provider code or
open audio.

- [ ] **Step 5: Run GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/contextual/test_shadow_replay.py tests/evaluation/contextual/test_cli.py -v
```

- [ ] **Step 6: Generate the append-only report**

```powershell
.venv\Scripts\python.exe -m signal_diag.evaluation.contextual shadow-replay-rule-closure --run-dir docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/agent_v9_6_dev_confirmation_1 --destination docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/v9_7_rule_closure_shadow_replay_1
```

Write `STATUS.md` with the verdict `shadow_replay_complete` and explicit
statements: no model call, no audio access, no expected-label input, no v9.6
mutation, and not development confirmation.

- [ ] **Step 7: Re-run preservation and review or commit**

```powershell
.venv\Scripts\python.exe -m pytest tests/evaluation/contextual/test_shadow_replay.py tests/evaluation/external/test_v03_contextual_preservation.py -v
```

Suggested commit:

```text
test: add v9.7 rule closure shadow replay
```

### Task 8: Run cumulative acceptance and record v9.7 harness status

**Files:**
- Create: `docs/evaluations/v0_3/contextual/V9_7_CODE_ACCEPTANCE_REPORT.md`
- Modify only if registry enforcement needs it: `tests/evaluation/external/test_v03_contextual_preservation.py`

**Interfaces:**
- Consumes: Tasks 1–7, frozen v9.7 prompt SHA, and shadow replay report.
- Produces: T-CX185 and either `v9_7_harness_complete` or an honest failing gate record.

- [ ] **Step 1: Run the focused v9.7 gate**

```powershell
.venv\Scripts\python.exe -m pytest tests/agent/test_v03_rule_closure_v9_7.py tests/agent/test_v03_runtime_rule_closure_v9_7.py tests/agent/test_v03_prompt_v9_7.py tests/evaluation/contextual/test_shadow_replay.py tests/evaluation/test_recording.py tests/evaluation/external/test_v03_contextual_preservation.py -q -rxXs -p no:cacheprovider
```

Expected: T-CX166–T-CX185 pass with zero required skip/xfail.

- [ ] **Step 2: Run the complete contextual and full suites**

```powershell
.venv\Scripts\python.exe -m pytest tests/signal tests/dsp tests/tools tests/rules tests/agent tests/app tests/evaluation/contextual -q -rxXs -p no:cacheprovider
.venv\Scripts\python.exe -m pytest -q -rxXs -p no:cacheprovider
```

- [ ] **Step 3: Run static, architecture, preservation, and diff gates**

```powershell
.venv\Scripts\python.exe -m ruff check --no-cache .
.venv\Scripts\python.exe -m mypy --no-incremental src
.venv\Scripts\python.exe -m pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py -q -p no:cacheprovider
git -c safe.directory=C:/Users/wei/Desktop/招聘/signal-diagnosis-agent diff --check 605c8a8
```

Also scan every new untracked plan/spec/report file for trailing whitespace
before staging, because `git diff --check` does not inspect untracked files.

- [ ] **Step 4: Run packaging and clean-environment gates**

```powershell
$env:PIP_CONFIG_FILE='NUL'
$env:PIP_INDEX_URL='https://pypi.org/simple'
.venv\Scripts\python.exe scripts/verify_phase5_wheel.py
$py311 = (uv python find 3.11).Trim()
$py312 = (uv python find 3.12).Trim()
.venv\Scripts\python.exe scripts/verify_phase5_local_matrix.py --python-3.11 $py311 --python-3.12 $py312
```

Missing interpreters, build failures, or dependency failures are gate failures,
not skips.

- [ ] **Step 5: Verify protected evidence directly**

Run T-CX001–T-CX003, T-CX146–T-CX148, and T-CX166 again. Confirm the two
profile SHA-256 values remain:

```text
profile_s1_distortion: 1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1
profile_s1_contextual_comparison: c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58
```

Confirm no historical run file appears in `git diff --name-only`.

- [ ] **Step 6: Write the acceptance report**

Record exact HEAD, prompt version/SHA, policy, both profile hashes, focused and
full pytest counts, Ruff/mypy/architecture/preservation results, wheel
contents, 3.11/3.12 matrix results, shadow replay summary, and protected-file
hashes. State whether each gate passed.

Only if every gate above is green may the report conclude:

```text
v9_7_harness_complete
```

Always state: no real model was run; development and validation performance are
not evaluated; a new 20-slot development confirmation needs separate written
authorization.

- [ ] **Step 7: Final scope audit and review or commit**

```powershell
git -c safe.directory=C:/Users/wei/Desktop/招聘/signal-diagnosis-agent status --short
git -c safe.directory=C:/Users/wei/Desktop/招聘/signal-diagnosis-agent diff --name-only 2f449646b90fc1d660147e1f17cc5df0a2cf4bf1
```

The output must exclude the user-owned investigation report, the validation
tree, all historical run directories, WAVs, credentials, caches, and build
artifacts.

Suggested commit:

```text
docs: record v9.7 deterministic closure acceptance
```

Stop after review. Do not run a real model, enter validation, push, or claim
performance improvement.
