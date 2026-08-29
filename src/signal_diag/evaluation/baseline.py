"""Honest two-Tool fixed-pipeline baseline."""

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
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.models import (
    RuleEvaluation,
    RuleEvaluationBatch,
    RuleProfileLoader,
)
from signal_diag.signal.repository import SignalRepository
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.results import ToolResult
from signal_diag.tools.service import SignalToolService

_OFFICIAL_PROFILE_ID = "profile_s1_distortion"
_CLIPPING_RULE_IDS = frozenset(
    {
        "rule_clipping_detected_absent",
        "rule_clipping_ratio_acceptable",
        "rule_flat_top_absent",
    }
)
_HARMONIC_VALID_RULE = "rule_harmonic_analysis_valid"
_THD_RULE = "rule_thd_acceptable"
_CLIPPING_PURPOSE = "fixed-pipeline clipping analysis"
_HARMONIC_PURPOSE = "fixed-pipeline harmonic distortion analysis"
_HARMONIC_LIMITATION = (
    "harmonic distortion analysis is not applicable; no THD value was fabricated"
)
TOutput = TypeVar("TOutput", bound=ToolOutput)


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"


def _refs_from_evaluations(
    evaluations: list[RuleEvaluation],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    evidence_refs: list[str] = []
    seen: set[str] = set()
    rule_refs: list[str] = []
    for item in evaluations:
        rule_refs.append(item.evaluation_id)
        for ref in item.evidence_refs:
            if ref in seen:
                continue
            seen.add(ref)
            evidence_refs.append(ref)
    return tuple(evidence_refs), tuple(rule_refs)


def _record_tool(
    tool_result: ToolResult[TOutput],
    args: ClippingInput | HarmonicDistortionInput,
    purpose: str,
) -> tuple[Observation, ToolHistoryEntry]:
    normalized = args.model_dump(mode="json")
    observation = Observation(
        observation_id=_stable_id(
            "obs_",
            {"call_id": tool_result.call_id, "tool_name": tool_result.tool_name},
        ),
        call_id=tool_result.call_id,
        tool_name=tool_result.tool_name,
        normalized_arguments=normalized,
        purpose=purpose,
        status=tool_result.status,
        result=cast(ToolOutput | None, tool_result.result),
        evidence_refs=tuple(item.evidence_id for item in tool_result.evidence),
        warnings=tool_result.warnings,
        error_message=tool_result.error_message,
    )
    history = ToolHistoryEntry(
        call_id=tool_result.call_id,
        tool_name=tool_result.tool_name,
        normalized_arguments=normalized,
        purpose=purpose,
        status=tool_result.status,
    )
    return observation, history


def _claim(
    *,
    run_id: str,
    fault_type: str,
    statement: str,
    evaluations: list[RuleEvaluation],
) -> DiagnosisClaim:
    evidence_refs, rule_refs = _refs_from_evaluations(evaluations)
    return DiagnosisClaim(
        claim_id=_stable_id(
            "claim_",
            {
                "run_id": run_id,
                "fault_type": fault_type,
                "evidence_refs": list(evidence_refs),
                "rule_refs": list(rule_refs),
            },
        ),
        fault_type=fault_type,  # type: ignore[arg-type]
        statement=statement,
        evidence_refs=evidence_refs,
        rule_refs=rule_refs,
        knowledge_refs=(),
    )


def _map_claims(
    batch: RuleEvaluationBatch,
    run_id: str,
) -> tuple[
    str,
    tuple[DiagnosisClaim, ...],
    tuple[str, ...],
    str,
    str,
    str,
]:
    evaluations = batch.evaluations
    clipping = any(
        item.rule_id in _CLIPPING_RULE_IDS and item.judgment == "fail"
        for item in evaluations
    )
    harmonic_valid = any(
        item.rule_id == _HARMONIC_VALID_RULE and item.judgment == "pass"
        for item in evaluations
    )
    harmonic = harmonic_valid and any(
        item.rule_id == _THD_RULE and item.judgment == "fail"
        for item in evaluations
    )
    clipping_fails = [
        item
        for item in evaluations
        if item.rule_id in _CLIPPING_RULE_IDS and item.judgment == "fail"
    ]
    harmonic_valid_passes = [
        item
        for item in evaluations
        if item.rule_id == _HARMONIC_VALID_RULE and item.judgment == "pass"
    ]
    thd_fails = [
        item
        for item in evaluations
        if item.rule_id == _THD_RULE and item.judgment == "fail"
    ]
    sufficient_passes = [
        item
        for item in evaluations
        if item.judgment == "pass"
        and item.rule_id in (_CLIPPING_RULE_IDS | {_HARMONIC_VALID_RULE, _THD_RULE})
    ]
    harmonic_unavailable = [
        item
        for item in evaluations
        if item.rule_id in {_HARMONIC_VALID_RULE, _THD_RULE}
        and item.judgment == "not_applicable"
    ]
    claims: list[DiagnosisClaim] = []
    if clipping:
        claims.append(
            _claim(
                run_id=run_id,
                fault_type="clipping",
                statement="Clipping is indicated by applicable profile rule failures.",
                evaluations=clipping_fails,
            )
        )
    if harmonic:
        claims.append(
            _claim(
                run_id=run_id,
                fault_type="harmonic_distortion",
                statement=(
                    "Harmonic distortion is indicated by valid analysis "
                    "and a THD rule failure."
                ),
                evaluations=harmonic_valid_passes + thd_fails,
            )
        )
    if clipping and harmonic:
        return (
            "supported_fault",
            tuple(claims),
            (),
            "high",
            "baseline_completed",
            "success",
        )
    if clipping and harmonic_valid:
        return (
            "supported_fault",
            tuple(claims),
            (),
            "high",
            "baseline_completed",
            "success",
        )
    if clipping:
        return (
            "supported_fault",
            tuple(claims),
            (_HARMONIC_LIMITATION,),
            "medium",
            "baseline_completed",
            "success",
        )
    if harmonic:
        return (
            "supported_fault",
            tuple(claims),
            (),
            "high",
            "baseline_completed",
            "success",
        )
    if harmonic_valid:
        return (
            "no_supported_fault",
            (
                _claim(
                    run_id=run_id,
                    fault_type="no_supported_fault",
                    statement=(
                        "No supported clipping or harmonic-distortion fault is indicated."
                    ),
                    evaluations=sufficient_passes,
                ),
            ),
            (),
            "medium",
            "baseline_completed",
            "success",
        )
    return (
        "inconclusive",
        (
            _claim(
                run_id=run_id,
                fault_type="inconclusive",
                statement=(
                    "Evidence is insufficient for a supported-fault "
                    "or no-supported-fault diagnosis."
                ),
                evaluations=harmonic_unavailable,
            ),
        ),
        (_HARMONIC_LIMITATION,),
        "low",
        "insufficient_evidence",
        "inconclusive",
    )


class FixedPipelineBaseline:
    def __init__(
        self,
        *,
        repository: SignalRepository,
        tool_service: SignalToolService,
        rule_engine: RuleEngine,
        profile_loader: RuleProfileLoader,
    ) -> None:
        self._repository = repository
        self._tool_service = tool_service
        self._rule_engine = rule_engine
        self._profile_loader = profile_loader

    async def run(
        self,
        *,
        signal_id: str,
        user_request: str,
    ) -> BaselineRunResult:
        self._repository.exists(signal_id)
        clipping_args = ClippingInput()
        harmonic_args = HarmonicDistortionInput()
        clipping_result = self._tool_service.detect_clipping(signal_id, clipping_args)
        harmonic_result = self._tool_service.analyze_harmonic_distortion(
            signal_id,
            harmonic_args,
        )
        clipping_obs, clipping_history = _record_tool(
            clipping_result,
            clipping_args,
            _CLIPPING_PURPOSE,
        )
        harmonic_obs, harmonic_history = _record_tool(
            harmonic_result,
            harmonic_args,
            _HARMONIC_PURPOSE,
        )
        evidence = tuple(clipping_result.evidence) + tuple(harmonic_result.evidence)
        profile = self._profile_loader.load(_OFFICIAL_PROFILE_ID)
        batch = self._rule_engine.evaluate_profile(profile, evidence)
        observations = (clipping_obs, harmonic_obs)
        tool_history = (clipping_history, harmonic_history)
        warnings = clipping_result.warnings + harmonic_result.warnings
        errors: tuple[str, ...] = ()
        if clipping_result.error_message is not None:
            errors += (clipping_result.error_message,)
        if harmonic_result.error_message is not None:
            errors += (harmonic_result.error_message,)
        run_id = _stable_id(
            "baseline_",
            {
                "signal_id": signal_id,
                "user_request": user_request,
                "call_ids": [clipping_obs.call_id, harmonic_obs.call_id],
                "evidence_ids": [item.evidence_id for item in evidence],
                "batch_id": batch.batch_id,
            },
        )
        (
            outcome,
            claims,
            limitations,
            confidence,
            completion_reason,
            status,
        ) = _map_claims(batch, run_id)
        diagnosis = BaselineDiagnosis(
            run_id=run_id,
            outcome=outcome,  # type: ignore[arg-type]
            claims=claims,
            confidence_label=confidence,  # type: ignore[arg-type]
            limitations=limitations,
            tool_call_count=2,
            rule_evaluation_batches=(batch,),
        )
        return BaselineRunResult(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            diagnosis=diagnosis,
            observations=observations,
            evidence=evidence,
            tool_history=tool_history,
            completion_reason=completion_reason,  # type: ignore[arg-type]
            warnings=warnings,
            errors=errors,
            rule_evaluation_batches=(batch,),
        )
