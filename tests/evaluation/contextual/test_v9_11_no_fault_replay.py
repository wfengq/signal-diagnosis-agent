"""T-CX255: replay the three retained v9.10 no-fault failure shapes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
)
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.tools.evidence import Evidence

REPO = Path(__file__).resolve().parents[3]
RUN = (
    REPO
    / "docs/evaluations/v0_3/contextual/development/"
    "study_v0_3_contextual_dev_1/agent_v9_10_dev_confirmation_4"
)
ASSESSMENT = TaskAssessment(task_type="distortion_analysis", objective="S1")


def _load_result(
    case_id: str,
) -> tuple[tuple[Evidence, ...], tuple[RuleEvaluation, ...]]:
    payload = json.loads(
        (RUN / "cases" / case_id / "result.json").read_text(encoding="utf-8")
    )
    evidence = tuple(Evidence.model_validate(item) for item in payload["evidence"])
    rules = tuple(
        RuleEvaluation.model_validate(evaluation)
        for batch in payload["rule_evaluation_batches"]
        for evaluation in batch["evaluations"]
    )
    return evidence, rules


def _context(mode: str) -> StimulusContext:
    if mode == "single_signal":
        return StimulusContext(
            mode="single_signal",
            test_signal_id="replay_test",
            assertion_source="evaluation_manifest",
        )
    return StimulusContext(
        mode="paired_reference",
        test_signal_id="replay_test",
        reference_signal_id="replay_reference",
        assertion_source="evaluation_manifest",
    )


def _validate(
    claim: DiagnosisClaim,
    *,
    context: StimulusContext,
    evidence: tuple[Evidence, ...],
    rules: tuple[RuleEvaluation, ...],
) -> None:
    validate_finish_decision(
        FinishDecision(
            outcome="no_supported_fault",
            claims=(claim,),
            confidence_label="medium",
            task_assessment=ASSESSMENT,
        ),
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=context,
        causal_policy_version="v9_11_mode_aware_no_fault_recovery",
    )


@pytest.mark.parametrize(
    ("case_id", "mode", "metric", "required_rule_ids"),
    (
        (
            "393940e92c58cf0b",
            "paired_reference",
            "test_clipping_mechanism",
            (
                "rule_test_clipping_ratio_acceptable",
                "rule_test_flat_top_absent",
                "rule_contextual_analysis_valid",
                "rule_contextual_f0_compatible",
                "rule_reference_clipping_ratio_acceptable",
                "rule_reference_flat_top_absent",
                "rule_even_harmonic_growth_acceptable",
            ),
        ),
        (
            "04f4068ec91d2621",
            "paired_reference",
            "test_clipping_mechanism",
            (
                "rule_test_clipping_ratio_acceptable",
                "rule_test_flat_top_absent",
                "rule_contextual_analysis_valid",
                "rule_contextual_f0_compatible",
                "rule_reference_clipping_ratio_acceptable",
                "rule_reference_flat_top_absent",
                "rule_even_harmonic_growth_acceptable",
            ),
        ),
        (
            "eabaecd422b2eeda",
            "single_signal",
            "clipping_mechanism",
            (
                "rule_clipping_ratio_acceptable",
                "rule_flat_top_absent",
                "rule_harmonic_analysis_valid",
                "rule_thd_acceptable",
            ),
        ),
    ),
)
def test_t_cx255_replay_rejects_incomplete_then_accepts_complete_no_fault(
    case_id: str,
    mode: str,
    metric: str,
    required_rule_ids: tuple[str, ...],
) -> None:
    evidence, rules = _load_result(case_id)
    mechanism = next(
        item for item in evidence if item.metric == metric and item.value is False
    )
    required = tuple(
        next(
            item
            for item in rules
            if item.rule_id == rule_id and item.judgment == "pass"
        )
        for rule_id in required_rule_ids
    )
    unrelated = next(item for item in evidence if item.evidence_id != mechanism.evidence_id)
    incomplete = DiagnosisClaim(
        claim_id="claim_replay_incomplete",
        fault_type="no_supported_fault",
        statement="No supported S1 fault is established.",
        evidence_refs=(unrelated.evidence_id,),
    )
    with pytest.raises(DiagnosisValidationError) as caught:
        _validate(
            incomplete,
            context=_context(mode),
            evidence=evidence,
            rules=rules,
        )
    message = str(caught.value)
    assert mechanism.evidence_id in message
    for evaluation in required:
        assert evaluation.evaluation_id in message

    complete = incomplete.model_copy(
        update={
            "claim_id": "claim_replay_complete",
            "evidence_refs": (mechanism.evidence_id,),
            "rule_refs": tuple(item.evaluation_id for item in required),
        }
    )
    _validate(
        complete,
        context=_context(mode),
        evidence=evidence,
        rules=rules,
    )
