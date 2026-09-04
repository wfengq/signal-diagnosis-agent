"""Shared fixtures for contextual evaluation harness tests."""

from __future__ import annotations

from hashlib import sha256

import pytest

from signal_diag.evaluation.contextual.manifest import (
    build_slot_plan,
    make_arm_plans,
    make_case,
)
from signal_diag.evaluation.contextual.models import (
    CONTEXTUAL_SCORING_VERSION,
    ContextualManifest,
)


def _sha(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _case(
    *,
    case_id: str,
    mode: str,
    role: str,
    outcome: str,
    causal: tuple[str, ...] = (),
    confidence: str,
    scoreable: bool,
    master: str,
) -> object:
    test_sha = _sha(f"test:{case_id}")
    reference_sha = _sha(f"ref:{case_id}") if mode == "paired_reference" else None
    return make_case(
        case_id=case_id,
        split="validation",
        mode=mode,
        role=role,
        expected_outcome=outcome,
        expected_causal_set=causal,
        confidence_tier=confidence,
        scoreable=scoreable,
        source_id=f"src_{master}",
        license_id="CC0-1.0",
        parent_master_id=master,
        recording_key=f"rec_{case_id}",
        transform_identity=f"xform_{case_id}",
        test_wav_sha256=test_sha,
        reference_wav_sha256=reference_sha,
        arms=make_arm_plans(
            mode=mode, test_sha=test_sha, reference_sha=reference_sha
        ),
    )


@pytest.fixture
def validation_manifest() -> ContextualManifest:
    """Exact 20-case validation-shaped distribution from the design."""
    cases = [
        # paired_reference (10)
        _case(
            case_id="val_p_clean",
            mode="paired_reference",
            role="clean",
            outcome="no_supported_fault",
            confidence="reference_supported",
            scoreable=True,
            master="master_a",
        ),
        _case(
            case_id="val_p_clip_1",
            mode="paired_reference",
            role="clipping",
            outcome="supported_fault",
            causal=("clipping",),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_b",
        ),
        _case(
            case_id="val_p_clip_2",
            mode="paired_reference",
            role="clipping",
            outcome="supported_fault",
            causal=("clipping",),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_c",
        ),
        _case(
            case_id="val_p_harm_1",
            mode="paired_reference",
            role="harmonic",
            outcome="supported_fault",
            causal=("harmonic_distortion",),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_d",
        ),
        _case(
            case_id="val_p_harm_2",
            mode="paired_reference",
            role="harmonic",
            outcome="supported_fault",
            causal=("harmonic_distortion",),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_e",
        ),
        _case(
            case_id="val_p_comb_1",
            mode="paired_reference",
            role="combined",
            outcome="supported_fault",
            causal=("clipping", "harmonic_distortion"),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_f",
        ),
        _case(
            case_id="val_p_comb_2",
            mode="paired_reference",
            role="combined",
            outcome="supported_fault",
            causal=("clipping", "harmonic_distortion"),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_g",
        ),
        _case(
            case_id="val_p_even_1",
            mode="paired_reference",
            role="natural_even_control",
            outcome="no_supported_fault",
            confidence="reference_supported",
            scoreable=True,
            master="master_h",
        ),
        _case(
            case_id="val_p_even_2",
            mode="paired_reference",
            role="natural_even_control",
            outcome="no_supported_fault",
            confidence="reference_supported",
            scoreable=True,
            master="master_i",
        ),
        _case(
            case_id="val_p_invalid",
            mode="paired_reference",
            role="invalid_comparison",
            outcome="inconclusive",
            confidence="reference_supported",
            scoreable=True,
            master="master_j",
        ),
        # nominal (4)
        _case(
            case_id="val_n_clean",
            mode="nominal_single_tone",
            role="clean",
            outcome="no_supported_fault",
            confidence="reference_supported",
            scoreable=True,
            master="master_k",
        ),
        _case(
            case_id="val_n_clip",
            mode="nominal_single_tone",
            role="clipping",
            outcome="supported_fault",
            causal=("clipping",),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_l",
        ),
        _case(
            case_id="val_n_harm",
            mode="nominal_single_tone",
            role="harmonic",
            outcome="supported_fault",
            causal=("harmonic_distortion",),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_m",
        ),
        _case(
            case_id="val_n_mismatch",
            mode="nominal_single_tone",
            role="frequency_mismatch",
            outcome="inconclusive",
            confidence="reference_supported",
            scoreable=True,
            master="master_n",
        ),
        # single_signal (6)
        _case(
            case_id="val_s_clean",
            mode="single_signal",
            role="clean",
            outcome="no_supported_fault",
            confidence="reference_supported",
            scoreable=True,
            master="master_o",
        ),
        _case(
            case_id="val_s_clip",
            mode="single_signal",
            role="clipping",
            outcome="supported_fault",
            causal=("clipping",),
            confidence="strong_ground_truth",
            scoreable=True,
            master="master_p",
        ),
        _case(
            case_id="val_s_ctrl_inc",
            mode="single_signal",
            role="controlled_inconclusive",
            outcome="inconclusive",
            confidence="reference_supported",
            scoreable=True,
            master="master_q",
        ),
        _case(
            case_id="val_s_dom_1",
            mode="single_signal",
            role="domain_out_inconclusive",
            outcome="inconclusive",
            confidence="weak_observation",
            scoreable=False,
            master="master_r",
        ),
        _case(
            case_id="val_s_dom_2",
            mode="single_signal",
            role="domain_out_inconclusive",
            outcome="inconclusive",
            confidence="unknown",
            scoreable=False,
            master="master_s",
        ),
        _case(
            case_id="val_s_dom_3",
            mode="single_signal",
            role="domain_out_inconclusive",
            outcome="inconclusive",
            confidence="weak_observation",
            scoreable=False,
            master="master_t",
        ),
    ]
    manifest = ContextualManifest(
        manifest_id="contextual_validation_fixture_1",
        split="validation",
        scoring_version=CONTEXTUAL_SCORING_VERSION,
        cases=tuple(cases),  # type: ignore[arg-type]
        paired_harmonic_slots=(),
    )
    slots = build_slot_plan(manifest)
    return manifest.model_copy(update={"paired_harmonic_slots": slots})
