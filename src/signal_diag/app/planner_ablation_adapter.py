"""App-level adapter for planner-ablation product slots (D037 entry)."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from signal_diag.agent.planner import PlannerModel
from signal_diag.app.service import (
    ApplicationDependencies,
    DiagnosisApplicationService,
    PlannerFactory,
)
from signal_diag.evaluation.planner_ablation.models import (
    ExecutionIdentity,
    ProductSlotOutcome,
    ProductSlotRequest,
    StudyContextGuidanceView,
)

_APPROVED_PRODUCT_PLANNER_CLASS = "RealLLMPlanner"


def _execution_identity_for_planner(planner_class: str) -> ExecutionIdentity:
    if planner_class == _APPROVED_PRODUCT_PLANNER_CLASS:
        return "product_campaign"
    return "harness_only"


def _map_guidance(
    guidance: object | None,
) -> StudyContextGuidanceView | None:
    if guidance is None:
        return None
    return StudyContextGuidanceView(
        reason_codes=tuple(guidance.reason_codes),  # type: ignore[attr-defined]
        unlockable_modes=tuple(guidance.unlockable_modes),  # type: ignore[attr-defined]
        required_inputs={
            key: tuple(value)
            for key, value in guidance.required_inputs.items()  # type: ignore[attr-defined]
        },
        summary=guidance.summary,  # type: ignore[attr-defined]
    )


class AppProductSlotExecutor:
    """Maps contextual submit/wait to study-owned product slot outcomes."""

    def __init__(self, service: DiagnosisApplicationService) -> None:
        self._service = service

    async def execute_product_slot(
        self,
        request: ProductSlotRequest,
    ) -> ProductSlotOutcome:
        dependencies: ApplicationDependencies = self._service._dependencies
        executed_planner_class = ""

        def tracking_factory() -> PlannerModel:
            nonlocal executed_planner_class
            planner = dependencies.planner_factory()
            executed_planner_class = type(planner).__name__
            return planner

        tracked_factory = cast(PlannerFactory, tracking_factory)
        self._service._dependencies = replace(
            dependencies,
            planner_factory=tracked_factory,
        )
        try:
            submission = await self._service.submit_contextual_wav(
                request.test_wav_bytes,
                test_filename=request.test_filename,
                mode=request.mode,
                reference_data=request.reference_wav_bytes,
                reference_filename=request.reference_filename,
                nominal_fundamental_hz=None,
                stimulus_kind=None,
                user_request=request.user_request,
            )
            snapshot = await self._service.wait_for_contextual_terminal(submission.run_id)
        finally:
            self._service._dependencies = dependencies
        guidance = snapshot.context_guidance
        return ProductSlotOutcome(
            run_id=snapshot.run_id,
            mode=request.mode,
            terminal_status="completed" if snapshot.status == "completed" else "failed",
            result=snapshot.result,
            context_guidance=_map_guidance(guidance),
            planner_class=executed_planner_class,
            execution_identity=_execution_identity_for_planner(executed_planner_class),
        )
