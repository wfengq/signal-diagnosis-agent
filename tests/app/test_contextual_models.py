"""T-CX086–T-CX089: contextual application DTOs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import AgentRunResult
from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualDiagnosisReport,
    ContextualRunSubmission,
)
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
GENERATED = datetime(2026, 9, 4, 12, 3, tzinfo=UTC)
RUN_ID = "run_" + "a" * 32


def _source(name: str = "test.wav") -> SourceSummary:
    return SourceSummary(
        source_kind="wav",
        display_name=name,
        sample_rate_hz=8_000,
        channels=1,
        num_frames=3,
        duration_s=3 / 8_000,
        bits_per_sample=16,
    )


def _preview() -> WaveformPreview:
    return WaveformPreview(
        sample_rate_hz=8_000,
        original_num_samples=3,
        points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.5),),
    )


def _planner() -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="v0.3-s1-planner-9.5",
        phase4_certified_default=True,
    )


def _context(*, mode: str = "paired_reference") -> StimulusContext:
    if mode == "nominal_single_tone":
        return StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            assertion_source="user_supplied",
            stimulus_kind="single_tone",
            nominal_fundamental_hz=440.0,
        )
    return StimulusContext(
        mode="paired_reference",
        test_signal_id="sig_test",
        reference_signal_id="sig_ref",
        assertion_source="user_supplied",
    )


def _caps(**overrides: object) -> EffectiveCapabilities:
    return EffectiveCapabilities.model_validate(
        {
            "clipping": True,
            "absolute_harmonic_description": True,
            "nominal_harmonic_attribution": False,
            "paired_harmonic_attribution": True,
            **overrides,
        }
    )


def _result() -> AgentRunResult:
    return AgentRunResult(
        run_id="run_agent",
        status="success",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="planner_finished",
    )


def _queued(**overrides: object) -> ContextualAppRunSnapshot:
    payload: dict[str, object] = {
        "run_id": RUN_ID,
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


def test_t_cx086_submission_is_frozen_queued_only() -> None:
    submission = ContextualRunSubmission(run_id=RUN_ID)
    assert submission.status == "queued"
    with pytest.raises(ValidationError):
        ContextualRunSubmission(run_id="run_bad")
    with pytest.raises(ValidationError):
        submission.status = "running"  # type: ignore[misc]


def test_t_cx087_snapshot_lifecycle_matrix() -> None:
    queued = _queued()
    assert queued.status == "queued"
    assert queued.started_at is None
    assert queued.result is None

    running = _queued(status="running", started_at=STARTED)
    assert running.started_at == STARTED

    completed = _queued(
        status="completed",
        started_at=STARTED,
        finished_at=FINISHED,
        result=_result(),
        effective_capabilities=_caps(paired_harmonic_attribution=False),
    )
    assert completed.result is not None
    assert completed.application_error is None

    failed = _queued(
        status="failed",
        started_at=STARTED,
        finished_at=FINISHED,
        application_error=AppErrorDetail(code="provider_error", message="boom"),
    )
    assert failed.application_error is not None

    with pytest.raises(ValidationError):
        _queued(status="completed", started_at=STARTED, finished_at=FINISHED)
    with pytest.raises(ValidationError):
        _queued(status="failed", started_at=STARTED, finished_at=FINISHED, result=_result())


def test_t_cx088_snapshot_requires_context_and_capabilities() -> None:
    with pytest.raises(ValidationError):
        ContextualAppRunSnapshot.model_validate(
            {
                "run_id": RUN_ID,
                "status": "queued",
                "created_at": NOW,
                "user_request": "Why?",
                "analyzed_channel": "mixdown",
                "test_source": _source(),
                "reference_source": None,
                "test_preview": _preview(),
                "planner_identity": _planner(),
            }
        )
    snap = _queued(
        reference_source=None,
        stimulus_context=_context(mode="nominal_single_tone"),
        effective_capabilities=_caps(
            paired_harmonic_attribution=False,
            nominal_harmonic_attribution=True,
        ),
    )
    assert snap.stimulus_context.mode == "nominal_single_tone"
    assert snap.effective_capabilities.nominal_harmonic_attribution is True


def test_t_cx089_report_schema_version_and_disclosure_fields() -> None:
    report = ContextualDiagnosisReport(
        generated_at=GENERATED,
        run_id=RUN_ID,
        test_source=_source("test.wav"),
        reference_source=_source("ref.wav"),
        stimulus_context=_context(),
        effective_capabilities=_caps(),
        analyzed_channel="mixdown",
        user_request="Why does this signal sound distorted?",
        planner_identity=_planner(),
        test_preview=_preview(),
        trace_events=(),
        result=_result(),
    )
    assert report.schema_version == "1.0.0"
    assert report.status == "completed"
    assert report.reference_source is not None
    assert report.stimulus_context.mode == "paired_reference"
    with pytest.raises(ValidationError):
        report.schema_version = "2.0.0"  # type: ignore[misc]
