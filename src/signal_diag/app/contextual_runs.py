"""Private contextual in-memory run store and one-worker FIFO executor."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from signal_diag.agent.models import AgentRunResult
from signal_diag.app.context_guidance import build_context_guidance
from signal_diag.app.contextual_models import ContextualAppRunSnapshot
from signal_diag.app.errors import (
    AppCapacityError,
    RunNotFoundError,
    sanitize_application_error,
)
from signal_diag.app.models import (
    AppErrorDetail,
    PlannerIdentity,
    SourceSummary,
    TraceEventView,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext

_QUEUED_LIMIT = 4
_RUNNING_LIMIT = 1
_CLOSED_MESSAGE = "executor closed before execution"
_CAPACITY_MESSAGE = "diagnosis capacity exceeded"
_NOT_FOUND_MESSAGE = "run not found"


@dataclass(frozen=True, slots=True)
class ContextualRunExecutionResult:
    result: AgentRunResult
    trace_events: tuple[TraceEventView, ...]
    effective_capabilities: EffectiveCapabilities


@dataclass(frozen=True, slots=True)
class ContextualRunWorkItem:
    run_id: str
    execute: Callable[[], Awaitable[ContextualRunExecutionResult]]


class _ShutdownSentinel:
    __slots__ = ()


_SHUTDOWN = _ShutdownSentinel()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _capacity_error(message: str = _CAPACITY_MESSAGE) -> AppCapacityError:
    return AppCapacityError(AppErrorDetail(code="capacity_exceeded", message=message))


def _not_found_error() -> RunNotFoundError:
    return RunNotFoundError(AppErrorDetail(code="run_not_found", message=_NOT_FOUND_MESSAGE))


def _placeholder_queued_snapshot(
    run_id: str, *, created_at: datetime
) -> ContextualAppRunSnapshot:
    return ContextualAppRunSnapshot(
        run_id=run_id,
        status="queued",
        created_at=created_at,
        user_request="Why does this signal sound distorted?",
        analyzed_channel="mixdown",
        test_source=SourceSummary(
            source_kind="wav",
            display_name="input.wav",
            sample_rate_hz=48_000,
            channels=2,
            num_frames=48_000,
            duration_s=1.0,
            bits_per_sample=16,
        ),
        reference_source=None,
        stimulus_context=StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_placeholder",
            assertion_source="user_supplied",
            stimulus_kind="single_tone",
            nominal_fundamental_hz=440.0,
        ),
        effective_capabilities=EffectiveCapabilities(nominal_harmonic_attribution=True),
        planner_identity=PlannerIdentity(
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_version="v0.3-s1-planner-9.5",
            phase4_certified_default=True,
        ),
        test_preview=WaveformPreview(
            sample_rate_hz=48_000,
            original_num_samples=1,
            points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.5),),
        ),
    )


class InMemoryContextualRunStore:
    def __init__(
        self,
        *,
        terminal_limit: int = 20,
        cleanup: Callable[[tuple[str, ...]], None],
    ) -> None:
        self._terminal_limit = terminal_limit
        self._cleanup = cleanup
        self._snapshots: dict[str, ContextualAppRunSnapshot] = {}
        self._owned_signal_ids: dict[str, tuple[str, ...]] = {}
        self._terminal_order: deque[str] = deque()
        self._condition = asyncio.Condition()

    def __contains__(self, run_id: object) -> bool:
        return isinstance(run_id, str) and run_id in self._snapshots

    def get(self, run_id: str) -> ContextualAppRunSnapshot:
        snapshot = self._snapshots.get(run_id)
        if snapshot is None:
            raise _not_found_error()
        return snapshot.model_copy(deep=True)

    async def reserve(
        self,
        snapshot: ContextualAppRunSnapshot,
        owned_signal_ids: tuple[str, ...] = (),
    ) -> ContextualAppRunSnapshot:
        if snapshot.status != "queued":
            raise ValueError("reserved snapshot must be queued")
        async with self._condition:
            if snapshot.run_id in self._snapshots:
                raise ValueError(f"run {snapshot.run_id} already exists")
            if self._count_status_locked("queued") >= _QUEUED_LIMIT:
                raise _capacity_error()
            self._evict_oldest_terminals_locked(retain=self._terminal_limit - 1)
            self._snapshots[snapshot.run_id] = snapshot
            self._owned_signal_ids[snapshot.run_id] = tuple(owned_signal_ids)
            self._condition.notify_all()
            return snapshot.model_copy(deep=True)

    async def rollback(self, run_id: str) -> None:
        async with self._condition:
            current = self._snapshots.get(run_id)
            if current is None:
                return
            if current.status != "queued":
                raise ValueError("can only rollback a queued reservation")
            del self._snapshots[run_id]
            self._owned_signal_ids.pop(run_id, None)
            self._condition.notify_all()

    async def mark_running(
        self, run_id: str, *, started_at: datetime
    ) -> ContextualAppRunSnapshot:
        async with self._condition:
            current = self._require_locked(run_id)
            if current.status != "queued":
                raise ValueError(f"illegal transition from {current.status} to running")
            if self._count_status_locked("running") >= _RUNNING_LIMIT:
                raise ValueError("already has a running run")
            updated = current.model_copy(
                update={"status": "running", "started_at": started_at}
            )
            self._snapshots[run_id] = updated
            self._condition.notify_all()
            return updated.model_copy(deep=True)

    async def mark_completed(
        self,
        run_id: str,
        *,
        finished_at: datetime,
        result: AgentRunResult,
        trace_events: tuple[TraceEventView, ...],
        effective_capabilities: EffectiveCapabilities,
    ) -> ContextualAppRunSnapshot:
        async with self._condition:
            current = self._require_locked(run_id)
            if current.status != "running":
                raise ValueError(f"illegal transition from {current.status} to completed")
            updated = current.model_copy(
                update={
                    "status": "completed",
                    "finished_at": finished_at,
                    "result": result,
                    "trace_events": trace_events,
                    "effective_capabilities": effective_capabilities,
                    "application_error": None,
                    "context_guidance": build_context_guidance(
                        mode=current.stimulus_context.mode,
                        result=result,
                    ),
                }
            )
            self._snapshots[run_id] = updated
            self._terminal_order.append(run_id)
            self._evict_oldest_terminals_locked(retain=self._terminal_limit)
            self._condition.notify_all()
            return updated.model_copy(deep=True)

    async def mark_failed(
        self,
        run_id: str,
        *,
        finished_at: datetime,
        error: AppErrorDetail,
    ) -> ContextualAppRunSnapshot:
        async with self._condition:
            current = self._require_locked(run_id)
            if current.status != "running":
                raise ValueError(f"illegal transition from {current.status} to failed")
            updated = current.model_copy(
                update={
                    "status": "failed",
                    "finished_at": finished_at,
                    "application_error": error,
                    "result": None,
                    "trace_events": (),
                }
            )
            self._snapshots[run_id] = updated
            self._terminal_order.append(run_id)
            self._evict_oldest_terminals_locked(retain=self._terminal_limit)
            self._condition.notify_all()
            return updated.model_copy(deep=True)

    async def fail_queued(
        self,
        run_id: str,
        *,
        finished_at: datetime,
        error: AppErrorDetail,
    ) -> ContextualAppRunSnapshot:
        async with self._condition:
            current = self._require_locked(run_id)
            if current.status == "failed":
                return current.model_copy(deep=True)
            if current.status != "queued":
                raise ValueError("fail_queued requires a queued snapshot")
            started_at = max(finished_at, current.created_at)
            actual_finished = max(finished_at, started_at)
            updated = current.model_copy(
                update={
                    "status": "failed",
                    "started_at": started_at,
                    "finished_at": actual_finished,
                    "application_error": error,
                    "result": None,
                    "trace_events": (),
                }
            )
            self._snapshots[run_id] = updated
            self._terminal_order.append(run_id)
            self._evict_oldest_terminals_locked(retain=self._terminal_limit)
            self._condition.notify_all()
            return updated.model_copy(deep=True)

    async def wait_for_terminal(self, run_id: str) -> ContextualAppRunSnapshot:
        async with self._condition:
            while True:
                snapshot = self._snapshots.get(run_id)
                if snapshot is None:
                    raise _not_found_error()
                if snapshot.status in ("completed", "failed"):
                    return snapshot.model_copy(deep=True)
                await self._condition.wait()

    async def wait_until_idle(self) -> None:
        async with self._condition:
            while any(
                snapshot.status in ("queued", "running")
                for snapshot in self._snapshots.values()
            ):
                await self._condition.wait()

    def _require_locked(self, run_id: str) -> ContextualAppRunSnapshot:
        snapshot = self._snapshots.get(run_id)
        if snapshot is None:
            raise _not_found_error()
        return snapshot

    def _count_status_locked(self, status: str) -> int:
        return sum(1 for snapshot in self._snapshots.values() if snapshot.status == status)

    def _evict_oldest_terminals_locked(self, *, retain: int) -> None:
        while len(self._terminal_order) > retain:
            oldest = self._terminal_order.popleft()
            self._snapshots.pop(oldest, None)
            owned = self._owned_signal_ids.pop(oldest, ())
            self._cleanup(owned)


class BoundedContextualRunExecutor:
    def __init__(
        self,
        store: InMemoryContextualRunStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or _utc_now
        self._queue: asyncio.Queue[ContextualRunWorkItem | _ShutdownSentinel] = (
            asyncio.Queue(maxsize=_QUEUED_LIMIT)
        )
        self._admit_lock = asyncio.Lock()
        self._closed = False
        self._worker: asyncio.Task[None] | None = None

    async def submit(
        self,
        item: ContextualRunWorkItem,
        snapshot: ContextualAppRunSnapshot | None = None,
        owned_signal_ids: tuple[str, ...] = (),
    ) -> None:
        async with self._admit_lock:
            if self._closed:
                raise _capacity_error(_CLOSED_MESSAGE)
            self._ensure_worker()
            queued = snapshot
            if queued is None:
                queued = _placeholder_queued_snapshot(
                    item.run_id, created_at=self._clock()
                )
            elif queued.run_id != item.run_id:
                raise ValueError("work item run_id does not match snapshot")
            if item.run_id not in self._store:
                await self._store.reserve(queued, owned_signal_ids)
            try:
                self._queue.put_nowait(item)
            except asyncio.QueueFull:
                await self._store.rollback(item.run_id)
                raise _capacity_error() from None

    async def wait_idle(self) -> None:
        await self._queue.join()
        await self._store.wait_until_idle()

    async def aclose(self) -> None:
        async with self._admit_lock:
            if self._closed:
                return
            self._closed = True
            leftover: list[ContextualRunWorkItem] = []
            while True:
                try:
                    item = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                self._queue.task_done()
                if isinstance(item, ContextualRunWorkItem):
                    leftover.append(item)
        error = AppErrorDetail(code="internal_error", message=_CLOSED_MESSAGE)
        finished_at = self._clock()
        for item in leftover:
            await self._store.fail_queued(
                item.run_id,
                finished_at=finished_at,
                error=error,
            )
        if self._worker is not None:
            await self._queue.put(_SHUTDOWN)
            try:
                await self._worker
            finally:
                self._worker = None

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if isinstance(item, _ShutdownSentinel):
                    break
                if self._closed:
                    await self._store.fail_queued(
                        item.run_id,
                        finished_at=self._clock(),
                        error=AppErrorDetail(
                            code="internal_error",
                            message=_CLOSED_MESSAGE,
                        ),
                    )
                    continue
                await self._store.mark_running(item.run_id, started_at=self._clock())
                try:
                    completed = await item.execute()
                except Exception as error:  # noqa: BLE001 - sanitize unexpected execute failures
                    await self._store.mark_failed(
                        item.run_id,
                        finished_at=self._clock(),
                        error=sanitize_application_error(error),
                    )
                else:
                    await self._store.mark_completed(
                        item.run_id,
                        finished_at=self._clock(),
                        result=completed.result,
                        trace_events=completed.trace_events,
                        effective_capabilities=completed.effective_capabilities,
                    )
            finally:
                self._queue.task_done()
