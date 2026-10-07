"""T-CX441–T-CX445: paired-reference fault time localization (D051)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.app.fault_localization import (
    COMPARISON_OVERLAP,
    SCAN_VERSION,
    FaultLocalization,
    localize_faults,
    scan_windows,
)
from signal_diag.signal import build_signal_record, load_wav_bytes
from signal_diag.signal.models import SignalRecord
from tests.app.test_fault_localization import _held_t2, _record

ROOT = Path(__file__).resolve().parents[2]
CONTEXTUAL = ROOT / "docs/evaluations/v0_3/contextual"
STUDIES = (
    CONTEXTUAL / "development/study_v0_3_contextual_dev_1",
    CONTEXTUAL / "validation/study_v0_3_contextual_validation_1",
)
BASELINE = Path(__file__).parent / "fixtures/fault_localization_v1_0_baseline.json"
RATE = 48_000
BURST = (1.0, 1.5)


def _note(seconds: float = 2.0, decay: float = 0.0) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    envelope = np.exp(-t * decay)
    return envelope * (
        0.5 * np.sin(2 * np.pi * 220 * t)
        + 0.15 * np.sin(2 * np.pi * 440 * t + 0.3)
        + 0.08 * np.sin(2 * np.pi * 660 * t + 1.0)
    )


def _with_burst(reference: np.ndarray) -> np.ndarray:
    test = reference.copy()
    span = slice(int(BURST[0] * RATE), int(BURST[1] * RATE))
    burst = test[span]
    test[span] = burst + 0.6 * burst**2 / np.max(np.abs(burst))
    return test


def _delayed(samples: np.ndarray, offset_s: float) -> np.ndarray:
    shift = int(offset_s * RATE)
    return np.concatenate([np.zeros(shift), samples])[: len(samples)]


def _mono(samples: np.ndarray) -> SignalRecord:
    return build_signal_record(
        samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=RATE, source_type="generated"
    )


HARMONIC = frozenset({"harmonic_distortion"})


def _paired(
    test: SignalRecord, reference: SignalRecord, diagnosed: frozenset[str] = HARMONIC
) -> FaultLocalization:
    # Scan-quality tests use a diagnosis that supports harmonic distortion, so
    # the reference-growth intervals are shown (§27.1); T-CX447 covers withholding.
    return localize_faults(
        test,
        mode="paired_reference",
        nominal_fundamental_hz=None,
        diagnosed_faults=diagnosed,
        reference=reference,
    )


def _harmonic(result: FaultLocalization) -> list[Any]:
    return [i for i in result.intervals if i.fault == "harmonic_distortion"]


@pytest.mark.parametrize("decay", [0.0, 1.5])
@pytest.mark.parametrize("offset_s", [0.0, 0.03, 0.2])
def test_t_cx441_synthetic_burst_is_localized_on_the_test_timeline(decay: float, offset_s: float) -> None:
    reference = _note(decay=decay)
    test = _delayed(_with_burst(reference), offset_s)
    result = _paired(_mono(test), _mono(reference))
    assert result.scan_version == SCAN_VERSION == "product-segment-scan-1.1"
    assert result.harmonic_scanned is True
    assert result.harmonic_basis == "reference_growth"
    assert result.comparison_overlap == COMPARISON_OVERLAP == 0.0
    harmonic = _harmonic(result)
    assert harmonic, (decay, offset_s)
    start, end = BURST[0] + offset_s, BURST[1] + offset_s
    for interval in harmonic:
        assert interval.channel == "mixdown"
        assert interval.agrees_with_diagnosis is True
        assert interval.start_s < end and start < interval.end_s
        assert start - 0.25 <= interval.start_s and interval.end_s <= end + 0.25
    covered = sum(i.end_s - i.start_s for i in harmonic)
    assert covered >= 0.25
    evidence_ids = {item.evidence_id for item in result.evidence}
    evaluations = {item.evaluation_id: item for item in result.rule_evaluations}
    for interval in harmonic:
        assert set(interval.evidence_refs) <= evidence_ids
        assert set(interval.evaluation_refs) <= set(evaluations)
        rules = {evaluations[ref].rule_id: evaluations[ref].judgment for ref in interval.evaluation_refs}
        assert rules["rule_even_harmonic_growth_acceptable"] == "fail"
        for gate in (
            "rule_contextual_analysis_valid",
            "rule_contextual_f0_compatible",
            "rule_reference_clipping_ratio_acceptable",
            "rule_reference_flat_top_absent",
        ):
            assert rules[gate] == "pass"


def test_t_cx441_identical_files_have_no_harmonic_interval() -> None:
    reference = _note(decay=1.5)
    result = _paired(_mono(reference), _mono(reference.copy()))
    assert _harmonic(result) == []
    assert result.windows_not_comparable == 0


def test_t_cx441_stereo_test_with_mono_reference_localizes_the_distorted_channel() -> None:
    reference = _note()
    test = np.stack([reference, _with_burst(reference)], axis=1).astype(np.float32)
    stereo = build_signal_record(test, sample_rate_hz=RATE, source_type="generated")
    result = _paired(stereo, _mono(reference))
    channels = {i.channel for i in _harmonic(result)}
    assert "right" in channels and "left" not in channels
    assert result.windows_not_comparable == 0


def test_t_cx442_windows_failing_the_gate_are_not_comparable() -> None:
    reference = _note()
    clipped_reference = reference.copy()
    span = slice(int(BURST[0] * RATE), int(BURST[1] * RATE))
    clipped_reference[span] = np.clip(clipped_reference[span] * 3.0, -0.999, 0.999)
    result = _paired(_mono(_with_burst(reference)), _mono(clipped_reference))
    assert result.windows_not_comparable is not None and result.windows_not_comparable >= 2
    for interval in _harmonic(result):
        assert interval.end_s <= BURST[0] or interval.start_s >= BURST[1]

    short = _paired(_mono(_with_burst(reference)), _mono(reference[: RATE // 2]))
    assert short.windows_not_comparable is not None and short.windows_not_comparable >= 6
    assert all(i.end_s <= 0.5 for i in _harmonic(short))

    t = np.arange(2 * RATE) / RATE
    other = 0.5 * np.sin(2 * np.pi * 330 * t)
    mismatch = _paired(_mono(_with_burst(reference)), _mono(other))
    assert _harmonic(mismatch) == []
    assert mismatch.windows_not_comparable == 8


def test_t_cx442_paired_mode_requires_a_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        localize_faults(
            _mono(_note()),
            mode="paired_reference",
            nominal_fundamental_hz=None,
            diagnosed_faults=frozenset(),
        )


def _study_cases() -> list[tuple[str, dict[str, Any], Path, Path]]:
    found: list[tuple[str, dict[str, Any], Path, Path]] = []
    for study in STUDIES:
        index = {
            hashlib.sha256(path.read_bytes()).hexdigest(): path
            for path in sorted((study / "wav").glob("*.wav"))
        }
        manifest = json.loads((study / "contextual_manifest.json").read_text(encoding="utf-8"))
        for case in manifest["cases"]:
            if case["mode"] != "paired_reference":
                continue
            found.append(
                (
                    f"{study.name}:{case['case_id']}:{case['role']}",
                    case,
                    index[case["test_wav_sha256"]],
                    index[case["reference_wav_sha256"]],
                )
            )
    return found


def _load(path: Path) -> SignalRecord:
    return load_wav_bytes(path.read_bytes(), filename=path.name).record


@pytest.mark.parametrize("label,case,test_path,reference_path", _study_cases(), ids=lambda v: v if isinstance(v, str) else "")
def test_t_cx443_contextual_study_paired_cases(
    label: str, case: dict[str, Any], test_path: Path, reference_path: Path
) -> None:
    result = _paired(_load(test_path), _load(reference_path))
    harmonic = _harmonic(result)
    if "harmonic_distortion" in case["expected_causal_set"]:
        assert harmonic, label
    else:
        assert harmonic == [], label
    if case["expected_outcome"] == "inconclusive":
        test_record = _load(test_path)
        windows = len(scan_windows(test_record, overlap=COMPARISON_OVERLAP))
        assert result.windows_not_comparable == windows, label


def test_t_cx444_single_and_nominal_modes_match_the_1_0_baseline() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    checked = 0
    for case in _held_t2():
        record = _record(case)
        for mode, nominal in (("single_signal", None), ("nominal_single_tone", 440.0)):
            result = localize_faults(
                record,
                mode=mode,
                nominal_fundamental_hz=nominal,
                diagnosed_faults=frozenset({"clipping"}),
            )
            dumped = result.model_dump(mode="json")
            assert dumped.pop("scan_version") == "product-segment-scan-1.1"
            expected_basis = "nominal_thd" if mode == "nominal_single_tone" else None
            assert dumped.pop("harmonic_basis") == expected_basis
            assert dumped.pop("windows_not_comparable") is None
            assert dumped.pop("comparison_overlap") is None
            assert dumped.pop("harmonic_windows_withheld") is None
            assert dumped == baseline[f"{case['case_id']}|{mode}"], (case["case_id"], mode)
            checked += 1
    assert checked == len(baseline)


def test_t_cx447_paired_harmonic_windows_are_withheld_without_a_harmonic_diagnosis() -> None:
    reference = _note()
    test = _mono(_with_burst(reference))
    shown = _paired(test, _mono(reference))
    assert shown.harmonic_windows_withheld == 0
    windows = len(_harmonic(shown))
    assert windows

    for diagnosed in (frozenset(), frozenset({"clipping"})):
        withheld = _paired(test, _mono(reference), diagnosed)
        assert _harmonic(withheld) == []
        assert withheld.harmonic_windows_withheld is not None
        assert withheld.harmonic_windows_withheld >= windows
        assert withheld.windows_not_comparable == shown.windows_not_comparable
        assert all(
            item.source_tool != "analyze_contextual_distortion" for item in withheld.evidence
        )
        assert all(
            evaluation.rule_id != "rule_even_harmonic_growth_acceptable"
            for evaluation in withheld.rule_evaluations
        )

    single = localize_faults(
        test, mode="single_signal", nominal_fundamental_hz=None, diagnosed_faults=frozenset()
    )
    assert single.harmonic_windows_withheld is None
