"""Shared builders for Phase 4 evaluation model tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from signal_diag.evaluation.dataset import load_dataset_manifest
from signal_diag.evaluation.models import (
    BenchmarkConfig,
    ClippedSineSignalSpec,
    CombinedDistortionSignalSpec,
    CombinedIdentifiabilitySpec,
    DatasetManifest,
    EvaluationCase,
    EvidenceCondition,
    HarmonicRatioSpec,
    HarmonicSineSignalSpec,
    SineSignalSpec,
    SufficientEvidenceSet,
    WhiteNoiseSignalSpec,
)

CANONICAL_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "signal_diag"
    / "evaluation"
    / "manifests"
    / "s1_distortion_v1.yaml"
)
PHASE4_1_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "signal_diag"
    / "evaluation"
    / "manifests"
    / "s1_distortion_v1_1.yaml"
)

_CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "clean": {
        "signal": SineSignalSpec(frequency_hz=200.0),
        "causal_faults": (),
        "acceptable_outcomes": ("no_supported_fault",),
        "knowledge_policy": "not_needed",
        "knowledge_tags": (),
        "requires_limitation": False,
        "identifiability": None,
        "supports_claims": ("no_supported_fault",),
        "set_claims": ("no_supported_fault",),
        "set_outcomes": ("no_supported_fault",),
    },
    "clipping": {
        "signal": ClippedSineSignalSpec(frequency_hz=200.0, clip_level=0.5),
        "causal_faults": ("clipping",),
        "acceptable_outcomes": ("supported_fault",),
        "knowledge_policy": "optional",
        "knowledge_tags": ("clipping",),
        "requires_limitation": False,
        "identifiability": None,
        "supports_claims": ("clipping",),
        "set_claims": ("clipping",),
        "set_outcomes": ("supported_fault",),
    },
    "harmonic": {
        "signal": HarmonicSineSignalSpec(
            fundamental_hz=200.0,
            harmonic_ratios=(HarmonicRatioSpec(order=2, ratio=0.1),),
        ),
        "causal_faults": ("harmonic_distortion",),
        "acceptable_outcomes": ("supported_fault",),
        "knowledge_policy": "optional",
        "knowledge_tags": ("harmonic_distortion",),
        "requires_limitation": False,
        "identifiability": None,
        "supports_claims": ("harmonic_distortion",),
        "set_claims": ("harmonic_distortion",),
        "set_outcomes": ("supported_fault",),
    },
    "combined": {
        "signal": CombinedDistortionSignalSpec(
            fundamental_hz=200.0,
            harmonic_ratios=(HarmonicRatioSpec(order=2, ratio=0.1),),
            clip_level=0.5,
        ),
        "causal_faults": ("clipping", "harmonic_distortion"),
        "acceptable_outcomes": ("supported_fault",),
        "knowledge_policy": "optional",
        "knowledge_tags": ("clipping", "harmonic_distortion"),
        "requires_limitation": False,
        "identifiability": CombinedIdentifiabilitySpec(
            signature_metric="harmonic_order_2_relative_amplitude",
            minimum_absolute_separation=0.05,
        ),
        "supports_claims": ("clipping", "harmonic_distortion"),
        "set_claims": ("clipping", "harmonic_distortion"),
        "set_outcomes": ("supported_fault",),
    },
    "invalid_noise": {
        "signal": WhiteNoiseSignalSpec(),
        "causal_faults": (),
        "acceptable_outcomes": ("inconclusive",),
        "knowledge_policy": "required",
        "knowledge_tags": ("invalid-signal",),
        "requires_limitation": True,
        "identifiability": None,
        "supports_claims": ("inconclusive",),
        "set_claims": ("inconclusive",),
        "set_outcomes": ("inconclusive",),
    },
}


def make_condition(
    *,
    condition_id: str = "cond_primary",
    tool_name: str = "detect_clipping",
    metric: str = "clipping_ratio",
    validity: str = "valid",
    comparator: str = "lte",
    expected_value: object = 0.01,
    unit: str | None = None,
    supports_claims: tuple[str, ...] = ("no_supported_fault",),
) -> EvidenceCondition:
    return EvidenceCondition(
        condition_id=condition_id,
        tool_name=tool_name,  # type: ignore[arg-type]
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
    supported_claims: tuple[str, ...] = ("no_supported_fault",),
    acceptable_outcomes: tuple[str, ...] = ("no_supported_fault",),
) -> SufficientEvidenceSet:
    return SufficientEvidenceSet(
        evidence_set_id=evidence_set_id,
        condition_refs=condition_refs,
        supported_claims=supported_claims,  # type: ignore[arg-type]
        acceptable_outcomes=acceptable_outcomes,  # type: ignore[arg-type]
    )


def make_evaluation_case(
    category: str = "clean",
    **overrides: Any,
) -> EvaluationCase:
    defaults = _CATEGORY_DEFAULTS[category]
    case_id = overrides.pop("case_id", f"case_{category}_dev_01")
    condition = overrides.pop(
        "observable_conditions",
        (
            make_condition(
                supports_claims=defaults["supports_claims"],
            ),
        ),
    )
    sufficient = overrides.pop(
        "sufficient_evidence_sets",
        (
            make_sufficient_set(
                supported_claims=defaults["set_claims"],
                acceptable_outcomes=defaults["set_outcomes"],
            ),
        ),
    )
    payload: dict[str, Any] = {
        "case_id": case_id,
        "split": "development",
        "category": category,
        "user_request": "Diagnose this signal.",
        "signal": defaults["signal"],
        "causal_faults": defaults["causal_faults"],
        "observable_conditions": condition,
        "acceptable_first_tools": ("detect_clipping",),
        "sufficient_evidence_sets": sufficient,
        "knowledge_policy": defaults["knowledge_policy"],
        "knowledge_tags": defaults["knowledge_tags"],
        "acceptable_outcomes": defaults["acceptable_outcomes"],
        "requires_limitation": defaults["requires_limitation"],
        "tags": (),
        "identifiability": defaults["identifiability"],
    }
    payload.update(overrides)
    return EvaluationCase(**payload)


def make_dataset_manifest(
    cases: tuple[EvaluationCase, ...] | None = None,
    **overrides: Any,
) -> DatasetManifest:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "dataset_id": "s1-distortion-synthetic",
        "version": "1.0.0",
        "rule_profile_id": "profile_s1_distortion",
        "rule_profile_version": "1.0.0-demo",
        "cases": cases if cases is not None else (make_evaluation_case(),),
    }
    payload.update(overrides)
    return DatasetManifest(**payload)


@pytest.fixture
def utc_now() -> datetime:
    return datetime(2026, 8, 29, 7, 0, tzinfo=UTC)


@pytest.fixture
def evaluation_case() -> EvaluationCase:
    return make_evaluation_case("clean")


@pytest.fixture
def dataset_manifest() -> DatasetManifest:
    return make_dataset_manifest()


@pytest.fixture(scope="module")
def official_manifest() -> DatasetManifest:
    return load_dataset_manifest(CANONICAL_MANIFEST)


@pytest.fixture
def deterministic_config(utc_now: datetime) -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id="bench_task8_deterministic",
        dataset_id="s1-distortion-synthetic",
        dataset_version="1.0.0",
        rule_profile_id="profile_s1_distortion",
        rule_profile_version="1.0.0-demo",
        started_at_utc=utc_now,
    )
