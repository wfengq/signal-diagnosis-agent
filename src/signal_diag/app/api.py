"""Bounded FastAPI diagnosis API."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any, Literal, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response as StarletteResponse

from signal_diag.app.composition import build_product_service
from signal_diag.app.contextual_models import ContextualAppRunSnapshot
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    render_contextual_report_html,
    render_contextual_report_json,
)
from signal_diag.app.errors import (
    ApplicationError,
    ReportUnavailableError,
    RunNotTerminalError,
    sanitize_application_error,
)
from signal_diag.app.models import (
    AppErrorDetail,
    AppErrorEnvelope,
    AppRunSnapshot,
    DemoPresetId,
)
from signal_diag.app.multipart import parse_contextual_wav_upload, parse_wav_upload
from signal_diag.app.reporting import (
    build_diagnosis_report,
    load_accepted_evaluation_summary,
    render_report_html,
    render_report_json,
)
from signal_diag.app.service import DiagnosisApplicationService
from signal_diag.signal import WavLoadLimits
from signal_diag.signal.models import ChannelMode

_CSP = "default-src 'self'; object-src 'none'; base-uri 'none'"
_MAX_FILE_BYTES = WavLoadLimits().max_upload_bytes
_STATIC_MEDIA_TYPES = {
    "styles.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
_STATUS_BY_CODE = {
    "invalid_request": 422,
    "invalid_wav": 422,
    "signal_limit_exceeded": 422,
    "unknown_preset": 422,
    "payload_too_large": 413,
    "unsupported_wav": 415,
    "run_not_found": 404,
    "run_not_terminal": 409,
    "report_unavailable": 409,
    "capacity_exceeded": 429,
    "planner_not_configured": 503,
    "trace_integrity_error": 500,
    "internal_error": 500,
}


class _SyntheticSubmitBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str = Field(min_length=1)
    user_request: str
    channel: ChannelMode = "mixdown"


def _envelope(detail: AppErrorDetail) -> dict[str, Any]:
    return AppErrorEnvelope(error=detail).model_dump(mode="json")


def _json_error(detail: AppErrorDetail, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_envelope(detail),
        headers={"Content-Security-Policy": _CSP},
    )


def _service(request: Request) -> DiagnosisApplicationService:
    return cast(DiagnosisApplicationService, request.app.state.service)


def _has_unsafe_static_path(name: str) -> bool:
    if not name:
        return True
    if "/" in name or "\\" in name:
        return True
    if ".." in name:
        return True
    parts = name.replace("\\", "/").split("/")
    return any(part in {".", "..", ""} for part in parts)


def _packaged_static(filename: str, media_type: str) -> Response:
    payload = files("signal_diag.app.static").joinpath(filename).read_bytes()
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Security-Policy": _CSP},
    )


def _static_asset_response(filename: str) -> Response:
    if _has_unsafe_static_path(filename) or filename not in _STATIC_MEDIA_TYPES:
        return Response(
            status_code=404,
            content=b"",
            headers={"Content-Security-Policy": _CSP},
        )
    return _packaged_static(filename, _STATIC_MEDIA_TYPES[filename])


def _completed_snapshot(request: Request, run_id: str) -> AppRunSnapshot:
    snapshot = _service(request).get_run(run_id)
    if snapshot.status in {"queued", "running"}:
        raise RunNotTerminalError(
            AppErrorDetail(
                code="run_not_terminal",
                message="report is available only after the run is completed",
            )
        )
    if snapshot.status == "failed":
        raise ReportUnavailableError(
            AppErrorDetail(
                code="report_unavailable",
                message="application-failed runs do not have a diagnosis report",
            )
        )
    return snapshot


def _completed_contextual_snapshot(
    request: Request, run_id: str
) -> ContextualAppRunSnapshot:
    snapshot = _service(request).get_contextual_run(run_id)
    if snapshot.status in {"queued", "running"}:
        raise RunNotTerminalError(
            AppErrorDetail(
                code="run_not_terminal",
                message="report is available only after the run is completed",
            )
        )
    if snapshot.status == "failed":
        raise ReportUnavailableError(
            AppErrorDetail(
                code="report_unavailable",
                message="application-failed runs do not have a diagnosis report",
            )
        )
    return snapshot


def create_app(
    service: DiagnosisApplicationService | None = None,
) -> FastAPI:
    owned = service is None
    bound = service if service is not None else build_product_service()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.service = bound
        app.state.owns_service = owned
        try:
            yield
        finally:
            if owned:
                await bound.aclose()

    app = FastAPI(lifespan=lifespan, title="Signal Diagnosis Agent")
    app.state.service = bound
    app.state.owns_service = owned

    @app.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[StarletteResponse]],
    ) -> StarletteResponse:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        return response

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        del request
        status = _STATUS_BY_CODE.get(exc.detail.code, 500)
        return _json_error(exc.detail, status)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return _json_error(
            AppErrorDetail(code="invalid_request", message="malformed request"),
            422,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        if isinstance(exc, StarletteHTTPException):
            raise exc
        if isinstance(exc, ApplicationError):
            status = _STATUS_BY_CODE.get(exc.detail.code, 500)
            return _json_error(exc.detail, status)
        del request
        return _json_error(sanitize_application_error(exc), 500)

    @app.get("/api/v1/health")
    async def health(request: Request) -> JSONResponse:
        deps = _service(request)._dependencies
        payload = {
            "status": "ok",
            "planner_configured": deps.planner_configured,
            "planner_identity": deps.planner_identity.model_dump(mode="json"),
        }
        return JSONResponse(content=payload)

    @app.get("/api/v1/presets")
    async def presets(request: Request) -> JSONResponse:
        items = [
            item.model_dump(mode="json") for item in _service(request).list_presets()
        ]
        return JSONResponse(content=items)

    @app.get("/api/v1/presets/{preset_id}/wav")
    async def preset_wav(request: Request, preset_id: str) -> Response:
        payload = _service(request).render_preset_wav(cast(DemoPresetId, preset_id))
        return Response(
            content=payload,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'attachment; filename="input.wav"',
                "Content-Security-Policy": _CSP,
            },
        )

    @app.get("/api/v1/evaluation-summary")
    async def evaluation_summary() -> JSONResponse:
        summary = load_accepted_evaluation_summary()
        return JSONResponse(content=summary.model_dump(mode="json"))

    @app.post("/api/v1/runs/wav")
    async def submit_wav(request: Request) -> JSONResponse:
        parsed = await parse_wav_upload(request, max_file_bytes=_MAX_FILE_BYTES)
        submission = await _service(request).submit_wav(
            parsed.data,
            filename=parsed.filename,
            user_request=parsed.user_request,
            channel=parsed.channel,
        )
        return JSONResponse(status_code=202, content=submission.model_dump(mode="json"))

    @app.post("/api/v1/runs/synthetic")
    async def submit_synthetic(
        request: Request,
        body: _SyntheticSubmitBody,
    ) -> JSONResponse:
        submission = await _service(request).submit_synthetic(
            cast(DemoPresetId, body.preset_id),
            user_request=body.user_request,
            channel=body.channel,
        )
        return JSONResponse(status_code=202, content=submission.model_dump(mode="json"))

    @app.get("/api/v1/runs/{run_id}")
    async def get_run(request: Request, run_id: str) -> JSONResponse:
        snapshot = _service(request).get_run(run_id)
        return JSONResponse(content=snapshot.model_dump(mode="json"))

    @app.get("/api/v1/runs/{run_id}/report.json")
    async def report_json(request: Request, run_id: str) -> Response:
        snapshot = _completed_snapshot(request, run_id)
        report = build_diagnosis_report(snapshot, generated_at=datetime.now(UTC))
        return Response(
            content=render_report_json(report),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.run_id}.report.json"'
                ),
                "Content-Security-Policy": _CSP,
            },
        )

    @app.get("/api/v1/runs/{run_id}/report.html")
    async def report_html(request: Request, run_id: str) -> Response:
        snapshot = _completed_snapshot(request, run_id)
        report = build_diagnosis_report(snapshot, generated_at=datetime.now(UTC))
        return Response(
            content=render_report_html(report),
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.run_id}.report.html"'
                ),
                "Content-Security-Policy": _CSP,
            },
        )

    @app.post("/api/v1/contextual-runs/wav")
    async def submit_contextual_wav(request: Request) -> JSONResponse:
        parsed = await parse_contextual_wav_upload(
            request, max_file_bytes=_MAX_FILE_BYTES
        )
        submission = await _service(request).submit_contextual_wav(
            parsed.test_data,
            test_filename=parsed.test_filename,
            mode=cast(
                Literal["single_signal", "nominal_single_tone", "paired_reference"],
                parsed.mode,
            ),
            reference_data=parsed.reference_data,
            reference_filename=parsed.reference_filename,
            nominal_fundamental_hz=parsed.nominal_fundamental_hz,
            stimulus_kind=cast(
                Literal["single_tone"] | None,
                parsed.stimulus_kind,
            ),
            user_request=parsed.user_request,
            channel=parsed.channel,
        )
        return JSONResponse(status_code=202, content=submission.model_dump(mode="json"))

    @app.get("/api/v1/contextual-runs/{run_id}")
    async def get_contextual_run(request: Request, run_id: str) -> JSONResponse:
        snapshot = _service(request).get_contextual_run(run_id)
        return JSONResponse(content=snapshot.model_dump(mode="json"))

    @app.get("/api/v1/contextual-runs/{run_id}/report.json")
    async def contextual_report_json(request: Request, run_id: str) -> Response:
        snapshot = _completed_contextual_snapshot(request, run_id)
        report = build_contextual_diagnosis_report(
            snapshot, generated_at=datetime.now(UTC)
        )
        return Response(
            content=render_contextual_report_json(report),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.run_id}.report.json"'
                ),
                "Content-Security-Policy": _CSP,
            },
        )

    @app.get("/api/v1/contextual-runs/{run_id}/report.html")
    async def contextual_report_html(request: Request, run_id: str) -> Response:
        snapshot = _completed_contextual_snapshot(request, run_id)
        report = build_contextual_diagnosis_report(
            snapshot, generated_at=datetime.now(UTC)
        )
        return Response(
            content=render_contextual_report_html(report),
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.run_id}.report.html"'
                ),
                "Content-Security-Policy": _CSP,
            },
        )

    @app.get("/")
    async def root() -> Response:
        return _packaged_static("index.html", "text/html; charset=utf-8")

    @app.get("/static/{filename:path}")
    async def static_asset(filename: str) -> Response:
        return _static_asset_response(filename)

    return app
