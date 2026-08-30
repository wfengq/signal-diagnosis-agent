"""Phase 4.1 versioned prompt identity, leakage, and dual-truth parsing (T184–T186)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pytest

from signal_diag.agent.models import FinishDecision, PlannerContext, TaskAssessment
from signal_diag.agent.planner import (
    RealLLMPlanner,
    _Phase4V4RealLLMPlanner,
    _Phase4V5RealLLMPlanner,
)
from signal_diag.agent.prompts import _S1_PROMPT_V4, _S1_PROMPT_V5
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors

_FORBIDDEN_EVALUATION_FIELDS = {
    "causal_faults",
    "knowledge_policy",
    "sufficient_evidence_sets",
    "observable_conditions",
    "acceptable_outcomes",
    "held_out",
}
_GENERATOR_INPUT_TOKENS = (
    "harmonic_ratios",
    "clip_level",
    "fundamental_amplitude",
)


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


def _planner_context(**overrides: object) -> PlannerContext:
    base = {
        "run_id": "run_phase4_1_prompt",
        "user_request": "Why distorted?",
        "signal_meta": SignalMeta(
            signal_id="sig_phase4_1",
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


def test_t184_v4_and_v5_prompt_identities_are_distinct() -> None:
    assert _S1_PROMPT_V4.version == "v0.2-s1-planner-4"
    assert _S1_PROMPT_V5.version == "v0.2-s1-planner-5"
    assert _S1_PROMPT_V4.system_prompt != _S1_PROMPT_V5.system_prompt
    assert hashlib.sha256(_S1_PROMPT_V5.system_prompt.encode()).hexdigest()


def test_t185_v5_prompt_contains_no_evaluation_truth() -> None:
    forbidden = {
        "causal_faults",
        "knowledge_policy",
        "sufficient_evidence_sets",
        "observable_conditions",
        "acceptable_outcomes",
        "held_out",
    }
    lowered = _S1_PROMPT_V5.system_prompt.lower()
    for token in forbidden:
        assert token not in lowered


@pytest.mark.asyncio
async def test_t184_active_planner_user_message_identifies_v5_only() -> None:
    client = _FakeClient(json.dumps(_valid_call_tool_payload()))
    planner = _Phase4V5RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    await planner.decide(_planner_context())
    assert client.chat.completions.last_kwargs is not None
    messages = client.chat.completions.last_kwargs["messages"]
    assert messages[0]["content"] == _S1_PROMPT_V5.system_prompt
    user_content = messages[1]["content"]
    payload = json.loads(user_content)
    assert payload["prompt_version"] == "v0.2-s1-planner-5"
    assert set(payload) == {"prompt_version", "planner_context"}
    keys = _json_keys(payload)
    assert "samples" not in keys
    assert "frequencies_hz" not in keys
    for token in _GENERATOR_INPUT_TOKENS:
        assert token not in keys
    lowered_keys = {key.lower() for key in keys}
    for token in _FORBIDDEN_EVALUATION_FIELDS:
        assert token not in lowered_keys
    lowered = user_content.lower()
    for token in _FORBIDDEN_EVALUATION_FIELDS:
        assert token not in lowered


@pytest.mark.asyncio
async def test_t184_phase4_v4_planner_sends_byte_identical_v4_identity() -> None:
    client = _FakeClient(json.dumps(_valid_call_tool_payload()))
    planner = _Phase4V4RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    await planner.decide(_planner_context())
    assert client.chat.completions.last_kwargs is not None
    messages = client.chat.completions.last_kwargs["messages"]
    assert messages[0]["content"] == _S1_PROMPT_V4.system_prompt
    payload = json.loads(messages[1]["content"])
    assert payload["prompt_version"] == "v0.2-s1-planner-4"
    assert set(payload) == {"prompt_version", "planner_context"}


def test_t186_v5_prompt_states_dual_truth_without_fixed_tool_order() -> None:
    required_meanings = (
        "distortion presence and configured acceptance are separate",
        "rule pass does not erase observed distortion",
        "evaluate_rules",
        "retrieve_knowledge",
        "invalid or not applicable",
        "stop when sufficient evidence exists",
    )
    lowered = _S1_PROMPT_V5.system_prompt.lower()
    for meaning in required_meanings:
        assert meaning in lowered
    assert "detect_clipping then analyze_harmonic_distortion" not in lowered


@pytest.mark.asyncio
async def test_t186_supported_harmonic_claim_with_pass_rule_is_not_rewritten() -> None:
    payload = {
        "decision_type": "finish",
        "task_assessment": {
            "task_type": "distortion_analysis",
            "objective": "report observed harmonic distortion and configured acceptance",
        },
        "outcome": "supported_fault",
        "claims": [
            {
                "claim_id": "claim_harm_1",
                "fault_type": "harmonic_distortion",
                "statement": (
                    "Harmonic distortion is present; a PASS rule does not erase it."
                ),
                "evidence_refs": ["ev_thd_001"],
                "rule_refs": ["ruleval_thd_pass_001"],
            }
        ],
        "confidence_label": "high",
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
                objective="report observed harmonic distortion and configured acceptance",
            )
        )
    )
    assert isinstance(decision, FinishDecision)
    assert decision.outcome == "supported_fault"
    assert decision.claims[0].fault_type == "harmonic_distortion"
    assert decision.claims[0].evidence_refs == ("ev_thd_001",)
    assert decision.claims[0].rule_refs == ("ruleval_thd_pass_001",)
