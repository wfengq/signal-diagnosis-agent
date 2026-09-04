"""Immutable stimulus-context models for V0.3 contextual diagnosis."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DiagnosticMode = Literal["single_signal", "nominal_single_tone", "paired_reference"]
ContextAssertionSource = Literal["user_supplied", "evaluation_manifest"]


class StimulusContext(BaseModel):
    """Declared stimulus provenance — not numerical Evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    mode: DiagnosticMode
    test_signal_id: str = Field(min_length=1)
    reference_signal_id: str | None = None
    nominal_fundamental_hz: float | None = Field(default=None, gt=0.0)
    stimulus_kind: Literal["single_tone"] | None = None
    assertion_source: ContextAssertionSource

    @model_validator(mode="after")
    def validate_mode_matrix(self) -> StimulusContext:
        if self.mode == "single_signal":
            if self.reference_signal_id is not None:
                raise ValueError("single_signal rejects reference_signal_id")
            if self.nominal_fundamental_hz is not None:
                raise ValueError("single_signal rejects nominal_fundamental_hz")
            if self.stimulus_kind is not None:
                raise ValueError("single_signal rejects stimulus_kind")
            return self
        if self.mode == "nominal_single_tone":
            if self.reference_signal_id is not None:
                raise ValueError("nominal_single_tone rejects reference_signal_id")
            if self.stimulus_kind != "single_tone":
                raise ValueError("nominal_single_tone requires stimulus_kind=single_tone")
            if self.nominal_fundamental_hz is None:
                raise ValueError("nominal_single_tone requires nominal_fundamental_hz")
            return self
        # paired_reference
        if self.reference_signal_id is None:
            raise ValueError("paired_reference requires reference_signal_id")
        if self.reference_signal_id == self.test_signal_id:
            raise ValueError("paired_reference requires a distinct reference_signal_id")
        if self.stimulus_kind is not None and self.stimulus_kind != "single_tone":
            raise ValueError("paired_reference stimulus_kind must be single_tone when set")
        if self.stimulus_kind == "single_tone" and self.nominal_fundamental_hz is None:
            raise ValueError(
                "paired_reference with stimulus_kind=single_tone requires "
                "nominal_fundamental_hz"
            )
        return self


class EffectiveCapabilities(BaseModel):
    """Requested-mode capabilities after qualification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    clipping: bool = True
    absolute_harmonic_description: bool = True
    nominal_harmonic_attribution: bool = False
    paired_harmonic_attribution: bool = False
