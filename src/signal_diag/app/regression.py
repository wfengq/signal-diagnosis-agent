"""In-session regression troubleshooting workbench service (D042 Phase B)."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.app.errors import (
    AppCapacityError,
    InvalidRequestError,
    PayloadTooLargeError,
)
from signal_diag.app.models import AppErrorDetail
from signal_diag.rules.regression import (
    ComparisonConditions,
    ComparisonProfile,
    ComparisonRecord,
    compare_measurements,
)
from signal_diag.signal import (
    InvalidWavError,
    SignalLimitExceededError,
    UnsupportedWavError,
    load_wav_bytes,
)
from signal_diag.signal.models import TimeRange
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.segment import _resolve_sample_bounds
from signal_diag.signal.wav import WavLoadLimits
from signal_diag.tools.regression_measurement import (
    InputIdentity,
    MeasurementSelection,
    ToolParameterSnapshot,
    measure_output,
)

_MAX_GOAL_CHARS = 2_000
_MAX_REQUEST_ID_CHARS = 64
_MAX_ACTIVE_CASES = 8
_MAX_SUBMITS_PER_CASE = 16
_RetestKind = Literal["repeat", "repair", "recommendation"]
_SubmitStatus = Literal["idle", "completed", "failed", "busy"]
_RecommendationStatus = Literal["unavailable", "pending", "completed", "failed"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _invalid(message: str) -> InvalidRequestError:
    return InvalidRequestError(AppErrorDetail(code="invalid_request", message=message))


def _capacity(message: str) -> AppCapacityError:
    return AppCapacityError(AppErrorDetail(code="capacity_exceeded", message=message))


def _payload_too_large() -> PayloadTooLargeError:
    return PayloadTooLargeError(
        AppErrorDetail(code="payload_too_large", message="WAV upload exceeds 20 MiB")
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class ComparisonUpload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_data: bytes
    candidate_data: bytes
    baseline_filename: str = Field(min_length=1, max_length=256)
    candidate_filename: str = Field(min_length=1, max_length=256)
    baseline_version: str = Field(min_length=1, max_length=256)
    candidate_version: str = Field(min_length=1, max_length=256)
    conditions: ComparisonConditions
    selection: MeasurementSelection
    original_input_data: bytes | None = None
    original_input_filename: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_versions_match_conditions(self) -> ComparisonUpload:
        if self.baseline_version != self.conditions.baseline_version:
            raise ValueError("baseline_version must match conditions.baseline_version")
        if self.candidate_version != self.conditions.candidate_version:
            raise ValueError("candidate_version must match conditions.candidate_version")
        if self.original_input_data is not None and not self.original_input_filename:
            raise ValueError("original_input_filename is required when original_input_data is set")
        return self


class RetestLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: _RetestKind
    parent_comparison_id: str = Field(min_length=1)
    recommendation_id: str | None = None

    @model_validator(mode="after")
    def validate_recommendation_link(self) -> RetestLink:
        if self.kind == "recommendation" and not self.recommendation_id:
            raise ValueError("recommendation_id is required for recommendation links")
        if self.kind != "recommendation" and self.recommendation_id is not None:
            raise ValueError("recommendation_id is only valid for recommendation links")
        return self


class CaseComparisonItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_id: str
    record: ComparisonRecord
    parent_comparison_id: str | None = None
    link_kind: _RetestKind | None = None
    request_id: str
    created_at: datetime


class CaseFailureRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    failure_id: str
    request_id: str
    message: str
    parent_comparison_id: str | None = None
    link_kind: _RetestKind | None = None
    created_at: datetime


class CaseRecommendationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    comparison_id: str
    status: _RecommendationStatus
    detail: str | None = None
    created_at: datetime


class RegressionCaseSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    revision: int
    goal: str
    comparisons: tuple[CaseComparisonItem, ...]
    failures: tuple[CaseFailureRecord, ...]
    recommendations: tuple[CaseRecommendationRecord, ...]
    latest_submit_status: _SubmitStatus
    created_at: datetime
    updated_at: datetime


@dataclass
class _RequestOutcome:
    kind: Literal["completed", "failed"]
    content_fingerprint: str
    comparison: CaseComparisonItem | None = None
    failure: CaseFailureRecord | None = None


@dataclass
class _CaseState:
    case_id: str
    goal: str
    created_at: datetime
    updated_at: datetime
    revision: int = 0
    comparisons: list[CaseComparisonItem] = field(default_factory=list)
    failures: list[CaseFailureRecord] = field(default_factory=list)
    recommendations: list[CaseRecommendationRecord] = field(default_factory=list)
    request_outcomes: dict[str, _RequestOutcome] = field(default_factory=dict)
    accepted_submit_count: int = 0
    latest_submit_status: _SubmitStatus = "idle"
    running: bool = False


def _upload_fingerprint(
    upload: ComparisonUpload,
    link: RetestLink | None = None,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(upload.baseline_data)
    hasher.update(b"\0")
    hasher.update(upload.candidate_data)
    hasher.update(b"\0")
    if upload.original_input_data is not None:
        hasher.update(upload.original_input_data)
    hasher.update(b"\0")
    hasher.update(
        upload.model_dump_json(
            exclude={"baseline_data", "candidate_data", "original_input_data"}
        ).encode("utf-8")
    )
    hasher.update(b"\0")
    if link is None:
        hasher.update(b"link:none")
    else:
        hasher.update(link.model_dump_json().encode("utf-8"))
    return hasher.hexdigest()


def _check_file_sizes(upload: ComparisonUpload, *, max_file_bytes: int) -> None:
    for payload in (upload.baseline_data, upload.candidate_data, upload.original_input_data):
        if payload is not None and len(payload) > max_file_bytes:
            raise _payload_too_large()


def _build_identity(
    *,
    run_id: str,
    side: Literal["baseline", "candidate"],
    wav_sha256: str,
    signal_id: str,
    repository: InMemorySignalRepository,
    selection: MeasurementSelection,
) -> InputIdentity:
    record = repository.get(signal_id)
    time_range = selection.clipping.time_range or TimeRange()
    resolved_start, resolved_end = _resolve_sample_bounds(record, time_range)
    snapshot = ToolParameterSnapshot(
        clipping=selection.clipping,
        harmonic=selection.harmonic,
    )
    return InputIdentity(
        run_id=run_id,
        side=side,
        wav_sha256=wav_sha256,
        signal_id=signal_id,
        sample_rate_hz=record.meta.sample_rate_hz,
        source_channels=record.meta.channels,
        total_frames=record.meta.num_samples,
        resolved_start_sample=resolved_start,
        resolved_end_sample=resolved_end,
        channel=selection.clipping.channel,
        tool_parameter_snapshot=snapshot,
    )


def _execute_comparison_group(
    upload: ComparisonUpload,
    *,
    profile: ComparisonProfile | None,
    max_file_bytes: int,
) -> ComparisonRecord:
    """Decode, measure both sides, and compare. Sync so tests can wrap it."""
    _check_file_sizes(upload, max_file_bytes=max_file_bytes)
    repository = InMemorySignalRepository()
    try:
        try:
            baseline_loaded = load_wav_bytes(
                upload.baseline_data,
                filename=upload.baseline_filename,
            )
            candidate_loaded = load_wav_bytes(
                upload.candidate_data,
                filename=upload.candidate_filename,
            )
        except SignalLimitExceededError as error:
            raise _payload_too_large() from error
        except (InvalidWavError, UnsupportedWavError) as error:
            raise _invalid(str(error) or "invalid WAV upload") from error

        if upload.original_input_data is not None:
            try:
                load_wav_bytes(
                    upload.original_input_data,
                    filename=upload.original_input_filename or "original.wav",
                )
            except SignalLimitExceededError as error:
                raise _payload_too_large() from error
            except (InvalidWavError, UnsupportedWavError) as error:
                raise _invalid(str(error) or "invalid original WAV upload") from error

        repository.put(baseline_loaded.record)
        repository.put(candidate_loaded.record)

        conditions = upload.conditions
        if upload.original_input_data is not None:
            digest = hashlib.sha256(upload.original_input_data).hexdigest()
            declared = conditions.original_input_sha256
            if declared is None:
                conditions = conditions.model_copy(
                    update={"original_input_sha256": digest}
                )
            elif declared != digest:
                raise _invalid(
                    "original_input_sha256 does not match uploaded original bytes"
                )

        baseline_identity = _build_identity(
            run_id=_new_id("run"),
            side="baseline",
            wav_sha256=hashlib.sha256(upload.baseline_data).hexdigest(),
            signal_id=baseline_loaded.record.meta.signal_id,
            repository=repository,
            selection=upload.selection,
        )
        candidate_identity = _build_identity(
            run_id=_new_id("run"),
            side="candidate",
            wav_sha256=hashlib.sha256(upload.candidate_data).hexdigest(),
            signal_id=candidate_loaded.record.meta.signal_id,
            repository=repository,
            selection=upload.selection,
        )
        baseline_bundle = measure_output(
            repository=repository,
            identity=baseline_identity,
            selection=upload.selection,
        )
        candidate_bundle = measure_output(
            repository=repository,
            identity=candidate_identity,
            selection=upload.selection,
        )
        return compare_measurements(
            baseline_bundle,
            candidate_bundle,
            conditions=conditions,
            profile=profile,
            comparison_id=_new_id("cmp"),
        )
    finally:
        for meta in list(repository.list_meta()):
            repository.remove(meta.signal_id)


class RegressionWorkbenchService:
    """Bounded in-memory case store for regression comparisons."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        comparison_profile: ComparisonProfile | None = None,
        wav_limits: WavLoadLimits | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._comparison_profile = comparison_profile
        self._wav_limits = wav_limits or WavLoadLimits()
        self._cases: dict[str, _CaseState] = {}
        self._lock = asyncio.Lock()
        self._busy = False
        self._inflight: set[asyncio.Task[object]] = set()
        self._closed = False

    def create_case(self, goal: str) -> RegressionCaseSnapshot:
        if self._closed:
            raise _invalid("regression service is closed")
        text = goal.strip()
        if not text:
            raise _invalid("goal must be a non-empty string")
        if len(text) > _MAX_GOAL_CHARS:
            raise _invalid("goal must be at most 2000 characters")
        if len(self._cases) >= _MAX_ACTIVE_CASES:
            raise _capacity("active cases limit exceeded")
        now = self._clock()
        case = _CaseState(
            case_id=_new_id("case"),
            goal=text,
            created_at=now,
            updated_at=now,
        )
        self._cases[case.case_id] = case
        return self._snapshot(case)

    def get_case(self, case_id: str) -> RegressionCaseSnapshot:
        case = self._require_case(case_id)
        return self._snapshot(case)

    def delete_case(self, case_id: str) -> None:
        case = self._require_case(case_id)
        if case.running:
            raise _invalid("case has a running comparison")
        del self._cases[case_id]

    async def submit_comparison(
        self,
        case_id: str,
        upload: ComparisonUpload,
        *,
        request_id: str,
        link: RetestLink | None = None,
    ) -> RegressionCaseSnapshot:
        if self._closed:
            raise _invalid("regression service is closed")
        self._validate_request_id(request_id)
        fingerprint = _upload_fingerprint(upload, link)

        slot_held = False
        async with self._lock:
            case = self._require_case(case_id)
            prior = case.request_outcomes.get(request_id)
            if prior is not None:
                if prior.content_fingerprint != fingerprint:
                    raise _invalid("request_id was reused with different content")
                case.latest_submit_status = prior.kind
                return self._snapshot(case)

            if case.accepted_submit_count >= _MAX_SUBMITS_PER_CASE:
                raise _capacity("case submits limit exceeded")

            if link is not None:
                self._validate_link(case, link)

            if self._busy or case.running:
                raise _invalid("regression service is busy")

            _check_file_sizes(upload, max_file_bytes=self._wav_limits.max_upload_bytes)

            case.running = True
            case.accepted_submit_count += 1
            self._busy = True
            slot_held = True

        try:
            try:
                outcome = await asyncio.to_thread(
                    _execute_comparison_group,
                    upload,
                    profile=self._comparison_profile,
                    max_file_bytes=self._wav_limits.max_upload_bytes,
                )
                if inspect.isawaitable(outcome):
                    record = await outcome
                else:
                    record = outcome
            except (InvalidRequestError, PayloadTooLargeError, AppCapacityError) as error:
                async with self._lock:
                    case = self._require_case(case_id)
                    failure = CaseFailureRecord(
                        failure_id=_new_id("fail"),
                        request_id=request_id,
                        message=error.detail.message,
                        parent_comparison_id=(
                            link.parent_comparison_id if link else None
                        ),
                        link_kind=link.kind if link else None,
                        created_at=self._clock(),
                    )
                    case.failures.append(failure)
                    case.request_outcomes[request_id] = _RequestOutcome(
                        kind="failed",
                        content_fingerprint=fingerprint,
                        failure=failure,
                    )
                    case.latest_submit_status = "failed"
                    case.revision += 1
                    case.updated_at = self._clock()
                raise error.__class__(error.detail) from error
            except Exception as error:
                async with self._lock:
                    case = self._require_case(case_id)
                    failure = CaseFailureRecord(
                        failure_id=_new_id("fail"),
                        request_id=request_id,
                        message="comparison execution failed",
                        parent_comparison_id=(
                            link.parent_comparison_id if link else None
                        ),
                        link_kind=link.kind if link else None,
                        created_at=self._clock(),
                    )
                    case.failures.append(failure)
                    case.request_outcomes[request_id] = _RequestOutcome(
                        kind="failed",
                        content_fingerprint=fingerprint,
                        failure=failure,
                    )
                    case.latest_submit_status = "failed"
                    case.revision += 1
                    case.updated_at = self._clock()
                raise _invalid("comparison execution failed") from error

            async with self._lock:
                case = self._require_case(case_id)
                item = CaseComparisonItem(
                    comparison_id=record.comparison_id,
                    record=record,
                    parent_comparison_id=link.parent_comparison_id if link else None,
                    link_kind=link.kind if link else None,
                    request_id=request_id,
                    created_at=self._clock(),
                )
                case.comparisons.append(item)
                recommendation = CaseRecommendationRecord(
                    recommendation_id=_new_id("rec"),
                    comparison_id=record.comparison_id,
                    status="unavailable",
                    detail=(
                        "retest recommendations are not enabled on this product path"
                    ),
                    created_at=self._clock(),
                )
                case.recommendations.append(recommendation)
                case.request_outcomes[request_id] = _RequestOutcome(
                    kind="completed",
                    content_fingerprint=fingerprint,
                    comparison=item,
                )
                case.latest_submit_status = "completed"
                case.revision += 1
                case.updated_at = self._clock()
                return self._snapshot(case)
        finally:
            if slot_held:
                async with self._lock:
                    case = self._cases.get(case_id)
                    if case is not None:
                        case.running = False
                    self._busy = False

    async def aclose(self) -> None:
        self._closed = True
        while True:
            async with self._lock:
                running = any(case.running for case in self._cases.values()) or self._busy
            if not running:
                break
            await asyncio.sleep(0.01)
        self._cases.clear()

    def _require_case(self, case_id: str) -> _CaseState:
        try:
            return self._cases[case_id]
        except KeyError as error:
            raise _invalid(f"unknown case_id: {case_id}") from error

    def _validate_request_id(self, request_id: str) -> None:
        text = request_id.strip()
        if not text or text != request_id:
            raise _invalid("request_id must be a non-empty trimmed string")
        if len(text) > _MAX_REQUEST_ID_CHARS:
            raise _invalid("request_id must be at most 64 characters")

    def _validate_link(self, case: _CaseState, link: RetestLink) -> None:
        parent = next(
            (
                item
                for item in case.comparisons
                if item.comparison_id == link.parent_comparison_id
            ),
            None,
        )
        if parent is None:
            raise _invalid("parent comparison does not exist in this case")
        if link.kind == "recommendation":
            recommendation = next(
                (
                    item
                    for item in case.recommendations
                    if item.recommendation_id == link.recommendation_id
                ),
                None,
            )
            if recommendation is None:
                raise _invalid("recommendation record does not exist for link")
            if recommendation.comparison_id != link.parent_comparison_id:
                raise _invalid("recommendation does not match parent comparison")

    def _snapshot(self, case: _CaseState) -> RegressionCaseSnapshot:
        return RegressionCaseSnapshot(
            case_id=case.case_id,
            revision=case.revision,
            goal=case.goal,
            comparisons=tuple(
                item.model_copy(deep=True) for item in case.comparisons
            ),
            failures=tuple(item.model_copy(deep=True) for item in case.failures),
            recommendations=tuple(
                item.model_copy(deep=True) for item in case.recommendations
            ),
            latest_submit_status=case.latest_submit_status,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )


def build_regression_service() -> RegressionWorkbenchService:
    """Product builder: descriptive-only comparisons, no fixture profiles."""
    return RegressionWorkbenchService(comparison_profile=None)
