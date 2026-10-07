"""T-CX463–T-CX465: sweep test reports, CLI, API and Web UI (D054)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from signal_diag.app.api import create_app
from signal_diag.app.cli import main
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.sweep import SweepDiagnosis, diagnose_sweep
from signal_diag.app.sweep_reporting import (
    SERIES_COLORS,
    build_sweep_report,
    render_band_chart_svg,
    render_sweep_html,
    render_sweep_json,
)
from signal_diag.dsp.sweep import generate_stimulus

RATE = 48_000
CSP = "default-src 'self'; object-src 'none'; base-uri 'none'"
STATIC = Path(__file__).resolve().parents[2] / "src" / "signal_diag" / "app" / "static"


def _wav(gain: float) -> bytes:
    stimulus, _ = generate_stimulus(RATE)
    response = np.tanh(4 * gain * stimulus) / 4
    recording = np.concatenate([np.zeros(RATE // 5), response, np.zeros(RATE // 3)])
    return encode_pcm32_wav(
        recording.astype(np.float32).reshape(-1, 1), sample_rate_hz=RATE
    )


@pytest.fixture(scope="module")
def two_levels() -> SweepDiagnosis:
    return diagnose_sweep([(_wav(0.1), "<low & quiet>"), (_wav(1.5), "0 dB")])


def test_t_cx463_json_and_html_reports(two_levels: SweepDiagnosis) -> None:
    report = build_sweep_report(
        two_levels, generated_at=datetime(2026, 10, 7, tzinfo=UTC)
    )
    payload = json.loads(render_sweep_json(report))
    assert payload["report_version"] == "sweep-report-1.0"
    assert "not industry standards" in payload["threshold_notice"]
    assert payload["diagnosis"]["model_calls"] == 0
    assert payload["diagnosis"]["outcome"] == "supported_fault"

    page = render_sweep_html(report)
    assert "&lt;low &amp; quiet&gt;" in page and "<low & quiet>" not in page
    assert "5% demo limit" in page and "(order 3)" in page
    for claim in two_levels.levels[1].claims:
        for ref in claim.rule_refs:
            assert ref in page


def test_t_cx463_chart_follows_the_mark_specs(two_levels: SweepDiagnosis) -> None:
    svg = render_band_chart_svg(two_levels)
    assert svg.startswith("<svg") and "<style" not in svg and "<script" not in svg
    assert svg.count('stroke-width="2" stroke-linejoin="round"') >= 2
    assert SERIES_COLORS[0] in svg and SERIES_COLORS[1] in svg
    assert 'stroke-dasharray="4 3"' in svg and "5% demo limit" in svg
    assert 'r="12"' in svg and 'tabindex="0"' in svg
    assert "&lt;low &amp; quiet&gt;" in svg


def test_t_cx463_report_rejects_foreign_citations(two_levels: SweepDiagnosis) -> None:
    first, second = two_levels.levels
    mixed = first.model_copy(update={"claims": second.claims})
    tampered = two_levels.model_copy(update={"levels": (mixed, second)})
    with pytest.raises(ValueError, match="another run"):
        build_sweep_report(tampered, generated_at=datetime.now(UTC))


def test_t_cx464_cli_stimulus_and_diagnose(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "stimulus.wav"
    assert main(["sweep", "stimulus", "--rate", "44100", "--out", str(out)]) == 0
    assert out.read_bytes()[:4] == b"RIFF"

    low, high = tmp_path / "low.wav", tmp_path / "high.wav"
    low.write_bytes(_wav(0.1))
    high.write_bytes(_wav(1.5))
    capsys.readouterr()
    html_out = tmp_path / "report.html"
    code = main(
        [
            "sweep",
            "diagnose",
            str(low),
            str(high),
            "--level",
            "-20 dB",
            "--level",
            "0 dB",
            "--html-output",
            str(html_out),
        ]
    )
    text = capsys.readouterr().out
    assert code == 0
    assert (
        "outcome: supported_fault" in text
        and "level -20 dB: no_supported_fault" in text
    )
    assert "not industry standards" in text
    assert html_out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")

    assert main(["sweep", "diagnose", str(low), "--output", "json"]) == 0
    assert (
        json.loads(capsys.readouterr().out)["diagnosis"]["levels"][0]["level_label"]
        == "L1"
    )

    assert main(["sweep", "diagnose", str(low), "--level", "a", "--level", "b"]) == 2
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"nope")
    assert main(["sweep", "diagnose", str(bad)]) == 2


@asynccontextmanager
async def _client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.mark.asyncio
async def test_t_cx465_api_stimulus_run_and_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    async with _client() as client:
        stimulus = await client.get("/api/v1/sweep/stimulus", params={"rate": 44_100})
        assert stimulus.status_code == 200
        assert stimulus.headers["content-type"] == "audio/wav"
        assert stimulus.headers["content-security-policy"] == CSP
        assert (
            await client.get("/api/v1/sweep/stimulus", params={"rate": 32_000})
        ).status_code == 422

        files = {
            "recording_1": ("low.wav", _wav(0.1), "audio/wav"),
            "recording_2": ("high.wav", _wav(1.5), "audio/wav"),
        }
        data = {"metadata": json.dumps({"levels": ["-20 dB", "0 dB"]})}
        created = await client.post("/api/v1/sweep-runs", files=files, data=data)
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["outcome"] == "supported_fault" and body["model_calls"] == 0
        assert body["chart_svg"].startswith("<svg")
        run_id = body["run_id"]

        fetched = await client.get(f"/api/v1/sweep-runs/{run_id}")
        assert fetched.json()["run_id"] == run_id
        report_json = await client.get(f"/api/v1/sweep-runs/{run_id}/report.json")
        assert report_json.status_code == 200
        assert "attachment" in report_json.headers["content-disposition"]
        report_html = await client.get(f"/api/v1/sweep-runs/{run_id}/report.html")
        assert report_html.headers["content-type"].startswith("text/html")
        assert (
            await client.get(f"/api/v1/sweep-runs/{run_id}/report.pdf")
        ).status_code == 404
        missing = await client.get("/api/v1/sweep-runs/swrun_unknown")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "run_not_found"


@pytest.mark.asyncio
async def test_t_cx465_api_rejects_bad_uploads() -> None:
    wav = _wav(0.1)
    cases = [
        ({"recording_1": ("a.wav", wav, "audio/wav")}, {"metadata": "not json"}),
        (
            {"recording_1": ("a.wav", wav, "audio/wav")},
            {"metadata": json.dumps({"levels": ["a", "b"]})},
        ),
        (
            {"recording_2": ("a.wav", wav, "audio/wav")},
            {"metadata": json.dumps({"levels": ["a"]})},
        ),
        (
            {"recording_1": ("a.wav", wav, "audio/wav")},
            {"metadata": json.dumps({"levels": ["a"], "x": 1})},
        ),
        (
            {"other": ("a.wav", wav, "audio/wav")},
            {"metadata": json.dumps({"levels": ["a"]})},
        ),
        (
            {"recording_1": ("a.wav", b"nope", "audio/wav")},
            {"metadata": json.dumps({"levels": ["a"]})},
        ),
    ]
    async with _client() as client:
        for files, data in cases:
            response = await client.post("/api/v1/sweep-runs", files=files, data=data)
            assert response.status_code == 422, (files.keys(), data, response.text)
            assert response.headers["content-security-policy"] == CSP


@pytest.mark.asyncio
async def test_t_cx465_web_ui_page_and_assets() -> None:
    async with _client() as client:
        page = await client.get("/sweep")
        assert page.status_code == 200 and "扫频测试" in page.text
        script = await client.get("/static/sweep.js")
        assert script.status_code == 200
        assert script.headers["content-type"].startswith("text/javascript")
        index = await client.get("/")
        assert 'href="/sweep"' in index.text

    html = (STATIC / "sweep.html").read_text(encoding="utf-8")
    js = (STATIC / "sweep.js").read_text(encoding="utf-8")
    assert (
        "<style" not in html
        and "onclick" not in html
        and 'src="/static/sweep.js"' in html
    )
    assert "innerHTML" not in js and "textContent" in js
    assert "recording_" in js and '"metadata"' in js
    assert "1.0.0-demo" in html and "not industry standards" in html
