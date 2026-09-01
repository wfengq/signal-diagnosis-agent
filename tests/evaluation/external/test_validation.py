"""Checkpoint G — grouping, confidence, and validation (EV-T031–EV-T034)."""

from __future__ import annotations

import hashlib
import wave
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.evaluation.external.models import (
    CaptureCoverageMetadata,
    ExternalCase,
    ExternalDatasetManifest,
    ExternalValidationReport,
    TransformConfig,
)
from signal_diag.evaluation.external.validation import validate_external_manifest
from tests.evaluation.external.conftest import (
    make_external_case,
    make_external_manifest,
    make_transform,
)

_FROZEN_TRANSFORM = TransformConfig(
    kind="combined",
    tail_proportion=0.05,
    alpha=0.15,
    post_gain=0.8,
    input_sha256="a" * 64,
    output_sha256="a" * 64,
    parameters_identity="combined_q0.05_a0.15_pg0.8_lower",
)
_A_COVERAGE_VALUES = (
    ("spk_a", "mic_a", "dist_a", "level_a", "room_a", "100-300"),
    ("spk_b", "mic_b", "dist_b", "level_b", "room_b", "400-1000"),
    ("spk_c", "mic_c", "unavailable", "level_c", "room_c", "1200-3000"),
    ("spk_d", "mic_d", "dist_d", "level_d", "room_d", "100-300"),
    ("spk_e", "mic_e", "dist_e", "level_e", "room_e", "400-1000"),
    ("spk_f", "mic_f", "dist_f", "level_f", "room_f", "1200-3000"),
)


def issue_codes(report: ExternalValidationReport) -> set[str]:
    return {issue.code for issue in report.issues}


def write_pcm24_wav(path: Path, *, frames: int = 960, seed: int = 0) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frequency = 220.0 + (seed % 97)
    phase = (seed % 360) * np.pi / 180.0
    samples = np.sin(
        2.0 * np.pi * frequency * np.arange(frames, dtype=np.float64) / 48_000 + phase,
        dtype=np.float64,
    )
    pcm = np.clip(np.round(samples * (1 << 23)), -(1 << 23), (1 << 23) - 1).astype(
        np.int32,
    )
    payload = bytearray()
    for value in pcm:
        payload.extend(int(value).to_bytes(3, "little", signed=True))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(3)
        handle.setframerate(48_000)
        handle.writeframes(bytes(payload))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize_manifest_assets(
    manifest: ExternalDatasetManifest,
    asset_root: Path,
) -> ExternalDatasetManifest:
    updated_cases: list[ExternalCase] = []
    master_digests: dict[str, str] = {}
    for index, case in enumerate(manifest.cases):
        wav_path = asset_root / case.analysis_wav_path
        digest = write_pcm24_wav(wav_path, frames=case.wav_frames, seed=index + 1)
        updates: dict[str, Any] = {"wav_sha256": digest}
        if case.source_group == "B" and case.external_class == "clean":
            master_digests[case.parent_master_id or ""] = digest
        if case.transform is not None:
            input_digest = master_digests[case.parent_master_id or ""]
            updates["transform"] = case.transform.model_copy(
                update={
                    "input_sha256": input_digest,
                    "output_sha256": digest,
                },
            )
        updated_cases.append(case.model_copy(update=updates))
    return manifest.model_copy(update={"cases": tuple(updated_cases)})


@dataclass(frozen=True)
class _SplitPlan:
    split: str
    a_ref_clean: int
    a_ref_inconclusive: int
    a_weak: int
    b_masters: tuple[str, ...]
    c_ref_inconclusive: int
    c_unknown: int


_SPLIT_PLANS: tuple[_SplitPlan, ...] = (
    _SplitPlan("development", 1, 1, 1, ("master_dev_01", "master_dev_02"), 2, 1),
    _SplitPlan("validation", 1, 1, 1, ("master_val_01",), 2, 1),
    _SplitPlan(
        "final_external_test",
        2,
        2,
        2,
        ("master_final_01", "master_final_02", "master_final_03", "master_final_04"),
        4,
        2,
    ),
)


def _next_case_id(counter: list[int]) -> str:
    value = counter[0]
    counter[0] += 1
    return f"{value:016x}"


def _make_a_case(
    *,
    split: str,
    case_id: str,
    external_class: str,
    confidence: str,
    source_recording_key: str,
    capture_configuration_key: str,
    coverage: CaptureCoverageMetadata | None,
) -> ExternalCase:
    acceptable_outcomes: tuple[str, ...]
    causal_faults: tuple[str, ...] = ()
    if confidence in {"weak_observation", "unknown"}:
        acceptable_outcomes = ()
    elif external_class == "inconclusive":
        acceptable_outcomes = ("inconclusive",)
    else:
        acceptable_outcomes = ("no_supported_fault",)
    return make_external_case(
        case_id=case_id,
        split=split,  # type: ignore[arg-type]
        source_group="A",
        external_class=external_class,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        parent_master_id=None,
        transform=None,
        source_recording_key=source_recording_key,
        capture_configuration_key=capture_configuration_key,
        acceptable_outcomes=acceptable_outcomes,  # type: ignore[arg-type]
        causal_faults=causal_faults,  # type: ignore[arg-type]
        capture_coverage=coverage,
        provenance_ref=f"prov_{case_id}",
        review_ref=f"review_{case_id}",
        analysis_wav_path=f"assets/{split}/extwav_{split}_{case_id}.wav",
        wav_frames=960,
    )


def _make_b_variant(
    *,
    split: str,
    case_id: str,
    parent_master_id: str,
    external_class: str,
    source_recording_key: str,
    capture_configuration_key: str,
    f0_band: str,
) -> ExternalCase:
    causal_faults: tuple[str, ...]
    if external_class == "clean":
        confidence = "reference_supported"
        transform = None
        acceptable_outcomes = ("no_supported_fault",)
        causal_faults = ()
    else:
        confidence = "strong_ground_truth"
        if external_class == "clipping":
            transform = make_transform(
                kind="clipping",
                tail_proportion=0.05,
                alpha=None,
                post_gain=None,
                parameters_identity="clipping_q0.05_lower",
            )
        elif external_class == "harmonic":
            transform = make_transform(
                kind="second_harmonic",
                tail_proportion=None,
                alpha=0.15,
                post_gain=0.8,
                parameters_identity="harmonic_a0.15_pg0.8",
            )
        else:
            transform = _FROZEN_TRANSFORM
        acceptable_outcomes = ("supported_fault",)
        if external_class == "combined":
            causal_faults = ("clipping", "harmonic_distortion")
        elif external_class == "clipping":
            causal_faults = ("clipping",)
        else:
            causal_faults = ("harmonic_distortion",)
    return make_external_case(
        case_id=case_id,
        split=split,  # type: ignore[arg-type]
        source_group="B",
        external_class=external_class,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        parent_master_id=parent_master_id,
        transform=transform,
        source_recording_key=source_recording_key,
        capture_configuration_key=capture_configuration_key,
        acceptable_outcomes=acceptable_outcomes,  # type: ignore[arg-type]
        causal_faults=causal_faults,  # type: ignore[arg-type]
        capture_coverage=CaptureCoverageMetadata(f0_band=f0_band),
        provenance_ref=f"prov_{case_id}",
        review_ref=f"review_{case_id}",
        analysis_wav_path=f"assets/{split}/extwav_{split}_{case_id}.wav",
        wav_frames=960,
    )


def _make_c_case(
    *,
    split: str,
    case_id: str,
    external_class: str,
    confidence: str,
    source_recording_key: str,
) -> ExternalCase:
    acceptable_outcomes = () if confidence == "unknown" else ("inconclusive",)
    return make_external_case(
        case_id=case_id,
        split=split,  # type: ignore[arg-type]
        source_group="C",
        external_class=external_class,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        parent_master_id=None,
        transform=None,
        source_recording_key=source_recording_key,
        capture_configuration_key=f"cap_{source_recording_key}",
        acceptable_outcomes=acceptable_outcomes,  # type: ignore[arg-type]
        causal_faults=(),
        provenance_ref=f"prov_{case_id}",
        review_ref=f"review_{case_id}",
        analysis_wav_path=f"assets/{split}/extwav_{split}_{case_id}.wav",
        wav_frames=960,
    )


def build_valid_manifest() -> ExternalDatasetManifest:
    counter = [1]
    cases: list[ExternalCase] = []
    a_index = 0
    esc_index = 0
    nsynth_index = 0
    f0_bands = (
        "100-300",
        "400-1000",
        "1200-3000",
        "100-300",
        "400-1000",
        "1200-3000",
        "100-300",
    )

    for plan in _SPLIT_PLANS:
        for _ in range(plan.a_ref_clean):
            coverage_tuple = _A_COVERAGE_VALUES[a_index % len(_A_COVERAGE_VALUES)]
            a_index += 1
            case_id = _next_case_id(counter)
            cases.append(
                _make_a_case(
                    split=plan.split,
                    case_id=case_id,
                    external_class="clean",
                    confidence="reference_supported",
                    source_recording_key=f"smard_rec_{plan.split}_{a_index}",
                    capture_configuration_key=f"smard_cfg_{plan.split}_{a_index}",
                    coverage=CaptureCoverageMetadata(
                        loudspeaker=coverage_tuple[0],
                        microphone_position=coverage_tuple[1],
                        distance=coverage_tuple[2],
                        playback_level=coverage_tuple[3],
                        acoustic_environment=coverage_tuple[4],
                        f0_band=coverage_tuple[5],
                    ),
                )
            )
        for idx in range(plan.a_ref_inconclusive):
            case_id = _next_case_id(counter)
            cases.append(
                _make_a_case(
                    split=plan.split,
                    case_id=case_id,
                    external_class="inconclusive",
                    confidence="reference_supported",
                    source_recording_key=f"smard_rec_{plan.split}_inc_{idx}",
                    capture_configuration_key=f"smard_cfg_{plan.split}_inc_{idx}",
                    coverage=CaptureCoverageMetadata(
                        loudspeaker=f"spk_inc_{plan.split}_{idx}",
                        microphone_position=f"mic_inc_{plan.split}_{idx}",
                        distance=f"dist_inc_{plan.split}_{idx}",
                        playback_level=f"level_inc_{plan.split}_{idx}",
                        acoustic_environment=f"room_inc_{plan.split}_{idx}",
                        f0_band="400-1000",
                    ),
                )
            )
        for idx in range(plan.a_weak):
            case_id = _next_case_id(counter)
            cases.append(
                _make_a_case(
                    split=plan.split,
                    case_id=case_id,
                    external_class="ambiguous",
                    confidence="weak_observation",
                    source_recording_key=f"smard_rec_{plan.split}_weak_{idx}",
                    capture_configuration_key=f"smard_cfg_{plan.split}_weak_{idx}",
                    coverage=None,
                )
            )

        for master_idx, parent_id in enumerate(plan.b_masters):
            source_key = f"b_src_{parent_id}"
            capture_key = f"b_cap_{parent_id}"
            f0_band = f0_bands[master_idx % len(f0_bands)]
            for external_class in ("clean", "clipping", "harmonic", "combined"):
                case_id = _next_case_id(counter)
                cases.append(
                    _make_b_variant(
                        split=plan.split,
                        case_id=case_id,
                        parent_master_id=parent_id,
                        external_class=external_class,
                        source_recording_key=source_key,
                        capture_configuration_key=capture_key,
                        f0_band=f0_band,
                    )
                )

        for idx in range(plan.c_ref_inconclusive):
            if idx % 2 == 0:
                esc_index += 1
                source_key = f"esc_src_file:esc_{plan.split}_{esc_index}"
            else:
                nsynth_index += 1
                source_key = f"nsynth_instrument:guitar_{nsynth_index}"
            case_id = _next_case_id(counter)
            cases.append(
                _make_c_case(
                    split=plan.split,
                    case_id=case_id,
                    external_class="inconclusive",
                    confidence="reference_supported",
                    source_recording_key=source_key,
                )
            )
        for idx in range(plan.c_unknown):
            case_id = _next_case_id(counter)
            cases.append(
                _make_c_case(
                    split=plan.split,
                    case_id=case_id,
                    external_class="ambiguous",
                    confidence="unknown",
                    source_recording_key=f"pyramic_rec_{plan.split}_unk_{idx}",
                )
            )

    return make_external_manifest(cases=tuple(cases))


def move_one_variant_to_validation(
    manifest: ExternalDatasetManifest,
) -> ExternalDatasetManifest:
    updated: list[ExternalCase] = []
    moved = False
    for case in manifest.cases:
        if (
            not moved
            and case.source_group == "B"
            and case.split == "development"
            and case.external_class == "clipping"
        ):
            case_id = case.case_id
            updated.append(
                case.model_copy(
                    update={
                        "split": "validation",
                        "analysis_wav_path": (
                            f"assets/validation/extwav_validation_{case_id}.wav"
                        ),
                    }
                )
            )
            moved = True
        else:
            updated.append(case)
    assert moved
    return manifest.model_copy(update={"cases": tuple(updated)})


@pytest.fixture
def valid_manifest(tmp_path: Path) -> ExternalDatasetManifest:
    manifest = build_valid_manifest()
    return materialize_manifest_assets(manifest, tmp_path / "assets_root")


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    return tmp_path / "assets_root"


def test_ev_t031_planned_split_and_group_counts_at_final_preflight(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid, report.issues
    assert len(valid_manifest.cases) == 52
    assert Counter(case.split for case in valid_manifest.cases) == {
        "development": 14,
        "validation": 10,
        "final_external_test": 28,
    }
    assert Counter(case.source_group for case in valid_manifest.cases) == {
        "A": 12,
        "B": 28,
        "C": 12,
    }


def test_ev_t032_seven_complete_b_families_with_four_variants(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    families: dict[str, set[str]] = {}
    for case in valid_manifest.cases:
        if case.source_group == "B":
            families.setdefault(case.parent_master_id or "", set()).add(
                case.external_class,
            )
    assert len(families) == 7
    assert all(
        classes == {"clean", "clipping", "harmonic", "combined"}
        for classes in families.values()
    )


def test_ev_t033_parent_family_cannot_cross_splits(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    leaked = move_one_variant_to_validation(valid_manifest)
    materialize_manifest_assets(leaked, fixture_root)
    report = validate_external_manifest(leaked, fixture_root, stage="validation")
    assert "parent_master_split_leakage" in issue_codes(report)
    assert not report.valid


def test_ev_t034_confidence_distributions_at_final_preflight(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    whole = Counter(case.confidence for case in valid_manifest.cases)
    final = Counter(
        case.confidence
        for case in valid_manifest.cases
        if case.split == "final_external_test"
    )
    assert whole == {
        "strong_ground_truth": 21,
        "reference_supported": 23,
        "weak_observation": 4,
        "unknown": 4,
    }
    assert final == {
        "strong_ground_truth": 12,
        "reference_supported": 12,
        "weak_observation": 2,
        "unknown": 2,
    }


def test_planned_class_distributions_from_spec(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid


def test_digest_and_group_key_non_overlap(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    assert "digest_split_leakage" not in issue_codes(report)
    assert "group_key_split_leakage" not in issue_codes(report)


def test_source_record_esc_and_nsynth_configuration_isolation(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    assert "esc_src_file_split_leakage" not in issue_codes(report)
    assert "nsynth_instrument_split_leakage" not in issue_codes(report)


def test_validation_stage_requires_14_plus_10_cases_and_frozen_transform(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    dev_val_cases = tuple(
        case
        for case in valid_manifest.cases
        if case.split in {"development", "validation"}
    )
    manifest = valid_manifest.model_copy(update={"cases": dev_val_cases})
    report = validate_external_manifest(manifest, fixture_root, stage="validation")
    assert report.valid


def test_development_stage_allows_incomplete_counts(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    dev_cases = tuple(
        case for case in valid_manifest.cases if case.split == "development"
    )
    manifest = valid_manifest.model_copy(update={"cases": dev_cases})
    report = validate_external_manifest(manifest, fixture_root, stage="development")
    assert report.valid


def test_wav_digest_format_and_loader_acceptance(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    assert "wav_digest_mismatch" not in issue_codes(report)
    assert "wav_loader_rejected" not in issue_codes(report)
    assert "wav_format_mismatch" not in issue_codes(report)


def test_truth_free_filename_and_identifiers(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    assert "truth_leaking_filename" not in issue_codes(report)
    assert "truth_leaking_identifier" not in issue_codes(report)


def test_strong_and_reference_only_correctness_mask(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    for case in valid_manifest.cases:
        if case.confidence in {"weak_observation", "unknown"}:
            assert not case.acceptable_outcomes
            assert not case.causal_faults
        elif case.confidence in {"strong_ground_truth", "reference_supported"}:
            assert case.acceptable_outcomes or case.causal_faults


def test_a_overload_never_promoted_to_strong_truth(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    assert "a_overload_promoted_to_strong" not in issue_codes(report)
    assert all(
        case.confidence != "strong_ground_truth"
        for case in valid_manifest.cases
        if case.source_group == "A"
    )


def test_global_transform_config_mismatch_is_reported(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    mismatched_cases: list[ExternalCase] = []
    changed = False
    for case in valid_manifest.cases:
        if (
            not changed
            and case.source_group == "B"
            and case.external_class == "clipping"
            and case.transform is not None
        ):
            mismatched_cases.append(
                case.model_copy(
                    update={
                        "transform": case.transform.model_copy(
                            update={"tail_proportion": 0.10},
                        ),
                    },
                )
            )
            changed = True
        else:
            mismatched_cases.append(case)
    manifest = valid_manifest.model_copy(update={"cases": tuple(mismatched_cases)})
    report = validate_external_manifest(manifest, fixture_root, stage="validation")
    assert "global_transform_config_mismatch" in issue_codes(report)


def test_final_preflight_requires_24_scoreable_final_cases(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.valid
    final_scoreable = [
        case
        for case in valid_manifest.cases
        if case.split == "final_external_test"
        and case.confidence in {"strong_ground_truth", "reference_supported"}
    ]
    assert len(final_scoreable) == 24


def test_coverage_reporting_marks_unavailable_without_inference(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    report = validate_external_manifest(
        valid_manifest,
        fixture_root,
        stage="final_preflight",
    )
    assert report.coverage is not None
    assert report.coverage.distance.documented_values
    assert "unavailable" not in report.coverage.distance.documented_values


def test_missing_b_variant_fails_family_validation(
    valid_manifest: ExternalDatasetManifest,
    fixture_root: Path,
) -> None:
    trimmed = tuple(
        case
        for case in valid_manifest.cases
        if not (
            case.parent_master_id == "master_dev_01"
            and case.external_class == "combined"
        )
    )
    manifest = valid_manifest.model_copy(update={"cases": trimmed})
    report = validate_external_manifest(manifest, fixture_root, stage="development")
    assert "incomplete_b_family" in issue_codes(report)
