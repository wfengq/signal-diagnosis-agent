"""Shared builders for external WAV validity study model tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from signal_diag.evaluation.external.models import (
    ExternalCase,
    ExternalDatasetManifest,
    TransformConfig,
)
from signal_diag.evaluation.models import (
    EvidenceCondition,
    SufficientEvidenceSet,
)
from signal_diag.tools.contracts import ToolName

_DEFAULT_CASE_ID = "0123456789abcdef"
_DEFAULT_WAV_SHA256 = "a" * 64
_DEFAULT_INPUT_SHA256 = _DEFAULT_WAV_SHA256
_DEFAULT_OUTPUT_SHA256 = _DEFAULT_WAV_SHA256


def make_condition(
    *,
    condition_id: str = "cond_primary",
    tool_name: ToolName = "detect_clipping",
    metric: str = "clipping_ratio",
    validity: str = "valid",
    comparator: str = "gt",
    expected_value: object = 0.01,
    unit: str | None = None,
    supports_claims: tuple[str, ...] = ("clipping",),
) -> EvidenceCondition:
    return EvidenceCondition(
        condition_id=condition_id,
        tool_name=tool_name,
        metric=metric,
        validity=validity,  # type: ignore[arg-type]
        comparator=comparator,  # type: ignore[arg-type]
        expected_value=expected_value,  # type: ignore[arg-type]
        unit=unit,
        supports_claims=supports_claims,  # type: ignore[arg-type]
    )


def make_sufficient_set(
    *,
    evidence_set_id: str = "evset_primary",
    condition_refs: tuple[str, ...] = ("cond_primary",),
    supported_claims: tuple[str, ...] = ("clipping",),
    acceptable_outcomes: tuple[str, ...] = ("supported_fault",),
) -> SufficientEvidenceSet:
    return SufficientEvidenceSet(
        evidence_set_id=evidence_set_id,
        condition_refs=condition_refs,
        supported_claims=supported_claims,  # type: ignore[arg-type]
        acceptable_outcomes=acceptable_outcomes,  # type: ignore[arg-type]
    )


def make_transform(
    *,
    kind: str = "clipping",
    tail_proportion: float | None = 0.05,
    alpha: float | None = None,
    post_gain: float | None = None,
    input_sha256: str = _DEFAULT_INPUT_SHA256,
    output_sha256: str = _DEFAULT_OUTPUT_SHA256,
    parameters_identity: str = "clipping_q0.05_lower",
) -> TransformConfig:
    return TransformConfig(
        kind=kind,  # type: ignore[arg-type]
        tail_proportion=tail_proportion,
        alpha=alpha,
        post_gain=post_gain,
        input_sha256=input_sha256,
        output_sha256=output_sha256,
        parameters_identity=parameters_identity,
    )


def make_external_case(**overrides: Any) -> ExternalCase:
    split = overrides.pop("split", "development")
    case_id = overrides.pop("case_id", _DEFAULT_CASE_ID)
    source_group = overrides.pop("source_group", "B")
    external_class = overrides.pop("external_class", "clipping")
    confidence = overrides.pop("confidence", "strong_ground_truth")
    parent_master_id = overrides.pop(
        "parent_master_id",
        "master_dev_01" if source_group == "B" else None,
    )
    default_causal_faults: tuple[str, ...]
    if external_class == "combined":
        default_causal_faults = ("clipping", "harmonic_distortion")
    elif confidence == "strong_ground_truth":
        default_causal_faults = ("clipping",)
    else:
        default_causal_faults = ()
    causal_faults = overrides.pop("causal_faults", default_causal_faults)
    if external_class == "combined":
        default_transform = make_transform(
            kind="combined",
            parameters_identity="combined_v1",
        )
    elif confidence == "strong_ground_truth":
        default_transform = make_transform()
    else:
        default_transform = None
    transform = overrides.pop("transform", default_transform)
    acceptable_outcomes = overrides.pop(
        "acceptable_outcomes",
        ("supported_fault",)
        if confidence in {"strong_ground_truth", "reference_supported"}
        else (),
    )
    payload: dict[str, Any] = {
        "case_id": case_id,
        "split": split,
        "source_group": source_group,
        "external_class": external_class,
        "analysis_wav_path": f"assets/{split}/extwav_{split}_{case_id}.wav",
        "wav_sha256": _DEFAULT_WAV_SHA256,
        "wav_sample_rate_hz": 48_000,
        "wav_sample_width_bytes": 3,
        "wav_channels": 1,
        "wav_frames": 96_000,
        "provenance_ref": f"prov_{case_id}",
        "source_recording_key": "src_rec_01",
        "capture_configuration_key": "cap_cfg_01",
        "parent_master_id": parent_master_id,
        "transform": transform,
        "confidence": confidence,
        "review_ref": f"review_{case_id}",
        "observable_conditions": (make_condition(),),
        "sufficient_evidence_sets": (
            make_sufficient_set(
                supported_claims=causal_faults or ("inconclusive",),
                acceptable_outcomes=acceptable_outcomes or ("inconclusive",),
            ),
        ),
        "knowledge_policy": "optional",
        "knowledge_tags": ("clipping",) if causal_faults else (),
        "acceptable_first_tools": ("detect_clipping",),
        "acceptable_outcomes": acceptable_outcomes,
        "causal_faults": causal_faults,
        "requires_limitation": False,
    }
    payload.update(overrides)
    return ExternalCase(**payload)


def make_external_manifest(
    cases: tuple[ExternalCase, ...] | None = None,
    **overrides: Any,
) -> ExternalDatasetManifest:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "dataset_id": "s1-distortion-external-wav",
        "version": "1.0.0",
        "study_id": "v0.2-external-wav-validity-1",
        "rule_profile_id": "profile_s1_distortion",
        "rule_profile_version": "1.0.0-demo",
        "external_scoring_id": "signal_diag.external_scoring",
        "external_scoring_version": "1.0.0",
        "cases": cases if cases is not None else (make_external_case(),),
    }
    payload.update(overrides)
    return ExternalDatasetManifest(**payload)


@pytest.fixture
def utc_now() -> datetime:
    return datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def external_case() -> ExternalCase:
    return make_external_case()


@pytest.fixture
def external_manifest() -> ExternalDatasetManifest:
    return make_external_manifest()
