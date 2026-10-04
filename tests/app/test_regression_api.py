"""Phase B Task 6: regression workbench HTTP API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from signal_diag.app.errors import ApplicationError
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.regression import (
    RegressionWorkbenchService,
    build_regression_service,
)
from signal_diag.app.regression_api import (
    build_regression_router,
    regression_application_error_handler,
)
from signal_diag.signal import WavLoadLimits, generate_sine
from tests.app.test_api import (
    CSP,
    _client,
    _encode_multipart,
    _error_detail,
    _make_service,
    _wav_form,
)

NOW = datetime(2026, 10, 4, 16, 0, tzinfo=UTC)
MAX_UPLOAD = WavLoadLimits().max_upload_bytes


def _mono_wav_bytes() -> bytes:
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.5,
        amplitude=0.4,
    )
    return encode_pcm32_wav(case.record.samples, sample_rate_hz=48_000)


def _metadata_bytes(**overrides: object) -> bytes:
    base: dict[str, Any] = {
        "request_id": "req-compare-1",
        "baseline_version": "v1",
        "candidate_version": "v2",
        "conditions": {
            "intent": "preserve_behavior",
            "baseline_version": "v1",
            "candidate_version": "v2",
            "stimulus_key": "sine-200",
            "parameters_key": "default",
            "same_input": "yes",
            "parameters_unchanged": "yes",
            "aligned_ranges": "yes",
            "repeatability": "declared_deterministic",
        },
        "selection": {
            "clipping": {"channel": "left", "full_scale_threshold": 0.99},
            "harmonic": {"channel": "left", "fundamental_hz": 200.0},
        },
        "link": None,
    }
    base.update(overrides)
    return json.dumps(base).encode("utf-8")


def _comparison_form(
    baseline: bytes,
    candidate: bytes,
    *,
    metadata: bytes | None = None,
    extra_files: list[tuple[str, str, bytes]] | None = None,
) -> tuple[bytes, str]:
    files: list[tuple[str, str, bytes]] = [
        ("baseline", "baseline.wav", baseline),
        ("candidate", "candidate.wav", candidate),
    ]
    if extra_files:
        files.extend(extra_files)
    return _encode_multipart(
        fields={"metadata": metadata or _metadata_bytes()},
        files=files,
    )


@pytest.fixture
async def regression_client() -> AsyncIterator[AsyncClient]:
    service = RegressionWorkbenchService(clock=lambda: NOW)
    app = FastAPI()
    app.include_router(build_regression_router(service))
    app.add_exception_handler(ApplicationError, regression_application_error_handler)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await service.aclose()


@pytest.mark.asyncio
async def test_capabilities_and_create_case(regression_client: AsyncClient) -> None:
    caps = await regression_client.get("/api/v1/regression/capabilities")
    assert caps.status_code == 200
    body = caps.json()
    assert body["measurement_available"] is True
    assert body["recommendation_available"] is False
    assert body["enabled_profile_ids"] == []

    created = await regression_client.post(
        "/api/v1/regression/cases",
        json={"goal": "compare builds"},
    )
    assert created.status_code == 200
    snapshot = created.json()
    assert snapshot["goal"] == "compare builds"
    assert snapshot["case_id"].startswith("case_")


@pytest.mark.asyncio
async def test_multipart_comparison_reaches_service(
    regression_client: AsyncClient,
) -> None:
    wav = _mono_wav_bytes()
    created = await regression_client.post(
        "/api/v1/regression/cases",
        json={"goal": "goal"},
    )
    case_id = created.json()["case_id"]
    body, content_type = _comparison_form(wav, wav)
    response = await regression_client.post(
        f"/api/v1/regression/cases/{case_id}/comparisons",
        content=body,
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 200
    snapshot = response.json()
    assert len(snapshot["comparisons"]) == 1
    clipping = snapshot["comparisons"][0]["record"]["metric_comparisons"][0]
    assert clipping["status"] == "descriptive_only"


@pytest.mark.asyncio
async def test_unknown_case_returns_404(regression_client: AsyncClient) -> None:
    response = await regression_client.get("/api/v1/regression/cases/case_missing")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_metadata_profile_field_rejected(regression_client: AsyncClient) -> None:
    wav = _mono_wav_bytes()
    created = await regression_client.post(
        "/api/v1/regression/cases",
        json={"goal": "goal"},
    )
    case_id = created.json()["case_id"]
    body, content_type = _comparison_form(
        wav,
        wav,
        metadata=_metadata_bytes(profile_id="forged"),
    )
    response = await regression_client.post(
        f"/api/v1/regression/cases/{case_id}/comparisons",
        content=body,
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_multipart_field_rejected(
    regression_client: AsyncClient,
) -> None:
    wav = _mono_wav_bytes()
    created = await regression_client.post(
        "/api/v1/regression/cases",
        json={"goal": "goal"},
    )
    case_id = created.json()["case_id"]
    duplicate, content_type = _encode_multipart(
        fields={"metadata": _metadata_bytes()},
        files=[
            ("baseline", "a.wav", wav),
            ("baseline", "b.wav", wav),
            ("candidate", "c.wav", wav),
        ],
    )
    response = await regression_client.post(
        f"/api/v1/regression/cases/{case_id}/comparisons",
        content=duplicate,
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_oversize_file_rejected(regression_client: AsyncClient) -> None:
    wav = _mono_wav_bytes()
    created = await regression_client.post(
        "/api/v1/regression/cases",
        json={"goal": "goal"},
    )
    case_id = created.json()["case_id"]
    huge = b"\x00" * (MAX_UPLOAD + 1)
    body, content_type = _comparison_form(huge, wav)
    response = await regression_client.post(
        f"/api/v1/regression/cases/{case_id}/comparisons",
        content=body,
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_report_exports(regression_client: AsyncClient) -> None:
    wav = _mono_wav_bytes()
    created = await regression_client.post(
        "/api/v1/regression/cases",
        json={"goal": "export me"},
    )
    case_id = created.json()["case_id"]
    body, content_type = _comparison_form(wav, wav)
    await regression_client.post(
        f"/api/v1/regression/cases/{case_id}/comparisons",
        content=body,
        headers={"Content-Type": content_type},
    )
    json_report = await regression_client.get(
        f"/api/v1/regression/cases/{case_id}/report.json"
    )
    html_report = await regression_client.get(
        f"/api/v1/regression/cases/{case_id}/report.html"
    )
    assert json_report.status_code == 200
    assert html_report.status_code == 200
    assert json_report.headers["content-security-policy"] == CSP
    assert "evidence_id" in json_report.text
    assert "export me" in html_report.text


@pytest.mark.asyncio
async def test_regression_works_without_planner_key() -> None:
    unconfigured = _make_service(lambda: None, planner_configured=False)
    try:
        async with _client(unconfigured) as client:
            caps = await client.get("/api/v1/regression/capabilities")
            assert caps.status_code == 200
            created = await client.post(
                "/api/v1/regression/cases",
                json={"goal": "no key"},
            )
            assert created.status_code == 200
            case_id = created.json()["case_id"]
            wav = _mono_wav_bytes()
            body, content_type = _comparison_form(wav, wav)
            compare = await client.post(
                f"/api/v1/regression/cases/{case_id}/comparisons",
                content=body,
                headers={"Content-Type": content_type},
            )
            assert compare.status_code == 200
            diag_body, diag_type = _wav_form(wav)
            denied = await client.post(
                "/api/v1/runs/wav",
                content=diag_body,
                headers={"Content-Type": diag_type},
            )
            assert denied.status_code == 503
            assert _error_detail(denied).code == "planner_not_configured"
    finally:
        await unconfigured.aclose()


@pytest.mark.asyncio
async def test_busy_comparison_post_returns_409_without_parsing_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.app import regression_api as regression_api_mod

    parse_calls = 0
    original_parse = regression_api_mod.parse_regression_comparison_upload

    async def counting_parse(*args: Any, **kwargs: Any) -> Any:
        nonlocal parse_calls
        parse_calls += 1
        return await original_parse(*args, **kwargs)

    monkeypatch.setattr(
        regression_api_mod,
        "parse_regression_comparison_upload",
        counting_parse,
    )

    wav = _mono_wav_bytes()
    held_service = RegressionWorkbenchService(clock=lambda: NOW)
    held_service._busy = True
    try:
        app = FastAPI()
        app.include_router(build_regression_router(held_service))
        app.add_exception_handler(ApplicationError, regression_application_error_handler)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as busy_client:
            case = held_service.create_case("busy")
            body, content_type = _comparison_form(wav, wav)
            response = await busy_client.post(
                f"/api/v1/regression/cases/{case.case_id}/comparisons",
                content=body,
                headers={"Content-Type": content_type},
            )
    finally:
        held_service._busy = False
    await held_service.aclose()
    assert response.status_code == 409
    assert parse_calls == 0


@pytest.mark.asyncio
async def test_regression_page_and_js_packaged() -> None:
    service = build_regression_service()
    app = FastAPI()
    app.include_router(build_regression_router(service))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        page = await client.get("/regression")
        assert page.status_code == 200
        assert "regression.js" in page.text
        from signal_diag.app.api import _static_asset_response

        script = _static_asset_response("regression.js")
        assert script.status_code == 200
    await service.aclose()
