"""Deterministic diagnosis engine for the live product (D052 phase 1, D053).

The engine implements :class:`PlannerModel` and runs inside the unchanged
:class:`DistortionDiagnosisRuntime`, so every Tool call, automatic rule closure,
Evidence reference and finish validation is the same as for the LLM planner.
It never calls a model: each mode has a fixed whole-file Tool sequence, and the
outcome follows only from the versioned rule evaluations the runtime produced.
"""

from __future__ import annotations

from collections.abc import Iterable

from signal_diag.rules.models import RuleEvaluation
from signal_diag.tools.contracts import (
    ClippingInput,
    ContextualDistortionInput,
    HarmonicDistortionInput,
)
from signal_diag.tools.evidence import Evidence

from .models import (
    AgentDecision,
    AnalyzeContextualDistortionCall,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    FinishDecision,
    PlannerContext,
    RetrieveKnowledgeDecision,
    TaskAssessment,
    ToolInvocation,
)

ENGINE_VERSION = "s1-engine-1.0"

_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective=f"Deterministic distortion diagnosis ({ENGINE_VERSION}).",
)
_KNOWLEDGE_TAGS = {
    "clipping": ("clipping",),
    "harmonic_distortion": ("harmonic-distortion",),
}
_SINGLE_CLIPPING_RULES = ("rule_clipping_ratio_acceptable", "rule_flat_top_absent")
_TEST_CLIPPING_RULES = ("rule_test_clipping_ratio_acceptable", "rule_test_flat_top_absent")
_PAIRED_GATE = (
    "rule_contextual_analysis_valid",
    "rule_contextual_f0_compatible",
    "rule_reference_clipping_ratio_acceptable",
    "rule_reference_flat_top_absent",
)
_NOMINAL_GATE = ("rule_contextual_analysis_valid", "rule_contextual_f0_compatible")
_SINGLE_NO_FAULT_RULES = (
    *_SINGLE_CLIPPING_RULES,
    "rule_harmonic_analysis_valid",
    "rule_thd_acceptable",
)
_PAIRED_NO_FAULT_RULES = (
    *_TEST_CLIPPING_RULES,
    *_PAIRED_GATE,
    "rule_even_harmonic_growth_acceptable",
)
_NOMINAL_NO_FAULT_RULES = (*_TEST_CLIPPING_RULES, *_NOMINAL_GATE, "rule_nominal_thd_acceptable")


def _tool_plan(mode: str) -> tuple[ToolInvocation, ...]:
    if mode == "single_signal":
        return (
            DetectClippingCall(args=ClippingInput()),
            AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
        )
    return (AnalyzeContextualDistortionCall(args=ContextualDistortionInput()),)


class _Facts:
    """Latest Evidence by metric and rule evaluation by rule ID for one run."""

    def __init__(self, context: PlannerContext) -> None:
        self.evidence: dict[str, Evidence] = {}
        for item in context.evidence:
            self.evidence[item.metric] = item
        # A later batch of the same profile re-evaluates every rule; rules without
        # matching Evidence there must not hide an earlier pass or fail.
        self.rules: dict[str, RuleEvaluation] = {}
        for batch in context.rule_evaluation_batches:
            for evaluation in batch.evaluations:
                if evaluation.judgment in ("pass", "fail") or evaluation.rule_id not in self.rules:
                    self.rules[evaluation.rule_id] = evaluation

    def metric_is(self, metric: str, value: object) -> Evidence | None:
        item = self.evidence.get(metric)
        if item is None or item.validity != "valid" or item.value != value:
            return None
        return item

    def judged(self, rule_id: str, judgment: str) -> RuleEvaluation | None:
        evaluation = self.rules.get(rule_id)
        if evaluation is None or evaluation.judgment != judgment:
            return None
        return evaluation

    def all_judged(self, rule_ids: Iterable[str], judgment: str) -> list[RuleEvaluation] | None:
        found = [self.judged(rule_id, judgment) for rule_id in rule_ids]
        if any(item is None for item in found):
            return None
        return [item for item in found if item is not None]


def _refs(
    evidence: Iterable[Evidence], evaluations: Iterable[RuleEvaluation]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    cited = list(evaluations)
    evidence_ids = [item.evidence_id for item in evidence]
    evidence_ids.extend(ref for item in cited for ref in item.evidence_refs)
    return (
        tuple(dict.fromkeys(evidence_ids)),
        tuple(dict.fromkeys(item.evaluation_id for item in cited)),
    )


def _claim(
    run_id: str,
    fault_type: str,
    statement: str,
    evidence: Iterable[Evidence],
    evaluations: Iterable[RuleEvaluation],
    knowledge_refs: tuple[str, ...] = (),
) -> DiagnosisClaim:
    evidence_refs, rule_refs = _refs(evidence, evaluations)
    return DiagnosisClaim(
        claim_id=f"claim_{run_id.removeprefix('run_')}_{fault_type}",
        fault_type=fault_type,  # type: ignore[arg-type]
        statement=statement,
        evidence_refs=evidence_refs,
        rule_refs=rule_refs,
        knowledge_refs=knowledge_refs,
    )


def _clipping_support(facts: _Facts, mode: str) -> tuple[list[Evidence], list[RuleEvaluation]] | None:
    rules: tuple[str, ...]
    if mode == "single_signal":
        mechanism = facts.metric_is("clipping_mechanism", True) or facts.metric_is(
            "flat_top_detected", True
        )
        rules = _SINGLE_CLIPPING_RULES
    else:
        mechanism = facts.metric_is("test_clipping_mechanism", True)
        rules = _TEST_CLIPPING_RULES
    failing = [item for item in (facts.judged(rule, "fail") for rule in rules) if item]
    if mechanism is None or not failing:
        return None
    return [mechanism], failing


def _harmonic_support(facts: _Facts, mode: str) -> tuple[list[Evidence], list[RuleEvaluation]] | None:
    if mode == "paired_reference":
        gate = facts.all_judged(_PAIRED_GATE, "pass")
        growth = facts.judged("rule_even_harmonic_growth_acceptable", "fail")
        if gate is None or growth is None:
            return None
        return [], [*gate, growth]
    if mode == "nominal_single_tone":
        gate = facts.all_judged(_NOMINAL_GATE, "pass")
        thd = facts.judged("rule_nominal_thd_acceptable", "fail")
        series = facts.metric_is("test_series_kind", "even_order_present")
        if gate is None or thd is None or series is None:
            return None
        return [series], [*gate, thd]
    return None  # D037: single-file mode never attributes harmonic distortion.


def _no_fault_support(facts: _Facts, mode: str) -> tuple[list[Evidence], list[RuleEvaluation]] | None:
    rules: tuple[str, ...]
    if mode == "single_signal":
        mechanism = facts.metric_is("clipping_mechanism", False)
        rules = _SINGLE_NO_FAULT_RULES
    else:
        mechanism = facts.metric_is("test_clipping_mechanism", False)
        rules = _PAIRED_NO_FAULT_RULES if mode == "paired_reference" else _NOMINAL_NO_FAULT_RULES
    passing = facts.all_judged(rules, "pass")
    if mechanism is None or passing is None:
        return None
    return [mechanism], passing


class DeterministicDiagnosisEngine:
    """Fixed Tool plan per mode; verdicts only from the run's rule evaluations."""

    engine_version = ENGINE_VERSION

    async def decide(self, context: PlannerContext) -> AgentDecision:
        mode = context.stimulus_context.mode if context.stimulus_context else "single_signal"
        plan = _tool_plan(mode)
        done = len(context.tool_history)
        if done < len(plan):
            call = plan[done]
            return CallToolDecision(
                task_assessment=_ASSESSMENT if done == 0 else None,
                call=call,
                purpose=f"{ENGINE_VERSION} fixed {mode} plan step {done + 1}/{len(plan)}",
            )
        facts = _Facts(context)
        supports = {
            "clipping": _clipping_support(facts, mode),
            "harmonic_distortion": _harmonic_support(facts, mode),
        }
        supported = [fault for fault, support in supports.items() if support is not None]
        retrieved = {
            tag
            for retrieval in context.knowledge_retrievals
            for tag in retrieval.query_tags
        }
        for fault in supported:
            tags = _KNOWLEDGE_TAGS[fault]
            if not set(tags) <= retrieved:
                return RetrieveKnowledgeDecision(
                    query_text=fault.replace("_", " "),
                    tags=tags,
                    purpose=f"{ENGINE_VERSION} explanation for supported {fault}",
                )
        return self._finish(context, facts, mode, supports)

    def _finish(
        self,
        context: PlannerContext,
        facts: _Facts,
        mode: str,
        supports: dict[str, tuple[list[Evidence], list[RuleEvaluation]] | None],
    ) -> FinishDecision:
        knowledge = {
            tag: retrieval.retrieval_id
            for retrieval in context.knowledge_retrievals
            for tag in retrieval.query_tags
        }
        claims: list[DiagnosisClaim] = []
        for fault, support in supports.items():
            if support is None:
                continue
            evidence, evaluations = support
            refs = tuple(
                knowledge[tag] for tag in _KNOWLEDGE_TAGS[fault] if tag in knowledge
            )
            claims.append(
                _claim(
                    context.run_id,
                    fault,
                    _STATEMENTS[fault],
                    evidence,
                    evaluations,
                    refs,
                )
            )
        if claims:
            return FinishDecision(
                task_assessment=None,
                outcome="supported_fault",
                claims=tuple(claims),
                confidence_label="high",
                limitations=_mode_limitations(mode),
            )
        no_fault = _no_fault_support(facts, mode)
        if no_fault is not None:
            evidence, evaluations = no_fault
            return FinishDecision(
                outcome="no_supported_fault",
                claims=(
                    _claim(
                        context.run_id,
                        "no_supported_fault",
                        "Every required rule passed; no supported fault was found.",
                        evidence,
                        evaluations,
                    ),
                ),
                confidence_label="medium",
                limitations=_mode_limitations(mode),
            )
        grounding = [item for item in facts.rules.values() if item.judgment != "pass"]
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                _claim(
                    context.run_id,
                    "inconclusive",
                    "The rules neither support a fault nor confirm that none is present.",
                    (),
                    grounding or list(facts.rules.values()),
                ),
            )
            if facts.rules
            else (),
            confidence_label="low",
            limitations=(
                *_mode_limitations(mode),
                "Deterministic rules did not reach a supported or no-fault verdict.",
            ),
        )


_STATEMENTS = {
    "clipping": "Clipping is supported by its mechanism Evidence and a failing clipping rule.",
    "harmonic_distortion": (
        "Harmonic distortion is supported by the mode's contextual gate and a failing "
        "harmonic rule."
    ),
}


def _mode_limitations(mode: str) -> tuple[str, ...]:
    if mode == "single_signal":
        return (
            (
                "Single-file mode: harmonic distortion is not attributed without a "
                "reference or declared fundamental (D037)."
            ),
        )
    return ()


__all__ = ["ENGINE_VERSION", "DeterministicDiagnosisEngine"]
