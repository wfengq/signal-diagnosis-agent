"""T-CX124–T-CX128: contextual manifest validation."""

from __future__ import annotations

from collections import Counter

import pytest

from signal_diag.evaluation.contextual.manifest import (
    build_slot_plan,
    validate_contextual_manifest,
)
from signal_diag.evaluation.contextual.models import ContextualManifest


def test_t_cx124_validation_distribution_is_exact(
    validation_manifest: ContextualManifest,
) -> None:
    assert len(validation_manifest.cases) == 20
    assert sum(case.scoreable for case in validation_manifest.cases) == 17
    assert Counter(case.mode for case in validation_manifest.cases) == {
        "paired_reference": 10,
        "nominal_single_tone": 4,
        "single_signal": 6,
    }
    validate_contextual_manifest(validation_manifest)


def test_t_cx125_rejects_development_marker_in_validation(
    validation_manifest: ContextualManifest,
) -> None:
    leaked = validation_manifest.cases[0].model_copy(
        update={"parent_master_id": "dev_master_x"}
    )
    bad = validation_manifest.model_copy(
        update={"cases": (leaked, *validation_manifest.cases[1:])}
    )
    with pytest.raises(ValueError, match="leakage"):
        validate_contextual_manifest(bad)


def test_t_cx126_rejects_wrong_scoreable_count(
    validation_manifest: ContextualManifest,
) -> None:
    flipped = validation_manifest.cases[-1].model_copy(
        update={"scoreable": True, "confidence_tier": "reference_supported"}
    )
    bad = validation_manifest.model_copy(
        update={"cases": (*validation_manifest.cases[:-1], flipped)}
    )
    with pytest.raises(ValueError, match="17 scoreable"):
        validate_contextual_manifest(bad)


def test_t_cx127_slot_plan_uses_paired_harmonic_roles(
    validation_manifest: ContextualManifest,
) -> None:
    slots = build_slot_plan(validation_manifest)
    assert len(slots) == 4
    assert {slot.case_id for slot in slots} == {
        "val_p_harm_1",
        "val_p_harm_2",
        "val_p_comb_1",
        "val_p_comb_2",
    }


def test_t_cx128_manifest_sha_is_stable(
    validation_manifest: ContextualManifest,
) -> None:
    from signal_diag.evaluation.contextual.manifest import manifest_sha256

    first = manifest_sha256(validation_manifest)
    second = manifest_sha256(validation_manifest)
    assert first == second
    assert len(first) == 64
