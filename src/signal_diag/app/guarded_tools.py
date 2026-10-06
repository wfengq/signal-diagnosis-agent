"""Product tool service with the D049 F0 subharmonic guard turned on."""

from __future__ import annotations

from signal_diag.dsp.pitch import subharmonic_guard_enabled
from signal_diag.signal.context import StimulusContext
from signal_diag.tools.contracts import (
    ContextualDistortionInput,
    ContextualDistortionOutput,
    FundamentalInput,
    FundamentalOutput,
    HarmonicDistortionInput,
    HarmonicDistortionOutput,
)
from signal_diag.tools.results import ToolResult
from signal_diag.tools.service import SignalToolService


class GuardedSignalToolService(SignalToolService):
    """Runs the F0-dependent tools with the subharmonic guard on.

    It adds no measurement logic: it only scopes the guard around the base
    tools. ``SignalToolService`` (T-CX351) and the Phase 1–4.3.1 ``tools/`` tree
    (T285) are frozen, so the scope lives here. Evaluation runners and the
    regression workbench keep the base class and the pre-D049 estimator.
    """

    def estimate_fundamental(
        self,
        signal_id: str,
        args: FundamentalInput,
    ) -> ToolResult[FundamentalOutput]:
        with subharmonic_guard_enabled():
            return super().estimate_fundamental(signal_id, args)

    def analyze_harmonic_distortion(
        self,
        signal_id: str,
        args: HarmonicDistortionInput,
    ) -> ToolResult[HarmonicDistortionOutput]:
        with subharmonic_guard_enabled():
            return super().analyze_harmonic_distortion(signal_id, args)

    def analyze_contextual_distortion(
        self,
        context: StimulusContext,
        args: ContextualDistortionInput,
    ) -> ToolResult[ContextualDistortionOutput]:
        with subharmonic_guard_enabled():
            return super().analyze_contextual_distortion(context, args)
