"""T-CX498–T-CX501: guide prompt 1.1, rejection records and held-out scenarios (D059). No network."""

from __future__ import annotations

import asyncio
import collections
import hashlib
import json
from pathlib import Path

from signal_diag.agent.guide import GUIDE_PROMPT_VERSION, SYSTEM_PROMPT, ScriptedGuide
from signal_diag.app.guide_eval import load_cases, oracle_draft, request_for, run
from signal_diag.app.guide_service import (
    GuideIdentity,
    GuideRejection,
    GuideService,
    guide_payload,
)
from signal_diag.app.test_plan import GuideRequest, validate_plan_draft

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "src" / "signal_diag" / "evaluation" / "assets" / "guide_cases_heldout.json"
FROZEN = ROOT / "docs" / "evaluations" / "v0_3" / "guide" / "heldout" / "guide_cases_heldout.json"
HELDOUT_SHA256 = "0d12418f9acd2398dc8a2c6b3b287d0c96959b0a078bbe658f3750a019cb9507"
SCRIPTED = GuideIdentity(provider="scripted", model="s")
REQUEST = GuideRequest(text="我的音箱一开大声就破音，可以用声卡录，采样率 48 kHz。", filenames=())
GOOD = {
    "plan_id": "sweep_levels",
    "parameters": {
        "sample_rate_hz": 48000,
        "level_labels": ["低于平时", "平时音量", "出问题的音量"],
        "connection": "line_loopback",
        "defaults": ["level_labels"],
    },
    "rationale_quotes": ["一开大声就破音"],
}


def test_t_cx498_prompt_1_1_states_each_rule() -> None:
    assert GUIDE_PROMPT_VERSION == "v0.3-s1-guide-1.1"
    for phrase in (
        "the tool generates the test signal",
        "never ask for a test file",
        "only for sweep_levels, the rate the test signal is generated at",
        "read from the file",
        '"line_loopback" when the device output is cabled',
        '"acoustic_mic" when a microphone',
        '"digital_capture" when the device records its own output',
        "never fill the connection as a default",
        "reference_file is the normal, original or unprocessed recording",
        "missing_fields lists only parameters the chosen plan uses",
        "existing_recording uses test_file",
        "with no other text",
        "parameters has exactly these keys",
        "Never invent a number",
        "Never mention standards, thresholds, percentages or pass/fail",
    ):
        assert phrase in SYSTEM_PROMPT, phrase
    assert set(json.loads(guide_payload(REQUEST))) == {"text", "filenames", "sample_rates_hz"}


def _service(reply: str, seen: list[GuideRejection]) -> GuideService:
    return GuideService(ScriptedGuide(reply), identity=SCRIPTED, rejection_sink=seen.append)


def test_t_cx499_rejection_sink_records_check_detail_and_text() -> None:
    seen: list[GuideRejection] = []
    asyncio.run(_service("not json", seen).draft(REQUEST, use_model=True))
    (illegal,) = seen
    assert illegal.check == "illegal_output" and illegal.raw == "not json" and illegal.detail

    seen.clear()
    extra = json.dumps({**GOOD, "parameters": {**GOOD["parameters"], "file": "x.wav"}}, ensure_ascii=False)
    result = asyncio.run(_service(extra, seen).draft(REQUEST, use_model=True))
    assert result.fallback_reason == "illegal_output"
    (rejection,) = seen
    assert rejection.detail.startswith("parameters.file:") and rejection.raw == extra

    seen.clear()
    unquoted = json.dumps({**GOOD, "rationale_quotes": ["不在原文里"]}, ensure_ascii=False)
    result = asyncio.run(_service(unquoted, seen).draft(REQUEST, use_model=True))
    assert result.fallback_reason == "validation_failed:quote"
    assert [(r.check, r.raw) for r in seen] == [("quote", unquoted)] and seen[0].detail

    seen.clear()
    good = _service(json.dumps(GOOD, ensure_ascii=False), seen)
    assert asyncio.run(good.draft(REQUEST, use_model=True)).source == "model"
    assert asyncio.run(good.draft(REQUEST)).source == "questionnaire"
    assert seen == []
    payload = json.dumps(asyncio.run(_service("not json", seen).draft(REQUEST, use_model=True)).model_dump())
    assert "rejection" not in payload and "not json" not in payload
    sinked = GuideService(ScriptedGuide("not json"), identity=SCRIPTED).with_rejection_sink(seen.append)
    assert sinked.status().model_available is True


def test_t_cx500_heldout_scenarios_are_frozen_and_valid() -> None:
    assert hashlib.sha256(ASSET.read_bytes()).hexdigest() == HELDOUT_SHA256
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == HELDOUT_SHA256
    cases = load_cases("heldout")
    assert len(cases) == 20 and len({case["case_id"] for case in cases}) == 20
    plans = collections.Counter(case["expected"]["plan_id"] for case in cases)
    assert plans == {"sweep_levels": 8, "existing_recording": 4, "paired_reference": 4, "nominal_tone": 4}
    tags = collections.Counter(tag for case in cases for tag in case["tags"])
    assert tags["mic"] == 2 and tags["digital"] == 2 and tags["conflict"] == 1 and tags["en"] >= 6
    dev_texts = {case["text"] for case in load_cases("dev")}
    for case in cases:
        assert case["text"] not in dev_texts and case["quote"] in case["text"], case["case_id"]
        validate_plan_draft(oracle_draft(case), request_for(case))


def test_t_cx501_harness_case_sets_and_rejection_fields(tmp_path: Path) -> None:
    offline = asyncio.run(run(tmp_path / "offline", live=False, case_set="heldout"))
    assert offline["case_set"] == "heldout" and offline["cases"] == 20 and offline["model_calls"] == 0
    assert offline["plan_accuracy"] == 1.0 and offline["parameter_accuracy"] == 1.0
    assert offline["prompt_version"] == GUIDE_PROMPT_VERSION and offline["rejection_details"] == {}
    rows = [json.loads(line) for line in (tmp_path / "offline" / "results.jsonl").read_text().splitlines()]
    assert all(row["rejection_detail"] is None and row["rejected_draft"] is None for row in rows)

    service = GuideService(ScriptedGuide("not json"), identity=SCRIPTED)
    live = asyncio.run(run(tmp_path / "live", live=True, service=service, case_set="heldout"))
    assert live["model_calls"] == 20 and sum(live["rejection_details"].values()) == 20
    rows = [json.loads(line) for line in (tmp_path / "live" / "results.jsonl").read_text().splitlines()]
    assert all(row["rejected_draft"] == "not json" and row["rejection_detail"] for row in rows)
    for name in ("results.jsonl", "summary.json"):
        text = (tmp_path / "live" / name).read_text(encoding="utf-8")
        assert "DEEPSEEK_API_KEY" not in text
        assert all(line == line.rstrip() for line in text.splitlines())
