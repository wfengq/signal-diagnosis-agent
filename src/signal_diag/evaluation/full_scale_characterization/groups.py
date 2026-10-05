"""Source-group enumeration for calibration and validation sides."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from signal_diag.evaluation.full_scale_characterization.constants import (
    CharacterizationConstants,
    HarmonicSet,
    M9ChannelLayout,
)
from signal_diag.evaluation.full_scale_characterization.materials import (
    compute_m7_marked,
)
from signal_diag.evaluation.full_scale_characterization.models import SourceGroupRecord

Side = Literal["calibration", "validation"]


@dataclass(frozen=True)
class _GroupDraft:
    side: Side
    family: str
    f0_hz: float
    sample_rate_hz: int
    start_phase_rad: float
    amplitude: float | None = None
    peak: float | None = None
    level: float | None = None
    depth: float | None = None
    harmonics: HarmonicSet | None = None
    m9_layout: M9ChannelLayout | None = None

    def group_key(self) -> str:
        payload = {
            "family": self.family,
            "f0_hz": self.f0_hz,
            "sr": self.sample_rate_hz,
            "phase": self.start_phase_rad,
            "amplitude": self.amplitude,
            "peak": self.peak,
            "level": self.level,
            "depth": self.depth,
            "harmonics": self.harmonics.coefficients if self.harmonics else (),
            "m9": self.m9_layout.model_dump(mode="json") if self.m9_layout else None,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def to_record(self, *, threshold: float, duration_s: float) -> SourceGroupRecord:
        harmonics = self.harmonics.coefficients if self.harmonics else ()
        m7 = False
        if self.family in {"M3", "M4"} and self.level is not None and self.depth is not None:
            m7 = compute_m7_marked(
                family=self.family,
                f0_hz=self.f0_hz,
                sample_rate_hz=self.sample_rate_hz,
                level=self.level,
                depth=self.depth,
                duration_s=duration_s,
                phase_rad=self.start_phase_rad,
                threshold=threshold,
            )
        return SourceGroupRecord(
            group_key=self.group_key(),
            side=self.side,
            family=self.family,
            f0_hz=self.f0_hz,
            sample_rate_hz=self.sample_rate_hz,
            start_phase_rad=self.start_phase_rad,
            amplitude=self.amplitude,
            peak=self.peak,
            level=self.level,
            depth=self.depth,
            harmonics=harmonics,
            m7_marked=m7,
            m9_layout=self.m9_layout.model_dump(mode="json") if self.m9_layout else None,
        )


def _dedupe(drafts: Iterator[_GroupDraft]) -> list[_GroupDraft]:
    seen: set[str] = set()
    out: list[_GroupDraft] = []
    for draft in drafts:
        key = draft.group_key()
        if key in seen:
            continue
        seen.add(key)
        out.append(draft)
    return out


def _calibration_m1(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.calibration_f0:
            for amp in c.m1_calibration_amplitudes:
                yield _GroupDraft("calibration", "M1", f0, sr, 0.0, amplitude=amp)


def _calibration_m2(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.calibration_f0:
            for peak in c.m2_calibration_peaks:
                for phase in c.calibration_start_phases_rad:
                    yield _GroupDraft("calibration", "M2", f0, sr, phase, peak=peak)


def _calibration_m3(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.calibration_f0:
            for level in c.m3_calibration_levels:
                for depth in c.m3_calibration_depths:
                    for phase in c.calibration_start_phases_rad:
                        yield _GroupDraft(
                            "calibration", "M3", f0, sr, phase, level=level, depth=depth
                        )


def _calibration_m4(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.calibration_f0:
            for level in c.m4_calibration_levels:
                for depth in c.m4_calibration_depths:
                    yield _GroupDraft("calibration", "M4", f0, sr, 0.0, level=level, depth=depth)


def _calibration_m5(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.calibration_f0:
            for harm in c.m5_calibration_harmonics:
                for level in c.m5_calibration_levels:
                    for depth in c.m5_calibration_depths:
                        for phase in c.calibration_start_phases_rad:
                            yield _GroupDraft(
                                "calibration",
                                "M5",
                                f0,
                                sr,
                                phase,
                                level=level,
                                depth=depth,
                                harmonics=harm,
                            )


def _calibration_m6(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.calibration_f0:
            for harm in c.m6_calibration_harmonics:
                yield _GroupDraft(
                    "calibration", "M6", f0, sr, 0.0, harmonics=harm
                )


def _calibration_m9(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.calibration_f0:
            for layout in c.m9_calibration_layouts:
                yield _GroupDraft(
                    "calibration", "M9", f0, sr, 0.0, m9_layout=layout
                )


def _validation_m1(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    fixed_amps = c.m1_calibration_amplitudes
    for sr in c.sample_rates:
        for f0 in c.validation_fixed_f0:
            for amp in c.m1_validation_amplitudes_heldout:
                yield _GroupDraft("validation", "M1", f0, sr, 0.0, amplitude=amp)
        for f0 in c.validation_f0_heldout:
            for amp in fixed_amps:
                yield _GroupDraft("validation", "M1", f0, sr, 0.0, amplitude=amp)
        for f0 in c.validation_f0_heldout:
            for amp in c.m1_validation_amplitudes_heldout:
                yield _GroupDraft("validation", "M1", f0, sr, 0.0, amplitude=amp)


def _validation_m2(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.validation_fixed_f0:
            for peak in c.m2_validation_peaks_heldout:
                for phase in c.validation_fixed_start_phases_rad:
                    yield _GroupDraft("validation", "M2", f0, sr, phase, peak=peak)
            for peak in c.validation_fixed_m2_peaks:
                for phase in c.validation_start_phases_heldout_rad:
                    yield _GroupDraft("validation", "M2", f0, sr, phase, peak=peak)
        for f0 in c.validation_f0_heldout:
            for peak in c.m2_validation_peaks_heldout:
                yield _GroupDraft("validation", "M2", f0, sr, 0.0, peak=peak)


def _validation_m3(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.validation_fixed_f0:
            for level in c.m3_validation_levels_heldout:
                for depth in c.validation_fixed_m3_depths:
                    for phase in c.validation_fixed_start_phases_rad:
                        yield _GroupDraft(
                            "validation", "M3", f0, sr, phase, level=level, depth=depth
                        )
            for depth in c.m3_validation_depths_heldout:
                for level in c.validation_fixed_m3_levels:
                    for phase in c.validation_fixed_start_phases_rad:
                        yield _GroupDraft(
                            "validation", "M3", f0, sr, phase, level=level, depth=depth
                        )
            for phase in c.validation_start_phases_heldout_rad:
                for level in c.validation_fixed_m3_levels:
                    for depth in c.validation_fixed_m3_depths:
                        yield _GroupDraft(
                            "validation", "M3", f0, sr, phase, level=level, depth=depth
                        )
        for f0 in c.validation_f0_heldout:
            for level in c.m3_validation_levels_heldout:
                for depth in c.validation_fixed_m3_depths:
                    yield _GroupDraft("validation", "M3", f0, sr, 0.0, level=level, depth=depth)
            for depth in c.m3_validation_depths_heldout:
                for level in c.validation_fixed_m3_levels:
                    yield _GroupDraft("validation", "M3", f0, sr, 0.0, level=level, depth=depth)


def _validation_m4(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.validation_fixed_f0:
            for level in c.m4_validation_levels_heldout:
                for depth in c.validation_fixed_m4_depths:
                    yield _GroupDraft("validation", "M4", f0, sr, 0.0, level=level, depth=depth)
            for depth in c.m4_validation_depths_heldout:
                for level in c.validation_fixed_m4_levels:
                    yield _GroupDraft("validation", "M4", f0, sr, 0.0, level=level, depth=depth)
        for f0 in c.validation_f0_heldout:
            for level in c.m4_validation_levels_heldout:
                for depth in c.validation_fixed_m4_depths:
                    yield _GroupDraft("validation", "M4", f0, sr, 0.0, level=level, depth=depth)


def _validation_m5(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.validation_fixed_f0:
            for harm in c.m5_validation_harmonics_heldout:
                for level in c.validation_fixed_m5_levels:
                    for depth in c.validation_fixed_m5_depths:
                        for phase in c.validation_fixed_start_phases_rad:
                            yield _GroupDraft(
                                "validation",
                                "M5",
                                f0,
                                sr,
                                phase,
                                level=level,
                                depth=depth,
                                harmonics=harm,
                            )
            for depth in c.m5_validation_depths_heldout:
                for harm in c.validation_fixed_m5_harmonics:
                    for level in c.validation_fixed_m5_levels:
                        for phase in c.validation_fixed_start_phases_rad:
                            yield _GroupDraft(
                                "validation",
                                "M5",
                                f0,
                                sr,
                                phase,
                                level=level,
                                depth=depth,
                                harmonics=harm,
                            )
            for phase in c.validation_start_phases_heldout_rad:
                for harm in c.validation_fixed_m5_harmonics:
                    for level in c.validation_fixed_m5_levels:
                        for depth in c.validation_fixed_m5_depths:
                            yield _GroupDraft(
                                "validation",
                                "M5",
                                f0,
                                sr,
                                phase,
                                level=level,
                                depth=depth,
                                harmonics=harm,
                            )
        for f0 in c.validation_f0_heldout:
            for harm in c.m5_validation_harmonics_heldout:
                for depth in c.validation_fixed_m5_depths:
                    for level in c.validation_fixed_m5_levels:
                        yield _GroupDraft(
                            "validation",
                            "M5",
                            f0,
                            sr,
                            0.0,
                            level=level,
                            depth=depth,
                            harmonics=harm,
                        )


def _validation_m6(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.validation_fixed_f0:
            for harm in c.m6_validation_harmonics:
                yield _GroupDraft("validation", "M6", f0, sr, 0.0, harmonics=harm)
        for f0 in c.validation_f0_heldout:
            for harm in c.m6_calibration_harmonics:
                yield _GroupDraft("validation", "M6", f0, sr, 0.0, harmonics=harm)
            for harm in c.m6_validation_harmonics:
                yield _GroupDraft("validation", "M6", f0, sr, 0.0, harmonics=harm)


def _validation_m9(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    for sr in c.sample_rates:
        for f0 in c.m9_validation_f0_only:
            for layout in c.m9_validation_layouts:
                yield _GroupDraft("validation", "M9", f0, sr, 0.0, m9_layout=layout)


def enumerate_source_groups(c: CharacterizationConstants) -> tuple[SourceGroupRecord, ...]:
    cal_funcs = [
        _calibration_m1,
        _calibration_m2,
        _calibration_m3,
        _calibration_m4,
        _calibration_m5,
        _calibration_m6,
        _calibration_m9,
    ]
    val_funcs = [
        _validation_m1,
        _validation_m2,
        _validation_m3,
        _validation_m4,
        _validation_m5,
        _validation_m6,
        _validation_m9,
    ]
    cal_drafts: list[_GroupDraft] = []
    for func in cal_funcs:
        cal_drafts.extend(_dedupe(func(c)))
    cal_keys = {d.group_key() for d in cal_drafts}

    val_drafts: list[_GroupDraft] = []
    for func in val_funcs:
        for draft in _dedupe(func(c)):
            if draft.group_key() in cal_keys:
                continue
            val_drafts.append(draft)

    drafts = cal_drafts + val_drafts
    records = [
        d.to_record(threshold=c.full_scale_threshold, duration_s=c.file_duration_s) for d in drafts
    ]
    return tuple(sorted(records, key=lambda r: (r.side, r.group_key)))
