"""T-CX473–T-CX475: explanation API, CLI, reports and Web UI (D055). No network."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from signal_diag.agent.explain import ScriptedExplainer
from signal_diag.app.api import create_app
from signal_diag.app.cli import main
from signal_diag.app.engine_service import build_engine_service
from signal_diag.app.explanation_service import ExplainerIdentity, ExplanationService
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.dsp.sweep import generate_stimulus
from tests.app.test_api import _client
from tests.app.test_engine_service import _burst_wav, _submit

STATIC = Path(__file__).resolve().parents[2] / "src" / "signal_diag" / "app" / "static"
CSP = "default-src 'self'; object-src 'none'; base-uri 'none'"


def _sweep_wav(gain: float) -> bytes:
    stimulus, _ = generate_stimulus(48_000)
    response = np.tanh(4 * gain * stimulus) / 4
    recording = np.concatenate([np.zeros(9_600), response, np.zeros(14_400)])
    return encode_pcm32_wav(recording.astype(np.float32).reshape(-1, 1), sample_rate_hz=48_000)


@pytest.fixture(autouse=True)
def _no_model_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNAL_DIAG_EXPLAIN_MODEL", raising=False)


@pytest.mark.asyncio
async def test_t_cx473_contextual_explanation_endpoint_and_report() -> None:
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        health = (await client.get("/api/v1/health")).json()
        assert health["explanation"] == {
            "template_available": True,
            "model_available": False,
            "prompt_version": "v0.3-s1-explain-1.0",
        }
        service = app.state.service
        submission = await _submit(service)
        await service.wait_for_contextual_terminal(submission.run_id)
        url = f"/api/v1/contextual-runs/{submission.run_id}/explanation"

        before = await client.get(f"/api/v1/contextual-runs/{submission.run_id}/report.json")
        assert "explanation" not in before.json()

        response = await client.post(url, json={})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["source"] == "template" and body["model_calls"] == 0
        assert [s["kind"] for s in body["draft"]["sections"]] == [
            "conclusion",
            "evidence",
            "meaning",
            "next_steps",
        ]
        assert "削波" in body["draft"]["sections"][0]["sentences"][0]["text"]
        english = (await client.post(url, json={"language": "en"})).json()
        assert english["language"] == "en"

        refused = await client.post(url, json={"use_model": True})
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "planner_not_configured"
        assert (await client.post(url, json={"extra": 1})).status_code == 422
        missing = await client.post("/api/v1/contextual-runs/run_missing/explanation", json={})
        assert missing.status_code == 404

        report = await client.get(f"/api/v1/contextual-runs/{submission.run_id}/report.json")
        assert report.json()["explanation"]["language"] == "en"
        page = await client.get(f"/api/v1/contextual-runs/{submission.run_id}/report.html")
        assert '<section id="explanation">' in page.text
        assert page.headers["content-security-policy"] == CSP


@pytest.mark.asyncio
async def test_t_cx473_model_path_with_scripted_explainer() -> None:
    explainer = ScriptedExplainer("not json")
    service = ExplanationService(
        explainer, identity=ExplainerIdentity(provider="scripted", model="scripted")
    )
    app = create_app(service=build_engine_service(environ={}), explanation_service=service)
    async with _client(app=app) as client:
        assert (await client.get("/api/v1/health")).json()["explanation"]["model_available"]
        files = {"recording_1": ("a.wav", _sweep_wav(1.0), "audio/wav")}
        data = {"metadata": json.dumps({"levels": ["0 dB"]})}
        run = (await client.post("/api/v1/sweep-runs", files=files, data=data)).json()
        url = f"/api/v1/sweep-runs/{run['run_id']}/explanation"
        result = (await client.post(url, json={"use_model": True})).json()
        assert result["source"] == "template" and result["fallback_reason"] == "illegal_output"
        assert result["model_calls"] == 1 and result["explainer"]["provider"] == "scripted"
        sent = json.loads(explainer.calls[0])
        assert set(sent) == {"language", "packet", "baseline"}
        report = await client.get(f"/api/v1/sweep-runs/{run['run_id']}/report.json")
        assert report.json()["explanation"]["fallback_reason"] == "illegal_output"
        html = await client.get(f"/api/v1/sweep-runs/{run['run_id']}/report.html")
        assert "AI 改写未采用" in html.text


def test_t_cx474_cli_explain_flags(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    burst = tmp_path / "burst.wav"
    burst.write_bytes(_burst_wav())
    code = main(
        ["diagnose", "contextual", str(burst), "--mode", "single_signal", "--explain", "template"]
    )
    out = capsys.readouterr().out
    assert code == 0 and "模板解释" in out and "结论:" in out

    html_out = tmp_path / "report.html"
    code = main(
        [
            "diagnose", "contextual", str(burst), "--mode", "single_signal",
            "--explain", "template", "--explain-language", "en",
            "--output", "json", "--html-output", str(html_out),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0 and payload["explanation"]["language"] == "en"
    assert '<section id="explanation">' in html_out.read_text(encoding="utf-8")

    code = main(["diagnose", "contextual", str(burst), "--mode", "single_signal", "--explain", "model"])
    assert code == 2 and "planner_not_configured" in capsys.readouterr().err

    sweep = tmp_path / "sweep.wav"
    sweep.write_bytes(_sweep_wav(1.0))
    assert main(["sweep", "diagnose", str(sweep), "--explain", "template"]) == 0
    assert "下一步:" in capsys.readouterr().out
    assert main(["sweep", "diagnose", str(sweep), "--explain", "model"]) == 2
    plain = main(["sweep", "diagnose", str(sweep)])
    assert plain == 0 and "模板解释" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_t_cx475_web_ui_wiring() -> None:
    script = (STATIC / "explanation.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "textContent" in script
    assert "model_available" in script and "use_model" in script
    for page, prefix in (("index.html", "explanation"), ("sweep.html", "sweep-explanation")):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert 'src="/static/explanation.js"' in html
        assert f'id="{prefix}-model" type="button" hidden' in html
        assert f'id="{prefix}-panel" hidden' in html
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "SignalExplanation.show" in app_js and "/explanation" in app_js
    sweep_js = (STATIC / "sweep.js").read_text(encoding="utf-8")
    assert "SignalExplanation.show" in sweep_js
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        served = await client.get("/static/explanation.js")
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("text/javascript")
