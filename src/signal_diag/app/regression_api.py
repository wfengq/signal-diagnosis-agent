"""Regression workbench HTTP routes and bounded comparison uploads."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.resources import files
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from signal_diag.app.errors import ApplicationError, InvalidRequestError
from signal_diag.app.models import AppErrorDetail, AppErrorEnvelope
from signal_diag.app.multipart import (
    ParsedRegressionComparisonUpload,
    parse_regression_comparison_upload,
)
from signal_diag.app.regression import (
    ComparisonUpload,
    RegressionWorkbenchService,
    RetestLink,
)
from signal_diag.app.regression_reporting import (
    build_case_report,
    render_case_html,
    render_case_json,
)
from signal_diag.rules.regression import ComparisonConditions
from signal_diag.signal import WavLoadLimits
from signal_diag.tools.regression_measurement import MeasurementSelection

_CSP = "default-src 'self'; object-src 'none'; base-uri 'none'"
_MAX_FILE_BYTES = WavLoadLimits().max_upload_bytes
_STATUS_BY_CODE = {
    "invalid_request": 422,
    "payload_too_large": 413,
    "capacity_exceeded": 429,
}


class _CreateCaseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    request_id: str | None = Field(default=None, max_length=64)


class RegressionComparisonMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=64)
    baseline_version: str = Field(min_length=1, max_length=256)
    candidate_version: str = Field(min_length=1, max_length=256)
    conditions: ComparisonConditions
    selection: MeasurementSelection
    baseline_filename: str | None = Field(default=None, max_length=256)
    candidate_filename: str | None = Field(default=None, max_length=256)
    original_filename: str | None = Field(default=None, max_length=256)
    link: RetestLink | None = None


def _envelope(detail: AppErrorDetail) -> dict[str, Any]:
    return AppErrorEnvelope(error=detail).model_dump(mode="json")


def _json_error(detail: AppErrorDetail, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_envelope(detail),
        headers={"Content-Security-Policy": _CSP},
    )


async def regression_application_error_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    del request
    status = _http_status_for_error(exc)
    return _json_error(exc.detail, status)


def _http_status_for_error(exc: ApplicationError) -> int:
    code = exc.detail.code
    if code == "invalid_request":
        message = exc.detail.message.lower()
        if "unknown case_id" in message:
            return 404
        if "busy" in message or "running comparison" in message:
            return 409
        if (
            "parent comparison" in message
            or "recommendation" in message
            or "request_id was reused" in message
        ):
            return 409
        return 422
    return _STATUS_BY_CODE.get(code, 500)


def _packaged_static(filename: str, media_type: str) -> Response:
    payload = files("signal_diag.app.static").joinpath(filename).read_bytes()
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Security-Policy": _CSP},
    )


def _filename_or_default(
    explicit: str | None,
    multipart_name: str | None,
    *,
    fallback: str,
) -> str:
    if explicit is not None and explicit.strip():
        return explicit.strip()
    if multipart_name and multipart_name.strip():
        return multipart_name.strip()
    return fallback


def _upload_from_parsed(parsed: ParsedRegressionComparisonUpload) -> ComparisonUpload:
    try:
        metadata = RegressionComparisonMetadata.model_validate_json(parsed.metadata_json)
    except (ValidationError, ValueError) as error:
        raise InvalidRequestError(
            AppErrorDetail(code="invalid_request", message="malformed comparison metadata")
        ) from error
    conditions = metadata.conditions
    if metadata.baseline_version != conditions.baseline_version:
        raise InvalidRequestError(
            AppErrorDetail(
                code="invalid_request",
                message="baseline_version must match conditions.baseline_version",
            )
        )
    if metadata.candidate_version != conditions.candidate_version:
        raise InvalidRequestError(
            AppErrorDetail(
                code="invalid_request",
                message="candidate_version must match conditions.candidate_version",
            )
        )
    baseline_filename = _filename_or_default(
        metadata.baseline_filename,
        parsed.baseline_filename,
        fallback="baseline.wav",
    )
    candidate_filename = _filename_or_default(
        metadata.candidate_filename,
        parsed.candidate_filename,
        fallback="candidate.wav",
    )
    original_filename = metadata.original_filename or parsed.original_filename
    if parsed.original_data is not None and not original_filename:
        raise InvalidRequestError(
            AppErrorDetail(
                code="invalid_request",
                message="original_filename is required when original WAV is provided",
            )
        )
    return ComparisonUpload(
        baseline_data=parsed.baseline_data,
        candidate_data=parsed.candidate_data,
        baseline_filename=baseline_filename,
        candidate_filename=candidate_filename,
        baseline_version=metadata.baseline_version,
        candidate_version=metadata.candidate_version,
        conditions=conditions,
        selection=metadata.selection,
        original_input_data=parsed.original_data,
        original_input_filename=original_filename,
    )


def build_regression_router(service: RegressionWorkbenchService) -> APIRouter:
    """Mount regression workbench routes on a dedicated router."""

    router = APIRouter()

    @router.get("/regression")
    async def regression_page() -> Response:
        return _packaged_static("regression.html", "text/html; charset=utf-8")

    @router.get("/api/v1/regression/capabilities")
    async def regression_capabilities() -> JSONResponse:
        return JSONResponse(
            content={
                "measurement_available": True,
                "recommendation_available": False,
                "enabled_profile_ids": [],
            }
        )

    @router.post("/api/v1/regression/cases")
    async def create_case(body: _CreateCaseBody) -> JSONResponse:
        del body.request_id
        snapshot = service.create_case(body.goal)
        return JSONResponse(content=snapshot.model_dump(mode="json"))

    @router.get("/api/v1/regression/cases/{case_id}")
    async def get_case(case_id: str) -> JSONResponse:
        snapshot = service.get_case(case_id)
        return JSONResponse(content=snapshot.model_dump(mode="json"))

    @router.delete("/api/v1/regression/cases/{case_id}")
    async def delete_case(case_id: str) -> Response:
        service.delete_case(case_id)
        return Response(status_code=204, headers={"Content-Security-Policy": _CSP})

    @router.post("/api/v1/regression/cases/{case_id}/comparisons")
    async def submit_comparison(case_id: str, request: Request) -> JSONResponse:
        async with service.hold_operation_slot():
            parsed = await parse_regression_comparison_upload(
                request,
                max_file_bytes=_MAX_FILE_BYTES,
            )
            try:
                metadata = RegressionComparisonMetadata.model_validate_json(
                    parsed.metadata_json
                )
            except (ValidationError, ValueError) as error:
                raise InvalidRequestError(
                    AppErrorDetail(
                        code="invalid_request", message="malformed comparison metadata"
                    )
                ) from error
            upload = _upload_from_parsed(parsed)
            snapshot = await service.submit_comparison(
                case_id,
                upload,
                request_id=metadata.request_id,
                link=metadata.link,
                reuse_operation_slot=True,
            )
        return JSONResponse(content=snapshot.model_dump(mode="json"))

    @router.get("/api/v1/regression/cases/{case_id}/report.json")
    async def case_report_json(case_id: str) -> Response:
        snapshot = service.get_case(case_id)
        report = build_case_report(snapshot, generated_at=datetime.now(UTC))
        return Response(
            content=render_case_json(report),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.case_id}.report.json"'
                ),
                "Content-Security-Policy": _CSP,
            },
        )

    @router.get("/api/v1/regression/cases/{case_id}/report.html")
    async def case_report_html(case_id: str) -> Response:
        snapshot = service.get_case(case_id)
        report = build_case_report(snapshot, generated_at=datetime.now(UTC))
        return Response(
            content=render_case_html(report),
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.case_id}.report.html"'
                ),
                "Content-Security-Policy": _CSP,
            },
        )

    return router
