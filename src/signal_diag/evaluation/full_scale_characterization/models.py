"""Pydantic models for characterization manifests and pair specs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.signal.models import ChannelMode, TimeRange

Side = Literal["calibration", "validation"]
PairKind = Literal["empty", "onset_change", "aggravation_change", "blind_change"]
PairRole = Literal["old", "new"]
RowTerminalState = Literal["measured", "invalid", "generation_failed"]
PairTerminalState = Literal["measured", "invalid", "generation_failed"]


class EffectiveMaterialParams(BaseModel):
    """Per-channel effective synthesis parameters after perturbations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family: str
    f0_hz: float
    sample_rate_hz: int
    phase_rad: float
    amplitude: float | None = None
    peak: float | None = None
    level: float | None = None
    depth: float | None = None
    harmonics: tuple[tuple[int, float], ...] = ()
    m7_marked: bool = False


class SourceGroupRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group_key: str
    side: Side
    family: str
    f0_hz: float
    sample_rate_hz: int
    start_phase_rad: float
    amplitude: float | None = None
    peak: float | None = None
    level: float | None = None
    depth: float | None = None
    harmonics: tuple[tuple[int, float], ...] = ()
    m7_marked: bool = False
    m9_layout: dict[str, Any] | None = None


class EncodingSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bits: Literal[8, 16, 24, 32]
    rounding: Literal[
        "round", "trunc", "away_one_step", "toward_one_step", "random_one_step"
    ] = "round"
    step_bits: Literal[16, 24, 32] | None = None
    seed: int | None = None
    filename: str = "material.wav"


class SideGenerationSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    encoding: EncodingSpec
    effective: EffectiveMaterialParams
    sample_offset: int = 0
    gain_factor: float = 1.0
    noise_rms: float | None = None
    noise_seed: int | None = None
    phase_delta_rad: float = 0.0


class PairRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    side: Side
    kind: PairKind
    family: str
    source_group_key: str
    perturbation_code: str
    perturbation_detail: str
    range_length_s: float
    f0_hz: float
    sample_rate_hz: int
    seed: int | None = None
    old_side: SideGenerationSpec
    new_side: SideGenerationSpec
    is_combo: bool = False
    is_blind: bool = False


class ExcludedNearDuplicate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    validation_group_key: str
    max_code_delta: int


class PairExpansionTemplates(BaseModel):
    """High-level pair catalog (B.3); expanded via rules + source groups."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tolerance_codes: tuple[str, ...]
    sensitivity_codes: tuple[str, ...]
    validation_combo_codes: tuple[str, ...]
    change_codes: tuple[str, ...]
    blind_codes: tuple[str, ...]


class PlannedPairCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    by_side: dict[str, int] = Field(default_factory=dict)
    by_side_family: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_side_family_perturbation: dict[str, dict[str, dict[str, int]]] = Field(
        default_factory=dict
    )


class Manifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    round_id: str
    constants_digest: str
    source_groups: tuple[SourceGroupRecord, ...]
    pair_templates: PairExpansionTemplates
    pairs_list_sha256: str
    planned_pair_counts: PlannedPairCounts
    excluded_near_duplicates: tuple[ExcludedNearDuplicate, ...] = ()
    pairs: tuple[PairRecord, ...] = ()


class ScaleLimitExceeded(Exception):
    """Validation planned pair count exceeds the approved ratio to calibration."""


class ManifestLeakageAbort(Exception):
    """Manifest generation aborted because grids overlap on base or tolerance material."""


class SanityAbort(Exception):
    """C.2 sanity check failure; abort the characterization round."""


class MeasurementRowSpec(BaseModel):
    """One WAV × channel × range × role measurement request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    side_spec: SideGenerationSpec
    role: PairRole
    channel: ChannelMode
    time_range: TimeRange
    file_duration_s: float
    full_scale_threshold: float = 0.99
    m9_layout: dict[str, Any] | None = None


class MeasurementRow(BaseModel):
    """One row of the characterization measurement table (C.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    wav_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    channel: ChannelMode
    time_range: TimeRange
    role: PairRole
    terminal_state: RowTerminalState
    terminal_reason: str | None = None
    counted_samples: int | None = Field(default=None, ge=0)
    over_threshold_uncounted: int | None = Field(default=None, ge=0)
    state: Literal["yes", "no"] | None = None
    peak_abs: float | None = None
    analyzed_samples: int | None = Field(default=None, gt=0)
    pcm_bit_depth: Literal[8, 16, 24, 32] | None = None
    clipping_ratio: float | None = None
    clipped_samples: int | None = None
    full_scale_detected: bool | None = None
    flat_top_detected: bool | None = None
    clipping_mechanism: bool | None = None
    bundle_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    facts_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    harmonic_tool_status: str | None = None


class MeasuredPair(BaseModel):
    """Pair-level scoring record referencing measurement rows (C.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    channel: ChannelMode
    range_length_s: float
    old_row: MeasurementRow
    new_row: MeasurementRow
    count_diff: int | None = None
    ratio_diff: float | None = None
    flip: bool | None = None
    terminal_state: PairTerminalState
    terminal_reason: str | None = None
