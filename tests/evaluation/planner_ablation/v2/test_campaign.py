"""T-CX298 / T-CX299: v2 campaign failure accounting, timeout, and limit blockers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from signal_diag.agent.models import TaskAssessment
from signal_diag.agent.policies import AgentLimits
from signal_diag.evaluation.planner_ablation.v2.campaign import (
    CampaignPreflightError,
    collect_resource_telemetry,
    inspect_limits,
    reject_online_preflight,
    run_schedule,
    snapshot_effective_configuration,
)
from signal_diag.evaluation.planner_ablation.v2.models import (
    ByteRequest,
    CanonicalRequest,
    ExecutionProvenance,
    FailureCause,
    Schedule,
    SlotKey,
    StudyProtocolV2,
    StudyTerminal,
)
from signal_diag.evaluation.planner_ablation.v2.timing import ControlledClock

_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_KEY_A = "a" * 64
_KEY_B = "b" * 64
_DIGEST = "c" * 64


def _byte_request() -> ByteRequest:
    return ByteRequest(
        mode="single_signal",
        test_wav_bytes=b"RIFF____WAVEfmt ",
        question="Diagnose supported S1 distortion conservatively.",
    )


def _provenance() -> ExecutionProvenance:
    return ExecutionProvenance(
        planner_class="ScriptedPlanner",
        execution_identity="harness_only",
        provider_client_bound=False,
        offline_session=True,
    )


def _completed(slot: SlotKey | None = None) -> StudyTerminal:
    return StudyTerminal(
        run_id="run_ok",
        arm="product_agent" if slot is None else slot.arm,
        mode="single_signal",
        status="completed",
        outcome="inconclusive",
        claims=(),
        task_assessment=_ASSESSMENT,
        provenance=_provenance(),
        slot_key=slot,
        request_key=None if slot is None else slot.request_key,
    )


def _failed(kind: str, detail: str, *, arm: str = "product_agent") -> StudyTerminal:
    return StudyTerminal(
        run_id="run_fail",
        arm=arm,  # type: ignore[arg-type]
        mode="single_signal",
        status="failed",
        failure_cause=FailureCause(kind=kind, detail=detail),  # type: ignore[arg-type]
        task_assessment=_ASSESSMENT,
        provenance=_provenance(),
    )


def _mini_schedule(*, slots: tuple[SlotKey, ...]) -> Schedule:
    request = _byte_request()
    keys = tuple(dict.fromkeys(slot.request_key for slot in slots))
    canonical = tuple(
        CanonicalRequest(
            request_key=key,
            mode="single_signal",
            representative_scenario_id=f"scenario_{key[:8]}",
            byte_request=request,
        )
        for key in keys
    )
    return Schedule(
        canonical_requests=canonical,
        scenario_aliases={},
        slots=slots,
        schedule_digest=_DIGEST,
    )


class _ScriptedSession:
    def __init__(
        self,
        factory: Callable[[ByteRequest], StudyTerminal] | Callable[[ByteRequest], object],
        *,
        on_close: Callable[[], None] | None = None,
        close_delay_s: float = 0.0,
    ) -> None:
        self._factory = factory
        self._on_close = on_close
        self.closed = False
        self.close_started = False
        self.execute_started = False
        self._close_delay_s = close_delay_s

    async def execute(self, request: ByteRequest) -> StudyTerminal:
        self.execute_started = True
        result = self._factory(request)
        if asyncio.iscoroutine(result):
            return await result  # type: ignore[no-any-return]
        return result  # type: ignore[return-value]

    async def aclose(self) -> None:
        self.close_started = True
        if self._close_delay_s:
            await asyncio.sleep(self._close_delay_s)
        self.closed = True
        if self._on_close is not None:
            self._on_close()


@pytest.mark.asyncio
async def test_behavior_failure_continues_without_retry() -> None:
    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="fixed_pipeline", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=30.0)
    attempts: list[SlotKey] = []

    async def factory(slot: SlotKey) -> _ScriptedSession:
        attempts.append(slot)

        def build(request: ByteRequest) -> StudyTerminal:
            del request
            if slot.request_key == _KEY_A:
                return _failed("behavioral", "max_planner_retries")
            return _completed(slot)

        return _ScriptedSession(build)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
    )

    assert [slot.request_key for slot in attempts] == [_KEY_A, _KEY_B]
    assert len(attempts) == 2
    assert all(
        item.attempt_count == 1 for item in record.slot_records
    ), "one campaign attempt per slot"
    assert record.slot_records[0].status == "failed"
    assert record.slot_records[0].terminal is not None
    assert record.slot_records[0].terminal.failure_cause is not None
    assert record.slot_records[0].terminal.failure_cause.kind == "behavioral"
    assert record.slot_records[1].status == "completed"
    assert record.status == "completed"
    assert record.failed_slot_count == 1
    assert record.accepted_conclusion_available is True
    assert record.campaign_retry_policy == "forbidden"
    assert [item.slot_key for item in record.slot_records] == list(slots)


@pytest.mark.asyncio
async def test_infrastructure_failure_stops_and_preserves_schedule() -> None:
    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_A, arm="fixed_pipeline", round_index=0),
        SlotKey(request_key=_KEY_B, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="fixed_pipeline", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=30.0)
    attempts: list[SlotKey] = []

    async def factory(slot: SlotKey) -> _ScriptedSession:
        attempts.append(slot)

        def build(request: ByteRequest) -> StudyTerminal:
            del request
            if slot.arm == "product_agent" and slot.request_key == _KEY_A:
                return _failed("infrastructure", "provider_auth_exhausted")
            return _completed(slot)

        return _ScriptedSession(build)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
    )

    assert len(attempts) == 1
    assert record.status == "infrastructure_stopped"
    assert record.accepted_conclusion_available is False
    assert record.stopped_after == slots[0]
    assert [item.status for item in record.slot_records] == [
        "failed",
        "unstarted",
        "unstarted",
        "unstarted",
    ]
    assert [item.slot_key for item in record.slot_records] == list(slots)
    assert record.unstarted_slot_count == 3
    assert record.attempted_slot_count == 1


@pytest.mark.asyncio
async def test_timeout_cancels_before_teardown() -> None:
    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="fixed_pipeline", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=0.05)
    events: list[str] = []
    active_workers = 0
    max_overlap = 0
    hang = asyncio.Event()

    async def factory(slot: SlotKey) -> _ScriptedSession:
        async def build(request: ByteRequest) -> StudyTerminal:
            nonlocal active_workers, max_overlap
            del request
            events.append(f"execute:{slot.request_key}")
            active_workers += 1
            max_overlap = max(max_overlap, active_workers)
            try:
                await hang.wait()
                return _completed(slot)
            finally:
                active_workers -= 1

        def on_close() -> None:
            events.append(f"teardown:{slot.request_key}")

        return _ScriptedSession(build, on_close=on_close, close_delay_s=0.02)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=True,
    )

    assert record.status == "infrastructure_stopped"
    assert record.slot_records[0].terminal is not None
    assert record.slot_records[0].terminal.failure_cause is not None
    assert record.slot_records[0].terminal.failure_cause.kind == "deadline_exceeded"
    assert record.slot_records[0].teardown_duration_s is not None
    assert record.slot_records[1].status == "unstarted"
    assert max_overlap == 1
    assert events[0].startswith("execute:")
    assert any(item.startswith("teardown:") for item in events)
    # Teardown for the timed-out slot completes before any later execute.
    teardown_idx = next(i for i, item in enumerate(events) if item.startswith("teardown:"))
    assert not any(item.startswith("execute:") for item in events[teardown_idx + 1 :])

    # Synchronous fixed-path overrun: async timeout alone must not accept a late result.
    clock = ControlledClock(0.0)
    sync_slots = (
        SlotKey(request_key=_KEY_A, arm="fixed_pipeline", round_index=0),
        SlotKey(request_key=_KEY_B, arm="product_agent", round_index=0),
    )
    sync_schedule = _mini_schedule(slots=sync_slots)
    sync_protocol = StudyProtocolV2(deadline_s=1.0)

    async def sync_factory(slot: SlotKey) -> _ScriptedSession:
        def build(request: ByteRequest) -> StudyTerminal:
            del request
            clock.advance(5.0)  # synchronous overrun past deadline
            return _completed(slot)

        return _ScriptedSession(build)

    sync_record = await run_schedule(
        sync_schedule,
        sync_protocol,
        sync_factory,
        execution_mode="offline",
        clock=clock,
        wall_timeout=False,
    )
    assert sync_record.status == "infrastructure_stopped"
    assert sync_record.accepted_conclusion_available is False
    assert sync_record.slot_records[0].terminal is not None
    assert sync_record.slot_records[0].terminal.failure_cause is not None
    assert sync_record.slot_records[0].terminal.failure_cause.kind == "deadline_exceeded"
    assert sync_record.slot_records[1].status == "unstarted"


@pytest.mark.asyncio
async def test_unknown_failure_blocks_campaign() -> None:
    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="fixed_pipeline", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=30.0)

    async def factory(slot: SlotKey) -> _ScriptedSession:
        def build(request: ByteRequest) -> StudyTerminal:
            del request
            if slot.request_key == _KEY_A:
                return _failed("unknown", "unclassified_provider_shape")
            return _completed(slot)

        return _ScriptedSession(build)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
    )
    assert record.status == "infrastructure_stopped"
    assert record.accepted_conclusion_available is False
    assert record.slot_records[0].terminal is not None
    assert record.slot_records[0].terminal.failure_cause is not None
    assert record.slot_records[0].terminal.failure_cause.kind == "unknown"
    assert record.slot_records[1].status == "unstarted"


class _LeakyBackgroundWorkerSession:
    """Reports a live background worker after teardown (drain honesty)."""

    def __init__(self, factory: Callable[[ByteRequest], StudyTerminal]) -> None:
        self._factory = factory
        self._worker_alive = True

    @property
    def background_worker_alive(self) -> bool:
        return self._worker_alive

    async def execute(self, request: ByteRequest) -> StudyTerminal:
        return self._factory(request)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_background_worker_alive_after_teardown_marks_drain_failed() -> None:
    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="fixed_pipeline", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=30.0)

    async def factory(slot: SlotKey) -> _LeakyBackgroundWorkerSession:
        def build(request: ByteRequest) -> StudyTerminal:
            del request
            return _completed(slot)

        return _LeakyBackgroundWorkerSession(build)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
    )
    assert record.slot_records[0].drain_failed is True
    assert record.status == "infrastructure_stopped"
    assert record.accepted_conclusion_available is False
    assert record.slot_records[1].status == "unstarted"


@pytest.mark.asyncio
async def test_oserror_from_session_stops_campaign() -> None:
    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="fixed_pipeline", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=30.0)

    class _OSErrorSession:
        async def execute(self, request: ByteRequest) -> StudyTerminal:
            del request
            raise OSError("disk read failed")

        async def aclose(self) -> None:
            return None

    async def factory(slot: SlotKey) -> _OSErrorSession:
        del slot
        return _OSErrorSession()

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
    )
    assert record.status == "infrastructure_stopped"
    assert record.slot_records[0].terminal is not None
    assert record.slot_records[0].terminal.failure_cause is not None
    assert record.slot_records[0].terminal.failure_cause.kind == "infrastructure"
    assert record.slot_records[1].status == "unstarted"


def test_limits_and_telemetry_block_unknowns() -> None:
    # Merge-audited AgentLimits defaults are visible but do not prove request/token bounds.
    config = snapshot_effective_configuration(limits=AgentLimits())
    assert config.max_tool_calls == 8
    assert config.max_planner_retries == 2
    assert config.max_no_progress == 2
    assert config.max_rule_evaluations == 4
    assert config.max_knowledge_retrievals == 4
    assert config.temperature == 0.0
    assert config.thinking_disabled is True
    assert config.max_tokens_explicit is False
    assert config.request_timeout_explicit is False
    assert config.transport_retry_override_explicit is False

    assessment = inspect_limits(config)
    assert assessment.execution_blocked is True
    assert assessment.seal_ready is False
    assert assessment.worst_case_requests is None
    assert "unknown_max_tokens_bound" in assessment.blockers
    assert "unknown_provider_request_timeout" in assessment.blockers
    assert "unknown_transport_attempts_per_call_bound" in assessment.blockers
    assert "unavailable_retry_telemetry" in assessment.blockers
    assert "unknown_planner_calls_per_slot_bound" in assessment.blockers
    assert "unknown_input_token_bound" in assessment.blockers
    assert "unknown_output_token_bound" in assessment.blockers
    assert any("tool_count_is_not_planner_calls" in item for item in assessment.blockers)

    with pytest.raises(CampaignPreflightError, match="missing_verified_seal"):
        reject_online_preflight(
            verified_seal_digest=None,
            authorization_reference="audit-link-not-permission",
            budget=assessment,
        )
    with pytest.raises(CampaignPreflightError, match="missing_authorization_reference"):
        reject_online_preflight(
            verified_seal_digest="d" * 64,
            authorization_reference=None,
            budget=assessment,
        )
    with pytest.raises(CampaignPreflightError, match="incomplete_budget_preflight"):
        reject_online_preflight(
            verified_seal_digest="d" * 64,
            authorization_reference="audit-link-not-permission",
            budget=assessment,
        )

    terminal = _failed("behavioral", "max_tool_calls")
    telemetry = collect_resource_telemetry(terminal)
    assert telemetry.tool_call_count == 0
    assert "planner_call_count" in telemetry.unknown_fields
    assert "transport_attempt_count" in telemetry.unknown_fields
    assert "input_tokens" in telemetry.unknown_fields
    assert telemetry.credentials_redacted is True
    assert telemetry.raw_waveform_persisted is False
    assert telemetry.raw_fft_persisted is False


def _resource_assessment(*, blocked: bool = True):
    from signal_diag.evaluation.planner_ablation.v2.resource_models import (
        ResourceAssessment,
    )

    return ResourceAssessment(
        planner_turn_ceiling=28,
        sdk_attempt_factor=3,
        logical_call_ceiling=57 * 28,
        sdk_attempt_ceiling=57 * 28 * 3,
        sdk_attempt_ceiling_per_slot=84,
        blockers=("fixture_assessment",) if blocked else (),
        execution_blocked=blocked,
        seal_ready=False,
        fixture_only=True,
    )


class _ResourceSession(_ScriptedSession):
    def __init__(self, *args, ledger, **kwargs):
        super().__init__(*args, **kwargs)
        self._ledger = ledger

    def resource_snapshot(self, *, worker_drained: bool):
        from signal_diag.evaluation.planner_ablation.v2.resource_models import (
            SlotResourceLedger,
        )

        payload = dict(self._ledger)
        payload["worker_drained"] = worker_drained
        payload["incomplete"] = not worker_drained or bool(payload.get("incomplete"))
        if worker_drained and payload.get("run_id") and not payload.get("incomplete"):
            payload["closed"] = True
        else:
            payload["closed"] = False
        return SlotResourceLedger.model_validate(payload)


@pytest.mark.asyncio
async def test_last_slot_resource_failure_blocks_conclusion() -> None:

    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="fixed_pipeline", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=30.0)
    assessment = _resource_assessment(blocked=False)

    async def factory(slot: SlotKey) -> _ResourceSession:
        bad = slot.request_key == _KEY_B
        ledger = {
            "slot_key_digest": f"digest_{slot.request_key}_{slot.arm}",
            "run_id": f"run_{slot.request_key}",
            "events": (),
            "planner_turn_count": 0,
            "repair_attempt_count": 0,
            "logical_call_count": 0,
            "sdk_attempt_count": 0,
            "http_send_attempt_count": 0,
            "exact_total_tokens": 0,
            "potential_token_exposure": 0,
            "pending_event_ids": ("late",) if bad else (),
            "worker_drained": True,
            "telemetry_invalid": False,
            "incomplete": bool(bad),
            "blockers": ("pending_events",) if bad else (),
            "closed": not bad,
        }

        def build(request: ByteRequest) -> StudyTerminal:
            del request
            terminal = _completed(slot)
            return terminal.model_copy(update={"run_id": f"run_{slot.request_key}"})

        return _ResourceSession(build, ledger=ledger)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
        resource_policy="planner_ablation_resource_v1",
        resource_assessment=assessment,
    )
    assert record.status == "resource_stopped"
    assert record.slot_records[0].status == "completed"
    assert record.slot_records[1].status == "completed"
    assert record.unstarted_slot_count == 0
    assert record.accepted_conclusion_available is False
    assert record.slot_records[-1].resource_stop_reason is not None


@pytest.mark.asyncio
async def test_late_callback_prevents_next_slot() -> None:
    slots = (
        SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0),
        SlotKey(request_key=_KEY_B, arm="product_agent", round_index=0),
    )
    schedule = _mini_schedule(slots=slots)
    protocol = StudyProtocolV2(deadline_s=30.0)
    assessment = _resource_assessment(blocked=False)
    started: list[str] = []

    async def factory(slot: SlotKey) -> _ResourceSession:
        started.append(slot.request_key)
        ledger = {
            "slot_key_digest": f"digest_{slot.request_key}",
            "run_id": f"run_{slot.request_key}",
            "events": (),
            "planner_turn_count": 0,
            "repair_attempt_count": 0,
            "logical_call_count": 0,
            "sdk_attempt_count": 0,
            "http_send_attempt_count": 0,
            "exact_total_tokens": 0,
            "pending_event_ids": ("late_callback",),
            "worker_drained": False,
            "telemetry_invalid": False,
            "incomplete": True,
            "blockers": ("pending_events", "worker_not_drained"),
            "closed": False,
        }

        def build(request: ByteRequest) -> StudyTerminal:
            del request
            return _completed(slot).model_copy(
                update={"run_id": f"run_{slot.request_key}"}
            )

        return _ResourceSession(build, ledger=ledger)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
        resource_policy="planner_ablation_resource_v1",
        resource_assessment=assessment,
    )
    assert started == [_KEY_A]
    assert record.status == "resource_stopped"
    assert record.slot_records[1].status == "unstarted"
