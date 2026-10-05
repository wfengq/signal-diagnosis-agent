#!/usr/bin/env python3
"""Reproduce OQ-020 clean-sine clipping_ratio probe on direct DSP and full tool path."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.evaluation.external.pcm import encode_pcm24_mono
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
    MeasurementSelection,
    ToolParameterSnapshot,
    measure_output,
)

SAMPLE_RATES = (44_100, 48_000)
FREQUENCIES_HZ = (50.0, 100.0, 220.0, 440.0, 880.0, 997.0)
AMPLITUDES = (0.01, 0.05, 0.2, 0.5, 0.9)
PHASES_RAD = (0.0, 0.1, 1.0, 2.0)
DURATION_S = 2.0
FULL_SCALE_THRESHOLD = 0.99
MIN_CONSECUTIVE_SAMPLES = 2
BitDepth = Literal[16, 24, 32]
WHITE_NOISE_SEED = 0
WHITE_NOISE_RMS = 0.5
CLIP_LEVELS = (0.5, 0.9, 0.98)


@dataclass(frozen=True, slots=True)
class CellKey:
    sample_rate_hz: int
    frequency_hz: float
    amplitude: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "sample_rate_hz": self.sample_rate_hz,
            "frequency_hz": self.frequency_hz,
            "amplitude": self.amplitude,
        }


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


def encode_pcm16_mono_wav(samples: np.ndarray, *, sample_rate_hz: int) -> bytes:
    """Mono float column vector -> 16-bit PCM WAV (rint * 2^15, clip, no peak normalize)."""
    if samples.ndim != 2 or samples.shape[1] != 1:
        raise ValueError("samples must have shape (num_frames, 1)")
    mono = np.asarray(samples[:, 0], dtype=np.float64)
    pcm = np.clip(np.rint(mono * 32767.0), -32768, 32767).astype("<i2")
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=sample_rate_hz, bits=16),
        data=pcm.tobytes(),
    )


def encode_wav(samples: np.ndarray, *, sample_rate_hz: int, bits: BitDepth) -> bytes:
    if bits == 16:
        return encode_pcm16_mono_wav(samples, sample_rate_hz=sample_rate_hz)
    if bits == 24:
        return encode_pcm24_mono(samples[:, 0], sample_rate_hz)
    if bits == 32:
        return encode_pcm32_wav(samples, sample_rate_hz=sample_rate_hz)
    raise ValueError(f"unsupported bit depth: {bits}")


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    padded = np.pad(mask, (1, 1), constant_values=False)
    edges = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    return [(int(start), int(stop)) for start, stop in zip(starts, stops)]


def full_scale_sample_count(
    values: np.ndarray,
    *,
    full_scale_threshold: float = FULL_SCALE_THRESHOLD,
    min_consecutive_samples: int = MIN_CONSECUTIVE_SAMPLES,
) -> int:
    """Count samples in |x| >= threshold runs of length >= min_consecutive_samples."""
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    mask = np.abs(arr) >= full_scale_threshold
    qualified = np.zeros(mask.shape, dtype=bool)
    for start, stop in _runs(mask):
        if stop - start >= min_consecutive_samples:
            qualified[start:stop] = True
    return int(np.count_nonzero(qualified))


def _selection_for_cell(cell: CellKey) -> MeasurementSelection:
    tr = TimeRange()
    return MeasurementSelection(
        clipping=ClippingInput(channel="left", time_range=tr, full_scale_threshold=FULL_SCALE_THRESHOLD),
        harmonic=HarmonicDistortionInput(
            channel="left",
            time_range=tr,
            fundamental_hz=cell.frequency_hz,
        ),
    )


def _resolved_bounds(
    repository: InMemorySignalRepository,
    signal_id: str,
    selection: MeasurementSelection,
) -> tuple[int, int]:
    record = repository.get(signal_id)
    time_range = selection.clipping.time_range or TimeRange()
    start = round(time_range.start_s * record.meta.sample_rate_hz)
    end = (
        record.meta.num_samples
        if time_range.end_s is None
        else min(
            round(time_range.end_s * record.meta.sample_rate_hz),
            record.meta.num_samples,
        )
    )
    return start, end


def _build_identity(
    *,
    run_id: str,
    wav_sha256: str,
    signal_id: str,
    repository: InMemorySignalRepository,
    selection: MeasurementSelection,
) -> InputIdentity:
    record = repository.get(signal_id)
    start, end = _resolved_bounds(repository, signal_id, selection)
    snapshot = ToolParameterSnapshot(
        clipping=selection.clipping,
        harmonic=selection.harmonic,
    )
    return InputIdentity(
        run_id=run_id,
        side="baseline",
        wav_sha256=wav_sha256,
        signal_id=signal_id,
        sample_rate_hz=record.meta.sample_rate_hz,
        source_channels=record.meta.channels,
        total_frames=record.meta.num_samples,
        resolved_start_sample=start,
        resolved_end_sample=end,
        channel=selection.clipping.channel,
        tool_parameter_snapshot=snapshot,
    )


def _clip_metrics_from_analysis(analysis: Any) -> dict[str, Any]:
    return {
        "clipping_ratio": analysis.clipping_ratio,
        "flat_top_detected": analysis.flat_top_detected,
        "clipping_mechanism": analysis.clipping_mechanism,
        "full_scale_detected": analysis.full_scale_detected,
        "clipped_samples": analysis.clipped_samples,
        "peak_abs": analysis.peak_abs,
    }


def _clip_metrics_from_tool(bundle_clipping: Any) -> dict[str, Any]:
    assert bundle_clipping.status == "success" and bundle_clipping.result is not None
    out = bundle_clipping.result
    return {
        "clipping_ratio": out.clipping_ratio,
        "flat_top_detected": out.flat_top_detected,
        "clipping_mechanism": out.clipping_mechanism,
        "full_scale_detected": out.full_scale_detected,
        "clipped_samples": out.clipped_samples,
        "peak_abs": out.peak_abs,
    }


def _phase_direct(cell: CellKey, phase_rad: float) -> dict[str, Any]:
    case = generate_sine(
        frequency_hz=cell.frequency_hz,
        sample_rate_hz=cell.sample_rate_hz,
        duration_s=DURATION_S,
        amplitude=cell.amplitude,
        phase_rad=phase_rad,
    )
    mono = case.record.samples[:, 0]
    analysis = analyze_clipping(mono)
    metrics = _clip_metrics_from_analysis(analysis)
    metrics["full_scale_sample_count"] = full_scale_sample_count(mono)
    return metrics


def _phase_toolpath(cell: CellKey, phase_rad: float, bits: BitDepth) -> dict[str, Any]:
    case = generate_sine(
        frequency_hz=cell.frequency_hz,
        sample_rate_hz=cell.sample_rate_hz,
        duration_s=DURATION_S,
        amplitude=cell.amplitude,
        phase_rad=phase_rad,
    )
    wav_bytes = encode_wav(case.record.samples, sample_rate_hz=cell.sample_rate_hz, bits=bits)
    loaded = load_wav_bytes(wav_bytes, filename=f"oq020_{cell.sample_rate_hz}_{cell.frequency_hz}.wav")
    repository = InMemorySignalRepository()
    repository.put(loaded.record)
    signal_id = loaded.record.meta.signal_id
    wav_sha = hashlib.sha256(wav_bytes).hexdigest()
    selection = _selection_for_cell(cell)
    identity = _build_identity(
        run_id=f"probe_{bits}",
        wav_sha256=wav_sha,
        signal_id=signal_id,
        repository=repository,
        selection=selection,
    )
    bundle = measure_output(repository=repository, identity=identity, selection=selection)
    decoded = repository.get(signal_id).samples[:, 0]
    metrics = _clip_metrics_from_tool(bundle.clipping)
    metrics["full_scale_sample_count"] = full_scale_sample_count(decoded)
    return metrics


def _aggregate_phases(phase_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ratios = [row["clipping_ratio"] for row in phase_rows]
    nonzero = any(r > 0.0 for r in ratios)
    return {
        "any_nonzero_ratio": nonzero,
        "max_clipping_ratio": max(ratios),
        "min_clipping_ratio": min(ratios),
        "any_flat_top": any(row["flat_top_detected"] for row in phase_rows),
        "any_mechanism": any(row["clipping_mechanism"] for row in phase_rows),
        "any_full_scale_detected": any(row["full_scale_detected"] for row in phase_rows),
        "max_full_scale_sample_count": max(row["full_scale_sample_count"] for row in phase_rows),
        "max_peak_abs": max(row["peak_abs"] for row in phase_rows),
        "phases": {str(PHASES_RAD[i]): phase_rows[i] for i in range(len(phase_rows))},
    }


def _iter_cells(quick: bool) -> list[CellKey]:
    rates = SAMPLE_RATES if not quick else (48_000,)
    freqs = FREQUENCIES_HZ if not quick else (100.0,)
    amps = AMPLITUDES if not quick else (0.01,)
    cells: list[CellKey] = []
    for rate in rates:
        for freq in freqs:
            for amp in amps:
                cells.append(CellKey(sample_rate_hz=rate, frequency_hz=freq, amplitude=amp))
    return cells


def _count_nonzero_cells(cell_aggs: dict[str, dict[str, Any]]) -> int:
    return sum(1 for agg in cell_aggs.values() if agg["any_nonzero_ratio"])


def _cell_id(cell: CellKey) -> str:
    return f"{cell.sample_rate_hz}_{cell.frequency_hz}_{cell.amplitude}"


def run_grid(quick: bool) -> dict[str, Any]:
    cells = _iter_cells(quick)
    phases = (0.0,) if quick else PHASES_RAD

    direct_by_cell: dict[str, dict[str, Any]] = {}
    tool_by_depth: dict[str, dict[str, dict[str, Any]]] = {
        "16": {},
        "24": {},
        "32": {},
    }

    for cell in cells:
        phase_rows = [_phase_direct(cell, p) for p in phases]
        direct_by_cell[_cell_id(cell)] = {
            "cell": cell.as_dict(),
            **_aggregate_phases(phase_rows),
        }
        for bits in (16, 24, 32):
            if quick and bits != 32:
                continue
            tool_phase_rows = [_phase_toolpath(cell, p, bits) for p in phases]
            tool_by_depth[str(bits)][_cell_id(cell)] = {
                "cell": cell.as_dict(),
                **_aggregate_phases(tool_phase_rows),
            }

    direct_nonzero = _count_nonzero_cells(direct_by_cell)
    total_cells = len(cells)

    depth_summary: dict[str, Any] = {}
    for bits_key, agg_map in tool_by_depth.items():
        nz = _count_nonzero_cells(agg_map)
        differs = 0
        for cid, tool_agg in agg_map.items():
            direct_agg = direct_by_cell[cid]
            if tool_agg["any_nonzero_ratio"] != direct_agg["any_nonzero_ratio"]:
                differs += 1
            elif abs(tool_agg["max_clipping_ratio"] - direct_agg["max_clipping_ratio"]) > 1e-12:
                differs += 1
        depth_summary[bits_key] = {
            "nonzero_cells": nz,
            "total_cells": total_cells,
            "cells_differing_from_direct": differs,
        }

    return {
        "grid": {
            "sample_rates": list(SAMPLE_RATES),
            "frequencies_hz": list(FREQUENCIES_HZ),
            "amplitudes": list(AMPLITUDES),
            "phases_rad": list(PHASES_RAD),
            "duration_s": DURATION_S,
            "quick": quick,
        },
        "direct_dsp": {
            "nonzero_cells": direct_nonzero,
            "total_cells": total_cells,
            "cells": direct_by_cell,
        },
        "tool_path_by_bit_depth": tool_by_depth,
        "tool_path_summary": depth_summary,
    }


def _noise_metrics_direct() -> dict[str, Any]:
    case = generate_white_noise(
        sample_rate_hz=48_000,
        duration_s=DURATION_S,
        rms=WHITE_NOISE_RMS,
        seed=WHITE_NOISE_SEED,
    )
    mono = np.clip(case.record.samples[:, 0], -1.0, 1.0)
    analysis = analyze_clipping(mono)
    return {
        "path": "direct_dsp",
        **_clip_metrics_from_analysis(analysis),
        "full_scale_sample_count": full_scale_sample_count(mono),
    }


def _noise_metrics_tool(bits: BitDepth) -> dict[str, Any]:
    case = generate_white_noise(
        sample_rate_hz=48_000,
        duration_s=DURATION_S,
        rms=WHITE_NOISE_RMS,
        seed=WHITE_NOISE_SEED,
    )
    clipped = np.clip(case.record.samples, -1.0, 1.0)
    record = case.record
    from signal_diag.signal.factory import build_signal_record

    limited = build_signal_record(
        clipped,
        sample_rate_hz=record.meta.sample_rate_hz,
        source_type="generated",
    )
    wav_bytes = encode_wav(limited.samples, sample_rate_hz=48_000, bits=bits)
    loaded = load_wav_bytes(wav_bytes, filename="oq020_white_noise.wav")
    repository = InMemorySignalRepository()
    repository.put(loaded.record)
    signal_id = loaded.record.meta.signal_id
    cell = CellKey(sample_rate_hz=48_000, frequency_hz=200.0, amplitude=0.5)
    selection = _selection_for_cell(cell)
    identity = _build_identity(
        run_id=f"noise_{bits}",
        wav_sha256=hashlib.sha256(wav_bytes).hexdigest(),
        signal_id=signal_id,
        repository=repository,
        selection=selection,
    )
    bundle = measure_output(repository=repository, identity=identity, selection=selection)
    decoded = repository.get(signal_id).samples[:, 0]
    return {
        "path": f"tool_path_pcm{bits}",
        **_clip_metrics_from_tool(bundle.clipping),
        "full_scale_sample_count": full_scale_sample_count(decoded),
    }


def _clipped_sine_cases(quick: bool) -> dict[str, Any]:
    if quick:
        levels = (0.9,)
    else:
        levels = CLIP_LEVELS
    rows: dict[str, Any] = {}
    for level in levels:
        case = generate_clipped_sine(
            frequency_hz=440.0,
            clip_level=level,
            sample_rate_hz=48_000,
            duration_s=DURATION_S,
            amplitude=0.9,
        )
        mono = case.record.samples[:, 0]
        direct = analyze_clipping(mono)
        wav_bytes = encode_pcm32_wav(case.record.samples, sample_rate_hz=48_000)
        loaded = load_wav_bytes(wav_bytes, filename=f"clipped_{level}.wav")
        repository = InMemorySignalRepository()
        repository.put(loaded.record)
        signal_id = loaded.record.meta.signal_id
        cell = CellKey(sample_rate_hz=48_000, frequency_hz=440.0, amplitude=0.9)
        selection = _selection_for_cell(cell)
        identity = _build_identity(
            run_id=f"clip_{level}",
            wav_sha256=hashlib.sha256(wav_bytes).hexdigest(),
            signal_id=signal_id,
            repository=repository,
            selection=selection,
        )
        bundle = measure_output(repository=repository, identity=identity, selection=selection)
        decoded = repository.get(signal_id).samples[:, 0]
        tool_clip = _clip_metrics_from_tool(bundle.clipping)
        tool_clip["full_scale_sample_count"] = full_scale_sample_count(decoded)
        rows[str(level)] = {
            "direct_dsp": {
                **_clip_metrics_from_analysis(direct),
                "full_scale_sample_count": full_scale_sample_count(mono),
            },
            "tool_path_pcm32_clipped_waveform": tool_clip,
            "note": "tool_path via generate_sine would be clean; clipped row uses clipped waveform",
        }
    return rows


def _example_cells(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull OQ-020 cited examples for the report JSON."""
    keys = [
        "48000_100.0_0.01",
        "48000_50.0_0.9",
        "48000_100.0_0.9",
        "44100_100.0_0.01",
    ]
    out: dict[str, Any] = {}
    direct_cells = payload["direct_dsp"]["cells"]
    for key in keys:
        if key not in direct_cells:
            continue
        out[key] = {
            "direct_dsp": direct_cells[key],
            "tool_path": {
                bits: payload["tool_path_by_bit_depth"][bits].get(key)
                for bits in ("16", "24", "32")
                if key in payload["tool_path_by_bit_depth"][bits]
            },
        }
    return out


def _print_summary(payload: dict[str, Any]) -> None:
    d = payload["direct_dsp"]
    print(f"direct_dsp: {d['nonzero_cells']}/{d['total_cells']} cells with any phase clipping_ratio > 0")
    for bits, summary in payload["tool_path_summary"].items():
        print(
            f"tool_path_pcm{bits}: {summary['nonzero_cells']}/{summary['total_cells']} nonzero; "
            f"{summary['cells_differing_from_direct']} cells differ from direct (aggregate)"
        )
    noise = payload["white_noise"]
    print(
        f"white_noise direct clipping_ratio={noise['direct_dsp']['clipping_ratio']:.6f}; "
        f"pcm32 tool={noise['tool_path_pcm32']['clipping_ratio']:.6f}"
    )
    clean_fs = all(
        cell["max_full_scale_sample_count"] == 0
        for cell in payload["direct_dsp"]["cells"].values()
    )
    print(f"direct_dsp clean sines: max full_scale_sample_count always 0 -> {clean_fs}")
    for bits in ("16", "24", "32"):
        if bits not in payload["tool_path_by_bit_depth"]:
            continue
        tool_fs = all(
            cell["max_full_scale_sample_count"] == 0
            for cell in payload["tool_path_by_bit_depth"][bits].values()
        )
        print(f"tool_path_pcm{bits} clean sines: max full_scale_sample_count always 0 -> {tool_fs}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs"),
        help="Directory for JSON output (default: docs/)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Smoke grid: one cell, one phase, pcm32 only",
    )
    args = parser.parse_args(argv)

    grid_payload = run_grid(args.quick)
    payload: dict[str, Any] = {
        "probe": "OQ-020 full tool path reproduction",
        "generated_on": "2026-10-05",
        **grid_payload,
        "white_noise": {
            "rms": WHITE_NOISE_RMS,
            "seed": WHITE_NOISE_SEED,
            "limited_to_full_scale": True,
            "direct_dsp": _noise_metrics_direct(),
            "tool_path_pcm16": _noise_metrics_tool(16) if not args.quick else None,
            "tool_path_pcm24": _noise_metrics_tool(24) if not args.quick else None,
            "tool_path_pcm32": _noise_metrics_tool(32),
        },
        "clipped_sine_sub_full_scale": _clipped_sine_cases(args.quick),
        "examples": _example_cells(grid_payload) if not args.quick else {},
        "disclaimer": (
            "Probe only; not layer-1 characterization approval; no floor values; "
            "§23 implementation unauthorized."
        ),
    }
    if args.quick:
        payload["white_noise"].pop("tool_path_pcm16", None)
        payload["white_noise"].pop("tool_path_pcm24", None)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "OQ020_FULL_TOOLPATH_PROBE_2026-10-05.json"
    # Drop per-phase detail from full run cells in JSON to keep size manageable.
    slim = json.loads(json.dumps(payload))
    for section in ("direct_dsp",):
        for cell in slim[section]["cells"].values():
            cell.pop("phases", None)
    for depth_cells in slim["tool_path_by_bit_depth"].values():
        for cell in depth_cells.values():
            cell.pop("phases", None)
    json_path.write_text(json.dumps(slim, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    _print_summary(payload)
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
