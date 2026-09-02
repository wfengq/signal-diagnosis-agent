"""Models owned by evaluator-only reference analysis."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReferenceAnalyzerVersion = Literal["1.0.0", "1.1.0"]
REFERENCE_ANALYZER_VERSION_V02: Literal["1.0.0"] = "1.0.0"
REFERENCE_ANALYZER_VERSION_V03: Literal["1.1.0"] = "1.1.0"


class ReferenceSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    reference_analyzer_id: Literal["signal_diag.external_reference"] = (
        "signal_diag.external_reference"
    )
    reference_analyzer_version: ReferenceAnalyzerVersion = REFERENCE_ANALYZER_VERSION_V02
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    applicable: bool
    clipping_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    flat_top_detected: bool | None = None
    f0_hz: float | None = Field(default=None, gt=0.0)
    thd_percent: float | None = Field(default=None, ge=0.0)
    order_2_relative_amplitude: float | None = Field(default=None, ge=0.0)
