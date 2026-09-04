"""Unit tests for RealLLMPlanner parsing and configuration (no network)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from signal_diag.agent.models import (
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    EvaluateRulesDecision,
    FinishDecision,
    PlannerContext,
    PlannerOutputError,
    RetrieveKnowledgeDecision,
    TaskAssessment,
)
from signal_diag.agent.planner import (
    PROMPT_VERSION,
    RealLLMPlanner,
    _missing_credentials_message,
    _normalize_agent_decision_payload,
    _parse_agent_decision,
)
from signal_diag.agent.prompts import _S1_PROMPT_V4
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors


def _planner_context(**overrides: object) -> PlannerContext:
    base = {
        "run_id": "run_llm_test",
        "user_request": "Why distorted?",
        "signal_meta": SignalMeta(
            signal_id="sig_llm",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=96_000,
            duration_s=2.0,
            original_dtype="float32",
        ),
        "task_assessment": None,
        "observations": (),
        "evidence": (),
        "tool_history": (),
        "available_tools": get_tool_descriptors(),
        "remaining_tool_calls": 8,
        "remaining_planner_retries": 2,
        "no_progress_count": 0,
    }
    base.update(overrides)
    return PlannerContext(**base)  # type: ignore[arg-type]


def _valid_call_tool_payload() -> dict[str, object]:
    return {
        "decision_type": "call_tool",
        "task_assessment": {
            "task_type": "distortion_analysis",
            "objective": "inspect clipping",
        },
        "call": {
            "tool_name": "detect_clipping",
            "args": {},
        },
        "purpose": "check clipping evidence",
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


class _FakeCompletions:
    def __init__(self, content: str | None) -> None:
        self._content = content
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_kwargs = kwargs
        return _FakeResponse([_FakeChoice(_FakeMessage(self._content))])


class _FakeChat:
    def __init__(self, content: str | None) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str | None) -> None:
        self.chat = _FakeChat(content)


def test_parse_agent_decision_accepts_valid_call_tool() -> None:
    decision = _parse_agent_decision(json.dumps(_valid_call_tool_payload()))
    assert isinstance(decision, CallToolDecision)
    assert decision.call.tool_name == "detect_clipping"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "call_tool": {
                "name": "detect_clipping",
                "purpose": "Check for clipping distortion in the signal.",
                "task_assessment": {
                    "task_type": "distortion_analysis",
                    "objective": "Identify clipping as a common cause.",
                },
            }
        },
        {
            "decision_type": "call_tool",
            "task_assessment": {
                "task_type": "distortion_analysis",
                "hypotheses": ["checking for clipping."],
            },
            "call_tool": {
                "decision_type": "call_tool",
                "name": "detect_clipping",
                "purpose": "checking for clipping.",
            },
        },
        {
            "decision_type": "call_tool",
            "task_assessment": {
                "task_type": "distortion_analysis",
                "objective": "Assess distortion affecting the signal.",
            },
            "call_tool": {
                "decision_type": "call_tool",
                "name": "detect_clipping",
                "purpose": "Detect clipping affecting the signal.",
            },
        },
    ],
)
def test_parse_agent_decision_normalizes_eval_trace_call_tool_patterns(
    payload: dict[str, object],
) -> None:
    decision = _parse_agent_decision(json.dumps(payload))
    assert isinstance(decision, CallToolDecision)
    assert decision.call.tool_name == "detect_clipping"
    assert decision.purpose
    assert decision.task_assessment is not None
    assert decision.task_assessment.objective


def test_normalize_agent_decision_payload_maps_finish_wrapper() -> None:
    normalized = _normalize_agent_decision_payload(
        {
            "finish": {
                "outcome": "no_supported_fault",
                "claims": [
                    {
                        "claim_id": "claim_clean",
                        "fault_type": "no_supported_fault",
                        "statement": "no clipping or harmonic evidence",
                        "evidence_refs": ["ev_none_001"],
                    }
                ],
                "confidence_label": "medium",
            }
        }
    )
    assert normalized["decision_type"] == "finish"
    assert normalized["outcome"] == "no_supported_fault"
    assert normalized["claims"][0]["evidence_refs"] == ["ev_none_001"]


def test_parse_agent_decision_accepts_finish_with_evidence_refs() -> None:
    payload = {
        "decision_type": "finish",
        "outcome": "supported_fault",
        "claims": [
            {
                "claim_id": "claim_clip_1",
                "fault_type": "clipping",
                "statement": "Clipping metrics exceed threshold.",
                "evidence_refs": ["ev_clip_001"],
            }
        ],
        "confidence_label": "high",
    }
    decision = _parse_agent_decision(json.dumps(payload))
    assert isinstance(decision, FinishDecision)
    assert decision.claims[0].evidence_refs == ("ev_clip_001",)


def test_parse_agent_decision_preserves_valid_payload() -> None:
    payload = _valid_call_tool_payload()
    normalized = _normalize_agent_decision_payload(payload)
    assert normalized == payload
    decision = _parse_agent_decision(json.dumps(payload))
    assert isinstance(decision, CallToolDecision)
    assert decision.call.tool_name == "detect_clipping"


def test_parse_agent_decision_rejects_invalid_json() -> None:
    with pytest.raises(PlannerOutputError, match="non-JSON"):
        _parse_agent_decision("not json")


def test_parse_agent_decision_rejects_invalid_schema() -> None:
    payload = _valid_call_tool_payload()
    payload["call"] = {"tool_name": "unknown_tool", "args": {}}
    with pytest.raises(PlannerOutputError, match="invalid AgentDecision"):
        _parse_agent_decision(json.dumps(payload))


@pytest.mark.asyncio
async def test_real_llm_planner_parses_mocked_response() -> None:
    client = _FakeClient(json.dumps(_valid_call_tool_payload()))
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    decision = await planner.decide(_planner_context())
    assert isinstance(decision, CallToolDecision)
    assert isinstance(decision.call, DetectClippingCall)
    assert decision.call.args == ClippingInput()
    assert client.chat.completions.last_kwargs is not None
    assert client.chat.completions.last_kwargs["model"] == "deepseek-v4-flash"
    assert client.chat.completions.last_kwargs["response_format"] == {
        "type": "json_object",
    }
    user_content = client.chat.completions.last_kwargs["messages"][1]["content"]
    assert json.loads(user_content)["prompt_version"] == "v0.3-s1-planner-9.6"
    assert "sig_llm" in user_content
    assert "frequencies_hz" not in user_content


@pytest.mark.asyncio
async def test_real_llm_planner_raises_on_empty_model_content() -> None:
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        client=_FakeClient(None),
    )
    with pytest.raises(PlannerOutputError, match="empty content"):
        await planner.decide(_planner_context())


@pytest.mark.asyncio
async def test_real_llm_planner_raises_without_provider() -> None:
    planner = RealLLMPlanner()
    with pytest.raises(PlannerOutputError, match="no LLM provider selected"):
        await planner.decide(_planner_context())


@pytest.mark.asyncio
async def test_real_llm_planner_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    planner = RealLLMPlanner(provider="deepseek")
    with pytest.raises(PlannerOutputError, match="DEEPSEEK_API_KEY"):
        await planner.decide(_planner_context())


def test_missing_credentials_message_is_explicit() -> None:
    message = _missing_credentials_message()
    assert "DEEPSEEK_API_KEY" in message
    assert "ScriptedPlanner" in message


def test_prompt_version_is_planner_9_0() -> None:
    assert PROMPT_VERSION == "v0.3-s1-planner-9.6"
    assert _S1_PROMPT_V4.version == "v0.2-s1-planner-4"


@pytest.mark.parametrize(
    ("alias_field", "alias_value", "expected_limitations"),
    [
        (
            "reason",
            "Fundamental frequency estimate is invalid.",
            ("Fundamental frequency estimate is invalid.",),
        ),
        (
            "summary",
            [
                "THD metrics are not applicable.",
                "No reliable harmonic evidence.",
            ],
            (
                "THD metrics are not applicable.",
                "No reliable harmonic evidence.",
            ),
        ),
        (
            "limitation",
            "Noise-only input prevents reliable pitch tracking.",
            ("Noise-only input prevents reliable pitch tracking.",),
        ),
    ],
)
def test_normalize_inconclusive_lifts_limitations_from_aliases(
    alias_field: str,
    alias_value: str | list[str],
    expected_limitations: tuple[str, ...],
) -> None:
    payload: dict[str, object] = {
        "decision_type": "finish",
        "outcome": "inconclusive",
        "claims": [],
        "confidence_label": "low",
        alias_field: alias_value,
    }
    normalized = _normalize_agent_decision_payload(payload)
    assert normalized["limitations"] == expected_limitations
    assert alias_field not in normalized


def test_normalize_inconclusive_preserves_existing_limitations() -> None:
    payload = {
        "decision_type": "finish",
        "outcome": "inconclusive",
        "claims": [],
        "confidence_label": "low",
        "limitations": ["Already provided limitation."],
        "reason": "Should not override existing limitations.",
    }
    normalized = _normalize_agent_decision_payload(payload)
    assert normalized["limitations"] == ["Already provided limitation."]
    assert "reason" in normalized


def test_parse_agent_decision_accepts_inconclusive_with_reason_alias() -> None:
    payload = {
        "decision_type": "finish",
        "outcome": "inconclusive",
        "claims": [],
        "confidence_label": "low",
        "reason": "Invalid F0 prevents harmonic analysis.",
    }
    decision = _parse_agent_decision(json.dumps(payload))
    assert isinstance(decision, FinishDecision)
    assert decision.outcome == "inconclusive"
    assert decision.limitations == ("Invalid F0 prevents harmonic analysis.",)


def test_normalize_no_supported_fault_finish_wrapper() -> None:
    normalized = _normalize_agent_decision_payload(
        {
            "finish": {
                "outcome": "no_supported_fault",
                "claims": [
                    {
                        "claim_id": "claim_clean",
                        "fault_type": "no_supported_fault",
                        "statement": "No clipping or harmonic distortion detected.",
                        "evidence_refs": ["ev_neg_001"],
                    }
                ],
                "confidence_label": "high",
            }
        }
    )
    assert normalized["decision_type"] == "finish"
    assert normalized["outcome"] == "no_supported_fault"
    assert normalized["claims"][0]["fault_type"] == "no_supported_fault"


def test_parse_agent_decision_accepts_no_supported_fault_finish() -> None:
    payload = {
        "decision_type": "finish",
        "outcome": "no_supported_fault",
        "claims": [
            {
                "claim_id": "claim_clean_1",
                "fault_type": "no_supported_fault",
                "statement": "Negative clipping and harmonic evidence.",
                "evidence_refs": ["ev_neg_001"],
            }
        ],
        "confidence_label": "high",
    }
    decision = _parse_agent_decision(json.dumps(payload))
    assert isinstance(decision, FinishDecision)
    assert decision.outcome == "no_supported_fault"
    assert decision.claims[0].fault_type == "no_supported_fault"


def test_normalize_does_not_convert_supported_fault_to_no_supported_fault() -> None:
    payload = {
        "decision_type": "finish",
        "outcome": "supported_fault",
        "claims": [
            {
                "claim_id": "claim_clip_1",
                "fault_type": "clipping",
                "statement": "Clipping detected.",
                "evidence_refs": ["ev_clip_001"],
            }
        ],
        "confidence_label": "high",
        "reason": "Negative evidence wording must not change outcome.",
    }
    normalized = _normalize_agent_decision_payload(payload)
    assert normalized["outcome"] == "supported_fault"
    assert "limitations" not in normalized


@pytest.mark.asyncio
async def test_real_llm_planner_parses_finish_decision() -> None:
    payload = {
        "decision_type": "finish",
        "task_assessment": {
            "task_type": "distortion_analysis",
            "objective": "conclude diagnosis",
        },
        "outcome": "no_supported_fault",
        "claims": (
            {
                "claim_id": "claim_clean",
                "fault_type": "no_supported_fault",
                "statement": "no clipping or harmonic evidence",
                "evidence_refs": (),
            },
        ),
        "confidence_label": "medium",
    }
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        client=_FakeClient(json.dumps(payload)),
    )
    decision = await planner.decide(
        _planner_context(
            task_assessment=TaskAssessment(
                task_type="distortion_analysis",
                objective="conclude diagnosis",
            )
        )
    )
    assert isinstance(decision, FinishDecision)
    assert decision.outcome == "no_supported_fault"


def test_parse_agent_decision_accepts_evaluate_rules_wrapper() -> None:
    decision = _parse_agent_decision(
        json.dumps(
            {
                "evaluate_rules": {
                    "profile_id": "profile_s1_distortion",
                    "evidence_refs": ["ev_clip_001"],
                    "purpose": "apply configured limits",
                }
            }
        )
    )
    assert isinstance(decision, EvaluateRulesDecision)
    assert decision.profile_id == "profile_s1_distortion"


def test_parse_agent_decision_accepts_retrieve_knowledge_wrapper() -> None:
    decision = _parse_agent_decision(
        json.dumps(
            {
                "retrieve_knowledge": {
                    "query_text": "clipping harmonic distortion",
                    "tags": ["clipping"],
                    "purpose": "explain findings",
                }
            }
        )
    )
    assert isinstance(decision, RetrieveKnowledgeDecision)
    assert decision.query_text == "clipping harmonic distortion"
