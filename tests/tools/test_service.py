"""Integration tests for SignalToolService (T053–T061)."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pytest

from signal_diag.signal import (
    InMemorySignalRepository,
    SyntheticCase,
    TimeRange,
    build_signal_record,
    generate_sine,
)
from signal_diag.tools import (
    ClippingInput,
    FundamentalInput,
    HarmonicDistortionInput,
    SignalToolService,
    SpectrumInput,
)

FORBIDDEN_FFT_KEYS = frozenset({"frequencies_hz", "magnitude_db"})


def _assert_json_tree_has_no_arrays_or_full_fft_keys(value: Any) -> None:
    if isinstance(value, np.ndarray):
        pytest.fail("serialized Tool output must not contain ndarray values")
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_FFT_KEYS:
                raise AssertionError(
                    "serialized Tool output must not expose full FFT arrays"
                )
            _assert_json_tree_has_no_arrays_or_full_fft_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_json_tree_has_no_arrays_or_full_fft_keys(item)


def test_t053_detect_clipping_returns_compact_result_and_evidence(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    repository.put(clipped_case.record)
    service = SignalToolService(repository)

    result = service.detect_clipping(
        clipped_case.record.meta.signal_id,
        ClippingInput(),
    )

    assert result.status == "success"
    assert result.result is not None
    assert result.result.detected is True
    assert result.result.flat_top_detected is True
    assert result.error_message is None
    assert result.evidence

    metrics = {item.metric for item in result.evidence}
    assert "clipping_detected" in metrics
    assert "clipping_ratio" in metrics
    assert "clipped_samples" in metrics
    assert "clipping_events" in metrics
    assert "peak_abs" in metrics


def test_t054_analyze_spectrum_is_compact_without_full_fft_arrays(
    repository: InMemorySignalRepository,
    sine_case: SyntheticCase,
) -> None:
    repository.put(sine_case.record)
    service = SignalToolService(repository)

    result = service.analyze_spectrum(
        sine_case.record.meta.signal_id,
        SpectrumInput(),
    )

    assert result.status == "success"
    assert result.result is not None
    assert result.result.dominant_frequency_hz == pytest.approx(200.0, abs=1.0)
    assert not hasattr(result.result, "frequencies_hz")
    assert not hasattr(result.result, "magnitude_db")
    assert all(
        peak.relative_magnitude_db >= -60.0
        for peak in result.result.spectral_peaks
    )

    payload = json.loads(result.model_dump_json())
    _assert_json_tree_has_no_arrays_or_full_fft_keys(payload)


def test_t055_estimate_fundamental_success_on_voiced_sine(
    repository: InMemorySignalRepository,
    sine_case: SyntheticCase,
) -> None:
    repository.put(sine_case.record)
    service = SignalToolService(repository)

    result = service.estimate_fundamental(
        sine_case.record.meta.signal_id,
        FundamentalInput(fmin_hz=100.0, fmax_hz=400.0),
    )

    assert result.status == "success"
    assert result.result is not None
    assert result.result.voiced is True
    assert result.result.f0_hz == pytest.approx(200.0, abs=1.0)
    assert any(item.metric == "f0_hz" for item in result.evidence)


def test_t056_estimate_fundamental_invalid_on_noise_without_fabricated_f0(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    repository.put(noise_case.record)
    service = SignalToolService(repository)

    result = service.estimate_fundamental(
        noise_case.record.meta.signal_id,
        FundamentalInput(),
    )

    assert result.status == "invalid"
    assert result.result is not None
    assert result.result.voiced is False
    assert result.result.f0_hz is None
    assert result.warnings
    assert not any(item.metric == "f0_hz" for item in result.evidence)


def test_t057_analyze_harmonic_distortion_returns_thd_evidence(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    repository.put(harmonic_case.record)
    service = SignalToolService(repository)

    result = service.analyze_harmonic_distortion(
        harmonic_case.record.meta.signal_id,
        HarmonicDistortionInput(fundamental_hz=200.0),
    )

    assert result.status == "success"
    assert result.result is not None
    assert result.result.valid is True
    assert result.result.thd_percent == pytest.approx(11.180339, abs=0.5)
    metrics = {item.metric for item in result.evidence}
    assert "thd_percent" in metrics
    assert "fundamental_frequency_hz" in metrics
    assert all(component.relative_amplitude >= 1e-6 for component in result.result.components)


def test_t058_analyze_harmonic_distortion_invalid_on_noise_without_numeric_thd(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    repository.put(noise_case.record)
    service = SignalToolService(repository)

    result = service.analyze_harmonic_distortion(
        noise_case.record.meta.signal_id,
        HarmonicDistortionInput(),
    )

    assert result.status == "invalid"
    assert result.result is not None
    assert result.result.valid is False
    assert result.result.thd_percent is None
    assert result.warnings
    assert not any(item.metric == "thd_percent" for item in result.evidence)
    assert not any(item.metric == "fundamental_frequency_hz" for item in result.evidence)


def test_t059_missing_signal_returns_error_without_evidence(
    repository: InMemorySignalRepository,
) -> None:
    service = SignalToolService(repository)
    missing_id = "missing-signal-id"

    clipping = service.detect_clipping(missing_id, ClippingInput())
    spectrum = service.analyze_spectrum(missing_id, SpectrumInput())
    fundamental = service.estimate_fundamental(missing_id, FundamentalInput())
    harmonic = service.analyze_harmonic_distortion(
        missing_id,
        HarmonicDistortionInput(),
    )

    for result in (clipping, spectrum, fundamental, harmonic):
        assert result.status == "error"
        assert result.result is None
        assert not result.evidence
        assert result.error_message is not None


def test_t060_segment_and_channel_selection_propagate_to_results(
    repository: InMemorySignalRepository,
) -> None:
    sample_rate_hz = 48_000
    first = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=sample_rate_hz,
        duration_s=1.0,
        amplitude=0.5,
    )
    second = generate_sine(
        frequency_hz=400.0,
        sample_rate_hz=sample_rate_hz,
        duration_s=1.0,
        amplitude=0.5,
    )
    combined = build_signal_record(
        np.concatenate(
            [first.record.samples[:, 0], second.record.samples[:, 0]]
        ).reshape(-1, 1),
        sample_rate_hz=sample_rate_hz,
        source_type="generated",
        signal_id="sig_two_regions",
    )
    repository.put(combined)

    stereo_rate = 48_000
    t = np.arange(stereo_rate, dtype=np.float64) / stereo_rate
    stereo = build_signal_record(
        np.column_stack(
            [
                np.sin(2 * np.pi * 200 * t, dtype=np.float64),
                np.sin(2 * np.pi * 400 * t, dtype=np.float64),
            ]
        ).astype(np.float32),
        sample_rate_hz=stereo_rate,
        source_type="generated",
        signal_id="sig_stereo",
    )
    repository.put(stereo)

    service = SignalToolService(repository)

    early = service.analyze_spectrum(
        combined.meta.signal_id,
        SpectrumInput(time_range=TimeRange(start_s=0.0, end_s=1.0)),
    )
    late = service.analyze_spectrum(
        combined.meta.signal_id,
        SpectrumInput(time_range=TimeRange(start_s=1.0, end_s=2.0)),
    )
    left = service.analyze_spectrum(
        stereo.meta.signal_id,
        SpectrumInput(channel="left"),
    )
    right = service.analyze_spectrum(
        stereo.meta.signal_id,
        SpectrumInput(channel="right"),
    )

    assert early.result is not None and early.result.dominant_frequency_hz == pytest.approx(
        200.0, abs=1.0
    )
    assert late.result is not None and late.result.dominant_frequency_hz == pytest.approx(
        400.0, abs=1.0
    )
    assert left.result is not None and left.result.dominant_frequency_hz == pytest.approx(
        200.0, abs=1.0
    )
    assert right.result is not None and right.result.dominant_frequency_hz == pytest.approx(
        400.0, abs=1.0
    )


def test_t061_evidence_linkage_is_unique_and_provenance_correct(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    repository.put(harmonic_case.record)
    service = SignalToolService(repository)
    time_range = TimeRange(start_s=0.5, end_s=1.5)

    result = service.analyze_harmonic_distortion(
        harmonic_case.record.meta.signal_id,
        HarmonicDistortionInput(
            fundamental_hz=200.0,
            time_range=time_range,
            channel="left",
        ),
    )

    assert result.status == "success"
    assert result.call_id.startswith("call_")
    evidence_ids = [item.evidence_id for item in result.evidence]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert all(item.evidence_id.startswith("ev_") for item in result.evidence)
    for item in result.evidence:
        assert item.call_id == result.call_id
        assert item.source_tool == "analyze_harmonic_distortion"
        assert item.channel == "left"
        assert item.time_range == time_range
        assert item.metric
