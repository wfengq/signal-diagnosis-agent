"""Checkpoint M — deterministic full-manifest acceptance (T167–T172)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from signal_diag.agent.models import (
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    RetrieveKnowledgeDecision,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedStep
from signal_diag.evaluation import (
    FixedPipelineBaseline,
    TargetBands,
    aggregate_benchmark,
    assemble_evaluation_trace,
    score_evaluation_trace,
)
from signal_diag.evaluation.models import (
    AttemptRecord,
    BenchmarkConfig,
    DatasetManifest,
    EvaluationCase,
    EvaluationTrace,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerDecisionEvent,
    RuleEvaluationEvent,
)
from signal_diag.evaluation.runner import (
    _official_dependencies,
    _run_deterministic_harness,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from tests.evaluation.conftest import CANONICAL_MANIFEST

_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_HARMONIC_ONLY_CASES = frozenset({"case_dev_harmonic_01"})
_HARMONIC_THEN_CLIPPING_CLEAN = "case_held_clean_02"
_DSP_TOOLS = frozenset(
    {
        "detect_clipping",
        "analyze_harmonic_distortion",
        "analyze_spectrum",
        "estimate_fundamental",
    }
)


def _tool_step(
    tool_name: str,
    *,
    observation_count: int,
    first: bool = False,
    required_metrics: tuple[str, ...] = (),
) -> ScriptedStep:
    if tool_name == "detect_clipping":
        call: Any = DetectClippingCall(args=ClippingInput())
    elif tool_name == "analyze_harmonic_distortion":
        call = AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput())
    else:
        raise ValueError(tool_name)
    return ScriptedStep(
        expected_observation_count=observation_count,
        required_evidence_metrics=required_metrics,
        decision=CallToolDecision(
            task_assessment=_ASSESSMENT if first else None,
            call=call,
            purpose=f"collect {tool_name} evidence",
        ),
    )


def _rules_step(observation_count: int) -> ScriptedStep:
    return ScriptedStep(
        expected_observation_count=observation_count,
        decision=EvaluateRulesDecision(
            profile_id="profile_s1_distortion",
            evidence_refs=(),
            purpose="apply configured S1 demonstration limits",
        ),
    )


def _knowledge_step(case: EvaluationCase, observation_count: int) -> ScriptedStep:
    return ScriptedStep(
        expected_observation_count=observation_count,
        decision=RetrieveKnowledgeDecision(
            query_text=" ".join(case.knowledge_tags) or "inconclusive analysis",
            tags=case.knowledge_tags,
            purpose="retrieve required knowledge for the current diagnosis",
        ),
    )


def _finish_template(case: EvaluationCase) -> FinishDecision:
    if case.category == "invalid_noise":
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_inconclusive",
                    fault_type="inconclusive",
                    statement="Harmonic analysis is not applicable on this signal.",
                ),
            ),
            confidence_label="low",
            limitations=(
                "harmonic analysis is not applicable; no THD value was fabricated",
            ),
        )
    if case.category == "clean":
        claims = (
            DiagnosisClaim(
                claim_id="claim_clean",
                fault_type="no_supported_fault",
                statement="Configured clipping and THD limits pass on this signal.",
            ),
        )
        outcome = "no_supported_fault"
    elif case.category == "clipping":
        claims = (
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping evidence supports a clipping diagnosis.",
            ),
        )
        outcome = "supported_fault"
    elif case.category == "harmonic":
        claims = (
            DiagnosisClaim(
                claim_id="claim_harm",
                fault_type="harmonic_distortion",
                statement="Harmonic evidence supports a harmonic-distortion diagnosis.",
            ),
        )
        outcome = "supported_fault"
    else:
        claims = (
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping evidence supports a clipping diagnosis.",
            ),
            DiagnosisClaim(
                claim_id="claim_harm",
                fault_type="harmonic_distortion",
                statement="Harmonic evidence supports a harmonic-distortion diagnosis.",
            ),
        )
        outcome = "supported_fault"
    return FinishDecision(
        outcome=outcome,  # type: ignore[arg-type]
        claims=claims,
        confidence_label="high",
    )


def _tool_route(case: EvaluationCase) -> tuple[str, ...]:
    if case.category == "clipping":
        return ("detect_clipping",)
    if case.category == "invalid_noise":
        return ("analyze_harmonic_distortion",)
    if case.category == "harmonic":
        if case.case_id in _HARMONIC_ONLY_CASES:
            return ("analyze_harmonic_distortion",)
        return ("detect_clipping", "analyze_harmonic_distortion")
    if case.category == "clean" and case.case_id == _HARMONIC_THEN_CLIPPING_CLEAN:
        return ("analyze_harmonic_distortion", "detect_clipping")
    return ("detect_clipping", "analyze_harmonic_distortion")


def build_case_script(case: EvaluationCase) -> tuple[ScriptedStep, ...]:
    """Build a legal route from the case's declared sufficient alternatives."""
    tools = _tool_route(case)
    steps: list[ScriptedStep] = []
    for index, tool_name in enumerate(tools):
        steps.append(
            _tool_step(tool_name, observation_count=index, first=index == 0)
        )
    observations = len(tools)
    if case.category != "invalid_noise":
        steps.append(_rules_step(observations))
    if case.knowledge_policy == "required":
        steps.append(_knowledge_step(case, observations))
    steps.append(
        ScriptedStep(
            expected_observation_count=observations,
            decision=_finish_template(case),
        )
    )
    return tuple(steps)


def build_manifest_scripts(
    manifest: DatasetManifest,
) -> dict[str, tuple[ScriptedStep, ...]]:
    return {case.case_id: build_case_script(case) for case in manifest.cases}


def _dsp_tools(trace: EvaluationTrace) -> tuple[str, ...]:
    names: list[str] = []
    for event in trace.events:
        if not isinstance(event, PlannerDecisionEvent):
            continue
        decision = event.record.decision
        if isinstance(decision, CallToolDecision) and decision.call.tool_name in _DSP_TOOLS:
            names.append(decision.call.tool_name)
    return tuple(names)


def _first_tool(trace: EvaluationTrace) -> str | None:
    tools = _dsp_tools(trace)
    return tools[0] if tools else None


def _by_id(traces: tuple[EvaluationTrace, ...], case_id: str) -> EvaluationTrace:
    matched = [trace for trace in traces if trace.case_id == case_id]
    assert len(matched) == 1
    return matched[0]


def _strip_clock_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        stripped: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"latency_ms", "started_at_utc", "finished_at_utc", "benchmark_id"}:
                continue
            stripped[key] = _strip_clock_fields(value)
        return stripped
    if isinstance(payload, list):
        return [_strip_clock_fields(item) for item in payload]
    return payload


def _normalized_trace_payload(trace: EvaluationTrace) -> Any:
    return _strip_clock_fields(trace.model_dump(mode="json"))


def _normalized_score_payload(score: object) -> Any:
    return _strip_clock_fields(score.model_dump(mode="json"))  # type: ignore[attr-defined]


class _DeterministicClock:
    def __init__(self) -> None:
        self._value = 0.0

    def __call__(self) -> float:
        self._value += 0.001
        return self._value


class _DeterministicUuid:
    def __init__(self) -> None:
        self._n = 0

    def reset(self) -> None:
        self._n = 0

    def uuid4(self) -> UUID:
        self._n += 1
        return UUID(int=self._n)


class PrivilegedRepository:
    def __init__(self, inner: object) -> None:
        self._inner = inner

    @property
    def causal_faults(self) -> object:
        raise AssertionError("baseline must not read manifest causal_faults")

    @property
    def matched_control(self) -> object:
        raise AssertionError("baseline must not read matched-control data")

    def put(self, record: object) -> None:
        self._inner.put(record)  # type: ignore[attr-defined]

    def get(self, signal_id: str) -> object:
        return self._inner.get(signal_id)  # type: ignore[attr-defined]

    def exists(self, signal_id: str) -> bool:
        return self._inner.exists(signal_id)  # type: ignore[attr-defined]

    def remove(self, signal_id: str) -> None:
        self._inner.remove(signal_id)  # type: ignore[attr-defined]

    def list_meta(self) -> list[object]:
        return self._inner.list_meta()  # type: ignore[attr-defined]


def _attempts_for(
    traces: tuple[EvaluationTrace, ...],
    config: BenchmarkConfig,
) -> tuple[AttemptRecord, ...]:
    finished = config.started_at_utc + timedelta(milliseconds=1)
    return tuple(
        AttemptRecord(
            execution_path=trace.execution_path,
            case_id=trace.case_id,
            run_slot=trace.run_slot,
            attempt_index=1,
            status="behavior_result",
            started_at_utc=config.started_at_utc,
            finished_at_utc=finished,
        )
        for trace in traces
    )


async def _run_agent_traces(
    manifest: DatasetManifest,
    config: BenchmarkConfig,
    *,
    clock: Callable[[], float] | None = None,
) -> tuple[EvaluationTrace, ...]:
    return await _run_deterministic_harness(
        manifest,
        build_manifest_scripts(manifest),
        config,
        _clock=clock,
    )


async def _run_baseline_traces(
    manifest: DatasetManifest,
    config: BenchmarkConfig,
) -> tuple[EvaluationTrace, ...]:
    from signal_diag.evaluation.dataset import _materialize_case
    from signal_diag.signal.repository import InMemorySignalRepository

    traces: list[EvaluationTrace] = []
    for case in manifest.cases:
        inner = InMemorySignalRepository()
        repository = PrivilegedRepository(inner)
        record = _materialize_case(case, inner)
        tool_service, rule_engine, profile_loader, _index = _official_dependencies(
            inner
        )
        baseline = FixedPipelineBaseline(
            repository=repository,  # type: ignore[arg-type]
            tool_service=tool_service,
            rule_engine=rule_engine,
            profile_loader=profile_loader,
        )
        result = await baseline.run(
            signal_id=record.meta.signal_id,
            user_request=case.user_request,
        )
        traces.append(
            assemble_evaluation_trace(
                case,
                (),
                result,
                config,
                run_slot=1,
                execution_path="fixed_pipeline",
            )
        )
    return tuple(traces)


@pytest.fixture(scope="module")
def official_agent_traces(
    official_manifest: DatasetManifest,
) -> tuple[EvaluationTrace, ...]:
    config = BenchmarkConfig(
        benchmark_id="bench_task8_deterministic",
        dataset_id=official_manifest.dataset_id,
        dataset_version=official_manifest.version,
        rule_profile_id=official_manifest.rule_profile_id,
        rule_profile_version=official_manifest.rule_profile_version,
        started_at_utc=datetime(2026, 8, 29, 7, 0, tzinfo=UTC),
    )
    return asyncio.run(_run_agent_traces(official_manifest, config))


@pytest.mark.asyncio
async def test_non_valid_dataset_prevents_harness_start(
    official_manifest: DatasetManifest,
    deterministic_config: BenchmarkConfig,
) -> None:
    invalid = official_manifest.model_copy(update={"cases": ()})
    with pytest.raises(ValueError, match="not valid"):
        await _run_deterministic_harness(invalid, {}, deterministic_config)


@pytest.mark.asyncio
async def test_t167_scripted_full_manifest_execution(
    official_manifest: DatasetManifest,
    official_agent_traces: tuple[EvaluationTrace, ...],
) -> None:
    traces = official_agent_traces
    assert len(traces) == 24
    assert len(official_manifest.cases) == 24
    assert tuple(trace.case_id for trace in traces) == tuple(
        case.case_id for case in official_manifest.cases
    )
    for case, trace in zip(official_manifest.cases, traces, strict=True):
        assert trace.execution_path == "agent"
        assert trace.run_slot == 1
        assert trace.result.status in {"success", "inconclusive"}
        assert trace.result.termination_reason == "planner_finished"
        assert trace.result.diagnosis is not None
        if case.category in {"clipping", "combined"}:
            assert trace.result.diagnosis.outcome in {
                *case.acceptable_outcomes,
                "no_supported_fault",
            }
        else:
            assert trace.result.diagnosis.outcome in case.acceptable_outcomes
        assert any(
            isinstance(event, ObservationEvent) and event.evidence
            for event in trace.events
        )


def test_t168_alternative_legal_routes(
    official_manifest: DatasetManifest,
    official_agent_traces: tuple[EvaluationTrace, ...],
) -> None:
    traces = official_agent_traces
    cases = {case.case_id: case for case in official_manifest.cases}
    clipping_started = any(
        cases[trace.case_id].category == "clipping"
        and _first_tool(trace) == "detect_clipping"
        for trace in traces
    )
    harmonic_started = any(
        cases[trace.case_id].category == "harmonic"
        and _first_tool(trace) == "analyze_harmonic_distortion"
        for trace in traces
    )
    assert clipping_started
    assert harmonic_started

    thd_only = _by_id(traces, "case_dev_harmonic_01")
    clipping_and_thd = _by_id(traces, "case_held_harmonic_01")
    assert _dsp_tools(thd_only) == ("analyze_harmonic_distortion",)
    assert _dsp_tools(clipping_and_thd) == (
        "detect_clipping",
        "analyze_harmonic_distortion",
    )
    assert _dsp_tools(thd_only) != _dsp_tools(clipping_and_thd)
    assert thd_only.result.diagnosis is not None
    assert clipping_and_thd.result.diagnosis is not None
    assert thd_only.result.diagnosis.outcome == clipping_and_thd.result.diagnosis.outcome
    assert (
        thd_only.result.diagnosis.outcome
        in cases["case_dev_harmonic_01"].acceptable_outcomes
    )


def test_t169_same_run_traceability(
    official_manifest: DatasetManifest,
    official_agent_traces: tuple[EvaluationTrace, ...],
) -> None:
    cases = {case.case_id: case for case in official_manifest.cases}
    for trace in official_agent_traces:
        evidence_ids: set[str] = set()
        rule_ids: set[str] = set()
        knowledge_ids: set[str] = set()
        for event in trace.events:
            if isinstance(event, ObservationEvent):
                evidence_ids.update(item.evidence_id for item in event.evidence)
            elif isinstance(event, RuleEvaluationEvent):
                rule_ids.update(
                    item.evaluation_id for item in event.batch.evaluations
                )
            elif isinstance(event, KnowledgeRetrievalEvent):
                knowledge_ids.add(event.retrieval.retrieval_id)
        diagnosis = trace.result.diagnosis
        assert diagnosis is not None
        for claim in diagnosis.claims:
            assert set(claim.evidence_refs) <= evidence_ids
            assert set(claim.rule_refs) <= rule_ids
            assert set(claim.knowledge_refs) <= knowledge_ids
        score = score_evaluation_trace(cases[trace.case_id], trace)
        assert score.trace_id == trace.trace_id
        if diagnosis.outcome == "supported_fault":
            assert "ungrounded_claim" not in score.failure_codes


@pytest.mark.asyncio
async def test_t170_deterministic_repeat(
    official_manifest: DatasetManifest,
    deterministic_config: BenchmarkConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.agent import runtime as runtime_module

    uuids = _DeterministicUuid()
    monkeypatch.setattr(runtime_module.uuid, "uuid4", uuids.uuid4)

    uuids.reset()
    first = await _run_agent_traces(
        official_manifest,
        deterministic_config,
        clock=_DeterministicClock(),
    )
    uuids.reset()
    second = await _run_agent_traces(
        official_manifest,
        deterministic_config.model_copy(
            update={"benchmark_id": "bench_task8_repeat"}
        ),
        clock=_DeterministicClock(),
    )
    assert len(first) == len(second) == 24
    cases = {case.case_id: case for case in official_manifest.cases}
    for left, right in zip(first, second, strict=True):
        assert left.result.diagnosis is not None
        assert right.result.diagnosis is not None
        assert left.result.run_id == right.result.run_id
        assert left.result.diagnosis.outcome == right.result.diagnosis.outcome
        assert left.result.termination_reason == right.result.termination_reason
        assert _normalized_trace_payload(left) == _normalized_trace_payload(right)
        left_score = score_evaluation_trace(cases[left.case_id], left)
        right_score = score_evaluation_trace(cases[right.case_id], right)
        assert _normalized_score_payload(left_score) == _normalized_score_payload(
            right_score
        )


@pytest.mark.asyncio
async def test_t171_baseline_full_manifest_execution(
    official_manifest: DatasetManifest,
    deterministic_config: BenchmarkConfig,
) -> None:
    traces = await _run_baseline_traces(official_manifest, deterministic_config)
    assert len(traces) == 24
    assert tuple(trace.case_id for trace in traces) == tuple(
        case.case_id for case in official_manifest.cases
    )
    for trace in traces:
        assert trace.execution_path == "fixed_pipeline"
        assert trace.run_slot == 1
        assert trace.result.diagnosis is not None
        assert all(
            not isinstance(event, PlannerDecisionEvent) for event in trace.events
        )
        assert not any(
            isinstance(event, KnowledgeRetrievalEvent) for event in trace.events
        )


@pytest.mark.asyncio
async def test_t172_agent_baseline_comparison(
    official_manifest: DatasetManifest,
    official_agent_traces: tuple[EvaluationTrace, ...],
    deterministic_config: BenchmarkConfig,
) -> None:
    baseline_traces = await _run_baseline_traces(
        official_manifest, deterministic_config
    )
    agent_traces = tuple(
        trace.model_copy(update={"config": deterministic_config})
        for trace in official_agent_traces
    )
    traces = agent_traces + baseline_traces
    cases = {case.case_id: case for case in official_manifest.cases}
    scores = tuple(
        score_evaluation_trace(cases[trace.case_id], trace) for trace in traces
    )
    report = aggregate_benchmark(
        official_manifest,
        traces,
        scores,
        _attempts_for(traces, deterministic_config),
        deterministic_config,
        TargetBands(),
        harness_status="pending",
    )
    assert report.agent_metrics is not None
    assert report.baseline_metrics is not None
    assert report.agent_metrics.run_count == 16
    assert report.baseline_metrics.run_count == 16
    # Intentionally no assertion that the Agent beats the baseline.


def test_canonical_manifest_path_exists() -> None:
    assert CANONICAL_MANIFEST.is_file()
