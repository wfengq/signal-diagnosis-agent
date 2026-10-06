"""T-CX399: live runner reserves before each send and does not fall back."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.intake import ContextDraft
from signal_diag.agent.planner import PROMPT_VERSION, PlannerOutputError, RealLLMPlanner
from signal_diag.evaluation.agent_increment import __main__ as increment_main
from signal_diag.evaluation.agent_increment.budget import CallCapStop, CallLedger
from signal_diag.evaluation.agent_increment.live import (
    require_live_credentials,
    run_live_agent,
)
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_sine

_TOOL = {
    "decision_type": "call_tool",
    "task_assessment": {
        "task_type": "distortion_analysis",
        "objective": "inspect clipping",
    },
    "call": {"tool_name": "detect_clipping", "args": {}},
    "purpose": "check clipping evidence",
}
_DRAFT = {
    "mode": "single_signal",
    "nominal_fundamental_hz": None,
    "reference_file": None,
    "stimulus_kind": None,
    "missing_fields": [],
    "questions": [],
}


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class ScriptedSDK:
    max_retries = 0

    def __init__(self, contents: list[str], events: list[str]) -> None:
        self.contents = contents
        self.events = events
        self.sends = 0
        self.systems: list[str] = []
        self.chat = self
        self.completions = self

    async def create(self, **kwargs: Any) -> _Response:
        self.events.append("send")
        self.sends += 1
        self.systems.append(str(kwargs["messages"][0]["content"]))
        content = self.contents[min(self.sends - 1, len(self.contents) - 1)]
        return _Response(content)


def _ledger(tmp_path: Path, stage_cap: int) -> CallLedger:
    return CallLedger(stage_cap=stage_cap, output_dir=tmp_path)


def _repo() -> tuple[InMemorySignalRepository, str]:
    case = generate_sine(frequency_hz=440.0, sample_rate_hz=8000, duration_s=0.05)
    repository = InMemorySignalRepository()
    repository.put(case.record)
    return repository, case.record.meta.signal_id


def _watch(ledger: CallLedger, events: list[str]) -> None:
    original = ledger.reserve

    def reserve(case_id: str) -> None:
        events.append("reserve")
        original(case_id)

    ledger.reserve = reserve  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_t_cx399_reserve_precedes_each_http_send(tmp_path: Path) -> None:
    repository, signal_id = _repo()
    events: list[str] = []
    sdk = ScriptedSDK([json.dumps(_DRAFT), json.dumps(_TOOL)], events)
    ledger = _ledger(tmp_path, 100)
    _watch(ledger, events)
    await run_live_agent(
        family="T1",
        case_id="t1-a",
        ledger=ledger,
        api_key="sk-test",
        repository=repository,
        signal_id=signal_id,
        user_text="听着发毛",
        truth=ContextDraft(mode="single_signal"),
        filenames=("only.wav",),
        test_file="only.wav",
        client=sdk,
    )
    assert events[:4] == ["reserve", "send", "reserve", "send"]
    assert ledger.total == sdk.sends
    assert "v0.3-s1-planner-9.13" in sdk.systems[1]
    assert RealLLMPlanner._prompt_spec.version == "v0.3-s1-planner-9.11"
    assert PROMPT_VERSION == "v0.3-s1-planner-9.11"


@pytest.mark.asyncio
async def test_t_cx399_caps_stop_before_the_next_send(tmp_path: Path) -> None:
    repository, signal_id = _repo()
    events: list[str] = []
    sdk = ScriptedSDK([json.dumps(_TOOL)], events)
    stage = _ledger(tmp_path / "stage", 1)
    _watch(stage, events)
    with pytest.raises(CallCapStop, match="stage_cap"):
        await run_live_agent(
            family="T2",
            case_id="t2-a",
            ledger=stage,
            api_key="sk-test",
            repository=repository,
            signal_id=signal_id,
            user_text="听着发毛",
            truth=None,
            filenames=("only.wav",),
            test_file="only.wav",
            client=sdk,
        )
    assert events == ["reserve", "send", "reserve"]
    stop = json.loads((tmp_path / "stage" / "stop_record.json").read_text(encoding="utf-8"))
    assert stop["reason"] == "stage_cap"

    per_case = _ledger(tmp_path / "case", 100)
    for _ in range(21):
        per_case.reserve("t2-b")
    case_events: list[str] = []
    sdk_case = ScriptedSDK([json.dumps(_TOOL)], case_events)
    _watch(per_case, case_events)
    with pytest.raises(CallCapStop, match="per_case_cap"):
        await run_live_agent(
            family="T2",
            case_id="t2-b",
            ledger=per_case,
            api_key="sk-test",
            repository=repository,
            signal_id=signal_id,
            user_text="听着发毛",
            truth=None,
            filenames=("only.wav",),
            test_file="only.wav",
            client=sdk_case,
        )
    assert case_events == ["reserve"]
    assert sdk_case.sends == 0
    record = json.loads((tmp_path / "case" / "stop_record.json").read_text(encoding="utf-8"))
    assert record["reason"] == "per_case_cap"
    assert record["case_calls"] == 21


def test_t_cx399_missing_credentials_do_not_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(PlannerOutputError, match="does not fall back to ScriptedPlanner"):
        require_live_credentials(None)
    with pytest.raises(PlannerOutputError, match="does not fall back to ScriptedPlanner"):
        require_live_credentials("  ")
    source = (
        Path(__file__).resolve().parents[3]
        / "src/signal_diag/evaluation/agent_increment/live.py"
    ).read_text(encoding="utf-8")
    assert "ScriptedPlanner(" not in source
    assert "ScriptedIntakePlanner" not in source


def test_t_cx399_dry_run_does_not_call_a_model(capsys: pytest.CaptureFixture[str]) -> None:
    source = Path(increment_main.__file__).read_text(encoding="utf-8")
    assert "openai" not in source
    assert "RealLLM" not in source
    code = increment_main.main(["--dry-run", "--split", "heldout", "--cases", "48"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["max_calls"] == 1008
    assert payload["cases"] == 48
