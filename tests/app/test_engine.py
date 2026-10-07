"""T-CX448–T-CX452: deterministic diagnosis engine s1-engine-1.0 (D053)."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.agent.engine import (
    ENGINE_VERSION,
    OVERLAP,
    WINDOW_S,
    DeterministicDiagnosisEngine,
    clipping_windows,
)
from signal_diag.agent.planner import PlannerModel
from signal_diag.app.engine_comparison import (
    KNOWN_LIMITATIONS,
    build_report,
    render,
    run_engine,
)
from signal_diag.signal import build_signal_record
from signal_diag.signal.models import SignalRecord

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/evaluations/v0_3/engine/phase1_comparison/report.json"
ENGINE_SOURCE = ROOT / "src/signal_diag/agent/engine.py"
RATE = 8_000


def _tone(seconds: float = 2.0, *, clip_span: tuple[float, float] | None = None) -> SignalRecord:
    t = np.arange(int(seconds * RATE)) / RATE
    samples = 0.3 * np.sin(2 * np.pi * 440.0 * t)
    if clip_span is not None:
        start, end = (int(edge * RATE) for edge in clip_span)
        burst = np.clip(0.9 * np.sin(2 * np.pi * 440.0 * t), -0.4, 0.4)
        samples[start:end] = burst[start:end]
    return build_signal_record(
        samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=RATE, source_type="generated"
    )


def _harmonic_tone(seconds: float = 1.0) -> SignalRecord:
    t = np.arange(int(seconds * RATE)) / RATE
    fundamental = np.sin(2 * np.pi * 440.0 * t)
    samples = 0.4 * (fundamental + 0.3 * np.sin(2 * np.pi * 880.0 * t))
    return build_signal_record(
        samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=RATE, source_type="generated"
    )


def _run(record: SignalRecord, **kwargs: Any) -> Any:
    kwargs.setdefault("mode", "single_signal")
    kwargs.setdefault("nominal_fundamental_hz", None)
    return asyncio.run(run_engine(record, kwargs.pop("reference", None), **kwargs))


def test_t_cx448_engine_is_a_planner_model_without_model_access() -> None:
    assert ENGINE_VERSION == "s1-engine-1.0"
    assert (WINDOW_S, OVERLAP) == (0.25, 0.5)
    assert isinstance(DeterministicDiagnosisEngine(), PlannerModel)
    tree = ast.parse(ENGINE_SOURCE.read_text(encoding="utf-8"))
    imported = {
        (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    for forbidden in ("openai", "httpx", "httpx2", "signal_diag.agent.planner", ".planner"):
        assert forbidden not in imported
    assert "planner" not in {name.split(".")[-1] for name in imported if name}


def test_t_cx448_single_file_plan_scans_windows_only_without_whole_file_clipping() -> None:
    clean = _run(_tone())
    tools = [entry.tool_name for entry in clean.tool_history]
    assert tools[:2] == ["detect_clipping", "analyze_harmonic_distortion"]
    windows = clipping_windows(_tone().meta)
    assert len(tools) == 2 + len(windows)
    assert set(tools[2:]) == {"detect_clipping"}
    assert clean.diagnosis is not None and clean.diagnosis.outcome == "no_supported_fault"

    burst = _run(_tone(clip_span=(1.0, 1.5)))
    assert burst.diagnosis is not None and burst.diagnosis.outcome == "supported_fault"
    assert {claim.fault_type for claim in burst.diagnosis.claims} == {"clipping"}
    assert burst.diagnosis.knowledge_retrievals
    clipping = burst.diagnosis.claims[0]
    assert clipping.knowledge_refs


def test_t_cx448_contextual_plan_is_one_comparison_call() -> None:
    reference = _tone(1.0)
    paired = _run(_tone(1.0), reference=reference, mode="paired_reference")
    assert [entry.tool_name for entry in paired.tool_history] == ["analyze_contextual_distortion"]
    nominal = _run(_tone(1.0), mode="nominal_single_tone", nominal_fundamental_hz=440.0)
    assert [entry.tool_name for entry in nominal.tool_history] == [
        "analyze_contextual_distortion"
    ]
    for result in (paired, nominal):
        assert result.status != "error"
        assert result.termination_reason == "planner_finished"


def test_t_cx449_and_t_cx452_comparison_report_is_reproducible() -> None:
    committed = REPORT.read_text(encoding="utf-8")
    regenerated = render(asyncio.run(build_report(ROOT)))
    assert regenerated == committed
    report = json.loads(committed)
    assert report["model_calls"] == 0
    for entry in report["sets"].values():
        assert entry["errors"] == 0
    for row in report["rows"]:
        assert row["status"] != "error"
        assert row["termination_reason"] == "planner_finished"


def test_t_cx452_engine_not_worse_except_accepted_limitations() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    shortfalls = [
        case_id
        for entry in report["sets"].values()
        for case_id in entry.get("engine_only_wrong", ())
    ]
    assert sorted(shortfalls) == sorted(KNOWN_LIMITATIONS)
    for name, entry in report["sets"].items():
        if "planner_correct" not in entry:
            continue
        accepted = sum(case_id in KNOWN_LIMITATIONS for case_id in entry.get("engine_only_wrong", ()))
        assert entry["engine_correct"] + accepted >= entry["planner_correct"], name


def test_t_cx450_runs_are_deterministic() -> None:
    def dump(record: SignalRecord) -> list[dict[str, Any]]:
        result = _run(record)
        assert result.diagnosis is not None
        claims = [claim.model_dump(exclude={"claim_id"}) for claim in result.diagnosis.claims]
        return [{"outcome": result.diagnosis.outcome}, *claims]

    for record in (_tone(), _tone(clip_span=(0.5, 0.8)), _harmonic_tone()):
        assert dump(record) == dump(record)


def test_t_cx451_single_file_mode_never_attributes_harmonic_distortion() -> None:
    result = _run(_harmonic_tone())
    assert result.diagnosis is not None
    assert all(claim.fault_type != "harmonic_distortion" for claim in result.diagnosis.claims)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    single = [row for row in report["rows"] if row["mode"] == "single_signal"]
    assert single
    assert all("harmonic_distortion" not in row["engine_faults"] for row in single)


@pytest.mark.parametrize("seconds", [0.1, 0.25, 0.3])
def test_t_cx448_short_files_still_finish(seconds: float) -> None:
    result = _run(_tone(seconds))
    assert result.termination_reason == "planner_finished"
