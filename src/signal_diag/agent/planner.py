"""Planner protocol and deterministic scripted / real LLM implementations."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .models import (
    AgentDecision,
    PlannerContext,
    PlannerOutputError,
    ScriptExhaustedError,
)

# DeepSeek V4 Flash official API model ID (OpenAI-compatible endpoint).
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
PROMPT_VERSION = "v0.2-s1-planner-1"

_AGENT_DECISION_ADAPTER: TypeAdapter[AgentDecision] = TypeAdapter(AgentDecision)

_SYSTEM_PROMPT = """You are a signal distortion diagnosis planner for Scenario S1.

You receive compact structured context: signal metadata, prior tool observations,
deterministic evidence records, tool descriptors, and runtime limits. You never
receive raw waveform samples or full FFT arrays.

Your job is to return exactly one JSON object matching the AgentDecision schema:
- Either call_tool: select one registered tool with valid args and a clear purpose.
- Or finish: provide outcome, evidence-grounded claims, and confidence.

Rules:
- Never invent or calculate DSP metrics; only reference evidence already in context.
- On the first decision, include task_assessment with task_type distortion_analysis.
- When finishing, every claim evidence_refs must reference existing evidence_id values.
- Prefer stopping once supported evidence is sufficient; avoid redundant tool calls.
- If metrics are invalid or not applicable, finish with inconclusive when justified.
- Use only tool names and argument fields from available_tools input schemas.
"""


@runtime_checkable
class PlannerModel(Protocol):
    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        ...


class _ChatClient(Protocol):
    class _Chat:
        class _Completions:
            async def create(self, **kwargs: Any) -> Any: ...

        completions: _Completions

    chat: _Chat


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


def _build_user_message(context: PlannerContext) -> str:
    payload = {
        "prompt_version": PROMPT_VERSION,
        "planner_context": context.model_dump(mode="json"),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _parse_agent_decision(raw_content: str) -> AgentDecision:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as error:
        raise PlannerOutputError(
            f"planner returned non-JSON content: {error.msg}"
        ) from error
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
        return PROMPT_VERSION

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
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(context)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_decision",
                    "schema": _AGENT_DECISION_ADAPTER.json_schema(),
                    "strict": True,
                },
            },
            temperature=0.0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        message = response.choices[0].message
        raw_content = message.content
        if not raw_content:
            raise PlannerOutputError("planner returned empty content")
        return _parse_agent_decision(raw_content)


def _create_async_openai_client(*, api_key: str, base_url: str) -> _ChatClient:
    try:
        from openai import AsyncOpenAI  # type: ignore[import-not-found]
    except ImportError as error:
        raise PlannerOutputError(
            "RealLLMPlanner requires the optional llm dependency. "
            "Install with: pip install 'signal-diagnosis-agent[llm]'"
        ) from error
    return AsyncOpenAI(api_key=api_key, base_url=base_url)
