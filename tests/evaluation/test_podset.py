"""T-CX480–T-CX482: pOD-set validation harness (D056). Nothing is downloaded."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.dsp.sweep import BandResult, analyze_known_sweep
from signal_diag.evaluation.podset import (
    CRITERIA,
    GAINS,
    LEVELS,
    RATE,
    TONE,
    RangeReader,
    RecordingResult,
    alias_free,
    evaluate,
    extract_members,
    run,
    short_time_band_thd,
    sweep_member_names,
    synthetic_check,
)


def _dry(peak: float) -> np.ndarray:
    rate_l = 4.0 / np.log(24_000 / 5.0)
    t = np.arange(4 * RATE) / RATE
    return peak * np.sin(2 * np.pi * 5.0 * rate_l * (np.exp(t / rate_l) - 1))


def _wav(samples: np.ndarray) -> bytes:
    return encode_pcm32_wav(samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=RATE)


def _pedal(drive: float):  # type: ignore[no-untyped-def]
    return lambda x: np.tanh(drive * x) / max(drive, 1.0)


def test_t_cx480_range_reader_extracts_only_named_members(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("p/s0_p_g0_t3.wav", b"abc")
        archive.writestr("p/a_p_g0_t3.wav", b"large main audio")
    data = buffer.getvalue()
    calls: list[tuple[int, int]] = []

    def read_range(start: int, end: int) -> bytes:
        calls.append((start, end))
        return data[start : end + 1]

    entries = extract_members(RangeReader(len(data), read_range), ["p/s0_p_g0_t3.wav"], tmp_path)
    assert entries == [
        {"path": "p/s0_p_g0_t3.wav", "bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}
    ]
    assert (tmp_path / "p/s0_p_g0_t3.wav").read_bytes() == b"abc"
    assert not (tmp_path / "p/a_p_g0_t3.wav").exists() and calls
    names = sweep_member_names("ped")
    assert len(names) == len(GAINS) * len(LEVELS) == 18
    assert all(name.endswith(f"_t{TONE}.wav") for name in names)


def test_t_cx481_synthetic_check_and_cross_check_agree() -> None:
    dry = _dry(0.63)
    check = synthetic_check(dry)
    assert check["passed"], check
    assert check["worst_abs_error_pp"] <= CRITERIA["synthetic_abs_pp"]
    recording = alias_free(_pedal(3.0), dry)
    analysis = analyze_known_sweep(recording, dry, RATE)
    for center in (1_000.0, 2_000.0, 4_000.0):
        band = next(b for b in analysis.bands if b.center_hz == center)
        short_time = short_time_band_thd(
            recording,
            rate_l=analysis.rate_l,
            start_frequency_hz=analysis.start_frequency_hz,
            lag=analysis.lag_samples,
            center_hz=center,
            orders=band.orders_used,
        )
        assert band.thd_percent is not None and short_time is not None
        assert short_time == pytest.approx(band.thd_percent, rel=0.15, abs=0.3), center


def _result(pedal: str, gain: int, level: str, thd: float, cross: float | None) -> RecordingResult:
    band = BandResult(1_000.0, True, thd, 0.01, 3, (2, 3, 4))
    return RecordingResult(pedal, gain, level, 0, (band,), {1_000.0: cross})


def test_t_cx481_criteria_count_violations() -> None:
    labels = [label for _, label in LEVELS]
    rising = [
        _result("p", gain, level, 1.0 + gain + 2 * index, 1.0 + gain + 2 * index)
        for gain in GAINS
        for index, level in enumerate(labels)
    ]
    summary = evaluate(rising)
    assert summary["level_monotone"]["share"] == 1.0 and summary["level_monotone"]["passed"]
    assert summary["gain_monotone"]["share"] == 1.0 and summary["cross_check"]["passed"]
    assert summary["low_gain"]["median_by_pedal"] == {"p": 3.0}
    falling = [
        _result("p", gain, level, 20.0 - 3 * index, 1.0)
        for gain in GAINS
        for index, level in enumerate(labels)
    ]
    summary = evaluate(falling)
    assert summary["level_monotone"]["share"] == 0.0 and not summary["level_monotone"]["passed"]
    assert summary["cross_check"]["share"] == 0.0 and not summary["cross_check"]["passed"]
    small_drop = [_result("q", 0, labels[0], 2.0, None), _result("q", 0, labels[1], 1.85, None)]
    assert evaluate(small_drop)["level_monotone"]["share"] == 1.0


def test_t_cx482_end_to_end_on_a_simulated_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    peaks = {"s0": 0.63, "s1": 0.32, "s2": 0.08}
    files = []

    def put(name: str, data: bytes) -> None:
        target = cache / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    for prefix, _ in LEVELS:
        put(f"input/{prefix}_0-input.wav", _wav(_dry(peaks[prefix])))
    for pedal in ("fakeod", "kingoftone"):
        for gain in GAINS:
            for prefix, _ in LEVELS:
                response = alias_free(_pedal(1.0 + 2.0 * gain), _dry(peaks[prefix]))
                put(f"{pedal}/{prefix}_{pedal}_g{gain}_t{TONE}.wav", _wav(0.9 * response / np.max(np.abs(response))))
    manifest = {
        "dataset": "pOD-set", "doi": "x", "license": "CC BY-NC 4.0", "attribution": "x",
        "pedals": ["fakeod", "kingoftone"], "gain_indices": list(GAINS), "tone_index": TONE,
        "levels": [label for _, label in LEVELS], "files": files,
    }
    (cache / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "out"
    report = run(cache, out)
    assert report["synthetic_check"]["passed"]
    assert report["all_pedals"]["recordings"] == 36
    assert report["without_design_pedal"]["recordings"] == 18
    assert report["all_pedals"]["level_monotone"]["passed"]
    assert report["all_pedals"]["gain_monotone"]["passed"]
    assert report["onset_at_demo_limit"]["fakeod"]["0"] is None
    assert report["onset_at_demo_limit"]["fakeod"]["5"] is not None
    assert report["model_calls"] == 0
    assert sorted(p.name for p in out.iterdir()) == ["manifest.json", "results.json", "summary.json"]
    assert not any(p.suffix == ".wav" for p in out.rglob("*"))

    (cache / files[3]["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        run(cache, tmp_path / "again")


def test_t_cx480_transient_network_errors_are_retried() -> None:
    import urllib.error

    from signal_diag.evaluation.podset import with_retries

    attempts: list[int] = []
    waits: list[float] = []

    def flaky() -> bytes:
        attempts.append(1)
        if len(attempts) < 3:
            raise urllib.error.URLError("EOF occurred in violation of protocol")
        return b"ok"

    assert with_retries(flaky, sleep=waits.append) == b"ok"
    assert waits == [2.0, 4.0]

    def broken() -> bytes:
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        with_retries(broken, attempts=2, sleep=waits.append)
