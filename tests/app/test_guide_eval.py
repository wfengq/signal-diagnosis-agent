"""T-CX493: test guide scenarios and acceptance harness (D057 4A). No network."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from signal_diag.agent.guide import ScriptedGuide
from signal_diag.app.guide_eval import load_cases, oracle_draft, request_for, run
from signal_diag.app.guide_service import GuideIdentity, GuideService
from signal_diag.app.test_plan import PLAN_IDS, validate_plan_draft


def test_t_cx493_authored_cases_are_consistent_with_the_validator() -> None:
    cases = load_cases()
    assert len(cases) == 40 and len({case["case_id"] for case in cases}) == 40
    assert {case["expected"]["plan_id"] for case in cases} == set(PLAN_IDS)
    for case in cases:
        assert case["quote"] in case["text"], case["case_id"]
        validate_plan_draft(oracle_draft(case), request_for(case))
    tags = {tag for case in cases for tag in case["tags"]}
    assert {"en", "mic", "line", "digital", "conflict", "ask_hz", "ask_connection", "no_files"} <= tags


def test_t_cx493_offline_and_scripted_live_runs(tmp_path: Path) -> None:
    offline = asyncio.run(run(tmp_path / "offline", live=False))
    assert offline["cases"] == 40 and offline["model_calls"] == 0
    assert offline["plan_accuracy"] == 1.0 and offline["parameter_accuracy"] == 1.0
    assert offline["meets_bar"] is False
    service = GuideService(ScriptedGuide("not json"), identity=GuideIdentity(provider="scripted", model="s"))
    live = asyncio.run(run(tmp_path / "live", live=True, service=service))
    assert live["model_calls"] == 40 and live["plan_accuracy"] == 0.0
    assert live["fallback_reasons"] == {"illegal_output": 40} and live["meets_bar"] is False
    rows = (tmp_path / "live" / "results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 40 and all(json.loads(row)["source"] == "questionnaire" for row in rows)
