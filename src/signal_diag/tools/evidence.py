"""Deterministic Evidence records produced by Tool adapters."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.signal.models import ChannelMode, TimeRange

from .contracts import ToolName

EvidenceValue = bool | int | float | str
EvidenceValidity = Literal["valid", "not_applicable"]


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(pattern=r"^ev_")
    source_tool: ToolName
    call_id: str = Field(pattern=r"^call_")
    metric: str = Field(min_length=1)
    value: EvidenceValue
    unit: str | None = None
    validity: EvidenceValidity = "valid"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    time_range: TimeRange | None = None
    channel: ChannelMode
