"""T-CX461: sweep facts, versioned rules and deterministic verdicts (D054)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from signal_diag.app.errors import ApplicationError
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.sweep import SweepDiagnosis, diagnose_sweep, stimulus_wav
from signal_diag.dsp.sweep import generate_stimulus
from signal_diag.rules.sweep import evaluate_sweep, load_sweep_profile
from signal_diag.signal import load_wav_bytes
from signal_diag.tools.sweep import measure_sweep_recording

RATE = 48_000
Device = Callable[[np.ndarray], np.ndarray]


def _wav(device: Device, *, lead_s: float = 0.2) -> bytes:
    stimulus, _ = generate_stimulus(RATE)
    response = device(stimulus)
    recording = np.concatenate(
        [np.zeros(int(lead_s * RATE)), response, np.zeros(int(0.3 * RATE))]
    )
    return encode_pcm32_wav(
        recording.astype(np.float32).reshape(-1, 1), sample_rate_hz=RATE
    )


def _clean(samples: np.ndarray) -> np.ndarray:
    return samples


def _all_refs(diagnosis: SweepDiagnosis) -> None:
    for level in diagnosis.levels:
        facts = {fact.fact_id for fact in level.measurement.facts}
        evaluations = {item.evaluation_id: item for item in level.rule_evaluations}
        for item in level.rule_evaluations:
            assert set(item.fact_refs) <= facts
        for claim in level.claims:
            assert claim.rule_refs and set(claim.rule_refs) <= set(evaluations)
            assert set(claim.fact_refs) <= facts


def test_t_cx461_profile_is_versioned_demo() -> None:
    profile = load_sweep_profile()
    assert (profile.profile_id, profile.version) == ("profile_s1_sweep", "1.0.0-demo")
    assert "not industry standards" in profile.description
    thresholds = {rule.rule_id: rule.threshold for rule in profile.rules}
    assert thresholds["rule_sweep_full_scale_acceptable"] == 0.01
    assert thresholds["rule_sweep_band_thd_acceptable"] == 5.0


def test_t_cx461_stimulus_wav_round_trips() -> None:
    data = stimulus_wav(RATE)
    assert data == stimulus_wav(RATE)
    loaded = load_wav_bytes(data)
    stimulus, spec = generate_stimulus(RATE)
    assert loaded.source_info.bits_per_sample == 24
    assert loaded.record.meta.sample_rate_hz == RATE
    assert np.max(np.abs(loaded.record.samples[:, 0] - stimulus)) < 1e-6
    assert f"sweep-stimulus-1.0 sha256:{spec.digest()}".encode() in data
    assert diagnose_sweep([(data, "loopback")]).outcome == "no_supported_fault"


def test_t_cx461_clean_device_has_no_supported_fault() -> None:
    diagnosis = diagnose_sweep([(_wav(_clean), "-12 dBFS")], sample_rate_hz=RATE)
    assert diagnosis.outcome == "no_supported_fault" and diagnosis.onset_level is None
    assert diagnosis.model_calls == 0
    (claim,) = diagnosis.levels[0].claims
    assert claim.fault_type == "no_supported_fault"
    _all_refs(diagnosis)


def test_t_cx461_harmonic_distortion_names_bands_and_order() -> None:
    diagnosis = diagnose_sweep(
        [(_wav(lambda s: np.tanh(2 * s) / 2), "0 dB")], sample_rate_hz=RATE
    )
    assert diagnosis.outcome == "supported_fault"
    (claim,) = diagnosis.levels[0].claims
    assert claim.fault_type == "harmonic_distortion"
    assert 1_000.0 in claim.bands_hz and "order 3" in claim.statement
    _all_refs(diagnosis)


def test_t_cx461_full_scale_is_clipping_with_frequency_span() -> None:
    diagnosis = diagnose_sweep(
        [(_wav(lambda s: np.clip(2.5 * s, -1.0, 1.0)), "hot")], sample_rate_hz=RATE
    )
    faults = {claim.fault_type for claim in diagnosis.levels[0].claims}
    assert "clipping" in faults
    clipping = next(c for c in diagnosis.levels[0].claims if c.fault_type == "clipping")
    assert "Hz of the sweep" in clipping.statement
    _all_refs(diagnosis)


def test_t_cx461_invalid_recordings_are_inconclusive() -> None:
    rng = np.random.default_rng(20261007)
    stimulus, _ = generate_stimulus(RATE)
    noise = encode_pcm32_wav(
        (0.3 * rng.standard_normal(len(stimulus))).astype(np.float32).reshape(-1, 1),
        sample_rate_hz=RATE,
    )
    diagnosis = diagnose_sweep([(noise, "wrong")], sample_rate_hz=RATE)
    assert diagnosis.outcome == "inconclusive"
    (claim,) = diagnosis.levels[0].claims
    assert "rule_sweep_alignment_acceptable" in claim.statement
    _all_refs(diagnosis)

    drifted = _wav(
        lambda s: np.interp(
            np.arange(int(len(s) * 1.0005)) / 1.0005, np.arange(len(s)), s
        )
    )
    assert (
        diagnose_sweep([(drifted, "drift")], sample_rate_hz=RATE).outcome
        == "inconclusive"
    )

    truncated = encode_pcm32_wav(
        stimulus[: len(stimulus) // 2].astype(np.float32).reshape(-1, 1),
        sample_rate_hz=RATE,
    )
    result = diagnose_sweep([(truncated, "short")], sample_rate_hz=RATE)
    assert result.outcome == "inconclusive"
    assert "rule_sweep_analysis_valid" in result.levels[0].claims[0].statement


def test_t_cx461_multi_level_reports_onset() -> None:
    def device(gain: float) -> Device:
        return lambda s: np.tanh(4 * gain * s) / 4

    recordings = [
        (_wav(device(0.1)), "-20 dB"),
        (_wav(device(0.5)), "-6 dB"),
        (_wav(device(1.5)), "0 dB"),
    ]
    diagnosis = diagnose_sweep(recordings, sample_rate_hz=RATE)
    outcomes = [level.outcome for level in diagnosis.levels]
    assert outcomes[0] == "no_supported_fault" and outcomes[-1] == "supported_fault"
    assert diagnosis.outcome == "supported_fault"
    assert diagnosis.onset_level in {"-6 dB", "0 dB"}
    assert "-20 dB" in diagnosis.summary
    _all_refs(diagnosis)


def test_t_cx461_input_checks() -> None:
    clean = _wav(_clean)
    bad: list[tuple[list[tuple[bytes, str]], int | None, str]] = [
        ([], None, "invalid_request"),
        ([(clean, str(i)) for i in range(4)], None, "invalid_request"),
        ([(clean, "a"), (clean, "a")], None, "invalid_request"),
        ([(clean, " ")], None, "invalid_request"),
        ([(clean, "x" * 65)], None, "invalid_request"),
        ([(clean, "a")], 44_100, "invalid_request"),
        ([(clean, "a")], 32_000, "invalid_request"),
        ([(b"not a wav", "a")], None, "invalid_wav"),
    ]
    for recordings, rate, code in bad:
        with pytest.raises(ApplicationError) as caught:
            diagnose_sweep(recordings, sample_rate_hz=rate)
        assert caught.value.detail.code == code
    assert diagnose_sweep([(clean, "a")]).sample_rate_hz == RATE


def test_t_cx461_ids_are_deterministic() -> None:
    stimulus, _ = generate_stimulus(RATE)
    first = measure_sweep_recording(stimulus, RATE, level_label="x")
    second = measure_sweep_recording(stimulus, RATE, level_label="x")
    assert first == second
    profile = load_sweep_profile()
    assert evaluate_sweep(profile, first) == evaluate_sweep(profile, second)
    assert len({fact.fact_id for fact in first.facts}) == len(first.facts)


def test_t_cx461_noise_is_inconclusive_and_device_clipping_is_harmonic() -> None:
    rng = np.random.default_rng(20261008)
    noisy = diagnose_sweep(
        [(_wav(lambda s: s + 0.05 * rng.standard_normal(len(s))), "noisy")]
    )
    assert noisy.outcome == "inconclusive"
    assert "rule_sweep_snr_acceptable" in noisy.levels[0].claims[0].statement

    clipped = diagnose_sweep([(_wav(lambda s: np.clip(s, -0.4, 0.4)), "device clip")])
    (claim,) = clipped.levels[0].claims
    assert claim.fault_type == "harmonic_distortion"
    orders = {
        band.dominant_order
        for band in clipped.levels[0].measurement.bands
        if band.center_hz in claim.bands_hz
    }
    assert orders <= {3, 5}
