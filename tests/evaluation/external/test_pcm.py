"""Checkpoint D — PCM derivation and WAV loader compatibility (EV-T015–EV-T020)."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from signal_diag.evaluation.external.models import DerivationSpec
from signal_diag.evaluation.external.pcm import (
    PcmDerivationError,
    derive_analysis_wav,
    encode_pcm24_mono,
    read_pcm_window,
)
from signal_diag.signal.wav import load_wav_bytes


def write_pcm_fixture(
    path: Path,
    channels: np.ndarray,
    *,
    sample_rate_hz: int = 48_000,
    sample_width_bytes: int = 2,
) -> Path:
    _frames, nchannels = channels.shape
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(nchannels)
        handle.setsampwidth(sample_width_bytes)
        handle.setframerate(sample_rate_hz)
        if sample_width_bytes == 1:
            payload = channels.astype(np.uint8).tobytes()
        elif sample_width_bytes == 2:
            payload = channels.astype("<i2").tobytes()
        elif sample_width_bytes == 3:
            payload = _pack_i24(channels.astype(np.int32))
        elif sample_width_bytes == 4:
            payload = channels.astype("<i4").tobytes()
        else:
            raise AssertionError(f"unsupported sample width: {sample_width_bytes}")
        handle.writeframes(payload)
    return path


def write_pcm16_fixture(path: Path, channels: np.ndarray) -> Path:
    return write_pcm_fixture(path, channels, sample_width_bytes=2)


def _pack_i24(values: np.ndarray) -> bytes:
    out = bytearray()
    for value in values.reshape(-1):
        out.extend(int(value).to_bytes(3, "little", signed=True))
    return bytes(out)


@pytest.mark.parametrize(
    ("sample_width_bytes", "values", "expected"),
    [
        (1, np.array([[128]], dtype=np.uint8), np.array([0.0], dtype=np.float32)),
        (2, np.array([[-16384]], dtype=np.int16), np.array([-0.5], dtype=np.float32)),
        (
            3,
            np.array([[0], [1 << 22]], dtype=np.int32),
            np.array([0.0, 0.5], dtype=np.float32),
        ),
        (
            4,
            np.array([[-(1 << 30)]], dtype=np.int32),
            np.array([-0.5], dtype=np.float32),
        ),
    ],
)
def test_ev_t015_signed_pcm_conversion_maps_to_full_scale_float32(
    tmp_path: Path,
    sample_width_bytes: int,
    values: np.ndarray,
    expected: np.ndarray,
) -> None:
    source = tmp_path / f"source_{sample_width_bytes}.wav"
    write_pcm_fixture(source, values, sample_width_bytes=sample_width_bytes)
    window = read_pcm_window(
        source,
        DerivationSpec(channel_index=0, start_frame=0, stop_frame=values.shape[0]),
    )
    np.testing.assert_allclose(window.samples, expected, rtol=0.0, atol=2**-23)


def test_ev_t016_selected_channel_is_extracted_from_multichannel_source(
    tmp_path: Path,
) -> None:
    channels = np.zeros((1, 48), dtype=np.int16)
    channels[0, 1] = 48
    source = tmp_path / "forty_eight.wav"
    write_pcm_fixture(source, channels, sample_width_bytes=2)
    window = read_pcm_window(
        source,
        DerivationSpec(channel_index=1, start_frame=0, stop_frame=1),
    )
    assert window.source_channels == 48
    np.testing.assert_allclose(
        window.samples,
        np.array([48 / 2**15], dtype=np.float32),
        atol=2**-23,
    )


def test_ev_t017_frame_crop_is_left_closed_right_open(tmp_path: Path) -> None:
    channels = np.arange(6, dtype=np.int16).reshape(-1, 1)
    source = tmp_path / "crop.wav"
    write_pcm16_fixture(source, channels)
    window = read_pcm_window(
        source,
        DerivationSpec(channel_index=0, start_frame=2, stop_frame=5),
    )
    np.testing.assert_allclose(
        window.samples,
        np.array([2 / 2**15, 3 / 2**15, 4 / 2**15], dtype=np.float32),
        atol=2**-23,
    )


def test_ev_t018_derived_pcm24_loads_without_peak_normalization(tmp_path: Path) -> None:
    source = write_pcm16_fixture(
        tmp_path / "source.wav",
        channels=np.array([[-16384, 8192], [16384, -8192]], dtype=np.int16),
    )
    destination = tmp_path / "extwav_development_0123456789abcdef.wav"
    derived = derive_analysis_wav(
        source,
        DerivationSpec(channel_index=0, start_frame=0, stop_frame=2),
        destination,
    )
    loaded = load_wav_bytes(
        Path(derived.path).read_bytes(),
        filename=Path(derived.path).name,
    )
    np.testing.assert_allclose(
        loaded.record.samples[:, 0],
        np.array([-0.5, 0.5], dtype=np.float32),
        atol=2**-23,
    )


def test_ev_t019_output_bounds_are_enforced(tmp_path: Path) -> None:
    channels = np.zeros((2_000_001, 1), dtype=np.int16)
    source = tmp_path / "too_many_frames.wav"
    write_pcm16_fixture(source, channels)
    destination = tmp_path / "extwav_development_0123456789abcdef.wav"
    with pytest.raises(PcmDerivationError, match="frame count exceeds"):
        derive_analysis_wav(
            source,
            DerivationSpec(channel_index=0, start_frame=0, stop_frame=2_000_001),
            destination,
        )


def test_ev_t020_destination_must_not_exist(tmp_path: Path) -> None:
    source = write_pcm16_fixture(
        tmp_path / "source.wav",
        channels=np.array([[0], [0]], dtype=np.int16),
    )
    destination = tmp_path / "extwav_development_0123456789abcdef.wav"
    destination.write_bytes(b"placeholder")
    with pytest.raises(FileExistsError):
        derive_analysis_wav(
            source,
            DerivationSpec(channel_index=0, start_frame=0, stop_frame=1),
            destination,
        )
    assert destination.read_bytes() == b"placeholder"


def test_derive_analysis_wav_rejects_invalid_destination_name(tmp_path: Path) -> None:
    source = write_pcm16_fixture(
        tmp_path / "source.wav",
        channels=np.array([[0]], dtype=np.int16),
    )
    destination = tmp_path / "not_truth_free.wav"
    with pytest.raises(PcmDerivationError, match="analysis filename"):
        derive_analysis_wav(
            source,
            DerivationSpec(channel_index=0, start_frame=0, stop_frame=1),
            destination,
        )


def test_encode_pcm24_mono_writes_valid_riff_payload() -> None:
    samples = np.array([-0.5, 0.5], dtype=np.float32)
    payload = encode_pcm24_mono(samples, sample_rate_hz=48_000)
    loaded = load_wav_bytes(payload, filename="extwav_development_0123456789abcdef.wav")
    np.testing.assert_allclose(
        loaded.record.samples[:, 0],
        samples,
        atol=2**-23,
    )
    assert loaded.source_info.bits_per_sample == 24
    assert loaded.source_info.channels == 1


def test_read_pcm_window_rejects_compressed_source(tmp_path: Path) -> None:
    source = tmp_path / "compressed.wav"
    source.write_bytes(b"not a wav")
    with pytest.raises(PcmDerivationError):
        read_pcm_window(
            source,
            DerivationSpec(channel_index=0, start_frame=0, stop_frame=1),
        )
