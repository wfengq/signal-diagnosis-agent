"""T-CX292: shared encoded_bytes_to_terminal_v1 timing for both study arms."""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest

from signal_diag.agent.models import DiagnosisClaim, TaskAssessment
from signal_diag.evaluation.planner_ablation.models import StudyContextGuidanceView
from signal_diag.evaluation.planner_ablation.v2.models import (
    TIMING_CONTRACT_V1,
    ByteRequest,
    ExecutionProvenance,
    FailureCause,
    PhaseMarker,
    RequestTiming,
    StudyTerminal,
)
from signal_diag.evaluation.planner_ablation.v2.timing import (
    ArmSession,
    ControlledClock,
    TimingValidationError,
    measure_request,
    validate_request_timing,
)

_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_GUIDANCE = StudyContextGuidanceView(
    reason_codes=("insufficient_evidence_for_supported_fault",),
    unlockable_modes=("paired_reference", "nominal_single_tone"),
    required_inputs={
        "paired_reference": ("reference_wav",),
        "nominal_single_tone": ("nominal_fundamental_hz", "stimulus_kind=single_tone"),
    },
    summary="insufficient evidence",
)


def _wav_stub() -> bytes:
    return b"RIFF____WAVEfmt "


def _byte_request() -> ByteRequest:
    return ByteRequest(
        mode="single_signal",
        test_wav_bytes=_wav_stub(),
        question="Diagnose supported S1 distortion conservatively.",
    )


def _provenance(*, arm_planner: str = "ScriptedPlanner") -> ExecutionProvenance:
    return ExecutionProvenance(
        planner_class=arm_planner,
        execution_identity="harness_only",
        provider_client_bound=False,
        offline_session=True,
    )


class _PhaseAdvancingSession:
    """Study double that advances the shared clock during each required phase."""

    def __init__(
        self,
        *,
        arm: str,
        clock: ControlledClock,
        advances: dict[str, float],
        terminal_factory: Callable[[], StudyTerminal],
    ) -> None:
        self._arm = arm
        self._clock = clock
        self._advances = advances
        self._terminal_factory = terminal_factory
        self.closed = False

    async def execute(self, request: ByteRequest) -> StudyTerminal:
        del request
        markers: list[PhaseMarker] = []
        for phase in ("decode", "execution", "guidance"):
            started = self._clock()
            self._clock.advance(self._advances[phase])
            ended = self._clock()
            markers.append(
                PhaseMarker(phase=phase, started_at=started, ended_at=ended)  # type: ignore[arg-type]
            )
        terminal = self._terminal_factory()
        return terminal.model_copy(
            update={
                "arm": self._arm,
                "timing": RequestTiming(
                    timing_contract=TIMING_CONTRACT_V1,
                    request_start=0.0,
                    terminal_result_ready=0.0,
                    elapsed_s=0.0,
                    phase_markers=tuple(markers),
                ),
            }
        )

    async def aclose(self) -> None:
        self.closed = True


def _success_terminal() -> StudyTerminal:
    return StudyTerminal(
        run_id="run_success",
        arm="product_agent",
        mode="single_signal",
        status="completed",
        outcome="no_supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clean",
                fault_type="no_supported_fault",
                statement="No supported fault.",
            ),
        ),
        task_assessment=_ASSESSMENT,
        provenance=_provenance(),
    )


def _inconclusive_terminal() -> StudyTerminal:
    return StudyTerminal(
        run_id="run_inconclusive",
        arm="fixed_pipeline",
        mode="single_signal",
        status="completed",
        outcome="inconclusive",
        claims=(),
        task_assessment=_ASSESSMENT,
        guidance=_GUIDANCE,
        limitations=("scripted inconclusive",),
        provenance=_provenance(arm_planner="PlannerAblationFixedPipelineBaseline"),
    )


def _diagnosis_less_failure() -> StudyTerminal:
    return StudyTerminal(
        run_id="run_failed",
        arm="product_agent",
        mode="single_signal",
        status="failed",
        failure_cause=FailureCause(kind="behavioral", detail="diagnosis missing"),
        outcome=None,
        claims=(),
        task_assessment=_ASSESSMENT,
        provenance=_provenance(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arm", "factory"),
    [
        ("product_agent", _success_terminal),
        ("fixed_pipeline", _success_terminal),
        ("product_agent", _inconclusive_terminal),
        ("fixed_pipeline", _inconclusive_terminal),
        ("product_agent", _diagnosis_less_failure),
        ("fixed_pipeline", _diagnosis_less_failure),
    ],
)
async def test_t_cx292_controlled_clock_includes_all_phases(
    arm: str,
    factory: Callable[[], StudyTerminal],
) -> None:
    clock = ControlledClock(start=50.0)
    session: ArmSession = _PhaseAdvancingSession(
        arm=arm,
        clock=clock,
        advances={"decode": 1.0, "execution": 2.0, "guidance": 3.0},
        terminal_factory=factory,
    )
    measured = await measure_request(
        session,
        _byte_request(),
        clock=clock,
        deadline_s=120.0,
    )
    assert measured.timing is not None
    assert measured.timing.elapsed_s == pytest.approx(6.0)
    assert measured.timing.timing_contract == TIMING_CONTRACT_V1
    assert [m.phase for m in measured.timing.phase_markers] == [
        "decode",
        "execution",
        "guidance",
    ]
    validate_request_timing(measured.timing)

    clock.advance(10.0)
    assert measured.timing.elapsed_s == pytest.approx(6.0)
    await session.aclose()
    assert session.closed  # type: ignore[attr-defined]


def test_t_cx292_missing_markers_fail_validation() -> None:
    timing = RequestTiming(
        timing_contract=TIMING_CONTRACT_V1,
        request_start=0.0,
        terminal_result_ready=6.0,
        elapsed_s=6.0,
        phase_markers=(
            PhaseMarker(phase="decode", started_at=0.0, ended_at=1.0),
            PhaseMarker(phase="execution", started_at=1.0, ended_at=3.0),
        ),
    )
    with pytest.raises(TimingValidationError, match="phase"):
        validate_request_timing(timing)


def test_t_cx292_reversed_markers_fail_validation() -> None:
    timing = RequestTiming(
        timing_contract=TIMING_CONTRACT_V1,
        request_start=0.0,
        terminal_result_ready=6.0,
        elapsed_s=6.0,
        phase_markers=(
            PhaseMarker(phase="execution", started_at=0.0, ended_at=2.0),
            PhaseMarker(phase="decode", started_at=2.0, ended_at=3.0),
            PhaseMarker(phase="guidance", started_at=3.0, ended_at=6.0),
        ),
    )
    with pytest.raises(TimingValidationError, match="order|phase"):
        validate_request_timing(timing)


@pytest.mark.parametrize(
    "elapsed",
    [0.0, -1.0, float("nan"), float("inf")],
)
def test_t_cx292_nonpositive_or_nonfinite_elapsed_fails(elapsed: float) -> None:
    markers = (
        PhaseMarker(phase="decode", started_at=0.0, ended_at=0.1),
        PhaseMarker(phase="execution", started_at=0.1, ended_at=0.2),
        PhaseMarker(phase="guidance", started_at=0.2, ended_at=0.3),
    )
    timing = RequestTiming.model_construct(
        timing_contract=TIMING_CONTRACT_V1,
        request_start=0.0,
        terminal_result_ready=1.0 if math.isnan(elapsed) else elapsed,
        elapsed_s=elapsed,
        phase_markers=markers,
        residual_overhead_notes=(),
    )
    with pytest.raises(TimingValidationError):
        validate_request_timing(timing)


def test_t_cx292_wrong_timing_version_fails() -> None:
    timing = RequestTiming.model_construct(
        timing_contract="legacy_unmatched_v0",
        request_start=0.0,
        terminal_result_ready=6.0,
        elapsed_s=6.0,
        phase_markers=(
            PhaseMarker(phase="decode", started_at=0.0, ended_at=1.0),
            PhaseMarker(phase="execution", started_at=1.0, ended_at=3.0),
            PhaseMarker(phase="guidance", started_at=3.0, ended_at=6.0),
        ),
        residual_overhead_notes=(),
    )
    with pytest.raises(TimingValidationError, match="timing_contract|version"):
        validate_request_timing(timing)
