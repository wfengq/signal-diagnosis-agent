"""V0.3 contextual application DTOs (additive; does not mutate V0.2 models)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from signal_diag.agent.models import AgentRunResult
from signal_diag.app.context_guidance import (
    ContextGuidance,
    validate_observed_facts_against_evidence,
)
from signal_diag.app.models import (
    AppErrorDetail,
    AppRunStatus,
    PlannerIdentity,
    SourceSummary,
    TraceEventView,
    WaveformPreview,
)
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext
from signal_diag.signal.models import ChannelMode

_RUN_ID_PATTERN = r"^run_[0-9a-f]{32}$"


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


class ContextualRunSubmission(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(pattern=_RUN_ID_PATTERN)
    status: Literal["queued"] = "queued"


class ContextualAppRunSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    run_id: str = Field(pattern=_RUN_ID_PATTERN)
    status: AppRunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    user_request: str = Field(min_length=1, max_length=2_000)
    analyzed_channel: ChannelMode
    test_source: SourceSummary
    reference_source: SourceSummary | None
    stimulus_context: StimulusContext
    effective_capabilities: EffectiveCapabilities
    test_preview: WaveformPreview
    planner_identity: PlannerIdentity
    trace_events: tuple[TraceEventView, ...] = ()
    result: AgentRunResult | None = None
    application_error: AppErrorDetail | None = None
    context_guidance: ContextGuidance | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> ContextualAppRunSnapshot:
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


class ContextualDiagnosisReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    run_id: str = Field(pattern=_RUN_ID_PATTERN)
    status: Literal["completed"] = "completed"
    test_source: SourceSummary
    reference_source: SourceSummary | None
    stimulus_context: StimulusContext
    effective_capabilities: EffectiveCapabilities
    analyzed_channel: ChannelMode
    user_request: str = Field(min_length=1, max_length=2_000)
    planner_identity: PlannerIdentity
    test_preview: WaveformPreview
    trace_events: tuple[TraceEventView, ...]
    result: AgentRunResult
    context_guidance: ContextGuidance | None = None

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        _require_utc(value, "generated_at")
        return value

    @model_validator(mode="after")
    def validate_observed_facts(self) -> ContextualDiagnosisReport:
        if self.context_guidance is not None:
            validate_observed_facts_against_evidence(
                evidence=self.result.evidence,
                observed_facts=self.context_guidance.observed_facts,
            )
        return self
