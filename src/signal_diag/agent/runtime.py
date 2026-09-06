"""Distortion diagnosis Agent runtime loop."""

from __future__ import annotations

import json
import uuid
from typing import cast

from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.models import RuleProfileLoader
from signal_diag.signal import SignalNotFoundError, SignalRepository
from signal_diag.signal.context import StimulusContext
from signal_diag.tools import SignalToolService, ToolResult, get_tool_descriptors

from .diagnosis import CausalPolicyVersion, validate_finish_decision
from .models import (
    AgentRunResult,
    AnalyzeContextualDistortionCall,
    AnalyzeHarmonicDistortionCall,
    AnalyzeSpectrumCall,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisValidationError,
    EstimateFundamentalCall,
    EvaluateRulesDecision,
    FinishDecision,
    Observation,
    PlannerContext,
    PlannerError,
    PlannerOutputError,
    RetrieveKnowledgeDecision,
    RunStatus,
    StructuredDiagnosis,
    TaskAssessment,
    TerminationReason,
    ToolHistoryEntry,
    ToolInvocation,
    ToolOutput,
)
from .planner import PlannerModel
from .policies import (
    AgentLimits,
    is_equivalent_call,
    normalize_tool_arguments,
    record_no_progress,
    reset_progress,
    should_terminate_no_progress,
)
from .rule_closure import (
    RuleClosureProfileId,
    build_rule_closure_request,
    required_rule_profile,
)
from .state import DiagnosisState

_DEFAULT_LIMITS = AgentLimits()


def _contextual_tool_routing_error(
    *,
    causal_policy_version: CausalPolicyVersion,
    stimulus_context: StimulusContext,
    tool_name: str,
) -> str | None:
    if causal_policy_version not in {
        "v9_6_contextual",
        "v9_7_deterministic_rule_closure",
        "v9_8_claim_reference_recovery",
        "v9_9_paired_reference_recovery",
        "v9_10_contextual_clipping_recovery",
        "v9_11_mode_aware_no_fault_recovery",
    }:
        return None
    if (
        stimulus_context.mode in {"paired_reference", "nominal_single_tone"}
        and tool_name == "analyze_harmonic_distortion"
    ):
        return (
            f"{stimulus_context.mode} harmonic closure requires "
            "analyze_contextual_distortion"
        )
    return None


class DistortionDiagnosisRuntime:
    """Deterministic runtime orchestrating planner decisions and Tool execution."""

    def __init__(
        self,
        *,
        repository: SignalRepository,
        tool_service: SignalToolService,
        planner: PlannerModel,
        limits: AgentLimits = _DEFAULT_LIMITS,
        rule_engine: RuleEngine | None = None,
        rule_profile_loader: RuleProfileLoader | None = None,
        knowledge_index: KnowledgeIndex | None = None,
        causal_policy_version: CausalPolicyVersion = "v9_4_legacy",
    ) -> None:
        self._repository = repository
        self._tool_service = tool_service
        self._planner = planner
        self._limits = limits
        self._rule_engine = rule_engine
        self._rule_profile_loader = rule_profile_loader
        self._knowledge_index = knowledge_index
        self._causal_policy_version = causal_policy_version
        self._observation_sequence = 0

    async def run(
        self,
        *,
        signal_id: str,
        user_request: str,
        stimulus_context: StimulusContext | None = None,
    ) -> AgentRunResult:
        try:
            record = self._repository.get(signal_id)
        except SignalNotFoundError as error:
            return self._error_result(
                run_id=self._new_run_id(),
                message=str(error),
                termination_reason="runtime_error",
            )

        if stimulus_context is None:
            resolved_context = StimulusContext(
                mode="single_signal",
                test_signal_id=signal_id,
                assertion_source="user_supplied",
            )
        elif stimulus_context.test_signal_id != signal_id:
            return self._error_result(
                run_id=self._new_run_id(),
                message=(
                    "stimulus_context.test_signal_id must match runtime signal_id"
                ),
                termination_reason="runtime_error",
            )
        else:
            resolved_context = stimulus_context

        reference_meta = None
        if resolved_context.mode == "paired_reference":
            assert resolved_context.reference_signal_id is not None
            try:
                reference_meta = self._repository.get(
                    resolved_context.reference_signal_id
                ).meta
            except SignalNotFoundError as error:
                return self._error_result(
                    run_id=self._new_run_id(),
                    message=str(error),
                    termination_reason="runtime_error",
                )

        state = self._initial_state(
            run_id=self._new_run_id(),
            signal_id=signal_id,
            user_request=user_request,
            signal_meta=record.meta,
            stimulus_context=resolved_context,
            reference_signal_meta=reference_meta,
        )
        planner_retries_remaining = self._limits.max_planner_retries
        recoverable_errors: list[str] = []
        seen_rule_evaluations: set[str] = set()
        seen_knowledge_retrievals: set[str] = set()

        while state["termination_reason"] is None:
            context = self._build_context(
                state,
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=tuple(recoverable_errors),
            )

            try:
                decision = await self._planner.decide(context)
            except PlannerOutputError as error:
                recoverable_errors.append(str(error))
                if planner_retries_remaining <= 0:
                    return self._finalize(
                        state,
                        termination_reason="max_planner_retries",
                        status="error",
                        recoverable_errors=recoverable_errors,
                    )
                planner_retries_remaining -= 1
                continue
            except PlannerError as error:
                state["errors"].append(str(error))
                return self._finalize(
                    state,
                    termination_reason="runtime_error",
                    status="error",
                    recoverable_errors=recoverable_errors,
                )

            if isinstance(decision, CallToolDecision):
                handled, planner_retries_remaining, recoverable_errors = (
                    self._handle_call_tool_decision(
                        state,
                        decision,
                        signal_id=signal_id,
                        planner_retries_remaining=planner_retries_remaining,
                        recoverable_errors=recoverable_errors,
                    )
                )
                if handled == "continue":
                    continue
                if handled == "terminated":
                    return self._finalize_from_state(
                        state,
                        recoverable_errors=recoverable_errors,
                    )
                continue

            if isinstance(decision, EvaluateRulesDecision):
                handled, planner_retries_remaining, recoverable_errors = (
                    self._handle_evaluate_rules_decision(
                        state,
                        decision,
                        seen_rule_evaluations=seen_rule_evaluations,
                        planner_retries_remaining=planner_retries_remaining,
                        recoverable_errors=recoverable_errors,
                    )
                )
                if handled == "continue":
                    continue
                if handled == "terminated":
                    return self._finalize_from_state(
                        state,
                        recoverable_errors=recoverable_errors,
                    )
                continue

            if isinstance(decision, RetrieveKnowledgeDecision):
                handled, planner_retries_remaining, recoverable_errors = (
                    self._handle_retrieve_knowledge_decision(
                        state,
                        decision,
                        seen_knowledge_retrievals=seen_knowledge_retrievals,
                        planner_retries_remaining=planner_retries_remaining,
                        recoverable_errors=recoverable_errors,
                    )
                )
                if handled == "continue":
                    continue
                if handled == "terminated":
                    return self._finalize_from_state(
                        state,
                        recoverable_errors=recoverable_errors,
                    )
                continue

            if not isinstance(decision, FinishDecision):
                state["errors"].append("unsupported planner decision type")
                state["termination_reason"] = "runtime_error"
                return self._finalize_from_state(
                    state,
                    recoverable_errors=recoverable_errors,
                )

            handled, planner_retries_remaining, recoverable_errors = (
                self._handle_finish_decision(
                    state,
                    decision,
                    planner_retries_remaining=planner_retries_remaining,
                    recoverable_errors=recoverable_errors,
                )
            )
            if handled == "continue":
                continue
            return self._finalize_from_state(
                state,
                recoverable_errors=recoverable_errors,
            )

        return self._finalize_from_state(state, recoverable_errors=recoverable_errors)

    def _initial_state(
        self,
        *,
        run_id: str,
        signal_id: str,
        user_request: str,
        signal_meta: object,
        stimulus_context: StimulusContext,
        reference_signal_meta: object | None = None,
    ) -> DiagnosisState:
        from signal_diag.signal.models import SignalMeta

        return DiagnosisState(
            run_id=run_id,
            signal_id=signal_id,
            user_request=user_request,
            signal_meta=cast(SignalMeta, signal_meta),
            stimulus_context=stimulus_context,
            reference_signal_meta=cast(SignalMeta | None, reference_signal_meta),
            task_assessment=None,
            observations=[],
            evidence=[],
            tool_history=[],
            planner_attempt_count=0,
            tool_call_count=0,
            no_progress_count=0,
            warnings=[],
            errors=[],
            termination_reason=None,
            diagnosis=None,
            rule_evaluation_batches=[],
            knowledge_retrievals=[],
            rule_evaluation_count=0,
            knowledge_retrieval_count=0,
        )

    def _new_run_id(self) -> str:
        return f"run_{uuid.uuid4().hex[:12]}"

    def _next_observation_id(self, call_id: str) -> str:
        observation_id = f"obs_{call_id.removeprefix('call_')}_{self._observation_sequence:03d}"
        self._observation_sequence += 1
        return observation_id

    def _build_context(
        self,
        state: DiagnosisState,
        *,
        planner_retries_remaining: int,
        recoverable_errors: tuple[str, ...],
    ) -> PlannerContext:
        remaining_tool_calls = max(
            0,
            self._limits.max_tool_calls - state["tool_call_count"],
        )
        return PlannerContext(
            run_id=state["run_id"],
            user_request=state["user_request"],
            signal_meta=state["signal_meta"],
            stimulus_context=state["stimulus_context"],
            reference_signal_meta=state.get("reference_signal_meta"),
            task_assessment=state["task_assessment"],
            observations=tuple(state["observations"]),
            evidence=tuple(state["evidence"]),
            tool_history=tuple(state["tool_history"]),
            available_tools=get_tool_descriptors(),
            remaining_tool_calls=remaining_tool_calls,
            remaining_planner_retries=planner_retries_remaining,
            no_progress_count=state["no_progress_count"],
            warnings=tuple(state["warnings"]),
            recoverable_errors=recoverable_errors,
            rule_evaluation_batches=tuple(state["rule_evaluation_batches"]),
            knowledge_retrievals=tuple(state["knowledge_retrievals"]),
        )

    def _apply_task_assessment(
        self,
        state: DiagnosisState,
        assessment: TaskAssessment | None,
    ) -> None:
        if assessment is not None:
            state["task_assessment"] = assessment

    def _reject_decision(
        self,
        state: DiagnosisState,
        *,
        message: str,
        planner_retries_remaining: int,
        recoverable_errors: list[str],
    ) -> tuple[str, int, list[str]]:
        recoverable_errors.append(message)
        if planner_retries_remaining <= 0:
            state["termination_reason"] = "max_planner_retries"
            return "terminated", planner_retries_remaining, recoverable_errors
        return "continue", planner_retries_remaining - 1, recoverable_errors

    def _handle_call_tool_decision(
        self,
        state: DiagnosisState,
        decision: CallToolDecision,
        *,
        signal_id: str,
        planner_retries_remaining: int,
        recoverable_errors: list[str],
    ) -> tuple[str, int, list[str]]:
        if state["task_assessment"] is None and decision.task_assessment is None:
            return self._reject_decision(
                state,
                message="initial decision requires task_assessment",
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=recoverable_errors,
            )

        self._apply_task_assessment(state, decision.task_assessment)

        assessment = state["task_assessment"]
        assert assessment is not None
        if assessment.task_type == "unsupported":
            handled, planner_retries_remaining, recoverable_errors = (
                self._reject_decision(
                    state,
                    message="unsupported task must finish without tool calls",
                    planner_retries_remaining=planner_retries_remaining,
                    recoverable_errors=recoverable_errors,
                )
            )
            if handled == "terminated":
                return "terminated", planner_retries_remaining, recoverable_errors
            return handled, planner_retries_remaining, recoverable_errors

        routing_error = _contextual_tool_routing_error(
            causal_policy_version=self._causal_policy_version,
            stimulus_context=state["stimulus_context"],
            tool_name=decision.call.tool_name,
        )
        if routing_error is not None:
            return self._reject_decision(
                state,
                message=routing_error,
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=recoverable_errors,
            )

        if state["tool_call_count"] >= self._limits.max_tool_calls:
            state["termination_reason"] = "max_tool_calls"
            return "terminated", planner_retries_remaining, recoverable_errors

        required_profile = required_rule_profile(
            causal_policy_version=self._causal_policy_version,
            stimulus_context=state["stimulus_context"],
            tool_name=decision.call.tool_name,
        )
        if (
            required_profile is not None
            and state["rule_evaluation_count"] >= self._limits.max_rule_evaluations
        ):
            state["termination_reason"] = "max_rule_evaluations"
            return "terminated", planner_retries_remaining, recoverable_errors

        normalized_arguments = normalize_tool_arguments(decision.call)
        if is_equivalent_call(
            decision.call.tool_name,
            normalized_arguments,
            tuple(state["tool_history"]),
        ):
            record_no_progress(state)
            recoverable_errors.append(
                "equivalent tool call rejected: "
                f"{decision.call.tool_name} with identical arguments"
            )
            if should_terminate_no_progress(state, self._limits):
                state["termination_reason"] = "no_progress"
                return "terminated", planner_retries_remaining, recoverable_errors
            return "continue", planner_retries_remaining, recoverable_errors

        tool_result = self._execute_tool(state, decision.call)
        observation = self._record_tool_execution(
            state,
            decision=decision,
            normalized_arguments=normalized_arguments,
            tool_result=tool_result,
        )

        if tool_result.status == "error":
            record_no_progress(state)
            if should_terminate_no_progress(state, self._limits):
                state["termination_reason"] = "no_progress"
                return "terminated", planner_retries_remaining, recoverable_errors
        else:
            reset_progress(state)
            if required_profile is not None:
                closed = self._append_automatic_rule_closure(
                    state,
                    profile_id=required_profile,
                    observation=observation,
                )
                if not closed:
                    return "terminated", planner_retries_remaining, recoverable_errors

        return "continue", planner_retries_remaining, recoverable_errors

    def _canonical_rule_evaluation_key(
        self,
        decision: EvaluateRulesDecision,
    ) -> str:
        payload = {
            "profile_id": decision.profile_id,
            "evidence_refs": sorted(decision.evidence_refs),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _handle_evaluate_rules_decision(
        self,
        state: DiagnosisState,
        decision: EvaluateRulesDecision,
        *,
        seen_rule_evaluations: set[str],
        planner_retries_remaining: int,
        recoverable_errors: list[str],
    ) -> tuple[str, int, list[str]]:
        if state["task_assessment"] is None and decision.task_assessment is None:
            return self._reject_decision(
                state,
                message="initial decision requires task_assessment",
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=recoverable_errors,
            )

        self._apply_task_assessment(state, decision.task_assessment)
        assessment = state["task_assessment"]
        assert assessment is not None
        if assessment.task_type == "unsupported":
            return self._reject_decision(
                state,
                message="unsupported task must finish without rule evaluation",
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=recoverable_errors,
            )

        if self._causal_policy_version in {
            "v9_7_deterministic_rule_closure",
            "v9_8_claim_reference_recovery",
            "v9_9_paired_reference_recovery",
            "v9_10_contextual_clipping_recovery",
            "v9_11_mode_aware_no_fault_recovery",
        }:
            return self._reject_decision(
                state,
                message=(
                    "rule batches are created automatically from relevant Tool "
                    "observations; use existing rule_evaluation_batches or call "
                    "the missing Tool"
                ),
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=recoverable_errors,
            )

        if state["rule_evaluation_count"] >= self._limits.max_rule_evaluations:
            state["termination_reason"] = "max_rule_evaluations"
            return "terminated", planner_retries_remaining, recoverable_errors

        canonical_key = self._canonical_rule_evaluation_key(decision)
        if canonical_key in seen_rule_evaluations:
            record_no_progress(state)
            recoverable_errors.append(
                "equivalent rule evaluation rejected: "
                f"{decision.profile_id} with identical evidence_refs"
            )
            if should_terminate_no_progress(state, self._limits):
                state["termination_reason"] = "no_progress"
                return "terminated", planner_retries_remaining, recoverable_errors
            return "continue", planner_retries_remaining, recoverable_errors

        known_evidence_ids = {
            item.evidence_id for item in state["evidence"]
        }
        for evidence_id in decision.evidence_refs:
            if evidence_id not in known_evidence_ids:
                return self._reject_decision(
                    state,
                    message=f"unknown evidence reference: {evidence_id}",
                    planner_retries_remaining=planner_retries_remaining,
                    recoverable_errors=recoverable_errors,
                )

        if self._rule_engine is None or self._rule_profile_loader is None:
            state["errors"].append(
                "evaluate_rules requires injected rule_engine and rule_profile_loader"
            )
            state["termination_reason"] = "runtime_error"
            return "terminated", planner_retries_remaining, recoverable_errors

        state["rule_evaluation_count"] += 1
        try:
            profile = self._rule_profile_loader.load(decision.profile_id)
            evidence_filter = (
                frozenset(decision.evidence_refs)
                if decision.evidence_refs
                else None
            )
            batch = self._rule_engine.evaluate_profile(
                profile,
                state["evidence"],
                evidence_filter=evidence_filter,
            )
        except Exception as error:  # noqa: BLE001 - runtime maps dependency failures
            state["errors"].append(str(error))
            state["termination_reason"] = "runtime_error"
            return "terminated", planner_retries_remaining, recoverable_errors

        state["rule_evaluation_batches"].append(batch)
        seen_rule_evaluations.add(canonical_key)
        reset_progress(state)
        return "continue", planner_retries_remaining, recoverable_errors

    def _canonical_knowledge_retrieval_key(
        self,
        decision: RetrieveKnowledgeDecision,
    ) -> str:
        payload = {
            "query_text": decision.query_text,
            "tags": [tag.strip() for tag in decision.tags],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _handle_retrieve_knowledge_decision(
        self,
        state: DiagnosisState,
        decision: RetrieveKnowledgeDecision,
        *,
        seen_knowledge_retrievals: set[str],
        planner_retries_remaining: int,
        recoverable_errors: list[str],
    ) -> tuple[str, int, list[str]]:
        if state["task_assessment"] is None and decision.task_assessment is None:
            return self._reject_decision(
                state,
                message="initial decision requires task_assessment",
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=recoverable_errors,
            )

        self._apply_task_assessment(state, decision.task_assessment)
        assessment = state["task_assessment"]
        assert assessment is not None
        if assessment.task_type == "unsupported":
            return self._reject_decision(
                state,
                message="unsupported task must finish without knowledge retrieval",
                planner_retries_remaining=planner_retries_remaining,
                recoverable_errors=recoverable_errors,
            )

        if state["knowledge_retrieval_count"] >= self._limits.max_knowledge_retrievals:
            state["termination_reason"] = "max_knowledge_retrievals"
            return "terminated", planner_retries_remaining, recoverable_errors

        canonical_key = self._canonical_knowledge_retrieval_key(decision)
        if canonical_key in seen_knowledge_retrievals:
            record_no_progress(state)
            recoverable_errors.append(
                "equivalent knowledge retrieval rejected: "
                f"{decision.query_text!r} with identical tags"
            )
            if should_terminate_no_progress(state, self._limits):
                state["termination_reason"] = "no_progress"
                return "terminated", planner_retries_remaining, recoverable_errors
            return "continue", planner_retries_remaining, recoverable_errors

        if self._knowledge_index is None:
            state["errors"].append(
                "retrieve_knowledge requires injected knowledge_index"
            )
            state["termination_reason"] = "runtime_error"
            return "terminated", planner_retries_remaining, recoverable_errors

        state["knowledge_retrieval_count"] += 1
        try:
            retrieval = self._knowledge_index.retrieve(
                query_text=decision.query_text,
                tags=decision.tags,
            )
        except Exception as error:  # noqa: BLE001 - runtime maps dependency failures
            state["errors"].append(str(error))
            state["termination_reason"] = "runtime_error"
            return "terminated", planner_retries_remaining, recoverable_errors

        state["knowledge_retrievals"].append(retrieval)
        seen_knowledge_retrievals.add(canonical_key)
        reset_progress(state)
        return "continue", planner_retries_remaining, recoverable_errors

    def _handle_finish_decision(
        self,
        state: DiagnosisState,
        decision: FinishDecision,
        *,
        planner_retries_remaining: int,
        recoverable_errors: list[str],
    ) -> tuple[str, int, list[str]]:
        if state["task_assessment"] is None and decision.task_assessment is None:
            handled, planner_retries_remaining, recoverable_errors = (
                self._reject_decision(
                    state,
                    message="finish decision requires task_assessment",
                    planner_retries_remaining=planner_retries_remaining,
                    recoverable_errors=recoverable_errors,
                )
            )
            if handled == "terminated":
                return "terminated", planner_retries_remaining, recoverable_errors
            return handled, planner_retries_remaining, recoverable_errors

        self._apply_task_assessment(state, decision.task_assessment)
        assessment = state["task_assessment"]
        assert assessment is not None

        known_evidence_ids = frozenset(
            item.evidence_id for item in state["evidence"]
        )
        known_rule_evaluation_ids = frozenset(
            evaluation.evaluation_id
            for batch in state["rule_evaluation_batches"]
            for evaluation in batch.evaluations
        )
        known_knowledge_retrieval_ids = frozenset(
            item.retrieval_id for item in state["knowledge_retrievals"]
        )
        try:
            validate_finish_decision(
                decision,
                known_evidence_ids=known_evidence_ids,
                known_rule_evaluation_ids=known_rule_evaluation_ids,
                known_knowledge_retrieval_ids=known_knowledge_retrieval_ids,
                task_assessment=assessment,
                evidence=tuple(state["evidence"]),
                rule_evaluations=tuple(
                    evaluation
                    for batch in state["rule_evaluation_batches"]
                    for evaluation in batch.evaluations
                ),
                stimulus_context=state["stimulus_context"],
                causal_policy_version=self._causal_policy_version,
            )
        except DiagnosisValidationError as error:
            handled, planner_retries_remaining, recoverable_errors = (
                self._reject_decision(
                    state,
                    message=str(error),
                    planner_retries_remaining=planner_retries_remaining,
                    recoverable_errors=recoverable_errors,
                )
            )
            if handled == "terminated":
                return "terminated", planner_retries_remaining, recoverable_errors
            return handled, planner_retries_remaining, recoverable_errors

        if assessment.task_type == "unsupported":
            termination_reason: TerminationReason = "unsupported_task"
        else:
            termination_reason = "planner_finished"

        state["termination_reason"] = termination_reason
        state["diagnosis"] = StructuredDiagnosis(
            run_id=state["run_id"],
            task_type=assessment.task_type,
            outcome=decision.outcome,
            claims=decision.claims,
            confidence_label=decision.confidence_label,
            limitations=decision.limitations,
            termination_reason=termination_reason,
            tool_call_count=state["tool_call_count"],
            rule_evaluation_batches=tuple(state["rule_evaluation_batches"]),
            knowledge_retrievals=tuple(state["knowledge_retrievals"]),
        )
        return "finished", planner_retries_remaining, recoverable_errors

    def _execute_tool(
        self,
        state: DiagnosisState,
        call: ToolInvocation,
    ) -> ToolResult[ToolOutput]:
        signal_id = state["signal_id"]
        if isinstance(call, DetectClippingCall):
            return cast(
                ToolResult[ToolOutput],
                self._tool_service.detect_clipping(signal_id, call.args),
            )
        if isinstance(call, AnalyzeSpectrumCall):
            return cast(
                ToolResult[ToolOutput],
                self._tool_service.analyze_spectrum(signal_id, call.args),
            )
        if isinstance(call, EstimateFundamentalCall):
            return cast(
                ToolResult[ToolOutput],
                self._tool_service.estimate_fundamental(signal_id, call.args),
            )
        if isinstance(call, AnalyzeHarmonicDistortionCall):
            return cast(
                ToolResult[ToolOutput],
                self._tool_service.analyze_harmonic_distortion(signal_id, call.args),
            )
        if isinstance(call, AnalyzeContextualDistortionCall):
            return cast(
                ToolResult[ToolOutput],
                self._tool_service.analyze_contextual_distortion(
                    state["stimulus_context"],
                    call.args,
                ),
            )
        raise RuntimeError(f"unsupported tool invocation: {call.tool_name}")

    def _append_automatic_rule_closure(
        self,
        state: DiagnosisState,
        *,
        profile_id: RuleClosureProfileId,
        observation: Observation,
    ) -> bool:
        try:
            request = build_rule_closure_request(
                profile_id=profile_id,
                observation=observation,
            )
            if request is None:
                return True
            if self._rule_engine is None or self._rule_profile_loader is None:
                raise RuntimeError("automatic rule closure requires rule dependencies")
            profile = self._rule_profile_loader.load(request.profile_id)
            evidence_by_id = {item.evidence_id: item for item in state["evidence"]}
            exact_evidence = tuple(
                evidence_by_id[ref] for ref in request.evidence_refs
            )
            batch = self._rule_engine.evaluate_profile(
                profile,
                exact_evidence,
                evidence_filter=frozenset(request.evidence_refs),
            )
            if batch.profile_id != request.profile_id:
                raise RuntimeError("automatic rule closure profile mismatch")
            allowed = frozenset(request.evidence_refs)
            if any(
                ref not in allowed
                for evaluation in batch.evaluations
                for ref in evaluation.evidence_refs
            ):
                raise RuntimeError("automatic rule closure Evidence scope mismatch")
        except Exception as error:  # noqa: BLE001
            state["errors"].append(str(error))
            state["termination_reason"] = "runtime_error"
            return False
        state["rule_evaluation_count"] += 1
        state["rule_evaluation_batches"].append(batch)
        return True

    def _record_tool_execution(
        self,
        state: DiagnosisState,
        *,
        decision: CallToolDecision,
        normalized_arguments: dict[str, object],
        tool_result: ToolResult[ToolOutput],
    ) -> Observation:
        state["tool_call_count"] += 1
        observation = Observation(
            observation_id=self._next_observation_id(tool_result.call_id),
            call_id=tool_result.call_id,
            tool_name=tool_result.tool_name,
            normalized_arguments=normalized_arguments,
            purpose=decision.purpose,
            status=tool_result.status,
            result=cast(ToolOutput | None, tool_result.result),
            evidence_refs=tuple(item.evidence_id for item in tool_result.evidence),
            warnings=tool_result.warnings,
            error_message=tool_result.error_message,
        )
        state["observations"].append(observation)
        state["evidence"].extend(tool_result.evidence)
        state["tool_history"].append(
            ToolHistoryEntry(
                call_id=tool_result.call_id,
                tool_name=tool_result.tool_name,
                normalized_arguments=normalized_arguments,
                purpose=decision.purpose,
                status=tool_result.status,
            )
        )
        state["warnings"].extend(tool_result.warnings)
        return observation

    def _run_status(
        self,
        *,
        termination_reason: TerminationReason,
        diagnosis: StructuredDiagnosis | None,
    ) -> RunStatus:
        if termination_reason in {
            "max_tool_calls",
            "max_planner_retries",
            "max_rule_evaluations",
            "max_knowledge_retrievals",
            "no_progress",
            "runtime_error",
        }:
            return "error"
        if diagnosis is None:
            return "error"
        if diagnosis.outcome == "inconclusive":
            return "inconclusive"
        return "success"

    def _finalize_from_state(
        self,
        state: DiagnosisState,
        *,
        recoverable_errors: list[str],
    ) -> AgentRunResult:
        termination_reason = state["termination_reason"] or "runtime_error"
        status = self._run_status(
            termination_reason=termination_reason,
            diagnosis=state["diagnosis"],
        )
        return AgentRunResult(
            run_id=state["run_id"],
            status=status,
            diagnosis=state["diagnosis"],
            observations=tuple(state["observations"]),
            evidence=tuple(state["evidence"]),
            tool_history=tuple(state["tool_history"]),
            termination_reason=termination_reason,
            warnings=tuple(state["warnings"]),
            errors=tuple(state["errors"] + recoverable_errors),
            rule_evaluation_batches=tuple(state["rule_evaluation_batches"]),
            knowledge_retrievals=tuple(state["knowledge_retrievals"]),
        )

    def _finalize(
        self,
        state: DiagnosisState,
        *,
        termination_reason: TerminationReason,
        status: RunStatus,
        recoverable_errors: list[str],
    ) -> AgentRunResult:
        state["termination_reason"] = termination_reason
        return AgentRunResult(
            run_id=state["run_id"],
            status=status,
            diagnosis=state["diagnosis"],
            observations=tuple(state["observations"]),
            evidence=tuple(state["evidence"]),
            tool_history=tuple(state["tool_history"]),
            termination_reason=termination_reason,
            warnings=tuple(state["warnings"]),
            errors=tuple(state["errors"] + recoverable_errors),
            rule_evaluation_batches=tuple(state["rule_evaluation_batches"]),
            knowledge_retrievals=tuple(state["knowledge_retrievals"]),
        )

    def _error_result(
        self,
        *,
        run_id: str,
        message: str,
        termination_reason: TerminationReason,
    ) -> AgentRunResult:
        return AgentRunResult(
            run_id=run_id,
            status="error",
            diagnosis=None,
            observations=(),
            evidence=(),
            tool_history=(),
            termination_reason=termination_reason,
            errors=(message,),
        )
