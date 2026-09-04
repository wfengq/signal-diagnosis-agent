"""Phase 1 Tool registry and JSON-serializable input schemas."""

from pydantic import BaseModel, ConfigDict

from .contracts import (
    ClippingInput,
    ContextualDistortionInput,
    FundamentalInput,
    HarmonicDistortionInput,
    SpectrumInput,
    ToolName,
)

_TOOL_REGISTRY: tuple[tuple[ToolName, type[BaseModel], str, str], ...] = (
    (
        "detect_clipping",
        ClippingInput,
        "Detect full-scale and flat-top clipping in a selected signal segment.",
        "Use when distortion may include amplitude limiting or waveform flattening.",
    ),
    (
        "analyze_spectrum",
        SpectrumInput,
        "Summarize spectral content with compact peak and centroid metrics.",
        "Use to inspect dominant frequency content without exposing full FFT arrays.",
    ),
    (
        "estimate_fundamental",
        FundamentalInput,
        "Estimate the fundamental frequency using deterministic autocorrelation.",
        "Use when a voiced pitch estimate is needed within a configured band.",
    ),
    (
        "analyze_harmonic_distortion",
        HarmonicDistortionInput,
        "Measure harmonic components and total harmonic distortion (THD).",
        "Use when harmonic distortion metrics are required for diagnosis evidence.",
    ),
    (
        "analyze_contextual_distortion",
        ContextualDistortionInput,
        "Compare test harmonics against a trusted reference or declared single-tone context.",
        "Use in nominal_single_tone or paired_reference modes for causal harmonic growth evidence.",
    ),
)


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: ToolName
    description: str
    useful_when: str
    input_schema: dict[str, object]


def get_tool_descriptors() -> tuple[ToolDescriptor, ...]:
    return tuple(
        ToolDescriptor(
            name=name,
            description=description,
            useful_when=useful_when,
            input_schema=input_model.model_json_schema(),
        )
        for name, input_model, description, useful_when in _TOOL_REGISTRY
    )
