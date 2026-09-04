"""T-CX133–T-CX137: contextual scoring metrics."""

from __future__ import annotations

from signal_diag.evaluation.contextual.models import ContextualManifest
from signal_diag.evaluation.contextual.runner import run_contextual_arms
from signal_diag.evaluation.contextual.scoring import score_contextual_run


def test_t_cx133_scoreable_denominators_are_fixed(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(validation_manifest)
    score = score_contextual_run(
        validation_manifest,
        results["contextual_agent"],
        arm="contextual_agent",
        ablation_results=results["no_context_ablation"],
    )
    assert score.aggregate.outcome_accuracy.denominator == 17
    assert score.aggregate.causal_exact_set_accuracy.denominator == 17
    assert score.aggregate.inconclusive_appropriateness.denominator == 6
    assert score.aggregate.inconclusive_appropriateness.numerator >= 5


def test_t_cx134_natural_even_fp_is_zero_for_oracle_arm(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(validation_manifest)
    score = score_contextual_run(
        validation_manifest,
        results["contextual_agent"],
        arm="contextual_agent",
    )
    assert score.aggregate.natural_even_harmonic_fp == 0


def test_t_cx135_zero_prediction_denominator_is_not_evaluated() -> None:
    from signal_diag.evaluation.contextual.scoring import _precision_or_na

    assert _precision_or_na(0, 0) == "not_evaluated"


def test_t_cx136_infrastructure_failure_counts_incorrect(
    validation_manifest: ContextualManifest,
) -> None:
    results = list(run_contextual_arms(validation_manifest)["contextual_agent"])
    failed = results[0].model_copy(
        update={
            "status": "infrastructure_failure",
            "infrastructure_failure": True,
            "predicted_outcome": None,
            "predicted_causal_set": (),
            "evidence_refs_complete": False,
        }
    )
    patched = (failed, *results[1:])
    score = score_contextual_run(
        validation_manifest,
        patched,
        arm="contextual_agent",
    )
    assert score.aggregate.outcome_accuracy.numerator == 16


def test_t_cx137_ablation_delta_is_positive_for_oracle(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(validation_manifest)
    score = score_contextual_run(
        validation_manifest,
        results["contextual_agent"],
        arm="contextual_agent",
        ablation_results=results["no_context_ablation"],
    )
    assert score.aggregate.ablation_correct_delta is not None
    assert score.aggregate.ablation_correct_delta >= 3
