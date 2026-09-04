"""T-CX121–T-CX123: contextual evaluation models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from signal_diag.evaluation.contextual.manifest import make_arm_plans, make_case
from signal_diag.evaluation.contextual.models import CONTEXTUAL_SCORING_ID


def test_t_cx121_case_requires_three_distinct_arms() -> None:
    test_sha = "a" * 64
    with pytest.raises(ValidationError):
        make_case(
            case_id="bad",
            split="validation",
            mode="single_signal",
            role="clean",
            expected_outcome="no_supported_fault",
            confidence_tier="reference_supported",
            scoreable=True,
            source_id="src",
            license_id="CC0",
            parent_master_id="m",
            recording_key="r",
            transform_identity="t",
            test_wav_sha256=test_sha,
            arms=make_arm_plans(mode="single_signal", test_sha=test_sha, reference_sha=None)[
                :2
            ],
        )


def test_t_cx122_ablation_arm_must_be_single_signal() -> None:
    test_sha = "b" * 64
    arms = list(
        make_arm_plans(mode="paired_reference", test_sha=test_sha, reference_sha="c" * 64)
    )
    arms[2] = arms[2].model_copy(update={"mode": "paired_reference"})
    with pytest.raises(ValidationError):
        make_case(
            case_id="bad_ablation",
            split="validation",
            mode="paired_reference",
            role="clean",
            expected_outcome="no_supported_fault",
            confidence_tier="reference_supported",
            scoreable=True,
            source_id="src",
            license_id="CC0",
            parent_master_id="m",
            recording_key="r",
            transform_identity="t",
            test_wav_sha256=test_sha,
            reference_wav_sha256="c" * 64,
            arms=tuple(arms),
        )


def test_t_cx123_scoring_identity_constant() -> None:
    assert CONTEXTUAL_SCORING_ID == "signal_diag.contextual_scoring"
