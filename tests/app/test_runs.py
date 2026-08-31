"""Checkpoint W — atomic RunStore and one-worker FIFO executor (T241–T245)."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from signal_diag.agent.models import AgentRunResult
from signal_diag.app.errors import (
    AppCapacityError,
    ApplicationError,
    RunNotFoundError,
    sanitize_application_error,
)
from signal_diag.app.models import (
    AppErrorDetail,
    AppRunSnapshot,
    PlannerIdentity,
    SourceSummary,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.app.runs import (
    BoundedRunExecutor,
    InMemoryRunStore,
    RunExecutionResult,
    RunWorkItem,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
STARTED = datetime(2026, 8, 31, 12, 1, tzinfo=UTC)
FINISHED = datetime(2026, 8, 31, 12, 2, tzinfo=UTC)
RUNS_PATH = Path(__file__).resolve().parents[2] / "src" / "signal_diag" / "app" / "runs.py"


def _wav_source() -> SourceSummary:
    return SourceSummary(
        source_kind="wav",
        display_name="input.wav",
        sample_rate_hz=48_000,
        channels=2,
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
        prompt_version="v0.2-s1-planner-8.1",
        phase4_certified_default=True,
    )


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


def _snapshot(**overrides: object) -> AppRunSnapshot:
    payload: dict[str, object] = {
        "run_id": "run_" + "0" * 32,
        "status": "queued",
        "created_at": NOW,
        "user_request": "Why does this signal sound distorted?",
        "analyzed_channel": "mixdown",
        "source": _wav_source(),
        "planner_identity": _planner(),
        "waveform_preview": _preview(),
    }
    payload.update(overrides)
    return AppRunSnapshot.model_validate(payload)


def _run_id(digit: str) -> str:
    return "run_" + digit * 32


def _opaque_run(index: int) -> str:
    return f"run_{index:032x}"


def _opaque_signal(index: int) -> str:
    return f"sig_{index:032x}"


def _work(
    run_id: str,
    execute: Callable[[], Awaitable[RunExecutionResult]],
) -> RunWorkItem:
    return RunWorkItem(run_id=run_id, execute=execute)


def _successful_execution(run_id: str) -> RunExecutionResult:
    return RunExecutionResult(result=_agent_result(run_id), trace_events=())


async def _instant_success() -> RunExecutionResult:
    return _successful_execution("run_" + "f" * 32)


@pytest.fixture
def cleaned() -> list[tuple[str, ...]]:
    return []


@pytest.fixture
def store(cleaned: list[tuple[str, ...]]) -> InMemoryRunStore:
    return InMemoryRunStore(cleanup=cleaned.append)


@pytest.fixture
async def executor(store: InMemoryRunStore) -> AsyncIterator[BoundedRunExecutor]:
    instance = BoundedRunExecutor(store, clock=lambda: NOW)
    yield instance
    await instance.aclose()


def test_t245_executor_constructs_outside_event_loop() -> None:
    standalone = InMemoryRunStore(cleanup=lambda _ids: None)
    BoundedRunExecutor(standalone)


@pytest.mark.asyncio
async def test_t241_one_active_and_fifo_four_queued(
    executor: BoundedRunExecutor,
    store: InMemoryRunStore,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    order: list[str] = []

    async def first() -> RunExecutionResult:
        order.append("first")
        entered.set()
        await release.wait()
        return _successful_execution("run_" + "1" * 32)

    try:
        await executor.submit(_work("run_" + "1" * 32, first))
        await entered.wait()
        assert store.get("run_" + "1" * 32).status == "running"
        for digit in "2345":
            await executor.submit(_work("run_" + digit * 32, _instant_success))
            assert store.get("run_" + digit * 32).status == "queued"
        with pytest.raises(AppCapacityError) as capacity:
            await executor.submit(_work("run_" + "6" * 32, _instant_success))
        assert capacity.value.detail.code == "capacity_exceeded"
        with pytest.raises(RunNotFoundError):
            store.get("run_" + "6" * 32)
        release.set()
        await executor.wait_idle()
    finally:
        release.set()

    assert order[0] == "first"
    for digit in "12345":
        snapshot = store.get("run_" + digit * 32)
        assert snapshot.status == "completed"
        assert snapshot.started_at is not None
        assert snapshot.finished_at is not None
        assert snapshot.result is not None
        assert snapshot.application_error is None


@pytest.mark.asyncio
async def test_t241_fifo_and_next_starts_only_after_terminal(
    executor: BoundedRunExecutor,
    store: InMemoryRunStore,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    order: list[str] = []

    async def first() -> RunExecutionResult:
        order.append("first")
        entered.set()
        await release.wait()
        return _successful_execution(_run_id("1"))

    def tracked(name: str) -> Callable[[], Awaitable[RunExecutionResult]]:
        async def execute() -> RunExecutionResult:
            assert store.get(_run_id("1")).status == "completed"
            order.append(name)
            return _successful_execution(_run_id(name))

        return execute

    try:
        await executor.submit(_work(_run_id("1"), first))
        await entered.wait()
        for digit in "2345":
            await executor.submit(_work(_run_id(digit), tracked(digit)))
        release.set()
        await executor.wait_idle()
    finally:
        release.set()

    assert order == ["first", "2", "3", "4", "5"]


@pytest.mark.asyncio
async def test_t241_monotonic_transitions_and_concurrent_polling(
    executor: BoundedRunExecutor,
    store: InMemoryRunStore,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    run_id = _run_id("a")
    seen: list[str] = []

    async def blocked() -> RunExecutionResult:
        seen.append(store.get(run_id).status)
        entered.set()
        await release.wait()
        return _successful_execution(run_id)

    try:
        await executor.submit(_work(run_id, blocked))
        await entered.wait()
        running = store.get(run_id)
        assert running.status == "running"
        copies = await asyncio.gather(*[asyncio.sleep(0, result=store.get(run_id)) for _ in range(8)])
        assert all(copy.status == "running" for copy in copies)
        assert all(copy == running for copy in copies)
        assert len({id(copy) for copy in copies}) == 8
        assert copies[0].source is not copies[1].source
        release.set()
        await executor.wait_idle()
    finally:
        release.set()

    completed = store.get(run_id)
    assert seen == ["running"]
    assert completed.status == "completed"
    again = store.get(run_id)
    assert again == completed
    assert again is not completed
    assert again.result is not completed.result


@pytest.mark.asyncio
async def test_t242_latest_twenty_terminal_evicts_oldest_on_admission(
    cleaned: list[tuple[str, ...]],
) -> None:
    store = InMemoryRunStore(cleanup=cleaned.append)
    executor = BoundedRunExecutor(store, clock=lambda: NOW)
    try:
        for index in range(20):
            run_id = _opaque_run(index)
            await executor.submit(
                _work(run_id, _instant_success),
                _snapshot(run_id=run_id),
                (_opaque_signal(index),),
            )
            await executor.wait_idle()
            assert store.get(run_id).status == "completed"

        for index in range(20):
            store.get(_opaque_run(index))

        new_id = _opaque_run(20)
        await executor.submit(
            _work(new_id, _instant_success),
            _snapshot(run_id=new_id),
            (_opaque_signal(20),),
        )
        with pytest.raises(RunNotFoundError) as missing:
            store.get(_opaque_run(0))
        assert missing.value.detail.code == "run_not_found"
        assert cleaned == [(_opaque_signal(0),)]
        for index in range(1, 21):
            assert store.get(_opaque_run(index)).run_id == _opaque_run(index)
        await executor.wait_idle()
        assert store.get(new_id).status == "completed"
        assert cleaned == [(_opaque_signal(0),)]
    finally:
        await executor.aclose()


@pytest.mark.asyncio
async def test_t243_queued_and_running_are_never_evicted() -> None:
    cleaned: list[tuple[str, ...]] = []
    store = InMemoryRunStore(terminal_limit=2, cleanup=cleaned.append)
    executor = BoundedRunExecutor(store, clock=lambda: NOW)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> RunExecutionResult:
        entered.set()
        await release.wait()
        return _successful_execution(_opaque_run(10))

    try:
        for index in range(2):
            run_id = _opaque_run(index)
            await executor.submit(
                _work(run_id, _instant_success),
                _snapshot(run_id=run_id),
                (_opaque_signal(index), _opaque_signal(index + 100)),
            )
            await executor.wait_idle()

        running_id = _opaque_run(10)
        await executor.submit(
            _work(running_id, hold),
            _snapshot(run_id=running_id),
            (_opaque_signal(10),),
        )
        await entered.wait()
        queued_ids = [_opaque_run(11), _opaque_run(12)]
        for index, run_id in enumerate(queued_ids, start=11):
            await executor.submit(
                _work(run_id, _instant_success),
                _snapshot(run_id=run_id),
                (_opaque_signal(index),),
            )

        with pytest.raises(RunNotFoundError):
            store.get(_opaque_run(0))
        assert store.get(_opaque_run(1)).status == "completed"
        assert store.get(running_id).status == "running"
        assert store.get(queued_ids[0]).status == "queued"
        assert store.get(queued_ids[1]).status == "queued"
        assert (_opaque_signal(10),) not in cleaned
        assert (_opaque_signal(11),) not in cleaned
        assert all(_opaque_signal(1) not in owned for owned in cleaned)
        release.set()
        await executor.wait_idle()
    finally:
        release.set()
        await executor.aclose()


@pytest.mark.asyncio
async def test_t243_eviction_cleanup_owns_only_that_run() -> None:
    cleaned: list[tuple[str, ...]] = []
    store = InMemoryRunStore(terminal_limit=1, cleanup=cleaned.append)
    executor = BoundedRunExecutor(store, clock=lambda: NOW)
    try:
        first = _opaque_run(1)
        second = _opaque_run(2)
        await executor.submit(
            _work(first, _instant_success),
            _snapshot(run_id=first),
            (_opaque_signal(1), _opaque_signal(91)),
        )
        await executor.wait_idle()
        await executor.submit(
            _work(second, _instant_success),
            _snapshot(run_id=second),
            (_opaque_signal(2),),
        )
        with pytest.raises(RunNotFoundError):
            store.get(first)
        assert cleaned == [(_opaque_signal(1), _opaque_signal(91))]
        assert store.get(second).run_id == second
        await executor.wait_idle()
        assert cleaned == [(_opaque_signal(1), _opaque_signal(91))]
    finally:
        await executor.aclose()


@pytest.mark.asyncio
async def test_t244_capacity_unknown_id_and_illegal_transitions() -> None:
    store = InMemoryRunStore(cleanup=lambda _ids: None)
    first = _opaque_run(1)
    second = _opaque_run(2)
    await store.reserve(_snapshot(run_id=first))
    queued = store.get(first)
    with pytest.raises(ValueError):
        await store.mark_completed(
            first,
            finished_at=FINISHED,
            result=_agent_result(),
            trace_events=(),
        )
    assert store.get(first) == queued
    with pytest.raises(ValueError):
        await store.mark_failed(
            first,
            finished_at=FINISHED,
            error=AppErrorDetail(code="internal_error", message="no"),
        )
    assert store.get(first).status == "queued"

    await store.mark_running(first, started_at=STARTED)
    running = store.get(first)
    await store.reserve(_snapshot(run_id=second))
    with pytest.raises(ValueError):
        await store.mark_running(second, started_at=STARTED)
    assert store.get(second).status == "queued"
    with pytest.raises(ValueError):
        await store.mark_running(first, started_at=STARTED)
    assert store.get(first) == running

    await store.mark_completed(
        first,
        finished_at=FINISHED,
        result=_agent_result(),
        trace_events=(),
    )
    completed = store.get(first)
    with pytest.raises(ValueError):
        await store.mark_failed(
            first,
            finished_at=FINISHED,
            error=AppErrorDetail(code="runtime_error", message="no"),
        )
    assert store.get(first) == completed

    unknown = _opaque_run(9)
    with pytest.raises(RunNotFoundError) as missing:
        store.get(unknown)
    assert missing.value.detail.code == "run_not_found"
    with pytest.raises(RunNotFoundError):
        await store.mark_running(unknown, started_at=STARTED)

    for index in range(3, 6):
        await store.reserve(_snapshot(run_id=_opaque_run(index)))
    with pytest.raises(AppCapacityError) as capacity:
        await store.reserve(_snapshot(run_id=_opaque_run(6)))
    assert capacity.value.detail.code == "capacity_exceeded"
    with pytest.raises(RunNotFoundError):
        store.get(_opaque_run(6))
    assert store.get(second).status == "queued"


@pytest.mark.asyncio
async def test_t244_unexpected_exception_is_sanitized(
    executor: BoundedRunExecutor,
    store: InMemoryRunStore,
) -> None:
    run_id = _run_id("b")

    async def boom() -> RunExecutionResult:
        raise RuntimeError("api_key=secret leaked")

    await executor.submit(_work(run_id, boom))
    await executor.wait_idle()
    snapshot = store.get(run_id)
    assert snapshot.status == "failed"
    assert snapshot.application_error is not None
    assert snapshot.application_error.code == "internal_error"
    assert snapshot.application_error.message == "diagnosis execution failed"
    assert "secret" not in snapshot.application_error.message
    assert snapshot.result is None
    assert snapshot.trace_events == ()

    leaked = sanitize_application_error(RuntimeError("authorization=Bearer sk-secret"))
    assert leaked == AppErrorDetail(
        code="internal_error", message="diagnosis execution failed"
    )
    typed = AppCapacityError(
        AppErrorDetail(code="capacity_exceeded", message="diagnosis capacity exceeded")
    )
    assert sanitize_application_error(typed) == typed.detail


@pytest.mark.asyncio
async def test_t244_application_error_detail_is_preserved(
    executor: BoundedRunExecutor,
    store: InMemoryRunStore,
) -> None:
    run_id = _run_id("c")
    detail = AppErrorDetail(code="provider_error", message="provider unavailable")

    async def boom() -> RunExecutionResult:
        raise ApplicationError(detail)

    await executor.submit(_work(run_id, boom))
    await executor.wait_idle()
    snapshot = store.get(run_id)
    assert snapshot.status == "failed"
    assert snapshot.application_error == detail


@pytest.mark.asyncio
async def test_t245_independent_stores_and_empty_restart() -> None:
    store_a = InMemoryRunStore(cleanup=lambda _ids: None)
    store_b = InMemoryRunStore(cleanup=lambda _ids: None)
    executor_a = BoundedRunExecutor(store_a, clock=lambda: NOW)
    executor_b = BoundedRunExecutor(store_b, clock=lambda: NOW)
    run_a = _run_id("d")
    run_b = _run_id("e")
    try:
        await executor_a.submit(_work(run_a, _instant_success))
        await executor_a.wait_idle()
        with pytest.raises(RunNotFoundError):
            store_b.get(run_a)
        await executor_b.submit(_work(run_b, _instant_success))
        await executor_b.wait_idle()
        with pytest.raises(RunNotFoundError):
            store_a.get(run_b)
        assert store_a.get(run_a).status == "completed"
        restart = InMemoryRunStore(cleanup=lambda _ids: None)
        with pytest.raises(RunNotFoundError):
            restart.get(run_a)
        with pytest.raises(RunNotFoundError):
            restart.get(run_b)
    finally:
        await executor_a.aclose()
        await executor_b.aclose()


@pytest.mark.asyncio
async def test_t245_idempotent_aclose_fails_queued_and_awaits_active() -> None:
    store = InMemoryRunStore(cleanup=lambda _ids: None)
    executor = BoundedRunExecutor(store, clock=lambda: NOW)
    entered = asyncio.Event()
    release = asyncio.Event()
    active_id = _run_id("1")
    queued_id = _run_id("2")

    async def active() -> RunExecutionResult:
        entered.set()
        await release.wait()
        return _successful_execution(active_id)

    try:
        await executor.submit(_work(active_id, active))
        await entered.wait()
        await executor.submit(_work(queued_id, _instant_success))
        assert store.get(queued_id).status == "queued"
        closing = asyncio.create_task(executor.aclose())
        failed_queued = await store.wait_for_terminal(queued_id)
        assert failed_queued.status == "failed"
        assert failed_queued.application_error is not None
        assert "secret" not in failed_queued.application_error.message
        assert store.get(active_id).status == "running"
        assert not closing.done()
        release.set()
        await closing
        assert store.get(active_id).status == "completed"
        await executor.aclose()
        with pytest.raises(AppCapacityError) as closed:
            await executor.submit(_work(_run_id("3"), _instant_success))
        assert closed.value.detail.code == "capacity_exceeded"
    finally:
        release.set()
        await executor.aclose()


def test_t245_no_persistence_cancellation_or_recovery_api() -> None:
    source = RUNS_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    imports: list[str] = []
    function_names: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module.split(".")[0])
            imports.append(node.module)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function_names.add(node.name)
    assert "fastapi" not in imports
    assert "sqlite3" not in imports
    assert "sqlalchemy" not in imports
    assert not any(name.startswith("signal_diag.evaluation") for name in imports)
    assert "cancel" not in function_names
    assert "cancel_run" not in function_names
    assert "save" not in function_names
    assert "load" not in function_names
    assert "recover" not in function_names
    assert not hasattr(BoundedRunExecutor, "cancel")
    assert not hasattr(InMemoryRunStore, "save")
    assert not hasattr(InMemoryRunStore, "load")
    assert "sqlite" not in source.lower()
    assert "postgres" not in source.lower()
    assert "redis" not in source.lower()
