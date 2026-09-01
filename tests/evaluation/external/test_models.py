"""Checkpoint B — external study models (EV-T005–EV-T008)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import nan

import pytest
from pydantic import ValidationError

from signal_diag.evaluation.external.models import (
    AcquiredAsset,
    TransformConfig,
)
from tests.evaluation.external.conftest import (
    make_external_case,
    make_external_manifest,
    make_transform,
)


def test_ev_t005_external_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        make_external_case(unexpected_field=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        make_external_manifest(schema_version="2.0")


def test_ev_t005_acquired_asset_requires_utc_timestamp() -> None:
    naive = datetime(2026, 9, 1, 9, 0)  # noqa: DTZ001
    with pytest.raises(
        ValidationError, match="acquired_at_utc must be timezone-aware UTC"
    ):
        AcquiredAsset(
            asset_id="asset_01",
            source_url="https://example.com/sample.wav",
            sha256="a" * 64,
            byte_count=1024,
            acquired_at_utc=naive,
        )
    offset = datetime(2026, 9, 1, 9, 0, tzinfo=timezone(timedelta(hours=8)))
    with pytest.raises(
        ValidationError, match="acquired_at_utc must be timezone-aware UTC"
    ):
        AcquiredAsset(
            asset_id="asset_01",
            source_url="https://example.com/sample.wav",
            sha256="a" * 64,
            byte_count=1024,
            acquired_at_utc=offset,
        )


def test_ev_t005_wav_sha256_must_be_lowercase_hex() -> None:
    with pytest.raises(ValidationError):
        make_external_case(wav_sha256="G" * 64)
    with pytest.raises(ValidationError):
        make_external_case(wav_sha256="abc")


def test_ev_t006_weak_case_cannot_expose_correctness_truth() -> None:
    with pytest.raises(ValueError, match="weak/unknown cases forbid scoring truth"):
        make_external_case(
            confidence="weak_observation",
            acceptable_outcomes=("supported_fault",),
            causal_faults=("clipping",),
        )
    with pytest.raises(ValueError, match="weak/unknown cases forbid scoring truth"):
        make_external_case(
            confidence="unknown",
            acceptable_outcomes=("inconclusive",),
            causal_faults=(),
        )


def test_ev_t007_strong_case_requires_transform_provenance() -> None:
    with pytest.raises(ValueError, match="strong ground truth requires transform"):
        make_external_case(confidence="strong_ground_truth", transform=None)


def test_ev_t007_only_b_degraded_cases_may_be_strong() -> None:
    with pytest.raises(
        ValueError, match="only B degraded cases may be strong_ground_truth"
    ):
        make_external_case(
            source_group="A",
            external_class="clipping",
            confidence="strong_ground_truth",
            parent_master_id=None,
            transform=make_transform(),
        )
    with pytest.raises(
        ValueError, match="only B degraded cases may be strong_ground_truth"
    ):
        make_external_case(
            source_group="B",
            external_class="clean",
            confidence="strong_ground_truth",
            parent_master_id="master_dev_01",
            transform=make_transform(kind="none", parameters_identity="none"),
        )


def test_ev_t008_truth_free_analysis_filename_and_split_match() -> None:
    case = make_external_case(
        split="validation",
        case_id="fedcba9876543210",
        analysis_wav_path="assets/validation/extwav_validation_fedcba9876543210.wav",
    )
    assert case.analysis_wav_path.endswith("extwav_validation_fedcba9876543210.wav")

    with pytest.raises(ValueError, match="analysis filename"):
        make_external_case(
            analysis_wav_path="assets/development/extwav_validation_0123456789abcdef.wav"
        )
    with pytest.raises(ValueError, match="analysis filename"):
        make_external_case(
            analysis_wav_path="assets/development/wrong_name.wav",
        )
    with pytest.raises(ValueError, match="relative path"):
        make_external_case(
            analysis_wav_path="../../extwav_development_0123456789abcdef.wav",
        )
    with pytest.raises(ValueError, match="relative path"):
        make_external_case(
            analysis_wav_path="C:/tmp/extwav_development_0123456789abcdef.wav",
        )


@pytest.mark.parametrize(
    ("external_class", "kind"),
    (
        ("clipping", "second_harmonic"),
        ("harmonic", "clipping"),
        ("combined", "clipping"),
    ),
)
def test_strong_b_transform_kind_must_match_class(
    external_class: str,
    kind: str,
) -> None:
    with pytest.raises(ValueError, match="transform kind must match external_class"):
        make_external_case(
            external_class=external_class,
            transform=make_transform(kind=kind),
        )


def test_strong_b_transform_output_must_match_case_wav() -> None:
    with pytest.raises(
        ValueError, match="transform output_sha256 must match wav_sha256"
    ):
        make_external_case(transform=make_transform(output_sha256="d" * 64))


def test_ev_t008_b_cases_require_parent_and_non_b_forbid_transform() -> None:
    with pytest.raises(ValueError, match="B cases require parent_master_id"):
        make_external_case(
            source_group="B",
            confidence="reference_supported",
            external_class="clean",
            parent_master_id=None,
            transform=None,
            acceptable_outcomes=("no_supported_fault",),
            causal_faults=(),
        )
    with pytest.raises(
        ValueError, match="non-B cases must not declare transform provenance"
    ):
        make_external_case(
            source_group="A",
            external_class="inconclusive",
            confidence="reference_supported",
            parent_master_id=None,
            transform=make_transform(),
            acceptable_outcomes=("inconclusive",),
            causal_faults=(),
        )


def test_ev_t008_combined_causal_order_is_canonical() -> None:
    case = make_external_case(
        external_class="combined",
        causal_faults=("clipping", "harmonic_distortion"),
        transform=make_transform(kind="combined", parameters_identity="combined_v1"),
    )
    assert case.causal_faults == ("clipping", "harmonic_distortion")
    with pytest.raises(ValueError, match="combined causal faults must be"):
        make_external_case(
            external_class="combined",
            causal_faults=("harmonic_distortion", "clipping"),
            transform=make_transform(
                kind="combined", parameters_identity="combined_v1"
            ),
        )


def test_reference_supported_case_requires_score_truth() -> None:
    with pytest.raises(
        ValueError, match="strong/reference cases require scoring truth"
    ):
        make_external_case(
            confidence="reference_supported",
            acceptable_outcomes=(),
            causal_faults=(),
        )


def test_external_case_is_immutable() -> None:
    case = make_external_case()
    with pytest.raises(ValidationError):
        case.case_id = "mutated"  # type: ignore[misc]


def test_transform_config_rejects_nan_parameters() -> None:
    with pytest.raises(ValidationError):
        TransformConfig(
            kind="clipping",
            tail_proportion=nan,
            input_sha256="a" * 64,
            output_sha256="b" * 64,
            parameters_identity="clipping_q0.05_lower",
        )
