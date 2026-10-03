"""Checkpoint AB — packaged native Web UI (T276–T280)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from importlib.resources import files
from pathlib import Path

import pytest

from signal_diag.app.models import AcceptedEvaluationSummary
from signal_diag.app.reporting import load_accepted_evaluation_summary
from signal_diag.app.service import DiagnosisApplicationService
from tests.app.test_api import (
    PRESET_IDS,
    QUESTION,
    _client,
    _ImmediateFinishPlanner,
    _make_service,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "src" / "signal_diag" / "app" / "static"
APP_API = PROJECT_ROOT / "src" / "signal_diag" / "app" / "api.py"
SECTION_IDS = (
    "input-panel",
    "lifecycle-panel",
    "diagnosis-panel",
    "declaration-panel",
    "qualification-panel",
    "limitation-panel",
    "waveform-panel",
    "trace-panel",
    "evidence-panel",
    "rules-panel",
    "knowledge-panel",
    "evaluation-panel",
)
FORBIDDEN_HTML_SINKS = (
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
)
FORBIDDEN_TOOL_NAMES = (
    "detect_clipping",
    "analyze_spectrum",
    "estimate_fundamental",
    "analyze_harmonic_distortion",
)
CDN_MARKERS = (
    "cdn.",
    "unpkg",
    "jsdelivr",
    "googleapis",
    "google-analytics",
    "googletagmanager",
    "cdnjs",
)
FRAMEWORK_MARKERS = (
    "react",
    "preact",
    "angular",
    "jquery",
    "svelte",
    "webpack",
    "vite",
    "node_modules",
)


def _static_text(name: str) -> str:
    path = STATIC_DIR / name
    assert path.is_file(), f"missing packaged asset {name}"
    return path.read_text(encoding="utf-8")


def _function_body(script: str, name: str) -> str:
    marker = f"function {name}"
    start = script.index(marker)
    rest = script[start + len(marker) :]
    nxt = rest.find("\nfunction ")
    return script[start:] if nxt < 0 else script[start : start + len(marker) + nxt]


def _honest_evaluation_copy(summary: AcceptedEvaluationSummary) -> str:
    return "\n".join(
        (
            f"{summary.benchmark_status}/{summary.target_status}",
            f"{summary.agent_slot_count} held-out Agent slots",
            f"{summary.behavioral_failure_slot_count}/{summary.agent_slot_count}",
            f"{summary.outcome_error_slot_count}/{summary.agent_slot_count}",
            summary.disclaimer.replace("_", " "),
        )
    )


@pytest.fixture
async def finish_service() -> AsyncIterator[DiagnosisApplicationService]:
    service = _make_service(lambda: _ImmediateFinishPlanner())
    try:
        yield service
    finally:
        await service.aclose()


def test_t276_packaged_no_build_ui_has_native_assets_only() -> None:
    html = _static_text("index.html")
    css = _static_text("styles.css")
    script = _static_text("app.js")
    page = f"{html}\n{css}\n{script}".casefold()

    assert "<!doctype html>" in html.casefold()
    assert 'href="/static/styles.css"' in html
    assert 'src="/static/app.js"' in html
    assert "package.json" not in page
    assert "webpack" not in page
    assert "vite" not in page
    assert "node_modules" not in page
    for marker in CDN_MARKERS:
        assert marker not in page
    assert "https://" not in html.casefold()
    assert "http://" not in html.casefold()
    assert 'type="password"' not in html.casefold()
    assert "api_key" not in page
    assert "api-key" not in page
    assert "authorization" not in page
    assert "gtag(" not in page
    assert "analytics" not in page
    for marker in FRAMEWORK_MARKERS:
        assert marker not in page
    assert not re.search(r"\son[a-z]+\s*=", html, flags=re.IGNORECASE)

    packaged = files("signal_diag.app.static")
    assert packaged.joinpath("index.html").read_text(encoding="utf-8") == html
    assert packaged.joinpath("styles.css").read_text(encoding="utf-8") == css
    assert packaged.joinpath("app.js").read_text(encoding="utf-8") == script

    api_source = APP_API.read_text(encoding="utf-8")
    assert 'files("signal_diag.app.static")' in api_source
    assert "StaticFiles" not in api_source


def test_t277_complete_interaction_surface() -> None:
    html = _static_text("index.html")
    script = _static_text("app.js")
    css = _static_text("styles.css")

    assert '<main>' in html
    assert 'id="input-panel" aria-labelledby="input-heading"' in html
    assert 'id="lifecycle-panel" aria-live="polite"' in html
    for section_id in SECTION_IDS:
        assert f'id="{section_id}"' in html

    assert 'id="source-mode-wav"' in html
    assert 'id="source-mode-preset"' in html
    assert 'id="wav-file"' in html
    assert 'accept=".wav' in html.casefold() or 'accept="audio/wav' in html.casefold()
    assert 'id="preset-id"' in html
    assert 'id="question"' in html
    assert QUESTION in html
    assert 'id="channel"' in html
    assert 'value="left"' in html
    assert 'value="right"' in html
    assert 'value="mixdown"' in html
    assert 'id="submit-run"' in html
    assert 'id="report-json"' in html
    assert 'id="report-html"' in html
    assert "local single-user/no-auth" in html
    assert "demonstration" in html.casefold()
    assert "1%" in html or "1% clipping" in html
    assert "5%" in html or "5% THD" in html.casefold()
    for control_id in (
        "source-mode-wav",
        "source-mode-preset",
        "wav-file",
        "preset-id",
        "question",
        "channel",
        "submit-run",
    ):
        assert f'for="{control_id}"' in html or f'id="{control_id}"' in html

    assert "function appendText" in script
    assert "async function pollRun" in script
    assert "function renderLifecycle" in script
    assert "function renderTerminal" in script
    assert "/api/v1/contextual-runs/wav" in script
    assert "/api/v1/presets/" in script and "/wav" in script
    assert "/api/v1/runs/synthetic" not in script
    assert "/api/v1/runs/" in script or "/api/v1/contextual-runs/" in script
    assert "/report.json" in script
    assert "/report.html" in script
    assert "/api/v1/presets" in script
    assert "createElementNS" in script
    assert "http://www.w3.org/2000/svg" in script
    assert "window.setTimeout(resolve, 500)" in script
    assert 'fetch("http' not in script
    assert "fetch('http" not in script
    assert "@media" in css


@pytest.mark.asyncio
async def test_t277_ui_api_paths_complete_a_scripted_run(
    finish_service: DiagnosisApplicationService,
) -> None:
    """UI product path uses contextual preset WAV; V0.2 synthetic remains on server."""
    from signal_diag.app.presets import render_demo_preset_wav
    from tests.app.test_api import _contextual_wav_form

    async with _client(finish_service) as client:
        root = await client.get("/")
        assert root.status_code == 200
        assert "text/html" in root.headers["content-type"]
        assert root.content == (STATIC_DIR / "index.html").read_bytes()

        presets = await client.get("/api/v1/presets")
        assert [item["preset_id"] for item in presets.json()] == list(PRESET_IDS)

        wav_response = await client.get("/api/v1/presets/clipping/wav")
        assert wav_response.status_code == 200
        assert wav_response.content == render_demo_preset_wav("clipping")

        body, content_type = _contextual_wav_form(
            wav_response.content,
            mode="single_signal",
            filename="input.wav",
        )
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
        payload = polled.json()
        assert payload["status"] == "completed"
        assert payload["result"] is not None
        assert "observations" in payload["result"]
        assert "evidence" in payload["result"]
        assert "rule_evaluation_batches" in payload["result"]
        assert "knowledge_retrievals" in payload["result"]
        assert payload["trace_events"] is not None
        assert payload["test_preview"]["points"] is not None
        json_report = await client.get(
            f"/api/v1/contextual-runs/{run_id}/report.json"
        )
        html_report = await client.get(
            f"/api/v1/contextual-runs/{run_id}/report.html"
        )
        assert json_report.status_code == 200
        assert html_report.status_code == 200
        assert terminal.status == "completed"

        # Frozen V0.2 synthetic route remains available for non-UI clients.
        legacy = await client.post(
            "/api/v1/runs/synthetic",
            json={
                "preset_id": "clipping",
                "user_request": QUESTION,
                "channel": "mixdown",
            },
        )
        assert legacy.status_code == 202


def test_t278_external_text_never_uses_html_sinks() -> None:
    script = _static_text("app.js")
    forbidden = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write")
    assert all(token not in script for token in forbidden)
    assert "textContent" in script


def test_t278_queued_running_never_fabricates_tool_progress() -> None:
    script = _static_text("app.js")
    html = _static_text("index.html")
    lifecycle = _function_body(script, "renderLifecycle")
    poll = _function_body(script, "pollRun")
    for name in FORBIDDEN_TOOL_NAMES:
        assert name not in lifecycle
        assert name not in poll
        assert name not in html
    assert "queued" in lifecycle
    assert "running" in lifecycle
    assert "elapsed" in lifecycle
    assert "calling" not in lifecycle.casefold()
    assert "progress %" not in lifecycle.casefold()
    assert "createTextNode" in script or "textContent" in script
    for sink in FORBIDDEN_HTML_SINKS:
        assert sink not in script


def test_t279_ui_loads_frozen_accepted_evaluation_summary() -> None:
    summary = load_accepted_evaluation_summary()
    packaged = files("signal_diag.evaluation.assets").joinpath(
        "phase4_3_1_official_summary.json"
    )
    loaded = AcceptedEvaluationSummary.model_validate_json(
        packaged.read_text(encoding="utf-8")
    )
    assert loaded == summary
    assert summary.benchmark_id == "bench_official_s1_v12_planner8_1_gate5"
    assert summary.dataset_id == "s1-distortion-synthetic"
    assert summary.dataset_version == "1.2.0"
    assert summary.provider == "deepseek"
    assert summary.model == "deepseek-v4-flash"
    assert summary.prompt_version == "v0.2-s1-planner-8.1"
    assert summary.rule_profile_id == "profile_s1_distortion"
    assert summary.rule_profile_version == "1.0.0-demo"
    assert summary.benchmark_status == "completed"
    assert summary.target_status == "meets_target"
    assert summary.agent_slot_count == 80
    assert summary.behavioral_failure_slot_count == 2
    assert summary.outcome_error_slot_count == 1
    assert set(summary.source_checksums_sha256) == {
        "benchmark_manifest.json",
        "case_summary.csv",
        "metrics.json",
        "report.md",
        "runs.jsonl",
    }

    script = _static_text("app.js")
    assert "/api/v1/evaluation-summary" in script
    assert "benchmark_status" in script
    assert "target_status" in script
    assert "agent_slot_count" in script
    assert "behavioral_failure_slot_count" in script
    assert "outcome_error_slot_count" in script
    assert "agent_metrics" in script
    assert "baseline_metrics" in script
    assert "targets" in script
    assert "disclaimer" in script


def test_t280_honest_evaluation_panel_after_loading_summary() -> None:
    summary = load_accepted_evaluation_summary()
    copy = _honest_evaluation_copy(summary)
    assert "completed/meets_target" in copy
    assert "80" in copy
    assert "2/80" in copy
    assert "1/80" in copy
    assert "demonstration" in copy
    assert "held-out Agent slots" in copy

    script = _static_text("app.js")
    html = _static_text("index.html")
    assert 'id="evaluation-panel"' in html
    assert "${summary.benchmark_status}/${summary.target_status}" in script
    assert "${summary.agent_slot_count}" in script
    assert (
        "${summary.behavioral_failure_slot_count}/${summary.agent_slot_count}" in script
    )
    assert "${summary.outcome_error_slot_count}/${summary.agent_slot_count}" in script
    assert "held-out Agent slots" in script
    assert "demonstration" in f"{html}\n{script}".casefold()
    assert "behavioral-failure" in script.casefold() or "behavioral failure" in script
    assert "outcome error" in script.casefold()
    assert "causal_macro_f1" in script
    assert "baseline_metrics" in script
    assert "meets_target" in copy


@pytest.mark.asyncio
async def test_t280_evaluation_summary_endpoint_matches_packaged_copy() -> None:
    async with _client() as client:
        response = await client.get("/api/v1/evaluation-summary")
        assert response.status_code == 200
        loaded = AcceptedEvaluationSummary.model_validate(response.json())
        assert loaded == load_accepted_evaluation_summary()
        copy = _honest_evaluation_copy(loaded)
        assert "completed/meets_target" in copy
        assert "80" in copy
        assert "2/80" in copy
        assert "1/80" in copy
        assert "demonstration" in copy


def test_t_cx117_contextual_ui_accessibility_labels() -> None:
    html = _static_text("index.html")
    assert 'id="diagnostic-mode"' in html
    assert 'for="diagnostic-mode"' in html
    assert 'id="nominal-fundamental-hz"' in html
    assert 'for="nominal-fundamental-hz"' in html
    assert 'id="reference-file"' in html
    assert 'for="reference-file"' in html
    assert 'id="guidance-panel"' in html
    assert "single_signal" in html or "unknown" in html.casefold()
    assert "single tone" in html.casefold() or "nominal" in html.casefold()
    assert "reference" in html.casefold()
    assert 'id="declaration-panel"' in html
    assert 'id="qualification-panel"' in html
    assert 'id="limitation-panel"' in html
    for section_id in (
        "declaration-panel",
        "qualification-panel",
        "limitation-panel",
        "guidance-panel",
    ):
        assert f'id="{section_id}"' in html


def test_t_cx118_contextual_ui_conditional_visibility() -> None:
    html = _static_text("index.html")
    script = _static_text("app.js")
    css = _static_text("styles.css")
    assert 'id="nominal-fields"' in html
    assert 'id="reference-fields"' in html
    assert "nominal-fields" in script
    assert "reference-fields" in script
    assert "diagnostic-mode" in script
    assert "hidden" in script or "display" in css
    assert "nominal_single_tone" in script or "single_tone" in script
    assert "paired_reference" in script
    # Default one-WAV experience uses contextual single_signal.
    assert 'value="single_signal"' in html
    assert "selected" in html or "checked" in html


def test_t_cx119_contextual_ui_sections_and_no_client_dsp() -> None:
    html = _static_text("index.html")
    script = _static_text("app.js")
    page = f"{html}\n{script}".casefold()
    assert "declaration-panel" in html
    assert "guidance-panel" in html
    assert "qualification-panel" in html
    assert "limitation-panel" in html
    assert "evidence-panel" in html
    assert html.index('id="declaration-panel"') != html.index('id="evidence-panel"')
    assert html.index('id="qualification-panel"') != html.index('id="evidence-panel"')
    assert html.index('id="limitation-panel"') != html.index('id="evidence-panel"')
    assert "/api/v1/contextual-runs/wav" in script
    assert "/api/v1/contextual-runs/" in script
    assert 'mode", diagnosticMode' in script or "mode\", diagnosticMode" in script
    assert "single_signal" in script
    assert "context_guidance" in script
    for token in (
        "fft",
        "numpy",
        "thd_percent",
        "analyze_contextual_distortion",
        "detect_clipping",
        "math.sin",
        "audiocontext",
    ):
        assert token not in page
    for sink in FORBIDDEN_HTML_SINKS:
        assert sink not in script


def test_t_cx327_ui_surfaces_planner_health_readiness() -> None:
    script = _static_text("app.js")
    assert "/api/v1/health" in script
    assert "planner_configured" in script
    assert "loadPlannerHealth" in script
    assert "submit-run" in script
    assert "setSubmitRunEnabled" in script
    assert "plannerHealthAllowsSubmit" in script
    assert "DEEPSEEK_" in script and "API" in script and "_KEY" in script
    assert "ScriptedPlanner" in script
    assert "planner_identity" in script
    assert "bindUi" in script
    assert "loadPresets" in script
    assert "thd_percent" not in script


def test_t_cx326_ui_lists_observed_facts_inside_guidance() -> None:
    script = _static_text("app.js")
    html = _static_text("index.html")
    assert "renderGuidance" in script
    assert "guidance-panel" in html
    assert "observed_facts" in script
    assert "observed-facts" in script
    assert "thd_percent" not in script


def test_t_cx328_ui_humanizes_context_guidance_labels() -> None:
    script = _static_text("app.js")
    html = _static_text("index.html")
    guidance = _function_body(script, "renderGuidance")
    assert "Unknown one-WAV signal" in script
    assert "Declared single tone" in script
    assert "Compare with clean reference" in script
    assert "Unknown one-WAV signal" in html
    assert "Optional upgrades:" in guidance
    assert "unlockable_modes:" not in guidance
    assert "reason_codes:" not in guidance
    assert "reference WAV" in script
    assert "nominal fundamental (Hz)" in script
    assert "stimulus kind single tone" in script
    assert "observed_facts" in guidance
    assert "thd_percent" not in script


def test_t_cx268_ui_unknown_wav_uses_contextual_single_signal() -> None:
    html = _static_text("index.html")
    script = _static_text("app.js")
    assert 'value="single_signal"' in html
    assert "selected" in html
    assert "/api/v1/contextual-runs/wav" in script
    assert 'body.append("mode", diagnosticMode)' in script
    assert "single_signal" in script
    assert "/api/v1/runs/synthetic" not in script
    assert script.count("/api/v1/runs/wav") == 0
    assert "renderGuidance" in script
    assert "guidance-panel" in html
    assert "context_guidance" in script


def test_t_cx275_ui_preset_wav_held_bytes_upgrade_controls() -> None:
    html = _static_text("index.html")
    script = _static_text("app.js")
    assert "/api/v1/presets/" in script
    assert "/wav" in script
    assert "fetchPresetWavBlob" in script
    assert 'filename", "input.wav"' in script or "input.wav" in script
    assert "/api/v1/contextual-runs/wav" in script
    assert "/api/v1/runs/synthetic" not in script
    assert "heldTestSignal" in script
    assert "rememberHeldTestSignal" in script
    assert 'id="upgrade-controls"' in html
    assert 'id="upgrade-reference-file"' in html
    assert 'id="upgrade-nominal-hz"' in html
    assert 'id="upgrade-paired"' in html
    assert 'id="upgrade-nominal"' in html
    assert "submitUpgradePaired" in script
    assert "submitUpgradeNominal" in script
    assert "paired_reference" in script
    assert "nominal_single_tone" in script
    assert "clean_periodic" not in _function_body(script, "submitUpgradePaired")
    assert "fundamental_frequency_hz" not in script
    assert "test_f0_hz" not in _function_body(script, "submitUpgradeNominal")
    for sink in FORBIDDEN_HTML_SINKS:
        assert sink not in script
