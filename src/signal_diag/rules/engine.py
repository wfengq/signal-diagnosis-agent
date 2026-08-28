"""Deterministic rule evaluation over Evidence."""

from __future__ import annotations

import hashlib
import json
import operator
from collections.abc import Callable, Sequence

from signal_diag.rules.models import (
    RuleDefinition,
    RuleEvaluation,
    RuleEvaluationBatch,
    RuleJudgment,
    RuleProfile,
)
from signal_diag.tools.evidence import Evidence, EvidenceValue

_COMPARATORS: dict[str, Callable[[EvidenceValue, EvidenceValue], bool]] = {
    "lt": operator.lt,
    "lte": operator.le,
    "gt": operator.gt,
    "gte": operator.ge,
    "eq": operator.eq,
    "neq": operator.ne,
}


def _same_scalar_category(left: EvidenceValue, right: EvidenceValue) -> bool:
    return type(left) is type(right) and type(left) in {bool, int, float, str}


def _unit_compatible(rule_unit: str | None, evidence_unit: str | None) -> bool:
    if rule_unit is None:
        return True
    return rule_unit == evidence_unit


def _trace_id(prefix: str, payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"


def _matching_evidence(
    rule: RuleDefinition,
    evidence: Sequence[Evidence],
    *,
    evidence_filter: frozenset[str] | None,
) -> list[Evidence]:
    matches: list[Evidence] = []
    for item in evidence:
        if evidence_filter is not None and item.evidence_id not in evidence_filter:
            continue
        if item.source_tool == rule.source_tool and item.metric == rule.metric:
            matches.append(item)
    return matches


def evaluate_one(
    *,
    rule: RuleDefinition,
    evidence: Evidence,
    profile: RuleProfile,
    match_ordinal: int = 0,
) -> RuleEvaluation:
    base_payload = {
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "rule_id": rule.rule_id,
        "metric": rule.metric,
        "source_tool": rule.source_tool,
        "comparator": rule.comparator,
        "threshold": rule.threshold,
        "rule_unit": rule.unit,
        "evidence_id": evidence.evidence_id,
        "evidence_value": evidence.value,
        "evidence_validity": evidence.validity,
        "evidence_unit": evidence.unit,
        "match_ordinal": match_ordinal,
    }
    if evidence.validity != "valid":
        return RuleEvaluation(
            evaluation_id=_trace_id("ruleval_", {**base_payload, "judgment": "not_applicable"}),
            rule_id=rule.rule_id,
            judgment="not_applicable",
            observed_value=None,
            comparator=rule.comparator,
            threshold=rule.threshold,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            evidence_refs=(evidence.evidence_id,),
            reason="evidence is not applicable",
        )
    if not _same_scalar_category(evidence.value, rule.threshold):
        return RuleEvaluation(
            evaluation_id=_trace_id("ruleval_", {**base_payload, "judgment": "not_applicable"}),
            rule_id=rule.rule_id,
            judgment="not_applicable",
            observed_value=None,
            comparator=rule.comparator,
            threshold=rule.threshold,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            evidence_refs=(evidence.evidence_id,),
            reason="observed value type is incompatible with rule threshold",
        )
    if not _unit_compatible(rule.unit, evidence.unit):
        return RuleEvaluation(
            evaluation_id=_trace_id("ruleval_", {**base_payload, "judgment": "not_applicable"}),
            rule_id=rule.rule_id,
            judgment="not_applicable",
            observed_value=None,
            comparator=rule.comparator,
            threshold=rule.threshold,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            evidence_refs=(evidence.evidence_id,),
            reason="evidence unit does not match rule unit constraint",
        )
    comparator_fn = _COMPARATORS[rule.comparator]
    passed = comparator_fn(evidence.value, rule.threshold)
    judgment: RuleJudgment = "pass" if passed else "fail"
    return RuleEvaluation(
        evaluation_id=_trace_id("ruleval_", {**base_payload, "judgment": judgment}),
        rule_id=rule.rule_id,
        judgment=judgment,
        observed_value=evidence.value,
        comparator=rule.comparator,
        threshold=rule.threshold,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        evidence_refs=(evidence.evidence_id,),
        reason=None,
    )


def _no_match_evaluation(rule: RuleDefinition, profile: RuleProfile) -> RuleEvaluation:
    payload = {
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "rule_id": rule.rule_id,
        "metric": rule.metric,
        "source_tool": rule.source_tool,
        "no_match": True,
    }
    return RuleEvaluation(
        evaluation_id=_trace_id("ruleval_", payload),
        rule_id=rule.rule_id,
        judgment="not_applicable",
        observed_value=None,
        comparator=rule.comparator,
        threshold=rule.threshold,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        evidence_refs=(),
        reason="no matching evidence for rule metric",
    )


class RuleEngine:
    def evaluate_profile(
        self,
        profile: RuleProfile,
        evidence: Sequence[Evidence],
        *,
        evidence_filter: frozenset[str] | None = None,
    ) -> RuleEvaluationBatch:
        evaluations: list[RuleEvaluation] = []
        for rule in profile.rules:
            matches = _matching_evidence(
                rule,
                evidence,
                evidence_filter=evidence_filter,
            )
            if not matches:
                evaluations.append(_no_match_evaluation(rule, profile))
                continue
            for ordinal, item in enumerate(matches):
                evaluations.append(
                    evaluate_one(
                        rule=rule,
                        evidence=item,
                        profile=profile,
                        match_ordinal=ordinal,
                    )
                )
        batch_payload: dict[str, object] = {
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "evaluation_ids": [item.evaluation_id for item in evaluations],
        }
        return RuleEvaluationBatch(
            batch_id=_trace_id("rulebatch_", batch_payload),
            profile_id=profile.profile_id,
            profile_version=profile.version,
            evaluations=tuple(evaluations),
        )
