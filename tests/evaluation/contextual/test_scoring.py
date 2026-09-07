"""T-CX133–T-CX137: contextual scoring metrics."""

from __future__ import annotations

from signal_diag.evaluation.contextual.models import (
    ArmResult,
    ContextualCase,
    ContextualManifest,
)
from signal_diag.evaluation.contextual.runner import run_contextual_arms
from signal_diag.evaluation.contextual.scoring import score_contextual_run


def _scoring_oracle(case: ContextualCase, arm: str) -> ArmResult:
    predicted = case.expected_causal_set
    outcome = case.expected_outcome
    if arm == "no_context_ablation" and "harmonic_distortion" in predicted:
        predicted = tuple(item for item in predicted if item != "harmonic_distortion")
        outcome = "supported_fault" if predicted else "inconclusive"
    return ArmResult(
        case_id=case.case_id,
        arm=arm,  # type: ignore[arg-type]
        status="ok",
        predicted_outcome=outcome,
        predicted_causal_set=predicted,
        evidence_refs_complete=True,
        claim_count=max(1, len(predicted)),
        grounded_claim_count=1,
        predicted_positive_fault_claim_count=len(predicted),
        unsupported_positive_fault_claim_count=0,
    )


def test_t_cx133_scoreable_denominators_are_fixed(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(validation_manifest, oracle=_scoring_oracle)
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
    results = run_contextual_arms(validation_manifest, oracle=_scoring_oracle)
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
    results = list(
        run_contextual_arms(validation_manifest, oracle=_scoring_oracle)[
            "contextual_agent"
        ]
    )
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
    results = run_contextual_arms(validation_manifest, oracle=_scoring_oracle)
    score = score_contextual_run(
        validation_manifest,
        results["contextual_agent"],
        arm="contextual_agent",
        ablation_results=results["no_context_ablation"],
    )
    assert score.aggregate.ablation_correct_delta is not None
    assert score.aggregate.ablation_correct_delta >= 3


def test_t_cx256_grounding_and_unsupported_use_dynamic_claim_populations(
    validation_manifest: ContextualManifest,
) -> None:
    results = list(
        run_contextual_arms(validation_manifest, oracle=_scoring_oracle)[
            "contextual_agent"
        ]
    )
    results[0] = results[0].model_copy(
        update={
            "claim_count": 2,
            "grounded_claim_count": 2,
            "predicted_positive_fault_claim_count": 1,
            "unsupported_positive_fault_claim_count": 0,
        }
    )
    results[1] = results[1].model_copy(
        update={
            "claim_count": 1,
            "grounded_claim_count": 0,
            "predicted_positive_fault_claim_count": 1,
            "unsupported_positive_fault_claim_count": 1,
        }
    )
    for index in range(2, len(results)):
        claim_count = 1
        results[index] = results[index].model_copy(
            update={
                "claim_count": claim_count,
                "grounded_claim_count": 1,
                "predicted_positive_fault_claim_count": 0,
                "unsupported_positive_fault_claim_count": 0,
            }
        )

    score = score_contextual_run(
        validation_manifest,
        results,
        arm="contextual_agent",
    )

    assert score.aggregate.evidence_grounding.numerator == 20
    assert score.aggregate.evidence_grounding.denominator == 21
    assert score.aggregate.unsupported_claim_rate.numerator == 1
    assert score.aggregate.unsupported_claim_rate.denominator == 2


def test_t_cx257_failure_without_diagnosis_is_absent_from_claim_populations(
    validation_manifest: ContextualManifest,
) -> None:
    results = list(
        run_contextual_arms(validation_manifest, oracle=_scoring_oracle)[
            "contextual_agent"
        ]
    )
    results[0] = results[0].model_copy(
        update={
            "status": "infrastructure_failure",
            "infrastructure_failure": True,
            "predicted_outcome": None,
            "predicted_causal_set": (),
            "evidence_refs_complete": False,
            "claim_count": 0,
            "grounded_claim_count": 0,
            "predicted_positive_fault_claim_count": 0,
            "unsupported_positive_fault_claim_count": 0,
        }
    )
    for index in range(1, len(results)):
        results[index] = results[index].model_copy(
            update={
                "claim_count": 1,
                "grounded_claim_count": 1,
                "predicted_positive_fault_claim_count": 0,
                "unsupported_positive_fault_claim_count": 0,
            }
        )

    score = score_contextual_run(
        validation_manifest,
        results,
        arm="contextual_agent",
    )

    assert score.aggregate.evidence_grounding.numerator == 19
    assert score.aggregate.evidence_grounding.denominator == 19
    assert score.aggregate.unsupported_claim_rate.denominator == 0


def test_t_cx261_arm_result_rejects_impossible_claim_populations() -> None:
    import pytest

    with pytest.raises(ValueError, match="positive claims cannot exceed total"):
        ArmResult(
            case_id="case",
            arm="contextual_agent",
            status="ok",
            claim_count=1,
            predicted_positive_fault_claim_count=2,
        )

    with pytest.raises(ValueError, match="failed results cannot contain"):
        ArmResult(
            case_id="case",
            arm="contextual_agent",
            status="infrastructure_failure",
            infrastructure_failure=True,
            claim_count=1,
        )
