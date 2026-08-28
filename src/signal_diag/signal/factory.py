"""Construction of canonical signal records."""

from uuid import uuid4

import numpy as np

from .exceptions import InvalidSignalError
from .models import SignalMeta, SignalRecord, SourceType


def _to_float32(samples: np.ndarray) -> np.ndarray:
    if np.issubdtype(samples.dtype, np.unsignedinteger):
        raise InvalidSignalError("unsigned PCM is not supported in V0.2")
    if np.issubdtype(samples.dtype, np.signedinteger):
        bits = np.iinfo(samples.dtype).bits
        scaled = samples.astype(np.float64) / float(2 ** (bits - 1))
        return scaled.astype(np.float32)
    if np.issubdtype(samples.dtype, np.floating):
        return samples.astype(np.float32, copy=True)
    raise InvalidSignalError(f"unsupported dtype: {samples.dtype}")


def build_signal_record(
    samples: np.ndarray,
    *,
    sample_rate_hz: int,
    source_type: SourceType,
    filename: str | None = None,
    signal_id: str | None = None,
) -> SignalRecord:
    """Validate and canonicalize a source waveform without peak normalization."""
    if sample_rate_hz <= 0:
        raise InvalidSignalError("sample_rate_hz must be positive")
    if not isinstance(samples, np.ndarray):
        raise InvalidSignalError("samples must be a numpy array")
    if samples.ndim not in (1, 2):
        raise InvalidSignalError("samples must have rank 1 or 2")
    if samples.size == 0:
        raise InvalidSignalError("samples must not be empty")
    if not (np.issubdtype(samples.dtype, np.integer) or np.issubdtype(samples.dtype, np.floating)):
        raise InvalidSignalError(f"unsupported dtype: {samples.dtype}")
    if not np.isfinite(samples).all():
        raise InvalidSignalError("samples must be finite")

    original_dtype = str(samples.dtype)
    values = _to_float32(samples)
    if values.ndim == 1:
        values = values[:, None]
    values = np.array(values, dtype=np.float32, order="C", copy=True)

    num_samples, channels = values.shape
    metadata = SignalMeta(
        signal_id=f"sig_{uuid4().hex}" if signal_id is None else signal_id,
        source_type=source_type,
        filename=filename,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        num_samples=num_samples,
        duration_s=num_samples / sample_rate_hz,
        original_dtype=original_dtype,
    )
    return SignalRecord(meta=metadata, samples=values)
