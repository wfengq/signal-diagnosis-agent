from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from pydantic import ValidationError

from signal_diag.signal.exceptions import InvalidSignalError
from signal_diag.signal.factory import build_signal_record
from signal_diag.signal.models import SignalMeta, SignalRecord


def test_t001_mono_is_canonical_float32() -> None:
    samples = np.array([0.0, 0.1, -0.2], dtype=np.float64)
    record = build_signal_record(
        samples,
        sample_rate_hz=48_000,
        source_type="generated",
    )

    assert record.samples.shape == (3, 1)
    assert record.samples.dtype == np.float32
    assert record.samples.flags.c_contiguous
    assert record.samples.flags.owndata
    assert not np.shares_memory(record.samples, samples)


def test_t002_float_input_is_not_peak_normalized() -> None:
    record = build_signal_record(
        np.array([0.0, 0.25, -0.5], dtype=np.float64),
        sample_rate_hz=48_000,
        source_type="generated",
    )

    assert np.max(np.abs(record.samples)) == pytest.approx(0.5, abs=1e-6)


def test_t003_int16_uses_signed_full_scale() -> None:
    record = build_signal_record(
        np.array([-32768, 0, 32767], dtype=np.int16),
        sample_rate_hz=48_000,
        source_type="generated",
    )

    np.testing.assert_allclose(
        record.samples[:, 0],
        [-1.0, 0.0, 32767 / 32768],
        atol=1e-6,
    )
    assert record.meta.original_dtype == "int16"


@pytest.mark.parametrize(
    ("samples", "sample_rate_hz"),
    [
        (np.array([], dtype=np.float64), 48_000),
        (np.array([np.nan]), 48_000),
        (np.array([np.inf]), 48_000),
        (np.array(0.0), 48_000),
        (np.zeros((1, 1, 1)), 48_000),
        (np.array([0.0]), 0),
        (np.array([0.0]), -1),
    ],
)
def test_t004_invalid_signal_inputs_raise_explicitly(
    samples: np.ndarray, sample_rate_hz: int
) -> None:
    with pytest.raises(InvalidSignalError):
        build_signal_record(
            samples,
            sample_rate_hz=sample_rate_hz,
            source_type="generated",
        )


def test_t005_unsigned_pcm_is_rejected() -> None:
    with pytest.raises(InvalidSignalError, match="unsigned PCM"):
        build_signal_record(
            np.array([0, 255], dtype=np.uint8),
            sample_rate_hz=48_000,
            source_type="pcm",
        )


def test_t006_metadata_record_invariants_and_generated_id() -> None:
    record = build_signal_record(
        np.array([0.0, 0.25, -0.5], dtype=np.float64),
        sample_rate_hz=48_000,
        source_type="generated",
    )

    assert record.meta.signal_id.startswith("sig_")
    assert record.meta.num_samples == 3
    assert record.meta.channels == 1
    assert record.meta.duration_s == pytest.approx(3 / 48_000, abs=1e-12)
    assert SignalRecord.__slots__ == ("meta", "samples")
    with pytest.raises(FrozenInstanceError):
        record.meta = record.meta

    with pytest.raises(ValidationError):
        build_signal_record(
            np.array([0.0], dtype=np.float32),
            sample_rate_hz=48_000,
            source_type="generated",
            signal_id="",
        )

    with pytest.raises(ValidationError):
        SignalMeta(
            signal_id="sig_direct",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=3,
            duration_s=1.0,
            original_dtype="float32",
        )

    invalid_meta = SignalMeta(
        signal_id="sig_direct",
        source_type="generated",
        sample_rate_hz=48_000,
        channels=2,
        num_samples=3,
        duration_s=3 / 48_000,
        original_dtype="float32",
    )
    with pytest.raises(InvalidSignalError):
        SignalRecord(meta=invalid_meta, samples=np.zeros((3, 1), dtype=np.float32))
