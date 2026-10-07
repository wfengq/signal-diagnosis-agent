"""pOD-set validation of the sweep test (D056; design 2026-10-07-sweep-podset-validation).

Data: Dal Rì, Stefani, Turchet, Conci, "Parametric Overdrive pedal dataset
(pOD-set)", Zenodo, DOI 10.5281/zenodo.15389653, CC BY-NC 4.0. Audio is fetched
by HTTP range requests into a cache outside the repository and never
committed; only file hashes and derived numbers are.

    python -m signal_diag.evaluation.podset fetch --cache DIR
    python -m signal_diag.evaluation.podset run --cache DIR --out DIR

The acceptance criteria (CRITERIA) were fixed in the approved design before the
full dataset was run (D056 3A) and are not tuned to results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import statistics
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from signal_diag.dsp.sweep import BandResult, analyze_known_sweep
from signal_diag.signal import load_wav_bytes

RECORD_URL = "https://zenodo.org/records/15389653/files"
DOI = "10.5281/zenodo.15389653"
LICENSE = "CC BY-NC 4.0"
ATTRIBUTION = (
    "Dal Rì, F. A.; Stefani, D.; Turchet, L.; Conci, N. Parametric Overdrive pedal "
    "dataset (pOD-set). Zenodo, 2025. DOI 10.5281/zenodo.15389653. CC BY-NC 4.0."
)
RATE = 48_000
GAINS = (0, 1, 2, 3, 4, 5)  # file index; knob positions 0, 2, 4, 6, 8, 10
TONE = 3  # file index 3, knob position 6
LEVELS = (("s2", "-24 dBFS"), ("s1", "-12 dBFS"), ("s0", "-6 dBFS"))  # quiet to loud
DESIGN_PEDAL = "kingoftone"  # used to design the method (§3); reported separately
CROSS_CHECK_BANDS = (1_000.0, 2_000.0, 4_000.0)
CRITERIA = {
    "synthetic_abs_pp": 0.1,
    "synthetic_identity_max": 0.05,
    "monotone_tolerance_pp": 0.2,
    "monotone_tolerance_rel": 0.10,
    "level_monotone_share": 0.95,
    "gain_monotone_share": 0.90,
    "low_gain_median_max": 1.0,
    "cross_check_rel": 0.15,
    "cross_check_pp": 0.3,
    "cross_check_min_thd": 0.5,
    "cross_check_share": 0.90,
}
DEMO_THD_LIMIT = 5.0  # profile_s1_sweep 1.0.0-demo, for the reported onset only
REPORT_SCHEMA = "podset_check/1"


# --- fetching ---------------------------------------------------------------


class RangeReader(io.RawIOBase):
    """Seekable read-only file over ``read_range(start, end_inclusive)``."""

    def __init__(self, size: int, read_range: Callable[[int, int], bytes]) -> None:
        self._size = size
        self._read_range = read_range
        self._pos = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:
        base = {0: 0, 1: self._pos, 2: self._size}[whence]
        self._pos = base + offset
        return self._pos

    def readinto(self, buffer: Any) -> int:
        if self._pos >= self._size or len(buffer) == 0:
            return 0
        end = min(self._size, self._pos + len(buffer)) - 1
        data = self._read_range(self._pos, end)
        buffer[: len(data)] = data
        self._pos += len(data)
        return len(data)


def with_retries(call: Callable[[], bytes], attempts: int = 5, sleep: Callable[[float], None] = time.sleep) -> bytes:
    """Retry transient network errors with exponential backoff (2, 4, 8, 16 s)."""
    for attempt in range(attempts):
        try:
            return call()
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == attempts - 1:
                raise
            sleep(2.0 * 2**attempt)
    raise AssertionError("unreachable")


def http_range_reader(url: str) -> RangeReader:
    def head() -> bytes:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=60) as response:
            return str(response.headers["Content-Length"]).encode()

    size = int(with_retries(head))

    def read_range(start: int, end: int) -> bytes:
        def get() -> bytes:
            request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = bytes(response.read())
            if len(data) != end - start + 1:
                raise ConnectionError("short range read")
            return data

        return with_retries(get)

    return RangeReader(size, read_range)


def sweep_member_names(pedal: str) -> list[str]:
    return [
        f"{pedal}/{prefix}_{pedal}_g{gain}_t{TONE}.wav"
        for gain in GAINS
        for prefix, _ in LEVELS
    ]


def extract_members(
    reader: io.RawIOBase, names: Iterable[str], cache: Path
) -> list[dict[str, Any]]:
    """Extract ``names`` from a zip into ``cache``; return manifest entries."""
    archive = zipfile.ZipFile(io.BufferedReader(reader, buffer_size=1 << 20))
    entries = []
    for name in names:
        target = cache / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
        data = target.read_bytes()
        entries.append(
            {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    return entries


def fetch(cache: Path, pedals: Iterable[str] | None = None) -> dict[str, Any]:
    """Download the dry sweeps and the selected pedal sweeps; write the manifest."""
    cache.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f"{RECORD_URL}/0_dataset_metadata.csv?download=1") as response:
        metadata = response.read().decode("utf-8")
    (cache / "0_dataset_metadata.csv").write_text(metadata, encoding="utf-8")
    names = [row["datasetname"] for row in csv.DictReader(io.StringIO(metadata))]
    selected = list(pedals) if pedals is not None else names
    files = extract_members(
        http_range_reader(f"{RECORD_URL}/0_input.zip?download=1"),
        [f"input/{prefix}_0-input.wav" for prefix, _ in LEVELS],
        cache,
    )
    for pedal in selected:
        files += extract_members(
            http_range_reader(f"{RECORD_URL}/{pedal}.zip?download=1"),
            sweep_member_names(pedal),
            cache,
        )
    manifest = {
        "dataset": "pOD-set",
        "doi": DOI,
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "pedals": selected,
        "gain_indices": list(GAINS),
        "tone_index": TONE,
        "levels": [label for _, label in LEVELS],
        "files": files,
    }
    (cache / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


# --- analysis ---------------------------------------------------------------


def _load(path: Path) -> np.ndarray:
    loaded = load_wav_bytes(path.read_bytes(), filename=path.name)
    return np.asarray(loaded.record.samples[:, 0], dtype=np.float64)


def alias_free(device: Callable[[np.ndarray], np.ndarray], samples: np.ndarray) -> np.ndarray:
    """A digital nonlinearity applied at 4x and band-limited, like an analog device
    behind an anti-aliasing filter (a plain one folds harmonics above Nyquist)."""
    n = len(samples)
    spectrum = np.fft.rfft(samples)
    upsampled = np.zeros(n * 2 + 1, dtype=complex)
    upsampled[: len(spectrum)] = spectrum
    output = device(np.fft.irfft(upsampled, n * 4) * 4)
    return np.fft.irfft(np.fft.rfft(output)[: len(spectrum)], n) / 4


def short_time_band_thd(
    recording: np.ndarray,
    *,
    rate_l: float,
    start_frequency_hz: float,
    lag: int,
    center_hz: float,
    orders: tuple[int, ...],
) -> float | None:
    """Independent cross-check: harmonics read from 20 ms windows where the
    sweep passes seven frequencies of the band (no deconvolution)."""
    if not orders:
        return None
    window = int(0.02 * RATE)
    size = 1 << 16
    freqs = np.fft.rfftfreq(size, 1 / RATE)
    fundamental = harmonic = 0.0
    for frequency in np.geomspace(center_hz / np.sqrt(2), center_hz * np.sqrt(2), 7):
        start = int(rate_l * np.log(frequency / start_frequency_hz) * RATE) + lag - window // 2
        if start < 0 or start + window > len(recording):
            return None
        spectrum = np.abs(np.fft.rfft(recording[start : start + window] * np.hanning(window), size))

        def energy(target: float, spectrum: np.ndarray = spectrum) -> float:
            mask = (freqs > target * 0.94) & (freqs < target * 1.06)
            return float(np.sum(spectrum[mask] ** 2))

        fundamental += energy(frequency)
        harmonic += sum(energy(order * frequency) for order in orders)
    return 100.0 * float(np.sqrt(harmonic / fundamental)) if fundamental > 0 else None


@dataclass(frozen=True)
class RecordingResult:
    pedal: str
    gain: int
    level: str
    lag_samples: int
    bands: tuple[BandResult, ...]
    cross_check: dict[float, float | None]

    def band(self, center: float) -> BandResult:
        return next(band for band in self.bands if band.center_hz == center)


def analyze_recording(
    pedal: str, gain: int, level: str, recording: np.ndarray, stimulus: np.ndarray
) -> RecordingResult:
    analysis = analyze_known_sweep(recording, stimulus, RATE)
    cross = {}
    for center in CROSS_CHECK_BANDS:
        band = next(b for b in analysis.bands if b.center_hz == center)
        cross[center] = short_time_band_thd(
            recording,
            rate_l=analysis.rate_l,
            start_frequency_hz=analysis.start_frequency_hz,
            lag=analysis.lag_samples,
            center_hz=center,
            orders=band.orders_used,
        )
    return RecordingResult(pedal, gain, level, analysis.lag_samples, analysis.bands, cross)


def synthetic_check(stimulus: np.ndarray) -> dict[str, Any]:
    """Criterion 1: identity and an alias-free polynomial on the dataset's dry sweep."""
    peak = float(np.max(np.abs(stimulus)))
    fundamental = peak + 3 * 0.05 * peak**3 / 4
    expected = 100 * float(np.hypot(0.1 * peak**2 / 2, 0.05 * peak**3 / 4)) / fundamental
    poly = analyze_known_sweep(
        alias_free(lambda x: x + 0.1 * x**2 + 0.05 * x**3, stimulus), stimulus, RATE
    )
    identity = analyze_known_sweep(stimulus, stimulus, RATE)
    checked = [b for b in poly.bands if 125.0 <= b.center_hz <= 4_000.0]
    worst = max(abs((b.thd_percent or 0.0) - expected) for b in checked)
    identity_max = max((b.thd_percent or 0.0) for b in identity.bands if b.measurable)
    return {
        "expected_thd_percent": round(expected, 4),
        "polynomial_band_thd_percent": {
            str(b.center_hz): (b.thd_percent if b.measurable else None) for b in checked
        },
        "worst_abs_error_pp": round(worst, 4),
        "identity_max_thd_percent": round(identity_max, 4),
        "passed": all(b.measurable for b in checked)
        and worst <= CRITERIA["synthetic_abs_pp"]
        and identity_max <= CRITERIA["synthetic_identity_max"],
    }


# --- criteria ---------------------------------------------------------------


def _not_falling(low: float, high: float) -> bool:
    tolerance = max(CRITERIA["monotone_tolerance_pp"], CRITERIA["monotone_tolerance_rel"] * low)
    return high >= low - tolerance


def _share(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 4) if flags else None


def evaluate(results: list[RecordingResult]) -> dict[str, Any]:
    """Criteria 2–5 over the given recordings (§5 of the design)."""
    index = {(r.pedal, r.gain, r.level): r for r in results}
    pedals = sorted({r.pedal for r in results})
    labels = [label for _, label in LEVELS]
    level_flags: list[bool] = []
    gain_flags: list[bool] = []
    for pedal in pedals:
        for gain in GAINS:
            for low, high in pairwise(labels):
                a, b = index.get((pedal, gain, low)), index.get((pedal, gain, high))
                if a is None or b is None:
                    continue
                for band_a, band_b in zip(a.bands, b.bands, strict=True):
                    if band_a.measurable and band_b.measurable:
                        level_flags.append(_not_falling(band_a.thd_percent or 0.0, band_b.thd_percent or 0.0))
        for level in labels:
            for gain_low, gain_high in pairwise(GAINS):
                a, b = index.get((pedal, gain_low, level)), index.get((pedal, gain_high, level))
                if a is None or b is None:
                    continue
                for band_a, band_b in zip(a.bands, b.bands, strict=True):
                    if band_a.measurable and band_b.measurable:
                        gain_flags.append(_not_falling(band_a.thd_percent or 0.0, band_b.thd_percent or 0.0))
    low_gain_medians: dict[str, float | None] = {}
    for pedal in pedals:
        values = [
            band.thd_percent
            for r in results
            if r.pedal == pedal and r.gain == GAINS[0]
            for band in r.bands
            if band.measurable and band.thd_percent is not None
        ]
        low_gain_medians[pedal] = round(statistics.median(values), 4) if values else None
    cross_flags: list[bool] = []
    for r in results:
        for center, short_time in r.cross_check.items():
            band = r.band(center)
            if not band.measurable or band.thd_percent is None or short_time is None:
                continue
            if band.thd_percent < CRITERIA["cross_check_min_thd"]:
                continue
            tolerance = max(CRITERIA["cross_check_rel"] * band.thd_percent, CRITERIA["cross_check_pp"])
            cross_flags.append(abs(short_time - band.thd_percent) <= tolerance)
    level_share, gain_share, cross_share = _share(level_flags), _share(gain_flags), _share(cross_flags)
    medians = [value for value in low_gain_medians.values() if value is not None]
    overall_low = round(statistics.median(medians), 4) if medians else None
    return {
        "recordings": len(results),
        "level_monotone": {"comparisons": len(level_flags), "share": level_share,
                           "passed": level_share is not None and level_share >= CRITERIA["level_monotone_share"]},
        "gain_monotone": {"comparisons": len(gain_flags), "share": gain_share,
                          "passed": gain_share is not None and gain_share >= CRITERIA["gain_monotone_share"]},
        "low_gain": {"median_by_pedal": low_gain_medians, "median_of_pedals": overall_low,
                     "below_limit": overall_low is not None and overall_low < CRITERIA["low_gain_median_max"],
                     "note": "distribution only; some pedals are not clean at minimum gain"},
        "cross_check": {"comparisons": len(cross_flags), "share": cross_share,
                        "passed": cross_share is not None and cross_share >= CRITERIA["cross_check_share"]},
    }


def onset(results: list[RecordingResult], pedal: str, gain: int) -> str | None:
    """First level (quiet to loud) whose measurable band THD exceeds the demo limit."""
    for _, label in LEVELS:
        result = next((r for r in results if (r.pedal, r.gain, r.level) == (pedal, gain, label)), None)
        if result and any(b.measurable and (b.thd_percent or 0.0) > DEMO_THD_LIMIT for b in result.bands):
            return label
    return None


# --- run --------------------------------------------------------------------


def run(cache: Path, out: Path) -> dict[str, Any]:
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        data = (cache / entry["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"hash mismatch for {entry['path']}")
    stimuli = {label: _load(cache / f"input/{prefix}_0-input.wav") for prefix, label in LEVELS}
    synthetic = synthetic_check(stimuli["-6 dBFS"])
    results: list[RecordingResult] = []
    for pedal in manifest["pedals"]:
        for gain in GAINS:
            for prefix, label in LEVELS:
                recording = _load(cache / f"{pedal}/{prefix}_{pedal}_g{gain}_t{TONE}.wav")
                results.append(analyze_recording(pedal, gain, label, recording, stimuli[label]))
    without_design = [r for r in results if r.pedal != DESIGN_PEDAL]
    report = {
        "schema": REPORT_SCHEMA,
        "dataset": {key: manifest[key] for key in ("dataset", "doi", "license", "attribution")},
        "selection": {"pedals": manifest["pedals"], "gain_indices": list(GAINS),
                      "tone_index": TONE, "levels": [label for _, label in LEVELS]},
        "criteria": CRITERIA,
        "synthetic_check": synthetic,
        "all_pedals": evaluate(results),
        "without_design_pedal": evaluate(without_design),
        "design_pedal": DESIGN_PEDAL,
        "onset_at_demo_limit": {
            pedal: {str(gain): onset(results, pedal, gain) for gain in GAINS}
            for pedal in manifest["pedals"]
        },
        "model_calls": 0,
    }
    rows = [
        {
            "pedal": r.pedal, "gain_index": r.gain, "level": r.level, "lag_samples": r.lag_samples,
            "bands": [
                {"center_hz": b.center_hz, "measurable": b.measurable, "thd_percent": b.thd_percent,
                 "noise_floor_percent": b.noise_floor_percent, "dominant_order": b.dominant_order}
                for b in r.bands
            ],
            "cross_check": {str(k): (round(v, 4) if v is not None else None) for k, v in r.cross_check.items()},
        }
        for r in results
    ]
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out / "results.json").write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m signal_diag.evaluation.podset")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch")
    fetch_parser.add_argument("--cache", type=Path, required=True)
    fetch_parser.add_argument("--pedal", action="append", default=None)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--cache", type=Path, required=True)
    run_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "fetch":
        manifest = fetch(args.cache, args.pedal)
        print(f"fetched {len(manifest['files'])} files")
        return 0
    report = run(args.cache, args.out)
    print(json.dumps({k: report[k] for k in ("synthetic_check", "all_pedals")}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
