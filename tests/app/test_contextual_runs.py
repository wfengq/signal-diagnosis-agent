"""T-CX090–T-CX095: contextual run store and executor lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

import pytest

from signal_diag.agent.models import AgentRunResult
from signal_diag.app.contextual_models import ContextualAppRunSnapshot
from signal_diag.app.contextual_runs import (
    BoundedContextualRunExecutor,
    ContextualRunExecutionResult,
    ContextualRunWorkItem,
    InMemoryContextualRunStore,
)
from signal_diag.app.errors import AppCapacityError, RunNotFoundError
from signal_diag.app.models import (
    AppErrorDetail,
    PlannerIdentity,
    SourceSummary,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
STARTED = datetime(2026, 9, 4, 12, 1, tzinfo=UTC)
FINISHED = datetime(2026, 9, 4, 12, 2, tzinfo=UTC)


def _source(name: str = "test.wav") -> SourceSummary:
    return SourceSummary(
        source_kind="wav",
        display_name=name,
        sample_rate_hz=48_000,
        channels=1,
        num_frames=48_000,
        duration_s=1.0,
        bits_per_sample=16,
    )


def _preview() -> WaveformPreview:
    return WaveformPreview(
        sample_rate_hz=48_000,
        original_num_samples=1,
        points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.5),),
    )


def _planner() -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="v0.3-s1-planner-9.5",
        phase4_certified_default=True,
    )


def _context() -> StimulusContext:
    return StimulusContext(
        mode="paired_reference",
        test_signal_id="sig_test",
        reference_signal_id="sig_ref",
        assertion_source="user_supplied",
    )


def _caps(*, paired: bool = True) -> EffectiveCapabilities:
    return EffectiveCapabilities(paired_harmonic_attribution=paired)


def _agent_result(run_id: str = "run_agent") -> AgentRunResult:
    return AgentRunResult(
        run_id=run_id,
        status="success",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="planner_finished",
    )


def _snapshot(**overrides: object) -> ContextualAppRunSnapshot:
    payload: dict[str, object] = {
        "run_id": "run_" + "0" * 32,
        "status": "queued",
        "created_at": NOW,
        "user_request": "Why does this signal sound distorted?",
        "analyzed_channel": "mixdown",
        "test_source": _source("test.wav"),
        "reference_source": _source("ref.wav"),
        "stimulus_context": _context(),
        "effective_capabilities": _caps(),
        "test_preview": _preview(),
        "planner_identity": _planner(),
    }
    payload.update(overrides)
    return ContextualAppRunSnapshot.model_validate(payload)


def _run_id(digit: str) -> str:
    return "run_" + digit * 32


def _opaque_run(index: int) -> str:
    return f"run_{index:032x}"


def _opaque_signal(index: int) -> str:
    return f"sig_{index:032x}"


def _work(
    run_id: str,
    execute: Callable[[], Awaitable[ContextualRunExecutionResult]],
) -> ContextualRunWorkItem:
    return ContextualRunWorkItem(run_id=run_id, execute=execute)


def _successful_execution(
    run_id: str,
    *,
    caps: EffectiveCapabilities | None = None,
) -> ContextualRunExecutionResult:
    return ContextualRunExecutionResult(
        result=_agent_result(run_id),
        trace_events=(),
        effective_capabilities=caps or _caps(paired=False),
    )


async def _instant_success() -> ContextualRunExecutionResult:
    return _successful_execution("run_" + "f" * 32)


@pytest.fixture
def cleaned() -> list[tuple[str, ...]]:
    return []


@pytest.fixture
def store(cleaned: list[tuple[str, ...]]) -> InMemoryContextualRunStore:
    return InMemoryContextualRunStore(cleanup=cleaned.append)


@pytest.fixture
async def executor(
    store: InMemoryContextualRunStore,
) -> AsyncIterator[BoundedContextualRunExecutor]:
    instance = BoundedContextualRunExecutor(store, clock=lambda: NOW)
    yield instance
    await instance.aclose()


@pytest.mark.asyncio
async def test_t_cx090_one_active_and_fifo_four_queued(
    executor: BoundedContextualRunExecutor,
    store: InMemoryContextualRunStore,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def first() -> ContextualRunExecutionResult:
        entered.set()
        await release.wait()
        return _successful_execution(_run_id("1"))

    try:
        await executor.submit(_work(_run_id("1"), first), _snapshot(run_id=_run_id("1")))
        await entered.wait()
        assert store.get(_run_id("1")).status == "running"
        for digit in "2345":
            await executor.submit(
                _work(_run_id(digit), _instant_success),
                _snapshot(run_id=_run_id(digit)),
            )
            assert store.get(_run_id(digit)).status == "queued"
        with pytest.raises(AppCapacityError):
            await executor.submit(
                _work(_run_id("6"), _instant_success),
                _snapshot(run_id=_run_id("6")),
            )
        with pytest.raises(RunNotFoundError):
            store.get(_run_id("6"))
        release.set()
        await executor.wait_idle()
    finally:
        release.set()

    for digit in "12345":
        assert store.get(_run_id(digit)).status == "completed"


@pytest.mark.asyncio
async def test_t_cx091_terminal_retention_cleans_two_signal_pairs(
    cleaned: list[tuple[str, ...]],
) -> None:
    store = InMemoryContextualRunStore(cleanup=cleaned.append)
    executor = BoundedContextualRunExecutor(store, clock=lambda: NOW)
    try:
        for index in range(20):
            run_id = _opaque_run(index)
            await executor.submit(
                _work(run_id, _instant_success),
                _snapshot(run_id=run_id),
                (
                    _opaque_signal(index),
                    _opaque_signal(index + 100),
                    _opaque_signal(index + 200),
                    _opaque_signal(index + 300),
                ),
            )
            await executor.wait_idle()

        new_id = _opaque_run(20)
        await executor.submit(
            _work(new_id, _instant_success),
            _snapshot(run_id=new_id),
            (
                _opaque_signal(20),
                _opaque_signal(120),
                _opaque_signal(220),
                _opaque_signal(320),
            ),
        )
        with pytest.raises(RunNotFoundError):
            store.get(_opaque_run(0))
        assert cleaned == [
            (
                _opaque_signal(0),
                _opaque_signal(100),
                _opaque_signal(200),
                _opaque_signal(300),
            )
        ]
        await executor.wait_idle()
    finally:
        await executor.aclose()


@pytest.mark.asyncio
async def test_t_cx092_get_returns_deep_copies(
    executor: BoundedContextualRunExecutor,
    store: InMemoryContextualRunStore,
) -> None:
    run_id = _run_id("a")
    await executor.submit(_work(run_id, _instant_success), _snapshot(run_id=run_id))
    await executor.wait_idle()
    first = store.get(run_id)
    second = store.get(run_id)
    assert first == second
    assert first is not second
    assert first.test_source is not second.test_source
    assert first.effective_capabilities is not second.effective_capabilities


@pytest.mark.asyncio
async def test_t_cx093_completion_updates_terminal_capabilities(
    executor: BoundedContextualRunExecutor,
    store: InMemoryContextualRunStore,
) -> None:
    run_id = _run_id("b")
    terminal_caps = _caps(paired=False)

    async def execute() -> ContextualRunExecutionResult:
        return _successful_execution(run_id, caps=terminal_caps)

    await executor.submit(
        _work(run_id, execute),
        _snapshot(run_id=run_id, effective_capabilities=_caps(paired=True)),
    )
    await executor.wait_idle()
    completed = store.get(run_id)
    assert completed.status == "completed"
    assert completed.effective_capabilities.paired_harmonic_attribution is False
    assert completed.effective_capabilities.clipping is True


@pytest.mark.asyncio
async def test_t_cx094_aclose_fails_queued_and_awaits_active(
    cleaned: list[tuple[str, ...]],
) -> None:
    store = InMemoryContextualRunStore(cleanup=cleaned.append)
    executor = BoundedContextualRunExecutor(store, clock=lambda: NOW)
    entered = asyncio.Event()
    release = asyncio.Event()
    active_id = _opaque_run(1)
    queued_id = _opaque_run(2)

    async def hold() -> ContextualRunExecutionResult:
        entered.set()
        await release.wait()
        return _successful_execution(active_id)

    try:
        await executor.submit(
            _work(active_id, hold),
            _snapshot(run_id=active_id),
            (_opaque_signal(1), _opaque_signal(2)),
        )
        await entered.wait()
        await executor.submit(
            _work(queued_id, _instant_success),
            _snapshot(run_id=queued_id),
            (_opaque_signal(3), _opaque_signal(4), _opaque_signal(5), _opaque_signal(6)),
        )
        closing = asyncio.create_task(executor.aclose())
        failed = await store.wait_for_terminal(queued_id)
        assert failed.status == "failed"
        assert failed.application_error is not None
        assert store.get(active_id).status == "running"
        assert cleaned == []
        release.set()
        await closing
        assert store.get(active_id).status == "completed"
    finally:
        release.set()
        await executor.aclose()


@pytest.mark.asyncio
async def test_t_cx095_queue_full_rolls_back_reservation(
    store: InMemoryContextualRunStore,
) -> None:
    executor = BoundedContextualRunExecutor(store, clock=lambda: NOW)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> ContextualRunExecutionResult:
        entered.set()
        await release.wait()
        return _successful_execution(_run_id("1"))

    try:
        await executor.submit(_work(_run_id("1"), hold), _snapshot(run_id=_run_id("1")))
        await entered.wait()
        for digit in "2345":
            await executor.submit(
                _work(_run_id(digit), _instant_success),
                _snapshot(run_id=_run_id(digit)),
            )
        with pytest.raises(AppCapacityError):
            await executor.submit(
                _work(_run_id("6"), _instant_success),
                _snapshot(run_id=_run_id("6")),
            )
        with pytest.raises(RunNotFoundError):
            store.get(_run_id("6"))
    finally:
        release.set()
        await executor.aclose()
