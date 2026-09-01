"""Checkpoint I — external scoring and stratification (EV-T040–EV-T043)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from signal_diag.evaluation.external.models import (
    ExternalAggregate,
    ExternalStratum,
    ReviewAgreement,
)
from signal_diag.evaluation.external.scoring import (
    EXTERNAL_SCORING_ID,
    EXTERNAL_SCORING_VERSION,
    aggregate_external_scores,
    evaluate_external_targets,
    score_external_trace,
)
from signal_diag.evaluation.models import EvaluationCase, RateMetric
from tests.evaluation.conftest import (
    make_condition,
    make_evaluation_case,
    make_sufficient_set,
)
from tests.evaluation.external.conftest import make_external_case
from tests.evaluation.test_scoring import (
    _agent_trace,
    _claim,
    _evidence,
)

_UNKNOWN_CASE = make_external_case(
    case_id="1111111111111111",
    confidence="unknown",
    external_class="ambiguous",
    source_group="C",
    parent_master_id=None,
    transform=None,
)
_STRONG_CASE = make_external_case(
    case_id="2222222222222222",
    confidence="strong_ground_truth",
    external_class="clipping",
    source_group="B",
    causal_faults=("clipping",),
    acceptable_outcomes=("supported_fault",),
)


def _clip_ratio_evidence(evidence_id: str = "ev_clip") -> object:
    return _evidence(
        evidence_id=evidence_id,
        call_id="call_000",
        tool_name="detect_clipping",
        metric="clipping_ratio",
        value=0.05,
    )


def _trace_evaluation_case() -> EvaluationCase:
    condition = make_condition(
        condition_id="cond_primary",
        tool_name="detect_clipping",
        metric="clipping_ratio",
        comparator="gt",
        expected_value=0.01,
        supports_claims=("clipping",),
    )
    return make_evaluation_case(
        "clipping",
        case_id="case_external_trace",
        observable_conditions=(condition,),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_primary",
                condition_refs=("cond_primary",),
                supported_claims=("clipping",),
                acceptable_outcomes=("supported_fault",),
            ),
        ),
        causal_faults=("clipping",),
        acceptable_outcomes=("supported_fault",),
    )


def _trace_with_clipping_claim() -> object:
    evidence = _clip_ratio_evidence()
    return _agent_trace(
        _trace_evaluation_case(),
        (
            {
                "kind": "tool",
                "tool_name": "detect_clipping",
                "evidence": (evidence,),
            },
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
            ),
        ),
        outcome="supported_fault",
    )


def _trace_with_foreign_evidence_reference() -> object:
    evidence = _clip_ratio_evidence("ev_clip")
    return _agent_trace(
        _trace_evaluation_case(),
        (
            {
                "kind": "tool",
                "tool_name": "detect_clipping",
                "evidence": (evidence,),
            },
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_foreign",),
            ),
        ),
        outcome="supported_fault",
    )


def test_ev_t040_unknown_case_has_no_correctness_boolean() -> None:
    score = score_external_trace(_UNKNOWN_CASE, _trace_with_clipping_claim())  # type: ignore[arg-type]
    assert score.outcome_correct is None
    assert score.causal_exact_set_correct is None
    assert score.positive_causal_claim_on_unscored is True


def test_ev_t041_grounding_is_same_run_even_for_unscored_case() -> None:
    score = score_external_trace(
        _UNKNOWN_CASE,
        _trace_with_foreign_evidence_reference(),  # type: ignore[arg-type]
    )
    assert score.evidence_grounding == RateMetric(
        numerator=0,
        denominator=1,
        value=0.0,
    )
    assert score.unsupported_same_run_claims == 1


def test_ev_t042_external_scoring_identity() -> None:
    score = score_external_trace(_STRONG_CASE, _trace_with_clipping_claim())  # type: ignore[arg-type]
    assert score.external_scoring_id == EXTERNAL_SCORING_ID
    assert score.external_scoring_version == EXTERNAL_SCORING_VERSION
    assert score.external_scoring_id == "signal_diag.external_scoring"
    assert score.external_scoring_version == "1.0.0"

    repo_root = Path(__file__).resolve().parents[3]
    scoring_path = repo_root / "src/signal_diag/evaluation/scoring.py"
    digest = hashlib.sha256(scoring_path.read_bytes()).hexdigest()
    assert digest == "91d5f13f460dd30b14b777aa6cb805fa69fd54577a64fc00066d9f44339f0cf4"


def test_ev_t043_stratified_aggregates_expose_numerator_denominator_exclusions() -> None:
    strong_a = make_external_case(
        case_id="aaaaaaaaaaaaaaaa",
        source_group="A",
        external_class="clipping",
        confidence="reference_supported",
        parent_master_id=None,
        transform=None,
        source_recording_key="src_a",
        capture_configuration_key="cap_a",
    )
    unknown_c = make_external_case(
        case_id="cccccccccccccccc",
        source_group="C",
        external_class="ambiguous",
        confidence="unknown",
        parent_master_id=None,
        transform=None,
        source_recording_key="src_c",
        capture_configuration_key="cap_c",
    )
    trace = _trace_with_clipping_claim()
    scores = (
        score_external_trace(strong_a, trace),  # type: ignore[arg-type]
        score_external_trace(unknown_c, trace),  # type: ignore[arg-type]
    )
    aggregate = aggregate_external_scores(
        (strong_a, unknown_c),
        scores,
        (),
    )
    assert aggregate.external_scoring_id == EXTERNAL_SCORING_ID
    assert aggregate.outcome_accuracy is not None
    assert aggregate.outcome_accuracy.numerator == 1
    assert aggregate.outcome_accuracy.denominator == 1
    assert aggregate.positive_causal_claims_on_unscored == RateMetric(
        numerator=1,
        denominator=1,
        value=1.0,
    )

    dimensions = {stratum.dimension for stratum in aggregate.strata}
    assert dimensions >= {
        "execution_path",
        "source_group",
        "confidence",
        "external_class",
        "source_recording_key",
        "capture_configuration_key",
    }
    for stratum in aggregate.strata:
        assert isinstance(stratum, ExternalStratum)
        for metric in stratum.metrics:
            assert metric.numerator >= 0
            assert metric.denominator >= 0
            assert metric.exclusions >= 0


def test_strong_case_scores_outcome_and_causal_set() -> None:
    score = score_external_trace(_STRONG_CASE, _trace_with_clipping_claim())  # type: ignore[arg-type]
    assert score.outcome_correct is True
    assert score.causal_exact_set_correct is True
    assert score.positive_causal_claim_on_unscored is None


def test_evaluate_external_targets_meets_when_thresholds_pass() -> None:
    aggregate = ExternalAggregate(
        outcome_accuracy=RateMetric(numerator=20, denominator=24, value=20 / 24),
        causal_exact_set_accuracy=RateMetric(numerator=19, denominator=24, value=19 / 24),
        causal_macro_f1=0.80,
        evidence_grounding=RateMetric(numerator=28, denominator=28, value=1.0),
        unsupported_same_run_claim_rate=RateMetric(numerator=0, denominator=10, value=0.0),
        unnecessary_tool_action_rate=RateMetric(numerator=2, denominator=20, value=0.1),
        inconclusive_appropriateness=RateMetric(numerator=5, denominator=6, value=5 / 6),
    )
    review = ReviewAgreement(
        raw_outcome_agreement=0.90,
        causal_set_agreement=0.85,
        outcome_cohen_kappa=0.75,
        confidence_quadratic_kappa=0.72,
    )
    assert evaluate_external_targets(aggregate, review) == "meets_target"


def test_evaluate_external_targets_below_when_threshold_misses() -> None:
    aggregate = ExternalAggregate(
        outcome_accuracy=RateMetric(numerator=18, denominator=24, value=0.75),
        causal_exact_set_accuracy=RateMetric(numerator=19, denominator=24, value=19 / 24),
        causal_macro_f1=0.80,
        evidence_grounding=RateMetric(numerator=28, denominator=28, value=1.0),
        unsupported_same_run_claim_rate=RateMetric(numerator=0, denominator=10, value=0.0),
        unnecessary_tool_action_rate=RateMetric(numerator=2, denominator=20, value=0.1),
        inconclusive_appropriateness=RateMetric(numerator=5, denominator=6, value=5 / 6),
    )
    review = ReviewAgreement(
        raw_outcome_agreement=0.90,
        causal_set_agreement=0.85,
        outcome_cohen_kappa=0.75,
        confidence_quadratic_kappa=0.72,
    )
    assert evaluate_external_targets(aggregate, review) == "below_target"


def test_evaluate_external_targets_not_evaluated_when_metrics_missing() -> None:
    review = ReviewAgreement(raw_outcome_agreement=0.90)
    assert evaluate_external_targets(ExternalAggregate(), review) == "not_evaluated"
