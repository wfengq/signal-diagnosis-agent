"""T224–T233: strict bounded PCM WAV ingestion."""

from __future__ import annotations

import pathlib
import re
import struct
import tempfile

import numpy as np
import pytest
from pydantic import ValidationError

from signal_diag.signal import (
    InMemorySignalRepository,
    InvalidWavError,
    LoadedWav,
    SignalLimitExceededError,
    UnsupportedWavError,
    WavDecodeError,
    WavLoadLimits,
    WavSourceInfo,
    load_wav_bytes,
)

PCM_GUID = bytes.fromhex("0100000000001000800000aa00389b71")
FLOAT_GUID = bytes.fromhex("0300000000001000800000aa00389b71")
SIGNAL_ID_RE = re.compile(r"sig_[0-9a-f]{32}")
PUBLIC_EXPORTS = (
    "WavLoadLimits",
    "WavSourceInfo",
    "LoadedWav",
    "load_wav_bytes",
    "WavDecodeError",
    "UnsupportedWavError",
    "InvalidWavError",
    "SignalLimitExceededError",
)


def _riff_wave(*, fmt_payload: bytes, data: bytes, extra: tuple[bytes, ...] = ()) -> bytes:
    chunks = [b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload]
    chunks.extend(extra)
    chunks.append(b"data" + struct.pack("<I", len(data)) + data)
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
    block_align = channels * bits // 8
    return struct.pack(
        "<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits
    )


def _extensible_pcm_fmt(
    *,
    channels: int,
    rate: int,
    bits: int,
    valid_bits: int | None = None,
    subtype: bytes = PCM_GUID,
) -> bytes:
    if valid_bits is None:
        valid_bits = bits
    block_align = channels * bits // 8
    return (
        struct.pack(
            "<HHIIHHHHI",
            0xFFFE,
            channels,
            rate,
            rate * block_align,
            block_align,
            bits,
            22,
            valid_bits,
            0,
        )
        + subtype
    )


def _riff_from_chunks(*chunks: bytes) -> bytes:
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _fmt_chunk(payload: bytes) -> bytes:
    return b"fmt " + struct.pack("<I", len(payload)) + payload


def _data_chunk(payload: bytes) -> bytes:
    return b"data" + struct.pack("<I", len(payload)) + payload


def _pack_i24(values: list[int]) -> bytes:
    out = bytearray()
    for value in values:
        out.extend((value & 0xFFFFFF).to_bytes(3, "little"))
    return bytes(out)


def _pcm_payload(*, channels: int, bits: int, frames: int) -> bytes:
    count = frames * channels
    if bits == 8:
        return bytes([128] * count)
    if bits == 16:
        return struct.pack(f"<{count}h", *([0] * count))
    if bits == 24:
        return _pack_i24([0] * count)
    if bits == 32:
        return struct.pack(f"<{count}i", *([0] * count))
    raise AssertionError(f"unsupported test bit depth: {bits}")


def _wav_grown_to(target_size: int) -> bytes:
    fmt_payload = _pcm_fmt(channels=1, rate=8_000, bits=16)
    pcm = struct.pack("<hhh", -32768, 0, 32767)
    probe = _riff_wave(fmt_payload=fmt_payload, data=pcm)
    growth = target_size - len(probe)
    payload_size = growth - 8
    extra = b"JUNK" + struct.pack("<I", payload_size) + bytes(payload_size)
    wav = _riff_wave(fmt_payload=fmt_payload, data=pcm, extra=(extra,))
    if len(wav) != target_size:
        raise AssertionError(f"grown WAV size {len(wav)} != {target_size}")
    return wav


def _i16_frames_wav(num_frames: int, *, rate: int) -> bytes:
    payload = np.zeros(num_frames, dtype="<i2")
    payload[0] = -32768
    if num_frames > 1:
        payload[-1] = 32767
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16),
        data=payload.tobytes(),
    )


def test_t224_public_exports_exist_on_signal_package() -> None:
    import signal_diag.signal as signal_pkg

    for name in PUBLIC_EXPORTS:
        assert hasattr(signal_pkg, name)
        assert name in signal_pkg.__all__
    assert signal_pkg.WavDecodeError is WavDecodeError
    assert issubclass(signal_pkg.WavDecodeError, signal_pkg.InvalidSignalError)
    assert issubclass(signal_pkg.UnsupportedWavError, signal_pkg.WavDecodeError)
    assert issubclass(signal_pkg.InvalidWavError, signal_pkg.WavDecodeError)
    assert issubclass(signal_pkg.SignalLimitExceededError, signal_pkg.WavDecodeError)


@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("bits", [8, 16, 24, 32])
def test_t224_standard_pcm_mono_stereo_bit_depths(channels: int, bits: int) -> None:
    rate = 48_000
    frames = 2
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=channels, rate=rate, bits=bits),
        data=_pcm_payload(channels=channels, bits=bits, frames=frames),
    )
    loaded = load_wav_bytes(wav)

    assert isinstance(loaded, LoadedWav)
    assert loaded.source_info.sample_rate_hz == rate
    assert loaded.source_info.channels == channels
    assert loaded.source_info.bits_per_sample == bits
    assert loaded.source_info.format_tag == "pcm"
    assert loaded.source_info.num_frames == frames
    assert loaded.record.meta.source_type == "wav"
    assert loaded.record.samples.shape == (frames, channels)


def test_t225_extensible_pcm_loads_with_matching_valid_bits() -> None:
    wav = _riff_wave(
        fmt_payload=_extensible_pcm_fmt(channels=1, rate=48_000, bits=16),
        data=struct.pack("<hhh", -32768, 0, 32767),
    )
    loaded = load_wav_bytes(wav)
    assert loaded.source_info.format_tag == "extensible_pcm"
    assert loaded.source_info.bits_per_sample == 16
    assert loaded.source_info.num_frames == 3


@pytest.mark.parametrize(
    "wav",
    [
        _riff_wave(
            fmt_payload=struct.pack("<HHIIHH", 3, 1, 8_000, 32_000, 4, 32),
            data=struct.pack("<f", 0.0),
        ),
        _riff_wave(
            fmt_payload=_extensible_pcm_fmt(
                channels=1, rate=8_000, bits=32, subtype=FLOAT_GUID
            ),
            data=struct.pack("<i", 0),
        ),
        b"RIFX"
        + _riff_wave(
            fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
            data=struct.pack("<h", 0),
        )[4:],
        b"RF64"
        + _riff_wave(
            fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
            data=struct.pack("<h", 0),
        )[4:],
        _riff_wave(
            fmt_payload=struct.pack("<HHIIHH", 2, 1, 8_000, 4_000, 1, 4),
            data=b"\x00",
        ),
        _riff_wave(
            fmt_payload=struct.pack("<HHIIHH", 0x11, 1, 8_000, 4_000, 1, 4),
            data=b"\x00",
        ),
        _riff_wave(
            fmt_payload=_extensible_pcm_fmt(
                channels=1, rate=8_000, bits=24, valid_bits=16
            ),
            data=_pack_i24([0]),
        ),
    ],
    ids=[
        "ieee_float_tag3",
        "extensible_float_guid",
        "rifx",
        "rf64",
        "compressed_tag2",
        "compressed_tag11",
        "valid_bits_mismatch",
    ],
)
def test_t225_unsupported_encodings_raise(wav: bytes) -> None:
    with pytest.raises(UnsupportedWavError):
        load_wav_bytes(wav)


def test_t226_int16_mono_extrema_are_exact() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=struct.pack("<hhh", -32768, 0, 32767),
    )
    loaded = load_wav_bytes(wav)
    np.testing.assert_array_equal(
        loaded.record.samples[:, 0],
        np.asarray([-1.0, 0.0, 32767 / 32768], dtype=np.float32),
    )


def test_t226_uint8_offset_extrema() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=8),
        data=bytes([0, 128, 255]),
    )
    loaded = load_wav_bytes(wav)
    np.testing.assert_array_equal(
        loaded.record.samples[:, 0],
        np.asarray([-1.0, 0.0, 127 / 128], dtype=np.float32),
    )


def test_t226_int32_extrema() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=32),
        data=struct.pack("<iii", -(2**31), 0, 2**31 - 1),
    )
    loaded = load_wav_bytes(wav)
    np.testing.assert_array_equal(
        loaded.record.samples[:, 0],
        np.asarray([-1.0, 0.0, (2**31 - 1) / (2**31)], dtype=np.float32),
    )


def test_t226_int24_extrema_and_sign_extension() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=24),
        data=_pack_i24([-(2**23), 0, 2**23 - 1, -1]),
    )
    loaded = load_wav_bytes(wav)
    np.testing.assert_array_equal(
        loaded.record.samples[:, 0],
        np.asarray(
            [-1.0, 0.0, (2**23 - 1) / (2**23), -1 / (2**23)],
            dtype=np.float32,
        ),
    )
    lone_neg = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=24),
        data=b"\xff\xff\xff",
    )
    loaded_neg = load_wav_bytes(lone_neg)
    np.testing.assert_array_equal(
        loaded_neg.record.samples[:, 0],
        np.asarray([-1 / (2**23)], dtype=np.float32),
    )


def test_t226_stereo_interleaving_columns() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=2, rate=8_000, bits=16),
        data=struct.pack("<hhhh", -32768, 0, 0, 32767),
    )
    loaded = load_wav_bytes(wav)
    np.testing.assert_array_equal(
        loaded.record.samples[:, 0],
        np.asarray([-1.0, 0.0], dtype=np.float32),
    )
    np.testing.assert_array_equal(
        loaded.record.samples[:, 1],
        np.asarray([0.0, 32767 / 32768], dtype=np.float32),
    )


def test_t227_canonical_record_and_source_info() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=2, rate=16_000, bits=16),
        data=struct.pack("<hhhh", -32768, 32767, 0, 0),
    )
    loaded = load_wav_bytes(wav, filename="stereo.wav")
    samples = loaded.record.samples
    assert samples.dtype == np.float32
    assert samples.flags.c_contiguous
    assert bool(np.isfinite(samples).all())
    assert samples.shape == (2, 2)
    assert loaded.record.meta.source_type == "wav"
    assert SIGNAL_ID_RE.fullmatch(loaded.record.meta.signal_id)
    assert loaded.source_info.sample_rate_hz == loaded.record.meta.sample_rate_hz
    assert loaded.source_info.channels == loaded.record.meta.channels
    assert loaded.source_info.num_frames == loaded.record.meta.num_samples
    assert loaded.source_info.duration_s == loaded.record.meta.duration_s
    assert loaded.source_info.file_size_bytes == len(wav)
    assert loaded.source_info.filename == "stereo.wav"

    repository = InMemorySignalRepository()
    repository.put(loaded.record)
    snapshot = repository.get(loaded.record.meta.signal_id)
    assert snapshot.samples.flags.writeable is False
    with pytest.raises(ValueError):
        snapshot.samples[0, 0] = 0.5


def test_t228_unknown_junk_chunk_is_skipped() -> None:
    extra = b"JUNK" + struct.pack("<I", 4) + b"xxxx"
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=struct.pack("<h", 0),
        extra=(extra,),
    )
    loaded = load_wav_bytes(wav)
    assert loaded.source_info.num_frames == 1


def test_t228_odd_size_chunk_consumes_pad_byte() -> None:
    extra = b"JUNK" + struct.pack("<I", 1) + b"Z"
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=8),
        data=bytes([128]),
        extra=(extra,),
    )
    loaded = load_wav_bytes(wav)
    assert loaded.source_info.num_frames == 1
    np.testing.assert_array_equal(
        loaded.record.samples[:, 0],
        np.asarray([0.0], dtype=np.float32),
    )


def test_t228_legal_extra_chunk_before_and_after_fmt() -> None:
    junk = b"JUNK" + struct.pack("<I", 4) + b"xxxx"
    wav = _riff_from_chunks(
        junk,
        _fmt_chunk(_pcm_fmt(channels=1, rate=8_000, bits=16)),
        junk,
        _data_chunk(struct.pack("<h", 0)),
        junk,
    )
    loaded = load_wav_bytes(wav)
    assert loaded.source_info.num_frames == 1


def test_t228_declared_chunk_size_checked_before_allocation() -> None:
    fmt = _fmt_chunk(_pcm_fmt(channels=1, rate=8_000, bits=16))
    junk_header = b"JUNK" + struct.pack("<I", 0x7FFFFFFF)
    wav = _riff_from_chunks(fmt, junk_header)
    with pytest.raises(InvalidWavError):
        load_wav_bytes(wav)


def test_t229_missing_fmt() -> None:
    wav = _riff_from_chunks(_data_chunk(struct.pack("<h", 0)))
    with pytest.raises(InvalidWavError):
        load_wav_bytes(wav)


def test_t229_missing_data() -> None:
    wav = _riff_from_chunks(_fmt_chunk(_pcm_fmt(channels=1, rate=8_000, bits=16)))
    with pytest.raises(InvalidWavError):
        load_wav_bytes(wav)


def test_t229_duplicate_fmt_even_if_identical() -> None:
    fmt = _fmt_chunk(_pcm_fmt(channels=1, rate=8_000, bits=16))
    wav = _riff_from_chunks(fmt, fmt, _data_chunk(struct.pack("<h", 0)))
    with pytest.raises(InvalidWavError):
        load_wav_bytes(wav)


def test_t229_duplicate_data_even_if_identical() -> None:
    data = _data_chunk(struct.pack("<h", 0))
    wav = _riff_from_chunks(
        _fmt_chunk(_pcm_fmt(channels=1, rate=8_000, bits=16)),
        data,
        data,
    )
    with pytest.raises(InvalidWavError):
        load_wav_bytes(wav)


def test_t229_truncation_and_bad_riff_size() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=struct.pack("<hhh", -32768, 0, 32767),
    )
    with pytest.raises(InvalidWavError):
        load_wav_bytes(wav[:-5])
    bad_size = wav[:4] + struct.pack("<I", 12) + wav[8:]
    with pytest.raises(InvalidWavError):
        load_wav_bytes(bad_size)


def test_t229_partial_frame_bad_byte_rate_bad_block_align() -> None:
    with pytest.raises(InvalidWavError):
        load_wav_bytes(
            _riff_wave(
                fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
                data=b"\x00\x00\x00",
            )
        )
    with pytest.raises(InvalidWavError):
        load_wav_bytes(
            _riff_wave(
                fmt_payload=struct.pack("<HHIIHH", 1, 1, 8_000, 9999, 2, 16),
                data=struct.pack("<h", 0),
            )
        )
    with pytest.raises(InvalidWavError):
        load_wav_bytes(
            _riff_wave(
                fmt_payload=struct.pack("<HHIIHH", 1, 1, 8_000, 8_000, 1, 16),
                data=struct.pack("<h", 0),
            )
        )


def test_t229_data_before_fmt_leftover_and_zero_channels() -> None:
    with pytest.raises(InvalidWavError):
        load_wav_bytes(
            _riff_from_chunks(
                _data_chunk(struct.pack("<h", 0)),
                _fmt_chunk(_pcm_fmt(channels=1, rate=8_000, bits=16)),
            )
        )
    complete = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=struct.pack("<h", 0),
    )
    leftover = complete + b"xxx"
    leftover = b"RIFF" + struct.pack("<I", len(leftover) - 8) + leftover[8:]
    with pytest.raises(InvalidWavError):
        load_wav_bytes(leftover)
    with pytest.raises(InvalidWavError):
        load_wav_bytes(
            _riff_wave(
                fmt_payload=struct.pack("<HHIIHH", 1, 0, 8_000, 0, 0, 16),
                data=b"",
            )
        )


def test_t230_three_channels_is_unsupported_without_record() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=3, rate=8_000, bits=16),
        data=struct.pack("<hhh", 0, 0, 0),
    )
    with pytest.raises(UnsupportedWavError):
        load_wav_bytes(wav)


def test_t230_unsupported_encoding_raises() -> None:
    wav = _riff_wave(
        fmt_payload=struct.pack("<HHIIHH", 0x06, 1, 8_000, 8_000, 1, 8),
        data=b"\x00",
    )
    with pytest.raises(UnsupportedWavError):
        load_wav_bytes(wav)


def test_t231_exactly_20_mib_is_eligible_to_parse() -> None:
    limits = WavLoadLimits()
    assert limits.max_upload_bytes == 20 * 1024 * 1024
    wav = _wav_grown_to(20 * 1024 * 1024)
    loaded = load_wav_bytes(wav)
    assert loaded.source_info.file_size_bytes == 20 * 1024 * 1024
    np.testing.assert_array_equal(
        loaded.record.samples[:, 0],
        np.asarray([-1.0, 0.0, 32767 / 32768], dtype=np.float32),
    )


def test_t231_one_byte_over_limit_raises_immediately() -> None:
    blob = b"\x00" * (20 * 1024 * 1024 + 1)
    with pytest.raises(SignalLimitExceededError):
        load_wav_bytes(blob)
    del blob


def test_t232_inclusive_sample_rate_bounds() -> None:
    limits = WavLoadLimits()
    assert limits.min_sample_rate_hz == 8_000
    assert limits.max_sample_rate_hz == 192_000
    for rate in (8_000, 192_000):
        wav = _riff_wave(
            fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16),
            data=struct.pack("<hhh", -32768, 0, 32767),
        )
        loaded = load_wav_bytes(wav)
        np.testing.assert_array_equal(
            loaded.record.samples[:, 0],
            np.asarray([-1.0, 0.0, 32767 / 32768], dtype=np.float32),
        )
        assert loaded.source_info.sample_rate_hz == rate
    for rate in (7_999, 192_001):
        wav = _riff_wave(
            fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16),
            data=struct.pack("<h", -32768),
        )
        with pytest.raises(SignalLimitExceededError):
            load_wav_bytes(wav)


def test_t232_frame_and_duration_limits() -> None:
    limits = WavLoadLimits()
    assert limits.max_sample_frames == 2_000_000
    assert limits.max_duration_s == 30.0

    two_million = _i16_frames_wav(2_000_000, rate=192_000)
    loaded = load_wav_bytes(two_million)
    assert loaded.source_info.num_frames == 2_000_000
    assert loaded.source_info.duration_s < 30.0
    assert loaded.record.samples[0, 0] == np.float32(-1.0)
    assert loaded.record.samples[-1, 0] == np.float32(32767 / 32768)

    with pytest.raises(SignalLimitExceededError):
        load_wav_bytes(_i16_frames_wav(2_000_001, rate=192_000))

    exact_30s = _i16_frames_wav(240_000, rate=8_000)
    loaded_30s = load_wav_bytes(exact_30s)
    assert loaded_30s.source_info.num_frames == 240_000
    assert loaded_30s.source_info.duration_s == 30.0
    assert loaded_30s.record.samples[0, 0] == np.float32(-1.0)

    with pytest.raises(SignalLimitExceededError):
        load_wav_bytes(_i16_frames_wav(240_001, rate=8_000))


def test_t232_rate_interval_min_must_not_exceed_max() -> None:
    with pytest.raises(ValidationError):
        WavLoadLimits(min_sample_rate_hz=48_000, max_sample_rate_hz=8_000)


def test_t233_filename_basename_and_code_point_truncation() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=struct.pack("<h", 0),
    )
    loaded = load_wav_bytes(wav, filename=r"C:\tmp\dir/foo.wav")
    assert loaded.source_info.filename == "foo.wav"

    long_name = "\u4e00" * 300
    loaded_long = load_wav_bytes(wav, filename=r"C:\tmp/" + long_name)
    assert loaded_long.source_info.filename == "\u4e00" * 255
    assert len(loaded_long.source_info.filename) == 255


def test_t233_repeated_loads_get_distinct_opaque_ids() -> None:
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=struct.pack("<h", 0),
    )
    first = load_wav_bytes(wav, filename="clipping.wav")
    second = load_wav_bytes(wav, filename="clipping.wav")
    assert SIGNAL_ID_RE.fullmatch(first.record.meta.signal_id)
    assert SIGNAL_ID_RE.fullmatch(second.record.meta.signal_id)
    assert first.record.meta.signal_id != second.record.meta.signal_id
    assert "clipping" not in first.record.meta.signal_id
    assert "clipping" not in second.record.meta.signal_id


def test_t233_load_does_not_use_tempfile_or_path_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("temp file or path write invoked")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", _fail)
    monkeypatch.setattr(tempfile, "mkstemp", _fail)
    monkeypatch.setattr(pathlib.Path, "write_bytes", _fail)
    wav = _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=struct.pack("<h", 0),
    )
    loaded = load_wav_bytes(wav, filename=r"C:\tmp\dir/foo.wav")
    assert loaded.source_info.filename == "foo.wav"
    assert isinstance(loaded.source_info, WavSourceInfo)
