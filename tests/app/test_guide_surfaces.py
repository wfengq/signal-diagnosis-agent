"""T-CX490–T-CX492: test guide API, CLI and Web UI (D057). No network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_diag.agent.guide import ScriptedGuide
from signal_diag.app.api import create_app
from signal_diag.app.cli import main
from signal_diag.app.engine_service import build_engine_service
from signal_diag.app.guide_service import GuideIdentity, GuideService
from tests.app.test_api import _client
from tests.app.test_engine_service import _submit
from tests.app.test_explanation_surfaces import _sweep_wav

STATIC = Path(__file__).resolve().parents[2] / "src" / "signal_diag" / "app" / "static"
GOOD = {
    "plan_id": "sweep_levels",
    "parameters": {
        "sample_rate_hz": 48000,
        "level_labels": ["低于平时", "平时音量", "出问题的音量"],
        "connection": "acoustic_mic",
        "defaults": ["sample_rate_hz", "level_labels"],
    },
    "rationale_quotes": ["一开大声就破音"],
}


@pytest.fixture(autouse=True)
def _no_model_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNAL_DIAG_GUIDE_MODEL", raising=False)
    monkeypatch.delenv("SIGNAL_DIAG_EXPLAIN_MODEL", raising=False)


@pytest.mark.asyncio
async def test_t_cx490_api_draft_confirm_link_and_report() -> None:
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        health = (await client.get("/api/v1/health")).json()
        assert health["guide"] == {
            "questionnaire_available": True,
            "model_available": False,
            "prompt_version": "v0.3-s1-guide-1.0",
        }
        draft = (await client.post("/api/v1/test-plans/draft", json={"text": "音箱破音"})).json()
        assert draft["source"] == "questionnaire" and draft["questionnaire"][0]["question_id"] == "can_replay"
        refused = await client.post("/api/v1/test-plans/draft", json={"text": "x", "use_model": True})
        assert refused.status_code == 503 and refused.json()["error"]["code"] == "planner_not_configured"
        answers = {"can_replay": "yes", "connection": "line_loopback"}
        planned = (await client.post("/api/v1/test-plans/questionnaire", json={"answers": answers})).json()
        assert planned["plan_id"] == "sweep_levels"
        bad = await client.post("/api/v1/test-plans/questionnaire", json={"answers": {"can_replay": "x"}})
        assert bad.status_code == 422
        confirm_body = {
            "plan_id": "sweep_levels",
            "source": "questionnaire",
            "sample_rate_hz": 48000,
            "level_labels": ["0 dB"],
            "connection": "line_loopback",
        }
        record = (await client.post("/api/v1/test-plans/confirm", json=confirm_body)).json()
        key = record["plan_key"]
        assert record["next_page"] == f"/sweep?plan={key}" and len(record["steps"]) == 5
        assert (await client.get(f"/api/v1/test-plans/{key}")).json() == record
        assert (await client.get("/api/v1/test-plans/plan_missing")).status_code == 404
        unconfirmed = await client.post("/api/v1/test-plans/confirm", json={"plan_id": "sweep_levels", "source": "model"})
        assert unconfirmed.status_code == 422

        files = {"recording_1": ("a.wav", _sweep_wav(1.0), "audio/wav")}
        data = {"metadata": json.dumps({"levels": ["0 dB"]})}
        run = (await client.post("/api/v1/sweep-runs", files=files, data=data)).json()
        before = await client.get(f"/api/v1/sweep-runs/{run['run_id']}/report.json")
        assert "test_plan" not in before.json()
        linked = await client.post(f"/api/v1/test-plans/{key}/runs", json={"run_id": run["run_id"]})
        assert linked.status_code == 200
        report = (await client.get(f"/api/v1/sweep-runs/{run['run_id']}/report.json")).json()
        assert report["test_plan"]["plan_key"] == key
        page = await client.get(f"/api/v1/sweep-runs/{run['run_id']}/report.html")
        assert '<section id="test-plan">' in page.text
        missing_run = await client.post(f"/api/v1/test-plans/{key}/runs", json={"run_id": "swrun_nope"})
        assert missing_run.status_code == 404

        submission = await _submit(app.state.service)
        await app.state.service.wait_for_contextual_terminal(submission.run_id)
        existing = (
            await client.post(
                "/api/v1/test-plans/confirm",
                json={"plan_id": "existing_recording", "source": "questionnaire"},
            )
        ).json()
        await client.post(f"/api/v1/test-plans/{existing['plan_key']}/runs", json={"run_id": submission.run_id})
        contextual = await client.get(f"/api/v1/contextual-runs/{submission.run_id}/report.json")
        assert contextual.json()["test_plan"]["plan_id"] == "existing_recording"


@pytest.mark.asyncio
async def test_t_cx490_model_draft_through_the_api() -> None:
    guide = GuideService(
        ScriptedGuide(json.dumps(GOOD, ensure_ascii=False)),
        identity=GuideIdentity(provider="scripted", model="s"),
    )
    app = create_app(service=build_engine_service(environ={}), guide_service=guide)
    async with _client(app=app) as client:
        assert (await client.get("/api/v1/health")).json()["guide"]["model_available"]
        body = {"text": "我的音箱一开大声就破音", "use_model": True}
        result = (await client.post("/api/v1/test-plans/draft", json=body)).json()
        assert result["source"] == "model" and result["draft"]["plan_id"] == "sweep_levels"
        quoteless = {"text": "音箱坏了", "use_model": True}
        fallback = (await client.post("/api/v1/test-plans/draft", json=quoteless)).json()
        assert fallback["source"] == "questionnaire"
        assert fallback["fallback_reason"] == "validation_failed:quote"


def test_t_cx491_cli_guide(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide", "draft", "音箱一开大声就破音"]) == 0
    assert "can_replay" in capsys.readouterr().out
    assert main(["guide", "draft", "x", "--model"]) == 2
    assert "planner_not_configured" in capsys.readouterr().err
    assert main(["guide", "questionnaire", "--answer", "can_replay=no", "--answer", "has_reference=yes"]) == 0
    assert '"paired_reference"' in capsys.readouterr().out
    code = main(
        ["guide", "confirm", "--plan", "sweep_levels", "--rate", "44100",
         "--level", "-20 dB", "--level", "0 dB", "--connection", "acoustic_mic"]
    )
    out = capsys.readouterr().out
    assert code == 0 and "44100 Hz" in out and "next page: /sweep?plan=plan_" in out
    assert main(["guide", "confirm", "--plan", "sweep_levels"]) == 2
    assert main(["guide", "confirm", "--plan", "nominal_tone", "--nominal-hz", "1000"]) == 0
    assert "1000 Hz" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_t_cx492_web_ui_wiring() -> None:
    script = (STATIC / "guide.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "textContent" in script
    assert "model_available" in script and "/api/v1/test-plans/confirm" in script
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="guide-model" type="button" hidden' in index and 'id="guide-start"' in index
    assert 'src="/static/guide.js"' in index and 'id="plan-banner" hidden' in index
    sweep = (STATIC / "sweep.html").read_text(encoding="utf-8")
    assert 'src="/static/guide.js"' in sweep and 'id="plan-banner" hidden' in sweep
    assert "SignalGuide.linkRun" in (STATIC / "sweep.js").read_text(encoding="utf-8")
    assert "SignalGuide.linkRun" in (STATIC / "app.js").read_text(encoding="utf-8")
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        served = await client.get("/static/guide.js")
        assert served.status_code == 200 and served.headers["content-type"].startswith("text/javascript")
