"""Arm-neutral request timing for planner-ablation protocol revision (dev_2)."""

from __future__ import annotations

import itertools
import math
import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from signal_diag.evaluation.planner_ablation.v2.models import (
    REQUIRED_PHASES,
    TIMING_CONTRACT_V1,
    ByteRequest,
    PhaseMarker,
    PhaseName,
    RequestTiming,
    StudyTerminal,
)


class TimingValidationError(ValueError):
    """Raised when timing markers cannot support matched comparison."""


class ControlledClock:
    """Deterministic monotonic clock for offline timing proofs."""

    def __init__(self, start: float = 0.0) -> None:
        self.value = float(start)

    def __call__(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += float(delta)


@runtime_checkable
class ArmSession(Protocol):
    async def execute(self, request: ByteRequest) -> StudyTerminal:
        ...

    async def aclose(self) -> None:
        ...


@runtime_checkable
class ResourceObservedSession(ArmSession, Protocol):
    """Additive session capability for resource-policy campaigns."""

    def resource_snapshot(self, *, worker_drained: bool) -> object:
        ...


def validate_request_timing(timing: RequestTiming) -> None:
    """Fail closed when markers/version/durations cannot support comparison."""
    if timing.timing_contract != TIMING_CONTRACT_V1:
        raise TimingValidationError(
            f"wrong timing_contract version: {timing.timing_contract!r}"
        )
    elapsed = timing.elapsed_s
    if not math.isfinite(elapsed) or elapsed <= 0.0:
        raise TimingValidationError(
            f"elapsed_s must be finite and positive; got {elapsed!r}"
        )
    if not math.isfinite(timing.request_start) or not math.isfinite(
        timing.terminal_result_ready
    ):
        raise TimingValidationError("timing markers must be finite")
    if timing.terminal_result_ready < timing.request_start:
        raise TimingValidationError("terminal_result_ready precedes request_start")
    expected = timing.terminal_result_ready - timing.request_start
    if not math.isfinite(expected) or abs(expected - elapsed) > 1e-9:
        raise TimingValidationError("elapsed_s does not match outer markers")

    markers = timing.phase_markers
    if len(markers) != len(REQUIRED_PHASES):
        raise TimingValidationError(
            f"expected phases {REQUIRED_PHASES}; got {[m.phase for m in markers]}"
        )
    for required, marker in zip(REQUIRED_PHASES, markers, strict=True):
        if marker.phase != required:
            raise TimingValidationError(
                f"phase order invalid: expected {required}, got {marker.phase}"
            )
        if not math.isfinite(marker.started_at) or not math.isfinite(marker.ended_at):
            raise TimingValidationError("phase marker times must be finite")
        duration = marker.ended_at - marker.started_at
        if not math.isfinite(duration) or duration < 0.0:
            raise TimingValidationError(f"invalid duration for phase {marker.phase}")
        if marker.started_at < timing.request_start - 1e-9:
            raise TimingValidationError(f"phase {marker.phase} starts before request_start")
        if marker.ended_at > timing.terminal_result_ready + 1e-9:
            raise TimingValidationError(
                f"phase {marker.phase} ends after terminal_result_ready"
            )
    for left, right in itertools.pairwise(markers):
        if right.started_at + 1e-9 < left.ended_at:
            raise TimingValidationError("phase markers overlap out of order")


async def measure_request(
    session: ArmSession,
    request: ByteRequest,
    *,
    clock: Callable[[], float] | None = None,
    deadline_s: float,
) -> StudyTerminal:
    """Own outer request_start / terminal_result_ready; session create/teardown outside."""
    if deadline_s <= 0.0 or not math.isfinite(deadline_s):
        raise TimingValidationError("deadline_s must be finite and positive")
    tick = clock if clock is not None else time.perf_counter
    request_start = float(tick())
    terminal = await session.execute(request)
    terminal_result_ready = float(tick())
    elapsed_s = terminal_result_ready - request_start
    phase_markers: tuple[PhaseMarker, ...] = ()
    residual: tuple[str, ...] = ()
    if terminal.timing is not None:
        phase_markers = terminal.timing.phase_markers
        residual = terminal.timing.residual_overhead_notes
    timing = RequestTiming(
        timing_contract=TIMING_CONTRACT_V1,
        request_start=request_start,
        terminal_result_ready=terminal_result_ready,
        elapsed_s=elapsed_s,
        phase_markers=phase_markers,
        residual_overhead_notes=residual,
    )
    updated = terminal.model_copy(update={"timing": timing})
    if elapsed_s > deadline_s:
        # Task 5 owns cancel/teardown policy; still surface an invalid comparison timing.
        validate_request_timing(timing)  # may still pass structurally
        raise TimingValidationError(
            f"deadline exceeded: elapsed_s={elapsed_s} deadline_s={deadline_s}"
        )
    return updated


def apply_phase_advance(
    clock: Callable[[], float],
    phase: PhaseName,
    advances: dict[str, float] | None,
) -> None:
    """Advance a ControlledClock when study hooks inject phase delays."""
    if not advances:
        return
    delta = float(advances.get(phase, 0.0))
    if delta == 0.0:
        return
    advance = getattr(clock, "advance", None)
    if not callable(advance):
        raise TimingValidationError(
            "phase_advances require a ControlledClock with advance()"
        )
    advance(delta)
