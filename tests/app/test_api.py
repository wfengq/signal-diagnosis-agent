"""Checkpoint Z — bounded FastAPI and polling endpoints (T264–T270)."""

from __future__ import annotations

import ast
import asyncio
import json
import struct
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from signal_diag.agent.models import (
    AgentDecision,
    FinishDecision,
    PlannerContext,
    PlannerError,
    TaskAssessment,
)
from signal_diag.app.api import _static_asset_response, create_app
from signal_diag.app.errors import AppCapacityError
from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualRunSubmission,
)
from signal_diag.app.models import (
    AcceptedEvaluationSummary,
    AppErrorEnvelope,
    AppRunSnapshot,
    DemoPresetId,
    DiagnosisReport,
    PlannerIdentity,
    RunSubmission,
)
from signal_diag.app.presets import list_demo_presets
from signal_diag.app.reporting import load_accepted_evaluation_summary
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository, WavLoadLimits

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "src" / "signal_diag" / "app"
PROFILE_PATH = (
    PROJECT_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
QUESTION = "Why does this signal sound distorted?"
PRESET_IDS: tuple[DemoPresetId, ...] = (
    "clean_periodic",
    "clipping",
    "harmonic_distortion",
    "combined_distortion",
    "noise_inconclusive",
)
CSP = "default-src 'self'; object-src 'none'; base-uri 'none'"
MAX_UPLOAD = WavLoadLimits().max_upload_bytes
RUN_ID_RE = r"^run_[0-9a-f]{32}$"
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_FINISH_DECISION = FinishDecision(
    task_assessment=_ASSESSMENT,
    outcome="inconclusive",
    claims=(),
    confidence_label="low",
    limitations=("deterministic test finish without additional tools",),
)
FORBIDDEN_SECRET_TOKENS = (
    "api_key",
    "api-key",
    "authorization",
    "bearer ",
    "sk-",
    "base_url",
    "base-url",
    "deepseek_api_key",
    "traceback",
)


class _ImmediateFinishPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        return _FINISH_DECISION


class _ProviderFailPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        raise PlannerError("provider unavailable after accept")


class _RuntimeBoomPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        raise RuntimeError("boom sk-SECRETVALUE leaked")


def _identity() -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="v0.2-s1-planner-8.1",
        phase4_certified_default=True,
    )


def _make_service(
    planner_factory: Any,
    *,
    planner_configured: bool = True,
) -> DiagnosisApplicationService:
    dependencies = ApplicationDependencies(
        repository=InMemorySignalRepository(),
        planner_factory=planner_factory,
        planner_identity=_identity(),
        planner_configured=planner_configured,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )
    return DiagnosisApplicationService(dependencies, clock=lambda: NOW)


def _riff_wave(*, fmt_payload: bytes, data: bytes) -> bytes:
    chunks = [b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload]
    chunks.append(b"data" + struct.pack("<I", len(data)) + data)
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
    block_align = channels * bits // 8
    return struct.pack(
        "<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits
    )


def _mono_extrema_wav(*, rate: int = 8_000) -> bytes:
    pcm = struct.pack("<hhh", -32768, 0, 32767)
    return _riff_wave(fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16), data=pcm)


def _encode_multipart(
    *,
    fields: dict[str, bytes],
    files: list[tuple[str, str, bytes]],
    boundary: str = "----ApiTestBoundary",
    terminate: bool = True,
) -> tuple[bytes, str]:
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n'
                "\r\n"
            ).encode("ascii")
            + value
            + b"\r\n"
        )
    for name, filename, data in files:
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n"
                "\r\n"
            ).encode("ascii")
            + data
            + b"\r\n"
        )
    if terminate:
        parts.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _wav_form(
    wav: bytes,
    *,
    filename: str = "demo.wav",
    user_request: str = QUESTION,
    channel: str = "mixdown",
) -> tuple[bytes, str]:
    return _encode_multipart(
        fields={
            "user_request": user_request.encode("utf-8"),
            "channel": channel.encode("utf-8"),
        },
        files=[("file", filename, wav)],
    )


def _oversize_sync_chunks() -> Iterator[bytes]:
    boundary = "----OversizeBoundary"
    preamble, _ = _encode_multipart(
        fields={
            "user_request": QUESTION.encode("utf-8"),
            "channel": b"mixdown",
        },
        files=[],
        boundary=boundary,
        terminate=False,
    )
    file_header = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="huge.wav"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
    ).encode("ascii")
    yield preamble + file_header
    remaining = MAX_UPLOAD + 1
    chunk = b"A" * (256 * 1024)
    while remaining > 0:
        size = min(len(chunk), remaining)
        yield chunk[:size]
        remaining -= size
    yield f"\r\n--{boundary}--\r\n".encode("ascii")


async def _oversize_file_chunks() -> AsyncIterator[bytes]:
    for chunk in _oversize_sync_chunks():
        yield chunk


@contextmanager
def _forbid_disk_spool() -> Iterator[None]:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("WAV upload must not spool or open a filesystem path")

    with (
        patch("tempfile.SpooledTemporaryFile", boom),
        patch("tempfile.NamedTemporaryFile", boom),
        patch("builtins.open", boom),
    ):
        yield


@asynccontextmanager
async def _client(
    service: DiagnosisApplicationService | None = None,
    *,
    app: Any | None = None,
) -> AsyncIterator[AsyncClient]:
    created = app if app is not None else create_app(service=service)
    async with created.router.lifespan_context(created):
        transport = ASGITransport(app=created)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def _assert_csp(response: Any) -> None:
    assert response.headers["content-security-policy"] == CSP


def _assert_json_type(response: Any) -> None:
    assert response.headers["content-type"].startswith("application/json")


def _assert_no_cors(response: Any) -> None:
    names = {name.lower() for name in response.headers}
    assert "access-control-allow-origin" not in names
    assert "access-control-allow-credentials" not in names


def _assert_no_secrets(payload: object) -> None:
    blob = json.dumps(payload).casefold() if not isinstance(payload, str) else payload.casefold()
    for token in FORBIDDEN_SECRET_TOKENS:
        assert token not in blob


def _error_detail(response: Any) -> Any:
    envelope = AppErrorEnvelope.model_validate(response.json())
    return envelope.error


@pytest.fixture
async def finish_service() -> AsyncIterator[DiagnosisApplicationService]:
    service = _make_service(lambda: _ImmediateFinishPlanner())
    try:
        yield service
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t264_readonly_endpoints_load_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    app = create_app()
    async with _client(app=app) as client:
        health = await client.get("/api/v1/health")
        assert health.status_code == 200
        _assert_json_type(health)
        _assert_csp(health)
        _assert_no_cors(health)
        body = health.json()
        assert body["planner_configured"] is False
        identity = body["planner_identity"]
        assert identity["provider"] == "deepseek"
        assert identity["model"]
        assert identity["prompt_version"]
        _assert_no_secrets(body)
        assert "https://" not in json.dumps(body)

        presets = await client.get("/api/v1/presets")
        assert presets.status_code == 200
        _assert_json_type(presets)
        catalog = presets.json()
        assert [item["preset_id"] for item in catalog] == list(PRESET_IDS)
        assert catalog == [item.model_dump(mode="json") for item in list_demo_presets()]

        summary = await client.get("/api/v1/evaluation-summary")
        assert summary.status_code == 200
        _assert_json_type(summary)
        loaded = AcceptedEvaluationSummary.model_validate(summary.json())
        assert loaded == load_accepted_evaluation_summary()

        root = await client.get("/")
        assert root.status_code == 200
        _assert_csp(root)
        assert "text/html" in root.headers["content-type"]
        assert 'id="input-panel"' in root.text
        assert 'href="/static/styles.css"' in root.text
        assert 'src="/static/app.js"' in root.text

        css = await client.get("/static/styles.css")
        assert css.status_code == 200
        _assert_csp(css)
        _assert_no_cors(css)
        assert css.headers["content-type"].startswith("text/css")

        script = await client.get("/static/app.js")
        assert script.status_code == 200
        _assert_csp(script)
        _assert_no_cors(script)
        assert "javascript" in script.headers["content-type"]

        openapi = await client.get("/openapi.json")
        assert openapi.status_code == 200
        _assert_no_secrets(openapi.json())
        paths = openapi.json()["paths"]
        assert "/api/v1/health" in paths
        assert "/api/v1/runs/wav" in paths

    init_source = (APP_DIR / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(init_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "fastapi" not in alias.name.lower()
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "fastapi" not in module.lower()
            assert "multipart" not in module.lower()


@pytest.mark.asyncio
async def test_t265_wav_submission_bounded_multipart_and_status_map(
    finish_service: DiagnosisApplicationService,
) -> None:
    wav = _mono_extrema_wav()
    body, content_type = _wav_form(wav, filename="demo.wav")
    original = finish_service.submit_wav
    repository = finish_service._dependencies.repository

    async with _client(finish_service) as client:
        with _forbid_disk_spool():
            accepted = await client.post(
                "/api/v1/runs/wav",
                content=body,
                headers={"Content-Type": content_type},
            )
        assert accepted.status_code == 202
        _assert_json_type(accepted)
        _assert_csp(accepted)
        submission = RunSubmission.model_validate(accepted.json())
        assert submission.status == "queued"
        terminal = await finish_service.wait_for_terminal(submission.run_id)
        assert terminal.status == "completed"

        before = {item.signal_id for item in repository.list_meta()}
        oversize_called = {"n": 0}

        async def oversize_spy(*args: Any, **kwargs: Any) -> Any:
            oversize_called["n"] += 1
            return await original(*args, **kwargs)

        finish_service.submit_wav = oversize_spy  # type: ignore[method-assign]
        with _forbid_disk_spool():
            too_large = await client.post(
                "/api/v1/runs/wav",
                content=_oversize_file_chunks(),
                headers={"Content-Type": "multipart/form-data; boundary=----OversizeBoundary"},
            )
        assert too_large.status_code == 413
        detail = _error_detail(too_large)
        assert detail.code == "payload_too_large"
        assert detail.message == "WAV upload exceeds 20 MiB"
        assert oversize_called["n"] == 0
        assert {item.signal_id for item in repository.list_meta()} == before
        _assert_csp(too_large)
        _assert_json_type(too_large)
        assert "traceback" not in too_large.text.casefold()

        truncated = wav[:-5]
        invalid = await client.post(
            "/api/v1/runs/wav",
            content=_wav_form(truncated)[0],
            headers={"Content-Type": _wav_form(truncated)[1]},
        )
        assert invalid.status_code == 422
        assert _error_detail(invalid).code == "invalid_wav"

        float_wav = _riff_wave(
            fmt_payload=struct.pack("<HHIIHH", 3, 1, 8_000, 32_000, 4, 32),
            data=struct.pack("<f", 0.0),
        )
        unsupported = await client.post(
            "/api/v1/runs/wav",
            content=_wav_form(float_wav)[0],
            headers={"Content-Type": _wav_form(float_wav)[1]},
        )
        assert unsupported.status_code == 415
        assert _error_detail(unsupported).code == "unsupported_wav"

        low_rate = _mono_extrema_wav(rate=7_999)
        limited = await client.post(
            "/api/v1/runs/wav",
            content=_wav_form(low_rate)[0],
            headers={"Content-Type": _wav_form(low_rate)[1]},
        )
        assert limited.status_code == 422
        assert _error_detail(limited).code == "signal_limit_exceeded"

        missing_boundary = await client.post(
            "/api/v1/runs/wav",
            content=body,
            headers={"Content-Type": "multipart/form-data"},
        )
        assert missing_boundary.status_code == 422
        assert _error_detail(missing_boundary).code == "invalid_request"

        unterminated, ctype = _encode_multipart(
            fields={
                "user_request": QUESTION.encode("utf-8"),
                "channel": b"mixdown",
            },
            files=[("file", "demo.wav", wav)],
            terminate=False,
        )
        malformed = await client.post(
            "/api/v1/runs/wav",
            content=unterminated,
            headers={"Content-Type": ctype},
        )
        assert malformed.status_code == 422
        assert _error_detail(malformed).code == "invalid_request"

        bad_utf8, utf_type = _encode_multipart(
            fields={"user_request": b"\xff\xfe", "channel": b"mixdown"},
            files=[("file", "demo.wav", wav)],
        )
        invalid_utf8 = await client.post(
            "/api/v1/runs/wav",
            content=bad_utf8,
            headers={"Content-Type": utf_type},
        )
        assert invalid_utf8.status_code == 422
        assert _error_detail(invalid_utf8).code == "invalid_request"

        duplicate, dup_type = _encode_multipart(
            fields={
                "user_request": QUESTION.encode("utf-8"),
                "channel": b"mixdown",
            },
            files=[
                ("file", "demo.wav", wav),
                ("file", "other.wav", wav),
            ],
        )
        dup = await client.post(
            "/api/v1/runs/wav",
            content=duplicate,
            headers={"Content-Type": dup_type},
        )
        assert dup.status_code == 422
        assert _error_detail(dup).code == "invalid_request"

        unknown, unk_type = _encode_multipart(
            fields={
                "user_request": QUESTION.encode("utf-8"),
                "channel": b"mixdown",
                "extra": b"nope",
            },
            files=[("file", "demo.wav", wav)],
        )
        extra = await client.post(
            "/api/v1/runs/wav",
            content=unknown,
            headers={"Content-Type": unk_type},
        )
        assert extra.status_code == 422
        assert _error_detail(extra).code == "invalid_request"

        huge_field, huge_type = _encode_multipart(
            fields={
                "user_request": b"x" * (8 * 1024 + 1),
                "channel": b"mixdown",
            },
            files=[("file", "demo.wav", wav)],
        )
        field_calls = {"n": 0}

        async def field_spy(*args: Any, **kwargs: Any) -> Any:
            field_calls["n"] += 1
            return await original(*args, **kwargs)

        finish_service.submit_wav = field_spy  # type: ignore[method-assign]
        oversized_field = await client.post(
            "/api/v1/runs/wav",
            content=huge_field,
            headers={"Content-Type": huge_type},
        )
        assert oversized_field.status_code == 422
        assert _error_detail(oversized_field).code == "invalid_request"
        assert field_calls["n"] == 0
        assert {item.signal_id for item in repository.list_meta()} == before


@pytest.mark.asyncio
async def test_t266_synthetic_submission_and_validation(
    finish_service: DiagnosisApplicationService,
) -> None:
    async with _client(finish_service) as client:
        accepted = await client.post(
            "/api/v1/runs/synthetic",
            json={
                "preset_id": "clipping",
                "user_request": QUESTION,
                "channel": "mixdown",
            },
        )
        assert accepted.status_code == 202
        submission = RunSubmission.model_validate(accepted.json())
        assert submission.status == "queued"
        await finish_service.wait_for_terminal(submission.run_id)

        unknown = await client.post(
            "/api/v1/runs/synthetic",
            json={
                "preset_id": "missing_preset",
                "user_request": QUESTION,
                "channel": "mixdown",
            },
        )
        assert unknown.status_code == 422
        assert _error_detail(unknown).code == "unknown_preset"

        channel = await client.post(
            "/api/v1/runs/synthetic",
            json={
                "preset_id": "clipping",
                "user_request": QUESTION,
                "channel": "middle",
            },
        )
        assert channel.status_code == 422
        assert _error_detail(channel).code == "invalid_request"

        empty = await client.post(
            "/api/v1/runs/synthetic",
            json={"preset_id": "clipping", "user_request": "   ", "channel": "mixdown"},
        )
        assert empty.status_code == 422
        assert _error_detail(empty).code == "invalid_request"

        too_long = await client.post(
            "/api/v1/runs/synthetic",
            json={
                "preset_id": "clipping",
                "user_request": "x" * 2001,
                "channel": "mixdown",
            },
        )
        assert too_long.status_code == 422
        assert _error_detail(too_long).code == "invalid_request"

        malformed = await client.post(
            "/api/v1/runs/synthetic",
            content=b"{not-json",
            headers={"Content-Type": "application/json"},
        )
        assert malformed.status_code == 422
        assert _error_detail(malformed).code == "invalid_request"
        assert "traceback" not in malformed.text.casefold()


@pytest.mark.asyncio
async def test_t267_polling_is_monotonic_and_get_is_immutable() -> None:
    gate = asyncio.Event()
    started = asyncio.Event()

    class GatedPlanner:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            started.set()
            await gate.wait()
            return _FINISH_DECISION

    service = _make_service(lambda: GatedPlanner())
    release_running = asyncio.Event()
    original_mark_running = service._store.mark_running

    async def delayed_mark_running(run_id: str, *, started_at: datetime) -> AppRunSnapshot:
        await release_running.wait()
        return await original_mark_running(run_id, started_at=started_at)

    service._store.mark_running = delayed_mark_running  # type: ignore[method-assign]
    try:
        async with _client(service) as client:
            accepted = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert accepted.status_code == 202
            run_id = accepted.json()["run_id"]
            queued = await client.get(f"/api/v1/runs/{run_id}")
            assert queued.status_code == 200
            queued_snap = AppRunSnapshot.model_validate(queued.json())
            assert queued_snap.status == "queued"
            assert queued_snap.result is None
            assert queued_snap.trace_events == ()
            release_running.set()
            await started.wait()
            running = await client.get(f"/api/v1/runs/{run_id}")
            running_snap = AppRunSnapshot.model_validate(running.json())
            assert running_snap.status == "running"
            assert running_snap.result is None
            assert running_snap.trace_events == ()
            first, second = await asyncio.gather(
                client.get(f"/api/v1/runs/{run_id}"),
                client.get(f"/api/v1/runs/{run_id}"),
            )
            assert first.json() == second.json()
            assert first.json()["status"] == "running"
            gate.set()
            for _ in range(100):
                polled = await client.get(f"/api/v1/runs/{run_id}")
                if polled.json()["status"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.02)
            completed = AppRunSnapshot.model_validate(polled.json())
            assert completed.status == "completed"
            assert completed.result is not None
            assert completed.trace_events
            assert queued_snap.status == "queued"
            assert running_snap.started_at is not None
            assert completed.finished_at is not None
    finally:
        release_running.set()
        gate.set()
        await service.aclose()


@pytest.mark.asyncio
async def test_t268_report_endpoints_and_conflict_states() -> None:
    gate = asyncio.Event()
    started = asyncio.Event()

    class GatedPlanner:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            started.set()
            await gate.wait()
            return _FINISH_DECISION

    success_service = _make_service(lambda: _ImmediateFinishPlanner())
    gated_service = _make_service(lambda: GatedPlanner())
    failed_service = _make_service(lambda: _RuntimeBoomPlanner())
    nested_service = _make_service(lambda: _ProviderFailPlanner())
    try:
        async with _client(success_service) as client:
            accepted = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            run_id = accepted.json()["run_id"]
            await success_service.wait_for_terminal(run_id)
            json_report = await client.get(f"/api/v1/runs/{run_id}/report.json")
            assert json_report.status_code == 200
            _assert_json_type(json_report)
            _assert_csp(json_report)
            assert json_report.headers["content-disposition"] == (
                f'attachment; filename="{run_id}.report.json"'
            )
            report = DiagnosisReport.model_validate_json(json_report.text)
            assert report.run_id == run_id
            assert report.status == "completed"
            html_report = await client.get(f"/api/v1/runs/{run_id}/report.html")
            assert html_report.status_code == 200
            assert html_report.headers["content-type"].startswith("text/html")
            assert "utf-8" in html_report.headers["content-type"].lower()
            assert html_report.headers["content-disposition"] == (
                f'attachment; filename="{run_id}.report.html"'
            )
            _assert_csp(html_report)
            assert run_id in html_report.text
            assert "<!DOCTYPE html>" in html_report.text

            missing = await client.get(
                "/api/v1/runs/run_" + ("0" * 32) + "/report.json"
            )
            assert missing.status_code == 404
            assert _error_detail(missing).code == "run_not_found"

        async with _client(gated_service) as client:
            accepted = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            run_id = accepted.json()["run_id"]
            queued_report = await client.get(f"/api/v1/runs/{run_id}/report.json")
            assert queued_report.status_code == 409
            assert _error_detail(queued_report).code == "run_not_terminal"
            await started.wait()
            running_report = await client.get(f"/api/v1/runs/{run_id}/report.html")
            assert running_report.status_code == 409
            assert _error_detail(running_report).code == "run_not_terminal"
            gate.set()
            await gated_service.wait_for_terminal(run_id)

        async with _client(failed_service) as client:
            accepted = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            run_id = accepted.json()["run_id"]
            failed = await failed_service.wait_for_terminal(run_id)
            assert failed.status == "failed"
            unavailable = await client.get(f"/api/v1/runs/{run_id}/report.json")
            assert unavailable.status_code == 409
            assert _error_detail(unavailable).code == "report_unavailable"

        async with _client(nested_service) as client:
            accepted = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert accepted.status_code == 202
            run_id = accepted.json()["run_id"]
            nested = await nested_service.wait_for_terminal(run_id)
            assert nested.status == "completed"
            assert nested.result is not None
            assert nested.result.status == "error"
            allowed = await client.get(f"/api/v1/runs/{run_id}/report.json")
            assert allowed.status_code == 200
            DiagnosisReport.model_validate_json(allowed.text)
    finally:
        gate.set()
        await success_service.aclose()
        await gated_service.aclose()
        await failed_service.aclose()
        await nested_service.aclose()


@pytest.mark.asyncio
async def test_t269_http_security_defaults_and_normalized_errors(
    finish_service: DiagnosisApplicationService,
) -> None:
    async with _client(finish_service) as client:
        health = await client.get(
            "/api/v1/health",
            headers={"Origin": "https://evil.example"},
        )
        _assert_no_cors(health)
        _assert_csp(health)
        traversal = await client.get("/static/../../pyproject.toml")
        assert traversal.status_code in {404, 422}
        assert "DiagnosisApplicationService" not in traversal.text
        escaped = await client.get("/static/%2e%2e/%2e%2e/src/signal_diag/app/service.py")
        assert escaped.status_code in {404, 422}
        assert "BoundedRunExecutor" not in escaped.text
        for path in (
            "/static/index.html",
            "/static/secret.js",
            "/static/foo/styles.css",
            "/static/styles.css/extra.js",
        ):
            rejected = await client.get(path)
            assert rejected.status_code in {404, 422}
            assert "DiagnosisApplicationService" not in rejected.text
        css = await client.get("/static/styles.css")
        js = await client.get("/static/app.js")
        assert css.status_code == 200
        assert js.status_code == 200
        assert css.headers["content-type"].startswith("text/css")
        assert "javascript" in js.headers["content-type"]
        _assert_csp(css)
        _assert_csp(js)
        for name in ("./app.js", "../styles.css", "styles.css/../app.js", r"..\app.js"):
            denied = _static_asset_response(name)
            assert denied.status_code in {404, 422}
        bad = await client.post(
            "/api/v1/runs/synthetic",
            json={"preset_id": "clipping", "user_request": "", "channel": "mixdown"},
        )
        assert bad.status_code == 422
        _assert_json_type(bad)
        _assert_csp(bad)
        assert "traceback" not in bad.text.casefold()
        assert "File " not in bad.text

    for path in APP_DIR.glob("*.py"):
        if path.name in {"api.py", "multipart.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "fastapi" not in text.casefold()
        assert "from starlette" not in text
        assert "import starlette" not in text
    api_source = (APP_DIR / "api.py").read_text(encoding="utf-8")
    multipart_source = (APP_DIR / "multipart.py").read_text(encoding="utf-8")
    for source in (api_source, multipart_source):
        assert "CORSMiddleware" not in source
        assert "UploadFile" not in source
        assert "request.form(" not in source
        assert "SpooledTemporaryFile" not in source
        assert "NamedTemporaryFile" not in source
    assert "CORSMiddleware" not in api_source
    assert "StaticFiles" not in api_source
    assert 'files("signal_diag.app.static")' in api_source


@pytest.mark.asyncio
async def test_t270_unconfigured_capacity_shutdown_and_post_accept_failures() -> None:
    unconfigured = _make_service(lambda: _ImmediateFinishPlanner(), planner_configured=False)
    provider_service = _make_service(lambda: _ProviderFailPlanner())
    boom_service = _make_service(lambda: _RuntimeBoomPlanner())
    gate = asyncio.Event()
    started = asyncio.Event()

    class GatedPlanner:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            started.set()
            await gate.wait()
            return _FINISH_DECISION

    capacity_service = _make_service(lambda: GatedPlanner())
    shutdown_service = _make_service(lambda: _ImmediateFinishPlanner())
    try:
        async with _client(unconfigured) as client:
            denied = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert denied.status_code == 503
            assert _error_detail(denied).code == "planner_not_configured"
            assert unconfigured._dependencies.repository.list_meta() == []
            missing = await client.get("/api/v1/runs/" + "run_" + ("0" * 32))
            assert missing.status_code == 404
            assert _error_detail(missing).code == "run_not_found"

        async with _client(provider_service) as client:
            accepted = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert accepted.status_code == 202
            run_id = accepted.json()["run_id"]
            snapshot = await provider_service.wait_for_terminal(run_id)
            polled = await client.get(f"/api/v1/runs/{run_id}")
            assert polled.status_code == 200
            body = polled.json()
            assert body["status"] == "completed"
            assert body["result"]["status"] == "error"
            assert snapshot.status == "completed"
            _assert_no_secrets(body)

        async with _client(boom_service) as client:
            accepted = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert accepted.status_code == 202
            run_id = accepted.json()["run_id"]
            failed = await boom_service.wait_for_terminal(run_id)
            polled = await client.get(f"/api/v1/runs/{run_id}")
            assert polled.status_code == 200
            body = polled.json()
            assert body["status"] == "failed"
            assert body["application_error"]["code"] == "internal_error"
            assert "sk-SECRETVALUE" not in polled.text
            assert failed.application_error is not None
            assert failed.application_error.code == "internal_error"

        async with _client(capacity_service) as client:
            first = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert first.status_code == 202
            await started.wait()
            for _ in range(4):
                queued = await client.post(
                    "/api/v1/runs/synthetic",
                    json={
                        "preset_id": "clipping",
                        "user_request": QUESTION,
                        "channel": "mixdown",
                    },
                )
                assert queued.status_code == 202
            overflow = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert overflow.status_code == 429
            assert _error_detail(overflow).code == "capacity_exceeded"
            gate.set()

        await shutdown_service.aclose()
        async with _client(shutdown_service) as client:
            closed = await client.post(
                "/api/v1/runs/synthetic",
                json={
                    "preset_id": "clipping",
                    "user_request": QUESTION,
                    "channel": "mixdown",
                },
            )
            assert closed.status_code == 429
            assert _error_detail(closed).code == "capacity_exceeded"

        api_source = (APP_DIR / "api.py").read_text(encoding="utf-8")
        assert "ScriptedPlanner" not in api_source
        with pytest.raises(AppCapacityError):
            await shutdown_service.submit_synthetic(
                "clipping",
                user_request=QUESTION,
            )
    finally:
        gate.set()
        await unconfigured.aclose()
        await provider_service.aclose()
        await boom_service.aclose()
        await capacity_service.aclose()
        await shutdown_service.aclose()


def _contextual_wav_form(
    test_wav: bytes,
    *,
    mode: str,
    reference_wav: bytes | None = None,
    nominal_fundamental_hz: str | None = None,
    stimulus_kind: str | None = None,
    filename: str = "test.wav",
    reference_filename: str = "ref.wav",
    user_request: str = QUESTION,
    channel: str = "mixdown",
) -> tuple[bytes, str]:
    fields: dict[str, bytes] = {
        "mode": mode.encode("utf-8"),
        "user_request": user_request.encode("utf-8"),
        "channel": channel.encode("utf-8"),
    }
    if nominal_fundamental_hz is not None:
        fields["nominal_fundamental_hz"] = nominal_fundamental_hz.encode("utf-8")
    if stimulus_kind is not None:
        fields["stimulus_kind"] = stimulus_kind.encode("utf-8")
    files: list[tuple[str, str, bytes]] = [("test_file", filename, test_wav)]
    if reference_wav is not None:
        files.append(("reference_file", reference_filename, reference_wav))
    return _encode_multipart(fields=fields, files=files)


async def _oversize_contextual_file_chunks(
    *,
    field_name: str = "test_file",
    include_reference: bool = False,
) -> AsyncIterator[bytes]:
    boundary = "----ContextualOversizeBoundary"
    fields: dict[str, bytes] = {
        "mode": b"nominal_single_tone",
        "user_request": QUESTION.encode("utf-8"),
        "channel": b"mixdown",
        "stimulus_kind": b"single_tone",
        "nominal_fundamental_hz": b"440",
    }
    files: list[tuple[str, str, bytes]] = []
    if include_reference:
        fields["mode"] = b"paired_reference"
        files.append(("reference_file", "ref.wav", _mono_extrema_wav()))
        fields.pop("stimulus_kind", None)
        fields.pop("nominal_fundamental_hz", None)
    preamble, _ = _encode_multipart(
        fields=fields,
        files=files,
        boundary=boundary,
        terminate=False,
    )
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; '
        f'filename="huge.wav"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
    ).encode("ascii")
    yield preamble + file_header
    remaining = MAX_UPLOAD + 1
    chunk = b"A" * (256 * 1024)
    while remaining > 0:
        size = min(len(chunk), remaining)
        yield chunk[:size]
        remaining -= size
    yield f"\r\n--{boundary}--\r\n".encode("ascii")


@pytest.mark.asyncio
async def test_t_cx106_contextual_nominal_wav_route(
    finish_service: DiagnosisApplicationService,
) -> None:
    wav = _mono_extrema_wav()
    body, content_type = _contextual_wav_form(
        wav,
        mode="nominal_single_tone",
        stimulus_kind="single_tone",
        nominal_fundamental_hz="440",
    )
    async with _client(finish_service) as client:
        with _forbid_disk_spool():
            accepted = await client.post(
                "/api/v1/contextual-runs/wav",
                content=body,
                headers={"Content-Type": content_type},
            )
        assert accepted.status_code == 202
        _assert_json_type(accepted)
        _assert_csp(accepted)
        submission = ContextualRunSubmission.model_validate(accepted.json())
        assert submission.status == "queued"
        terminal = await finish_service.wait_for_contextual_terminal(submission.run_id)
        assert terminal.status == "completed"
        assert terminal.stimulus_context.mode == "nominal_single_tone"


@pytest.mark.asyncio
async def test_t_cx107_contextual_paired_snapshot_route(
    finish_service: DiagnosisApplicationService,
) -> None:
    wav = _mono_extrema_wav()
    body, content_type = _contextual_wav_form(
        wav,
        mode="paired_reference",
        reference_wav=wav,
    )
    async with _client(finish_service) as client:
        accepted = await client.post(
            "/api/v1/contextual-runs/wav",
            content=body,
            headers={"Content-Type": content_type},
        )
        assert accepted.status_code == 202
        run_id = accepted.json()["run_id"]
        terminal = await finish_service.wait_for_contextual_terminal(run_id)
        polled = await client.get(f"/api/v1/contextual-runs/{run_id}")
        assert polled.status_code == 200
        snapshot = ContextualAppRunSnapshot.model_validate(polled.json())
        assert snapshot.status == "completed"
        assert snapshot.stimulus_context.mode == "paired_reference"
        assert snapshot.reference_source is not None
        assert terminal.status == "completed"


@pytest.mark.asyncio
async def test_t_cx108_contextual_report_routes(
    finish_service: DiagnosisApplicationService,
) -> None:
    wav = _mono_extrema_wav()
    body, content_type = _contextual_wav_form(
        wav,
        mode="paired_reference",
        reference_wav=wav,
    )
    async with _client(finish_service) as client:
        accepted = await client.post(
            "/api/v1/contextual-runs/wav",
            content=body,
            headers={"Content-Type": content_type},
        )
        run_id = accepted.json()["run_id"]
        await finish_service.wait_for_contextual_terminal(run_id)
        json_report = await client.get(f"/api/v1/contextual-runs/{run_id}/report.json")
        html_report = await client.get(f"/api/v1/contextual-runs/{run_id}/report.html")
        assert json_report.status_code == 200
        assert html_report.status_code == 200
        assert "application/json" in json_report.headers["content-type"]
        assert "text/html" in html_report.headers["content-type"]
        assert "schema_version" in json_report.text
        assert "Declared context" in html_report.text or "declared" in html_report.text.casefold()
        assert "Measured Evidence" in html_report.text or "evidence" in html_report.text.casefold()
        assert run_id in json_report.headers.get("content-disposition", "")
        assert run_id in html_report.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_t_cx109_contextual_per_file_limit(
    finish_service: DiagnosisApplicationService,
) -> None:
    original = finish_service.submit_contextual_wav
    calls = {"n": 0}

    async def spy(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        return await original(*args, **kwargs)

    finish_service.submit_contextual_wav = spy  # type: ignore[method-assign]
    async with _client(finish_service) as client:
        with _forbid_disk_spool():
            too_large_test = await client.post(
                "/api/v1/contextual-runs/wav",
                content=_oversize_contextual_file_chunks(field_name="test_file"),
                headers={
                    "Content-Type": (
                        "multipart/form-data; boundary=----ContextualOversizeBoundary"
                    )
                },
            )
        assert too_large_test.status_code == 413
        assert _error_detail(too_large_test).code == "payload_too_large"
        assert calls["n"] == 0

        # Build an oversize reference while keeping a valid small test_file.
        boundary = "----ContextualRefOversize"
        wav = _mono_extrema_wav()
        preamble, _ = _encode_multipart(
            fields={
                "mode": b"paired_reference",
                "user_request": QUESTION.encode("utf-8"),
                "channel": b"mixdown",
            },
            files=[("test_file", "test.wav", wav)],
            boundary=boundary,
            terminate=False,
        )
        file_header = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="reference_file"; '
            'filename="huge.wav"\r\n'
            "Content-Type: application/octet-stream\r\n"
            "\r\n"
        ).encode("ascii")

        async def ref_chunks() -> AsyncIterator[bytes]:
            yield preamble + file_header
            remaining = MAX_UPLOAD + 1
            chunk = b"B" * (256 * 1024)
            while remaining > 0:
                size = min(len(chunk), remaining)
                yield chunk[:size]
                remaining -= size
            yield f"\r\n--{boundary}--\r\n".encode("ascii")

        with _forbid_disk_spool():
            too_large_ref = await client.post(
                "/api/v1/contextual-runs/wav",
                content=ref_chunks(),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
        assert too_large_ref.status_code == 413
        assert _error_detail(too_large_ref).code == "payload_too_large"
        assert calls["n"] == 0
        assert "traceback" not in too_large_ref.text.casefold()


@pytest.mark.asyncio
async def test_t_cx110_contextual_aggregate_body_limit(
    finish_service: DiagnosisApplicationService,
) -> None:
    original = finish_service.submit_contextual_wav
    calls = {"n": 0}

    async def spy(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        return await original(*args, **kwargs)

    finish_service.submit_contextual_wav = spy  # type: ignore[method-assign]
    boundary = "----ContextualAggregate"
    wav = _mono_extrema_wav()
    body, _ = _encode_multipart(
        fields={
            "mode": b"paired_reference",
            "user_request": QUESTION.encode("utf-8"),
            "channel": b"mixdown",
        },
        files=[
            ("test_file", "test.wav", wav),
            ("reference_file", "ref.wav", wav),
        ],
        boundary=boundary,
    )
    max_total = (2 * MAX_UPLOAD) + (64 * 1024)
    padding = b"X" * (max_total - len(body) + 1)

    async def aggregate_chunks() -> AsyncIterator[bytes]:
        yield body
        yield padding

    async with _client(finish_service) as client:
        with _forbid_disk_spool():
            rejected = await client.post(
                "/api/v1/contextual-runs/wav",
                content=aggregate_chunks(),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
        assert rejected.status_code == 413
        assert _error_detail(rejected).code == "payload_too_large"
        assert calls["n"] == 0


@pytest.mark.asyncio
async def test_t_cx111_contextual_multipart_validation_and_sanitized_errors(
    finish_service: DiagnosisApplicationService,
) -> None:
    wav = _mono_extrema_wav()
    original = finish_service.submit_contextual_wav
    calls = {"n": 0}

    async def spy(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        return await original(*args, **kwargs)

    finish_service.submit_contextual_wav = spy  # type: ignore[method-assign]
    async with _client(finish_service) as client:
        missing, missing_type = _encode_multipart(
            fields={
                "user_request": QUESTION.encode("utf-8"),
                "channel": b"mixdown",
            },
            files=[("test_file", "test.wav", wav)],
        )
        missing_mode = await client.post(
            "/api/v1/contextual-runs/wav",
            content=missing,
            headers={"Content-Type": missing_type},
        )
        assert missing_mode.status_code == 422
        assert _error_detail(missing_mode).code == "invalid_request"

        duplicate, dup_type = _encode_multipart(
            fields={
                "mode": b"nominal_single_tone",
                "user_request": QUESTION.encode("utf-8"),
                "channel": b"mixdown",
                "stimulus_kind": b"single_tone",
                "nominal_fundamental_hz": b"440",
            },
            files=[
                ("test_file", "test.wav", wav),
                ("test_file", "other.wav", wav),
            ],
        )
        dup = await client.post(
            "/api/v1/contextual-runs/wav",
            content=duplicate,
            headers={"Content-Type": dup_type},
        )
        assert dup.status_code == 422
        assert _error_detail(dup).code == "invalid_request"

        unknown, unk_type = _encode_multipart(
            fields={
                "mode": b"nominal_single_tone",
                "user_request": QUESTION.encode("utf-8"),
                "channel": b"mixdown",
                "stimulus_kind": b"single_tone",
                "nominal_fundamental_hz": b"440",
                "extra": b"nope",
            },
            files=[("test_file", "test.wav", wav)],
        )
        extra = await client.post(
            "/api/v1/contextual-runs/wav",
            content=unknown,
            headers={"Content-Type": unk_type},
        )
        assert extra.status_code == 422
        assert _error_detail(extra).code == "invalid_request"
        assert calls["n"] == 0
        for response in (missing_mode, dup, extra):
            assert "traceback" not in response.text.casefold()
            assert "File " not in response.text
            _assert_csp(response)


@pytest.mark.asyncio
async def test_t_cx112_original_wav_route_unchanged(
    finish_service: DiagnosisApplicationService,
) -> None:
    wav = _mono_extrema_wav()
    body, content_type = _wav_form(wav, filename="demo.wav")
    async with _client(finish_service) as client:
        accepted = await client.post(
            "/api/v1/runs/wav",
            content=body,
            headers={"Content-Type": content_type},
        )
        assert accepted.status_code == 202
        submission = RunSubmission.model_validate(accepted.json())
        terminal = await finish_service.wait_for_terminal(submission.run_id)
        assert terminal.status == "completed"
        snapshot = AppRunSnapshot.model_validate(
            (await client.get(f"/api/v1/runs/{submission.run_id}")).json()
        )
        assert snapshot.status == "completed"
        assert "stimulus_context" not in snapshot.model_dump()
        assert "reference_source" not in snapshot.model_dump()
