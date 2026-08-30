"""Canonical dataset loading, materialization, and validation.

Fixture calibration notes (dataset QA only; not product thresholds):

- THD-at-boundary harmonic rows inject second-harmonic ratio ``0.04999999``
  so measured THD is about ``4.9999993522848%``, inside the stacked
  ``gte 4.999`` / ``lte 5.001`` window and the rule condition ``lte 5.0``.
- ``case_held_clean_01`` uses 220 Hz at amplitude 0.35. A 100 Hz sine at
  the same amplitude false-triggers the existing DSP 1e-4 flat-top
  detector near peaks; that is a known DSP/dataset-calibration limitation.
"""

from __future__ import annotations

import hashlib
import operator
from collections import Counter
from pathlib import Path

import numpy as np
import yaml
from pydantic import ValidationError

from signal_diag.evaluation.models import (
    ClippedSineSignalSpec,
    CombinedDistortionSignalSpec,
    DatasetManifest,
    DatasetValidationIssue,
    DatasetValidationReport,
    EvaluationCase,
    EvidenceCondition,
    HarmonicSineSignalSpec,
    SineSignalSpec,
    WhiteNoiseSignalSpec,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.models import RuleProfileLoader
from signal_diag.signal.factory import build_signal_record
from signal_diag.signal.models import SignalRecord
from signal_diag.signal.repository import SignalRepository
from signal_diag.signal.synthetic import (
    SyntheticCase,
    generate_clipped_sine,
    generate_combined_distortion,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from signal_diag.tools.contracts import (
    ClippingInput,
    FundamentalInput,
    HarmonicDistortionInput,
)
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

_OFFICIAL_DATASET_ID = "s1-distortion-synthetic"
_SUPPORTED_DATASETS = frozenset(
    {
        ("s1-distortion-synthetic", "1.0.0"),
        ("s1-distortion-synthetic", "1.1.0"),
        ("s1-distortion-synthetic", "1.2.0"),
    }
)
_ORDER2_RELATIVE_AMPLITUDE = "harmonic_order_2_relative_amplitude"
_DEV_CATEGORY_COUNTS = {
    "clean": 2,
    "clipping": 2,
    "harmonic": 2,
    "combined": 1,
    "invalid_noise": 1,
}
_HELD_CATEGORY_COUNTS = {
    "clean": 3,
    "clipping": 4,
    "harmonic": 4,
    "combined": 3,
    "invalid_noise": 2,
}
_COMPARATORS = {
    "eq": operator.eq,
    "neq": operator.ne,
    "lt": operator.lt,
    "lte": operator.le,
    "gt": operator.gt,
    "gte": operator.ge,
}


def load_dataset_manifest(path: Path) -> DatasetManifest:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return DatasetManifest.model_validate(payload)


def _stable_signal_id(case_id: str) -> str:
    return f"sig_eval_{case_id.removeprefix('case_')}"


def _opaque_evaluation_signal_id(
    dataset_id: str, dataset_version: str, case_id: str
) -> str:
    raw = f"{dataset_id}\0{dataset_version}\0{case_id}".encode()
    return f"sig_eval_{hashlib.sha256(raw).hexdigest()[:24]}"


def _harmonic_ratio_map(
    spec: HarmonicSineSignalSpec | CombinedDistortionSignalSpec,
) -> dict[int, float]:
    return {item.order: item.ratio for item in spec.harmonic_ratios}


def _generate(case: EvaluationCase) -> SyntheticCase:
    spec = case.signal
    if isinstance(spec, SineSignalSpec):
        return generate_sine(
            frequency_hz=spec.frequency_hz,
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            amplitude=spec.amplitude,
            phase_rad=spec.phase_rad,
            dc_offset=spec.dc_offset,
        )
    if isinstance(spec, ClippedSineSignalSpec):
        return generate_clipped_sine(
            frequency_hz=spec.frequency_hz,
            clip_level=spec.clip_level,
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            amplitude=spec.amplitude,
        )
    if isinstance(spec, HarmonicSineSignalSpec):
        return generate_harmonic_sine(
            fundamental_hz=spec.fundamental_hz,
            harmonic_ratios=_harmonic_ratio_map(spec),
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            fundamental_amplitude=spec.fundamental_amplitude,
        )
    if isinstance(spec, CombinedDistortionSignalSpec):
        return generate_combined_distortion(
            fundamental_hz=spec.fundamental_hz,
            harmonic_ratios=_harmonic_ratio_map(spec),
            clip_level=spec.clip_level,
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            fundamental_amplitude=spec.fundamental_amplitude,
        )
    if isinstance(spec, WhiteNoiseSignalSpec):
        return generate_white_noise(
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            rms=spec.rms,
            seed=spec.seed,
        )
    raise TypeError(f"unsupported signal spec: {type(spec)!r}")


def _materialize_case(
    case: EvaluationCase,
    repository: SignalRepository,
    *,
    signal_id: str | None = None,
) -> SignalRecord:
    generated = _generate(case)
    record = build_signal_record(
        generated.record.samples,
        sample_rate_hz=generated.record.meta.sample_rate_hz,
        source_type="generated",
        signal_id=signal_id if signal_id is not None else _stable_signal_id(case.case_id),
    )
    repository.put(record)
    return record


def _condition_matches(condition: EvidenceCondition, evidence: Evidence) -> bool:
    if evidence.source_tool != condition.tool_name:
        return False
    if evidence.metric != condition.metric:
        return False
    if evidence.validity != condition.validity:
        return False
    if type(evidence.value) is not type(condition.expected_value):
        return False
    if evidence.unit != condition.unit:
        return False
    return bool(_COMPARATORS[condition.comparator](evidence.value, condition.expected_value))


def _collect_evidence(
    case: EvaluationCase,
    signal_id: str,
    tool_service: SignalToolService,
) -> dict[tuple[str, str], Evidence]:
    indexed: dict[tuple[str, str], Evidence] = {}
    needed = {condition.tool_name for condition in case.observable_conditions}
    if "detect_clipping" in needed:
        clipping_result = tool_service.detect_clipping(signal_id, ClippingInput())
        for item in clipping_result.evidence:
            indexed[(item.source_tool, item.metric)] = item
    if "analyze_harmonic_distortion" in needed:
        harmonic_result = tool_service.analyze_harmonic_distortion(
            signal_id,
            HarmonicDistortionInput(),
        )
        for item in harmonic_result.evidence:
            indexed[(item.source_tool, item.metric)] = item
    if "estimate_fundamental" in needed:
        fundamental_result = tool_service.estimate_fundamental(
            signal_id,
            FundamentalInput(),
        )
        for item in fundamental_result.evidence:
            indexed[(item.source_tool, item.metric)] = item
    return indexed


def _identity_issues(manifest: DatasetManifest) -> list[DatasetValidationIssue]:
    if manifest.dataset_id != _OFFICIAL_DATASET_ID:
        return []
    if (manifest.dataset_id, manifest.version) in _SUPPORTED_DATASETS:
        return []
    return [
        DatasetValidationIssue(
            code="dataset_identity",
            message=(
                "unsupported dataset identity: "
                f"{manifest.dataset_id} {manifest.version}"
            ),
        )
    ]


def _allocation_issues(manifest: DatasetManifest) -> list[DatasetValidationIssue]:
    if (manifest.dataset_id, manifest.version) not in _SUPPORTED_DATASETS:
        return []
    development = [case for case in manifest.cases if case.split == "development"]
    held_out = [case for case in manifest.cases if case.split == "held_out"]
    if (
        len(development) != 8
        or len(held_out) != 16
        or Counter(case.category for case in development) != _DEV_CATEGORY_COUNTS
        or Counter(case.category for case in held_out) != _HELD_CATEGORY_COUNTS
    ):
        return [
            DatasetValidationIssue(
                code="allocation",
                message=(
                    "official s1-distortion-synthetic allocation must be "
                    "8 development and 16 held-out cases with frozen category counts"
                ),
            )
        ]
    return []


def _profile_issues(
    manifest: DatasetManifest,
    rule_engine: RuleEngine,
    profile_loader: RuleProfileLoader,
) -> list[DatasetValidationIssue]:
    try:
        profile = profile_loader.load(manifest.rule_profile_id)
    except (KeyError, ValueError, OSError, ValidationError, yaml.YAMLError) as error:
        return [
            DatasetValidationIssue(
                code="profile_identity",
                message=f"failed to load rule profile: {error}",
            )
        ]
    if (
        profile.profile_id != manifest.rule_profile_id
        or profile.version != manifest.rule_profile_version
    ):
        return [
            DatasetValidationIssue(
                code="profile_identity",
                message="rule profile identity does not match the manifest",
            )
        ]
    batch = rule_engine.evaluate_profile(profile, ())
    if (
        batch.profile_id != manifest.rule_profile_id
        or batch.profile_version != manifest.rule_profile_version
    ):
        return [
            DatasetValidationIssue(
                code="profile_identity",
                message="rule engine profile identity does not match the manifest",
            )
        ]
    return []


def _observable_issues(
    case: EvaluationCase,
    indexed: dict[tuple[str, str], Evidence],
) -> list[DatasetValidationIssue]:
    issues: list[DatasetValidationIssue] = []
    for condition in case.observable_conditions:
        evidence = indexed.get((condition.tool_name, condition.metric))
        if evidence is None or not _condition_matches(condition, evidence):
            issues.append(
                DatasetValidationIssue(
                    code="observable_condition",
                    case_id=case.case_id,
                    message=(
                        f"observable condition {condition.condition_id} "
                        "is not satisfied by real Tool Evidence"
                    ),
                )
            )
    return issues


def _control_harmonic_is_valid(result: object) -> bool:
    status = getattr(result, "status", None)
    evidence = getattr(result, "evidence", ())
    if status != "success":
        return False
    return any(
        item.metric == "valid" and item.value is True and item.validity == "valid"
        for item in evidence
    )


def _identifiability_issues(
    case: EvaluationCase,
    indexed: dict[tuple[str, str], Evidence],
    repository: SignalRepository,
    tool_service: SignalToolService,
    *,
    treat_absent_order_2_as_zero: bool = False,
) -> list[DatasetValidationIssue]:
    spec = case.signal
    ident = case.identifiability
    if ident is None or not isinstance(spec, CombinedDistortionSignalSpec):
        return []
    combined = indexed.get(("analyze_harmonic_distortion", ident.signature_metric))
    control_id = f"sig_eval_control_{case.case_id.removeprefix('case_')}"
    generated = generate_clipped_sine(
        frequency_hz=spec.fundamental_hz,
        clip_level=spec.clip_level,
        sample_rate_hz=spec.sample_rate_hz,
        duration_s=spec.duration_s,
        amplitude=spec.fundamental_amplitude,
    )
    control = build_signal_record(
        generated.record.samples,
        sample_rate_hz=generated.record.meta.sample_rate_hz,
        source_type="generated",
        signal_id=control_id,
    )
    repository.put(control)
    try:
        result = tool_service.analyze_harmonic_distortion(
            control_id,
            HarmonicDistortionInput(),
        )
        matched = next(
            (
                item
                for item in result.evidence
                if item.metric == ident.signature_metric
            ),
            None,
        )
    finally:
        repository.remove(control_id)
    ident_issue = [
        DatasetValidationIssue(
            code="identifiability",
            case_id=case.case_id,
            message=(
                "combined case does not exceed the matched clipping-only "
                "control by the declared harmonic-signature separation"
            ),
        )
    ]
    if matched is not None:
        control_value = matched.value
    elif treat_absent_order_2_as_zero:
        if (
            ident.signature_metric == _ORDER2_RELATIVE_AMPLITUDE
            and _control_harmonic_is_valid(result)
        ):
            control_value = 0.0
        else:
            return ident_issue
    else:
        # Historical v1.0/v1.1: missing matched-control component is amplitude 0.
        control_value = 0.0
    if (
        combined is None
        or type(combined.value) is not float
        or type(control_value) is not float
        or abs(combined.value - control_value) < ident.minimum_absolute_separation
    ):
        return ident_issue
    return []


def validate_dataset(
    manifest: DatasetManifest,
    repository: SignalRepository,
    tool_service: SignalToolService,
    rule_engine: RuleEngine,
    profile_loader: RuleProfileLoader,
) -> DatasetValidationReport:
    issues: list[DatasetValidationIssue] = []
    issues.extend(_identity_issues(manifest))
    issues.extend(_allocation_issues(manifest))
    issues.extend(_profile_issues(manifest, rule_engine, profile_loader))
    for case in manifest.cases:
        first = _materialize_case(case, repository)
        second = _materialize_case(case, repository)
        if first.meta != second.meta or not np.array_equal(first.samples, second.samples):
            issues.append(
                DatasetValidationIssue(
                    code="reconstruction",
                    case_id=case.case_id,
                    message=f"seeded reconstruction mismatch for {case.case_id}",
                )
            )
        indexed = _collect_evidence(case, first.meta.signal_id, tool_service)
        issues.extend(_observable_issues(case, indexed))
        issues.extend(
            _identifiability_issues(
                case,
                indexed,
                repository,
                tool_service,
                treat_absent_order_2_as_zero=manifest.version == "1.2.0",
            )
        )
    issue_tuple = tuple(issues)
    return DatasetValidationReport(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        valid=not issue_tuple,
        checked_case_ids=tuple(case.case_id for case in manifest.cases),
        issues=issue_tuple,
    )
