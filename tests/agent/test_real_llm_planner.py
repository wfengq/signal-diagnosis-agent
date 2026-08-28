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
    FinishDecision,
    PlannerContext,
    PlannerOutputError,
    TaskAssessment,
)
from signal_diag.agent.planner import (
    RealLLMPlanner,
    _missing_credentials_message,
    _parse_agent_decision,
)
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
    user_content = client.chat.completions.last_kwargs["messages"][1]["content"]
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
