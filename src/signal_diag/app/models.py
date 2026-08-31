"""Frozen Phase 5 application DTOs."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from signal_diag.agent.models import AgentRunResult
from signal_diag.evaluation.models import AggregateMetrics, ProviderUsage, TargetBands
from signal_diag.signal.models import ChannelMode

DemoPresetId = Literal[
    "clean_periodic",
    "clipping",
    "harmonic_distortion",
    "combined_distortion",
    "noise_inconclusive",
]

AppRunStatus = Literal["queued", "running", "completed", "failed"]

AppErrorCode = Literal[
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
]

_RUN_ID_PATTERN = r"^run_[0-9a-f]{32}$"
_SUMMARY_FILES = frozenset(
    {
        "benchmark_manifest.json",
        "case_summary.csv",
        "metrics.json",
        "report.md",
        "runs.jsonl",
    }
)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


class DemoPresetDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    preset_id: DemoPresetId
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    sample_rate_hz: int = Field(gt=0)
    duration_s: float = Field(gt=0.0)
    channels: Literal[1] = 1


class WaveformPoint(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    sample_index: int = Field(ge=0)
    time_s: float = Field(ge=0.0)
    amplitude: float


class WaveformPreview(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    label: Literal["visualization_only"] = "visualization_only"
    sample_rate_hz: int = Field(gt=0)
    original_num_samples: int = Field(gt=0)
    points: tuple[WaveformPoint, ...] = Field(max_length=1_000)


class AppErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    code: AppErrorCode
    message: str = Field(min_length=1)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class AppErrorEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    error: AppErrorDetail


class SourceSummary(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    source_kind: Literal["wav", "synthetic"]
    display_name: str = Field(min_length=1, max_length=255)
    sample_rate_hz: int = Field(gt=0)
    channels: Literal[1, 2]
    num_frames: int = Field(gt=0)
    duration_s: float = Field(gt=0.0)
    bits_per_sample: Literal[8, 16, 24, 32] | None = None
    preset_id: DemoPresetId | None = None

    @model_validator(mode="after")
    def validate_source(self) -> SourceSummary:
        if self.source_kind == "wav":
            if self.bits_per_sample is None or self.preset_id is not None:
                raise ValueError("wav source requires bits and forbids preset")
        elif self.preset_id is None or self.bits_per_sample is not None:
            raise ValueError("synthetic source requires preset and forbids bits")
        return self


class PlannerIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    phase4_certified_default: bool


class TraceEventView(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    event_index: int = Field(ge=0)
    kind: Literal["planner", "observation", "rule", "knowledge"]
    action_name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    purpose: str | None = None
    reference_ids: tuple[str, ...] = ()
    latency_ms: float | None = Field(default=None, ge=0.0)
    provider_usage: ProviderUsage | None = None


class RunSubmission(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    run_id: str = Field(pattern=_RUN_ID_PATTERN)
    status: Literal["queued"] = "queued"


class AppRunSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    run_id: str = Field(pattern=_RUN_ID_PATTERN)
    status: AppRunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    user_request: str = Field(min_length=1, max_length=2_000)
    analyzed_channel: ChannelMode
    source: SourceSummary
    planner_identity: PlannerIdentity
    waveform_preview: WaveformPreview
    trace_events: tuple[TraceEventView, ...] = ()
    result: AgentRunResult | None = None
    application_error: AppErrorDetail | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> AppRunSnapshot:
        _require_utc(self.created_at, "created_at")
        if self.started_at is not None:
            _require_utc(self.started_at, "started_at")
        if self.finished_at is not None:
            _require_utc(self.finished_at, "finished_at")
        if self.status == "queued":
            valid = (
                self.started_at is None
                and self.finished_at is None
                and self.result is None
                and self.application_error is None
            )
        elif self.status == "running":
            valid = (
                self.started_at is not None
                and self.finished_at is None
                and self.result is None
                and self.application_error is None
            )
        elif self.status == "completed":
            valid = (
                self.started_at is not None
                and self.finished_at is not None
                and self.result is not None
                and self.application_error is None
            )
        else:
            valid = (
                self.started_at is not None
                and self.finished_at is not None
                and self.result is None
                and self.application_error is not None
            )
        if not valid:
            raise ValueError("snapshot fields do not match lifecycle status")
        if self.status not in ("completed", "failed") and self.trace_events:
            raise ValueError("non-terminal snapshots forbid trace events")
        if self.status == "failed" and self.trace_events:
            raise ValueError("application-failed snapshots forbid trace events")
        if self.started_at is not None and self.created_at > self.started_at:
            raise ValueError("created_at must be <= started_at")
        if self.finished_at is not None:
            if self.started_at is not None and self.started_at > self.finished_at:
                raise ValueError("started_at must be <= finished_at")
            if self.created_at > self.finished_at:
                raise ValueError("created_at must be <= finished_at")
        return self


class DiagnosisReport(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    schema_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    run_id: str = Field(pattern=_RUN_ID_PATTERN)
    status: Literal["completed"] = "completed"
    source: SourceSummary
    analyzed_channel: ChannelMode
    user_request: str = Field(min_length=1, max_length=2_000)
    planner_identity: PlannerIdentity
    waveform_preview: WaveformPreview
    trace_events: tuple[TraceEventView, ...]
    result: AgentRunResult

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        _require_utc(value, "generated_at")
        return value


class AcceptedEvaluationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    schema_version: Literal["1.0.0"] = "1.0.0"
    source_bundle_relative_path: str = Field(min_length=1)
    source_checksums_sha256: dict[str, str]
    benchmark_id: str = Field(pattern=r"^bench_")
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_profile_id: str = Field(pattern=r"^profile_")
    rule_profile_version: str = Field(min_length=1)
    scoring_version: str = Field(min_length=1)
    benchmark_status: Literal["completed"] = "completed"
    target_status: Literal["meets_target"] = "meets_target"
    agent_slot_count: Literal[80] = 80
    behavioral_failure_slot_count: Literal[2] = 2
    outcome_error_slot_count: Literal[1] = 1
    targets: TargetBands
    agent_metrics: AggregateMetrics
    baseline_metrics: AggregateMetrics
    disclaimer: Literal["demonstration_targets_not_standards_or_slas"] = (
        "demonstration_targets_not_standards_or_slas"
    )

    @field_validator("source_checksums_sha256")
    @classmethod
    def validate_checksums(cls, value: dict[str, str]) -> dict[str, str]:
        if set(value) != _SUMMARY_FILES:
            raise ValueError("evaluation summary checksum keys are not canonical")
        if any(re.fullmatch(r"[0-9a-f]{64}", digest) is None for digest in value.values()):
            raise ValueError("evaluation summary checksums must be lowercase SHA-256")
        return dict(sorted(value.items()))
