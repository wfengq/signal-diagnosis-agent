"""External study manifest validation for counts, labels, provenance, and isolation."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from signal_diag.evaluation.external.models import (
    CoverageDimensionReport,
    ExternalCase,
    ExternalCoverageReport,
    ExternalDatasetManifest,
    ExternalSplit,
    ExternalValidationIssue,
    ExternalValidationReport,
    LabelConfidence,
    SourceGroup,
)
from signal_diag.signal.wav import InvalidWavError, load_wav_bytes

ValidationStage = Literal["development", "validation", "final_preflight"]

PLANNED_SPLIT_COUNTS: dict[ExternalSplit, int] = {
    "development": 14,
    "validation": 10,
    "final_external_test": 28,
}
PLANNED_GROUP_COUNTS: dict[SourceGroup, int] = {"A": 12, "B": 28, "C": 12}
PLANNED_CONFIDENCE_WHOLE: dict[LabelConfidence, int] = {
    "strong_ground_truth": 21,
    "reference_supported": 23,
    "weak_observation": 4,
    "unknown": 4,
}
PLANNED_CONFIDENCE_FINAL: dict[LabelConfidence, int] = {
    "strong_ground_truth": 12,
    "reference_supported": 12,
    "weak_observation": 2,
    "unknown": 2,
}
PLANNED_CLASS_WHOLE: dict[str, int] = {
    "no_supported_fault": 11,
    "clipping_only": 7,
    "harmonic_only": 7,
    "combined": 7,
    "reference_inconclusive": 12,
    "weak_unknown": 8,
}
PLANNED_CLASS_FINAL: dict[str, int] = {
    "no_supported_fault": 6,
    "clipping_only": 4,
    "harmonic_only": 4,
    "combined": 4,
    "reference_inconclusive": 6,
    "weak_unknown": 4,
}
B_VARIANT_CLASSES: frozenset[str] = frozenset(
    {"clean", "clipping", "harmonic", "combined"},
)
SCOREABLE_CONFIDENCES: frozenset[str] = frozenset(
    {"strong_ground_truth", "reference_supported"},
)
FORBIDDEN_TRUTH_TOKENS: tuple[str, ...] = (
    "SMARD",
    "Pyramic",
    "ESC",
    "NSynth",
    "clipping",
    "harmonic",
    "alpha",
    "parent_master",
    "strong_ground_truth",
    "supported_fault",
    "no_supported_fault",
)
_COVERAGE_MINIMUMS_WHOLE: dict[str, int] = {
    "loudspeaker": 2,
    "microphone_position": 2,
    "distance": 2,
    "playback_level": 2,
    "acoustic_environment": 2,
    "f0_band": 3,
}
_COVERAGE_MINIMUMS_FINAL: dict[str, int] = {
    "loudspeaker": 2,
    "microphone_position": 2,
    "distance": 2,
    "playback_level": 2,
    "acoustic_environment": 2,
    "f0_band": 2,
}
_UNAVAILABLE = "unavailable"


def validate_external_manifest(
    manifest: ExternalDatasetManifest,
    asset_root: Path,
    *,
    stage: ValidationStage,
) -> ExternalValidationReport:
    """Validate *manifest* cases under *asset_root* for the requested *stage*."""
    issues: list[ExternalValidationIssue] = []
    checked_case_ids: list[str] = []

    for case in manifest.cases:
        checked_case_ids.append(case.case_id)
        issues.extend(_validate_case_assets(case, asset_root))
        issues.extend(_validate_truth_free_fields(case))
        issues.extend(_validate_correctness_mask(case))
        issues.extend(_validate_a_group_never_strong(case))

    issues.extend(_validate_b_families(manifest.cases))
    issues.extend(_validate_group_isolation(manifest.cases))
    issues.extend(_validate_digest_non_overlap(manifest.cases))
    issues.extend(_validate_source_configuration_isolation(manifest.cases))

    if stage in {"validation", "final_preflight"}:
        issues.extend(_validate_global_transform_config(manifest.cases))

    if stage == "validation":
        issues.extend(_validate_required_counts(manifest.cases, stage))
    elif stage == "final_preflight":
        issues.extend(_validate_required_counts(manifest.cases, stage))
        issues.extend(_validate_confidence_distributions(manifest.cases))
        issues.extend(_validate_class_distributions(manifest.cases))
        issues.extend(_validate_final_scoreable_slots(manifest.cases))
        issues.extend(_validate_review_references(manifest.cases))

    coverage = _build_coverage_report(manifest.cases, stage)
    if stage == "final_preflight":
        issues.extend(_coverage_target_issues(coverage))

    return ExternalValidationReport(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        stage=stage,
        valid=not issues,
        checked_case_ids=tuple(checked_case_ids),
        issues=tuple(issues),
        coverage=coverage,
    )


def _issue(
    code: str, message: str, *, case_id: str | None = None
) -> ExternalValidationIssue:
    return ExternalValidationIssue(code=code, case_id=case_id, message=message)


def _validate_case_assets(
    case: ExternalCase, asset_root: Path
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    wav_path = asset_root / case.analysis_wav_path
    if not wav_path.is_file():
        issues.append(
            _issue(
                "missing_analysis_wav",
                f"analysis WAV not found: {case.analysis_wav_path}",
                case_id=case.case_id,
            )
        )
        return issues

    payload = wav_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != case.wav_sha256:
        issues.append(
            _issue(
                "wav_digest_mismatch",
                "analysis WAV SHA-256 does not match manifest",
                case_id=case.case_id,
            )
        )

    try:
        loaded = load_wav_bytes(payload, filename=wav_path.name)
    except InvalidWavError as exc:
        issues.append(
            _issue(
                "wav_loader_rejected",
                f"frozen loader rejected analysis WAV: {exc}",
                case_id=case.case_id,
            )
        )
        return issues

    record = loaded.record
    source_info = loaded.source_info
    if record.meta.sample_rate_hz != case.wav_sample_rate_hz:
        issues.append(
            _issue(
                "wav_format_mismatch",
                "sample rate does not match manifest",
                case_id=case.case_id,
            )
        )
    sample_width_bytes = source_info.bits_per_sample // 8
    if sample_width_bytes != case.wav_sample_width_bytes:
        issues.append(
            _issue(
                "wav_format_mismatch",
                "sample width does not match manifest",
                case_id=case.case_id,
            )
        )
    if record.meta.channels != case.wav_channels:
        issues.append(
            _issue(
                "wav_format_mismatch",
                "channel count does not match manifest",
                case_id=case.case_id,
            )
        )
    if record.meta.num_samples != case.wav_frames:
        issues.append(
            _issue(
                "wav_format_mismatch",
                "frame count does not match manifest",
                case_id=case.case_id,
            )
        )
    return issues


def _validate_truth_free_fields(case: ExternalCase) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    filename = case.analysis_wav_path.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    if not re.fullmatch(
        rf"extwav_{case.split}_{case.case_id}\.wav",
        filename,
    ):
        issues.append(
            _issue(
                "truth_leaking_filename",
                "analysis filename must be opaque and truth-free",
                case_id=case.case_id,
            )
        )

    for field_name, value in (
        ("case_id", case.case_id),
        ("provenance_ref", case.provenance_ref),
        ("review_ref", case.review_ref),
    ):
        for token in FORBIDDEN_TRUTH_TOKENS:
            if token.lower() in value.lower():
                issues.append(
                    _issue(
                        "truth_leaking_identifier",
                        f"{field_name} contains forbidden truth token: {token}",
                        case_id=case.case_id,
                    )
                )
    return issues


def _validate_correctness_mask(case: ExternalCase) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    if case.confidence in {"weak_observation", "unknown"}:
        if case.acceptable_outcomes or case.causal_faults:
            issues.append(
                _issue(
                    "weak_unknown_exposes_scoring_truth",
                    "weak/unknown cases must not expose correctness truth",
                    case_id=case.case_id,
                )
            )
    elif (
        case.confidence in SCOREABLE_CONFIDENCES
        and not case.acceptable_outcomes
        and not case.causal_faults
    ):
        issues.append(
            _issue(
                "scoreable_case_missing_truth",
                "strong/reference cases require scoring truth",
                case_id=case.case_id,
            )
        )
    return issues


def _validate_a_group_never_strong(case: ExternalCase) -> list[ExternalValidationIssue]:
    if case.source_group != "A":
        return []
    if case.confidence == "strong_ground_truth":
        return [
            _issue(
                "a_overload_promoted_to_strong",
                "A-group overload or real-capture cases must never be strong ground truth",
                case_id=case.case_id,
            )
        ]
    return []


def _validate_b_families(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    families: dict[str, list[ExternalCase]] = defaultdict(list)
    for case in cases:
        if case.source_group == "B":
            families[case.parent_master_id or ""].append(case)

    for parent_id, members in sorted(families.items()):
        if not parent_id:
            continue
        classes = {member.external_class for member in members}
        if classes != B_VARIANT_CLASSES:
            missing = sorted(B_VARIANT_CLASSES - classes)
            extra = sorted(classes - B_VARIANT_CLASSES)
            issues.append(
                _issue(
                    "incomplete_b_family",
                    (
                        f"parent {parent_id} missing variants {missing}"
                        if missing
                        else f"parent {parent_id} has unexpected variants {extra}"
                    ),
                )
            )
        splits = {member.split for member in members}
        if len(splits) != 1:
            issues.append(
                _issue(
                    "parent_master_split_leakage",
                    f"parent {parent_id} variants span splits {sorted(splits)}",
                )
            )
        source_keys = {member.source_recording_key for member in members}
        capture_keys = {member.capture_configuration_key for member in members}
        if len(source_keys) != 1 or len(capture_keys) != 1:
            issues.append(
                _issue(
                    "b_family_configuration_mismatch",
                    f"parent {parent_id} variants must share source and capture keys",
                )
            )
    return issues


def _validate_group_isolation(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    key_splits: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        for key in (
            case.source_recording_key,
            case.capture_configuration_key,
        ):
            key_splits[key].add(case.split)
            if len(key_splits[key]) > 1:
                issues.append(
                    _issue(
                        "group_key_split_leakage",
                        f"group key {key!r} appears in multiple splits",
                        case_id=case.case_id,
                    )
                )
    return issues


def _validate_digest_non_overlap(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    digest_splits: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        digests = [case.wav_sha256]
        if case.transform is not None:
            digests.extend(
                [case.transform.input_sha256, case.transform.output_sha256],
            )
        for digest in digests:
            digest_splits[digest].add(case.split)
            if len(digest_splits[digest]) > 1:
                issues.append(
                    _issue(
                        "digest_split_leakage",
                        f"digest {digest} appears in multiple splits",
                        case_id=case.case_id,
                    )
                )
    return issues


def _validate_source_configuration_isolation(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    esc_splits: dict[str, set[str]] = defaultdict(set)
    nsynth_splits: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        if case.source_group != "C":
            continue
        if case.source_recording_key.startswith("esc_src_file:"):
            esc_key = case.source_recording_key.removeprefix("esc_src_file:")
            esc_splits[esc_key].add(case.split)
            if len(esc_splits[esc_key]) > 1:
                issues.append(
                    _issue(
                        "esc_src_file_split_leakage",
                        f"ESC src_file {esc_key!r} crosses splits",
                        case_id=case.case_id,
                    )
                )
        if case.source_recording_key.startswith("nsynth_instrument:"):
            instrument = case.source_recording_key.removeprefix("nsynth_instrument:")
            nsynth_splits[instrument].add(case.split)
            if len(nsynth_splits[instrument]) > 1:
                issues.append(
                    _issue(
                        "nsynth_instrument_split_leakage",
                        f"NSynth instrument {instrument!r} crosses splits",
                        case_id=case.case_id,
                    )
                )
    return issues


def _validate_global_transform_config(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    tail_values: set[float] = set()
    alpha_values: set[float] = set()
    post_gain_values: set[float] = set()
    transform_versions: set[str] = set()
    for case in cases:
        if case.source_group != "B" or case.transform is None:
            continue
        if case.external_class == "clean":
            continue
        transform = case.transform
        transform_versions.add(transform.transform_version)
        if (
            case.external_class in {"clipping", "combined"}
            and transform.tail_proportion is not None
        ):
            tail_values.add(transform.tail_proportion)
        if case.external_class in {"harmonic", "combined"}:
            if transform.alpha is not None:
                alpha_values.add(transform.alpha)
            if transform.post_gain is not None:
                post_gain_values.add(transform.post_gain)

    if len(tail_values) > 1:
        issues.append(
            _issue(
                "global_transform_config_mismatch",
                "B clipping/combined transforms must share one frozen tail_proportion",
            )
        )
    if len(alpha_values) > 1:
        issues.append(
            _issue(
                "global_transform_config_mismatch",
                "B harmonic/combined transforms must share one frozen alpha",
            )
        )
    if len(post_gain_values) > 1:
        issues.append(
            _issue(
                "global_transform_config_mismatch",
                "B harmonic/combined transforms must share one frozen post_gain",
            )
        )
    if len(transform_versions) > 1:
        issues.append(
            _issue(
                "global_transform_config_mismatch",
                "B degraded transforms must share one frozen transform_version",
            )
        )
    return issues


def _validate_required_counts(
    cases: tuple[ExternalCase, ...],
    stage: ValidationStage,
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    split_counts = Counter(case.split for case in cases)
    group_counts = Counter(case.source_group for case in cases)

    if stage == "validation":
        expected_splits: dict[ExternalSplit, int] = {
            "development": 14,
            "validation": 10,
        }
        expected_total = 24
    else:
        expected_splits = PLANNED_SPLIT_COUNTS
        expected_total = 52

    if len(cases) != expected_total:
        issues.append(
            _issue(
                "planned_case_count_mismatch",
                f"expected {expected_total} cases, found {len(cases)}",
            )
        )

    for split_name, expected in expected_splits.items():
        if split_counts.get(split_name, 0) != expected:
            issues.append(
                _issue(
                    "planned_split_count_mismatch",
                    (
                        f"split {split_name} expected {expected} cases, "
                        f"found {split_counts.get(split_name, 0)}"
                    ),
                )
            )

    if stage == "final_preflight":
        for group_name, expected in PLANNED_GROUP_COUNTS.items():
            if group_counts.get(group_name, 0) != expected:
                issues.append(
                    _issue(
                        "planned_group_count_mismatch",
                        (
                            f"group {group_name} expected {expected} cases, "
                            f"found {group_counts.get(group_name, 0)}"
                        ),
                    )
                )
        b_parents = {
            case.parent_master_id
            for case in cases
            if case.source_group == "B" and case.parent_master_id
        }
        if len(b_parents) != 7:
            issues.append(
                _issue(
                    "planned_b_master_count_mismatch",
                    f"expected 7 B parent masters, found {len(b_parents)}",
                )
            )
    return issues


def _validate_confidence_distributions(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    whole = Counter(case.confidence for case in cases)
    final = Counter(
        case.confidence for case in cases if case.split == "final_external_test"
    )
    for label, expected in PLANNED_CONFIDENCE_WHOLE.items():
        if whole.get(label, 0) != expected:
            issues.append(
                _issue(
                    "planned_confidence_distribution_mismatch",
                    f"whole study expected {expected} {label}, found {whole.get(label, 0)}",
                )
            )
    for label, expected in PLANNED_CONFIDENCE_FINAL.items():
        if final.get(label, 0) != expected:
            issues.append(
                _issue(
                    "planned_final_confidence_distribution_mismatch",
                    f"final split expected {expected} {label}, found {final.get(label, 0)}",
                )
            )
    return issues


def _planned_class_bucket(case: ExternalCase) -> str:
    if case.confidence in {"weak_observation", "unknown"}:
        return "weak_unknown"
    if case.external_class == "inconclusive" or (
        case.confidence == "reference_supported"
        and case.external_class in {"inconclusive", "ambiguous"}
        and case.acceptable_outcomes == ("inconclusive",)
    ):
        return "reference_inconclusive"
    if case.external_class == "clean":
        return "no_supported_fault"
    if case.external_class == "clipping":
        return "clipping_only"
    if case.external_class == "harmonic":
        return "harmonic_only"
    if case.external_class == "combined":
        return "combined"
    return "unclassified"


def _validate_class_distributions(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    whole = Counter(_planned_class_bucket(case) for case in cases)
    final = Counter(
        _planned_class_bucket(case)
        for case in cases
        if case.split == "final_external_test"
    )
    for label, expected in PLANNED_CLASS_WHOLE.items():
        if whole.get(label, 0) != expected:
            issues.append(
                _issue(
                    "planned_class_distribution_mismatch",
                    f"whole study expected {expected} {label}, found {whole.get(label, 0)}",
                )
            )
    for label, expected in PLANNED_CLASS_FINAL.items():
        if final.get(label, 0) != expected:
            issues.append(
                _issue(
                    "planned_final_class_distribution_mismatch",
                    f"final split expected {expected} {label}, found {final.get(label, 0)}",
                )
            )
    if whole.get("unclassified", 0):
        issues.append(
            _issue(
                "unclassified_planned_class",
                f"{whole['unclassified']} cases do not map to a planned class bucket",
            )
        )
    return issues


def _validate_final_scoreable_slots(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    final_cases = [case for case in cases if case.split == "final_external_test"]
    issues: list[ExternalValidationIssue] = []
    if len(final_cases) != 28:
        issues.append(
            _issue(
                "final_slot_count_mismatch",
                f"expected 28 final slots, found {len(final_cases)}",
            )
        )
    scoreable = [
        case for case in final_cases if case.confidence in SCOREABLE_CONFIDENCES
    ]
    if len(scoreable) != 24:
        issues.append(
            _issue(
                "final_scoreable_count_mismatch",
                f"expected 24 scoreable final cases, found {len(scoreable)}",
            )
        )
    return issues


def _validate_review_references(
    cases: tuple[ExternalCase, ...],
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    for case in cases:
        if not case.review_ref.startswith("review_"):
            issues.append(
                _issue(
                    "missing_review_reference",
                    "final preflight requires a review reference for every case",
                    case_id=case.case_id,
                )
            )
    return issues


def _collect_coverage_values(
    cases: tuple[ExternalCase, ...],
    *,
    dimension: str,
    include_groups: frozenset[str],
    final_only: bool,
) -> tuple[set[str], bool]:
    documented: set[str] = set()
    saw_unavailable = False
    for case in cases:
        if final_only and case.split != "final_external_test":
            continue
        if case.source_group not in include_groups:
            continue
        metadata = case.capture_coverage
        if metadata is None:
            continue
        raw = getattr(metadata, dimension)
        if raw is None:
            continue
        if raw == _UNAVAILABLE:
            saw_unavailable = True
            continue
        documented.add(raw)
    return documented, saw_unavailable


def _dimension_report(
    cases: tuple[ExternalCase, ...],
    *,
    dimension: str,
    include_groups: frozenset[str],
    minimum: int,
    final_only: bool,
) -> CoverageDimensionReport:
    documented, unavailable = _collect_coverage_values(
        cases,
        dimension=dimension,
        include_groups=include_groups,
        final_only=final_only,
    )
    if unavailable and not documented:
        return CoverageDimensionReport(
            documented_values=(),
            unavailable=True,
            meets_target=False,
        )
    return CoverageDimensionReport(
        documented_values=tuple(sorted(documented)),
        unavailable=unavailable and not documented,
        meets_target=len(documented) >= minimum,
    )


def _build_coverage_report(
    cases: tuple[ExternalCase, ...],
    stage: ValidationStage,
) -> ExternalCoverageReport:
    final_only = stage == "final_preflight"
    minimums = _COVERAGE_MINIMUMS_FINAL if final_only else _COVERAGE_MINIMUMS_WHOLE
    a_groups = frozenset({"A"})
    ab_groups = frozenset({"A", "B"})
    return ExternalCoverageReport(
        loudspeaker=_dimension_report(
            cases,
            dimension="loudspeaker",
            include_groups=a_groups,
            minimum=minimums["loudspeaker"],
            final_only=final_only,
        ),
        microphone_position=_dimension_report(
            cases,
            dimension="microphone_position",
            include_groups=a_groups,
            minimum=minimums["microphone_position"],
            final_only=final_only,
        ),
        distance=_dimension_report(
            cases,
            dimension="distance",
            include_groups=a_groups,
            minimum=minimums["distance"],
            final_only=final_only,
        ),
        playback_level=_dimension_report(
            cases,
            dimension="playback_level",
            include_groups=a_groups,
            minimum=minimums["playback_level"],
            final_only=final_only,
        ),
        acoustic_environment=_dimension_report(
            cases,
            dimension="acoustic_environment",
            include_groups=a_groups,
            minimum=minimums["acoustic_environment"],
            final_only=final_only,
        ),
        f0_band=_dimension_report(
            cases,
            dimension="f0_band",
            include_groups=ab_groups,
            minimum=minimums["f0_band"],
            final_only=final_only,
        ),
    )


def _coverage_target_issues(
    coverage: ExternalCoverageReport,
) -> list[ExternalValidationIssue]:
    issues: list[ExternalValidationIssue] = []
    for name, dimension in coverage.model_dump().items():
        if not isinstance(dimension, dict):
            continue
        if dimension.get("meets_target"):
            continue
        if dimension.get("unavailable"):
            issues.append(
                _issue(
                    "coverage_dimension_unavailable",
                    f"coverage dimension {name} is unavailable",
                )
            )
        else:
            documented = dimension.get("documented_values", ())
            issues.append(
                _issue(
                    "coverage_dimension_insufficient",
                    (
                        f"coverage dimension {name} has "
                        f"{len(documented)} documented values"
                    ),
                )
            )
    return issues
