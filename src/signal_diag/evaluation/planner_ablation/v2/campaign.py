"""V2 planner-ablation schedule execution, failure accounting, and limit audit.

Study-only. Does not construct provider clients, seal protocols, or score product
campaigns. Task 3 owns timing analysis helpers; this module owns preparation,
measured dispatch, persistence hooks, and teardown.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Literal

from signal_diag.agent.models import TaskAssessment
from signal_diag.agent.policies import AgentLimits
from signal_diag.evaluation.planner_ablation.v2.models import (
    AUDITED_AGENT_LIMIT_DEFAULTS,
    PRODUCT_SLOT_COUNT_V2,
    TIMING_CONTRACT_V1,
    BudgetAssessment,
    ByteRequest,
    CampaignRecord,
    CampaignStatus,
    EffectiveConfiguration,
    ExecutionMode,
    ExecutionProvenance,
    FailureCause,
    PhaseMarker,
    RequestTiming,
    ResourceTelemetry,
    Schedule,
    SlotAttemptRecord,
    SlotKey,
    StudyProtocolV2,
    StudyTerminal,
)
from signal_diag.evaluation.planner_ablation.v2.timing import (
    ArmSession,
    TimingValidationError,
    validate_request_timing,
)

_BEHAVIORAL_KINDS = frozenset({"behavioral", "decode_failure"})
_STOP_KINDS = frozenset({"infrastructure", "deadline_exceeded", "unknown"})
_BEHAVIORAL_TERMINATION_MARKERS = frozenset(
    {
        "max_tool_calls",
        "max_planner_retries",
        "max_rule_evaluations",
        "max_knowledge_retrievals",
        "no_progress",
        "diagnosis/repair",
        "repair_budget",
        "exhausted diagnosis",
        "exhausted repair",
    }
)
_DEFAULT_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_DRAIN_GRACE_S = 5.0


def _session_background_worker_alive(session: ArmSession) -> bool:
    alive = getattr(session, "background_worker_alive", False)
    if callable(alive):
        return bool(alive())
    return bool(alive)


class CampaignPreflightError(RuntimeError):
    """Online/offline campaign refused before slot dispatch."""


class CampaignInfrastructureError(RuntimeError):
    """Infrastructure stop; preserved schedule; no accepted conclusion."""


def snapshot_effective_configuration(
    *,
    limits: AgentLimits | None = None,
    temperature: float | None = 0.0,
    thinking_disabled: bool | None = True,
    max_tokens_explicit: bool = False,
    max_tokens: int | None = None,
    request_timeout_explicit: bool = False,
    request_timeout_s: float | None = None,
    transport_retry_override_explicit: bool = False,
    transport_retry_override: int | None = None,
    transport_attempts_per_call_bound: int | None = None,
    planner_calls_per_slot_bound: int | None = None,
    input_token_bound_per_call: int | None = None,
    output_token_bound_per_call: int | None = None,
    retry_telemetry_available: bool = False,
    provider_sdk_version: str | None = None,
    notes: Sequence[str] = (),
) -> EffectiveConfiguration:
    """Capture pinned product-path facts without mutating composition defaults."""
    agent_limits = limits if limits is not None else AgentLimits()
    return EffectiveConfiguration(
        max_tool_calls=agent_limits.max_tool_calls,
        max_planner_retries=agent_limits.max_planner_retries,
        max_no_progress=agent_limits.max_no_progress,
        max_rule_evaluations=agent_limits.max_rule_evaluations,
        max_knowledge_retrievals=agent_limits.max_knowledge_retrievals,
        temperature=temperature,
        thinking_disabled=thinking_disabled,
        max_tokens_explicit=max_tokens_explicit,
        max_tokens=max_tokens,
        request_timeout_explicit=request_timeout_explicit,
        request_timeout_s=request_timeout_s,
        transport_retry_override_explicit=transport_retry_override_explicit,
        transport_retry_override=transport_retry_override,
        transport_attempts_per_call_bound=transport_attempts_per_call_bound,
        planner_calls_per_slot_bound=planner_calls_per_slot_bound,
        input_token_bound_per_call=input_token_bound_per_call,
        output_token_bound_per_call=output_token_bound_per_call,
        retry_telemetry_available=retry_telemetry_available,
        provider_sdk_version=provider_sdk_version,
        notes=tuple(notes),
    )


def inspect_limits(config: EffectiveConfiguration) -> BudgetAssessment:
    """Audit AgentLimits/transport facts and emit explicit unknown-bound blockers.

    Observed merge defaults (tool=8, planner_retries=2, no_progress=2,
    rule_evaluations=4, knowledge_retrievals=4; temperature 0; thinking disabled;
    no explicit max_tokens/timeout/retry override) do **not** prove an effective
    request or token bound. Missing production limits remain seal/execution blockers.
    """
    blockers: list[str] = []
    audited: dict[str, int | None] = {
        "max_tool_calls": config.max_tool_calls,
        "max_planner_retries": config.max_planner_retries,
        "max_no_progress": config.max_no_progress,
        "max_rule_evaluations": config.max_rule_evaluations,
        "max_knowledge_retrievals": config.max_knowledge_retrievals,
    }
    for name, expected in AUDITED_AGENT_LIMIT_DEFAULTS.items():
        actual = audited.get(name)
        if actual is None:
            blockers.append(f"unknown_agent_limit:{name}")
        elif actual != expected:
            blockers.append(
                f"agent_limit_drift:{name}:expected_{expected}:actual_{actual}"
            )

    if config.temperature is None:
        blockers.append("unknown_temperature")
    elif config.temperature != 0.0:
        blockers.append(f"temperature_drift:{config.temperature}")

    if config.thinking_disabled is None:
        blockers.append("unknown_thinking_setting")
    elif config.thinking_disabled is not True:
        blockers.append("thinking_not_disabled")

    if not config.max_tokens_explicit or config.max_tokens is None:
        blockers.append("unknown_max_tokens_bound")
    if not config.request_timeout_explicit or config.request_timeout_s is None:
        blockers.append("unknown_provider_request_timeout")
    if (
        not config.transport_retry_override_explicit
        or config.transport_attempts_per_call_bound is None
    ):
        blockers.append("unknown_transport_attempts_per_call_bound")
    if not config.retry_telemetry_available:
        blockers.append("unavailable_retry_telemetry")
    if config.planner_calls_per_slot_bound is None:
        blockers.append("unknown_planner_calls_per_slot_bound")
        blockers.append(
            "agent_limits_do_not_prove_planner_call_bound:"
            "tool_count_is_not_planner_calls"
        )
    if config.input_token_bound_per_call is None:
        blockers.append("unknown_input_token_bound")
    if config.output_token_bound_per_call is None:
        blockers.append("unknown_output_token_bound")
    if config.provider_sdk_version is None:
        blockers.append("unknown_provider_sdk_identity")

    planner_bound = config.planner_calls_per_slot_bound
    transport_bound = config.transport_attempts_per_call_bound
    worst_case_requests: int | None = None
    worst_case_input: int | None = None
    worst_case_output: int | None = None
    if planner_bound is not None and transport_bound is not None:
        if planner_bound <= 0 or transport_bound <= 0:
            blockers.append("non_positive_request_bound")
        else:
            worst_case_requests = (
                PRODUCT_SLOT_COUNT_V2 * planner_bound * transport_bound
            )
            if (
                config.input_token_bound_per_call is not None
                and config.output_token_bound_per_call is not None
            ):
                worst_case_input = (
                    worst_case_requests * config.input_token_bound_per_call
                )
                worst_case_output = (
                    worst_case_requests * config.output_token_bound_per_call
                )
    else:
        blockers.append("worst_case_requests_uncomputable")

    # De-dupe while preserving order.
    unique_blockers = tuple(dict.fromkeys(blockers))
    execution_blocked = len(unique_blockers) > 0
    return BudgetAssessment(
        product_slot_count=PRODUCT_SLOT_COUNT_V2,
        planner_calls_per_slot_bound=planner_bound,
        transport_attempts_per_call_bound=transport_bound,
        worst_case_requests=worst_case_requests,
        worst_case_input_tokens=worst_case_input,
        worst_case_output_tokens=worst_case_output,
        audited_agent_limits=audited,
        temperature=config.temperature,
        thinking_disabled=config.thinking_disabled,
        blockers=unique_blockers,
        execution_blocked=execution_blocked,
        seal_ready=False,
    )


def collect_resource_telemetry(terminal: StudyTerminal) -> ResourceTelemetry:
    """Derive available study-owned telemetry without inventing provider usage."""
    tool_count = len(terminal.tool_history)
    rule_count = sum(len(batch.evaluations) for batch in terminal.rule_evaluation_batches)
    unknown: list[str] = [
        "planner_call_count",
        "repair_attempt_count",
        "transport_attempt_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ]
    return ResourceTelemetry(
        planner_call_count=None,
        tool_call_count=tool_count,
        rule_evaluation_count=rule_count,
        repair_attempt_count=None,
        transport_attempt_count=None,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        unknown_fields=tuple(unknown),
        credentials_redacted=True,
        raw_waveform_persisted=False,
        raw_fft_persisted=False,
    )


def classify_failure_cause(terminal: StudyTerminal) -> FailureCause | None:
    """Map terminal failure into typed campaign stop/continue categories."""
    if terminal.status == "completed":
        return None
    cause = terminal.failure_cause
    if cause is None:
        return FailureCause(kind="unknown", detail="missing_failure_cause")
    if cause.kind in _STOP_KINDS or cause.kind in _BEHAVIORAL_KINDS:
        if cause.kind == "unknown":
            return FailureCause(kind="unknown", detail=cause.detail)
        return cause
    detail = (cause.detail or "").lower()
    if any(marker in detail for marker in _BEHAVIORAL_TERMINATION_MARKERS):
        return FailureCause(kind="behavioral", detail=cause.detail)
    return FailureCause(kind="unknown", detail=cause.detail or cause.kind)


def _is_infrastructure_stop(cause: FailureCause | None) -> bool:
    if cause is None:
        return False
    return cause.kind in _STOP_KINDS


def reject_online_preflight(
    *,
    verified_seal_digest: str | None,
    authorization_reference: str | None,
    budget: BudgetAssessment | None,
) -> None:
    """Fail closed before any network client construction.

    ``authorization_reference`` is an audit link, not self-issued permission.
    """
    missing: list[str] = []
    if not verified_seal_digest:
        missing.append("missing_verified_seal")
    if not authorization_reference:
        missing.append("missing_authorization_reference")
    if budget is None:
        missing.append("missing_budget_preflight")
    elif budget.execution_blocked or budget.worst_case_requests is None:
        missing.append("incomplete_budget_preflight")
        if budget.worst_case_requests is None:
            missing.append("unbounded_worst_case_requests")
    if missing:
        raise CampaignPreflightError(
            "online mode refused before network client construction: "
            + ",".join(dict.fromkeys(missing))
        )


def _placeholder_timing(request_start: float, terminal_ready: float) -> RequestTiming:
    elapsed = terminal_ready - request_start
    return RequestTiming(
        timing_contract=TIMING_CONTRACT_V1,
        request_start=request_start,
        terminal_result_ready=terminal_ready,
        elapsed_s=elapsed,
        phase_markers=(),
        residual_overhead_notes=("campaign_deadline_path_incomplete_phases",),
    )


def _deadline_terminal(
    *,
    slot: SlotKey,
    mode: Literal["single_signal", "paired_reference"],
    request_start: float,
    terminal_ready: float,
    detail: str,
    provenance: ExecutionProvenance | None = None,
) -> StudyTerminal:
    return StudyTerminal(
        run_id=f"deadline_{slot.request_key[:12]}_{slot.arm}_{slot.round_index}",
        arm=slot.arm,
        mode=mode,
        status="failed",
        failure_cause=FailureCause(kind="deadline_exceeded", detail=detail),
        task_assessment=_DEFAULT_ASSESSMENT,
        provenance=provenance
        or ExecutionProvenance(
            planner_class="unknown",
            execution_identity="harness_only",
            provider_client_bound=False,
            offline_session=True,
        ),
        timing=_placeholder_timing(request_start, terminal_ready),
        slot_key=slot,
        request_key=slot.request_key,
    )


def _infrastructure_terminal(
    *,
    slot: SlotKey,
    mode: Literal["single_signal", "paired_reference"],
    kind: Literal["infrastructure", "unknown"],
    detail: str,
    request_start: float,
    terminal_ready: float,
    provenance: ExecutionProvenance | None = None,
) -> StudyTerminal:
    return StudyTerminal(
        run_id=f"infra_{slot.request_key[:12]}_{slot.arm}_{slot.round_index}",
        arm=slot.arm,
        mode=mode,
        status="failed",
        failure_cause=FailureCause(kind=kind, detail=detail),
        task_assessment=_DEFAULT_ASSESSMENT,
        provenance=provenance
        or ExecutionProvenance(
            planner_class="unknown",
            execution_identity="harness_only",
            provider_client_bound=False,
            offline_session=True,
        ),
        timing=_placeholder_timing(request_start, terminal_ready),
        slot_key=slot,
        request_key=slot.request_key,
    )


def _attach_outer_timing(
    terminal: StudyTerminal,
    *,
    request_start: float,
    terminal_ready: float,
    slot: SlotKey,
) -> StudyTerminal:
    phase_markers: tuple[PhaseMarker, ...] = ()
    residual: tuple[str, ...] = ()
    if terminal.timing is not None:
        phase_markers = terminal.timing.phase_markers
        residual = terminal.timing.residual_overhead_notes
    timing = RequestTiming(
        timing_contract=TIMING_CONTRACT_V1,
        request_start=request_start,
        terminal_result_ready=terminal_ready,
        elapsed_s=terminal_ready - request_start,
        phase_markers=phase_markers,
        residual_overhead_notes=residual,
    )
    return terminal.model_copy(
        update={
            "timing": timing,
            "slot_key": slot,
            "request_key": slot.request_key,
        }
    )


async def _teardown_session(
    session: ArmSession,
    *,
    clock: Callable[[], float],
) -> tuple[float, str | None]:
    started = float(clock())
    error: str | None = None
    try:
        await session.aclose()
    except Exception as exc:  # noqa: BLE001 — teardown errors are recorded, not raised
        error = f"{type(exc).__name__}: {exc}"
    return float(clock()) - started, error


async def _drain_cancelled_worker(
    task: asyncio.Task[StudyTerminal],
    *,
    grace_s: float,
) -> bool:
    """Return True when the cancelled worker drained; False if still running."""
    if task.done():
        with suppress(asyncio.CancelledError, Exception):
            task.result()
        return True
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=grace_s)
    except TimeoutError:
        return False
    except asyncio.CancelledError:
        return True
    except Exception:  # noqa: BLE001
        return True
    return task.done()


async def _dispatch_slot(
    *,
    slot: SlotKey,
    request: ByteRequest,
    session: ArmSession,
    deadline_s: float,
    clock: Callable[[], float],
    wall_timeout_s: float | None,
) -> tuple[StudyTerminal, float | None, str | None, bool, bool]:
    """Measured dispatch with cancel/teardown.

    Returns
    -------
    terminal, teardown_duration_s, teardown_error, drain_failed, stop_campaign
    """
    request_start = float(clock())
    worker = asyncio.create_task(session.execute(request), name=f"slot:{slot.arm}")

    async def _await_worker() -> StudyTerminal:
        if wall_timeout_s is None:
            return await worker
        return await asyncio.wait_for(worker, timeout=wall_timeout_s)

    timed_out = False
    raised: BaseException | None = None
    raw_terminal: StudyTerminal | None = None
    try:
        raw_terminal = await _await_worker()
    except TimeoutError as exc:
        timed_out = True
        raised = exc
    except asyncio.CancelledError as exc:
        timed_out = True
        raised = exc
    except Exception as exc:  # noqa: BLE001
        raised = exc

    terminal_ready = float(clock())
    elapsed = terminal_ready - request_start
    drain_failed = False

    if timed_out or (math.isfinite(elapsed) and elapsed > deadline_s and raw_terminal is None):
        drained = await _drain_cancelled_worker(worker, grace_s=_DRAIN_GRACE_S)
        teardown_duration, teardown_error = await _teardown_session(session, clock=clock)
        if not drained:
            drain_failed = True
            terminal = _infrastructure_terminal(
                slot=slot,
                mode=request.mode,
                kind="infrastructure",
                detail="timed_out_worker_could_not_be_drained",
                request_start=request_start,
                terminal_ready=terminal_ready,
            )
            if _session_background_worker_alive(session):
                drain_failed = True
            return terminal, teardown_duration, teardown_error, True, True
        terminal = _deadline_terminal(
            slot=slot,
            mode=request.mode,
            request_start=request_start,
            terminal_ready=terminal_ready,
            detail="async_deadline_exceeded",
        )
        if _session_background_worker_alive(session):
            drain_failed = True
        return terminal, teardown_duration, teardown_error, drain_failed, True

    if raised is not None and raw_terminal is None:
        drained = True
        if not worker.done():
            drained = await _drain_cancelled_worker(worker, grace_s=_DRAIN_GRACE_S)
        teardown_duration, teardown_error = await _teardown_session(session, clock=clock)
        detail = f"{type(raised).__name__}: {raised}"
        kind: Literal["infrastructure", "unknown"] = "unknown"
        if isinstance(raised, (OSError, TimeoutError, ConnectionError)):
            kind = "infrastructure"
        lowered = detail.lower()
        if any(
            token in lowered
            for token in (
                "auth",
                "transport",
                "persist",
                "permission",
                "credential",
                "connection",
            )
        ):
            kind = "infrastructure"
        terminal = _infrastructure_terminal(
            slot=slot,
            mode=request.mode,
            kind=kind,
            detail=detail,
            request_start=request_start,
            terminal_ready=terminal_ready,
        )
        if _session_background_worker_alive(session):
            drain_failed = True
        return terminal, teardown_duration, teardown_error, not drained or drain_failed, True

    assert raw_terminal is not None
    terminal = _attach_outer_timing(
        raw_terminal,
        request_start=request_start,
        terminal_ready=terminal_ready,
        slot=slot,
    )

    # Independent readiness check: async timeout alone must not accept sync overruns.
    if not math.isfinite(elapsed) or elapsed > deadline_s:
        teardown_duration, teardown_error = await _teardown_session(session, clock=clock)
        detail = f"terminal_ready_elapsed_s={elapsed} deadline_s={deadline_s}"
        terminal = _deadline_terminal(
            slot=slot,
            mode=request.mode,
            request_start=request_start,
            terminal_ready=terminal_ready,
            detail=detail,
            provenance=terminal.provenance,
        )
        if _session_background_worker_alive(session):
            drain_failed = True
        return terminal, teardown_duration, teardown_error, drain_failed, True

    try:
        if terminal.timing is not None and terminal.timing.phase_markers:
            validate_request_timing(terminal.timing)
    except TimingValidationError as exc:
        teardown_duration, teardown_error = await _teardown_session(session, clock=clock)
        terminal = _infrastructure_terminal(
            slot=slot,
            mode=request.mode,
            kind="infrastructure",
            detail=f"timing_validation:{exc}",
            request_start=request_start,
            terminal_ready=terminal_ready,
            provenance=terminal.provenance,
        )
        if _session_background_worker_alive(session):
            drain_failed = True
        return terminal, teardown_duration, teardown_error, drain_failed, True

    classified = classify_failure_cause(terminal)
    if terminal.status == "failed":
        terminal = terminal.model_copy(update={"failure_cause": classified})

    teardown_duration, teardown_error = await _teardown_session(session, clock=clock)
    if _session_background_worker_alive(session):
        drain_failed = True
    stop = _is_infrastructure_stop(classified)
    return terminal, teardown_duration, teardown_error, drain_failed, stop


def _resolve_request(
    slot: SlotKey,
    schedule: Schedule,
    requests_by_key: Mapping[str, ByteRequest],
) -> ByteRequest:
    if slot.request_key in requests_by_key:
        return requests_by_key[slot.request_key]
    for canonical in schedule.canonical_requests:
        if canonical.request_key == slot.request_key:
            return canonical.byte_request
    raise CampaignPreflightError(f"no ByteRequest for slot key {slot.request_key}")


def _write_campaign_artifacts(output_dir: Path, record: CampaignRecord) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "campaign_record.json"
    payload = record.model_dump(mode="json")
    ledger_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


async def run_schedule(
    schedule: Schedule,
    protocol: StudyProtocolV2,
    session_factory: Callable[[SlotKey], Awaitable[ArmSession]],
    *,
    execution_mode: ExecutionMode,
    clock: Callable[[], float] | None = None,
    requests_by_key: Mapping[str, ByteRequest] | None = None,
    output_dir: Path | None = None,
    budget_assessment: BudgetAssessment | None = None,
    verified_seal_digest: str | None = None,
    authorization_reference: str | None = None,
    wall_timeout: bool = True,
) -> CampaignRecord:
    """Execute the frozen schedule sequentially with typed failure accounting.

    Factory performs no slot analysis. One campaign attempt per slot; no dynamic
    retry or reorder. Behavioral failures continue; infrastructure stops preserve
    the full schedule and block accepted conclusions.
    """
    tick = clock if clock is not None else time.perf_counter
    request_map = dict(requests_by_key or {})

    if execution_mode == "online":
        reject_online_preflight(
            verified_seal_digest=verified_seal_digest,
            authorization_reference=authorization_reference,
            budget=budget_assessment,
        )

    if output_dir is not None and output_dir.exists() and any(output_dir.iterdir()):
        raise CampaignPreflightError(
            f"campaign output directory must be fresh/empty: {output_dir}"
        )

    records: list[SlotAttemptRecord] = []
    status: CampaignStatus = "completed"
    stopped_after: SlotKey | None = None
    limitations: list[str] = []

    for index, slot in enumerate(schedule.slots):
        if stopped_after is not None:
            records.append(
                SlotAttemptRecord(
                    slot_key=slot,
                    status="unstarted",
                    attempt_count=0,
                )
            )
            continue

        request = _resolve_request(slot, schedule, request_map)
        session = await session_factory(slot)
        wall_timeout_s = protocol.deadline_s if wall_timeout else None
        (
            terminal,
            teardown_duration,
            teardown_error,
            drain_failed,
            stop_campaign,
        ) = await _dispatch_slot(
            slot=slot,
            request=request,
            session=session,
            deadline_s=protocol.deadline_s,
            clock=tick,
            wall_timeout_s=wall_timeout_s,
        )
        telemetry = collect_resource_telemetry(terminal)
        slot_status: Literal["completed", "failed"]
        if terminal.status == "completed":
            slot_status = "completed"
        else:
            slot_status = "failed"
        attempt = SlotAttemptRecord(
            slot_key=slot,
            status=slot_status,
            attempt_count=1,
            terminal=terminal,
            resource_telemetry=telemetry,
            teardown_duration_s=teardown_duration,
            teardown_error=teardown_error,
            drain_failed=drain_failed,
            stop_campaign=stop_campaign,
        )
        records.append(attempt)

        if stop_campaign or drain_failed:
            status = "infrastructure_stopped"
            stopped_after = slot
            limitations.append(
                f"stopped_after_slot_index={index}:{slot.arm}:{slot.round_index}"
            )
            if drain_failed:
                limitations.append("timed_out_worker_could_not_be_drained")
            # Mark remaining slots unstarted without reordering.
            for remaining in schedule.slots[index + 1 :]:
                records.append(
                    SlotAttemptRecord(
                        slot_key=remaining,
                        status="unstarted",
                        attempt_count=0,
                    )
                )
            break

    if len(records) != len(schedule.slots):
        raise RuntimeError("campaign failed to cover full schedule")

    attempted = sum(1 for item in records if item.attempt_count == 1)
    completed = sum(1 for item in records if item.status == "completed")
    failed = sum(1 for item in records if item.status == "failed")
    unstarted = sum(1 for item in records if item.status == "unstarted")
    accepted = status == "completed" and unstarted == 0

    record = CampaignRecord(
        schedule_digest=schedule.schedule_digest,
        execution_mode=execution_mode,
        status=status,
        slot_records=tuple(records),
        planned_slot_count=len(schedule.slots),
        attempted_slot_count=attempted,
        completed_slot_count=completed,
        failed_slot_count=failed,
        unstarted_slot_count=unstarted,
        stopped_after=stopped_after,
        accepted_conclusion_available=accepted,
        budget_assessment=budget_assessment,
        schedule_order_preserved=True,
        campaign_retry_policy="forbidden",
        limitations=tuple(limitations),
    )
    if output_dir is not None:
        _write_campaign_artifacts(output_dir, record)
    return record
