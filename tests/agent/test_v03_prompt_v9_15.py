"""T-CX409: v9.15 names an outcome the runtime accepts on every single-file path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.prompts_v03 import (
    _S1_PROMPT_V9_11,
    _S1_PROMPT_V9_14,
    _S1_PROMPT_V9_15,
    _V9_14_MONO_WINDOWS,
    _V9_14_STEREO_HALVES,
)
from signal_diag.evaluation.agent_increment.budget import CallLedger
from signal_diag.evaluation.agent_increment.live import run_live_agent
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.wav import load_wav_bytes

_ROOT = Path(__file__).resolve().parents[2]
_WAV = _ROOT / "docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1/wav"
_V9_14_SHA256 = "a510d8ec390e5021c37285f36cfcd773d8e02103d0249996ac42f41c33c9b2c3"
_TASK = {"task_type": "distortion_analysis", "objective": "diagnose"}


def test_t_cx409_v915_prefixes_v911_and_leaves_v914_unchanged() -> None:
    assert _S1_PROMPT_V9_15.version == "v0.3-s1-planner-9.15"
    assert _S1_PROMPT_V9_15.system_prompt.startswith(_S1_PROMPT_V9_11.system_prompt)
    digest = hashlib.sha256(_S1_PROMPT_V9_14.system_prompt.encode()).hexdigest()
    assert digest == _V9_14_SHA256
    extra = _S1_PROMPT_V9_15.system_prompt.removeprefix(_S1_PROMPT_V9_11.system_prompt)
    assert "outcome inconclusive" in extra
    assert "no_supported_fault" in extra
    assert PROMPT_VERSION == "v0.3-s1-planner-9.11"
    assert RealLLMPlanner._prompt_spec is _S1_PROMPT_V9_11


class _Reply:
    def __init__(self, content: str) -> None:
        message = type("Message", (), {"content": content})()
        self.choices = [type("Choice", (), {"message": message})()]


class _PlanFollowingSDK:
    """Follows the v9.15 single-file plan from the planner context it is sent."""

    max_retries = 0

    def __init__(self) -> None:
        self.chat = type("Chat", (), {})()
        self.chat.completions = self
        self.errors: list[str] = []

    async def create(self, **kwargs: Any) -> _Reply:
        context = json.loads(kwargs["messages"][-1]["content"])["planner_context"]
        self.errors.extend(context.get("recoverable_errors") or ())
        meta = context["signal_meta"]
        duration = float(meta["duration_s"])
        done = len(context["tool_history"])
        calls = self._plan(meta["channels"], duration, context)
        if done < len(calls):
            channel, span = calls[done]
            args: dict[str, Any] = {"channel": channel}
            if span is not None:
                args["time_range"] = {"start_s": span[0], "end_s": span[1]}
            decision: dict[str, Any] = {
                "decision_type": "call_tool",
                "task_assessment": _TASK,
                "call": {"tool_name": "detect_clipping", "args": args},
                "purpose": "planned call",
            }
        else:
            decision = self._finish(context)
        return _Reply(json.dumps(decision))

    @staticmethod
    def _clipped(context: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            item
            for item in context["evidence"]
            if item["metric"] == "clipping_mechanism" and item["value"] is True
        ]

    def _plan(
        self, channels: int, duration: float, context: dict[str, Any]
    ) -> list[tuple[str, tuple[float, float] | None]]:
        if channels == 1:
            step = duration / _V9_14_MONO_WINDOWS
            return [("mixdown", (i * step, (i + 1) * step)) for i in range(_V9_14_MONO_WINDOWS)]
        whole: list[tuple[str, tuple[float, float] | None]] = [("left", None), ("right", None)]
        clipped = {item["channel"] for item in self._clipped(context)}
        target = "left" if "left" in clipped else "right" if "right" in clipped else "mixdown"
        step = duration / _V9_14_STEREO_HALVES
        return whole + [(target, (i * step, (i + 1) * step)) for i in range(_V9_14_STEREO_HALVES)]

    def _finish(self, context: dict[str, Any]) -> dict[str, Any]:
        windows = [item for item in self._clipped(context) if item["time_range"] is not None]
        base = {"decision_type": "finish", "task_assessment": _TASK, "limitations": ["plan"]}
        if not windows:
            return {**base, "outcome": "inconclusive", "claims": [], "confidence_label": "low"}
        first_call = windows[0]["call_id"]
        refs = {item["evidence_id"] for item in context["evidence"] if item["call_id"] == first_call}
        rule_refs = [
            evaluation["evaluation_id"]
            for batch in context["rule_evaluation_batches"]
            for evaluation in batch["evaluations"]
            if refs & set(evaluation["evidence_refs"])
        ]
        claim = {
            "claim_id": "claim_window",
            "fault_type": "clipping",
            "statement": "A window shows clipping.",
            "evidence_refs": sorted(refs),
            "rule_refs": rule_refs,
            "knowledge_refs": [],
        }
        return {**base, "outcome": "supported_fault", "claims": [claim], "confidence_label": "medium"}

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "expected"),
    [("dev_t2_00.wav", "inconclusive"), ("dev_t2_07.wav", "supported_fault"), ("dev_t2_09.wav", "supported_fault")],
)
async def test_t_cx409_runtime_accepts_every_prescribed_finish(
    tmp_path: Path, name: str, expected: str
) -> None:
    """D1 round 4: v9.14 left the no-clipping outcome open and every such finish was rejected."""
    record = load_wav_bytes((_WAV / name).read_bytes(), filename=name).record
    repository = InMemorySignalRepository()
    repository.put(record)
    sdk = _PlanFollowingSDK()
    result = await run_live_agent(
        family="T2",
        case_id="x",
        ledger=CallLedger(stage_cap=100, output_dir=tmp_path),
        api_key="sk-test",
        repository=repository,
        signal_id=record.meta.signal_id,
        user_text="diagnose",
        truth=None,
        filenames=(name,),
        test_file=name,
        client=sdk,
        diagnosis_request="diagnose",
    )
    assert sdk.errors == []
    assert result.run.termination_reason == "planner_finished"
    assert result.run.diagnosis is not None
    assert result.run.diagnosis.outcome == expected
    assert len(result.run.tool_history) <= AgentLimits().max_rule_evaluations
