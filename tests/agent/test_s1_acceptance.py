"""Checkpoint F — Deterministic S1 acceptance (T086–T092)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from signal_diag.agent.models import (
    AgentDecision,
    AnalyzeHarmonicDistortionCall,
    AnalyzeSpectrumCall,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    EstimateFundamentalCall,
    FinishDecision,
    FundamentalInput,
    HarmonicDistortionInput,
    PlannerContext,
    SpectrumInput,
    TaskAssessment,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.signal import SyntheticCase
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case


def _assessment() -> TaskAssessment:
    return TaskAssessment(
        task_type="distortion_analysis",
        objective="determine why the signal sounds distorted",
        hypotheses=("clipping", "harmonic distortion"),
    )


FinishBuilder = Callable[[PlannerContext], FinishDecision]


class S1RoutePlanner:
    """Scripted tool route with a context-aware finish decision."""

    def __init__(
        self,
        tool_steps: list[CallToolDecision],
        finish_builder: FinishBuilder,
    ) -> None:
        self._tool_steps = tool_steps
        self._finish_builder = finish_builder
        self._index = 0

    async def decide(self, context: PlannerContext) -> AgentDecision:
        if self._index < len(self._tool_steps):
            if self._index == 0 and self._tool_steps[0].task_assessment is None:
                decision = self._tool_steps[0].model_copy(
                    update={"task_assessment": _assessment()}
                )
            else:
                decision = self._tool_steps[self._index]
            self._index += 1
            return decision
        return self._finish_builder(context)


def _evidence_by_metric(context: PlannerContext, metric: str) -> str:
    for item in context.evidence:
        if item.metric == metric:
            return item.evidence_id
    raise AssertionError(f"missing evidence metric: {metric}")


FORBIDDEN_FFT_KEYS = frozenset({"frequencies_hz", "magnitude_db"})


def _assert_json_tree_has_no_arrays_or_full_fft_keys(value: Any) -> None:
    if isinstance(value, np.ndarray):
        pytest.fail("serialized state must not contain ndarray values")
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_FFT_KEYS:
                raise AssertionError(
                    "serialized state must not expose full FFT arrays"
                )
            _assert_json_tree_has_no_arrays_or_full_fft_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_json_tree_has_no_arrays_or_full_fft_keys(item)


def _assert_s1_trace(result, *, expected_tool_calls: int) -> None:
    parsed = json.loads(result.model_dump_json())
    _assert_json_tree_has_no_arrays_or_full_fft_keys(parsed)
    assert result.termination_reason in {
        "planner_finished",
        "unsupported_task",
        "max_tool_calls",
        "max_planner_retries",
        "no_progress",
        "runtime_error",
    }
    assert len(result.tool_history) == expected_tool_calls
    if result.diagnosis is not None:
        known = {item.evidence_id for item in result.evidence}
        for claim in result.diagnosis.claims:
            for ref in claim.evidence_refs:
                assert ref in known


async def _run_route(
    repository: InMemorySignalRepository,
    signal_id: str,
    planner: S1RoutePlanner,
) -> object:
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
    )
    return await runtime.run(
        signal_id=signal_id,
        user_request="Why does this signal sound distorted?",
    )


@pytest.mark.asyncio
async def test_t086_s1_clip_fs(
    repository: InMemorySignalRepository,
    full_scale_clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, full_scale_clipped_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clip_fs",
                    fault_type="clipping",
                    statement="full-scale clipping detected",
                    evidence_refs=(
                        _evidence_by_metric(context, "full_scale_detected"),
                    ),
                ),
            ),
            confidence_label="high",
        )

    planner = S1RoutePlanner(
        [CallToolDecision(call=DetectClippingCall(args=ClippingInput()), purpose="detect clipping")],
        finish,
    )
    result = await _run_route(repository, signal_id, planner)
    _assert_s1_trace(result, expected_tool_calls=1)
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"


@pytest.mark.asyncio
async def test_t087_s1_clip_subfs(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_flat_top",
                    fault_type="clipping",
                    statement="flat-top clipping detected",
                    evidence_refs=(
                        _evidence_by_metric(context, "flat_top_detected"),
                    ),
                ),
            ),
            confidence_label="high",
        )

    planner = S1RoutePlanner(
        [CallToolDecision(call=DetectClippingCall(args=ClippingInput()), purpose="detect clipping")],
        finish,
    )
    result = await _run_route(repository, signal_id, planner)
    _assert_s1_trace(result, expected_tool_calls=1)


@pytest.mark.asyncio
async def test_t088_s1_harm_after_negative_clipping(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, harmonic_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_harm",
                    fault_type="harmonic_distortion",
                    statement="harmonic distortion with elevated THD",
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                ),
            ),
            confidence_label="high",
        )

    planner = S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="rule out clipping first",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="measure harmonic distortion",
            ),
        ],
        finish,
    )
    result = await _run_route(repository, signal_id, planner)
    _assert_s1_trace(result, expected_tool_calls=2)
    assert result.observations[0].tool_name == "detect_clipping"
    assert result.observations[1].tool_name == "analyze_harmonic_distortion"


@pytest.mark.asyncio
async def test_t089_s1_harm_alternate_first_tool(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, harmonic_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_harm_alt",
                    fault_type="harmonic_distortion",
                    statement="harmonic distortion from spectrum-first route",
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                ),
            ),
            confidence_label="medium",
        )

    planner = S1RoutePlanner(
        [
            CallToolDecision(
                call=AnalyzeSpectrumCall(args=SpectrumInput(max_peaks=5)),
                purpose="inspect spectrum first",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="confirm harmonic distortion",
            ),
        ],
        finish,
    )
    result = await _run_route(repository, signal_id, planner)
    _assert_s1_trace(result, expected_tool_calls=2)
    assert result.observations[0].tool_name == "analyze_spectrum"


@pytest.mark.asyncio
async def test_t090_s1_combined(
    repository: InMemorySignalRepository,
    combined_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, combined_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clip_combined",
                    fault_type="clipping",
                    statement="clipping present",
                    evidence_refs=(_evidence_by_metric(context, "clipping_detected"),),
                ),
                DiagnosisClaim(
                    claim_id="claim_harm_combined",
                    fault_type="harmonic_distortion",
                    statement="harmonic distortion present",
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                ),
            ),
            confidence_label="high",
        )

    planner = S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="detect clipping",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="measure harmonic distortion",
            ),
        ],
        finish,
    )
    result = await _run_route(repository, signal_id, planner)
    _assert_s1_trace(result, expected_tool_calls=2)
    assert result.diagnosis is not None
    assert len(result.diagnosis.claims) == 2
    refs = {
        ref
        for claim in result.diagnosis.claims
        for ref in claim.evidence_refs
    }
    assert len(refs) == 2


@pytest.mark.asyncio
async def test_t091_s1_clean(
    repository: InMemorySignalRepository,
    sine_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, sine_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="no_supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clean",
                    fault_type="no_supported_fault",
                    statement="no supported distortion fault found",
                    evidence_refs=(_evidence_by_metric(context, "clipping_detected"),),
                ),
            ),
            confidence_label="medium",
        )

    planner = S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="check for clipping",
            ),
        ],
        finish,
    )
    result = await _run_route(repository, signal_id, planner)
    _assert_s1_trace(result, expected_tool_calls=1)
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "no_supported_fault"


@pytest.mark.asyncio
async def test_t092_s1_noise_inconclusive(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="inconclusive",
            claims=(),
            confidence_label="low",
            limitations=(
                "fundamental and harmonic analysis invalid on noise-only input",
            ),
        )

    planner = S1RoutePlanner(
        [
            CallToolDecision(
                call=EstimateFundamentalCall(args=FundamentalInput()),
                purpose="attempt fundamental on noise",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="attempt harmonic analysis on noise",
            ),
        ],
        finish,
    )
    result = await _run_route(repository, signal_id, planner)
    _assert_s1_trace(result, expected_tool_calls=2)
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    for item in result.evidence:
        if item.metric == "f0_hz":
            pytest.fail("noise case must not fabricate f0_hz evidence")
