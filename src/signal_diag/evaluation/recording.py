"""Transparent planner wrapper that records every decide() attempt."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from pydantic import TypeAdapter, ValidationError

from signal_diag.agent.models import (
    AgentDecision,
    CallToolDecision,
    EvaluateRulesDecision,
    FinishDecision,
    PlannerContext,
    PlannerOutputError,
    RetrieveKnowledgeDecision,
)
from signal_diag.agent.planner import PlannerModel
from signal_diag.evaluation.models import (
    PlannerCallStatus,
    PlannerDecisionRecord,
    ProviderUsage,
)

_AGENT_DECISION_ADAPTER: TypeAdapter[AgentDecision] = TypeAdapter(AgentDecision)
_DECISION_TYPES = (
    CallToolDecision,
    EvaluateRulesDecision,
    RetrieveKnowledgeDecision,
    FinishDecision,
)
_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key\s*[=:]\s*)\S+"
    r"|(?:authorization\s*[=:]\s*)\S+"
    r"|(?:bearer\s+)\S+"
    r"|\bsk-[A-Za-z0-9]+\b"
)
_MAX_ERROR_MESSAGE_CHARS = 1000


@runtime_checkable
class _ProviderUsageCapture(Protocol):
    @property
    def captured_provider_usage(self) -> ProviderUsage | None: ...


class RecordingPlanner:
    """Wrap a PlannerModel and snapshot every decide() call without changing it."""

    def __init__(
        self,
        planner: PlannerModel,
        *,
        _clock: Callable[[], float] | None = None,
    ) -> None:
        self._planner = planner
        self._clock = time.perf_counter if _clock is None else _clock
        self._records: list[PlannerDecisionRecord] = []

    async def decide(self, context: PlannerContext) -> AgentDecision:
        index = len(self._records)
        started = self._clock()
        try:
            candidate = await self._planner.decide(context)
        except BaseException as error:
            self._append_error(index, context, error, started)
            raise
        try:
            validated = _AGENT_DECISION_ADAPTER.validate_python(candidate)
        except ValidationError as error:
            output_error = PlannerOutputError(
                f"planner returned invalid AgentDecision: {error}"
            )
            self._append_error(index, context, output_error, started)
            raise output_error from error
        decision = candidate if isinstance(candidate, _DECISION_TYPES) else validated
        self._records.append(
            PlannerDecisionRecord(
                record_id=f"decision_{index:06d}",
                decision_index=index,
                context=context,
                status="decision",
                decision=decision,
                latency_ms=max(0.0, (self._clock() - started) * 1000.0),
                provider_usage=self._read_usage(),
            )
        )
        return decision

    @property
    def records(self) -> tuple[PlannerDecisionRecord, ...]:
        return tuple(self._records)

    def _append_error(
        self,
        index: int,
        context: PlannerContext,
        error: BaseException,
        started: float,
    ) -> None:
        self._records.append(
            PlannerDecisionRecord(
                record_id=f"decision_{index:06d}",
                decision_index=index,
                context=context,
                status=_status_for_error(error),
                error_type=type(error).__name__,
                error_message=_sanitize_message(error),
                latency_ms=max(0.0, (self._clock() - started) * 1000.0),
                provider_usage=self._read_usage(),
            )
        )

    def _read_usage(self) -> ProviderUsage | None:
        client = getattr(self._planner, "_client", None)
        if not isinstance(client, _ProviderUsageCapture):
            return None
        return _validated_usage(client.captured_provider_usage)


def _validated_usage(raw: object) -> ProviderUsage | None:
    if raw is None:
        return None
    if isinstance(raw, ProviderUsage):
        return raw
    try:
        return ProviderUsage.model_validate(raw)
    except (ValidationError, TypeError, ValueError):
        return None


def _status_for_error(error: BaseException) -> PlannerCallStatus:
    if isinstance(error, PlannerOutputError):
        return "planner_output_error"
    if _is_provider_adapter_error(error):
        return "provider_error"
    return "planner_error"


def _is_provider_adapter_error(error: BaseException) -> bool:
    if getattr(error, "_signal_diag_provider_error", False):
        return True
    module = type(error).__module__ or ""
    return module == "openai" or module.startswith("openai.")


def _sanitize_message(error: BaseException) -> str:
    message = str(error).strip() or type(error).__name__
    redacted = _SECRET_PATTERN.sub("[redacted]", message)
    if len(redacted) > _MAX_ERROR_MESSAGE_CHARS:
        return redacted[:_MAX_ERROR_MESSAGE_CHARS] + "…"
    return redacted
