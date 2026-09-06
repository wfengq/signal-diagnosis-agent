"""Transparent planner wrapper that records every decide() attempt."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import TypeAdapter, ValidationError

from signal_diag.agent.models import (
    AgentDecision,
    AgentRunResult,
    CallToolDecision,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    Observation,
    PlannerContext,
    PlannerOutputError,
    RetrieveKnowledgeDecision,
)
from signal_diag.agent.planner import PlannerModel
from signal_diag.agent.policies import normalize_tool_arguments
from signal_diag.agent.rule_closure import automatic_profile_for_tool
from signal_diag.evaluation.models import (
    BaselineRunResult,
    BenchmarkConfig,
    EvaluationCase,
    EvaluationEvent,
    EvaluationTrace,
    ExecutionPath,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerCallStatus,
    PlannerDecisionEvent,
    PlannerDecisionRecord,
    ProviderUsage,
    RuleEvaluationEvent,
)
from signal_diag.knowledge.models import KnowledgeRetrievalResult
from signal_diag.rules.models import RuleEvaluationBatch
from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import Evidence

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


def restricted_error_fingerprint(error: BaseException) -> dict[str, str | int | None]:
    """Return a non-sensitive category for an evaluation-time failure.

    The fingerprint intentionally excludes the exception message, module name,
    request payload, and response body.  It is for append-only campaign
    diagnostics, not for user-facing application errors.
    """

    status_code = getattr(error, "status_code", None)
    if not isinstance(status_code, int) or not 100 <= status_code <= 599:
        status_code = None
    name = type(error).__name__
    module = type(error).__module__ or ""
    lowered = name.lower()
    if status_code in {401, 403} or "auth" in lowered:
        category = "authentication"
    elif status_code == 429 or "ratelimit" in lowered:
        category = "rate_limited"
    elif status_code is not None and 500 <= status_code <= 599:
        category = "provider_5xx"
    elif (
        getattr(error, "_signal_diag_provider_error", False)
        or module == "openai"
        or module.startswith("openai.")
    ):
        category = "provider_transport"
    elif isinstance(error, TimeoutError) or "timeout" in lowered:
        category = "timeout"
    else:
        category = "evaluator_internal"
    return {
        "category": category,
        "error_type": name[:100],
        "status_code": status_code,
    }


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


T = TypeVar("T")
_MAX_COMPACT_NUMERIC_SEQUENCE = 20
_BASELINE_TOOL_ORDINAL: dict[ToolName, int] = {
    "detect_clipping": 0,
    "analyze_harmonic_distortion": 1,
}
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "samples",
        "waveform",
        "api_key",
        "apikey",
        "api-key",
        "authorization",
        "password",
        "secret",
        "credentials",
        "access_token",
        "raw_response",
        "provider_response",
        "response_body",
        "raw_body",
        "raw_provider_response",
    }
)


def assemble_agent_events(
    records: tuple[PlannerDecisionRecord, ...],
    result: AgentRunResult,
) -> tuple[EvaluationEvent, ...]:
    _validate_path("agent", result, records)
    events = _assemble_agent_events(records, result)
    _validate_result_artifacts(result, events)
    _validate_claim_refs(records, result, events)
    _reject_forbidden_payloads(records, events)
    return tuple(events)


def assemble_evaluation_trace(
    case: EvaluationCase,
    records: tuple[PlannerDecisionRecord, ...],
    result: AgentRunResult | BaselineRunResult,
    config: BenchmarkConfig,
    *,
    run_slot: int,
    execution_path: ExecutionPath,
) -> EvaluationTrace:
    _validate_path(execution_path, result, records)
    if execution_path == "fixed_pipeline":
        if not isinstance(result, BaselineRunResult):
            raise ValueError("fixed_pipeline execution_path requires BaselineRunResult")
        events = _assemble_baseline_events(result)
        usage = None
        _validate_result_artifacts(result, events)
        _validate_claim_refs(records, result, events)
        _reject_forbidden_payloads(records, events)
    else:
        if not isinstance(result, AgentRunResult):
            raise ValueError("agent execution_path requires AgentRunResult")
        events = list(assemble_agent_events(records, result))
        usage = _aggregate_provider_usage(records)
    return EvaluationTrace(
        trace_id=f"trace_{execution_path}_{case.case_id}_{run_slot:02d}",
        case_id=case.case_id,
        run_slot=run_slot,
        execution_path=execution_path,
        config=config,
        events=tuple(events),
        result=result,
        provider_usage=usage,
    )


def _validate_path(
    execution_path: ExecutionPath,
    result: AgentRunResult | BaselineRunResult,
    records: tuple[PlannerDecisionRecord, ...],
) -> None:
    if execution_path == "agent":
        if not isinstance(result, AgentRunResult):
            raise ValueError("agent execution_path requires AgentRunResult")
        if not records:
            raise ValueError("grouped history is forbidden; agent traces require records")
        return
    if execution_path == "fixed_pipeline":
        if not isinstance(result, BaselineRunResult):
            raise ValueError("fixed_pipeline execution_path requires BaselineRunResult")
        if records:
            raise ValueError("fixed_pipeline traces must not include planner records")
        return
    raise ValueError(f"unknown execution_path: {execution_path}")


def _strict_suffix(before: tuple[T, ...], after: tuple[T, ...], label: str) -> tuple[T, ...]:
    if len(after) < len(before) or after[: len(before)] != before:
        raise ValueError(f"{label} is not an append-only delta")
    return after[len(before) :]


def _assemble_agent_events(
    records: tuple[PlannerDecisionRecord, ...],
    result: AgentRunResult,
) -> list[EvaluationEvent]:
    events: list[EvaluationEvent] = []
    event_index = 0
    for index, record in enumerate(records):
        events.append(
            PlannerDecisionEvent(
                event_index=event_index,
                record=record,
            )
        )
        event_index += 1
        if record.status != "decision" or record.decision is None:
            continue
        after = _after_artifacts(records, index, result)
        before = record.context
        obs_delta = _strict_suffix(before.observations, after[0], "observations")
        evidence_delta = _strict_suffix(before.evidence, after[1], "evidence")
        rule_delta = _strict_suffix(
            before.rule_evaluation_batches, after[2], "rule_evaluation_batches"
        )
        knowledge_delta = _strict_suffix(
            before.knowledge_retrievals, after[3], "knowledge_retrievals"
        )
        decision = record.decision
        if isinstance(decision, CallToolDecision):
            if knowledge_delta:
                raise ValueError(
                    "CallToolDecision produced unexpected knowledge artifacts"
                )
            if len(rule_delta) > 1:
                raise ValueError(
                    "CallToolDecision permits at most one automatic rule batch"
                )
            if not obs_delta and not evidence_delta and not rule_delta:
                continue
            if len(obs_delta) != 1:
                raise ValueError("CallToolDecision requires exactly one Observation")
            observation = obs_delta[0]
            if observation.tool_name != decision.call.tool_name:
                raise ValueError("Observation tool does not match CallToolDecision")
            if observation.normalized_arguments != normalize_tool_arguments(decision.call):
                raise ValueError("Observation arguments do not match CallToolDecision")
            evidence_ids = tuple(item.evidence_id for item in evidence_delta)
            if observation.evidence_refs != evidence_ids:
                raise ValueError("Observation evidence_refs do not match Evidence suffix")
            events.append(
                ObservationEvent(
                    event_index=event_index,
                    caused_by_decision_index=record.decision_index,
                    observation=observation,
                    evidence=evidence_delta,
                )
            )
            event_index += 1
            if rule_delta:
                batch = rule_delta[0]
                expected_profile = automatic_profile_for_tool(observation.tool_name)
                if observation.status == "error":
                    raise ValueError("errored Tool cannot produce automatic rules")
                if expected_profile is None or batch.profile_id != expected_profile:
                    raise ValueError("automatic rule batch does not match Tool")
                events.append(
                    RuleEvaluationEvent(
                        event_index=event_index,
                        caused_by_decision_index=record.decision_index,
                        batch=batch,
                    )
                )
                event_index += 1
            continue
        if isinstance(decision, EvaluateRulesDecision):
            if obs_delta or evidence_delta or knowledge_delta:
                raise ValueError("EvaluateRulesDecision produced unexpected artifacts")
            if not rule_delta:
                continue
            if len(rule_delta) != 1:
                raise ValueError("EvaluateRulesDecision requires exactly one RuleEvaluationBatch")
            events.append(
                RuleEvaluationEvent(
                    event_index=event_index,
                    caused_by_decision_index=record.decision_index,
                    batch=rule_delta[0],
                )
            )
            event_index += 1
            continue
        if isinstance(decision, RetrieveKnowledgeDecision):
            if obs_delta or evidence_delta or rule_delta:
                raise ValueError("RetrieveKnowledgeDecision produced unexpected artifacts")
            if not knowledge_delta:
                continue
            if len(knowledge_delta) != 1:
                raise ValueError(
                    "RetrieveKnowledgeDecision requires exactly one KnowledgeRetrievalResult"
                )
            events.append(
                KnowledgeRetrievalEvent(
                    event_index=event_index,
                    caused_by_decision_index=record.decision_index,
                    retrieval=knowledge_delta[0],
                )
            )
            event_index += 1
            continue
        if isinstance(decision, FinishDecision):
            if obs_delta or evidence_delta or rule_delta or knowledge_delta:
                raise ValueError("FinishDecision must not produce runtime artifacts")
            continue
        raise ValueError("unsupported AgentDecision")
    return events


def _after_artifacts(
    records: tuple[PlannerDecisionRecord, ...],
    index: int,
    result: AgentRunResult,
) -> tuple[
    tuple[Observation, ...],
    tuple[Evidence, ...],
    tuple[RuleEvaluationBatch, ...],
    tuple[KnowledgeRetrievalResult, ...],
]:
    if index + 1 < len(records):
        context = records[index + 1].context
        return (
            context.observations,
            context.evidence,
            context.rule_evaluation_batches,
            context.knowledge_retrievals,
        )
    return (
        result.observations,
        result.evidence,
        result.rule_evaluation_batches,
        result.knowledge_retrievals,
    )


def _assemble_baseline_events(result: BaselineRunResult) -> list[EvaluationEvent]:
    events: list[EvaluationEvent] = []
    event_index = 0
    evidence_by_id = {item.evidence_id: item for item in result.evidence}
    for observation in result.observations:
        try:
            ordinal = _BASELINE_TOOL_ORDINAL[observation.tool_name]
        except KeyError as error:
            raise ValueError(
                f"unsupported baseline tool: {observation.tool_name}"
            ) from error
        try:
            attached = tuple(evidence_by_id[ref] for ref in observation.evidence_refs)
        except KeyError as error:
            raise ValueError("unresolved observation evidence_ref") from error
        events.append(
            ObservationEvent(
                event_index=event_index,
                caused_by_decision_index=ordinal,
                observation=observation,
                evidence=attached,
            )
        )
        event_index += 1
    for batch in result.rule_evaluation_batches:
        events.append(
            RuleEvaluationEvent(
                event_index=event_index,
                caused_by_decision_index=2,
                batch=batch,
            )
        )
        event_index += 1
    return events


def _validate_result_artifacts(
    result: AgentRunResult | BaselineRunResult,
    events: list[EvaluationEvent],
) -> None:
    observations = tuple(
        event.observation for event in events if isinstance(event, ObservationEvent)
    )
    evidence = tuple(
        item
        for event in events
        if isinstance(event, ObservationEvent)
        for item in event.evidence
    )
    batches = tuple(
        event.batch for event in events if isinstance(event, RuleEvaluationEvent)
    )
    retrievals = tuple(
        event.retrieval for event in events if isinstance(event, KnowledgeRetrievalEvent)
    )
    if observations != result.observations:
        raise ValueError("result observations do not match assembled trace")
    if evidence != result.evidence:
        raise ValueError("result evidence does not match assembled trace")
    if batches != result.rule_evaluation_batches:
        raise ValueError("result rule batches do not match assembled trace")
    if isinstance(result, AgentRunResult) and retrievals != result.knowledge_retrievals:
        raise ValueError("result knowledge retrievals do not match assembled trace")


def _validate_claim_refs(
    records: tuple[PlannerDecisionRecord, ...],
    result: AgentRunResult | BaselineRunResult,
    events: list[EvaluationEvent],
) -> None:
    evidence_ids = {
        item.evidence_id
        for event in events
        if isinstance(event, ObservationEvent)
        for item in event.evidence
    }
    rule_ids = {
        evaluation.evaluation_id
        for event in events
        if isinstance(event, RuleEvaluationEvent)
        for evaluation in event.batch.evaluations
    }
    knowledge_ids = {
        event.retrieval.retrieval_id
        for event in events
        if isinstance(event, KnowledgeRetrievalEvent)
    }
    applied_claims = (
        tuple(result.diagnosis.claims) if result.diagnosis is not None else ()
    )
    claims: list[DiagnosisClaim] = list(applied_claims)
    for record in records:
        decision = record.decision
        if not isinstance(decision, FinishDecision):
            continue
        if decision.claims != applied_claims:
            continue
        claims.extend(decision.claims)
    for claim in claims:
        for ref in claim.evidence_refs:
            if ref not in evidence_ids:
                raise ValueError(f"unresolved evidence ref: {ref}")
        for ref in claim.rule_refs:
            if ref not in rule_ids:
                raise ValueError(f"unresolved rule ref: {ref}")
        for ref in claim.knowledge_refs:
            if ref not in knowledge_ids:
                raise ValueError(f"unresolved knowledge ref: {ref}")


def _aggregate_provider_usage(
    records: tuple[PlannerDecisionRecord, ...],
) -> ProviderUsage | None:
    usages = tuple(record.provider_usage for record in records if record.provider_usage is not None)
    if not usages:
        return None

    def _sum_int(attribute: str) -> int | None:
        values = [getattr(item, attribute) for item in usages if getattr(item, attribute) is not None]
        if not values:
            return None
        return int(sum(values))

    costs = [item.cost_usd for item in usages if item.cost_usd is not None]
    return ProviderUsage(
        input_tokens=_sum_int("input_tokens"),
        output_tokens=_sum_int("output_tokens"),
        total_tokens=_sum_int("total_tokens"),
        cost_usd=sum(costs) if costs else None,
    )


def _reject_forbidden_payloads(
    records: tuple[PlannerDecisionRecord, ...],
    events: list[EvaluationEvent],
) -> None:
    dumped: list[object] = [
        record.model_dump(mode="python") for record in records
    ]
    dumped.extend(event.model_dump(mode="python") for event in events)
    for item in dumped:
        _reject_forbidden_value(item)


def _reject_forbidden_value(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower().replace("_", "-")
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_PAYLOAD_KEYS or normalized in _FORBIDDEN_PAYLOAD_KEYS:
                raise ValueError(f"forbidden payload key: {key}")
            _reject_forbidden_value(nested)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if _is_numeric_sequence(value) and len(value) > _MAX_COMPACT_NUMERIC_SEQUENCE:
            raise ValueError("forbidden full spectral array")
        for item in value:
            _reject_forbidden_value(item)
        return
    if type(value).__name__ == "ndarray" and type(value).__module__.startswith("numpy"):
        raise ValueError("forbidden array payload")


def _is_numeric_sequence(value: Sequence[object]) -> bool:
    if not value:
        return False
    return all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    )
