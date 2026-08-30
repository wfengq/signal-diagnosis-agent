"""Phase 4.1 planner v6 product-boundary runtime tests (T198)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent import prompts as prompts_mod
from signal_diag.agent.models import AgentRunResult, CallToolDecision
from signal_diag.agent.planner import RealLLMPlanner
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.evaluation.recording import RecordingPlanner
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import (
    SyntheticCase,
    generate_combined_distortion,
    generate_harmonic_sine,
)
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
_V6_VERSION = "v0.2-s1-planner-6"
_S1_DSP_TOOLS = frozenset({"detect_clipping", "analyze_harmonic_distortion"})
_ASSESSMENT = {
    "task_type": "distortion_analysis",
    "objective": "Determine whether clipping or harmonic distortion explains the signal.",
    "hypotheses": ["clipping", "harmonic_distortion"],
}
_FORBIDDEN_EVALUATION_FIELDS = {
    "causal_faults",
    "knowledge_policy",
    "sufficient_evidence_sets",
    "observable_conditions",
    "acceptable_outcomes",
    "held_out",
    "expected_faults",
    "expected_outcomes",
    "target_metrics",
}
_GENERATOR_INPUT_TOKENS = (
    "harmonic_ratios",
    "clip_level",
    "fundamental_amplitude",
)
_FFT_KEYS = frozenset({"frequencies_hz", "magnitude_db"})
_CASE_ID_PATTERN = re.compile(r"case_v11_")
_USER_REQUEST = "Why does this signal sound distorted?"


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


class _V6PolicyFakeCompletions:
    """Observation-driven fake that returns exactly one JSON decision per create()."""

    def __init__(
        self,
        *,
        first_tool: str,
        collect_other_family: bool = False,
        knowledge_tags: tuple[str, ...] = ("inconclusive",),
        knowledge_query: str = "inconclusive harmonic analysis",
    ) -> None:
        self._first_tool = first_tool
        self._collect_other_family = collect_other_family
        self._knowledge_tags = knowledge_tags
        self._knowledge_query = knowledge_query
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        context = json.loads(kwargs["messages"][1]["content"])["planner_context"]
        payload = _v6_policy_decision(
            context,
            first_tool=self._first_tool,
            collect_other_family=self._collect_other_family,
            knowledge_tags=self._knowledge_tags,
            knowledge_query=self._knowledge_query,
        )
        return _FakeResponse([_FakeChoice(_FakeMessage(json.dumps(payload)))])


@dataclass
class _FakeChat:
    completions: _V6PolicyFakeCompletions


@dataclass
class _FakeClient:
    chat: _FakeChat


def _v6_client(
    *,
    first_tool: str,
    collect_other_family: bool = False,
    knowledge_tags: tuple[str, ...] = ("inconclusive",),
    knowledge_query: str = "inconclusive harmonic analysis",
) -> _FakeClient:
    completions = _V6PolicyFakeCompletions(
        first_tool=first_tool,
        collect_other_family=collect_other_family,
        knowledge_tags=knowledge_tags,
        knowledge_query=knowledge_query,
    )
    return _FakeClient(_FakeChat(completions))


def _json_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for nested in value.values():
            keys.update(_json_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_json_keys(item))
    return keys


def _has_long_numeric_array(value: object, *, min_len: int = 32) -> bool:
    if isinstance(value, list):
        if len(value) >= min_len and all(isinstance(item, (int, float)) for item in value):
            return True
        return any(_has_long_numeric_array(item, min_len=min_len) for item in value)
    if isinstance(value, dict):
        return any(_has_long_numeric_array(item, min_len=min_len) for item in value.values())
    return False


def _has_invalid_harmonic(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "analyze_harmonic_distortion"
        and item.get("validity") == "not_applicable"
        for item in evidence
    )


def _flatten_evaluations(context: dict[str, Any]) -> list[dict[str, Any]]:
    batches = list(context.get("rule_evaluation_batches") or [])
    return [item for batch in batches for item in batch.get("evaluations", [])]


def _ids_for_tool(evidence: list[dict[str, Any]], tool_name: str) -> list[str]:
    return [
        item["evidence_id"]
        for item in evidence
        if item.get("source_tool") == tool_name
    ]


def _valid_thd_values(evidence: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for item in evidence:
        if (
            item.get("source_tool") == "analyze_harmonic_distortion"
            and item.get("metric") == "thd_percent"
            and item.get("validity") == "valid"
            and isinstance(item.get("value"), (int, float))
        ):
            values.append(float(item["value"]))
    return values


def _clipping_detected(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "detect_clipping"
        and item.get("metric") == "clipping_detected"
        and item.get("value") is True
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


def _v6_finish(context: dict[str, Any]) -> dict[str, Any]:
    evidence = list(context.get("evidence") or [])
    evaluations = _flatten_evaluations(context)
    retrievals = list(context.get("knowledge_retrievals") or [])
    evidence_ids = [item["evidence_id"] for item in evidence]
    clip_ids = _ids_for_tool(evidence, "detect_clipping")
    harm_ids = [
        item["evidence_id"]
        for item in evidence
        if item.get("source_tool") == "analyze_harmonic_distortion"
        and item.get("validity") == "valid"
    ]
    matched_knowledge = [
        item["retrieval_id"] for item in retrievals if item.get("matches")
    ]
    clip_fail = [
        item
        for item in evaluations
        if item.get("judgment") == "fail"
        and (
            "clip" in item.get("rule_id", "")
            or "flat_top" in item.get("rule_id", "")
        )
    ]
    thd_evals = [
        item for item in evaluations if item.get("rule_id") == "rule_thd_acceptable"
    ]
    harmonic_valid_evals = [
        item
        for item in evaluations
        if item.get("rule_id") == "rule_harmonic_analysis_valid"
    ]
    thd_present = bool(_valid_thd_values(evidence))
    thd_pass = any(item.get("judgment") == "pass" for item in thd_evals)
    clipping_present = _clipping_detected(evidence) or bool(clip_fail)

    if _has_invalid_harmonic(evidence):
        na_or_applicable = [
            item["evaluation_id"]
            for item in evaluations
            if item.get("judgment") in {"not_applicable", "fail", "pass"}
        ]
        return {
            "decision_type": "finish",
            "outcome": "inconclusive",
            "claims": [
                {
                    "claim_id": "claim_inconclusive",
                    "fault_type": "inconclusive",
                    "statement": (
                        "Harmonic analysis is not applicable; no numeric THD was "
                        "fabricated."
                    ),
                    "evidence_refs": evidence_ids,
                    "rule_refs": na_or_applicable,
                    "knowledge_refs": matched_knowledge,
                }
            ],
            "confidence_label": "low",
            "limitations": [
                "Harmonic analysis is invalid or not applicable on this signal."
            ],
        }

    claims: list[dict[str, Any]] = []
    if clipping_present:
        claims.append(
            {
                "claim_id": "claim_clip",
                "fault_type": "clipping",
                "statement": "Clipping evidence supports a clipping diagnosis.",
                "evidence_refs": clip_ids,
                "rule_refs": [item["evaluation_id"] for item in clip_fail],
            }
        )
    if thd_present:
        harm_rule_ids = [
            item["evaluation_id"] for item in thd_evals + harmonic_valid_evals
        ]
        statement = (
            "Harmonic distortion is present in the deterministic Evidence, while "
            "the observed THD still satisfies the configured 5% demonstration "
            "limit (rule PASS)."
            if thd_pass
            else "Harmonic evidence supports a harmonic-distortion diagnosis."
        )
        harm_refs = list(harm_ids)
        if clip_ids and not clipping_present:
            harm_refs.extend(clip_ids)
        claims.append(
            {
                "claim_id": "claim_harm",
                "fault_type": "harmonic_distortion",
                "statement": statement,
                "evidence_refs": harm_refs,
                "rule_refs": harm_rule_ids,
            }
        )
    if claims:
        return {
            "decision_type": "finish",
            "outcome": "supported_fault",
            "claims": claims,
            "confidence_label": "high",
        }
    return {
        "decision_type": "finish",
        "outcome": "no_supported_fault",
        "claims": [
            {
                "claim_id": "claim_clean",
                "fault_type": "no_supported_fault",
                "statement": (
                    "Clipping and harmonic distortion are both ruled out; the "
                    "supported cause set is empty."
                ),
                "evidence_refs": evidence_ids,
                "rule_refs": [item["evaluation_id"] for item in evaluations],
            }
        ],
        "confidence_label": "high",
    }


def _v6_policy_decision(
    context: dict[str, Any],
    *,
    first_tool: str,
    collect_other_family: bool,
    knowledge_tags: tuple[str, ...],
    knowledge_query: str,
) -> dict[str, Any]:
    observations = list(context.get("observations") or [])
    evidence = list(context.get("evidence") or [])
    batches = list(context.get("rule_evaluation_batches") or [])
    retrievals = list(context.get("knowledge_retrievals") or [])
    observed_tools = {item.get("tool_name") for item in observations}
    if not observations:
        return _call_tool_payload(first_tool, first=True)
    if collect_other_family:
        remaining = _S1_DSP_TOOLS - observed_tools
        if remaining:
            return _call_tool_payload(min(remaining), first=False)
    if evidence and not batches:
        return {
            "decision_type": "evaluate_rules",
            "profile_id": "profile_s1_distortion",
            "evidence_refs": [item["evidence_id"] for item in evidence],
            "purpose": "evaluate current S1 evidence under the configured profile",
        }
    if _has_invalid_harmonic(evidence) and not retrievals:
        return {
            "decision_type": "retrieve_knowledge",
            "query_text": knowledge_query,
            "tags": list(knowledge_tags),
            "purpose": "explain invalid or not applicable harmonic analysis",
        }
    return _v6_finish(context)


def _assert_no_leakage(calls: list[dict[str, Any]]) -> None:
    assert calls
    for kwargs in calls:
        messages = kwargs["messages"]
        assert len(messages) >= 2
        for message in messages:
            content = message["content"]
            lowered = content.lower()
            assert _CASE_ID_PATTERN.search(content) is None
            for token in _GENERATOR_INPUT_TOKENS:
                assert token not in lowered
            for token in _FORBIDDEN_EVALUATION_FIELDS:
                assert token not in lowered
        user_payload = json.loads(messages[1]["content"])
        keys = _json_keys(user_payload)
        lowered_keys = {key.lower() for key in keys}
        assert "samples" not in keys
        assert "waveform" not in lowered_keys
        for token in _FFT_KEYS:
            assert token not in keys
        for token in _GENERATOR_INPUT_TOKENS:
            assert token not in keys
        for token in _FORBIDDEN_EVALUATION_FIELDS:
            assert token not in lowered_keys
        assert not _has_long_numeric_array(user_payload)


def _assert_same_run_refs(result: AgentRunResult) -> None:
    assert result.diagnosis is not None
    evidence_ids = {item.evidence_id for item in result.evidence}
    rule_ids = {
        evaluation.evaluation_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    matched_knowledge_ids = {
        item.retrieval_id
        for item in result.knowledge_retrievals
        if item.matches
    }
    empty_knowledge_ids = knowledge_ids - matched_knowledge_ids
    for claim in result.diagnosis.claims:
        assert set(claim.evidence_refs) <= evidence_ids
        assert set(claim.rule_refs) <= rule_ids
        assert set(claim.knowledge_refs) <= knowledge_ids
        assert set(claim.knowledge_refs).isdisjoint(empty_knowledge_ids)
        assert claim.evidence_refs


def _assert_runtime_does_not_force_actions(
    result: AgentRunResult,
    recording: RecordingPlanner,
) -> None:
    planned_tools = [
        record.decision.call.tool_name
        for record in recording.records
        if isinstance(record.decision, CallToolDecision)
    ]
    observed_tools = [observation.tool_name for observation in result.observations]
    assert observed_tools == planned_tools
    planned_kinds = [
        getattr(record.decision, "decision_type", None)
        for record in recording.records
        if record.decision is not None
    ]
    assert planned_kinds
    assert "finish" in planned_kinds


def _boundary_harmonic_case() -> SyntheticCase:
    return generate_harmonic_sine(
        fundamental_hz=200.0,
        harmonic_ratios={2: 0.04999999},
        sample_rate_hz=48_000,
        duration_s=2.0,
        fundamental_amplitude=0.48,
    )


def _combined_case() -> SyntheticCase:
    return generate_combined_distortion(
        fundamental_hz=150.0,
        harmonic_ratios={3: 0.16},
        clip_level=0.70,
        sample_rate_hz=48_000,
        duration_s=2.0,
        fundamental_amplitude=0.88,
    )


def _strong_harmonic_case() -> SyntheticCase:
    return generate_harmonic_sine(
        fundamental_hz=425.0,
        harmonic_ratios={2: 0.085},
        sample_rate_hz=48_000,
        duration_s=2.0,
        fundamental_amplitude=0.48,
    )


async def _run_v6_product_path(
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
    assert type(planner) is RealLLMPlanner
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
    result = await runtime.run(signal_id=signal_id, user_request=_USER_REQUEST)
    calls = client.chat.completions.calls
    assert calls
    first_system = calls[0]["messages"][0]["content"]
    assert first_system == prompts_mod._S1_PROMPT_V6.system_prompt
    assert "phase 4.1 observation-driven decision policy" not in first_system.lower()
    for kwargs in calls:
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["prompt_version"] == _V6_VERSION
        assert kwargs["messages"][0]["content"] == prompts_mod._S1_PROMPT_V6.system_prompt
    _assert_no_leakage(calls)
    _assert_same_run_refs(result)
    _assert_runtime_does_not_force_actions(result, recording)
    return result, recording


def _rule_judgments(result: AgentRunResult) -> dict[str, str]:
    return {
        evaluation.rule_id: evaluation.judgment
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }


def _causal_fault_types(result: AgentRunResult) -> list[str]:
    assert result.diagnosis is not None
    return [claim.fault_type for claim in result.diagnosis.claims]


def _dsp_tool_names(result: AgentRunResult) -> tuple[str, ...]:
    return tuple(
        observation.tool_name
        for observation in result.observations
        if observation.tool_name in _S1_DSP_TOOLS
    )


@pytest.mark.asyncio
async def test_t198_boundary_harmonic_pass_still_supports_harmonic(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = store_synthetic_case(repository, _boundary_harmonic_case())
    client = _v6_client(first_tool="analyze_harmonic_distortion")
    result, _recording = await _run_v6_product_path(repository, signal_id, client)
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert "harmonic_distortion" in _causal_fault_types(result)
    assert "no_supported_fault" not in _causal_fault_types(result)
    judgments = _rule_judgments(result)
    assert judgments["rule_thd_acceptable"] == "pass"
    thd_values = [
        float(item.value)
        for item in result.evidence
        if item.metric == "thd_percent" and item.validity == "valid"
    ]
    assert thd_values
    assert 4.999 <= thd_values[0] <= 5.001
    harm_claims = [
        claim
        for claim in result.diagnosis.claims
        if claim.fault_type == "harmonic_distortion"
    ]
    assert harm_claims
    statement = harm_claims[0].statement.lower()
    assert "pass" in statement
    assert "configured" in statement
    assert harm_claims[0].rule_refs
    assert harm_claims[0].evidence_refs


@pytest.mark.asyncio
async def test_t198_combined_does_not_stop_after_clipping_only(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = store_synthetic_case(repository, _combined_case())
    client = _v6_client(first_tool="detect_clipping", collect_other_family=True)
    result, recording = await _run_v6_product_path(repository, signal_id, client)
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    dsp_tools = _dsp_tool_names(result)
    assert dsp_tools[0] == "detect_clipping"
    assert "analyze_harmonic_distortion" in dsp_tools
    finish_records = [
        record
        for record in recording.records
        if record.decision is not None
        and getattr(record.decision, "decision_type", None) == "finish"
    ]
    assert finish_records
    finish_tools = {
        observation.tool_name
        for observation in finish_records[0].context.observations
        if observation.tool_name in _S1_DSP_TOOLS
    }
    assert finish_tools == _S1_DSP_TOOLS
    faults = set(_causal_fault_types(result))
    assert faults >= {"clipping", "harmonic_distortion"}
    assert "no_supported_fault" not in faults
    clip_claim = next(
        claim for claim in result.diagnosis.claims if claim.fault_type == "clipping"
    )
    harm_claim = next(
        claim
        for claim in result.diagnosis.claims
        if claim.fault_type == "harmonic_distortion"
    )
    assert clip_claim.evidence_refs
    assert harm_claim.evidence_refs
    assert set(clip_claim.evidence_refs).isdisjoint(set(harm_claim.evidence_refs))


@pytest.mark.asyncio
async def test_t198_invalid_harmonic_is_traceable_inconclusive(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)
    client = _v6_client(first_tool="analyze_harmonic_distortion")
    result, recording = await _run_v6_product_path(repository, signal_id, client)
    assert result.status == "inconclusive"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.diagnosis.limitations
    assert any(item.validity == "not_applicable" for item in result.evidence)
    assert result.knowledge_retrievals
    assert result.knowledge_retrievals[0].matches
    claims = result.diagnosis.claims
    assert claims
    assert all(claim.fault_type == "inconclusive" for claim in claims)
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    for claim in claims:
        assert claim.evidence_refs
        assert claim.knowledge_refs
        assert set(claim.knowledge_refs) <= knowledge_ids
        assert claim.rule_refs
    judgments = _rule_judgments(result)
    assert "not_applicable" in judgments.values()
    kinds = [
        getattr(record.decision, "decision_type", None)
        for record in recording.records
        if record.decision is not None
    ]
    assert kinds.index("evaluate_rules") < kinds.index("retrieve_knowledge")
    assert kinds.index("retrieve_knowledge") < kinds.index("finish")


@pytest.mark.asyncio
async def test_t198_strong_harmonic_cites_clean_clipping_without_no_fault_cause(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = store_synthetic_case(repository, _strong_harmonic_case())
    client = _v6_client(
        first_tool="analyze_harmonic_distortion",
        collect_other_family=True,
    )
    result, _recording = await _run_v6_product_path(repository, signal_id, client)
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert set(_dsp_tool_names(result)) == _S1_DSP_TOOLS
    judgments = _rule_judgments(result)
    assert judgments["rule_thd_acceptable"] == "fail"
    assert judgments["rule_clipping_detected_absent"] == "pass"
    faults = _causal_fault_types(result)
    assert "harmonic_distortion" in faults
    assert "no_supported_fault" not in faults
    clip_ids = {
        item.evidence_id
        for item in result.evidence
        if item.source_tool == "detect_clipping"
    }
    assert clip_ids
    harm_claim = next(
        claim
        for claim in result.diagnosis.claims
        if claim.fault_type == "harmonic_distortion"
    )
    assert clip_ids & set(harm_claim.evidence_refs)
    assert harm_claim.rule_refs
