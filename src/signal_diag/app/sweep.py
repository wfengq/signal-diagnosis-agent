"""Sweep stimulus test: deterministic verdicts and service (D054, §29).

Each recording at one level is measured (``tools.sweep``) and judged by the
versioned ``profile_s1_sweep`` (``rules.sweep``). A verdict follows only from
those rule evaluations, and every claim cites the facts and evaluations of the
same run. No model is called.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.dsp.sweep import SUPPORTED_RATES, generate_stimulus
from signal_diag.rules.sweep import (
    SweepRuleEvaluation,
    evaluate_sweep,
    load_sweep_profile,
)
from signal_diag.signal import load_wav_bytes
from signal_diag.tools.sweep import SweepMeasurement, measure_sweep_recording

SWEEP_ENGINE_VERSION = "sweep-engine-1.0"
MAX_LEVELS = 3
SweepOutcome = Literal["supported_fault", "no_supported_fault", "inconclusive"]
SweepFaultType = Literal[
    "clipping", "harmonic_distortion", "no_supported_fault", "inconclusive"
]


class SweepClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str = Field(pattern=r"^swc_")
    fault_type: SweepFaultType
    statement: str = Field(min_length=1)
    bands_hz: tuple[float, ...] = ()
    fact_refs: tuple[str, ...]
    rule_refs: tuple[str, ...]


class SweepLevelResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    level_label: str
    outcome: SweepOutcome
    claims: tuple[SweepClaim, ...]
    measurement: SweepMeasurement
    rule_evaluations: tuple[SweepRuleEvaluation, ...]


class SweepDiagnosis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    run_id: str = Field(pattern=r"^swrun_")
    engine_version: str = SWEEP_ENGINE_VERSION
    profile_id: str
    profile_version: str
    sample_rate_hz: int
    outcome: SweepOutcome
    onset_level: str | None
    summary: str
    levels: tuple[SweepLevelResult, ...]
    model_calls: int = 0


def stimulus_wav(sample_rate_hz: int) -> bytes:
    """The versioned stimulus as 32-bit PCM WAV."""
    samples, _ = generate_stimulus(sample_rate_hz)
    return encode_pcm32_wav(
        samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=sample_rate_hz
    )


def _claim_id(level: str, fault: str, refs: tuple[str, ...]) -> str:
    payload = json.dumps([level, fault, refs])
    return "swc_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _judge(
    measurement: SweepMeasurement, evaluations: tuple[SweepRuleEvaluation, ...]
) -> tuple[SweepOutcome, tuple[SweepClaim, ...]]:
    level = measurement.level_label
    validity = [item for item in evaluations if item.role == "validity"]
    failed_validity = [item for item in validity if item.judgment != "pass"]
    if failed_validity:
        refs = tuple(ref for item in failed_validity for ref in item.fact_refs)
        rules = tuple(item.evaluation_id for item in failed_validity)
        return "inconclusive", (
            SweepClaim(
                claim_id=_claim_id(level, "inconclusive", rules),
                fault_type="inconclusive",
                statement="The recording does not meet the sweep test's validity rules: "
                + ", ".join(sorted({item.rule_id for item in failed_validity})),
                fact_refs=refs,
                rule_refs=rules,
            ),
        )
    claims: list[SweepClaim] = []
    clipping = [
        item
        for item in evaluations
        if item.role == "clipping" and item.judgment == "fail"
    ]
    if clipping:
        rules = tuple(item.evaluation_id for item in clipping)
        span = measurement.clipped_frequency_hz
        where = (
            f" between {span[0]:g} Hz and {span[1]:g} Hz of the sweep" if span else ""
        )
        claims.append(
            SweepClaim(
                claim_id=_claim_id(level, "clipping", rules),
                fault_type="clipping",
                statement=f"The recording reaches full scale{where}.",
                fact_refs=tuple(ref for item in clipping for ref in item.fact_refs),
                rule_refs=rules,
            )
        )
    harmonic = [
        item
        for item in evaluations
        if item.role == "harmonic" and item.judgment == "fail"
    ]
    if harmonic:
        rules = tuple(item.evaluation_id for item in harmonic)
        bands = tuple(
            sorted(item.band_hz for item in harmonic if item.band_hz is not None)
        )
        orders = {
            band.center_hz: band.dominant_order
            for band in measurement.bands
            if band.center_hz in bands
        }
        detail = ", ".join(
            f"{center:g} Hz (order {orders[center]})" for center in bands
        )
        claims.append(
            SweepClaim(
                claim_id=_claim_id(level, "harmonic_distortion", rules),
                fault_type="harmonic_distortion",
                statement=f"Octave-band THD exceeds the demonstration limit at {detail}.",
                bands_hz=bands,
                fact_refs=tuple(ref for item in harmonic for ref in item.fact_refs),
                rule_refs=rules,
            )
        )
    if claims:
        return "supported_fault", tuple(claims)
    passing = [
        item
        for item in evaluations
        if item.role == "harmonic" and item.judgment == "pass"
    ]
    clipping_pass = [
        item
        for item in evaluations
        if item.role == "clipping" and item.judgment == "pass"
    ]
    if passing and clipping_pass:
        cited = [*validity, *clipping_pass, *passing]
        rules = tuple(item.evaluation_id for item in cited)
        return "no_supported_fault", (
            SweepClaim(
                claim_id=_claim_id(level, "no_supported_fault", rules),
                fault_type="no_supported_fault",
                statement="Every measurable band and the full-scale check pass.",
                bands_hz=tuple(
                    item.band_hz for item in passing if item.band_hz is not None
                ),
                fact_refs=tuple(ref for item in cited for ref in item.fact_refs),
                rule_refs=rules,
            ),
        )
    rules = tuple(item.evaluation_id for item in evaluations if item.role == "harmonic")
    return "inconclusive", (
        SweepClaim(
            claim_id=_claim_id(level, "inconclusive", rules),
            fault_type="inconclusive",
            statement="No octave band could be measured above the noise floor.",
            fact_refs=(),
            rule_refs=rules,
        ),
    )


def diagnose_sweep(
    recordings: list[tuple[bytes, str]], *, sample_rate_hz: int
) -> SweepDiagnosis:
    """Judge 1–3 recordings, given in increasing level order."""
    if sample_rate_hz not in SUPPORTED_RATES:
        raise ValueError(f"sample rate must be one of {SUPPORTED_RATES}")
    if not 1 <= len(recordings) <= MAX_LEVELS:
        raise ValueError(f"upload 1 to {MAX_LEVELS} recordings")
    labels = [label for _, label in recordings]
    if len(set(labels)) != len(labels):
        raise ValueError("level labels must be unique")
    profile = load_sweep_profile()
    levels: list[SweepLevelResult] = []
    for data, label in recordings:
        loaded = load_wav_bytes(data, filename=f"{label}.wav")
        if loaded.record.meta.sample_rate_hz != sample_rate_hz:
            raise ValueError(
                f"recording {label!r} is {loaded.record.meta.sample_rate_hz} Hz; "
                f"the stimulus is {sample_rate_hz} Hz"
            )
        mono = np.mean(loaded.record.samples, axis=1)
        measurement = measure_sweep_recording(mono, sample_rate_hz, level_label=label)
        evaluations = evaluate_sweep(profile, measurement)
        outcome, claims = _judge(measurement, evaluations)
        levels.append(
            SweepLevelResult(
                level_label=label,
                outcome=outcome,
                claims=claims,
                measurement=measurement,
                rule_evaluations=evaluations,
            )
        )
    onset = next(
        (item.level_label for item in levels if item.outcome == "supported_fault"), None
    )
    if onset is not None:
        overall: SweepOutcome = "supported_fault"
        summary = f"Distortion is supported from level {onset}."
        clean = [
            item.level_label
            for item in levels[: labels.index(onset)]
            if item.outcome == "no_supported_fault"
        ]
        if clean:
            summary += " Lower levels pass: " + ", ".join(clean) + "."
    elif levels and all(item.outcome == "no_supported_fault" for item in levels):
        overall, summary = "no_supported_fault", "No supported fault at any level."
    else:
        overall, summary = "inconclusive", "At least one level could not be judged."
    run_id = (
        "swrun_"
        + hashlib.sha256(
            json.dumps([item.measurement.measurement_id for item in levels]).encode()
        ).hexdigest()[:24]
    )
    return SweepDiagnosis(
        run_id=run_id,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        sample_rate_hz=sample_rate_hz,
        outcome=overall,
        onset_level=onset,
        summary=summary,
        levels=tuple(levels),
    )


__all__ = [
    "MAX_LEVELS",
    "SWEEP_ENGINE_VERSION",
    "SweepClaim",
    "SweepDiagnosis",
    "SweepLevelResult",
    "diagnose_sweep",
    "stimulus_wav",
]
