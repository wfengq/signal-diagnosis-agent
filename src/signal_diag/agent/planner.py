"""Planner protocol and deterministic scripted / real LLM implementations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    AgentDecision,
    PlannerContext,
    PlannerOutputError,
    ScriptExhaustedError,
)


@runtime_checkable
class PlannerModel(Protocol):
    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        ...


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


class RealLLMPlanner:
    """Product planner using a real LLM with structured output.

    Provider configuration is deferred until a provider is selected.
    This class never falls back to ScriptedPlanner.
    """

    def __init__(self, *, provider: str | None = None) -> None:
        self._provider = provider

    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        if self._provider is None:
            raise PlannerOutputError(
                "RealLLMPlanner is not configured: no LLM provider selected. "
                "Set provider credentials before running real-model evaluation."
            )
        raise PlannerOutputError(
            f"RealLLMPlanner provider {self._provider!r} is not implemented yet"
        )
