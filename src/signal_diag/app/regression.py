"""In-session regression troubleshooting workbench service (D042 Phase B)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import inspect
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.agent.retest_planner import (
    RetestCallLimits,
    RetestPlanner,
    RetestPlannerError,
    build_retest_context,
    render_recommendation_detail,
    validate_selection_against_context,
)
from signal_diag.app.errors import (
    AppCapacityError,
    InvalidRequestError,
    PayloadTooLargeError,
)
from signal_diag.app.models import AppErrorDetail
from signal_diag.rules.full_scale_check import (
    FullScaleCheckRecord,
    FullScaleDeclarations,
    FullScaleMethodFloor,
    FullScaleSubmission,
    assert_product_profile_allowed,
    evaluate_full_scale_check,
    resolve_anchor_id,
)
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
from signal_diag.tools.regression_full_scale import (
    FullScaleFacts,
    measure_full_scale_facts,
)
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
    full_scale_declarations: FullScaleDeclarations = Field(
        default_factory=FullScaleDeclarations
    )

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

    case_id: str
    comparison_id: str
    record: ComparisonRecord
    parent_comparison_id: str | None = None
    link_kind: _RetestKind | None = None
    request_id: str
    created_at: datetime
    full_scale_declarations: FullScaleDeclarations = Field(
        default_factory=FullScaleDeclarations
    )
    baseline_full_scale: FullScaleFacts | None = None
    candidate_full_scale: FullScaleFacts | None = None


class CaseFailureRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    failure_id: str
    request_id: str
    message: str
    parent_comparison_id: str | None = None
    link_kind: _RetestKind | None = None
    created_at: datetime


class CaseRecommendationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
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
    full_scale_checks: tuple[FullScaleCheckRecord, ...] = ()
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
class _RecommendationOutcome:
    kind: Literal["completed", "failed", "unavailable"]
    content_fingerprint: str
    recommendation: CaseRecommendationRecord


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
    recommendation_outcomes: dict[str, _RecommendationOutcome] = field(
        default_factory=dict
    )
    accepted_submit_count: int = 0
    latest_submit_status: _SubmitStatus = "idle"
    running: bool = False
    full_scale_checks: list[FullScaleCheckRecord] = field(default_factory=list)


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


def _recommendation_fingerprint(
    *,
    case_id: str,
    comparison_id: str,
    comparison_digest: str,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(case_id.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(comparison_id.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(comparison_digest.encode("ascii"))
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


@dataclass(frozen=True, slots=True)
class _ComparisonGroupResult:
    record: ComparisonRecord
    baseline_facts: FullScaleFacts | None
    candidate_facts: FullScaleFacts | None


def submissions_from_items(
    items: tuple[CaseComparisonItem, ...] | list[CaseComparisonItem],
) -> dict[str, FullScaleSubmission]:
    """Map comparison items to full-scale submissions for anchor resolution."""
    return {
        item.comparison_id: FullScaleSubmission(
            comparison_id=item.comparison_id,
            parent_comparison_id=item.parent_comparison_id,
            link_kind=item.link_kind,
            record=item.record,
            declarations=item.full_scale_declarations,
            baseline_facts=item.baseline_full_scale,
            candidate_facts=item.candidate_full_scale,
        )
        for item in items
    }


def _execute_comparison_group(
    upload: ComparisonUpload,
    *,
    profile: ComparisonProfile | None,
    max_file_bytes: int,
) -> _ComparisonGroupResult:
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
        baseline_facts = measure_full_scale_facts(
            repository=repository,
            bundle=baseline_bundle,
            pcm_bit_depth=baseline_loaded.source_info.bits_per_sample,
        )
        candidate_facts = measure_full_scale_facts(
            repository=repository,
            bundle=candidate_bundle,
            pcm_bit_depth=candidate_loaded.source_info.bits_per_sample,
        )
        record = compare_measurements(
            baseline_bundle,
            candidate_bundle,
            conditions=conditions,
            profile=profile,
            comparison_id=_new_id("cmp"),
        )
        return _ComparisonGroupResult(
            record=record,
            baseline_facts=baseline_facts,
            candidate_facts=candidate_facts,
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
        retest_planner: RetestPlanner | None = None,
        retest_model: str | None = None,
        retest_limits: RetestCallLimits | None = None,
        full_scale_floor: FullScaleMethodFloor | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._comparison_profile = comparison_profile
        self._full_scale_floor = full_scale_floor
        self._wav_limits = wav_limits or WavLoadLimits()
        self._retest_planner = retest_planner
        self._retest_model = retest_model.strip() if retest_model else None
        self._retest_limits = retest_limits
        self._cases: dict[str, _CaseState] = {}
        self._lock = asyncio.Lock()
        self._busy = False
        self._closed = False
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="regression-measure",
        )

    @property
    def recommendation_available(self) -> bool:
        return (
            self._retest_planner is not None
            and self._retest_model is not None
            and self._retest_limits is not None
        )

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

    @asynccontextmanager
    async def hold_operation_slot(self) -> AsyncIterator[None]:
        async with self._lock:
            if self._closed:
                raise _invalid("regression service is closed")
            if self._busy:
                raise _invalid("regression service is busy")
            self._busy = True
        try:
            yield
        finally:
            async with self._lock:
                self._busy = False

    async def submit_comparison(
        self,
        case_id: str,
        upload: ComparisonUpload,
        *,
        request_id: str,
        link: RetestLink | None = None,
        reuse_operation_slot: bool = False,
    ) -> RegressionCaseSnapshot:
        if self._closed:
            raise _invalid("regression service is closed")
        self._validate_request_id(request_id)
        fingerprint = _upload_fingerprint(upload, link)

        slot_held = False
        comparison_running = False
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

            if case.running:
                raise _invalid("regression service is busy")
            if reuse_operation_slot:
                if not self._busy:
                    raise _invalid("regression operation slot is not held")
            elif self._busy:
                raise _invalid("regression service is busy")

            _check_file_sizes(upload, max_file_bytes=self._wav_limits.max_upload_bytes)

            case.running = True
            comparison_running = True
            case.accepted_submit_count += 1
            if not reuse_operation_slot:
                self._busy = True
            slot_held = not reuse_operation_slot

        try:
            cf_future = self._executor.submit(
                _execute_comparison_group,
                upload,
                profile=self._comparison_profile,
                max_file_bytes=self._wav_limits.max_upload_bytes,
            )
            try:
                try:
                    outcome = await asyncio.wrap_future(cf_future)
                except asyncio.CancelledError:
                    # wrap_future cancel does not stop a running worker; keep the
                    # slot until the thread actually finishes.
                    while not cf_future.done():
                        try:
                            await asyncio.sleep(0.01)
                        except asyncio.CancelledError:
                            continue
                    raise
                if inspect.isawaitable(outcome):
                    group_result = await outcome
                else:
                    group_result = outcome
                record = group_result.record
            except (InvalidRequestError, PayloadTooLargeError, AppCapacityError) as error:
                async with self._lock:
                    case = self._require_case(case_id)
                    failure = CaseFailureRecord(
                        case_id=case_id,
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
                        case_id=case_id,
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
                    case_id=case_id,
                    comparison_id=record.comparison_id,
                    record=record,
                    parent_comparison_id=link.parent_comparison_id if link else None,
                    link_kind=link.kind if link else None,
                    request_id=request_id,
                    created_at=self._clock(),
                    full_scale_declarations=upload.full_scale_declarations,
                    baseline_full_scale=group_result.baseline_facts,
                    candidate_full_scale=group_result.candidate_facts,
                )
                case.comparisons.append(item)
                submission_index = submissions_from_items(case.comparisons)
                anchor_id = resolve_anchor_id(record.comparison_id, submission_index)
                anchor_submission = submission_index[anchor_id]
                repeats = tuple(
                    submission_index[row.comparison_id]
                    for row in case.comparisons
                    if row.link_kind == "repeat"
                    and resolve_anchor_id(row.comparison_id, submission_index) == anchor_id
                )
                prior_checks = [
                    check
                    for check in case.full_scale_checks
                    if check.anchor_comparison_id == anchor_id
                ]
                supersedes = prior_checks[-1].check_id if prior_checks else None
                case.full_scale_checks.append(
                    evaluate_full_scale_check(
                        check_id=_new_id("fsc"),
                        anchor=anchor_submission,
                        repeats=repeats,
                        floor=self._full_scale_floor,
                        supersedes=supersedes,
                    )
                )
                recommendation = CaseRecommendationRecord(
                    case_id=case_id,
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
            if comparison_running or slot_held:
                async with self._lock:
                    if comparison_running:
                        held = self._cases.get(case_id)
                        if held is not None:
                            held.running = False
                    if slot_held:
                        self._busy = False

    async def request_recommendation(
        self,
        case_id: str,
        comparison_id: str,
        *,
        request_id: str,
        reuse_operation_slot: bool = False,
    ) -> RegressionCaseSnapshot:
        if self._closed:
            raise _invalid("regression service is closed")
        self._validate_request_id(request_id)

        slot_held = False
        async with self._lock:
            case = self._require_case(case_id)
            item = next(
                (
                    row
                    for row in case.comparisons
                    if row.comparison_id == comparison_id
                ),
                None,
            )
            if item is None:
                raise _invalid("comparison does not exist in this case")
            if item.case_id != case_id:
                raise _invalid("comparison does not belong to this case")
            fingerprint = _recommendation_fingerprint(
                case_id=case_id,
                comparison_id=comparison_id,
                comparison_digest=item.record.digest,
            )
            prior = case.recommendation_outcomes.get(request_id)
            if prior is not None:
                if prior.content_fingerprint != fingerprint:
                    raise _invalid("request_id was reused with different content")
                return self._snapshot(case)

            if case.running:
                raise _invalid("regression service is busy")
            if reuse_operation_slot:
                if not self._busy:
                    raise _invalid("regression operation slot is not held")
            elif self._busy:
                raise _invalid("regression service is busy")

            if not reuse_operation_slot:
                self._busy = True
            slot_held = not reuse_operation_slot

            recommendation_id = _new_id("rec")
            created_at = self._clock()
            comparison_record = item.record

        record_snapshot = comparison_record.model_copy(deep=True)
        try:
            if not self.recommendation_available:
                return await self._finalize_recommendation(
                    case_id=case_id,
                    comparison_id=comparison_id,
                    request_id=request_id,
                    fingerprint=fingerprint,
                    recommendation_id=recommendation_id,
                    created_at=created_at,
                    status="unavailable",
                    detail=(
                        "retest recommendations are not enabled on this product path"
                    ),
                    kind="unavailable",
                    record_snapshot=record_snapshot,
                )

            context = build_retest_context(comparison_record)
            if not context.eligible_options:
                return await self._finalize_recommendation(
                    case_id=case_id,
                    comparison_id=comparison_id,
                    request_id=request_id,
                    fingerprint=fingerprint,
                    recommendation_id=recommendation_id,
                    created_at=created_at,
                    status="unavailable",
                    detail="no eligible retest options for this comparison",
                    kind="unavailable",
                    record_snapshot=record_snapshot,
                )

            planner = self._retest_planner
            assert planner is not None
            choose_task = asyncio.create_task(planner.choose(context))
            try:
                try:
                    selection = await choose_task
                except asyncio.CancelledError:
                    while not choose_task.done():
                        try:
                            await asyncio.sleep(0.01)
                        except asyncio.CancelledError:
                            continue
                    raise
                # AC14: admit at the service boundary, not only inside RealLLMRetestPlanner.
                selection = validate_selection_against_context(
                    selection, context=context
                )
                detail = render_recommendation_detail(selection, context=context)
            except RetestPlannerError as error:
                return await self._finalize_recommendation(
                    case_id=case_id,
                    comparison_id=comparison_id,
                    request_id=request_id,
                    fingerprint=fingerprint,
                    recommendation_id=recommendation_id,
                    created_at=created_at,
                    status="failed",
                    detail=str(error),
                    kind="failed",
                    record_snapshot=record_snapshot,
                )
            except Exception:  # noqa: BLE001 - fail closed; never surface raw planner faults
                return await self._finalize_recommendation(
                    case_id=case_id,
                    comparison_id=comparison_id,
                    request_id=request_id,
                    fingerprint=fingerprint,
                    recommendation_id=recommendation_id,
                    created_at=created_at,
                    status="failed",
                    detail="retest recommendation failed",
                    kind="failed",
                    record_snapshot=record_snapshot,
                )

            return await self._finalize_recommendation(
                case_id=case_id,
                comparison_id=comparison_id,
                request_id=request_id,
                fingerprint=fingerprint,
                recommendation_id=recommendation_id,
                created_at=created_at,
                status="completed",
                detail=detail,
                kind="completed",
                record_snapshot=record_snapshot,
            )
        finally:
            if slot_held:
                async with self._lock:
                    self._busy = False

    async def aclose(self) -> None:
        self._closed = True
        while True:
            async with self._lock:
                running = any(case.running for case in self._cases.values()) or self._busy
            if not running:
                break
            await asyncio.sleep(0.01)
        planner = self._retest_planner
        if planner is not None:
            close = getattr(planner, "aclose", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
        self._cases.clear()
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _recommendation_for_comparison(
        self,
        case: _CaseState,
        comparison_id: str,
    ) -> CaseRecommendationRecord | None:
        for row in reversed(case.recommendations):
            if row.comparison_id == comparison_id:
                return row
        return None

    async def _finalize_recommendation(
        self,
        *,
        case_id: str,
        comparison_id: str,
        request_id: str,
        fingerprint: str,
        recommendation_id: str,
        created_at: datetime,
        status: _RecommendationStatus,
        detail: str,
        kind: Literal["completed", "failed", "unavailable"],
        record_snapshot: ComparisonRecord,
    ) -> RegressionCaseSnapshot:
        recommendation = CaseRecommendationRecord(
            case_id=case_id,
            recommendation_id=recommendation_id,
            comparison_id=comparison_id,
            status=status,
            detail=detail,
            created_at=created_at,
        )
        async with self._lock:
            case = self._require_case(case_id)
            item = next(
                row
                for row in case.comparisons
                if row.comparison_id == comparison_id
            )
            if item.record.model_dump_json() != record_snapshot.model_dump_json():
                raise _invalid("comparison record changed during recommendation")
            case.recommendations.append(recommendation)
            case.recommendation_outcomes[request_id] = _RecommendationOutcome(
                kind=kind,
                content_fingerprint=fingerprint,
                recommendation=recommendation,
            )
            case.revision += 1
            case.updated_at = self._clock()
            return self._snapshot(case)

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
            full_scale_checks=tuple(
                item.model_copy(deep=True) for item in case.full_scale_checks
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
    profile = None
    assert_product_profile_allowed(profile)
    return RegressionWorkbenchService(comparison_profile=profile, full_scale_floor=None)
