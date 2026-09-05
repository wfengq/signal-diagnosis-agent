"""Truth-free deterministic contextual baseline."""

from __future__ import annotations

import hashlib
import json
from typing import TypeVar, cast

from signal_diag.agent.models import (
    DiagnosisClaim,
    Observation,
    ToolHistoryEntry,
    ToolOutput,
)
from signal_diag.evaluation.contextual.models import ContextualBaselineRequest
from signal_diag.evaluation.models import BaselineDiagnosis, BaselineRunResult
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.models import RuleEvaluation, RuleProfileLoader
from signal_diag.signal.repository import SignalRepository
from signal_diag.tools.contracts import (
    ClippingInput,
    ContextualDistortionInput,
    HarmonicDistortionInput,
)
from signal_diag.tools.results import ToolResult
from signal_diag.tools.service import SignalToolService

_S1_PROFILE = "profile_s1_distortion"
_CONTEXTUAL_PROFILE = "profile_s1_contextual_comparison"
_SUBSTANTIAL_CLIPPING_RULES = frozenset({"rule_clipping_ratio_acceptable", "rule_flat_top_absent"})
_PAIRED_BASE_RULES = (
    ("rule_contextual_analysis_valid", "pass"),
    ("rule_contextual_f0_compatible", "pass"),
    ("rule_reference_clipping_ratio_acceptable", "pass"),
    ("rule_reference_flat_top_absent", "pass"),
)
_PAIRED_HARMONIC_RULES = _PAIRED_BASE_RULES + (("rule_even_harmonic_growth_acceptable", "fail"),)
_PAIRED_NO_FAULT_RULES = _PAIRED_BASE_RULES + (("rule_even_harmonic_growth_acceptable", "pass"),)
_NOMINAL_BASE_RULES = (("rule_contextual_analysis_valid", "pass"), ("rule_contextual_f0_compatible", "pass"))
_NOMINAL_HARMONIC_RULES = _NOMINAL_BASE_RULES + (("rule_nominal_thd_acceptable", "fail"),)
_NOMINAL_NO_FAULT_RULES = _NOMINAL_BASE_RULES + (("rule_nominal_thd_acceptable", "pass"),)
_SINGLE_NO_FAULT_RULES = (("rule_harmonic_analysis_valid", "pass"), ("rule_thd_acceptable", "pass"))
_CLIPPING_NO_FAULT_RULES = (("rule_clipping_ratio_acceptable", "pass"), ("rule_flat_top_absent", "pass"))
_INSUFFICIENT = "deterministic evidence does not satisfy a supported causal gate"
TOutput = TypeVar("TOutput", bound=ToolOutput)
ToolArgs = ClippingInput | HarmonicDistortionInput | ContextualDistortionInput


def require_baseline_request(value: object) -> ContextualBaselineRequest:
    """Reject manifest cases at the execution boundary."""
    if not isinstance(value, ContextualBaselineRequest):
        raise TypeError("fixed pipeline requires ContextualBaselineRequest")
    return value


def _stable_id(prefix: str, payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _record_tool(result: ToolResult[TOutput], args: ToolArgs, purpose: str) -> tuple[Observation, ToolHistoryEntry]:
    normalized = args.model_dump(mode="json")
    observation = Observation(
        observation_id=_stable_id("obs_", {"call_id": result.call_id, "tool_name": result.tool_name}),
        call_id=result.call_id,
        tool_name=result.tool_name,
        normalized_arguments=normalized,
        purpose=purpose,
        status=result.status,
        result=cast(ToolOutput | None, result.result),
        evidence_refs=tuple(item.evidence_id for item in result.evidence),
        warnings=result.warnings,
        error_message=result.error_message,
    )
    history = ToolHistoryEntry(
        call_id=result.call_id,
        tool_name=result.tool_name,
        normalized_arguments=normalized,
        purpose=purpose,
        status=result.status,
    )
    return observation, history


def _matching(evaluations: tuple[RuleEvaluation, ...], requirements: tuple[tuple[str, str], ...]) -> list[RuleEvaluation] | None:
    selected: list[RuleEvaluation] = []
    for rule_id, judgment in requirements:
        item = next((row for row in evaluations if row.rule_id == rule_id and row.judgment == judgment), None)
        if item is None:
            return None
        selected.append(item)
    return selected


def _claim(
    *,
    run_id: str,
    fault_type: str,
    statement: str,
    rules: list[RuleEvaluation],
    extra_evidence_refs: tuple[str, ...] = (),
) -> DiagnosisClaim:
    evidence_refs: list[str] = list(extra_evidence_refs)
    for item in rules:
        for ref in item.evidence_refs:
            if ref not in evidence_refs:
                evidence_refs.append(ref)
    return DiagnosisClaim(
        claim_id=_stable_id("claim_", {"run_id": run_id, "fault_type": fault_type, "evidence_refs": evidence_refs, "rule_refs": [item.evaluation_id for item in rules]}),
        fault_type=fault_type,  # type: ignore[arg-type]
        statement=statement,
        evidence_refs=tuple(evidence_refs),
        rule_refs=tuple(item.evaluation_id for item in rules),
    )


class ContextualFixedPipelineBaseline:
    """Execute fixed Tools and rules without planner or truth metadata."""

    def __init__(self, *, repository: SignalRepository, tool_service: SignalToolService, rule_engine: RuleEngine, profile_loader: RuleProfileLoader) -> None:
        self._repository = repository
        self._tools = tool_service
        self._rules = rule_engine
        self._profiles = profile_loader

    async def run(self, request: ContextualBaselineRequest) -> BaselineRunResult:
        request = require_baseline_request(request)
        context = request.stimulus_context
        self._repository.get(request.signal_id)
        clipping_args = ClippingInput()
        clipping = self._tools.detect_clipping(request.signal_id, clipping_args)
        clip_observation, clip_history = _record_tool(clipping, clipping_args, "fixed contextual clipping analysis")
        clip_batch = self._rules.evaluate_profile(self._profiles.load(_S1_PROFILE), clipping.evidence)

        if context.mode == "single_signal":
            harmonic_args = HarmonicDistortionInput()
            harmonic_result = self._tools.analyze_harmonic_distortion(
                request.signal_id, harmonic_args
            )
            analysis_args: ToolArgs = harmonic_args
            analysis = cast(ToolResult[ToolOutput], harmonic_result)
            analysis_profile = _S1_PROFILE
            purpose = "fixed absolute harmonic analysis"
        else:
            contextual_args = ContextualDistortionInput()
            contextual_result = self._tools.analyze_contextual_distortion(
                context, contextual_args
            )
            analysis_args = contextual_args
            analysis = cast(ToolResult[ToolOutput], contextual_result)
            analysis_profile = _CONTEXTUAL_PROFILE
            purpose = "fixed contextual distortion analysis"
        analysis_observation, analysis_history = _record_tool(analysis, analysis_args, purpose)
        analysis_batch = self._rules.evaluate_profile(self._profiles.load(analysis_profile), analysis.evidence)
        evidence = tuple(clipping.evidence) + tuple(analysis.evidence)
        batches = (clip_batch, analysis_batch)
        evaluations = tuple(item for batch in batches for item in batch.evaluations)
        run_id = _stable_id("baseline_", {"case_id": request.case_id, "signal_id": request.signal_id, "context": context.model_dump(mode="json"), "evidence_ids": [item.evidence_id for item in evidence], "batch_ids": [item.batch_id for item in batches]})

        mechanism = next((item for item in clipping.evidence if item.metric == "clipping_mechanism" and item.value is True), None)
        substantial = [item for item in clip_batch.evaluations if item.rule_id in _SUBSTANTIAL_CLIPPING_RULES and item.judgment == "fail"]
        clipping_supported = mechanism is not None and bool(substantial)
        harmonic_rules: list[RuleEvaluation] | None = None
        if context.mode == "paired_reference":
            harmonic_rules = _matching(evaluations, _PAIRED_HARMONIC_RULES)
        elif context.mode == "nominal_single_tone":
            candidate = _matching(evaluations, _NOMINAL_HARMONIC_RULES)
            even_order = any(item.metric == "test_series_kind" and item.value == "even_order_present" and item.validity == "valid" for item in analysis.evidence)
            if candidate is not None and even_order:
                harmonic_rules = candidate

        claims: list[DiagnosisClaim] = []
        if clipping_supported:
            mechanism_rules = [item for item in clip_batch.evaluations if mechanism is not None and mechanism.evidence_id in item.evidence_refs]
            claims.append(_claim(run_id=run_id, fault_type="clipping", statement="Clipping is supported by mechanism Evidence and a substantial rule failure.", rules=mechanism_rules + substantial, extra_evidence_refs=(mechanism.evidence_id,) if mechanism is not None else ()))
        if harmonic_rules is not None:
            even_order_refs = tuple(item.evidence_id for item in analysis.evidence if item.metric == "test_series_kind" and item.value == "even_order_present")
            claims.append(_claim(run_id=run_id, fault_type="harmonic_distortion", statement="Harmonic distortion is supported by the mode-specific contextual rule gate.", rules=harmonic_rules, extra_evidence_refs=even_order_refs))

        limitations: tuple[str, ...] = ()
        if harmonic_rules is not None and context.mode == "nominal_single_tone":
            limitations = (
                "harmonic attribution is conditional on the declared single-tone stimulus",
            )
        if claims:
            outcome, confidence, status, completion = "supported_fault", ("high" if len(claims) == 2 else "medium"), "success", "baseline_completed"
        else:
            clip_clean = _matching(evaluations, _CLIPPING_NO_FAULT_RULES)
            mode_clean = _matching(evaluations, _PAIRED_NO_FAULT_RULES if context.mode == "paired_reference" else _NOMINAL_NO_FAULT_RULES if context.mode == "nominal_single_tone" else _SINGLE_NO_FAULT_RULES)
            false_mechanism = next((item for item in clipping.evidence if item.metric == "clipping_mechanism" and item.value is False), None)
            if clip_clean is not None and mode_clean is not None and false_mechanism is not None:
                claims.append(_claim(run_id=run_id, fault_type="no_supported_fault", statement="The fixed Tools and all applicable frozen rules indicate no supported fault.", rules=clip_clean + mode_clean, extra_evidence_refs=(false_mechanism.evidence_id,)))
                outcome, confidence, status, completion = "no_supported_fault", "medium", "success", "baseline_completed"
            else:
                cited = [item for item in evaluations if item.judgment == "not_applicable"] or list(evaluations)
                claims.append(_claim(run_id=run_id, fault_type="inconclusive", statement="The fixed evidence is insufficient for a supported causal diagnosis.", rules=cited))
                outcome, confidence, status, completion = "inconclusive", "low", "inconclusive", "insufficient_evidence"
                limitations = (_INSUFFICIENT,)

        diagnosis = BaselineDiagnosis(run_id=run_id, outcome=outcome, claims=tuple(claims), confidence_label=confidence, limitations=limitations, tool_call_count=2, rule_evaluation_batches=batches)  # type: ignore[arg-type]
        return BaselineRunResult(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            diagnosis=diagnosis,
            observations=(clip_observation, analysis_observation),
            evidence=evidence,
            tool_history=(clip_history, analysis_history),
            completion_reason=completion,  # type: ignore[arg-type]
            warnings=clipping.warnings + analysis.warnings,
            errors=tuple(message for message in (clipping.error_message, analysis.error_message) if message is not None),
            rule_evaluation_batches=batches,
        )
