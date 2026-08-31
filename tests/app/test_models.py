"""Checkpoint W — frozen application DTOs and lifecycle (T239–T240)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from math import inf, nan

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import AgentRunResult
from signal_diag.app import (
    AcceptedEvaluationSummary,
    AppErrorCode,
    AppErrorDetail,
    AppErrorEnvelope,
    AppRunSnapshot,
    AppRunStatus,
    DemoPresetDescriptor,
    DemoPresetId,
    DiagnosisReport,
    PlannerIdentity,
    RunSubmission,
    SourceSummary,
    TraceEventView,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.app.errors import (
    AppCapacityError,
    ApplicationError,
    InvalidRequestError,
    PayloadTooLargeError,
    PlannerNotConfiguredError,
    ReportUnavailableError,
    RunNotFoundError,
    RunNotTerminalError,
    TraceIntegrityError,
    UnknownPresetError,
)
from signal_diag.evaluation.models import AggregateMetrics, RateMetric, TargetBands

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
STARTED = datetime(2026, 8, 31, 12, 1, tzinfo=UTC)
FINISHED = datetime(2026, 8, 31, 12, 2, tzinfo=UTC)
RUN_ID = "run_0123456789abcdef0123456789abcdef"
DIGEST = "a" * 64
SUMMARY_FILES = (
    "benchmark_manifest.json",
    "case_summary.csv",
    "metrics.json",
    "report.md",
    "runs.jsonl",
)
APP_ERROR_CODES: tuple[AppErrorCode, ...] = (
    "invalid_request",
    "payload_too_large",
    "unsupported_wav",
    "invalid_wav",
    "signal_limit_exceeded",
    "unknown_preset",
    "run_not_found",
    "run_not_terminal",
    "report_unavailable",
    "capacity_exceeded",
    "planner_not_configured",
    "provider_error",
    "runtime_error",
    "trace_integrity_error",
    "internal_error",
)
TYPED_ERRORS: tuple[tuple[type[ApplicationError], AppErrorCode], ...] = (
    (InvalidRequestError, "invalid_request"),
    (PayloadTooLargeError, "payload_too_large"),
    (UnknownPresetError, "unknown_preset"),
    (RunNotFoundError, "run_not_found"),
    (RunNotTerminalError, "run_not_terminal"),
    (ReportUnavailableError, "report_unavailable"),
    (AppCapacityError, "capacity_exceeded"),
    (PlannerNotConfiguredError, "planner_not_configured"),
    (TraceIntegrityError, "trace_integrity_error"),
)
ZERO_RATE = RateMetric(numerator=0, denominator=0, value=0.0)
EAST8 = timezone(timedelta(hours=8))


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


def _synthetic_source() -> SourceSummary:
    return SourceSummary(
        source_kind="synthetic",
        display_name="clipping",
        sample_rate_hz=48_000,
        channels=1,
        num_frames=48_000,
        duration_s=1.0,
        preset_id="clipping",
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


def _agent_result() -> AgentRunResult:
    return AgentRunResult(
        run_id="run_agent",
        status="success",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="planner_finished",
    )


def _trace() -> TraceEventView:
    return TraceEventView(
        event_index=0,
        kind="planner",
        action_name="finish",
        status="decision",
    )


def _app_error(*, code: AppErrorCode = "runtime_error") -> AppErrorDetail:
    return AppErrorDetail(code=code, message="application failed")


def _checksums(**overrides: str) -> dict[str, str]:
    values = {name: DIGEST for name in SUMMARY_FILES}
    values.update(overrides)
    return values


def _metrics() -> AggregateMetrics:
    return AggregateMetrics(
        run_count=0,
        causal_exact_set_accuracy=ZERO_RATE,
        causal_macro_f1=0.0,
        outcome_accuracy=ZERO_RATE,
        evidence_grounding_rate=ZERO_RATE,
        unsupported_claim_rate=ZERO_RATE,
        first_tool_selection_rate=ZERO_RATE,
        observation_driven_replan_rate=ZERO_RATE,
        unnecessary_tool_action_rate=ZERO_RATE,
        timely_stopping_rate=ZERO_RATE,
        applicable_rule_usage_rate=ZERO_RATE,
        required_knowledge_usage_rate=ZERO_RATE,
        unnecessary_knowledge_retrieval_rate=ZERO_RATE,
        knowledge_citation_utilization_rate=ZERO_RATE,
        average_tool_actions=0.0,
        provider_usage_coverage_rate=ZERO_RATE,
    )


def _snapshot(**overrides: object) -> AppRunSnapshot:
    payload: dict[str, object] = {
        "run_id": RUN_ID,
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


def _report(**overrides: object) -> DiagnosisReport:
    payload: dict[str, object] = {
        "generated_at": NOW,
        "run_id": RUN_ID,
        "source": _wav_source(),
        "analyzed_channel": "mixdown",
        "user_request": "Why does this signal sound distorted?",
        "planner_identity": _planner(),
        "waveform_preview": _preview(),
        "trace_events": (),
        "result": _agent_result(),
    }
    payload.update(overrides)
    return DiagnosisReport.model_validate(payload)


def _summary(**overrides: object) -> AcceptedEvaluationSummary:
    payload: dict[str, object] = {
        "source_bundle_relative_path": "docs/reports/phase4_3_1_official",
        "source_checksums_sha256": _checksums(),
        "benchmark_id": "bench_phase4_3_1",
        "dataset_id": "s1-distortion-synthetic",
        "dataset_version": "1.2.0",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "prompt_version": "v0.2-s1-planner-8.1",
        "prompt_sha256": DIGEST,
        "rule_profile_id": "profile_s1_distortion",
        "rule_profile_version": "1.0.0-demo",
        "scoring_version": "1.0.0",
        "targets": TargetBands(),
        "agent_metrics": _metrics(),
        "baseline_metrics": _metrics(),
    }
    payload.update(overrides)
    return AcceptedEvaluationSummary.model_validate(payload)


def test_t239_source_discriminator_and_run_id() -> None:
    wav = SourceSummary(
        source_kind="wav",
        display_name="input.wav",
        sample_rate_hz=48_000,
        channels=2,
        num_frames=48_000,
        duration_s=1.0,
        bits_per_sample=16,
    )
    assert wav.preset_id is None
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**wav.model_dump(), "preset_id": "clipping"})
    with pytest.raises(ValidationError):
        RunSubmission(run_id="run_clipping", status="queued")


def test_t239_synthetic_forbids_bits_and_requires_preset() -> None:
    synthetic = _synthetic_source()
    assert synthetic.bits_per_sample is None
    assert synthetic.preset_id == "clipping"
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**synthetic.model_dump(), "bits_per_sample": 16})
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**synthetic.model_dump(), "preset_id": None})
    with pytest.raises(ValidationError):
        SourceSummary(
            source_kind="wav",
            display_name="input.wav",
            sample_rate_hz=48_000,
            channels=2,
            num_frames=48_000,
            duration_s=1.0,
        )


@pytest.mark.parametrize(
    "run_id",
    [
        "run_clipping",
        "run_",
        "RUN_0123456789abcdef0123456789abcdef",
        "0123456789abcdef0123456789abcdef",
        "run_0123456789abcdef0123456789abcde",
        "run_0123456789abcdef0123456789abcdef0",
        "run_0123456789ABCDEF0123456789abcdef",
    ],
)
def test_t239_run_submission_rejects_non_opaque_ids(run_id: str) -> None:
    with pytest.raises(ValidationError):
        RunSubmission(run_id=run_id)


def test_t239_run_submission_accepts_opaque_queued_id() -> None:
    submission = RunSubmission(run_id=RUN_ID)
    assert submission.status == "queued"
    with pytest.raises(ValidationError):
        RunSubmission.model_validate({"run_id": RUN_ID, "status": "running"})


def test_t239_models_are_immutable() -> None:
    wav = _wav_source()
    preview = _preview()
    planner = _planner()
    snapshot = _snapshot()
    report = _report()
    summary = _summary()
    with pytest.raises(ValidationError):
        wav.display_name = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        preview.label = "analysis"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        planner.provider = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        snapshot.status = "running"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        report.status = "failed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        summary.agent_slot_count = 79  # type: ignore[misc]


@pytest.mark.parametrize("bad", [nan, inf, -inf])
def test_t239_finite_numeric_fields_reject_nan_inf(bad: float) -> None:
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**_wav_source().model_dump(), "duration_s": bad})
    with pytest.raises(ValidationError):
        WaveformPoint(sample_index=0, time_s=0.0, amplitude=bad)
    with pytest.raises(ValidationError):
        DemoPresetDescriptor(
            preset_id="clipping",
            label="Clipping",
            description="clipped sine",
            sample_rate_hz=48_000,
            duration_s=bad,
        )
    with pytest.raises(ValidationError):
        TraceEventView(
            event_index=0,
            kind="planner",
            action_name="finish",
            status="decision",
            latency_ms=bad,
        )


def test_t239_preview_and_preset_literals() -> None:
    preview = _preview()
    assert preview.label == "visualization_only"
    descriptor = DemoPresetDescriptor(
        preset_id="clean_periodic",
        label="Clean",
        description="clean sine",
        sample_rate_hz=48_000,
        duration_s=1.0,
    )
    assert descriptor.channels == 1
    assert descriptor.preset_id in (
        "clean_periodic",
        "clipping",
        "harmonic_distortion",
        "combined_distortion",
        "noise_inconclusive",
    )
    with pytest.raises(ValidationError):
        WaveformPreview.model_validate({**preview.model_dump(), "label": "evidence"})
    with pytest.raises(ValidationError):
        DemoPresetDescriptor(
            preset_id="run_clipping",  # type: ignore[arg-type]
            label="Bad",
            description="not a catalog id",
            sample_rate_hz=48_000,
            duration_s=1.0,
        )


def test_t239_error_codes_and_envelope() -> None:
    assert len(APP_ERROR_CODES) == 15
    assert APP_ERROR_CODES == AppErrorCode.__args__
    for code in APP_ERROR_CODES:
        detail = AppErrorDetail(code=code, message="safe")
        envelope = AppErrorEnvelope(error=detail)
        assert envelope.error.code == code
    with pytest.raises(ValidationError):
        AppErrorDetail(code="http_error", message="no")  # type: ignore[arg-type]


def test_t239_non_utc_and_naive_datetimes_rejected() -> None:
    naive = datetime(2026, 8, 31, 12, 0)  # noqa: DTZ001
    offset = datetime(2026, 8, 31, 12, 0, tzinfo=EAST8)
    with pytest.raises(ValidationError):
        _snapshot(created_at=naive)
    with pytest.raises(ValidationError):
        _snapshot(created_at=offset)
    with pytest.raises(ValidationError):
        _snapshot(status="running", started_at=naive)
    with pytest.raises(ValidationError):
        _snapshot(
            status="completed",
            started_at=STARTED,
            finished_at=offset,
            result=_agent_result(),
        )
    with pytest.raises(ValidationError):
        _report(generated_at=naive)
    with pytest.raises(ValidationError):
        _report(generated_at=offset)


def test_t239_diagnosis_report_requires_completed_and_utc() -> None:
    report = _report()
    assert report.status == "completed"
    assert report.generated_at.utcoffset() == timedelta(0)
    with pytest.raises(ValidationError):
        _report(status="failed")
    with pytest.raises(ValidationError):
        _report(status="queued")


def test_t239_accepted_evaluation_summary_checksums_and_frozen_counts() -> None:
    summary = _summary()
    assert summary.agent_slot_count == 80
    assert summary.behavioral_failure_slot_count == 2
    assert summary.outcome_error_slot_count == 1
    assert summary.benchmark_status == "completed"
    assert summary.target_status == "meets_target"
    assert summary.disclaimer == "demonstration_targets_not_standards_or_slas"
    assert list(summary.source_checksums_sha256) == sorted(SUMMARY_FILES)
    missing = _checksums()
    del missing["report.md"]
    with pytest.raises(ValidationError):
        _summary(source_checksums_sha256=missing)
    extra = _checksums()
    extra["extra.json"] = DIGEST
    with pytest.raises(ValidationError):
        _summary(source_checksums_sha256=extra)
    with pytest.raises(ValidationError):
        _summary(source_checksums_sha256=_checksums(report_md_wrong="no"))
    with pytest.raises(ValidationError):
        _summary(source_checksums_sha256=_checksums(**{"report.md": "A" * 64}))
    with pytest.raises(ValidationError):
        _summary(prompt_sha256="A" * 64)
    with pytest.raises(ValidationError):
        _summary(agent_slot_count=79)
    with pytest.raises(ValidationError):
        _summary(behavioral_failure_slot_count=1)
    with pytest.raises(ValidationError):
        _summary(outcome_error_slot_count=0)
    with pytest.raises(ValidationError):
        _summary(disclaimer="industry_standard")


@pytest.mark.parametrize(("exc_cls", "code"), TYPED_ERRORS)
def test_t239_typed_errors_expose_frozen_codes(
    exc_cls: type[ApplicationError],
    code: AppErrorCode,
) -> None:
    error = exc_cls(AppErrorDetail(code=code, message="api_key=secret leaked"))
    assert error.detail.code == code
    assert "secret" not in error.detail.message
    assert "secret" not in str(error)
    assert "[redacted]" in error.detail.message
    assert not hasattr(error, "status_code")
    assert not hasattr(error, "http_status")


def test_t239_application_error_sanitizes_secret_in_detail_message() -> None:
    error = ApplicationError(
        AppErrorDetail(code="internal_error", message="api_key=secret leaked")
    )
    assert "secret" not in error.detail.message
    assert "secret" not in str(error)
    assert "[redacted]" in error.detail.message


def test_t239_typed_error_rejects_mismatched_detail_code() -> None:
    with pytest.raises((TypeError, ValueError)):
        AppCapacityError(AppErrorDetail(code="invalid_request", message="x"))


def test_t239_generic_application_error_keeps_remaining_codes() -> None:
    for code in (
        "unsupported_wav",
        "invalid_wav",
        "signal_limit_exceeded",
        "provider_error",
        "runtime_error",
        "internal_error",
    ):
        error = ApplicationError(AppErrorDetail(code=code, message="safe"))
        assert error.detail.code == code


def test_t239_field_bounds() -> None:
    with pytest.raises(ValidationError):
        _snapshot(user_request="")
    with pytest.raises(ValidationError):
        _snapshot(user_request="x" * 2001)
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**_wav_source().model_dump(), "display_name": ""})
    with pytest.raises(ValidationError):
        SourceSummary.model_validate(
            {**_wav_source().model_dump(), "display_name": "x" * 256}
        )
    overflow_points = tuple(
        WaveformPoint(sample_index=index, time_s=0.0, amplitude=0.0)
        for index in range(1001)
    )
    with pytest.raises(ValidationError):
        WaveformPreview.model_validate(
            {**_preview().model_dump(), "points": overflow_points}
        )
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**_wav_source().model_dump(), "sample_rate_hz": 0})
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**_wav_source().model_dump(), "duration_s": 0})
    with pytest.raises(ValidationError):
        SourceSummary.model_validate({**_wav_source().model_dump(), "num_frames": 0})
    with pytest.raises(ValidationError):
        TraceEventView(
            event_index=-1,
            kind="planner",
            action_name="finish",
            status="decision",
        )
    with pytest.raises(ValidationError):
        TraceEventView(
            event_index=0,
            kind="planner",
            action_name="finish",
            status="decision",
            latency_ms=-0.1,
        )
    with pytest.raises(ValidationError):
        DemoPresetDescriptor(
            preset_id="clipping",
            label="",
            description="clipped sine",
            sample_rate_hz=48_000,
            duration_s=1.0,
        )
    with pytest.raises(ValidationError):
        DemoPresetDescriptor(
            preset_id="clipping",
            label="Clipping",
            description="",
            sample_rate_hz=48_000,
            duration_s=1.0,
        )


def test_t240_legal_queued_running_completed_failed_snapshots() -> None:
    queued = _snapshot()
    running = _snapshot(status="running", started_at=STARTED)
    completed = _snapshot(
        status="completed",
        started_at=STARTED,
        finished_at=FINISHED,
        result=_agent_result(),
        trace_events=(_trace(),),
    )
    failed = _snapshot(
        status="failed",
        started_at=STARTED,
        finished_at=FINISHED,
        application_error=_app_error(),
    )
    assert queued.status == "queued"
    assert queued.started_at is None
    assert queued.finished_at is None
    assert queued.result is None
    assert queued.application_error is None
    assert queued.trace_events == ()
    assert running.status == "running"
    assert running.started_at == STARTED
    assert running.finished_at is None
    assert running.result is None
    assert running.application_error is None
    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.application_error is None
    assert failed.status == "failed"
    assert failed.result is None
    assert failed.application_error is not None
    assert failed.trace_events == ()


def test_t240_rejects_illegal_timestamp_result_error_trace_combos() -> None:
    with pytest.raises(ValidationError):
        _snapshot(started_at=STARTED)
    with pytest.raises(ValidationError):
        _snapshot(status="running")
    with pytest.raises(ValidationError):
        _snapshot(
            status="completed",
            started_at=STARTED,
            finished_at=FINISHED,
        )
    with pytest.raises(ValidationError):
        _snapshot(
            status="completed",
            started_at=STARTED,
            finished_at=FINISHED,
            result=_agent_result(),
            application_error=_app_error(),
        )
    with pytest.raises(ValidationError):
        _snapshot(
            status="failed",
            started_at=STARTED,
            finished_at=FINISHED,
            result=_agent_result(),
            application_error=_app_error(),
        )
    with pytest.raises(ValidationError):
        _snapshot(
            status="failed",
            started_at=STARTED,
            finished_at=FINISHED,
        )
    with pytest.raises(ValidationError):
        _snapshot(trace_events=(_trace(),))
    with pytest.raises(ValidationError):
        _snapshot(status="running", started_at=STARTED, trace_events=(_trace(),))
    with pytest.raises(ValidationError):
        _snapshot(
            status="failed",
            started_at=STARTED,
            finished_at=FINISHED,
            application_error=_app_error(),
            trace_events=(_trace(),),
        )
    with pytest.raises(ValidationError):
        _snapshot(result=_agent_result())
    with pytest.raises(ValidationError):
        _snapshot(application_error=_app_error())
    with pytest.raises(ValidationError):
        _snapshot(status="running", started_at=STARTED, result=_agent_result())
    with pytest.raises(ValidationError):
        _snapshot(
            status="running",
            started_at=STARTED,
            application_error=_app_error(),
        )


def test_t240_rejects_illegal_timestamp_combos() -> None:
    with pytest.raises(ValidationError):
        _snapshot(finished_at=FINISHED)
    with pytest.raises(ValidationError):
        _snapshot(status="running", started_at=STARTED, finished_at=FINISHED)
    with pytest.raises(ValidationError):
        _snapshot(status="completed", finished_at=FINISHED, result=_agent_result())
    with pytest.raises(ValidationError):
        _snapshot(status="completed", started_at=STARTED, result=_agent_result())
    with pytest.raises(ValidationError):
        _snapshot(
            status="failed",
            finished_at=FINISHED,
            application_error=_app_error(),
        )
    with pytest.raises(ValidationError):
        _snapshot(
            status="failed",
            started_at=STARTED,
            application_error=_app_error(),
        )
    with pytest.raises(ValidationError):
        _snapshot(
            status="completed",
            created_at=FINISHED,
            started_at=STARTED,
            finished_at=NOW,
            result=_agent_result(),
        )
    with pytest.raises(ValidationError):
        _snapshot(
            status="completed",
            created_at=FINISHED,
            started_at=FINISHED,
            finished_at=NOW,
            result=_agent_result(),
        )


def test_t240_rejects_non_monotonic_timestamps() -> None:
    with pytest.raises(ValidationError):
        _snapshot(status="running", started_at=NOW - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        _snapshot(
            status="completed",
            started_at=FINISHED,
            finished_at=STARTED,
            result=_agent_result(),
        )


def test_t239_public_aliases_are_exported() -> None:
    assert "queued" in AppRunStatus.__args__
    assert DemoPresetId.__args__ == (
        "clean_periodic",
        "clipping",
        "harmonic_distortion",
        "combined_distortion",
        "noise_inconclusive",
    )
