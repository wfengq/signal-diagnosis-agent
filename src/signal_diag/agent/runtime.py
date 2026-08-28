"""Distortion diagnosis Agent runtime loop."""

from __future__ import annotations

import uuid
from typing import cast

from signal_diag.signal import SignalNotFoundError, SignalRepository
from signal_diag.tools import SignalToolService, ToolResult, get_tool_descriptors

from .diagnosis import validate_finish_decision
from .models import (
    AgentRunResult,
    AnalyzeHarmonicDistortionCall,
    AnalyzeSpectrumCall,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisValidationError,
    EstimateFundamentalCall,
    FinishDecision,
    Observation,
    PlannerContext,
    PlannerError,
    PlannerOutputError,
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
from .state import DiagnosisState

_DEFAULT_LIMITS = AgentLimits()


class DistortionDiagnosisRuntime:
    """Deterministic runtime orchestrating planner decisions and Tool execution."""

    def __init__(
        self,
        *,
        repository: SignalRepository,
        tool_service: SignalToolService,
        planner: PlannerModel,
        limits: AgentLimits = _DEFAULT_LIMITS,
    ) -> None:
        self._repository = repository
        self._tool_service = tool_service
        self._planner = planner
        self._limits = limits
        self._observation_sequence = 0

    async def run(
        self,
        *,
        signal_id: str,
        user_request: str,
    ) -> AgentRunResult:
        try:
            record = self._repository.get(signal_id)
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
        )
        planner_retries_remaining = self._limits.max_planner_retries
        recoverable_errors: list[str] = []

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
    ) -> DiagnosisState:
        from signal_diag.signal.models import SignalMeta

        return DiagnosisState(
            run_id=run_id,
            signal_id=signal_id,
            user_request=user_request,
            signal_meta=cast(SignalMeta, signal_meta),
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

        if state["tool_call_count"] >= self._limits.max_tool_calls:
            state["termination_reason"] = "max_tool_calls"
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

        tool_result = self._execute_tool(signal_id, decision.call)
        self._record_tool_execution(
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
        try:
            validate_finish_decision(
                decision,
                known_evidence_ids=known_evidence_ids,
                task_assessment=assessment,
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
        )
        return "finished", planner_retries_remaining, recoverable_errors

    def _execute_tool(
        self,
        signal_id: str,
        call: ToolInvocation,
    ) -> ToolResult[ToolOutput]:
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
        raise RuntimeError(f"unsupported tool invocation: {call.tool_name}")

    def _record_tool_execution(
        self,
        state: DiagnosisState,
        *,
        decision: CallToolDecision,
        normalized_arguments: dict[str, object],
        tool_result: ToolResult[ToolOutput],
    ) -> None:
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

    def _run_status(
        self,
        *,
        termination_reason: TerminationReason,
        diagnosis: StructuredDiagnosis | None,
    ) -> RunStatus:
        if termination_reason in {
            "max_tool_calls",
            "max_planner_retries",
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
