"""Phase 4.1 deterministic product-path acceptance with a fake LLM (T187–T190)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.models import AgentRunResult
from signal_diag.agent.planner import RealLLMPlanner
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.evaluation.models import (
    BenchmarkConfig,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    RuleEvaluationEvent,
)
from signal_diag.evaluation.recording import RecordingPlanner, assemble_evaluation_trace
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import SyntheticCase
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case
from tests.evaluation.conftest import make_evaluation_case

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
_ASSESSMENT = {
    "task_type": "distortion_analysis",
    "objective": "Determine whether clipping or harmonic distortion explains the signal.",
    "hypotheses": ["clipping", "harmonic_distortion"],
}


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


class _PolicyFakeCompletions:
    """Observation-driven fake that returns exactly one JSON decision per create()."""

    def __init__(
        self,
        *,
        first_tool: str,
        second_tool: str | None = None,
        knowledge_tags: tuple[str, ...] = ("inconclusive",),
        knowledge_query: str = "inconclusive harmonic analysis",
    ) -> None:
        self._first_tool = first_tool
        self._second_tool = second_tool
        self._knowledge_tags = knowledge_tags
        self._knowledge_query = knowledge_query
        self.last_kwargs: dict[str, Any] | None = None
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_kwargs = kwargs
        self.calls.append(kwargs)
        context = json.loads(kwargs["messages"][1]["content"])["planner_context"]
        payload = _policy_decision(
            context,
            first_tool=self._first_tool,
            second_tool=self._second_tool,
            knowledge_tags=self._knowledge_tags,
            knowledge_query=self._knowledge_query,
        )
        return _FakeResponse([_FakeChoice(_FakeMessage(json.dumps(payload)))])


@dataclass
class _FakeChat:
    completions: _PolicyFakeCompletions


@dataclass
class _FakeClient:
    chat: _FakeChat


def _policy_client(
    *,
    first_tool: str,
    second_tool: str | None = None,
    knowledge_tags: tuple[str, ...] = ("inconclusive",),
    knowledge_query: str = "inconclusive harmonic analysis",
) -> _FakeClient:
    completions = _PolicyFakeCompletions(
        first_tool=first_tool,
        second_tool=second_tool,
        knowledge_tags=knowledge_tags,
        knowledge_query=knowledge_query,
    )
    return _FakeClient(_FakeChat(completions))


def _has_invalid_harmonic(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "analyze_harmonic_distortion"
        and item.get("validity") == "not_applicable"
        for item in evidence
    )


def _call_tool_payload(tool_name: str, *, first: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision_type": "call_tool",
        "call": {"tool_name": tool_name, "args": {}},
        "purpose": f"collect {tool_name} evidence from the current request",
    }
    if first:
        payload["task_assessment"] = _ASSESSMENT
    return payload


def _finish_with_only_live_ids(context: dict[str, Any]) -> dict[str, Any]:
    evidence = list(context.get("evidence") or [])
    batches = list(context.get("rule_evaluation_batches") or [])
    retrievals = list(context.get("knowledge_retrievals") or [])
    evidence_ids = [item["evidence_id"] for item in evidence]
    evaluations = [
        item for batch in batches for item in batch.get("evaluations", [])
    ]
    fail_evals = [item for item in evaluations if item.get("judgment") == "fail"]
    pass_evals = [item for item in evaluations if item.get("judgment") == "pass"]
    relevant_knowledge = [
        item["retrieval_id"] for item in retrievals if item.get("matches")
    ]
    if _has_invalid_harmonic(evidence):
        return {
            "decision_type": "finish",
            "outcome": "inconclusive",
            "claims": [
                {
                    "claim_id": "claim_inconclusive",
                    "fault_type": "inconclusive",
                    "statement": (
                        "Harmonic analysis is not applicable; no numeric THD was fabricated."
                    ),
                    "evidence_refs": evidence_ids,
                    "rule_refs": [item["evaluation_id"] for item in evaluations],
                    "knowledge_refs": relevant_knowledge,
                }
            ],
            "confidence_label": "low",
            "limitations": [
                "Harmonic analysis is invalid or not applicable on this signal."
            ],
        }
    clipping_fail = [
        item
        for item in fail_evals
        if "clip" in item.get("rule_id", "") or "flat_top" in item.get("rule_id", "")
    ]
    harmonic_fail = [
        item
        for item in fail_evals
        if item.get("rule_id") in {"rule_thd_acceptable", "rule_harmonic_analysis_valid"}
    ]
    if clipping_fail:
        clip_ids = [
            item["evidence_id"]
            for item in evidence
            if item.get("source_tool") == "detect_clipping"
        ]
        return {
            "decision_type": "finish",
            "outcome": "supported_fault",
            "claims": [
                {
                    "claim_id": "claim_clip",
                    "fault_type": "clipping",
                    "statement": "Clipping evidence supports a clipping diagnosis.",
                    "evidence_refs": clip_ids,
                    "rule_refs": [item["evaluation_id"] for item in clipping_fail],
                }
            ],
            "confidence_label": "high",
        }
    if harmonic_fail:
        harm_ids = [
            item["evidence_id"]
            for item in evidence
            if item.get("source_tool") == "analyze_harmonic_distortion"
            and item.get("validity") == "valid"
        ]
        return {
            "decision_type": "finish",
            "outcome": "supported_fault",
            "claims": [
                {
                    "claim_id": "claim_harm",
                    "fault_type": "harmonic_distortion",
                    "statement": "Harmonic evidence supports a harmonic-distortion diagnosis.",
                    "evidence_refs": harm_ids,
                    "rule_refs": [item["evaluation_id"] for item in harmonic_fail],
                }
            ],
            "confidence_label": "high",
        }
    return {
        "decision_type": "finish",
        "outcome": "no_supported_fault",
        "claims": [
            {
                "claim_id": "claim_clean",
                "fault_type": "no_supported_fault",
                "statement": "Configured clipping and THD limits pass on this evidence.",
                "evidence_refs": evidence_ids,
                "rule_refs": [item["evaluation_id"] for item in pass_evals],
            }
        ],
        "confidence_label": "high",
    }


def _policy_decision(
    context: dict[str, Any],
    *,
    first_tool: str,
    second_tool: str | None,
    knowledge_tags: tuple[str, ...],
    knowledge_query: str,
) -> dict[str, Any]:
    observations = list(context.get("observations") or [])
    evidence = list(context.get("evidence") or [])
    batches = list(context.get("rule_evaluation_batches") or [])
    retrievals = list(context.get("knowledge_retrievals") or [])
    route_requires_second_tool = second_tool is not None
    if not observations:
        return _call_tool_payload(first_tool, first=True)
    if route_requires_second_tool and len(observations) == 1:
        assert second_tool is not None
        return _call_tool_payload(second_tool, first=False)
    if _has_invalid_harmonic(evidence) and not retrievals:
        return {
            "decision_type": "retrieve_knowledge",
            "query_text": knowledge_query,
            "tags": list(knowledge_tags),
            "purpose": "explain invalid or not applicable harmonic analysis",
        }
    if evidence and not batches:
        return {
            "decision_type": "evaluate_rules",
            "profile_id": "profile_s1_distortion",
            "evidence_refs": [item["evidence_id"] for item in evidence],
            "purpose": "evaluate current S1 evidence under the configured profile",
        }
    return _finish_with_only_live_ids(context)


def _benchmark_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id="bench_phase4_1_acceptance",
        dataset_id="s1-distortion-synthetic",
        dataset_version="1.0.0",
        rule_profile_id="profile_s1_distortion",
        rule_profile_version="1.0.0-demo",
        started_at_utc=datetime(2026, 8, 30, 0, 0, tzinfo=UTC),
    )


async def _run_product_path(
    repository: InMemorySignalRepository,
    signal_id: str,
    client: _FakeClient,
) -> tuple[AgentRunResult, RecordingPlanner]:
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    recording = RecordingPlanner(planner)
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=recording,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )
    result = await runtime.run(
        signal_id=signal_id,
        user_request="Why does this signal sound distorted?",
    )
    first_system = client.chat.completions.calls[0]["messages"][0]["content"]
    assert "phase 4.1 observation-driven decision policy" in first_system.lower()
    return result, recording


def _dsp_tool_names(result: AgentRunResult) -> tuple[str, ...]:
    return tuple(
        observation.tool_name
        for observation in result.observations
        if observation.tool_name
        in {"detect_clipping", "analyze_harmonic_distortion"}
    )


@pytest.mark.asyncio
async def test_t187_applicable_evidence_reaches_rules_and_final_rule_refs(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    client = _policy_client(first_tool="detect_clipping")
    result, recording = await _run_product_path(repository, signal_id, client)
    assert result.status == "success"
    assert result.evidence
    assert result.rule_evaluation_batches
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert any(claim.rule_refs for claim in result.diagnosis.claims)

    evaluate_indexes = [
        index
        for index, record in enumerate(recording.records)
        if record.decision is not None
        and getattr(record.decision, "decision_type", None) == "evaluate_rules"
    ]
    assert evaluate_indexes
    evaluate_index = evaluate_indexes[0]
    assert recording.records[evaluate_index].context.evidence
    later = recording.records[evaluate_index + 1 :]
    assert later
    assert later[0].context.rule_evaluation_batches


@pytest.mark.asyncio
async def test_t188_invalid_harmonic_retrieves_and_finishes_inconclusive(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)
    client = _policy_client(first_tool="analyze_harmonic_distortion")
    result, _recording = await _run_product_path(repository, signal_id, client)
    assert result.status == "inconclusive"
    assert any(item.validity == "not_applicable" for item in result.evidence)
    assert result.knowledge_retrievals
    assert result.knowledge_retrievals[0].matches
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.diagnosis.limitations
    claims = result.diagnosis.claims
    assert claims
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    evidence_ids = {item.evidence_id for item in result.evidence}
    for claim in claims:
        assert claim.evidence_refs
        assert set(claim.evidence_refs) <= evidence_ids
        assert claim.knowledge_refs
        assert set(claim.knowledge_refs) <= knowledge_ids


@pytest.mark.asyncio
async def test_t189_same_run_refs_resolve_in_assembled_trace(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)
    client = _policy_client(first_tool="analyze_harmonic_distortion")
    result, recording = await _run_product_path(repository, signal_id, client)
    case = make_evaluation_case(
        "invalid_noise",
        case_id="case_phase4_1_noise_01",
        acceptable_first_tools=("analyze_harmonic_distortion",),
    )
    trace = assemble_evaluation_trace(
        case,
        recording.records,
        result,
        _benchmark_config(),
        run_slot=1,
        execution_path="agent",
    )
    evidence_ids = {
        item.evidence_id
        for event in trace.events
        if isinstance(event, ObservationEvent)
        for item in event.evidence
    }
    rule_ids = {
        evaluation.evaluation_id
        for event in trace.events
        if isinstance(event, RuleEvaluationEvent)
        for evaluation in event.batch.evaluations
    }
    knowledge_ids = {
        event.retrieval.retrieval_id
        for event in trace.events
        if isinstance(event, KnowledgeRetrievalEvent)
    }
    assert result.diagnosis is not None
    for claim in result.diagnosis.claims:
        assert set(claim.evidence_refs) <= evidence_ids
        assert set(claim.rule_refs) <= rule_ids
        assert set(claim.knowledge_refs) <= knowledge_ids
        assert claim.evidence_refs
        assert claim.rule_refs
        assert claim.knowledge_refs


@pytest.mark.asyncio
async def test_t190_clipping_first_and_harmonic_first_are_not_a_fixed_sequence(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
    harmonic_case: SyntheticCase,
) -> None:
    clip_id = store_synthetic_case(repository, clipped_case)
    clip_client = _policy_client(first_tool="detect_clipping")
    clip_result, _clip_recording = await _run_product_path(
        repository, clip_id, clip_client
    )
    harm_id = store_synthetic_case(repository, harmonic_case)
    harm_client = _policy_client(first_tool="analyze_harmonic_distortion")
    harm_result, _harm_recording = await _run_product_path(
        repository, harm_id, harm_client
    )
    assert clip_result.status == "success"
    assert harm_result.status == "success"
    clip_tools = _dsp_tool_names(clip_result)
    harm_tools = _dsp_tool_names(harm_result)
    assert clip_tools[0] == "detect_clipping"
    assert harm_tools[0] == "analyze_harmonic_distortion"
    complete = ("detect_clipping", "analyze_harmonic_distortion")
    assert clip_tools != complete
    assert harm_tools != complete
    assert clip_tools != harm_tools


@pytest.mark.asyncio
async def test_empty_retrieval_is_never_cited(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)
    client = _policy_client(
        first_tool="analyze_harmonic_distortion",
        knowledge_tags=("no-such-tag",),
        knowledge_query="zzzznonexistent",
    )
    result, _recording = await _run_product_path(repository, signal_id, client)
    assert result.status == "inconclusive"
    assert result.evidence
    assert result.knowledge_retrievals
    assert result.knowledge_retrievals[0].matches == ()
    assert result.diagnosis is not None
    assert result.diagnosis.limitations
    cited = {
        ref
        for claim in result.diagnosis.claims
        for ref in claim.knowledge_refs
    }
    empty_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    assert cited.isdisjoint(empty_ids)


@pytest.mark.asyncio
async def test_not_applicable_rule_is_never_described_as_pass(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)
    client = _policy_client(first_tool="analyze_harmonic_distortion")
    result, _recording = await _run_product_path(repository, signal_id, client)
    assert result.status == "inconclusive"
    assert result.evidence
    assert result.diagnosis is not None
    assert result.diagnosis.limitations
    judgments = {
        evaluation.rule_id: evaluation.judgment
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    assert "not_applicable" in judgments.values()
    text = " ".join(
        [result.diagnosis.outcome, *result.diagnosis.limitations]
        + [claim.statement for claim in result.diagnosis.claims]
    )
    assert not re.search(r"\bpass\b", text, flags=re.IGNORECASE)
    for claim in result.diagnosis.claims:
        assert claim.evidence_refs
