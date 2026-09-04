"""T-CX129–T-CX132: three-arm runner behavior."""

from __future__ import annotations

from signal_diag.evaluation.contextual.models import ContextualManifest
from signal_diag.evaluation.contextual.runner import (
    run_contextual_arms,
    run_fixed_pipeline_case,
)


def test_t_cx129_three_arms_execute_once(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(validation_manifest, execute_once=True)
    assert set(results) == {
        "contextual_agent",
        "fixed_pipeline",
        "no_context_ablation",
    }
    for arm_results in results.values():
        assert len(arm_results) == 20


def test_t_cx130_fixed_pipeline_is_conservative_on_domain_out(
    validation_manifest: ContextualManifest,
) -> None:
    case = next(
        item
        for item in validation_manifest.cases
        if item.role == "domain_out_inconclusive"
    )
    result = run_fixed_pipeline_case(case)
    assert result.predicted_outcome == "inconclusive"
    assert result.predicted_causal_set == ()


def test_t_cx131_ablation_cannot_claim_paired_harmonic(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(validation_manifest)
    ablation = {
        item.case_id: item for item in results["no_context_ablation"]
    }
    harm = ablation["val_p_harm_1"]
    assert harm.predicted_outcome == "inconclusive"
    assert "harmonic_distortion" not in harm.predicted_causal_set


def test_t_cx132_ablation_uses_same_test_sha(
    validation_manifest: ContextualManifest,
) -> None:
    for slot in validation_manifest.paired_harmonic_slots:
        assert slot.contextual.test_wav_sha256 == slot.ablation.test_wav_sha256
