"""T-CX434–T-CX437: product fault time localization by segment scan (D050)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.app.fault_localization import (
    OVERLAP,
    SCAN_VERSION,
    WINDOW_S,
    FaultLocalization,
    localize_faults,
    scan_windows,
)
from signal_diag.evaluation.dataset import _generate, load_dataset_manifest
from signal_diag.signal import build_signal_record, load_wav_bytes
from signal_diag.signal.models import SignalRecord

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1"
MANIFESTS = sorted((ROOT / "src/signal_diag/evaluation/manifests").glob("s1_distortion_v1*.yaml"))


def _held_t2() -> list[dict[str, Any]]:
    manifest = json.loads((STUDY / "manifest.json").read_text(encoding="utf-8"))
    return [c for c in manifest["cases"] if c["family"] == "T2" and c["split"] == "heldout"]


def _record(case: dict[str, Any]) -> SignalRecord:
    path = ROOT / case["files"][0]
    return load_wav_bytes(path.read_bytes(), filename=path.name).record


def _overlaps(localization: FaultLocalization, span: dict[str, Any], fault: str) -> bool:
    for interval in localization.intervals:
        if interval.fault != fault:
            continue
        if interval.channel not in (span["channel"], "mixdown"):
            continue
        if interval.start_s < span["end_s"] and span["start_s"] < interval.end_s:
            return True
    return False


def _tone(seconds: float = 1.0, rate: int = 8_000) -> SignalRecord:
    t = np.arange(int(seconds * rate)) / rate
    samples = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32).reshape(-1, 1)
    return build_signal_record(samples, sample_rate_hz=rate, source_type="generated")


def test_t_cx434_windows_are_fixed_and_cover_the_file() -> None:
    assert SCAN_VERSION == "product-segment-scan-1.0"
    assert (WINDOW_S, OVERLAP) == (0.25, 0.5)
    windows = scan_windows(_tone(seconds=1.0))
    assert windows[0].start_s == 0.0 and windows[0].end_s == pytest.approx(0.25)
    assert windows[1].start_s == pytest.approx(0.125)
    assert windows[-1].end_s == pytest.approx(1.0)
    starts = [w.start_s for w in windows]
    assert starts == sorted(starts)


def test_t_cx434_intervals_merge_windows_and_stay_traceable() -> None:
    clipped = np.clip(0.9 * np.sin(2 * np.pi * 440.0 * np.arange(16_000) / 8_000), -0.4, 0.4)
    samples = np.zeros(16_000, dtype=np.float32)
    samples[8_000:12_000] = clipped[8_000:12_000].astype(np.float32)  # 1.0–1.5 s
    samples[:8_000] = (0.3 * np.sin(2 * np.pi * 440.0 * np.arange(8_000) / 8_000)).astype(
        np.float32
    )
    record = build_signal_record(samples.reshape(-1, 1), sample_rate_hz=8_000, source_type="generated")
    result = localize_faults(
        record, mode="single_signal", nominal_fundamental_hz=None, diagnosed_faults=frozenset()
    )
    clipping = [i for i in result.intervals if i.fault == "clipping"]
    assert len(clipping) == 1
    interval = clipping[0]
    assert interval.channel == "mixdown"
    assert 0.8 <= interval.start_s <= 1.0
    assert 1.5 <= interval.end_s <= 1.7
    assert interval.agrees_with_diagnosis is False
    evidence_ids = {item.evidence_id for item in result.evidence}
    evaluation_ids = {item.evaluation_id for item in result.rule_evaluations}
    assert set(interval.evidence_refs) <= evidence_ids
    assert set(interval.evaluation_refs) <= evaluation_ids
    assert len(interval.evidence_refs) >= 2
    for evaluation in result.rule_evaluations:
        assert evaluation.judgment == "fail"
        assert set(evaluation.evidence_refs) <= evidence_ids


@pytest.mark.parametrize(
    "case",
    [c for c in _held_t2() if c["truth"]["fault_spans"]],
    ids=lambda case: case["case_id"],
)
def test_t_cx435_h1_t2_fault_cases_are_localized(case: dict[str, Any]) -> None:
    truth = case["truth"]
    record = _record(case)
    if truth["conclusion"] == "harmonic_distortion":
        result = localize_faults(
            record,
            mode="nominal_single_tone",
            nominal_fundamental_hz=440.0,
            diagnosed_faults=frozenset({"harmonic_distortion"}),
        )
    else:
        result = localize_faults(
            record,
            mode="single_signal",
            nominal_fundamental_hz=None,
            diagnosed_faults=frozenset({"clipping"}),
        )
    for span in truth["fault_spans"]:
        assert _overlaps(result, span, truth["conclusion"]), (case["case_id"], span)
    assert all(i.agrees_with_diagnosis for i in result.intervals if i.fault == truth["conclusion"])


@pytest.mark.parametrize(
    "case",
    [c for c in _held_t2() if not c["truth"]["fault_spans"]],
    ids=lambda case: case["case_id"],
)
def test_t_cx436_clean_t2_cases_have_no_intervals(case: dict[str, Any]) -> None:
    record = _record(case)
    for mode, nominal in (("single_signal", None), ("nominal_single_tone", 440.0)):
        result = localize_faults(
            record, mode=mode, nominal_fundamental_hz=nominal, diagnosed_faults=frozenset()
        )
        assert result.intervals == (), (case["case_id"], mode)


def test_t_cx436_v02_clean_synthetic_cases_have_no_intervals() -> None:
    checked = 0
    for manifest in MANIFESTS:
        for case in load_dataset_manifest(manifest).cases:
            if type(case.signal).__name__ != "SineSignalSpec":
                continue
            generated = _generate(case)
            result = localize_faults(
                generated.record,
                mode="single_signal",
                nominal_fundamental_hz=None,
                diagnosed_faults=frozenset(),
            )
            assert result.intervals == (), case.case_id
            checked += 1
    assert checked > 0


def test_t_cx437_single_file_mode_never_localizes_harmonics() -> None:
    harmonic_cases = [c for c in _held_t2() if c["truth"]["conclusion"] == "harmonic_distortion"]
    assert harmonic_cases
    for case in harmonic_cases:
        result = localize_faults(
            _record(case),
            mode="single_signal",
            nominal_fundamental_hz=None,
            diagnosed_faults=frozenset({"harmonic_distortion"}),
        )
        assert result.harmonic_scanned is False
        assert all(i.fault != "harmonic_distortion" for i in result.intervals)
        assert all(item.source_tool != "analyze_harmonic_distortion" for item in result.evidence)
