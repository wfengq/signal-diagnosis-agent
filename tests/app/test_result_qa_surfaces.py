"""T-CX516: result Q&A API and Web UI (D060 C, §33). No network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_diag.agent.qa import ScriptedAnswerer
from signal_diag.app.api import create_app
from signal_diag.app.engine_service import build_engine_service
from signal_diag.app.qa_service import AnswererIdentity, QAService
from tests.app.test_api import _client
from tests.app.test_engine_service import _submit
from tests.app.test_explanation_surfaces import _sweep_wav

STATIC = Path(__file__).resolve().parents[2] / "src" / "signal_diag" / "app" / "static"


@pytest.fixture(autouse=True)
def _no_model_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNAL_DIAG_QA_MODEL", raising=False)


@pytest.mark.asyncio
async def test_t_cx516_contextual_questions_endpoint() -> None:
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        health = (await client.get("/api/v1/health")).json()
        assert health["qa"] == {
            "model_available": False,
            "prompt_version": "v0.3-s1-qa-1.1",
        }
        service = app.state.service
        submission = await _submit(service)
        await service.wait_for_contextual_terminal(submission.run_id)
        url = f"/api/v1/contextual-runs/{submission.run_id}/questions"

        plain = await client.post(url, json={"question": "结论是什么？"})
        assert plain.status_code == 200, plain.text
        body = plain.json()
        assert body["source"] == "template" and body["model_calls"] == 0
        assert not body["answer"]["declined"] and "削波" in body["lines"][0]
        declined = (
            await client.post(url, json={"question": "是不是喇叭坏了？"})
        ).json()
        assert declined["answer"]["declined"] is True

        refused = await client.post(url, json={"question": "结论？", "use_model": True})
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "planner_not_configured"
        for bad in (
            {},
            {"question": ""},
            {"question": "x" * 501},
            {"question": "x", "extra": 1},
        ):
            assert (await client.post(url, json=bad)).status_code == 422
        missing = await client.post(
            "/api/v1/contextual-runs/run_missing/questions", json={"question": "x"}
        )
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_t_cx516_sweep_questions_with_scripted_answerer() -> None:
    answerer = ScriptedAnswerer("not json")
    qa = QAService(
        answerer, identity=AnswererIdentity(provider="scripted", model="scripted")
    )
    app = create_app(service=build_engine_service(environ={}), qa_service=qa)
    async with _client(app=app) as client:
        assert (await client.get("/api/v1/health")).json()["qa"][
            "model_available"
        ] is True
        files = {"recording_1": ("a.wav", _sweep_wav(1.0), "audio/wav")}
        data = {"metadata": json.dumps({"levels": ["0 dB"]})}
        run = (await client.post("/api/v1/sweep-runs", files=files, data=data)).json()
        url = f"/api/v1/sweep-runs/{run['run_id']}/questions"
        result = (
            await client.post(url, json={"question": "为什么失真？", "use_model": True})
        ).json()
        assert (
            result["source"] == "template"
            and result["fallback_reason"] == "illegal_output"
        )
        assert (
            result["model_calls"] == 1 and result["answerer"]["provider"] == "scripted"
        )
        sent = json.loads(answerer.calls[0])
        assert set(sent) == {"language", "question", "packet"}
        assert sent["question"] == "为什么失真？"


@pytest.mark.asyncio
async def test_t_cx516_web_ui_wiring() -> None:
    script = (STATIC / "qa.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "textContent" in script
    assert (
        "health.qa" in script
        and "use_model: true" in script
        and "maxLength = 500" in script
    )
    explanation = (STATIC / "explanation.js").read_text(encoding="utf-8")
    assert "SignalQA.attach" in explanation and '"/questions"' in explanation
    for page in ("index.html", "sweep.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert html.index('src="/static/explanation.js"') < html.index(
            'src="/static/qa.js"'
        )
    assert "SignalQA.loadAvailability" in (STATIC / "app.js").read_text(
        encoding="utf-8"
    )
    assert "SignalQA.loadAvailability" in (STATIC / "sweep.js").read_text(
        encoding="utf-8"
    )
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        served = await client.get("/static/qa.js")
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("text/javascript")
