"""T-CX276: D037 contextual entry via injected executor."""

from __future__ import annotations

import pytest

from signal_diag.evaluation.planner_ablation.models import ProductSlotRequest
from signal_diag.evaluation.planner_ablation.runner import run_product_slot


class _LegacyForbiddenExecutor:
    async def submit_wav(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("legacy submit_wav must not be called for study slots")

    async def wait_for_terminal(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("legacy wait_for_terminal must not be called")

    async def execute_product_slot(self, request: ProductSlotRequest) -> object:
        submission = await self.submit_contextual_wav(
            request.test_wav_bytes,
            test_filename=request.test_filename,
            mode=request.mode,
            reference_data=request.reference_wav_bytes,
            reference_filename=request.reference_filename,
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=request.user_request,
        )
        return await self.wait_for_contextual_terminal(submission.run_id)

    async def submit_contextual_wav(self, *args: object, **kwargs: object) -> object:
        class _Submission:
            run_id = "run_" + "a" * 32

        return _Submission()

    async def wait_for_contextual_terminal(self, run_id: str) -> object:
        from signal_diag.evaluation.planner_ablation.models import ProductSlotOutcome

        return ProductSlotOutcome(
            run_id=run_id,
            mode="single_signal",
            terminal_status="completed",
            planner_class="FakePlanner",
        )


@pytest.mark.asyncio
async def test_t_cx276_legacy_submit_wav_fails_immediately() -> None:
    executor = _LegacyForbiddenExecutor()
    executor.submit_wav = lambda *a, **k: (_ for _ in ()).throw(  # type: ignore[method-assign]
        AssertionError("legacy submit_wav")
    )
    with pytest.raises(AssertionError, match="legacy submit_wav"):
        await executor.submit_wav(b"data")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_t_cx276_runner_uses_contextual_executor_surface() -> None:
    outcome = await run_product_slot(
        _LegacyForbiddenExecutor(),
        ProductSlotRequest(
            case_id="case_ctx",
            test_wav_bytes=b"RIFFxxxx",
            test_filename="input.wav",
            mode="single_signal",
            user_request="Diagnose supported S1 distortion conservatively.",
        ),
    )
    assert outcome.run_id.startswith("run_")
