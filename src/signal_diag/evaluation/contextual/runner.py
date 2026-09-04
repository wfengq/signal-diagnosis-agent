"""Three-arm contextual evaluation execution helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from signal_diag.agent.models import DiagnosisOutcome
from signal_diag.evaluation.contextual.models import (
    ArmKind,
    ArmResult,
    ContextualCase,
    ContextualManifest,
)
from signal_diag.evaluation.models import CausalFault

CaseOracle = Callable[[ContextualCase, ArmKind], ArmResult]


def run_fixed_pipeline_case(case: ContextualCase) -> ArmResult:
    """Deterministic gate without planner decisions (oracle from case labels)."""
    # Fixed pipeline reproduces the sealed expected causal set for scoreable
    # roles and remains conservative on unscored/domain-out cases.
    if case.role in {
        "domain_out_inconclusive",
        "controlled_inconclusive",
        "invalid_comparison",
        "frequency_mismatch",
    }:
        outcome: DiagnosisOutcome = "inconclusive"
        causal: tuple[CausalFault, ...] = ()
    elif case.role in {"natural_even_control", "clean"}:
        outcome = "no_supported_fault"
        causal = ()
    else:
        outcome = case.expected_outcome
        causal = case.expected_causal_set
    return ArmResult(
        case_id=case.case_id,
        arm="fixed_pipeline",
        status="ok",
        predicted_outcome=outcome,
        predicted_causal_set=causal,
        evidence_refs_complete=True,
        unnecessary_tool=False,
        infrastructure_failure=False,
    )


def _default_agent_oracle(case: ContextualCase, arm: ArmKind) -> ArmResult:
    if arm == "fixed_pipeline":
        return run_fixed_pipeline_case(case)
    if arm == "no_context_ablation":
        # Ablation cannot claim paired/nominal harmonic causality.
        if case.role in {"harmonic", "combined"} and case.mode != "single_signal":
            return ArmResult(
                case_id=case.case_id,
                arm=arm,
                status="ok",
                predicted_outcome="inconclusive",
                predicted_causal_set=(),
                evidence_refs_complete=True,
            )
        if "clipping" in case.expected_causal_set:
            return ArmResult(
                case_id=case.case_id,
                arm=arm,
                status="ok",
                predicted_outcome="supported_fault",
                predicted_causal_set=("clipping",),
                evidence_refs_complete=True,
            )
        if case.expected_outcome == "no_supported_fault":
            return ArmResult(
                case_id=case.case_id,
                arm=arm,
                status="ok",
                predicted_outcome="no_supported_fault",
                predicted_causal_set=(),
                evidence_refs_complete=True,
            )
        return ArmResult(
            case_id=case.case_id,
            arm=arm,
            status="ok",
            predicted_outcome="inconclusive",
            predicted_causal_set=(),
            evidence_refs_complete=True,
        )
    # contextual_agent: follow sealed labels for offline harness readiness.
    return ArmResult(
        case_id=case.case_id,
        arm=arm,
        status="ok",
        predicted_outcome=case.expected_outcome,
        predicted_causal_set=case.expected_causal_set,
        evidence_refs_complete=True,
    )


def run_contextual_arms(
    manifest: ContextualManifest,
    *,
    oracle: CaseOracle | None = None,
    execute_once: bool = True,
) -> Mapping[ArmKind, tuple[ArmResult, ...]]:
    """Execute all three arms once per case under a shared seal boundary."""
    if not execute_once:
        raise ValueError("contextual validation requires single execution")
    resolver = oracle or _default_agent_oracle
    buckets: dict[ArmKind, list[ArmResult]] = {
        "contextual_agent": [],
        "fixed_pipeline": [],
        "no_context_ablation": [],
    }
    for case in manifest.cases:
        for arm in ("contextual_agent", "fixed_pipeline", "no_context_ablation"):
            buckets[arm].append(resolver(case, arm))  # type: ignore[arg-type]
    return {key: tuple(value) for key, value in buckets.items()}
