"""Bounded FastAPI diagnosis API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any, Literal, cast

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response as StarletteResponse

from signal_diag.app.contextual_models import ContextualAppRunSnapshot, DiagnosisPath
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    dump_contextual_snapshot,
    render_contextual_report_html,
    render_contextual_report_json,
)
from signal_diag.app.engine_service import build_engine_service
from signal_diag.app.errors import (
    ApplicationError,
    InvalidRequestError,
    ReportUnavailableError,
    RunNotFoundError,
    RunNotTerminalError,
    sanitize_application_error,
)
from signal_diag.app.explanation_service import (
    ExplanationResult,
    ExplanationService,
    build_explanation_service,
    contextual_explanation_packet,
    render_explanation_html,
    sweep_explanation_packet,
)
from signal_diag.app.guide_service import (
    GuideService,
    build_guide_service,
    render_plan_html,
)
from signal_diag.app.intake_flow import ContextOrigin
from signal_diag.app.models import (
    AppErrorDetail,
    AppErrorEnvelope,
    AppRunSnapshot,
    DemoPresetId,
)
from signal_diag.app.multipart import (
    parse_contextual_wav_upload,
    parse_sweep_upload,
    parse_wav_upload,
)
from signal_diag.app.qa_service import QAService, build_qa_service
from signal_diag.app.regression import build_regression_service
from signal_diag.app.regression_api import (
    _http_status_for_error,
    build_regression_router,
)
from signal_diag.app.reporting import (
    build_diagnosis_report,
    load_accepted_evaluation_summary,
    render_report_html,
    render_report_json,
)
from signal_diag.app.result_qa import MAX_QUESTION_CHARS
from signal_diag.app.service import DiagnosisApplicationService
from signal_diag.app.sweep import (
    SUPPORTED_RATES,
    SweepRunStore,
    diagnose_sweep,
    stimulus_wav,
)
from signal_diag.app.sweep_reporting import (
    build_sweep_report,
    render_sweep_html,
    render_sweep_json,
    sweep_payload,
)
from signal_diag.app.test_plan import (
    ConfirmRequest,
    GuideRequest,
    PlanRejected,
    PlanStore,
    confirm_plan,
    questionnaire_draft,
)
from signal_diag.app.test_session import (
    SessionRejected,
    SessionStore,
    advance,
    apply_answer,
    new_session,
    record_result,
    session_view,
)
from signal_diag.signal import WavLoadLimits
from signal_diag.signal.models import ChannelMode

_CSP = "default-src 'self'; object-src 'none'; base-uri 'none'"
_MAX_FILE_BYTES = WavLoadLimits().max_upload_bytes
_STATIC_MEDIA_TYPES = {
    "styles.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "intake_flow.js": "text/javascript; charset=utf-8",
    "regression.js": "text/javascript; charset=utf-8",
    "sweep.js": "text/javascript; charset=utf-8",
    "explanation.js": "text/javascript; charset=utf-8",
    "guide.js": "text/javascript; charset=utf-8",
    "session.js": "text/javascript; charset=utf-8",
    "qa.js": "text/javascript; charset=utf-8",
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


class _ExplainBody(BaseModel):
    """§30: template by default; ``use_model`` asks for the AI rewrite."""

    model_config = ConfigDict(extra="forbid")

    language: Literal["zh", "en"] = "zh"
    use_model: bool = False


class _QuestionBody(BaseModel):
    """§33: one question about a finished run; ``use_model`` asks the AI."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    language: Literal["zh", "en"] = "zh"
    use_model: bool = False


def _explanation_parts(
    result: ExplanationResult | None,
) -> tuple[dict[str, object] | None, str | None]:
    if result is None:
        return None, None
    return result.model_dump(mode="json"), render_explanation_html(result)


class _GuideDraftBody(BaseModel):
    """§31: questionnaire by default; ``use_model`` asks for an AI draft."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2_000)
    filenames: tuple[str, ...] = Field(default=(), max_length=3)
    sample_rates_hz: tuple[float, ...] = ()
    use_model: bool = False


class _QuestionnaireBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str]
    language: Literal["zh", "en"] = "zh"


class _LinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=80)


class _SessionBody(BaseModel):
    """§32: start a multi-round test session (rule policy, no model)."""

    model_config = ConfigDict(extra="forbid")

    plan_key: str | None = Field(default=None, max_length=80)
    sample_rate_hz: int = 48_000
    connection: str | None = None
    max_rounds: int = 4
    start_outcome: Literal["supported_fault", "no_supported_fault", "inconclusive"] | None = None
    answers: dict[str, bool | float | str] = Field(default_factory=dict)
    language: Literal["zh", "en"] = "zh"


class _SessionAnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=40)
    value: bool | float | str
    language: Literal["zh", "en"] = "zh"


def _session_error(rejected: SessionRejected) -> InvalidRequestError:
    return InvalidRequestError(AppErrorDetail(code="invalid_request", message=str(rejected)))


def _plan_error(rejected: PlanRejected) -> InvalidRequestError:
    return InvalidRequestError(AppErrorDetail(code="invalid_request", message=str(rejected)))


def create_app(
    service: DiagnosisApplicationService | None = None,
    explanation_service: ExplanationService | None = None,
    guide_service: GuideService | None = None,
    qa_service: QAService | None = None,
) -> FastAPI:
    owned = service is None
    bound = service if service is not None else build_engine_service()
    explainer = (
        explanation_service
        if explanation_service is not None
        else build_explanation_service(os.environ)
    )

    guide = guide_service if guide_service is not None else build_guide_service(os.environ)
    qa = qa_service if qa_service is not None else build_qa_service(os.environ)
    plans = PlanStore()
    sessions = SessionStore()
    regression_service = build_regression_service()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.service = bound
        app.state.owns_service = owned
        app.state.regression_service = regression_service
        try:
            yield
        finally:
            if owned:
                await bound.aclose()
            await regression_service.aclose()
            if explanation_service is None:
                await explainer.aclose()
            if guide_service is None:
                await guide.aclose()
            if qa_service is None:
                await qa.aclose()

    app = FastAPI(lifespan=lifespan, title="Signal Diagnosis Agent")
    app.state.service = bound
    app.state.owns_service = owned
    app.state.regression_service = regression_service
    app.include_router(build_regression_router(regression_service))
    sweep_runs = SweepRunStore()

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
        if exc.detail.code == "invalid_request":
            status = _http_status_for_error(exc)
        else:
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
            if exc.detail.code == "invalid_request":
                status = _http_status_for_error(exc)
            else:
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
            # §28 (D053): additive; the T264 fields above keep their meaning.
            "diagnosis_engine": _service(request).diagnosis_engine_status(),
            # §30 (D055): additive.
            "explanation": explainer.status().model_dump(mode="json"),
            # §31 (D057): additive.
            "guide": guide.status().model_dump(mode="json"),
            # §33 (D060 C): additive.
            "qa": qa.status().model_dump(mode="json"),
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

    @app.post("/api/v1/intake/draft")
    async def intake_draft(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except (ValueError, TypeError) as error:
            raise ApplicationError(
                AppErrorDetail(code="invalid_request", message="malformed intake request")
            ) from error
        draft = await _service(request).draft_intake_payload(payload)
        return JSONResponse(content=draft.model_dump(mode="json"))

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
            context_origin=cast(ContextOrigin | None, parsed.context_origin),
            diagnosis_path=cast(DiagnosisPath | None, parsed.diagnosis_path),
        )
        return JSONResponse(status_code=202, content=submission.model_dump(mode="json"))

    @app.get("/api/v1/contextual-runs/{run_id}")
    async def get_contextual_run(request: Request, run_id: str) -> JSONResponse:
        snapshot = _service(request).get_contextual_run(run_id)
        return JSONResponse(content=dump_contextual_snapshot(snapshot))

    @app.get("/api/v1/contextual-runs/{run_id}/report.json")
    async def contextual_report_json(request: Request, run_id: str) -> Response:
        snapshot = _completed_contextual_snapshot(request, run_id)
        report = build_contextual_diagnosis_report(
            snapshot, generated_at=datetime.now(UTC)
        )
        explanation, _ = _explanation_parts(explainer.latest(snapshot.run_id))
        plan = plans.plan_for_run(snapshot.run_id)
        return Response(
            content=render_contextual_report_json(
                report,
                explanation=explanation,
                test_plan=plan.model_dump(mode="json") if plan else None,
            ),
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
        _, explanation_html = _explanation_parts(explainer.latest(snapshot.run_id))
        plan = plans.plan_for_run(snapshot.run_id)
        extra = (explanation_html or "") + (render_plan_html(plan) if plan else "")
        return Response(
            content=render_contextual_report_html(report, explanation_html=extra or None),
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.run_id}.report.html"'
                ),
                "Content-Security-Policy": _CSP,
            },
        )

    @app.get("/sweep")
    async def sweep_page() -> Response:
        return _packaged_static("sweep.html", "text/html; charset=utf-8")

    @app.get("/api/v1/sweep/stimulus")
    async def sweep_stimulus(rate: int = 48_000) -> Response:
        if rate not in SUPPORTED_RATES:
            raise InvalidRequestError(
                AppErrorDetail(
                    code="invalid_request",
                    message=f"rate must be one of {SUPPORTED_RATES}",
                )
            )
        data = await run_in_threadpool(stimulus_wav, rate)
        return Response(
            content=data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="sweep-stimulus-1.0-{rate}.wav"',
                "Content-Security-Policy": _CSP,
            },
        )

    @app.post("/api/v1/sweep-runs")
    async def create_sweep_run(request: Request) -> JSONResponse:
        recordings, labels = await parse_sweep_upload(
            request, max_file_bytes=_MAX_FILE_BYTES
        )
        diagnosis = await run_in_threadpool(
            diagnose_sweep, list(zip(recordings, labels, strict=True))
        )
        sweep_runs.put(diagnosis)
        return JSONResponse(content=sweep_payload(diagnosis))

    @app.get("/api/v1/sweep-runs/{run_id}")
    async def get_sweep_run(run_id: str) -> JSONResponse:
        return JSONResponse(content=sweep_payload(sweep_runs.get(run_id)))

    @app.get("/api/v1/sweep-runs/{run_id}/report.{kind}")
    async def sweep_report(run_id: str, kind: str) -> Response:
        if kind not in ("json", "html"):
            raise RunNotFoundError(
                AppErrorDetail(code="run_not_found", message="unknown report kind")
            )
        built = build_sweep_report(
            sweep_runs.get(run_id), generated_at=datetime.now(UTC)
        )
        explanation, explanation_html = _explanation_parts(explainer.latest(run_id))
        plan = plans.plan_for_run(run_id)
        extra = (explanation_html or "") + (render_plan_html(plan) if plan else "")
        content = (
            render_sweep_json(
                built,
                explanation=explanation,
                test_plan=plan.model_dump(mode="json") if plan else None,
            )
            if kind == "json"
            else render_sweep_html(built, explanation_html=extra or None)
        )
        media = "application/json" if kind == "json" else "text/html; charset=utf-8"
        return Response(
            content=content,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}.report.{kind}"',
                "Content-Security-Policy": _CSP,
            },
        )

    @app.post("/api/v1/contextual-runs/{run_id}/explanation")
    async def explain_contextual_run(
        request: Request, run_id: str, body: _ExplainBody
    ) -> JSONResponse:
        snapshot = _completed_contextual_snapshot(request, run_id)
        packet = contextual_explanation_packet(snapshot)
        result = await explainer.explain(
            packet, language=body.language, use_model=body.use_model
        )
        return JSONResponse(content=result.model_dump(mode="json"))

    @app.post("/api/v1/sweep-runs/{run_id}/explanation")
    async def explain_sweep_run(run_id: str, body: _ExplainBody) -> JSONResponse:
        packet = await run_in_threadpool(sweep_explanation_packet, sweep_runs.get(run_id))
        result = await explainer.explain(
            packet, language=body.language, use_model=body.use_model
        )
        return JSONResponse(content=result.model_dump(mode="json"))

    @app.post("/api/v1/contextual-runs/{run_id}/questions")
    async def ask_contextual_run(request: Request, run_id: str, body: _QuestionBody) -> JSONResponse:
        snapshot = _completed_contextual_snapshot(request, run_id)
        packet = contextual_explanation_packet(snapshot)
        result = await qa.answer(
            packet, body.question, language=body.language, use_model=body.use_model
        )
        return JSONResponse(content=result.model_dump(mode="json"))

    @app.post("/api/v1/sweep-runs/{run_id}/questions")
    async def ask_sweep_run(run_id: str, body: _QuestionBody) -> JSONResponse:
        packet = await run_in_threadpool(sweep_explanation_packet, sweep_runs.get(run_id))
        result = await qa.answer(
            packet, body.question, language=body.language, use_model=body.use_model
        )
        return JSONResponse(content=result.model_dump(mode="json"))

    @app.post("/api/v1/test-plans/draft")
    async def draft_test_plan(body: _GuideDraftBody) -> JSONResponse:
        guide_request = GuideRequest(
            text=body.text, filenames=body.filenames, sample_rates_hz=body.sample_rates_hz
        )
        result = await guide.draft(guide_request, use_model=body.use_model)
        return JSONResponse(content=result.model_dump(mode="json"))

    @app.post("/api/v1/test-plans/questionnaire")
    async def questionnaire_test_plan(body: _QuestionnaireBody) -> JSONResponse:
        try:
            draft = questionnaire_draft(body.answers, language=body.language)
        except PlanRejected as rejected:
            raise _plan_error(rejected) from rejected
        return JSONResponse(content=draft.model_dump(mode="json"))

    @app.post("/api/v1/test-plans/confirm")
    async def confirm_test_plan(body: ConfirmRequest) -> JSONResponse:
        try:
            record = plans.put(confirm_plan(body))
        except PlanRejected as rejected:
            raise _plan_error(rejected) from rejected
        return JSONResponse(content=record.model_dump(mode="json"))

    def _plan(plan_key: str) -> Any:
        record = plans.get(plan_key)
        if record is None:
            raise RunNotFoundError(
                AppErrorDetail(code="run_not_found", message="unknown test plan")
            )
        return record

    @app.get("/api/v1/test-plans/{plan_key}")
    async def get_test_plan(plan_key: str) -> JSONResponse:
        return JSONResponse(content=_plan(plan_key).model_dump(mode="json"))

    @app.post("/api/v1/test-plans/{plan_key}/runs")
    async def link_test_plan(request: Request, plan_key: str, body: _LinkBody) -> JSONResponse:
        _plan(plan_key)
        if body.run_id.startswith("swrun_"):
            sweep_runs.get(body.run_id)
        else:
            _service(request).get_contextual_run(body.run_id)
        plans.link(plan_key, body.run_id)
        return JSONResponse(content={"plan_key": plan_key, "run_id": body.run_id})

    def _session(session_id: str) -> Any:
        state = sessions.get(session_id)
        if state is None:
            raise RunNotFoundError(
                AppErrorDetail(code="run_not_found", message="unknown test session")
            )
        return state

    @app.post("/api/v1/test-sessions")
    async def create_test_session(body: _SessionBody) -> JSONResponse:
        rate, connection = body.sample_rate_hz, body.connection
        if body.plan_key is not None:
            record = _plan(body.plan_key)
            if record.plan_id != "sweep_levels":
                raise _session_error(SessionRejected("plan", "a session starts from a sweep plan"))
            rate = record.parameters.sample_rate_hz or rate
            connection = record.parameters.connection or connection
        try:
            state = new_session(
                sample_rate_hz=rate,
                connection=connection,
                max_rounds=body.max_rounds,
                start_outcome=body.start_outcome,
                answers=body.answers,
                seed=body.plan_key or "",
            )
            state = sessions.put(advance(state))
        except SessionRejected as rejected:
            raise _session_error(rejected) from rejected
        return JSONResponse(content=session_view(state, body.language))

    @app.get("/api/v1/test-sessions/{session_id}")
    async def get_test_session(session_id: str, language: Literal["zh", "en"] = "zh") -> JSONResponse:
        return JSONResponse(content=session_view(_session(session_id), language))

    @app.post("/api/v1/test-sessions/{session_id}/answers")
    async def answer_test_session(session_id: str, body: _SessionAnswerBody) -> JSONResponse:
        state = _session(session_id)
        try:
            state = sessions.put(advance(apply_answer(state, body.field, body.value)))
        except SessionRejected as rejected:
            raise _session_error(rejected) from rejected
        return JSONResponse(content=session_view(state, body.language))

    @app.post("/api/v1/test-sessions/{session_id}/runs")
    async def add_test_session_run(session_id: str, body: _LinkBody) -> JSONResponse:
        state = _session(session_id)
        diagnosis = sweep_runs.get(body.run_id)
        try:
            state = sessions.put(advance(record_result(state, diagnosis)))
        except SessionRejected as rejected:
            raise _session_error(rejected) from rejected
        return JSONResponse(content=session_view(state))

    @app.get("/")
    async def root() -> Response:
        return _packaged_static("index.html", "text/html; charset=utf-8")

    @app.get("/static/{filename:path}")
    async def static_asset(filename: str) -> Response:
        return _static_asset_response(filename)

    return app
