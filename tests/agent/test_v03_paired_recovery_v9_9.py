"""T-CX192–T-CX196: v9.9 paired-reference recovery."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
)
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_8, _S1_PROMPT_V9_9
from signal_diag.agent.rule_closure import required_rule_profile
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.tools.evidence import Evidence

ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="diagnose S1 distortion",
)
_FROZEN_V98_SHA256 = (
    "6d7e18dae4bc1b7e19e3430a9266e7d2c10496df194d3571390df025c6f7bf41"
)


def _evidence(evidence_id: str, metric: str, value: object) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="analyze_contextual_distortion",
        call_id="call_contextual_000001",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        channel="mixdown",
    )


def _rule(
    evaluation_id: str,
    rule_id: str,
    judgment: str,
    evidence_ref: str,
) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment=judgment,  # type: ignore[arg-type]
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id="profile_s1_contextual_comparison",
        profile_version="1.0.0",
        evidence_refs=(evidence_ref,),
    )


def _paired_pack() -> tuple[tuple[Evidence, ...], tuple[RuleEvaluation, ...]]:
    evidence = (
        _evidence("ev_analysis", "context_valid", True),
        _evidence("ev_f0", "f0_compatible", True),
        _evidence("ev_ref_ratio", "reference_clipping_ratio", 0.0),
        _evidence("ev_ref_flat", "reference_flat_top_detected", False),
        _evidence("ev_growth", "even_harmonic_growth_percent", 8.0),
        _evidence("ev_clip_mechanism", "clipping_mechanism", True),
    )
    rules = (
        _rule("ruleval_analysis", "rule_contextual_analysis_valid", "pass", "ev_analysis"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass", "ev_f0"),
        _rule(
            "ruleval_ref_ratio",
            "rule_reference_clipping_ratio_acceptable",
            "pass",
            "ev_ref_ratio",
        ),
        _rule(
            "ruleval_ref_flat",
            "rule_reference_flat_top_absent",
            "pass",
            "ev_ref_flat",
        ),
        _rule(
            "ruleval_growth",
            "rule_even_harmonic_growth_acceptable",
            "fail",
            "ev_growth",
        ),
        _rule(
            "ruleval_clip_fail",
            "rule_clipping_ratio_acceptable",
            "fail",
            "ev_clip_mechanism",
        ),
    )
    return evidence, rules


def _paired_context() -> StimulusContext:
    return StimulusContext(
        mode="paired_reference",
        test_signal_id="sig_test",
        reference_signal_id="sig_reference",
        nominal_fundamental_hz=440.0,
        stimulus_kind="single_tone",
        assertion_source="evaluation_manifest",
    )


def _finish(claims: tuple[DiagnosisClaim, ...]) -> FinishDecision:
    return FinishDecision(
        outcome="supported_fault",
        claims=claims,
        confidence_label="medium",
        limitations=(),
        task_assessment=ASSESSMENT,
    )


def _harmonic_claim(rule_refs: tuple[str, ...]) -> DiagnosisClaim:
    return DiagnosisClaim(
        claim_id="claim_harmonic",
        fault_type="harmonic_distortion",
        statement="Paired harmonic growth supports distortion.",
        evidence_refs=("ev_growth",),
        rule_refs=rule_refs,
    )


def _validate(decision: FinishDecision) -> None:
    evidence, rules = _paired_pack()
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_paired_context(),
        causal_policy_version="v9_9_paired_reference_recovery",
    )


def test_t_cx192_paired_harmonic_keeps_all_five_requirements() -> None:
    complete_refs = (
        "ruleval_analysis",
        "ruleval_f0",
        "ruleval_ref_ratio",
        "ruleval_ref_flat",
        "ruleval_growth",
    )
    _validate(_finish((_harmonic_claim(complete_refs),)))

    for missing in complete_refs:
        incomplete = tuple(item for item in complete_refs if item != missing)
        with pytest.raises(DiagnosisValidationError, match="paired harmonic"):
            _validate(_finish((_harmonic_claim(incomplete),)))


def test_t_cx193_paired_rejection_lists_all_same_run_ids() -> None:
    with pytest.raises(DiagnosisValidationError) as caught:
        _validate(_finish((_harmonic_claim(()),)))
    message = str(caught.value)
    for evaluation_id in (
        "ruleval_analysis",
        "ruleval_f0",
        "ruleval_ref_ratio",
        "ruleval_ref_flat",
        "ruleval_growth",
    ):
        assert evaluation_id in message
    assert "together" in message.lower()
    assert "rule_nominal_thd_acceptable" not in message


def test_t_cx194_combined_claims_remain_independent() -> None:
    clipping = DiagnosisClaim(
        claim_id="claim_clipping",
        fault_type="clipping",
        statement="Clipping is independently supported.",
        evidence_refs=("ev_clip_mechanism",),
        rule_refs=("ruleval_clip_fail",),
    )
    with pytest.raises(DiagnosisValidationError) as caught:
        _validate(_finish((clipping, _harmonic_claim(("ruleval_growth",)))))
    message = str(caught.value)
    assert "ruleval_ref_ratio" in message
    assert "ruleval_ref_flat" in message
    assert "clipping supported_fault" not in message


def test_t_cx195_v99_prompt_separates_modes_and_preserves_v98() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_8.system_prompt.encode("utf-8")).hexdigest()
    assert digest == _FROZEN_V98_SHA256
    text = _S1_PROMPT_V9_9.system_prompt
    assert _S1_PROMPT_V9_9.version == "v0.3-s1-planner-9.9"
    assert "paired_reference" in text
    assert "rule_reference_clipping_ratio_acceptable" in text
    assert "rule_reference_flat_top_absent" in text
    assert "rule_even_harmonic_growth_acceptable" in text
    assert "rule_nominal_thd_acceptable" in text
    assert "do not substitute" in text.lower()
    assert "Never fall back to ScriptedPlanner" in text


def test_t_cx196_v99_rule_closure_remains_available_after_product_upgrade() -> None:
    assert _S1_PROMPT_V9_9.version == "v0.3-s1-planner-9.9"
    assert (
        required_rule_profile(
            causal_policy_version="v9_9_paired_reference_recovery",
            stimulus_context=_paired_context(),
            tool_name="analyze_contextual_distortion",
        )
        == "profile_s1_contextual_comparison"
    )


def test_t_cx191_registry_has_each_v99_id_once() -> None:
    registry = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "TEST_PLAN_V0_3_CONTEXTUAL.md"
    ).read_text(encoding="utf-8")
    ids = re.findall(r"^\| (T-CX\d+) \|", registry, flags=re.MULTILINE)
    for number in range(191, 197):
        assert ids.count(f"T-CX{number}") == 1
