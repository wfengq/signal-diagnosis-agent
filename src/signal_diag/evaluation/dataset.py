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
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

_OFFICIAL_DATASET_ID = "s1-distortion-synthetic"
_OFFICIAL_VERSION = "1.0.0"
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


def _materialize_case(case: EvaluationCase, repository: SignalRepository) -> SignalRecord:
    generated = _generate(case)
    record = build_signal_record(
        generated.record.samples,
        sample_rate_hz=generated.record.meta.sample_rate_hz,
        source_type="generated",
        signal_id=_stable_signal_id(case.case_id),
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
    return indexed


def _allocation_issues(manifest: DatasetManifest) -> list[DatasetValidationIssue]:
    if (
        manifest.dataset_id != _OFFICIAL_DATASET_ID
        or manifest.version != _OFFICIAL_VERSION
    ):
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
                    "official s1-distortion-synthetic 1.0.0 allocation must be "
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


def _identifiability_issues(
    case: EvaluationCase,
    indexed: dict[tuple[str, str], Evidence],
    repository: SignalRepository,
    tool_service: SignalToolService,
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
    # Symmetric clipping often emits no even-order Evidence; absence is amplitude 0.
    control_value = 0.0 if matched is None else matched.value
    if (
        combined is None
        or type(combined.value) is not float
        or type(control_value) is not float
        or abs(combined.value - control_value) < ident.minimum_absolute_separation
    ):
        return [
            DatasetValidationIssue(
                code="identifiability",
                case_id=case.case_id,
                message=(
                    "combined case does not exceed the matched clipping-only "
                    "control by the declared harmonic-signature separation"
                ),
            )
        ]
    return []


def validate_dataset(
    manifest: DatasetManifest,
    repository: SignalRepository,
    tool_service: SignalToolService,
    rule_engine: RuleEngine,
    profile_loader: RuleProfileLoader,
) -> DatasetValidationReport:
    issues: list[DatasetValidationIssue] = []
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
            _identifiability_issues(case, indexed, repository, tool_service)
        )
    issue_tuple = tuple(issues)
    return DatasetValidationReport(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        valid=not issue_tuple,
        checked_case_ids=tuple(case.case_id for case in manifest.cases),
        issues=issue_tuple,
    )
