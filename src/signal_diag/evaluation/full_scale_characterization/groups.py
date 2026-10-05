"""Source-group enumeration for calibration and validation sides."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Literal

from signal_diag.evaluation.full_scale_characterization.constants import (
    CharacterizationConstants,
    HarmonicSet,
    M9ChannelLayout,
)
from signal_diag.evaluation.full_scale_characterization.materials import (
    compute_m7_marked,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    EffectiveMaterialParams,
    SourceGroupRecord,
)

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
        if self.family in {"M2", "M3", "M5"}:
            m7 = compute_m7_marked(
                EffectiveMaterialParams(
                    family=self.family,
                    f0_hz=self.f0_hz,
                    sample_rate_hz=self.sample_rate_hz,
                    phase_rad=self.start_phase_rad,
                    peak=self.peak,
                    level=self.level,
                    depth=self.depth,
                    harmonics=harmonics,
                ),
                duration_s=duration_s,
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


_Dim = tuple[str, tuple, tuple]  # (name, fixed subset, held-out values)


def _validation_grid(
    c: CharacterizationConstants,
    *,
    family: str,
    level_dims: list[_Dim],
    has_phase: bool,
    make: Callable[[float, int, float, dict[str, Any]], _GroupDraft],
) -> Iterator[_GroupDraft]:
    """Plan B.2 validation sub-grid for one family.

    Rule 1: exactly one dimension (f0, phase where applicable, or one clipping
    dimension) takes a held-out value; all others take the fixed subset.
    Rule 2: f0 held out and at least one clipping dimension held out; the other
    clipping dimensions fixed; phase 0.
    """
    phases_fixed = c.validation_fixed_start_phases_rad if has_phase else (0.0,)
    f0_fixed = c.validation_fixed_f0
    f0_held = c.validation_f0_heldout

    def combos(held: frozenset[str]) -> Iterator[dict[str, Any]]:
        pools = [(name, held_vals if name in held else fixed) for name, fixed, held_vals in level_dims]

        def rec(i: int, acc: dict[str, Any]) -> Iterator[dict[str, Any]]:
            if i == len(pools):
                yield dict(acc)
                return
            name, values = pools[i]
            for v in values:
                acc[name] = v
                yield from rec(i + 1, acc)
            acc.pop(name, None)

        yield from rec(0, {})

    for sr in c.sample_rates:
        # Rule 1, one clipping dimension held out.
        for name, _fixed, _held in level_dims:
            for f0 in f0_fixed:
                for phase in phases_fixed:
                    for values in combos(frozenset({name})):
                        yield make(f0, sr, phase, values)
        # Rule 1, phase held out.
        if has_phase:
            for f0 in f0_fixed:
                for phase in c.validation_start_phases_heldout_rad:
                    for values in combos(frozenset()):
                        yield make(f0, sr, phase, values)
        # Rule 1, f0 held out.
        for f0 in f0_held:
            for phase in phases_fixed:
                for values in combos(frozenset()):
                    yield make(f0, sr, phase, values)
        # Rule 2: f0 held out and a non-empty set of clipping dimensions held out.
        names = [name for name, _f, _h in level_dims]
        subsets = [
            frozenset(n for j, n in enumerate(names) if mask >> j & 1)
            for mask in range(1, 1 << len(names))
        ]
        for f0 in f0_held:
            for held in subsets:
                for values in combos(held):
                    yield make(f0, sr, 0.0, values)


def _validation_m1(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    yield from _validation_grid(
        c,
        family="M1",
        level_dims=[("amp", c.m1_calibration_amplitudes, c.m1_validation_amplitudes_heldout)],
        has_phase=False,
        make=lambda f0, sr, ph, v: _GroupDraft("validation", "M1", f0, sr, ph, amplitude=v["amp"]),
    )


def _validation_m2(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    yield from _validation_grid(
        c,
        family="M2",
        level_dims=[("peak", c.validation_fixed_m2_peaks, c.m2_validation_peaks_heldout)],
        has_phase=True,
        make=lambda f0, sr, ph, v: _GroupDraft("validation", "M2", f0, sr, ph, peak=v["peak"]),
    )


def _validation_m3(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    yield from _validation_grid(
        c,
        family="M3",
        level_dims=[
            ("level", c.validation_fixed_m3_levels, c.m3_validation_levels_heldout),
            ("depth", c.validation_fixed_m3_depths, c.m3_validation_depths_heldout),
        ],
        has_phase=True,
        make=lambda f0, sr, ph, v: _GroupDraft(
            "validation", "M3", f0, sr, ph, level=v["level"], depth=v["depth"]
        ),
    )


def _validation_m4(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    yield from _validation_grid(
        c,
        family="M4",
        level_dims=[
            ("level", c.validation_fixed_m4_levels, c.m4_validation_levels_heldout),
            ("depth", c.validation_fixed_m4_depths, c.m4_validation_depths_heldout),
        ],
        has_phase=False,
        make=lambda f0, sr, ph, v: _GroupDraft(
            "validation", "M4", f0, sr, ph, level=v["level"], depth=v["depth"]
        ),
    )


def _validation_m5(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    # The M5 level is not held out (B.2): both fixed levels are crossed with every combination.
    yield from _validation_grid(
        c,
        family="M5",
        level_dims=[
            ("harm", c.validation_fixed_m5_harmonics, c.m5_validation_harmonics_heldout),
            ("depth", c.validation_fixed_m5_depths, c.m5_validation_depths_heldout),
            ("level", c.validation_fixed_m5_levels, ()),
        ],
        has_phase=True,
        make=lambda f0, sr, ph, v: _GroupDraft(
            "validation",
            "M5",
            f0,
            sr,
            ph,
            level=v["level"],
            depth=v["depth"],
            harmonics=v["harm"],
        ),
    )


def _validation_m6(c: CharacterizationConstants) -> Iterator[_GroupDraft]:
    yield from _validation_grid(
        c,
        family="M6",
        level_dims=[("harm", c.m6_calibration_harmonics, c.m6_validation_harmonics)],
        has_phase=False,
        make=lambda f0, sr, ph, v: _GroupDraft("validation", "M6", f0, sr, ph, harmonics=v["harm"]),
    )


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
