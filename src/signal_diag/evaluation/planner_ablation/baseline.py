"""Study fixed-pipeline baseline with matched §19 gates (Option C single_signal)."""

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
from signal_diag.evaluation.models import BaselineDiagnosis, BaselineRunResult
from signal_diag.evaluation.planner_ablation.models import (
    PlannerAblationBaselineRequest,
)
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
_CONTEXTUAL_PROFILE = "profile_s1_contextual_comparison_v9_10"
_SUBSTANTIAL_LEGACY_CLIPPING_RULES = frozenset(
    {"rule_clipping_ratio_acceptable", "rule_flat_top_absent"}
)
_SUBSTANTIAL_TEST_CLIPPING_RULES = frozenset(
    {"rule_test_clipping_ratio_acceptable", "rule_test_flat_top_absent"}
)
_PAIRED_BASE_RULES = (
    ("rule_contextual_analysis_valid", "pass"),
    ("rule_contextual_f0_compatible", "pass"),
    ("rule_reference_clipping_ratio_acceptable", "pass"),
    ("rule_reference_flat_top_absent", "pass"),
)
_PAIRED_HARMONIC_RULES = _PAIRED_BASE_RULES + (("rule_even_harmonic_growth_acceptable", "fail"),)
_PAIRED_NO_FAULT_RULES = _PAIRED_BASE_RULES + (("rule_even_harmonic_growth_acceptable", "pass"),)
_SINGLE_NO_FAULT_RULES = (
    ("rule_harmonic_analysis_valid", "pass"),
    ("rule_thd_acceptable", "pass"),
)
_CLIPPING_NO_FAULT_RULES = (
    ("rule_clipping_ratio_acceptable", "pass"),
    ("rule_flat_top_absent", "pass"),
)
_INSUFFICIENT = "deterministic evidence does not satisfy a supported causal gate"
TOutput = TypeVar("TOutput", bound=ToolOutput)
ToolArgs = ClippingInput | HarmonicDistortionInput | ContextualDistortionInput


def require_baseline_request(value: object) -> PlannerAblationBaselineRequest:
    if not isinstance(value, PlannerAblationBaselineRequest):
        raise TypeError("study fixed pipeline requires PlannerAblationBaselineRequest")
    return value


def single_signal_clipping_supported(
    clipping_evidence: tuple[object, ...],
    clip_evaluations: tuple[RuleEvaluation, ...],
) -> bool:
    """OQ-014 Option C gate for study baseline (§16 / T-CX277)."""
    mechanism = any(
        getattr(item, "metric", None) == "clipping_mechanism"
        and getattr(item, "value", None) is True
        and getattr(item, "validity", None) == "valid"
        for item in clipping_evidence
    )
    flat_top = any(
        getattr(item, "metric", None) == "flat_top_detected"
        and getattr(item, "value", None) is True
        and getattr(item, "validity", None) == "valid"
        for item in clipping_evidence
    )
    substantial = [
        item
        for item in clip_evaluations
        if item.rule_id in _SUBSTANTIAL_LEGACY_CLIPPING_RULES and item.judgment == "fail"
    ]
    if not substantial:
        return False
    if mechanism:
        return True
    return flat_top


def paired_clipping_supported(
    analysis_evidence: tuple[object, ...],
    evaluations: tuple[RuleEvaluation, ...],
) -> bool:
    """Contextual test family only; no legacy family mixing (T-CX278)."""
    test_mechanism = any(
        getattr(item, "metric", None) == "test_clipping_mechanism"
        and getattr(item, "value", None) is True
        and getattr(item, "validity", None) == "valid"
        for item in analysis_evidence
    )
    if not test_mechanism:
        return False
    legacy_mechanism = any(
        getattr(item, "metric", None) == "clipping_mechanism"
        and getattr(item, "value", None) is True
        for item in analysis_evidence
    )
    substantial_test = [
        item
        for item in evaluations
        if item.rule_id in _SUBSTANTIAL_TEST_CLIPPING_RULES and item.judgment == "fail"
    ]
    if legacy_mechanism and not substantial_test:
        return False
    return bool(substantial_test)


def _stable_id(prefix: str, payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _record_tool(
    result: ToolResult[TOutput],
    args: ToolArgs,
    purpose: str,
) -> tuple[Observation, ToolHistoryEntry]:
    normalized = args.model_dump(mode="json")
    observation = Observation(
        observation_id=_stable_id(
            "obs_",
            {"call_id": result.call_id, "tool_name": result.tool_name},
        ),
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


def _matching(
    evaluations: tuple[RuleEvaluation, ...],
    requirements: tuple[tuple[str, str], ...],
) -> list[RuleEvaluation] | None:
    selected: list[RuleEvaluation] = []
    for rule_id, judgment in requirements:
        item = next(
            (row for row in evaluations if row.rule_id == rule_id and row.judgment == judgment),
            None,
        )
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
        claim_id=_stable_id(
            "claim_",
            {
                "run_id": run_id,
                "fault_type": fault_type,
                "evidence_refs": evidence_refs,
                "rule_refs": [item.evaluation_id for item in rules],
            },
        ),
        fault_type=fault_type,  # type: ignore[arg-type]
        statement=statement,
        evidence_refs=tuple(evidence_refs),
        rule_refs=tuple(item.evaluation_id for item in rules),
    )


class PlannerAblationFixedPipelineBaseline:
    """Truth-free study baseline; historical contextual baseline stays unchanged."""

    def __init__(
        self,
        *,
        repository: SignalRepository,
        tool_service: SignalToolService,
        rule_engine: RuleEngine,
        profile_loader: RuleProfileLoader,
    ) -> None:
        self._repository = repository
        self._tools = tool_service
        self._rules = rule_engine
        self._profiles = profile_loader

    async def run(self, request: PlannerAblationBaselineRequest) -> BaselineRunResult:
        request = require_baseline_request(request)
        context = request.stimulus_context
        self._repository.get(request.signal_id)
        clipping_args = ClippingInput()
        clipping = self._tools.detect_clipping(request.signal_id, clipping_args)
        clip_observation, clip_history = _record_tool(
            clipping, clipping_args, "study fixed clipping analysis"
        )
        clip_batch = self._rules.evaluate_profile(
            self._profiles.load(_S1_PROFILE), clipping.evidence
        )

        if context.mode == "single_signal":
            harmonic_args = HarmonicDistortionInput()
            harmonic_result = self._tools.analyze_harmonic_distortion(
                request.signal_id, harmonic_args
            )
            analysis_args: ToolArgs = harmonic_args
            analysis = cast(ToolResult[ToolOutput], harmonic_result)
            analysis_profile = _S1_PROFILE
            purpose = "study fixed absolute harmonic analysis"
        else:
            contextual_args = ContextualDistortionInput()
            contextual_result = self._tools.analyze_contextual_distortion(
                context, contextual_args
            )
            analysis_args = contextual_args
            analysis = cast(ToolResult[ToolOutput], contextual_result)
            analysis_profile = _CONTEXTUAL_PROFILE
            purpose = "study fixed contextual distortion analysis"
        analysis_observation, analysis_history = _record_tool(analysis, analysis_args, purpose)
        analysis_batch = self._rules.evaluate_profile(
            self._profiles.load(analysis_profile), analysis.evidence
        )
        evidence = tuple(clipping.evidence) + tuple(analysis.evidence)
        batches = (clip_batch, analysis_batch)
        evaluations = tuple(item for batch in batches for item in batch.evaluations)
        run_id = _stable_id(
            "baseline_",
            {
                "case_id": request.case_id,
                "signal_id": request.signal_id,
                "context": context.model_dump(mode="json"),
                "evidence_ids": [item.evidence_id for item in evidence],
                "batch_ids": [item.batch_id for item in batches],
            },
        )

        claims: list[DiagnosisClaim] = []
        if context.mode == "single_signal":
            clipping_supported = single_signal_clipping_supported(
                clipping.evidence, clip_batch.evaluations
            )
            if clipping_supported:
                mechanism = next(
                    (
                        item
                        for item in clipping.evidence
                        if item.metric == "clipping_mechanism" and item.value is True
                    ),
                    None,
                )
                flat_top = next(
                    (
                        item
                        for item in clipping.evidence
                        if item.metric == "flat_top_detected" and item.value is True
                    ),
                    None,
                )
                substantial = [
                    item
                    for item in clip_batch.evaluations
                    if item.rule_id in _SUBSTANTIAL_LEGACY_CLIPPING_RULES
                    and item.judgment == "fail"
                ]
                presence_rules = [
                    item
                    for item in clip_batch.evaluations
                    if mechanism is not None and mechanism.evidence_id in item.evidence_refs
                ]
                extra_refs: tuple[str, ...] = ()
                if mechanism is not None:
                    extra_refs = (mechanism.evidence_id,)
                elif flat_top is not None:
                    extra_refs = (flat_top.evidence_id,)
                claims.append(
                    _claim(
                        run_id=run_id,
                        fault_type="clipping",
                        statement=(
                            "Clipping is supported by study single_signal Option C gates."
                        ),
                        rules=presence_rules + substantial,
                        extra_evidence_refs=extra_refs,
                    )
                )
        else:
            if paired_clipping_supported(analysis.evidence, evaluations):
                test_mechanism = next(
                    item
                    for item in analysis.evidence
                    if item.metric == "test_clipping_mechanism" and item.value is True
                )
                substantial = [
                    item
                    for item in evaluations
                    if item.rule_id in _SUBSTANTIAL_TEST_CLIPPING_RULES
                    and item.judgment == "fail"
                ]
                claims.append(
                    _claim(
                        run_id=run_id,
                        fault_type="clipping",
                        statement=(
                            "Clipping is supported by contextual test-family Evidence."
                        ),
                        rules=substantial,
                        extra_evidence_refs=(test_mechanism.evidence_id,),
                    )
                )

        harmonic_rules: list[RuleEvaluation] | None = None
        if context.mode == "paired_reference":
            harmonic_rules = _matching(evaluations, _PAIRED_HARMONIC_RULES)

        if harmonic_rules is not None:
            even_order_refs = tuple(
                item.evidence_id
                for item in analysis.evidence
                if item.metric == "test_series_kind" and item.value == "even_order_present"
            )
            claims.append(
                _claim(
                    run_id=run_id,
                    fault_type="harmonic_distortion",
                    statement="Harmonic distortion is supported by the contextual harmonic gate.",
                    rules=harmonic_rules,
                    extra_evidence_refs=even_order_refs,
                )
            )

        limitations: tuple[str, ...] = ()
        if claims:
            outcome, confidence, status, completion = (
                "supported_fault",
                ("high" if len(claims) == 2 else "medium"),
                "success",
                "baseline_completed",
            )
        else:
            if context.mode == "paired_reference":
                clip_clean = _matching(
                    evaluations,
                    (
                        ("rule_test_clipping_ratio_acceptable", "pass"),
                        ("rule_test_flat_top_absent", "pass"),
                    ),
                )
                false_test_mechanism = next(
                    (
                        item
                        for item in analysis.evidence
                        if item.metric == "test_clipping_mechanism" and item.value is False
                    ),
                    None,
                )
                mode_clean = _matching(evaluations, _PAIRED_NO_FAULT_RULES)
                if (
                    clip_clean is not None
                    and mode_clean is not None
                    and false_test_mechanism is not None
                ):
                    claims.append(
                        _claim(
                            run_id=run_id,
                            fault_type="no_supported_fault",
                            statement="Contextual test clean family indicates no supported fault.",
                            rules=clip_clean + mode_clean,
                            extra_evidence_refs=(false_test_mechanism.evidence_id,),
                        )
                    )
                    outcome, confidence, status, completion = (
                        "no_supported_fault",
                        "medium",
                        "success",
                        "baseline_completed",
                    )
                else:
                    cited = [
                        item for item in evaluations if item.judgment == "not_applicable"
                    ] or list(evaluations)
                    claims.append(
                        _claim(
                            run_id=run_id,
                            fault_type="inconclusive",
                            statement="Insufficient contextual evidence for a supported diagnosis.",
                            rules=cited,
                        )
                    )
                    outcome, confidence, status, completion = (
                        "inconclusive",
                        "low",
                        "inconclusive",
                        "insufficient_evidence",
                    )
                    limitations = (_INSUFFICIENT,)
            else:
                clip_clean = _matching(evaluations, _CLIPPING_NO_FAULT_RULES)
                mode_clean = _matching(evaluations, _SINGLE_NO_FAULT_RULES)
                false_mechanism = next(
                    (
                        item
                        for item in clipping.evidence
                        if item.metric == "clipping_mechanism" and item.value is False
                    ),
                    None,
                )
                if clip_clean is not None and mode_clean is not None and false_mechanism is not None:
                    claims.append(
                        _claim(
                            run_id=run_id,
                            fault_type="no_supported_fault",
                            statement="Legacy clipping clean family indicates no supported fault.",
                            rules=clip_clean + mode_clean,
                            extra_evidence_refs=(false_mechanism.evidence_id,),
                        )
                    )
                    outcome, confidence, status, completion = (
                        "no_supported_fault",
                        "medium",
                        "success",
                        "baseline_completed",
                    )
                else:
                    cited = [
                        item for item in evaluations if item.judgment == "not_applicable"
                    ] or list(evaluations)
                    claims.append(
                        _claim(
                            run_id=run_id,
                            fault_type="inconclusive",
                            statement="Insufficient evidence for a supported causal diagnosis.",
                            rules=cited,
                        )
                    )
                    outcome, confidence, status, completion = (
                        "inconclusive",
                        "low",
                        "inconclusive",
                        "insufficient_evidence",
                    )
                    limitations = (_INSUFFICIENT,)

        diagnosis = BaselineDiagnosis(
            run_id=run_id,
            outcome=outcome,  # type: ignore[arg-type]
            claims=tuple(claims),
            confidence_label=confidence,  # type: ignore[arg-type]
            limitations=limitations,
            tool_call_count=2,
            rule_evaluation_batches=batches,
        )
        return BaselineRunResult(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            diagnosis=diagnosis,
            observations=(clip_observation, analysis_observation),
            evidence=evidence,
            tool_history=(clip_history, analysis_history),
            completion_reason=completion,  # type: ignore[arg-type]
            warnings=clipping.warnings + analysis.warnings,
            errors=tuple(
                message
                for message in (clipping.error_message, analysis.error_message)
                if message is not None
            ),
            rule_evaluation_batches=batches,
        )
