"""V0.3 Workstream C — DSP series_kind / clipping_mechanism gold labels."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.dsp import analyze_clipping, analyze_harmonic_distortion
from signal_diag.signal import extract_segment, load_wav_bytes

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEV_WAV_DIR = (
    PROJECT_ROOT
    / "docs"
    / "evaluations"
    / "v0_3"
    / "dev"
    / "study_v0_3_dev_1"
    / "wav"
)


def _analyze_dev(case_id: str):
    path = DEV_WAV_DIR / f"v03dev_{case_id}.wav"
    loaded = load_wav_bytes(path.read_bytes(), filename=path.name)
    samples = extract_segment(loaded.record)
    sample_rate_hz = loaded.record.meta.sample_rate_hz
    harmonic = analyze_harmonic_distortion(samples, sample_rate_hz)
    clipping = analyze_clipping(samples)
    return harmonic, clipping


def test_workstream_c_series_kind_gold_labels() -> None:
    harmonic, _ = _analyze_dev("b2e4d0f3c915e827")
    assert harmonic.valid
    assert harmonic.series_kind == "even_order_present"

    harmonic, _ = _analyze_dev("e5b7a3c6f2481b5a")
    assert harmonic.valid
    assert harmonic.series_kind == "multi_partial"

    harmonic, clipping = _analyze_dev("6d3f5be41ac093d2")
    assert harmonic.valid
    assert harmonic.series_kind == "native_odd_series"
    assert clipping.clipping_mechanism is False

    harmonic, _ = _analyze_dev("7e4a6cf52bd1a4e3")
    assert harmonic.valid
    assert harmonic.series_kind == "native_odd_series"

    harmonic, clipping = _analyze_dev("29fb17a0d68c5f9e")
    assert not harmonic.valid
    assert harmonic.series_kind == "not_applicable"

    harmonic, _ = _analyze_dev("a1f3c9e2b804d716")
    assert harmonic.valid
    assert harmonic.series_kind is None


def test_workstream_c_clipping_mechanism_gold_labels() -> None:
    _, clipping = _analyze_dev("6d3f5be41ac093d2")
    assert clipping.peak_abs == pytest.approx(0.50, abs=1e-6)
    assert clipping.flat_top_detected is True
    assert clipping.full_scale_detected is False
    assert clipping.clipping_mechanism is False

    _, clipping = _analyze_dev("c3f5e1a4d026f938")
    assert clipping.peak_abs == pytest.approx(0.99, abs=1e-6)
    assert clipping.full_scale_detected is True
    assert clipping.clipping_mechanism is True
