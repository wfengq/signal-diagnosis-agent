"""Compact Tool contracts, Evidence, and registry."""

from .contracts import (
    ClippingInput,
    ClippingOutput,
    FundamentalInput,
    FundamentalOutput,
    HarmonicComponentOutput,
    HarmonicDistortionInput,
    HarmonicDistortionOutput,
    SignalSelection,
    SpectrumInput,
    SpectrumOutput,
    SpectrumPeakOutput,
    ToolName,
)
from .evidence import Evidence, EvidenceValidity, EvidenceValue
from .registry import ToolDescriptor, get_tool_descriptors
from .results import ToolResult, ToolStatus
from .service import SignalToolService

__all__ = [
    "ClippingInput",
    "ClippingOutput",
    "Evidence",
    "EvidenceValidity",
    "EvidenceValue",
    "FundamentalInput",
    "FundamentalOutput",
    "HarmonicComponentOutput",
    "HarmonicDistortionInput",
    "HarmonicDistortionOutput",
    "SignalSelection",
    "SignalToolService",
    "SpectrumInput",
    "SpectrumOutput",
    "SpectrumPeakOutput",
    "ToolDescriptor",
    "ToolName",
    "ToolResult",
    "ToolStatus",
    "get_tool_descriptors",
]
