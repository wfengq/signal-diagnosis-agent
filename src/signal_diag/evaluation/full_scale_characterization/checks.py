"""C.2 sanity checks for characterization rounds (T-CX376).

Any failure raises :class:`SanityAbort` naming the pair and the check item; the
round must then stop without a report.  P9 flips outside the fixed minimum
(C.3, k = 1) do not abort; they are counted for the report (A.10, OQ-022).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

import numpy as np
from pydantic import BaseModel, ConfigDict

from signal_diag.dsp.full_scale import count_full_scale_samples
from signal_diag.evaluation.full_scale_characterization.constants import M9ChannelLayout
from signal_diag.evaluation.full_scale_characterization.executor import (
    MeasurementCache,
    _encode_side,
    measure_row,
    row_specs_for_pair,
)
from signal_diag.evaluation.full_scale_characterization.gate import (
    require_validation_access,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    MeasuredPair,
    MeasurementRow,
    PairRecord,
    PairRole,
    SanityAbort,
    SideGenerationSpec,
)
from signal_diag.evaluation.full_scale_characterization.pairs import TOLERANCE_CODES
from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.signal.segment import extract_segment
from signal_diag.signal.wav import load_wav_bytes
from signal_diag.tools.regression_full_scale import FULL_SCALE_MIN_CONSECUTIVE_SAMPLES

CHECK_P0 = "C.2#1 P0 identity"
CHECK_SANDWICH = "C.2#2 tolerance sandwich"
CHECK_P7_EQUALITY = "C.2#3 one-step worst-case equality"
CHECK_P7_FLIP = "C.2#4 one-step flip outside fixed minimum"
CHECK_FACTS = "C.2#5 verify_full_scale_facts"

P7_CODES = frozenset({"P7a", "P7b", "P7c", "P7d"})
P9_CODES = frozenset({"P9a", "P9b", "P9c"})

_TOLERANCE_STEP: dict[int, float] = {16: 2.0**-15, 24: 2.0**-23, 32: 2.0**-24}


class P9FlipCounts(BaseModel):
    """C.3 report input: P9 flips and those outside the k = 1 / k = 2 fixed minimum."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    flips_by_code: dict[str, int]
    out_of_zone_k1_by_code: dict[str, int]
    out_of_zone_k2_by_code: dict[str, int]

    @property
    def out_of_zone_k1_total(self) -> int:
        return sum(self.out_of_zone_k1_by_code.values())

    @property
    def out_of_zone_k2_total(self) -> int:
        return sum(self.out_of_zone_k2_by_code.values())


def coarser_bit_depth(pair: PairRecord) -> int:
    return min(pair.old_side.encoding.bits, pair.new_side.encoding.bits)


def tolerance_step(bits: int) -> float:
    """C.2 delta: one coarser-depth step (16: 2^-15, 24: 2^-23, 32: 2^-24)."""
    try:
        return _TOLERANCE_STEP[bits]
    except KeyError as error:
        raise ValueError(f"no tolerance step for {bits}-bit PCM") from error


def product_quantization_step(bits: int) -> float:
    """C.3 step, verbatim with the product: max(2^-(b-1), 2^-24)."""
    return max(2.0 ** -(bits - 1), 2.0**-24)


def _abort(pair: PairRecord, channel: ChannelMode, check: str, detail: str) -> SanityAbort:
    return SanityAbort(
        f"sanity abort [{check}] pair_id={pair.pair_id} "
        f"code={pair.perturbation_code} detail={pair.perturbation_detail} "
        f"channel={channel}: {detail}"
    )


def measure_pair_checked(
    pair: PairRecord,
    *,
    file_duration_s: float,
    full_scale_threshold: float,
    m9_layout: dict[str, Any] | None,
    cache: MeasurementCache | None = None,
    validation_access: object = None,
) -> dict[tuple[PairRole, ChannelMode], MeasurementRow]:
    """Measure every row of a pair; re-raise facts-verification aborts (C.2#5) with the pair id.

    ``executor.measure_row`` already converts a ``verify_full_scale_facts`` failure
    into :class:`SanityAbort`; this wrapper is the call site that names the pair.
    """
    rows: dict[tuple[PairRole, ChannelMode], MeasurementRow] = {}
    for spec in row_specs_for_pair(
        pair,
        file_duration_s=file_duration_s,
        full_scale_threshold=full_scale_threshold,
        m9_layout=m9_layout,
        validation_access=validation_access,
    ):
        try:
            rows[(spec.role, spec.channel)] = measure_row(spec, cache=cache)
        except SanityAbort as error:
            raise _abort(pair, spec.channel, CHECK_FACTS, f"role={spec.role}: {error}") from error
    return rows


def _decoded_segment(
    side: SideGenerationSpec,
    *,
    channel: ChannelMode,
    time_range: TimeRange,
    file_duration_s: float,
    m9_layout: dict[str, Any] | None,
) -> np.ndarray:
    layout = M9ChannelLayout.model_validate(m9_layout) if m9_layout is not None else None
    wav_bytes = _encode_side(side, file_duration_s=file_duration_s, m9_layout=layout)
    loaded = load_wav_bytes(wav_bytes, filename=side.encoding.filename)
    return extract_segment(loaded.record, time_range=time_range, channel=channel)


def _count(samples: np.ndarray, threshold: float) -> int:
    return count_full_scale_samples(
        samples,
        full_scale_threshold=threshold,
        min_consecutive_samples=FULL_SCALE_MIN_CONSECUTIVE_SAMPLES,
    ).counted_samples


def _no_side_peak(measured: MeasuredPair) -> float:
    no_row = measured.old_row if measured.old_row.state == "no" else measured.new_row
    assert no_row.peak_abs is not None
    return no_row.peak_abs


def _check_p0(pair: PairRecord, measured: MeasuredPair) -> None:
    if measured.old_row.wav_sha256 != measured.new_row.wav_sha256:
        raise _abort(
            pair,
            measured.channel,
            CHECK_P0,
            f"wav_sha256 old={measured.old_row.wav_sha256} new={measured.new_row.wav_sha256}",
        )
    if measured.count_diff is not None and measured.count_diff != 0:
        raise _abort(pair, measured.channel, CHECK_P0, f"count_diff={measured.count_diff}")


def _check_counts(
    pair: PairRecord,
    measured: MeasuredPair,
    *,
    file_duration_s: float,
    full_scale_threshold: float,
    m9_layout: dict[str, Any] | None,
) -> None:
    """C.2#2 sandwich and C.2#3 equalities, with the old side as reference x."""
    code = pair.perturbation_code
    delta = tolerance_step(coarser_bit_depth(pair))
    delta_prime = 2.0 * delta if code in P9_CODES else delta
    x = _decoded_segment(
        pair.old_side,
        channel=measured.channel,
        time_range=TimeRange(start_s=0.0, end_s=pair.range_length_s),
        file_duration_s=file_duration_s,
        m9_layout=m9_layout,
    )
    count_y = measured.new_row.counted_samples
    assert count_y is not None
    lower = _count(x, full_scale_threshold + delta_prime)
    upper = _count(x, full_scale_threshold - delta_prime)
    if not lower <= count_y <= upper:
        raise _abort(
            pair,
            measured.channel,
            CHECK_SANDWICH,
            f"count(x, thr+{delta_prime!r})={lower} <= count(y)={count_y} "
            f"<= count(x, thr-{delta_prime!r})={upper} violated",
        )
    if code == "P7a":
        expected = _count(x, full_scale_threshold - delta)
    elif code == "P7b":
        expected = _count(x, full_scale_threshold + delta)
    else:
        return
    if count_y != expected:
        raise _abort(
            pair,
            measured.channel,
            CHECK_P7_EQUALITY,
            f"count(y)={count_y} != expected {expected} (delta={delta!r})",
        )


def _check_p7_flip(pair: PairRecord, measured: MeasuredPair, *, full_scale_threshold: float) -> None:
    if not measured.flip:
        return
    step = product_quantization_step(coarser_bit_depth(pair))
    peak = _no_side_peak(measured)
    if peak < full_scale_threshold - step:
        raise _abort(
            pair,
            measured.channel,
            CHECK_P7_FLIP,
            f"no-side peak_abs={peak!r} < thr - step={full_scale_threshold - step!r}",
        )


def p9_out_of_zone_flip_counts(
    items: Iterable[tuple[PairRecord, MeasuredPair]],
    *,
    full_scale_threshold: float,
) -> P9FlipCounts:
    """Count P9 flips and those whose "no" side lies outside thr - k*step (k = 1, 2)."""
    flips: dict[str, int] = {}
    out_k1: dict[str, int] = {}
    out_k2: dict[str, int] = {}
    for pair, measured in items:
        code = pair.perturbation_code
        if code not in P9_CODES or measured.terminal_state != "measured" or not measured.flip:
            continue
        flips[code] = flips.get(code, 0) + 1
        step = product_quantization_step(coarser_bit_depth(pair))
        peak = _no_side_peak(measured)
        if peak < full_scale_threshold - step:
            out_k1[code] = out_k1.get(code, 0) + 1
        if peak < full_scale_threshold - 2.0 * step:
            out_k2[code] = out_k2.get(code, 0) + 1
    return P9FlipCounts(
        flips_by_code=dict(sorted(flips.items())),
        out_of_zone_k1_by_code=dict(sorted(out_k1.items())),
        out_of_zone_k2_by_code=dict(sorted(out_k2.items())),
    )


def run_sanity_checks(
    items: Iterable[tuple[PairRecord, MeasuredPair]],
    *,
    file_duration_s: float,
    full_scale_threshold: float,
    m9_layouts: Mapping[str, dict[str, Any]] | None = None,
    validation_access: object = None,
) -> P9FlipCounts:
    """Apply C.2 checks 1–4 to measured pair records; return P9 flip counts (C.3).

    Check 5 is enforced at measurement time by :func:`measure_pair_checked`.
    Only tolerance-class pairs are checked; sensitivity, combo and change pairs are
    disclosure-only.
    """
    materialized = list(items)
    if any(pair.side == "validation" for pair, _ in materialized):
        require_validation_access(validation_access, what="sanity-check validation pairs")
    layouts = m9_layouts or {}
    for pair, measured in materialized:
        if pair.pair_id != measured.pair_id:
            raise ValueError(
                f"pair record {pair.pair_id} does not match measured pair {measured.pair_id}"
            )
        code = pair.perturbation_code
        if code not in TOLERANCE_CODES:
            continue
        if code == "P0":
            _check_p0(pair, measured)
        if measured.terminal_state != "measured":
            continue
        _check_counts(
            pair,
            measured,
            file_duration_s=file_duration_s,
            full_scale_threshold=full_scale_threshold,
            m9_layout=cast(dict[str, Any] | None, layouts.get(pair.pair_id)),
        )
        if code in P7_CODES:
            _check_p7_flip(pair, measured, full_scale_threshold=full_scale_threshold)
    return p9_out_of_zone_flip_counts(materialized, full_scale_threshold=full_scale_threshold)
