"""Checkpoint J — RecordingPlanner and chronological trace (T141–T148)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import (
    AgentDecision,
    AgentRunResult,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    Observation,
    PlannerContext,
    PlannerOutputError,
    RetrieveKnowledgeDecision,
    ScriptExhaustedError,
    StructuredDiagnosis,
    TaskAssessment,
    ToolHistoryEntry,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import normalize_tool_arguments
from signal_diag.evaluation.models import (
    BaselineDiagnosis,
    BaselineRunResult,
    BenchmarkConfig,
    EvaluationCase,
    PlannerDecisionRecord,
    ProviderUsage,
)
from signal_diag.evaluation.recording import RecordingPlanner, assemble_evaluation_trace
from signal_diag.knowledge.models import (
    KnowledgeChunk,
    KnowledgeMatch,
    KnowledgeRetrievalResult,
)
from signal_diag.rules.models import RuleEvaluation, RuleEvaluationBatch
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.contracts import (
    ClippingOutput,
    HarmonicComponentOutput,
    HarmonicDistortionInput,
    HarmonicDistortionOutput,
    SpectrumOutput,
    SpectrumPeakOutput,
)
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.registry import get_tool_descriptors
from tests.evaluation.conftest import make_evaluation_case


def _planner_context() -> PlannerContext:
    return PlannerContext(
        run_id="run_recording",
        user_request="Why distorted?",
        signal_meta=SignalMeta(
            signal_id="sig_recording",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=96_000,
            duration_s=2.0,
            original_dtype="float32",
        ),
        task_assessment=None,
        observations=(),
        evidence=(),
        tool_history=(),
        available_tools=get_tool_descriptors(),
        remaining_tool_calls=8,
        remaining_planner_retries=2,
        no_progress_count=0,
    )


def _call_decision(purpose: str = "inspect clipping") -> CallToolDecision:
    return CallToolDecision(
        task_assessment=TaskAssessment(
            task_type="distortion_analysis",
            objective="inspect clipping",
        ),
        call=DetectClippingCall(args=ClippingInput()),
        purpose=purpose,
    )


class _IdentityPlanner:
    def __init__(self, decision: AgentDecision) -> None:
        self.decision = decision
        self.received: list[PlannerContext] = []

    async def decide(self, context: PlannerContext) -> AgentDecision:
        self.received.append(context)
        return self.decision


class _RaisePlanner:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def decide(self, context: PlannerContext) -> AgentDecision:
        raise self.error


@pytest.mark.asyncio
async def test_t141_transparent_planner_delegation() -> None:
    context = _planner_context()
    decision = _call_decision()
    inner = _IdentityPlanner(decision)
    planner = RecordingPlanner(inner)

    returned = await planner.decide(context)

    assert inner.received == [context]
    assert inner.received[0] is context
    assert returned is decision
    records = planner.records
    assert len(records) == 1
    assert records[0].decision_index == 0
    assert records[0].status == "decision"
    assert records[0].decision is decision
    assert records[0].context is context
    assert records[0].provider_usage is None

    scripted_decision = _call_decision("scripted")
    scripted = ScriptedPlanner(
        [ScriptedStep(expected_observation_count=0, decision=scripted_decision)]
    )
    wrapped_scripted = RecordingPlanner(scripted)
    scripted_returned = await wrapped_scripted.decide(context)
    assert scripted_returned is scripted_decision
    assert wrapped_scripted.records[0].decision is scripted_decision


@pytest.mark.asyncio
async def test_t142_planner_call_snapshot_order() -> None:
    context = _planner_context()
    success_decision = _call_decision("first")
    output_error = PlannerOutputError("delegate output error")
    runtime_error = RuntimeError("delegate boom")

    class _SequencePlanner:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, context: PlannerContext) -> AgentDecision:
            self.calls += 1
            if self.calls == 1:
                return success_decision
            if self.calls == 2:
                return {"not": "an AgentDecision"}  # type: ignore[return-value]
            if self.calls == 3:
                raise output_error
            raise runtime_error

    planner = RecordingPlanner(_SequencePlanner())

    first = await planner.decide(context)
    assert first is success_decision
    snapshot_after_success = planner.records
    assert isinstance(snapshot_after_success, tuple)
    assert len(snapshot_after_success) == 1

    with pytest.raises(PlannerOutputError) as invalid_info:
        await planner.decide(context)
    invalid_error = invalid_info.value
    assert invalid_error is not output_error
    assert "invalid AgentDecision" in str(invalid_error)

    with pytest.raises(PlannerOutputError) as raised_output_info:
        await planner.decide(context)
    assert raised_output_info.value is output_error

    with pytest.raises(RuntimeError) as raised_runtime_info:
        await planner.decide(context)
    assert raised_runtime_info.value is runtime_error

    records = planner.records
    assert records is not snapshot_after_success
    assert len(snapshot_after_success) == 1
    assert [item.decision_index for item in records] == [0, 1, 2, 3]
    assert [item.record_id for item in records] == [
        "decision_000000",
        "decision_000001",
        "decision_000002",
        "decision_000003",
    ]
    assert [item.status for item in records] == [
        "decision",
        "planner_output_error",
        "planner_output_error",
        "planner_error",
    ]
    assert records[0].decision is success_decision
    assert records[1].decision is None
    assert records[1].error_type == "PlannerOutputError"
    assert records[1].error_message
    assert records[2].error_type == "PlannerOutputError"
    assert records[2].error_message == "delegate output error"
    assert records[3].error_type == "RuntimeError"
    assert records[3].error_message == "delegate boom"
    assert all(item.context is context for item in records)
    assert all(item.provider_usage is None for item in records)
    assert all(item.latency_ms is not None and item.latency_ms >= 0.0 for item in records)

    with pytest.raises(ValidationError):
        records[0].decision_index = 99  # type: ignore[misc]

    exhausted = ScriptExhaustedError("scripted planner has no remaining steps")
    exhausted_planner = RecordingPlanner(_RaisePlanner(exhausted))
    with pytest.raises(ScriptExhaustedError) as exhausted_info:
        await exhausted_planner.decide(context)
    assert exhausted_info.value is exhausted
    exhausted_record = exhausted_planner.records[0]
    assert exhausted_record.decision_index == 0
    assert exhausted_record.status == "planner_error"
    assert exhausted_record.error_type == "ScriptExhaustedError"


def _signal_meta() -> SignalMeta:
    return SignalMeta(
        signal_id="sig_recording",
        source_type="generated",
        sample_rate_hz=48_000,
        channels=1,
        num_samples=96_000,
        duration_s=2.0,
        original_dtype="float32",
    )


def _empty_context() -> PlannerContext:
    return PlannerContext(
        run_id="run_recording",
        user_request="Why distorted?",
        signal_meta=_signal_meta(),
        task_assessment=None,
        observations=(),
        evidence=(),
        tool_history=(),
        available_tools=get_tool_descriptors(),
        remaining_tool_calls=8,
        remaining_planner_retries=2,
        no_progress_count=0,
    )


def _benchmark_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id="bench_task4",
        dataset_id="s1-distortion-synthetic",
        dataset_version="1.0.0",
        rule_profile_id="profile_s1_distortion",
        rule_profile_version="1.0.0-demo",
        started_at_utc=datetime(2026, 8, 29, 9, 0, tzinfo=UTC),
    )


def _task_assessment() -> TaskAssessment:
    return TaskAssessment(task_type="distortion_analysis", objective="inspect clipping")


def _clipping_call() -> DetectClippingCall:
    return DetectClippingCall(args=ClippingInput())


def _clipping_decision() -> CallToolDecision:
    return CallToolDecision(
        task_assessment=_task_assessment(),
        call=_clipping_call(),
        purpose="inspect clipping",
    )


def _rules_decision() -> EvaluateRulesDecision:
    return EvaluateRulesDecision(
        task_assessment=_task_assessment(),
        profile_id="profile_s1_distortion",
        evidence_refs=("ev_clip_001",),
        purpose="apply official profile",
    )


def _knowledge_decision() -> RetrieveKnowledgeDecision:
    return RetrieveKnowledgeDecision(
        task_assessment=_task_assessment(),
        query_text="clipping",
        tags=("clipping",),
        purpose="retrieve clipping notes",
    )


def _claim() -> DiagnosisClaim:
    return DiagnosisClaim(
        claim_id="claim_001",
        fault_type="no_supported_fault",
        statement="No supported clipping fault.",
        evidence_refs=("ev_clip_001",),
        rule_refs=("ruleval_clip_001",),
        knowledge_refs=("know_clip_001",),
    )


def _finish_decision() -> FinishDecision:
    return FinishDecision(
        task_assessment=_task_assessment(),
        outcome="no_supported_fault",
        claims=(_claim(),),
        confidence_label="high",
    )


def _clipping_output() -> ClippingOutput:
    return ClippingOutput(
        detected=False,
        clipping_ratio=0.0,
        clipped_samples=0,
        clipping_events=0,
        longest_event_samples=0,
        peak_abs=0.5,
        full_scale_detected=False,
        flat_top_detected=False,
    )


def _clipping_evidence() -> Evidence:
    return Evidence(
        evidence_id="ev_clip_001",
        source_tool="detect_clipping",
        call_id="call_clip_001",
        metric="clipping_ratio",
        value=0.0,
        unit="ratio",
        channel="mixdown",
    )


def _clipping_observation() -> Observation:
    call = _clipping_call()
    return Observation(
        observation_id="obs_clip_001",
        call_id="call_clip_001",
        tool_name="detect_clipping",
        normalized_arguments=normalize_tool_arguments(call),
        purpose="inspect clipping",
        status="success",
        result=_clipping_output(),
        evidence_refs=("ev_clip_001",),
    )


def _rule_batch() -> RuleEvaluationBatch:
    evaluation = RuleEvaluation(
        evaluation_id="ruleval_clip_001",
        rule_id="rule_clipping_ratio_acceptable",
        judgment="pass",
        observed_value=0.0,
        comparator="lte",
        threshold=0.01,
        profile_id="profile_s1_distortion",
        profile_version="1.0.0-demo",
        evidence_refs=("ev_clip_001",),
    )
    return RuleEvaluationBatch(
        batch_id="rulebatch_clip_001",
        profile_id="profile_s1_distortion",
        profile_version="1.0.0-demo",
        evaluations=(evaluation,),
    )


def _retrieval() -> KnowledgeRetrievalResult:
    chunk = KnowledgeChunk(
        chunk_id="chunk_clipping_000",
        document_id="doc_clipping",
        title="Clipping evidence",
        excerpt="Flat tops support clipping.",
    )
    match = KnowledgeMatch(
        document_id="doc_clipping",
        chunk_id="chunk_clipping_000",
        matched_terms=("clipping",),
    )
    return KnowledgeRetrievalResult(
        retrieval_id="know_clip_001",
        query_text="clipping",
        query_tags=("clipping",),
        matches=(match,),
        chunks=(chunk,),
    )


def _decision_record(
    index: int,
    context: PlannerContext,
    decision: AgentDecision,
    *,
    provider_usage: ProviderUsage | None = None,
) -> PlannerDecisionRecord:
    return PlannerDecisionRecord(
        record_id=f"decision_{index:06d}",
        decision_index=index,
        context=context,
        status="decision",
        decision=decision,
        latency_ms=1.0,
        provider_usage=provider_usage,
    )


def _error_record(index: int, context: PlannerContext) -> PlannerDecisionRecord:
    return PlannerDecisionRecord(
        record_id=f"decision_{index:06d}",
        decision_index=index,
        context=context,
        status="planner_error",
        error_type="RuntimeError",
        error_message="transient planner failure",
        latency_ms=1.0,
    )


def _advance(
    context: PlannerContext,
    *,
    observations: tuple[Observation, ...] | None = None,
    evidence: tuple[Evidence, ...] | None = None,
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...] | None = None,
    knowledge_retrievals: tuple[KnowledgeRetrievalResult, ...] | None = None,
) -> PlannerContext:
    updates: dict[str, Any] = {}
    if observations is not None:
        updates["observations"] = observations
    if evidence is not None:
        updates["evidence"] = evidence
    if rule_evaluation_batches is not None:
        updates["rule_evaluation_batches"] = rule_evaluation_batches
    if knowledge_retrievals is not None:
        updates["knowledge_retrievals"] = knowledge_retrievals
    return context.model_copy(update=updates)


def _diagnosis(
    *,
    observations: tuple[Observation, ...],
    evidence: tuple[Evidence, ...],
    batches: tuple[RuleEvaluationBatch, ...],
    retrievals: tuple[KnowledgeRetrievalResult, ...],
    claims: tuple[DiagnosisClaim, ...] | None = None,
) -> StructuredDiagnosis:
    return StructuredDiagnosis(
        run_id="run_recording",
        task_type="distortion_analysis",
        outcome="no_supported_fault",
            claims=(_claim(),) if claims is None else claims,
        confidence_label="high",
        limitations=(),
        termination_reason="planner_finished",
        tool_call_count=len(observations),
        rule_evaluation_batches=batches,
        knowledge_retrievals=retrievals,
    )


def _agent_result(
    *,
    observations: tuple[Observation, ...],
    evidence: tuple[Evidence, ...],
    batches: tuple[RuleEvaluationBatch, ...],
    retrievals: tuple[KnowledgeRetrievalResult, ...],
    claims: tuple[DiagnosisClaim, ...] | None = None,
) -> AgentRunResult:
    return AgentRunResult(
        run_id="run_recording",
        status="success",
        diagnosis=_diagnosis(
            observations=observations,
            evidence=evidence,
            batches=batches,
            retrievals=retrievals,
            claims=claims,
        ),
        observations=observations,
        evidence=evidence,
        tool_history=(),
        termination_reason="planner_finished",
        rule_evaluation_batches=batches,
        knowledge_retrievals=retrievals,
    )


def _full_agent_chain() -> tuple[
    EvaluationCase,
    tuple[PlannerDecisionRecord, ...],
    AgentRunResult,
    BenchmarkConfig,
]:
    case = make_evaluation_case("clean", case_id="case_trace_dev_01")
    empty = _empty_context()
    observation = _clipping_observation()
    evidence = _clipping_evidence()
    batch = _rule_batch()
    retrieval = _retrieval()
    after_tool = _advance(empty, observations=(observation,), evidence=(evidence,))
    after_rules = _advance(after_tool, rule_evaluation_batches=(batch,))
    after_knowledge = _advance(after_rules, knowledge_retrievals=(retrieval,))
    records = (
        _decision_record(0, empty, _clipping_decision()),
        _error_record(1, after_tool),
        _decision_record(2, after_tool, _rules_decision()),
        _decision_record(3, after_rules, _knowledge_decision()),
        _decision_record(4, after_knowledge, _finish_decision()),
    )
    result = _agent_result(
        observations=(observation,),
        evidence=(evidence,),
        batches=(batch,),
        retrievals=(retrieval,),
    )
    return case, records, result, _benchmark_config()


def _assemble_agent(
    records: tuple[PlannerDecisionRecord, ...],
    result: AgentRunResult,
    *,
    case: EvaluationCase | None = None,
):
    return assemble_evaluation_trace(
        case if case is not None else make_evaluation_case("clean", case_id="case_trace_dev_01"),
        records,
        result,
        _benchmark_config(),
        run_slot=1,
        execution_path="agent",
    )


def test_t143_tool_delta_assembly() -> None:
    empty = _empty_context()
    observation = _clipping_observation()
    evidence = _clipping_evidence()
    after_tool = _advance(empty, observations=(observation,), evidence=(evidence,))
    claims = (
        DiagnosisClaim(
            claim_id="claim_001",
            fault_type="no_supported_fault",
            statement="No supported clipping fault.",
            evidence_refs=("ev_clip_001",),
        ),
    )
    finish = FinishDecision(
        task_assessment=_task_assessment(),
        outcome="no_supported_fault",
        claims=claims,
        confidence_label="high",
    )
    records = (
        _decision_record(0, empty, _clipping_decision()),
        _decision_record(1, after_tool, finish),
    )
    result = _agent_result(
        observations=(observation,),
        evidence=(evidence,),
        batches=(),
        retrievals=(),
        claims=claims,
    )
    trace = _assemble_agent(records, result)

    assert [event.event_index for event in trace.events] == list(range(len(trace.events)))
    assert trace.events[0].event_type == "planner_call"
    assert trace.events[1].event_type == "observation"
    assert trace.events[1].caused_by_decision_index == 0
    assert trace.events[1].observation is observation
    assert trace.events[1].evidence == (evidence,)
    assert [event.event_type for event in trace.events] == [
        "planner_call",
        "observation",
        "planner_call",
    ]


def test_t144_rule_delta_assembly() -> None:
    empty = _empty_context()
    observation = _clipping_observation()
    evidence = _clipping_evidence()
    batch = _rule_batch()
    after_tool = _advance(empty, observations=(observation,), evidence=(evidence,))
    after_rules = _advance(after_tool, rule_evaluation_batches=(batch,))
    claims = (
        DiagnosisClaim(
            claim_id="claim_001",
            fault_type="no_supported_fault",
            statement="No supported clipping fault.",
            evidence_refs=("ev_clip_001",),
            rule_refs=("ruleval_clip_001",),
        ),
    )
    finish = FinishDecision(
        task_assessment=_task_assessment(),
        outcome="no_supported_fault",
        claims=claims,
        confidence_label="high",
    )
    records = (
        _decision_record(0, empty, _clipping_decision()),
        _decision_record(1, after_tool, _rules_decision()),
        _decision_record(2, after_rules, finish),
    )
    result = _agent_result(
        observations=(observation,),
        evidence=(evidence,),
        batches=(batch,),
        retrievals=(),
        claims=claims,
    )
    trace = _assemble_agent(records, result)
    types = [event.event_type for event in trace.events]
    assert types == [
        "planner_call",
        "observation",
        "planner_call",
        "rule_evaluation",
        "planner_call",
    ]
    assert [event.event_index for event in trace.events] == [0, 1, 2, 3, 4]
    assert trace.events[3].caused_by_decision_index == 1
    assert trace.events[3].batch is batch


def test_t145_knowledge_delta_assembly() -> None:
    case, records, result, config = _full_agent_chain()
    trace = assemble_evaluation_trace(
        case,
        records,
        result,
        config,
        run_slot=1,
        execution_path="agent",
    )
    types = [event.event_type for event in trace.events]
    assert types == [
        "planner_call",
        "observation",
        "planner_call",
        "planner_call",
        "rule_evaluation",
        "planner_call",
        "knowledge_retrieval",
        "planner_call",
    ]
    assert [event.event_index for event in trace.events] == list(range(8))
    assert trace.events[6].event_type == "knowledge_retrieval"
    assert trace.events[6].caused_by_decision_index == 3
    assert trace.events[6].retrieval is result.knowledge_retrievals[0]
    assert trace.events[2].event_type == "planner_call"
    assert trace.events[2].record.status == "planner_error"


def test_t146_final_result_assembly() -> None:
    case, records, result, config = _full_agent_chain()
    trace = assemble_evaluation_trace(
        case,
        records,
        result,
        config,
        run_slot=1,
        execution_path="agent",
    )
    assert trace.trace_id.startswith("trace_")
    assert trace.case_id == case.case_id
    assert trace.run_slot == 1
    assert trace.execution_path == "agent"
    assert trace.result is result
    assert [event.event_index for event in trace.events] == list(range(len(trace.events)))
    assert trace.events[-1].event_type == "planner_call"
    assert trace.events[-1].record.decision.decision_type == "finish"
    claim = result.diagnosis.claims[0] if result.diagnosis is not None else None
    assert claim is not None
    evidence_ids = {
        item.evidence_id
        for event in trace.events
        if event.event_type == "observation"
        for item in event.evidence
    }
    rule_ids = {
        evaluation.evaluation_id
        for event in trace.events
        if event.event_type == "rule_evaluation"
        for evaluation in event.batch.evaluations
    }
    knowledge_ids = {
        event.retrieval.retrieval_id
        for event in trace.events
        if event.event_type == "knowledge_retrieval"
    }
    assert set(claim.evidence_refs) <= evidence_ids
    assert set(claim.rule_refs) <= rule_ids
    assert set(claim.knowledge_refs) <= knowledge_ids

    clipping_obs = _clipping_observation()
    harmonic_obs = Observation(
        observation_id="obs_harm_001",
        call_id="call_harm_001",
        tool_name="analyze_harmonic_distortion",
        normalized_arguments=HarmonicDistortionInput().model_dump(mode="json"),
        purpose="inspect harmonics",
        status="success",
        result=HarmonicDistortionOutput(
            valid=True,
            invalid_reason=None,
            fundamental_frequency_hz=200.0,
            thd_percent=1.0,
            components=(
                HarmonicComponentOutput(
                    order=2,
                    measured_frequency_hz=400.0,
                    relative_amplitude=0.1,
                    relative_magnitude_db=-20.0,
                ),
            ),
        ),
        evidence_refs=("ev_harm_001",),
    )
    clipping_ev = _clipping_evidence()
    harmonic_ev = Evidence(
        evidence_id="ev_harm_001",
        source_tool="analyze_harmonic_distortion",
        call_id="call_harm_001",
        metric="thd_percent",
        value=1.0,
        unit="percent",
        channel="mixdown",
    )
    batch = _rule_batch()
    baseline_claim = DiagnosisClaim(
        claim_id="claim_baseline_001",
        fault_type="no_supported_fault",
        statement="Baseline found no supported fault.",
        evidence_refs=("ev_clip_001", "ev_harm_001"),
        rule_refs=("ruleval_clip_001",),
    )
    baseline = BaselineRunResult(
        run_id="baseline_trace_001",
        status="success",
        diagnosis=BaselineDiagnosis(
            run_id="baseline_trace_001",
            outcome="no_supported_fault",
            claims=(baseline_claim,),
            confidence_label="medium",
            tool_call_count=2,
            rule_evaluation_batches=(batch,),
        ),
        observations=(clipping_obs, harmonic_obs),
        evidence=(clipping_ev, harmonic_ev),
        tool_history=(),
        completion_reason="baseline_completed",
        rule_evaluation_batches=(batch,),
    )
    baseline_trace = assemble_evaluation_trace(
        case,
        (),
        baseline,
        config,
        run_slot=2,
        execution_path="fixed_pipeline",
    )
    assert baseline_trace.execution_path == "fixed_pipeline"
    assert [event.event_type for event in baseline_trace.events] == [
        "observation",
        "observation",
        "rule_evaluation",
    ]
    assert "planner_call" not in [event.event_type for event in baseline_trace.events]
    assert baseline_trace.events[0].caused_by_decision_index == 0
    assert baseline_trace.events[1].caused_by_decision_index == 1
    assert baseline_trace.events[2].caused_by_decision_index == 2


def _history_with_payload(payload: dict[str, Any]) -> ToolHistoryEntry:
    arguments = dict(normalize_tool_arguments(_clipping_call()))
    arguments.update(payload)
    return ToolHistoryEntry(
        call_id="call_clip_001",
        tool_name="detect_clipping",
        normalized_arguments=arguments,
        purpose="inspect clipping",
        status="success",
    )


@pytest.mark.parametrize(
    "kind",
    [
        "missing_observation",
        "duplicate_observation",
        "reordered_observation",
        "evidence_ref_mismatch",
        "two_rule_batches",
        "unresolved_claim_ref",
        "grouped_history",
    ],
)
def test_t147_ambiguity_rejection(kind: str) -> None:
    case, records, result, config = _full_agent_chain()
    if kind == "missing_observation":
        empty = records[0].context
        records = (
            records[0],
            _decision_record(1, empty, _finish_decision()),
        )
        result = _agent_result(
            observations=(),
            evidence=(),
            batches=(),
            retrievals=(),
            claims=(
                DiagnosisClaim(
                    claim_id="claim_001",
                    fault_type="inconclusive",
                    statement="Missing tool artifact.",
                ),
            ),
        )
    elif kind == "duplicate_observation":
        extra = records[1].context.observations[0].model_copy(
            update={"observation_id": "obs_clip_002", "call_id": "call_clip_002"}
        )
        duplicated = records[1].context.model_copy(
            update={"observations": records[1].context.observations + (extra,)}
        )
        records = (records[0], records[1].model_copy(update={"context": duplicated})) + records[2:]
    elif kind == "reordered_observation":
        first = records[1].context.observations[0]
        second = first.model_copy(
            update={"observation_id": "obs_clip_000", "call_id": "call_clip_000"}
        )
        after_first = records[1].context.model_copy(update={"observations": (first,)})
        after_second = records[3].context.model_copy(
            update={"observations": (second, first)}
        )
        second_tool = CallToolDecision(
            task_assessment=_task_assessment(),
            call=_clipping_call(),
            purpose="inspect clipping again",
        )
        records = (
            records[0],
            _decision_record(1, after_first, second_tool),
            records[2].model_copy(update={"context": after_second}),
        )
    elif kind == "evidence_ref_mismatch":
        mismatched = records[1].context.observations[0].model_copy(
            update={"evidence_refs": ("ev_other_001",)}
        )
        updated = records[1].context.model_copy(update={"observations": (mismatched,)})
        records = (records[0], records[1].model_copy(update={"context": updated})) + records[2:]
        result = result.model_copy(update={"observations": (mismatched,)})
    elif kind == "two_rule_batches":
        extra_batch = records[3].context.rule_evaluation_batches[0].model_copy(
            update={"batch_id": "rulebatch_clip_002"}
        )
        doubled = records[3].context.model_copy(
            update={
                "rule_evaluation_batches": records[3].context.rule_evaluation_batches
                + (extra_batch,)
            }
        )
        records = records[:3] + (records[3].model_copy(update={"context": doubled}),) + records[4:]
    elif kind == "unresolved_claim_ref":
        bad_claim = _claim().model_copy(update={"evidence_refs": ("ev_missing_001",)})
        finish = FinishDecision(
            task_assessment=_task_assessment(),
            outcome="no_supported_fault",
            claims=(bad_claim,),
            confidence_label="high",
        )
        records = records[:-1] + (_decision_record(4, records[-1].context, finish),)
        result = result.model_copy(
            update={
                "diagnosis": result.diagnosis.model_copy(update={"claims": (bad_claim,)})
                if result.diagnosis is not None
                else None
            }
        )
    elif kind == "grouped_history":
        records = ()
    with pytest.raises(ValueError):
        assemble_evaluation_trace(
            case,
            records,
            result,
            config,
            run_slot=1,
            execution_path="agent",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"samples": [0.1, -0.2, 0.3]},
        {"waveform": [0.0, 1.0]},
        {"fft": [float(index) for index in range(64)]},
        {"magnitudes": [0.01] * 32},
        {"api_key": "sk-leaked-credential"},
        {"authorization": "Bearer secret-token"},
        {"raw_response": {"choices": [{"text": "provider body"}]}},
        {"provider_response": "<raw provider body>"},
    ],
)
def test_t148_trace_safety_and_optional_usage(payload: dict[str, Any]) -> None:
    case, records, result, config = _full_agent_chain()
    leaked_context = records[1].context.model_copy(
        update={"tool_history": (_history_with_payload(payload),)}
    )
    leaked_records = (records[0], records[1].model_copy(update={"context": leaked_context})) + records[
        2:
    ]
    with pytest.raises(ValueError):
        assemble_evaluation_trace(
            case,
            leaked_records,
            result,
            config,
            run_slot=1,
            execution_path="agent",
        )

    safe_case, safe_records, safe_result, safe_config = _full_agent_chain()
    spectrum = SpectrumOutput(
        frequency_resolution_hz=1.0,
        dominant_frequency_hz=200.0,
        spectral_centroid_hz=210.0,
        spectral_peaks=(
            SpectrumPeakOutput(frequency_hz=200.0, relative_magnitude_db=0.0),
        ),
    )
    compact = safe_result.observations[0].model_copy(update={"result": spectrum})
    compact_records = tuple(
        record.model_copy(
            update={
                "context": record.context.model_copy(
                    update={
                        "observations": (compact,)
                        if record.context.observations
                        else record.context.observations
                    }
                )
            }
        )
        for record in safe_records
    )
    compact_result = safe_result.model_copy(update={"observations": (compact,)})
    usage_records = (
        compact_records[0].model_copy(
            update={
                "provider_usage": ProviderUsage(
                    input_tokens=9,
                    output_tokens=None,
                    total_tokens=None,
                    cost_usd=None,
                )
            }
        ),
        *compact_records[1:],
    )
    trace = assemble_evaluation_trace(
        safe_case,
        usage_records,
        compact_result,
        safe_config,
        run_slot=1,
        execution_path="agent",
    )
    dumped = trace.model_dump(mode="json")
    serialized = str(dumped)
    assert '"samples":' not in serialized
    assert '"waveform":' not in serialized
    assert '"api_key":' not in serialized
    assert '"raw_response":' not in serialized
    assert trace.events[1].observation.result == spectrum
    assert trace.provider_usage is not None
    assert trace.provider_usage.input_tokens == 9
    assert trace.provider_usage.output_tokens is None
    assert trace.provider_usage.total_tokens is None
    assert trace.provider_usage.cost_usd is None

    unused = assemble_evaluation_trace(
        safe_case,
        compact_records,
        compact_result,
        safe_config,
        run_slot=1,
        execution_path="agent",
    )
    assert unused.provider_usage is None
