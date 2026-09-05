"""Development-only even-harmonic growth threshold calibration."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
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


def product_package_sha256(*relative_paths: str) -> str:
    """SHA-256 over sorted relative paths and file bytes under ``signal_diag``."""
    package_root = Path(__file__).resolve().parents[2]
    digest = sha256()
    for relative in sorted(relative_paths):
        path = package_root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def contextual_implementation_sha256() -> str:
    """Identity of the contextual calibration-relevant implementation tree."""
    package_root = Path(__file__).resolve().parents[2]
    paths: list[str] = []
    contextual_dir = package_root / "evaluation" / "contextual"
    for path in sorted(contextual_dir.glob("*.py")):
        paths.append(str(path.relative_to(package_root)).replace("\\", "/"))
    paths.extend(
        [
            "app/contextual_campaign.py",
            "dsp/contextual.py",
            "dsp/clipping.py",
            "dsp/harmonics.py",
            "rules/profiles/s1_contextual_comparison_v1.yaml",
        ]
    )
    return product_package_sha256(*paths)


def contextual_product_tree_sha256() -> str:
    """Hash the live product tree used by contextual diagnosis.

    The provider-facing campaign adapter is evaluation harness code and is
    intentionally covered by :func:`contextual_implementation_sha256` instead.
    """

    package_root = Path(__file__).resolve().parents[2]
    paths: list[str] = []
    for directory in ("signal", "dsp", "tools", "rules", "knowledge", "agent", "app"):
        for path in sorted((package_root / directory).rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".yaml", ".md"}:
                continue
            relative = str(path.relative_to(package_root)).replace("\\", "/")
            if relative == "app/contextual_campaign.py":
                continue
            paths.append(relative)
    return product_package_sha256(*paths)


def stable_code_sha(text: str) -> str:
    """Deprecated alias retained for older tests; prefer ``contextual_implementation_sha256``."""
    return sha256(text.encode("utf-8")).hexdigest()


def resolve_active_freeze_code_sha256(study_dir: Path) -> str:
    """Resolve active freeze code identity via freeze record or append-only amendment.

    If ``profile_freeze_record.json`` already matches the current implementation
    tree, return that digest. Otherwise require ``code_identity_amendment.json``
    to bridge the recorded calibration SHA to the current implementation SHA.
    """
    study_dir = study_dir.resolve()
    freeze_path = study_dir / "profile_freeze_record.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    recorded = str(freeze["code_sha256"])
    current = contextual_implementation_sha256()
    if recorded == current:
        return current
    amendment_path = study_dir / "code_identity_amendment.json"
    if not amendment_path.is_file():
        raise ValueError(
            "freeze code SHA does not match current implementation and no amendment"
        )
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    rows = amendment if isinstance(amendment, list) else [amendment]
    for row in rows:
        if (
            str(row["original_calibration_code_sha256"]) == recorded
            and str(row["current_implementation_sha256"]) == current
        ):
            return current
    raise ValueError(
        "no amendment bridges freeze record code SHA to current implementation"
    )
