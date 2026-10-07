"""Sweep measurement facts for the sweep stimulus test (D054, §29).

The frozen ``ToolName`` and ``Evidence`` contracts cover the contextual tools;
the sweep test has its own compact, deterministic fact records, judged by
``rules.sweep``. Raw samples and spectra never leave ``dsp.sweep``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from signal_diag.dsp.sweep import SWEEP_STIMULUS_VERSION, analyze_sweep_recording

FactValue = bool | int | float | str
FactValidity = Literal["valid", "not_applicable"]


class SweepFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    fact_id: str = Field(pattern=r"^swf_")
    metric: str = Field(min_length=1)
    value: FactValue
    unit: str | None = None
    band_hz: float | None = None
    validity: FactValidity = "valid"


class SweepBandSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    center_hz: float
    measurable: bool
    thd_percent: float | None
    noise_floor_percent: float | None
    dominant_order: int | None
    orders_used: tuple[int, ...]


class SweepMeasurement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    measurement_id: str = Field(pattern=r"^swm_")
    level_label: str = Field(min_length=1, max_length=64)
    sample_rate_hz: int
    stimulus_version: str
    stimulus_digest: str
    analysis_version: str
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    valid: bool
    invalid_reason: str | None
    clipped_frequency_hz: tuple[float, float] | None
    bands: tuple[SweepBandSummary, ...]
    facts: tuple[SweepFact, ...]


def _fact_id(measurement_id: str, metric: str, band_hz: float | None) -> str:
    payload = json.dumps([measurement_id, metric, band_hz])
    return "swf_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def measure_sweep_recording(
    samples: np.ndarray, sample_rate_hz: int, *, level_label: str
) -> SweepMeasurement:
    """Analyse one recording and return its deterministic fact record."""
    values = np.asarray(samples, dtype=np.float64).reshape(-1)
    recording_sha256 = hashlib.sha256(values.astype("<f8").tobytes()).hexdigest()
    analysis = analyze_sweep_recording(values, sample_rate_hz)
    measurement_id = (
        "swm_"
        + hashlib.sha256(
            json.dumps(
                [recording_sha256, sample_rate_hz, level_label, analysis.version]
            ).encode()
        ).hexdigest()[:24]
    )

    facts: list[SweepFact] = []

    def add(
        metric: str,
        value: FactValue | None,
        *,
        unit: str | None = None,
        band_hz: float | None = None,
    ) -> None:
        facts.append(
            SweepFact(
                fact_id=_fact_id(measurement_id, metric, band_hz),
                metric=metric,
                value="not_applicable" if value is None else value,
                unit=unit,
                band_hz=band_hz,
                validity="not_applicable" if value is None else "valid",
            )
        )

    add("analysis_valid", analysis.valid)
    add("alignment_correlation", analysis.alignment_correlation)
    add(
        "drift_abs_ppm",
        None if analysis.drift_ppm is None else abs(analysis.drift_ppm),
        unit="ppm",
    )
    add("snr_db", analysis.snr_db, unit="dB")
    add("full_scale_ratio", analysis.full_scale_ratio)
    for band in analysis.bands:
        add(
            "band_thd_percent",
            band.thd_percent if band.measurable else None,
            unit="%",
            band_hz=band.center_hz,
        )
    return SweepMeasurement(
        measurement_id=measurement_id,
        level_label=level_label,
        sample_rate_hz=sample_rate_hz,
        stimulus_version=SWEEP_STIMULUS_VERSION,
        stimulus_digest=analysis.stimulus_digest,
        analysis_version=analysis.version,
        recording_sha256=recording_sha256,
        valid=analysis.valid,
        invalid_reason=analysis.invalid_reason,
        clipped_frequency_hz=analysis.clipped_frequency_hz,
        bands=tuple(
            SweepBandSummary(
                center_hz=band.center_hz,
                measurable=band.measurable,
                thd_percent=band.thd_percent,
                noise_floor_percent=band.noise_floor_percent,
                dominant_order=band.dominant_order,
                orders_used=band.orders_used,
            )
            for band in analysis.bands
        ),
        facts=tuple(facts),
    )


__all__ = [
    "SweepBandSummary",
    "SweepFact",
    "SweepMeasurement",
    "measure_sweep_recording",
]
