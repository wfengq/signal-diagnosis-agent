"""T-CX453–T-CX455: the engine as the product default (D053, §28)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.agent.engine import ENGINE_VERSION
from signal_diag.agent.planner import RealLLMPlanner
from signal_diag.app.api import create_app
from signal_diag.app.cli import main
from signal_diag.app.composition import build_engine_service, build_product_service
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    dump_contextual_snapshot,
    render_contextual_report_html,
    render_contextual_report_json,
)
from signal_diag.app.errors import InvalidRequestError, PlannerNotConfiguredError
from signal_diag.app.pcm_wav import encode_pcm32_wav
from tests.app.test_api import _client

ROOT = Path(__file__).resolve().parents[2]
QUESTION = "Why does this signal sound distorted?"


def _burst_wav() -> bytes:
    rate = 8_000
    t = np.arange(2 * rate) / rate
    samples = 0.3 * np.sin(2 * np.pi * 440.0 * t)
    burst = np.clip(0.9 * np.sin(2 * np.pi * 440.0 * t), -0.4, 0.4)
    samples[rate : rate + rate // 2] = burst[rate : rate + rate // 2]
    return encode_pcm32_wav(samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=rate)


async def _submit(service: Any, **kwargs: Any) -> Any:
    return await service.submit_contextual_wav(
        _burst_wav(),
        test_filename="burst.wav",
        mode="single_signal",
        reference_data=None,
        reference_filename=None,
        nominal_fundamental_hz=None,
        stimulus_kind=None,
        user_request=QUESTION,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_t_cx453_engine_service_diagnoses_without_credentials() -> None:
    service = build_engine_service(environ={})
    try:
        submission = await _submit(service)
        snapshot = await service.wait_for_contextual_terminal(submission.run_id)
        assert snapshot.status == "completed"
        assert snapshot.result is not None and snapshot.result.diagnosis is not None
        assert snapshot.result.diagnosis.outcome == "supported_fault"
        assert {claim.fault_type for claim in snapshot.result.diagnosis.claims} == {"clipping"}
        with pytest.raises(PlannerNotConfiguredError):
            await _submit(service, diagnosis_path="planner")
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t_cx453_planner_path_is_explicit_and_product_builder_unchanged() -> None:
    engine = build_engine_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
    dependencies = engine._dependencies
    assert dependencies.default_diagnosis_path == "engine"
    assert dependencies.engine_factory is not None
    assert isinstance(dependencies.planner_factory(), RealLLMPlanner)
    await engine.aclose()

    product = build_product_service(environ={})
    assert product._dependencies.default_diagnosis_path == "planner"
    assert product._dependencies.engine_factory is None
    with pytest.raises(PlannerNotConfiguredError):
        await _submit(product)
    with pytest.raises(InvalidRequestError):
        await _submit(product, diagnosis_path="engine")
    await product.aclose()


@pytest.mark.asyncio
async def test_t_cx454_identity_in_snapshot_report_and_html() -> None:
    service = build_engine_service(environ={})
    try:
        submission = await _submit(service)
        snapshot = await service.wait_for_contextual_terminal(submission.run_id)
    finally:
        await service.aclose()
    assert snapshot.planner_identity is None
    identity = snapshot.diagnosis_identity
    assert identity is not None
    assert identity.kind == "deterministic_engine"
    assert identity.engine_version == ENGINE_VERSION
    assert identity.rule_profiles == ("profile_s1_distortion",)
    dumped = dump_contextual_snapshot(snapshot)
    assert "planner_identity" not in dumped
    assert dumped["diagnosis_identity"]["engine_version"] == ENGINE_VERSION
    report = build_contextual_diagnosis_report(
        snapshot, generated_at=snapshot.finished_at  # type: ignore[arg-type]
    )
    payload = json.loads(render_contextual_report_json(report))
    assert "planner_identity" not in payload
    assert payload["diagnosis_identity"]["kind"] == "deterministic_engine"
    html = render_contextual_report_html(report)
    assert 'id="diagnosis-engine"' in html
    assert 'id="planner"' not in html
    assert ENGINE_VERSION in html


def test_t_cx454_cli_defaults_to_the_engine(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    wav = tmp_path / "burst.wav"
    wav.write_bytes(_burst_wav())
    code = main(["diagnose", "contextual", str(wav), "--mode", "single_signal"])
    out = capsys.readouterr().out
    assert code == 0
    assert f"diagnosis: deterministic engine {ENGINE_VERSION}" in out
    assert "outcome: supported_fault" in out

    code = main(
        [
            "diagnose",
            "contextual",
            str(wav),
            "--mode",
            "single_signal",
            "--diagnosis-path",
            "planner",
        ]
    )
    assert code != 0


@pytest.mark.asyncio
async def test_t_cx454_health_keeps_t264_fields_and_adds_the_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    async with _client(app=create_app()) as client:
        body = (await client.get("/api/v1/health")).json()
    assert body["planner_configured"] is False
    assert body["planner_identity"]["prompt_version"]
    assert body["diagnosis_engine"] == {
        "available": True,
        "engine_version": ENGINE_VERSION,
        "default_path": "engine",
    }


def test_t_cx455_page_allows_diagnosis_without_credentials() -> None:
    script = (ROOT / "src/signal_diag/app/static/app.js").read_text(encoding="utf-8")
    assert "health.diagnosis_engine" in script
    assert 'engine.default_path === "engine"' in script
    assert "intakeDraftAvailable = Boolean(health.planner_configured)" in script
    assert "draftButton.disabled = !intakeDraftAvailable" in script
    assert "诊断依据" in script
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert sink not in script
