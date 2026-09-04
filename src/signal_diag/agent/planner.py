"""Planner protocol and deterministic scripted / real LLM implementations."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .models import (
    AgentDecision,
    PlannerContext,
    PlannerOutputError,
    ScriptExhaustedError,
)
from .prompts import (
    _S1_PROMPT_V4,
    _S1_PROMPT_V5,
    _S1_PROMPT_V6,
    _S1_PROMPT_V7,
    _S1_PROMPT_V8,
    _S1_PROMPT_V8_1,
    _PlannerPromptSpec,
)
from .prompts_v03 import _S1_PROMPT_V9_7

# DeepSeek V4 Flash official API model ID (OpenAI-compatible endpoint).
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
PROMPT_VERSION = _S1_PROMPT_V9_7.version
_SYSTEM_PROMPT = _S1_PROMPT_V9_7.system_prompt

_AGENT_DECISION_ADAPTER: TypeAdapter[AgentDecision] = TypeAdapter(AgentDecision)


def _deepseek_response_format() -> dict[str, str]:
    """DeepSeek-compatible structured output (json_schema is not always available)."""
    return {"type": "json_object"}


@runtime_checkable
class PlannerModel(Protocol):
    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        ...


class _ChatCompletions(Protocol):
    async def create(
        self,
        *,
        model: Any,
        messages: Any,
        response_format: Any,
        temperature: Any,
        extra_body: Any,
    ) -> Any: ...


class _ChatResource(Protocol):
    @property
    def completions(self) -> _ChatCompletions: ...


class _ChatClient(Protocol):
    @property
    def chat(self) -> _ChatResource: ...


class ScriptedStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_observation_count: int = Field(ge=0)
    required_evidence_metrics: tuple[str, ...] = ()
    decision: AgentDecision


class ScriptedPlanner:
    """Deterministic planner for tests; consumes one scripted step per call."""

    def __init__(self, steps: Sequence[ScriptedStep]) -> None:
        self._steps = tuple(steps)
        self._index = 0

    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        if self._index >= len(self._steps):
            raise ScriptExhaustedError("scripted planner has no remaining steps")

        step = self._steps[self._index]
        if len(context.observations) != step.expected_observation_count:
            raise PlannerOutputError(
                "scripted step observation count mismatch: "
                f"expected {step.expected_observation_count}, "
                f"got {len(context.observations)}"
            )

        present_metrics = {item.metric for item in context.evidence}
        missing = [
            metric
            for metric in step.required_evidence_metrics
            if metric not in present_metrics
        ]
        if missing:
            raise PlannerOutputError(
                f"scripted step missing required evidence metrics: {missing}"
            )

        self._index += 1
        return step.decision


def _missing_credentials_message() -> str:
    return (
        "RealLLMPlanner is not configured: set DEEPSEEK_API_KEY in the "
        "environment before running real-model evaluation. "
        "This command does not fall back to ScriptedPlanner."
    )


def _resolve_deepseek_config(
    *,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> tuple[str, str, str]:
    resolved_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not resolved_key:
        raise PlannerOutputError(_missing_credentials_message())
    resolved_base_url = (
        base_url
        or os.environ.get("DEEPSEEK_BASE_URL")
        or DEFAULT_DEEPSEEK_BASE_URL
    )
    resolved_model = (
        model or os.environ.get("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL
    )
    return resolved_key, resolved_base_url, resolved_model


def _build_user_message(
    context: PlannerContext,
    *,
    prompt_version: str,
) -> str:
    payload = {
        "prompt_version": prompt_version,
        "planner_context": context.model_dump(mode="json"),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _normalize_call_dict(call: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(call)
    if "tool_name" not in normalized and "name" in normalized:
        normalized["tool_name"] = normalized.pop("name")
    normalized.setdefault("args", {})
    return normalized


def _normalize_task_assessment_payload(
    task_assessment: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(task_assessment)
    if "objective" not in normalized:
        for alias in ("goal", "description", "summary"):
            if alias in normalized:
                normalized["objective"] = normalized.pop(alias)
                break
    hypotheses = normalized.get("hypotheses")
    if "objective" not in normalized and isinstance(hypotheses, str):
        normalized["objective"] = hypotheses
        normalized["hypotheses"] = ()
    elif "objective" not in normalized and isinstance(hypotheses, list) and hypotheses:
        first = hypotheses[0]
        if isinstance(first, str):
            normalized["objective"] = first
    return normalized


def _merge_call_tool_branch(
    outer: dict[str, Any],
    inner: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(outer)
    branch = dict(inner)
    branch.pop("decision_type", None)

    for field in ("purpose", "expected_evidence", "task_assessment"):
        if field not in merged and field in branch:
            merged[field] = branch.pop(field)

    if "call" in branch:
        merged["call"] = branch.pop("call")
    elif "tool_name" in branch or "name" in branch:
        merged["call"] = {
            key: branch.pop(key)
            for key in ("tool_name", "name", "args")
            if key in branch
        }
        if "tool_name" not in merged["call"] and "name" in merged["call"]:
            merged["call"]["tool_name"] = merged["call"].pop("name")
        merged["call"].setdefault("args", {})
    elif "tool" in branch and isinstance(branch["tool"], dict):
        merged["call"] = branch.pop("tool")

    if "purpose" not in merged and "purpose" in branch:
        merged["purpose"] = branch.pop("purpose")

    return merged


def _normalize_call_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    if "call_tool" in normalized and isinstance(normalized["call_tool"], dict):
        normalized = _merge_call_tool_branch(normalized, normalized.pop("call_tool"))

    if "tool" in normalized and "call" not in normalized and isinstance(
        normalized["tool"], dict
    ):
        normalized["call"] = normalized.pop("tool")

    if "call" not in normalized and ("tool_name" in normalized or "name" in normalized):
        normalized["call"] = {
            key: normalized.pop(key)
            for key in ("tool_name", "name", "args")
            if key in normalized
        }

    if isinstance(normalized.get("call"), dict):
        normalized["call"] = _normalize_call_dict(normalized["call"])

    if isinstance(normalized.get("task_assessment"), dict):
        normalized["task_assessment"] = _normalize_task_assessment_payload(
            normalized["task_assessment"]
        )

    return normalized


def _merge_finish_branch(
    outer: dict[str, Any],
    inner: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(outer)
    branch = dict(inner)
    branch.pop("decision_type", None)

    for field in (
        "task_assessment",
        "outcome",
        "claims",
        "confidence_label",
        "limitations",
    ):
        if field not in merged and field in branch:
            merged[field] = branch.pop(field)

    return merged


def _coerce_limitation_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    if isinstance(value, list):
        return tuple(
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        )
    return ()


def _lift_inconclusive_limitations(normalized: dict[str, Any]) -> dict[str, Any]:
    if normalized.get("outcome") != "inconclusive":
        return normalized

    limitations = normalized.get("limitations")
    if limitations:
        return normalized

    for alias in ("limitation", "summary", "reason"):
        if alias not in normalized:
            continue
        lifted = _coerce_limitation_strings(normalized.pop(alias))
        if lifted:
            normalized["limitations"] = lifted
            break

    return normalized


def _normalize_finish_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    if "finish" in normalized and isinstance(normalized["finish"], dict):
        normalized = _merge_finish_branch(normalized, normalized.pop("finish"))

    if isinstance(normalized.get("task_assessment"), dict):
        normalized["task_assessment"] = _normalize_task_assessment_payload(
            normalized["task_assessment"]
        )

    return _lift_inconclusive_limitations(normalized)


def _normalize_agent_decision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload

    normalized: dict[str, Any] = dict(payload)

    if "decision_type" not in normalized:
        if "call_tool" in normalized and isinstance(normalized["call_tool"], dict):
            branch = normalized.pop("call_tool")
            normalized["decision_type"] = "call_tool"
            normalized = _merge_call_tool_branch(normalized, branch)
        elif "finish" in normalized and isinstance(normalized["finish"], dict):
            branch = normalized.pop("finish")
            normalized["decision_type"] = "finish"
            normalized = _merge_finish_branch(normalized, branch)
        elif "evaluate_rules" in normalized and isinstance(
            normalized["evaluate_rules"], dict
        ):
            branch = normalized.pop("evaluate_rules")
            normalized = {**normalized, **branch, "decision_type": "evaluate_rules"}
        elif "retrieve_knowledge" in normalized and isinstance(
            normalized["retrieve_knowledge"], dict
        ):
            branch = normalized.pop("retrieve_knowledge")
            normalized = {
                **normalized,
                **branch,
                "decision_type": "retrieve_knowledge",
            }

    decision_type = normalized.get("decision_type")
    if decision_type == "call_tool":
        return _normalize_call_tool_payload(normalized)
    if decision_type == "finish":
        return _normalize_finish_payload(normalized)
    return normalized


def _parse_agent_decision(raw_content: str) -> AgentDecision:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as error:
        raise PlannerOutputError(
            f"planner returned non-JSON content: {error.msg}"
        ) from error
    if isinstance(parsed, dict):
        parsed = _normalize_agent_decision_payload(parsed)
    try:
        return _AGENT_DECISION_ADAPTER.validate_python(parsed)
    except ValidationError as error:
        raise PlannerOutputError(
            f"planner returned invalid AgentDecision: {error}"
        ) from error


class RealLLMPlanner:
    """Product planner using a real LLM with structured output.

    Uses the DeepSeek OpenAI-compatible API by default. Never falls back to
    ScriptedPlanner.
    """

    _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V9_7

    def __init__(
        self,
        *,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        client: _ChatClient | None = None,
    ) -> None:
        self._provider = provider
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._client = client

    @property
    def prompt_version(self) -> str:
        return self._prompt_spec.version

    @property
    def model_id(self) -> str | None:
        if self._model is not None:
            return self._model
        if self._provider == "deepseek":
            return os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
        return None

    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        if self._provider is None:
            raise PlannerOutputError(
                "RealLLMPlanner is not configured: no LLM provider selected. "
                "Set provider credentials before running real-model evaluation."
            )
        if self._provider != "deepseek":
            raise PlannerOutputError(
                f"RealLLMPlanner provider {self._provider!r} is not implemented"
            )
        return await self._decide_deepseek(context)

    async def _decide_deepseek(self, context: PlannerContext) -> AgentDecision:
        api_key, base_url, model = _resolve_deepseek_config(
            api_key=self._api_key,
            base_url=self._base_url,
            model=self._model,
        )
        client = self._client or _create_async_openai_client(
            api_key=api_key,
            base_url=base_url,
        )
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self._prompt_spec.system_prompt},
                {
                    "role": "user",
                    "content": _build_user_message(
                        context,
                        prompt_version=self.prompt_version,
                    ),
                },
            ],
            response_format=_deepseek_response_format(),
            temperature=0.0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        message = response.choices[0].message
        raw_content = message.content
        if not raw_content:
            raise PlannerOutputError("planner returned empty content")
        return _parse_agent_decision(raw_content)


class _Phase4V4RealLLMPlanner(RealLLMPlanner):
    _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V4


class _Phase4V5RealLLMPlanner(RealLLMPlanner):
    _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V5


class _Phase4V6RealLLMPlanner(RealLLMPlanner):
    _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V6


class _Phase4V7RealLLMPlanner(RealLLMPlanner):
    _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V7


class _Phase4V8RealLLMPlanner(RealLLMPlanner):
    _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V8


class _Phase4V8_1RealLLMPlanner(RealLLMPlanner):
    _prompt_spec: ClassVar[_PlannerPromptSpec] = _S1_PROMPT_V8_1


def _create_async_openai_client(*, api_key: str, base_url: str) -> _ChatClient:
    try:
        from openai import AsyncOpenAI  # type: ignore[import-not-found]
    except ImportError as error:
        raise PlannerOutputError(
            "RealLLMPlanner requires the optional llm dependency. "
            "Install with: pip install 'signal-diagnosis-agent[llm]'"
        ) from error
    return AsyncOpenAI(api_key=api_key, base_url=base_url)
