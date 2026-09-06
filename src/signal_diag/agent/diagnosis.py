"""Finish-decision and diagnosis validation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.tools.evidence import Evidence

from .models import (
    DiagnosisClaim,
    DiagnosisOutcome,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
    TaskType,
)

CausalPolicyVersion = Literal[
    "v9_4_legacy",
    "v9_5_contextual",
    "v9_6_contextual",
    "v9_7_deterministic_rule_closure",
    "v9_8_claim_reference_recovery",
    "v9_9_paired_reference_recovery",
    "v9_10_contextual_clipping_recovery",
]
_CONTEXTUAL_CAUSAL_POLICIES = frozenset(
    {
        "v9_5_contextual",
        "v9_6_contextual",
        "v9_7_deterministic_rule_closure",
        "v9_8_claim_reference_recovery",
        "v9_9_paired_reference_recovery",
        "v9_10_contextual_clipping_recovery",
    }
)
_SUBSTANTIAL_CLIPPING_RULE_IDS = frozenset(
    {
        "rule_clipping_ratio_acceptable",
        "rule_flat_top_absent",
    }
)
_SUBSTANTIAL_TEST_CLIPPING_RULE_IDS = frozenset(
    {
        "rule_test_clipping_ratio_acceptable",
        "rule_test_flat_top_absent",
    }
)


def _claim_requires_evidence(claim: DiagnosisClaim, outcome: DiagnosisOutcome) -> bool:
    if outcome == "inconclusive":
        return False
    return claim.fault_type != "inconclusive"


def _cited_evidence(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
) -> list[Evidence]:
    cited: list[Evidence] = []
    for evidence_id in claim.evidence_refs:
        item = evidence_by_id.get(evidence_id)
        if item is not None:
            cited.append(item)
    return cited


def _cited_evaluations(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
) -> list[RuleEvaluation]:
    cited: list[RuleEvaluation] = []
    for evaluation_id in claim.rule_refs:
        item = evaluations_by_id.get(evaluation_id)
        if item is not None:
            cited.append(item)
    return cited


def _has_harmonic_even_order_structure(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    return any(
        item.metric == "series_kind"
        and item.value == "even_order_present"
        and item.validity == "valid"
        for item in _cited_evidence(claim, evidence_by_id)
    )


def _has_clipping_mechanism(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    return any(
        item.metric == "clipping_mechanism" and item.value is True
        for item in _cited_evidence(claim, evidence_by_id)
    )


def _has_test_clipping_mechanism(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    return any(
        item.metric == "test_clipping_mechanism"
        and item.value is True
        and item.validity == "valid"
        for item in _cited_evidence(claim, evidence_by_id)
    )


def _has_substantial_clipping_rule_fail(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
) -> bool:
    for evaluation in _cited_evaluations(claim, evaluations_by_id):
        if (
            evaluation.rule_id in _SUBSTANTIAL_CLIPPING_RULE_IDS
            and evaluation.judgment == "fail"
        ):
            return True
    return False


def _has_substantial_test_clipping_rule_fail(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
) -> bool:
    return any(
        evaluation.rule_id in _SUBSTANTIAL_TEST_CLIPPING_RULE_IDS
        and evaluation.judgment == "fail"
        for evaluation in _cited_evaluations(claim, evaluations_by_id)
    )


def _validate_v910_clipping_supported(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    has_legacy_mechanism = _has_clipping_mechanism(claim, evidence_by_id)
    has_contextual_mechanism = _has_test_clipping_mechanism(claim, evidence_by_id)
    has_legacy_fail = _has_substantial_clipping_rule_fail(claim, evaluations_by_id)
    has_contextual_fail = _has_substantial_test_clipping_rule_fail(
        claim, evaluations_by_id
    )
    legacy_ok = has_legacy_mechanism and has_legacy_fail
    contextual_ok = has_contextual_mechanism and has_contextual_fail
    if (has_legacy_mechanism or has_legacy_fail) and (
        has_contextual_mechanism or has_contextual_fail
    ):
        raise DiagnosisValidationError(
            "clipping claim mixes legacy and contextual evidence families; "
            "no coherent family"
        )
    if not (legacy_ok or contextual_ok):
        raise DiagnosisValidationError(
            "clipping claim lacks one coherent evidence family"
        )


def _validate_v910_no_supported_fault(
    claim: DiagnosisClaim,
    context: StimulusContext,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    _require_metric(
        claim,
        evidence_by_id,
        "test_clipping_mechanism",
        False,
        gate_name="test_clipping_mechanism=false",
    )
    _require_rule_pass(
        claim,
        evaluations_by_id,
        "rule_test_clipping_ratio_acceptable",
        gate_name="test clipping ratio PASS",
    )
    _require_rule_pass(
        claim,
        evaluations_by_id,
        "rule_test_flat_top_absent",
        gate_name="test flat-top absent PASS",
    )
    _validate_contextual_mode_no_fault(
        claim, context, evaluations_by_id
    )


def _v910_clipping_subset_is_supported(
    decision: FinishDecision,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> bool:
    if any(
        claim.fault_type not in {"clipping", "harmonic_distortion"}
        for claim in decision.claims
    ):
        return False
    clipping_claims = tuple(
        claim for claim in decision.claims if claim.fault_type == "clipping"
    )
    if not clipping_claims:
        return False
    try:
        for claim in clipping_claims:
            _validate_v910_clipping_supported(
                claim, evidence_by_id, evaluations_by_id
            )
    except DiagnosisValidationError:
        return False
    return True


def _require_metric(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
    metric: str,
    value: object,
    *,
    gate_name: str,
) -> None:
    for item in _cited_evidence(claim, evidence_by_id):
        if (
            item.metric == metric
            and item.value == value
            and item.validity == "valid"
        ):
            return
    raise DiagnosisValidationError(f"missing {gate_name}")


def _require_rule_judgment(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
    rule_id: str,
    judgment: Literal["pass", "fail"],
    *,
    gate_name: str,
) -> None:
    for evaluation in _cited_evaluations(claim, evaluations_by_id):
        if evaluation.rule_id == rule_id and evaluation.judgment == judgment:
            return
    raise DiagnosisValidationError(f"missing {gate_name}")


def _require_rule_pass(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
    rule_id: str,
    *,
    gate_name: str,
) -> None:
    _require_rule_judgment(
        claim,
        evaluations_by_id,
        rule_id,
        "pass",
        gate_name=gate_name,
    )


def _require_rule_fail(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
    rule_id: str,
    *,
    gate_name: str,
) -> None:
    _require_rule_judgment(
        claim,
        evaluations_by_id,
        rule_id,
        "fail",
        gate_name=gate_name,
    )


def _validate_clipping_supported(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    if not _has_clipping_mechanism(claim, evidence_by_id):
        raise DiagnosisValidationError(
            "clipping supported_fault requires clipping_mechanism=true Evidence"
        )
    if not _has_substantial_clipping_rule_fail(claim, evaluations_by_id):
        raise DiagnosisValidationError(
            "clipping supported_fault requires a same-run substantial "
            "clipping rule FAIL (rule_clipping_ratio_acceptable or "
            "rule_flat_top_absent)"
        )


def _available_metric_ids(
    evidence_by_id: dict[str, Evidence],
    metric: str,
    value: object,
) -> list[str]:
    return [
        item.evidence_id
        for item in evidence_by_id.values()
        if item.metric == metric and item.value == value and item.validity == "valid"
    ]


def _available_rule_ids(
    evaluations_by_id: dict[str, RuleEvaluation],
    rule_id: str,
    judgment: Literal["pass", "fail"],
) -> list[str]:
    return [
        item.evaluation_id
        for item in evaluations_by_id.values()
        if item.rule_id == rule_id and item.judgment == judgment
    ]


def _has_cited_metric(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
    metric: str,
    value: object,
) -> bool:
    for item in _cited_evidence(claim, evidence_by_id):
        if item.metric == metric and item.value == value and item.validity == "valid":
            return True
    return False


def _has_cited_rule_judgment(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
    rule_id: str,
    judgment: Literal["pass", "fail"],
) -> bool:
    for evaluation in _cited_evaluations(claim, evaluations_by_id):
        if evaluation.rule_id == rule_id and evaluation.judgment == judgment:
            return True
    return False


def _nominal_thd_fail_evidence_ids(
    evaluations_by_id: dict[str, RuleEvaluation],
    evidence_by_id: dict[str, Evidence],
) -> list[str]:
    ids: list[str] = []
    for evaluation in evaluations_by_id.values():
        if (
            evaluation.rule_id != "rule_nominal_thd_acceptable"
            or evaluation.judgment != "fail"
        ):
            continue
        for evidence_id in evaluation.evidence_refs:
            item = evidence_by_id.get(evidence_id)
            if item is not None and item.metric == "test_thd_percent":
                ids.append(evidence_id)
    return ids


def _has_cited_nominal_thd_fail_evidence(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
    evidence_by_id: dict[str, Evidence],
) -> bool:
    cited = set(claim.evidence_refs)
    for evaluation in _cited_evaluations(claim, evaluations_by_id):
        if (
            evaluation.rule_id != "rule_nominal_thd_acceptable"
            or evaluation.judgment != "fail"
        ):
            continue
        for evidence_id in evaluation.evidence_refs:
            if evidence_id not in cited:
                continue
            item = evidence_by_id.get(evidence_id)
            if item is not None and item.metric == "test_thd_percent":
                return True
    return False


def _format_id_hint(label: str, ids: list[str]) -> str:
    if not ids:
        return f"missing {label} (no same-run ID available)"
    joined = ", ".join(ids)
    return f"missing {label} (cite {joined})"


def _collect_nominal_harmonic_deficits(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> list[str]:
    deficits: list[str] = []
    if not _has_cited_rule_judgment(
        claim, evaluations_by_id, "rule_contextual_analysis_valid", "pass"
    ):
        deficits.append(
            _format_id_hint(
                "contextual analysis PASS ruleval_id",
                _available_rule_ids(
                    evaluations_by_id, "rule_contextual_analysis_valid", "pass"
                ),
            )
        )
    if not _has_cited_rule_judgment(
        claim, evaluations_by_id, "rule_contextual_f0_compatible", "pass"
    ):
        deficits.append(
            _format_id_hint(
                "contextual F0 compatibility PASS ruleval_id",
                _available_rule_ids(
                    evaluations_by_id, "rule_contextual_f0_compatible", "pass"
                ),
            )
        )
    if not _has_cited_metric(
        claim, evidence_by_id, "test_series_kind", "even_order_present"
    ):
        deficits.append(
            _format_id_hint(
                "test_series_kind=even_order_present evidence_id",
                _available_metric_ids(
                    evidence_by_id, "test_series_kind", "even_order_present"
                ),
            )
        )
    if not _has_cited_rule_judgment(
        claim, evaluations_by_id, "rule_nominal_thd_acceptable", "fail"
    ):
        deficits.append(
            _format_id_hint(
                "nominal THD FAIL ruleval_id",
                _available_rule_ids(
                    evaluations_by_id, "rule_nominal_thd_acceptable", "fail"
                ),
            )
        )
    if not _has_cited_nominal_thd_fail_evidence(
        claim, evaluations_by_id, evidence_by_id
    ):
        deficits.append(
            _format_id_hint(
                "nominal THD FAIL test_thd_percent evidence_id",
                _nominal_thd_fail_evidence_ids(evaluations_by_id, evidence_by_id),
            )
        )
    return deficits


def _collect_paired_harmonic_deficits(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
) -> list[str]:
    requirements: tuple[tuple[str, Literal["pass", "fail"], str], ...] = (
        (
            "rule_contextual_analysis_valid",
            "pass",
            "contextual analysis PASS ruleval_id",
        ),
        (
            "rule_contextual_f0_compatible",
            "pass",
            "contextual F0 compatibility PASS ruleval_id",
        ),
        (
            "rule_reference_clipping_ratio_acceptable",
            "pass",
            "reference clipping ratio PASS ruleval_id",
        ),
        (
            "rule_reference_flat_top_absent",
            "pass",
            "reference flat-top PASS ruleval_id",
        ),
        (
            "rule_even_harmonic_growth_acceptable",
            "fail",
            "harmonic growth FAIL ruleval_id",
        ),
    )
    deficits: list[str] = []
    for rule_id, judgment, label in requirements:
        if _has_cited_rule_judgment(
            claim, evaluations_by_id, rule_id, judgment
        ):
            continue
        deficits.append(
            _format_id_hint(
                label,
                _available_rule_ids(evaluations_by_id, rule_id, judgment),
            )
        )
    return deficits


def _validate_v95_harmonic_supported(
    claim: DiagnosisClaim,
    context: StimulusContext,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    if context.mode == "single_signal":
        raise DiagnosisValidationError(
            "harmonic_distortion supported_fault lacks contextual support"
        )
    if context.mode == "paired_reference":
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_contextual_analysis_valid",
            gate_name="contextual analysis PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_contextual_f0_compatible",
            gate_name="contextual F0 compatibility PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_reference_clipping_ratio_acceptable",
            gate_name="reference clipping ratio PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_reference_flat_top_absent",
            gate_name="reference flat-top PASS",
        )
        _require_rule_fail(
            claim,
            evaluations_by_id,
            "rule_even_harmonic_growth_acceptable",
            gate_name="harmonic growth FAIL",
        )
        return
    # nominal_single_tone
    _require_rule_pass(
        claim,
        evaluations_by_id,
        "rule_contextual_analysis_valid",
        gate_name="contextual analysis PASS",
    )
    _require_rule_pass(
        claim,
        evaluations_by_id,
        "rule_contextual_f0_compatible",
        gate_name="contextual F0 compatibility PASS",
    )
    _require_metric(
        claim,
        evidence_by_id,
        "test_series_kind",
        "even_order_present",
        gate_name="test_series_kind=even_order_present",
    )
    _require_rule_fail(
        claim,
        evaluations_by_id,
        "rule_nominal_thd_acceptable",
        gate_name="nominal THD FAIL",
    )


def _validate_v98_harmonic_supported(
    claim: DiagnosisClaim,
    context: StimulusContext,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    if context.mode != "nominal_single_tone":
        _validate_v95_harmonic_supported(
            claim, context, evidence_by_id, evaluations_by_id
        )
        return
    deficits = _collect_nominal_harmonic_deficits(
        claim, evidence_by_id, evaluations_by_id
    )
    if deficits:
        raise DiagnosisValidationError(
            "nominal harmonic_distortion claim incomplete; cite ALL of the "
            "following same-run IDs together in one finish (do not fix only "
            "one): " + "; ".join(deficits)
        )


def _validate_v99_harmonic_supported(
    claim: DiagnosisClaim,
    context: StimulusContext,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    if context.mode != "paired_reference":
        _validate_v98_harmonic_supported(
            claim, context, evidence_by_id, evaluations_by_id
        )
        return
    deficits = _collect_paired_harmonic_deficits(claim, evaluations_by_id)
    if deficits:
        raise DiagnosisValidationError(
            "paired harmonic_distortion claim incomplete; cite ALL of the "
            "following same-run ruleval IDs together in one finish (do not fix "
            "only one and do not substitute nominal THD rules): "
            + "; ".join(deficits)
        )


def _validate_v95_no_supported_fault(
    claim: DiagnosisClaim,
    context: StimulusContext,
    evidence_by_id: dict[str, Evidence],
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    _require_metric(
        claim,
        evidence_by_id,
        "clipping_mechanism",
        False,
        gate_name="clipping_mechanism=false",
    )
    _require_rule_pass(
        claim,
        evaluations_by_id,
        "rule_clipping_ratio_acceptable",
        gate_name="clipping ratio PASS",
    )
    _require_rule_pass(
        claim,
        evaluations_by_id,
        "rule_flat_top_absent",
        gate_name="flat-top absent PASS",
    )
    _validate_contextual_mode_no_fault(claim, context, evaluations_by_id)


def _validate_contextual_mode_no_fault(
    claim: DiagnosisClaim,
    context: StimulusContext,
    evaluations_by_id: dict[str, RuleEvaluation],
) -> None:
    if context.mode == "paired_reference":
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_contextual_analysis_valid",
            gate_name="contextual analysis PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_contextual_f0_compatible",
            gate_name="contextual F0 compatibility PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_reference_clipping_ratio_acceptable",
            gate_name="reference clipping ratio PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_reference_flat_top_absent",
            gate_name="reference flat-top PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_even_harmonic_growth_acceptable",
            gate_name="harmonic growth PASS",
        )
    elif context.mode == "nominal_single_tone":
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_contextual_analysis_valid",
            gate_name="contextual analysis PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_contextual_f0_compatible",
            gate_name="contextual F0 compatibility PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_nominal_thd_acceptable",
            gate_name="nominal THD PASS",
        )
    else:
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_harmonic_analysis_valid",
            gate_name="harmonic analysis PASS",
        )
        _require_rule_pass(
            claim,
            evaluations_by_id,
            "rule_thd_acceptable",
            gate_name="THD PASS",
        )


def _require_inconclusive_grounding(decision: FinishDecision) -> None:
    for claim in decision.claims:
        if claim.evidence_refs or claim.rule_refs:
            return
    if decision.claims:
        raise DiagnosisValidationError(
            "inconclusive finish requires at least one same-run Evidence or rule ref"
        )


def validate_finish_decision(
    decision: FinishDecision,
    *,
    known_evidence_ids: frozenset[str],
    task_assessment: TaskAssessment | None,
    known_rule_evaluation_ids: frozenset[str] = frozenset(),
    known_knowledge_retrieval_ids: frozenset[str] = frozenset(),
    evidence: Sequence[Evidence] | None = None,
    rule_evaluations: Sequence[RuleEvaluation] | None = None,
    stimulus_context: StimulusContext | None = None,
    causal_policy_version: CausalPolicyVersion = "v9_4_legacy",
) -> None:
    """Validate finish semantics before accepting a terminal diagnosis."""
    assessment = decision.task_assessment or task_assessment
    if assessment is None:
        raise DiagnosisValidationError("finish decision requires task assessment")

    for claim in decision.claims:
        for evidence_id in claim.evidence_refs:
            if evidence_id not in known_evidence_ids:
                raise DiagnosisValidationError(
                    f"unknown evidence reference: {evidence_id}"
                )
        for rule_id in claim.rule_refs:
            if rule_id not in known_rule_evaluation_ids:
                raise DiagnosisValidationError(
                    f"unknown rule reference: {rule_id}"
                )
        for knowledge_id in claim.knowledge_refs:
            if knowledge_id not in known_knowledge_retrieval_ids:
                raise DiagnosisValidationError(
                    f"unknown knowledge reference: {knowledge_id}"
                )

    if assessment.task_type == "unsupported":
        return

    if decision.outcome == "inconclusive":
        if not decision.limitations:
            raise DiagnosisValidationError(
                "inconclusive finish requires at least one limitation"
            )
        if causal_policy_version in _CONTEXTUAL_CAUSAL_POLICIES:
            _require_inconclusive_grounding(decision)
        return

    if not decision.claims:
        raise DiagnosisValidationError(
            "supported or no-supported-fault finish requires at least one claim"
        )

    if decision.outcome == "supported_fault":
        fault_types = {claim.fault_type for claim in decision.claims}
        positive_faults = fault_types - {"no_supported_fault", "inconclusive"}
        if positive_faults and "no_supported_fault" in fault_types:
            raise DiagnosisValidationError(
                "supported_fault must not include a sibling no_supported_fault claim"
            )

    for claim in decision.claims:
        if not _claim_requires_evidence(claim, decision.outcome):
            continue
        if not claim.evidence_refs:
            if (
                causal_policy_version == "v9_8_claim_reference_recovery"
                and decision.outcome == "supported_fault"
                and claim.fault_type == "harmonic_distortion"
                and stimulus_context is not None
                and stimulus_context.mode == "nominal_single_tone"
                and evidence is not None
            ):
                continue
            raise DiagnosisValidationError(
                f"claim {claim.claim_id} requires evidence references"
            )
        for evidence_id in claim.evidence_refs:
            if evidence_id not in known_evidence_ids:
                raise DiagnosisValidationError(
                    f"unknown evidence reference: {evidence_id}"
                )

    if evidence is None:
        return

    evidence_by_id = {item.evidence_id: item for item in evidence}
    evaluations_by_id = {
        item.evaluation_id: item for item in (rule_evaluations or ())
    }

    if causal_policy_version in _CONTEXTUAL_CAUSAL_POLICIES:
        if stimulus_context is None:
            raise DiagnosisValidationError(
                f"{causal_policy_version} finish requires stimulus_context"
            )
        for claim in decision.claims:
            if decision.outcome == "supported_fault":
                if claim.fault_type == "clipping":
                    if causal_policy_version == "v9_10_contextual_clipping_recovery":
                        _validate_v910_clipping_supported(
                            claim, evidence_by_id, evaluations_by_id
                        )
                    else:
                        _validate_clipping_supported(
                            claim, evidence_by_id, evaluations_by_id
                        )
                elif claim.fault_type == "harmonic_distortion":
                    try:
                        if causal_policy_version == "v9_9_paired_reference_recovery":
                            _validate_v99_harmonic_supported(
                                claim,
                                stimulus_context,
                                evidence_by_id,
                                evaluations_by_id,
                            )
                        elif causal_policy_version == "v9_8_claim_reference_recovery":
                            _validate_v98_harmonic_supported(
                                claim,
                                stimulus_context,
                                evidence_by_id,
                                evaluations_by_id,
                            )
                        else:
                            _validate_v95_harmonic_supported(
                                claim,
                                stimulus_context,
                                evidence_by_id,
                                evaluations_by_id,
                            )
                    except DiagnosisValidationError as error:
                        if (
                            causal_policy_version == "v9_10_contextual_clipping_recovery"
                            and stimulus_context.mode == "single_signal"
                            and _v910_clipping_subset_is_supported(
                                decision, evidence_by_id, evaluations_by_id
                            )
                        ):
                            raise DiagnosisValidationError(
                                "clipping claim is independently supported; preserve "
                                "the clipping claim and its same-run references; "
                                "remove the unsupported harmonic_distortion sibling"
                            ) from error
                        raise
            elif decision.outcome == "no_supported_fault" and (
                claim.fault_type == "no_supported_fault"
            ):
                if causal_policy_version == "v9_10_contextual_clipping_recovery":
                    _validate_v910_no_supported_fault(
                        claim,
                        stimulus_context,
                        evidence_by_id,
                        evaluations_by_id,
                    )
                else:
                    _validate_v95_no_supported_fault(
                        claim,
                        stimulus_context,
                        evidence_by_id,
                        evaluations_by_id,
                    )
        return

    if decision.outcome != "supported_fault":
        return

    for claim in decision.claims:
        if (
            claim.fault_type == "harmonic_distortion"
            and not _has_harmonic_even_order_structure(claim, evidence_by_id)
        ):
            raise DiagnosisValidationError(
                "harmonic_distortion supported_fault requires series_kind="
                "even_order_present Evidence"
            )
        if claim.fault_type == "clipping":
            _validate_clipping_supported(claim, evidence_by_id, evaluations_by_id)


def build_task_type(decision: FinishDecision, assessment: TaskAssessment) -> TaskType:
    return assessment.task_type
