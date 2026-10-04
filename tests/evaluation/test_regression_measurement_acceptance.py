"""Phase A offline acceptance for regression measurement and compare."""

from __future__ import annotations

import hashlib
import math
import struct

import numpy as np

from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.rules.regression import ComparisonConditions, compare_measurements
from signal_diag.signal import (
    InMemorySignalRepository,
    TimeRange,
    generate_clipped_sine,
    generate_sine,
    generate_white_noise,
    load_wav_bytes,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.regression_measurement import (
    InputIdentity,
    MeasurementBundle,
    MeasurementSelection,
    ToolParameterSnapshot,
    measure_output,
)
from tests.rules.regression_fixtures import build_fixture_clipping_profile


def _conditions() -> ComparisonConditions:
    return ComparisonConditions(
        baseline_version="accept-base",
        candidate_version="accept-cand",
        stimulus_key="phase-a",
        parameters_key="seeded",
        same_input="yes",
        parameters_unchanged="yes",
        aligned_ranges="yes",
        repeatability="declared_deterministic",
    )


def _selection(
    *,
    channel: str = "left",
    time_range: TimeRange | None = None,
    fundamental_hz: float | None = 200.0,
) -> MeasurementSelection:
    tr = time_range or TimeRange()
    return MeasurementSelection(
        clipping=ClippingInput(channel=channel, time_range=tr),
        harmonic=HarmonicDistortionInput(
            channel=channel,
            time_range=tr,
            fundamental_hz=fundamental_hz,
        ),
    )


def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
    block_align = channels * (bits // 8)
    return struct.pack("<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits)


def _riff_wave(*, fmt_payload: bytes, data: bytes) -> bytes:
    chunks = [
        b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload,
        b"data" + struct.pack("<I", len(data)) + data,
    ]
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _stereo_wav_bytes() -> bytes:
    rate = 48_000
    frames = 2_048
    t = np.arange(frames, dtype=np.float64) / rate
    left = (0.35 * np.sin(2 * math.pi * 200.0 * t)).astype(np.float64)
    right = (0.35 * np.sin(2 * math.pi * 500.0 * t)).astype(np.float64)
    interleaved = np.empty(frames * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(np.rint(left * 32767.0), -32768, 32767)
    interleaved[1::2] = np.clip(np.rint(right * 32767.0), -32768, 32767)
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=2, rate=rate, bits=16),
        data=interleaved.tobytes(),
    )


def _measure_side(
    *,
    wav_bytes: bytes,
    run_id: str,
    side: str,
    selection: MeasurementSelection,
) -> tuple[MeasurementBundle, InMemorySignalRepository]:
    repository = InMemorySignalRepository()
    loaded = load_wav_bytes(wav_bytes, filename=f"{side}.wav")
    repository.put(loaded.record)
    signal_id = loaded.record.meta.signal_id
    wav_sha = hashlib.sha256(wav_bytes).hexdigest()
    tr = selection.clipping.time_range or TimeRange()
    start = round(tr.start_s * loaded.record.meta.sample_rate_hz)
    end = (
        loaded.record.meta.num_samples
        if tr.end_s is None
        else min(
            round(tr.end_s * loaded.record.meta.sample_rate_hz),
            loaded.record.meta.num_samples,
        )
    )
    identity = InputIdentity(
        run_id=run_id,
        side=side,
        wav_sha256=wav_sha,
        signal_id=signal_id,
        sample_rate_hz=loaded.record.meta.sample_rate_hz,
        source_channels=loaded.record.meta.channels,
        total_frames=loaded.record.meta.num_samples,
        resolved_start_sample=start,
        resolved_end_sample=end,
        channel=selection.clipping.channel,
        tool_parameter_snapshot=ToolParameterSnapshot(
            clipping=selection.clipping,
            harmonic=selection.harmonic,
        ),
    )
    bundle = measure_output(
        repository=repository,
        identity=identity,
        selection=selection,
    )
    return bundle, repository


def _compare_pair(
    baseline_bytes: bytes,
    candidate_bytes: bytes,
    *,
    selection: MeasurementSelection,
    profile,
):
    baseline, _ = _measure_side(
        wav_bytes=baseline_bytes,
        run_id="acc_base",
        side="baseline",
        selection=selection,
    )
    candidate, _ = _measure_side(
        wav_bytes=candidate_bytes,
        run_id="acc_cand",
        side="candidate",
        selection=selection,
    )
    return compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )


def test_acceptance_identical_sine_descriptive_and_fixture() -> None:
    sine = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.3,
        amplitude=0.45,
    )
    wav = encode_pcm32_wav(sine.record.samples, sample_rate_hz=48_000)
    selection = _selection()
    descriptive = _compare_pair(wav, wav, selection=selection, profile=None)
    clip_row = next(
        item for item in descriptive.metric_comparisons if item.metric == "clipping_ratio"
    )
    assert clip_row.status == "descriptive_only"
    assert descriptive.overall_regression_pass is None

    fixture = _compare_pair(
        wav,
        wav,
        selection=selection,
        profile=build_fixture_clipping_profile(),
    )
    clip_fixture = next(
        item for item in fixture.metric_comparisons if item.metric == "clipping_ratio"
    )
    assert clip_fixture.status == "no_regression_detected"


def test_acceptance_added_clipping_and_both_clipped() -> None:
    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.3,
        amplitude=0.45,
    )
    clipped = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.3,
        amplitude=0.95,
        clip_level=0.4,
    )
    clean_wav = encode_pcm32_wav(clean.record.samples, sample_rate_hz=48_000)
    clip_wav = encode_pcm32_wav(clipped.record.samples, sample_rate_hz=48_000)
    selection = _selection()
    profile = build_fixture_clipping_profile()

    added = _compare_pair(clean_wav, clip_wav, selection=selection, profile=profile)
    assert next(
        item for item in added.metric_comparisons if item.metric == "clipping_ratio"
    ).status == "regression_detected"

    both = _compare_pair(clip_wav, clip_wav, selection=selection, profile=profile)
    facts = {item.side: item for item in both.clipping_facts}
    assert facts["baseline"].flat_top_detected is True
    assert facts["candidate"].flat_top_detected is True


def test_acceptance_harmonic_not_applicable_stereo_and_truncated_range() -> None:
    noise = generate_white_noise(sample_rate_hz=48_000, duration_s=0.3, seed=31)
    noise_wav = encode_pcm32_wav(noise.record.samples, sample_rate_hz=48_000)
    selection = _selection(fundamental_hz=200.0)
    record = _compare_pair(noise_wav, noise_wav, selection=selection, profile=None)
    thd = next(item for item in record.metric_comparisons if item.metric == "thd_percent")
    assert thd.status == "not_comparable"
    assert thd.reason_codes[0] == "harmonic_tool_not_success"

    stereo = _stereo_wav_bytes()
    left_sel = _selection(channel="left")
    right_sel = _selection(channel="right")
    left_bundle, _ = _measure_side(
        wav_bytes=stereo, run_id="st_l", side="baseline", selection=left_sel
    )
    right_bundle, _ = _measure_side(
        wav_bytes=stereo, run_id="st_r", side="baseline", selection=right_sel
    )
    left_clip = next(
        item.value
        for item in left_bundle.clipping.evidence
        if item.metric == "clipping_ratio"
    )
    right_clip = next(
        item.value
        for item in right_bundle.clipping.evidence
        if item.metric == "clipping_ratio"
    )
    assert left_clip != right_clip

    sine = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.5,
        amplitude=0.4,
    )
    wav = encode_pcm32_wav(sine.record.samples, sample_rate_hz=48_000)
    truncated = _selection(time_range=TimeRange(start_s=0.1, end_s=0.2))
    truncated_record = _compare_pair(wav, wav, selection=truncated, profile=None)
    assert (
        truncated_record.baseline_bundle.identity.resolved_end_sample
        > truncated_record.baseline_bundle.identity.resolved_start_sample
    )
