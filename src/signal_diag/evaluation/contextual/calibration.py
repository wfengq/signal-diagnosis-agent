"""Development-only even-harmonic growth threshold calibration."""

from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.evaluation.contextual.manifest import manifest_sha256
from signal_diag.evaluation.contextual.models import ContextualManifest

CONTEXTUAL_GROWTH_CANDIDATES: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0, 5.0)


class CandidateConfusion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    threshold_percent: float
    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    true_negatives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)
    specificity: float = Field(ge=0.0, le=1.0)
    sensitivity: float = Field(ge=0.0, le=1.0)


class CalibrationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    calibration_status: Literal["selected", "blocked"]
    candidates: tuple[CandidateConfusion, ...]
    selected_threshold_percent: float | None
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _specificity(tn: int, fp: int) -> float:
    denom = tn + fp
    return 1.0 if denom == 0 else tn / denom


def _sensitivity(tp: int, fn: int) -> float:
    denom = tp + fn
    return 0.0 if denom == 0 else tp / denom


def calibrate_even_growth_threshold(
    *,
    manifest: ContextualManifest,
    control_growth_percents: tuple[float, ...],
    positive_growth_percents: tuple[float, ...],
    code_sha256: str,
    candidates: tuple[float, ...] = CONTEXTUAL_GROWTH_CANDIDATES,
) -> CalibrationReport:
    """Select the largest candidate with 100% specificity and >=90% sensitivity."""
    if not control_growth_percents or not positive_growth_percents:
        raise ValueError("calibration requires control and positive growth samples")
    rows: list[CandidateConfusion] = []
    selected: float | None = None
    for threshold in sorted(candidates):
        tp = sum(1 for value in positive_growth_percents if value > threshold)
        fn = len(positive_growth_percents) - tp
        fp = sum(1 for value in control_growth_percents if value > threshold)
        tn = len(control_growth_percents) - fp
        specificity = _specificity(tn, fp)
        sensitivity = _sensitivity(tp, fn)
        rows.append(
            CandidateConfusion(
                threshold_percent=threshold,
                true_positives=tp,
                false_positives=fp,
                true_negatives=tn,
                false_negatives=fn,
                specificity=specificity,
                sensitivity=sensitivity,
            )
        )
        if specificity == 1.0 and sensitivity >= 0.90:
            selected = threshold
    status: Literal["selected", "blocked"] = (
        "selected" if selected is not None else "blocked"
    )
    return CalibrationReport(
        calibration_status=status,
        candidates=tuple(rows),
        selected_threshold_percent=selected,
        source_manifest_sha256=manifest_sha256(manifest),
        code_sha256=code_sha256,
    )


def stable_code_sha(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()
