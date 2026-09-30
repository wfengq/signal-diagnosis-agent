"""App-level adapter for planner-ablation product slots (D037 entry)."""

from __future__ import annotations

from signal_diag.app.context_guidance import build_context_guidance
from signal_diag.app.service import DiagnosisApplicationService
from signal_diag.evaluation.planner_ablation.models import (
    ProductSlotOutcome,
    ProductSlotRequest,
    StudyContextGuidanceView,
)


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
        guidance = snapshot.context_guidance
        if guidance is None and snapshot.result is not None:
            guidance = build_context_guidance(
                mode=request.mode,
                result=snapshot.result,
            )
        planner_class = type(self._service._dependencies.planner_factory()).__name__
        return ProductSlotOutcome(
            run_id=snapshot.run_id,
            mode=request.mode,
            terminal_status="completed" if snapshot.status == "completed" else "failed",
            result=snapshot.result,
            context_guidance=_map_guidance(guidance),
            planner_class=planner_class,
            execution_identity="product_campaign",
        )
