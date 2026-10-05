"""Leakage checks and near-duplicate exclusion for manifest generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from signal_diag.evaluation.full_scale_characterization.constants import (
    CharacterizationConstants,
    M9ChannelLayout,
)
from signal_diag.evaluation.full_scale_characterization.materials import (
    _layout_channel_params,
    channel_effectives_from_group,
    codes_for_analysis_range,
    normalize_phase,
    params_from_group_record,
    synthesize_mono,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    EffectiveMaterialParams,
    EncodingSpec,
    ExcludedNearDuplicate,
    ManifestLeakageAbort,
    PairRecord,
    SideGenerationSpec,
    SourceGroupRecord,
)
from signal_diag.evaluation.full_scale_characterization.pairs import (
    TOLERANCE_CODES,
    _pairs_for_group,
    _r0_description_batches,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

ParamBucketKey = tuple[str, float, int, float]

_WAVE_CACHE: dict[tuple, NDArray[np.float64]] = {}


def clear_wave_cache() -> None:
    _WAVE_CACHE.clear()


def _bucket_key(params) -> ParamBucketKey:
    return (
        params.family,
        params.f0_hz,
        params.sample_rate_hz,
        normalize_phase(params.phase_rad),
    )


def _cache_key_for_side(side_spec: SideGenerationSpec, *, duration_s: float) -> tuple:
    eff = side_spec.effective
    return (
        eff.family,
        eff.f0_hz,
        eff.sample_rate_hz,
        normalize_phase(eff.phase_rad),
        eff.amplitude,
        eff.peak,
        eff.level,
        eff.depth,
        eff.harmonics,
        duration_s,
        side_spec.sample_offset,
        side_spec.gain_factor,
        side_spec.noise_rms,
        side_spec.noise_seed,
        side_spec.phase_delta_rad,
    )


def _side_wave_cached(
    side_spec: SideGenerationSpec,
    *,
    duration_s: float,
) -> NDArray[np.float64]:
    key = _cache_key_for_side(side_spec, duration_s=duration_s)
    cached = _WAVE_CACHE.get(key)
    if cached is not None:
        return cached
    wave = synthesize_mono(
        side_spec.effective,
        duration_s=duration_s,
        sample_offset=side_spec.sample_offset,
        gain_factor=side_spec.gain_factor,
        noise_rms=side_spec.noise_rms,
        noise_seed=side_spec.noise_seed,
    )
    _WAVE_CACHE[key] = wave
    return wave


def _analysis_segment(
    wave: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> NDArray[np.float64]:
    n = round(range_length_s * sample_rate_hz)
    n = min(n, wave.shape[0])
    return wave[:n]


def max_abs_diff_scaled(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> float:
    seg_a = _analysis_segment(wave_a, sample_rate_hz=sample_rate_hz, range_length_s=range_length_s)
    seg_b = _analysis_segment(wave_b, sample_rate_hz=sample_rate_hz, range_length_s=range_length_s)
    if seg_a.shape != seg_b.shape:
        return float("inf")
    if seg_a.size == 0:
        return 0.0
    return float(np.max(np.abs(seg_a - seg_b)))


def prefilter_near_duplicate(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> bool:
    """True when float prefilter passes (worth 16-bit code comparison). A.15."""
    d = max_abs_diff_scaled(
        wave_a,
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    return d * 32768.0 <= 2.0


def full_encode_max_code_delta(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> int:
    codes_a = codes_for_analysis_range(
        wave_a,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    codes_b = codes_for_analysis_range(
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    if codes_a.shape != codes_b.shape:
        return 10**9
    if codes_a.size == 0:
        return 0
    return int(max(abs(int(a) - int(b)) for a, b in zip(codes_a, codes_b, strict=True)))


def near_duplicate_hit(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> tuple[bool, int]:
    if not prefilter_near_duplicate(
        wave_a,
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    ):
        return False, 10**9
    delta = full_encode_max_code_delta(
        wave_a,
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    return delta <= 1, delta


def _validation_wave_index(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
) -> dict[ParamBucketKey, list[tuple[NDArray[np.float64], str]]]:
    index: dict[ParamBucketKey, list[tuple[NDArray[np.float64], str]]] = {}
    # Calibration sides never change f0 or sample rate, so only validation materials
    # sharing a calibration (f0, sr) can ever be compared (same-f0, same-rate rule).
    calibration_rates = {(g.f0_hz, g.sample_rate_hz) for g in groups if g.side == "calibration"}
    for group in groups:
        if group.side != "validation":
            continue
        if (group.f0_hz, group.sample_rate_hz) not in calibration_rates:
            continue
        for params in channel_effectives_from_group(group):
            side_spec = SideGenerationSpec(encoding=EncodingSpec(bits=16), effective=params)
            wave = _side_wave_cached(side_spec, duration_s=c.file_duration_s)
            key = _bucket_key(params)
            index.setdefault(key, []).append((wave, group.group_key))
    return index


def _effective_key(params) -> tuple:
    return (
        params.family,
        params.f0_hz,
        params.sample_rate_hz,
        normalize_phase(params.phase_rad),
        params.amplitude,
        params.peak,
        params.level,
        params.depth,
        params.harmonics,
    )


def build_validation_effective_index(
    groups: tuple[SourceGroupRecord, ...],
) -> dict[tuple, str]:
    index: dict[tuple, str] = {}
    for group in groups:
        if group.side != "validation":
            continue
        for ch in channel_effectives_from_group(group):
            index[_effective_key(ch)] = group.group_key
    return index


def _side_from_any(side: SideGenerationSpec | dict) -> SideGenerationSpec:
    if isinstance(side, SideGenerationSpec):
        return side
    enc = side["encoding"]
    return SideGenerationSpec(
        encoding=EncodingSpec(
            bits=enc["bits"],
            rounding=enc.get("rounding", "round"),
            step_bits=enc.get("step_bits"),
            seed=enc.get("seed"),
            filename=enc.get("filename", "material.wav"),
        ),
        effective=EffectiveMaterialParams(**side["effective"]),
        sample_offset=side.get("sample_offset", 0),
        gain_factor=side.get("gain_factor", 1.0),
        noise_rms=side.get("noise_rms"),
        noise_seed=side.get("noise_seed"),
        phase_delta_rad=side.get("phase_delta_rad", 0.0),
    )


def _channel_params(
    side: SideGenerationSpec, m9_layout: Mapping[str, Any] | None
) -> list[tuple[str, EffectiveMaterialParams]]:
    """Per-channel effective parameters of a pair side (M9 split into left/right)."""
    eff = side.effective
    if eff.family != "M9":
        return [("mono", eff)]
    if m9_layout is None:
        raise ManifestLeakageAbort("M9 side without a channel layout")
    left, right = _layout_channel_params(
        M9ChannelLayout.model_validate(m9_layout),
        f0_hz=eff.f0_hz,
        sample_rate_hz=eff.sample_rate_hz,
        phase_rad=eff.phase_rad,
    )
    return [("left", left), ("right", right)]


def param_leakage_hits(
    pairs: Sequence[PairRecord | dict[str, Any]],
    validation_index: dict[tuple, str],
    *,
    m9_layouts: Mapping[str, Mapping[str, Any] | None],
) -> list[str]:
    """Calibration sides whose per-channel effective parameters equal a validation material."""
    hits: list[str] = []
    for pair in pairs:
        record = pair if isinstance(pair, dict) else pair.model_dump(mode="python")
        if record["side"] != "calibration":
            continue
        layout = m9_layouts.get(record["source_group_key"])
        for label in ("old_side", "new_side"):
            side = _side_from_any(record[label])
            for channel, params in _channel_params(side, layout):
                hit_key = validation_index.get(_effective_key(params))
                if hit_key is not None:
                    hits.append(
                        f"calibration pair {record['pair_id']} ({record['family']}) {label} "
                        f"{channel} matches validation material {hit_key}"
                    )
    return hits


def assert_no_param_leakage(
    pairs: Sequence[PairRecord | dict[str, Any]],
    validation_index: dict[tuple, str],
    *,
    m9_layouts: Mapping[str, Mapping[str, Any] | None],
) -> None:
    hits = param_leakage_hits(pairs, validation_index, m9_layouts=m9_layouts)
    if hits:
        raise ManifestLeakageAbort(hits[0] + (f" (+{len(hits) - 1} more)" if len(hits) > 1 else ""))


def count_param_leakage(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
    *,
    skip_pair_ids: frozenset[str] = frozenset(),
) -> list[str]:
    """Streaming per-channel parameter leakage scan over every calibration pair (R0 path)."""
    validation_index = build_validation_effective_index(groups)
    layouts = {g.group_key: g.m9_layout for g in groups}
    hits: list[str] = []
    for batch in _r0_description_batches(groups, c, batch_size=2048):
        kept = [d for d in batch if d["side"] == "calibration" and d["pair_id"] not in skip_pair_ids]
        hits.extend(param_leakage_hits(kept, validation_index, m9_layouts=layouts))
    return hits


# ---------------------------------------------------------------------------
# A.15 near-reproduction scan


class _Bucket:
    """Validation waves of one (family, f0, sr, phase) bucket with short-prefix matrices."""

    def __init__(self, entries: list[tuple[NDArray[np.float64], str]]) -> None:
        self.entries = entries
        self._prefix: dict[int, NDArray[np.float64]] = {}

    def prefix(self, n: int) -> NDArray[np.float64]:
        if n not in self._prefix:
            self._prefix[n] = np.stack([wave[:n] for wave, _ in self.entries])
        return self._prefix[n]


def _short_length(c: CharacterizationConstants, sample_rate_hz: int) -> int:
    return round(min(c.calibration_range_lengths_s) * sample_rate_hz)


def _candidates(bucket: _Bucket, prefix: NDArray[np.float64]) -> list[int]:
    """Exact necessary condition on the shortest range: max |a - b| * 32768 <= 2."""
    n = prefix.shape[0]
    d = np.max(np.abs(bucket.prefix(n) - prefix[None, :]), axis=1)
    return [int(i) for i in np.flatnonzero(d * 32768.0 <= 2.0)]


def _best_hit(
    wave: NDArray[np.float64],
    bucket: _Bucket,
    candidates: list[int],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> tuple[int, str | None]:
    best, hit = 10**9, None
    for i in candidates:
        val_wave, val_key = bucket.entries[i]
        ok, delta = near_duplicate_hit(
            wave, val_wave, sample_rate_hz=sample_rate_hz, range_length_s=range_length_s
        )
        if ok and delta < best:
            best, hit = delta, val_key
    return best, hit


class _SideWave:
    """Lazily synthesised channel wave of one pair side; prefixes avoid full synthesis."""

    def __init__(
        self,
        params: EffectiveMaterialParams,
        side: SideGenerationSpec,
        c: CharacterizationConstants,
        base_cache: dict[tuple, NDArray[np.float64]],
    ) -> None:
        self.params = params
        self.side = side
        self.c = c
        self.base_cache = base_cache
        self._full: NDArray[np.float64] | None = None

    def _base(self) -> NDArray[np.float64]:
        key = _effective_key(self.params)
        if key not in self.base_cache:
            self.base_cache[key] = synthesize_mono(self.params, duration_s=self.c.file_duration_s)
        return self.base_cache[key]

    def _simple(self) -> bool:
        return self.side.sample_offset == 0

    def prefix(self, n: int) -> NDArray[np.float64]:
        if not self._simple():
            return self.full()[:n]
        wave = self._base()[:n]
        side = self.side
        if side.gain_factor != 1.0:
            wave = np.clip(wave * side.gain_factor, -1.0, 1.0)
        if side.noise_rms is not None:
            rng = np.random.default_rng(side.noise_seed)
            wave = np.clip(wave + rng.normal(0.0, side.noise_rms, size=n), -1.0, 1.0)
        return wave

    def full(self) -> NDArray[np.float64]:
        if self._full is None:
            side = self.side
            key = (
                _effective_key(self.params),
                side.sample_offset,
                side.gain_factor,
                side.noise_rms,
                side.noise_seed,
            )
            if self._simple() and side.gain_factor == 1.0 and side.noise_rms is None:
                self._full = self._base()
            elif key in self.base_cache:
                self._full = self.base_cache[key]
            else:
                self._full = self.base_cache[key] = synthesize_mono(
                    self.params,
                    duration_s=self.c.file_duration_s,
                    sample_offset=self.side.sample_offset,
                    gain_factor=self.side.gain_factor,
                    noise_rms=self.side.noise_rms,
                    noise_seed=self.side.noise_seed,
                )
        return self._full


def _side_hit(
    side: SideGenerationSpec,
    layout: Mapping[str, Any] | None,
    buckets: dict[ParamBucketKey, _Bucket],
    c: CharacterizationConstants,
    base_cache: dict[tuple, NDArray[np.float64]],
    range_length_s: float,
) -> tuple[int, str | None]:
    """Smallest code delta to any same-bucket validation material over any channel."""
    best, hit = 10**9, None
    for _channel, params in _channel_params(side, layout):
        bucket = buckets.get(_bucket_key(params))
        if bucket is None:
            continue
        sw = _SideWave(params, side, c, base_cache)
        sr = params.sample_rate_hz
        candidates = _candidates(bucket, sw.prefix(_short_length(c, sr)))
        if not candidates:
            continue
        delta, key = _best_hit(
            sw.full(), bucket, candidates, sample_rate_hz=sr, range_length_s=range_length_s
        )
        if key is not None and delta < best:
            best, hit = delta, key
    return best, hit


def scan_near_duplicates(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
    *,
    wave_index: dict[ParamBucketKey, list[tuple[NDArray[np.float64], str]]],
) -> tuple[frozenset[str], tuple[ExcludedNearDuplicate, ...], list[tuple[str, str, float]]]:
    """A.15 over every side of every calibration pair, channel by channel (M9 included).

    Base material or tolerance-pair hits abort generation. Sensitivity and change
    pairs whose new side lands within one 16-bit code of a same-form, same-f0,
    same-rate, same-phase validation material over the pair's analysis range are
    excluded and listed.
    """
    buckets = {key: _Bucket(entries) for key, entries in wave_index.items()}
    rate_keys = {(key[1], key[2]) for key in buckets}
    excluded_ids: set[str] = set()
    entries: list[ExcludedNearDuplicate] = []
    families: list[tuple[str, str, float]] = []
    for group in groups:
        if group.side != "calibration":
            continue
        layout = group.m9_layout
        base_side = SideGenerationSpec(
            encoding=EncodingSpec(bits=16), effective=params_from_group_record(group)
        )
        # Every bucket key carries (f0, sr); a perturbed side keeps the group's f0 and sr.
        if (group.f0_hz, group.sample_rate_hz) not in rate_keys:
            continue
        group_pairs = _pairs_for_group(group, c)
        base_cache: dict[tuple, NDArray[np.float64]] = {}
        for range_len in c.calibration_range_lengths_s:
            delta, key = _side_hit(base_side, layout, buckets, c, base_cache, range_len)
            if key is not None:
                raise ManifestLeakageAbort(
                    f"base material of calibration group {group.group_key} reproduces "
                    f"validation material {key} (max code delta {delta})"
                )
        for d in group_pairs:
            code = d["perturbation_code"]
            new_side = _side_from_any(d["new_side"])
            if code in TOLERANCE_CODES:
                if code != "P5t":
                    continue  # same float material as the base; checked above
                delta, key = _side_hit(new_side, layout, buckets, c, base_cache, d["range_length_s"])
                if key is not None:
                    raise ManifestLeakageAbort(
                        f"tolerance near-duplicate on pair {d['pair_id']} vs validation {key}"
                    )
                continue
            if code == "P8":
                continue  # new side is the base material at 8 bits
            delta, key = _side_hit(new_side, layout, buckets, c, base_cache, d["range_length_s"])
            if key is not None:
                excluded_ids.add(d["pair_id"])
                entries.append(
                    ExcludedNearDuplicate(
                        pair_id=d["pair_id"], validation_group_key=key, max_code_delta=delta
                    )
                )
                families.append((d["family"], code, d["range_length_s"]))
    return frozenset(excluded_ids), tuple(entries), families


def assert_p3_phases_disjoint(c: CharacterizationConstants) -> None:
    cal_phases = {round(v, 12) for v in c.p3_calibration_deltas_rad}
    val_phases = {round(v, 12) for v in c.validation_start_phases_heldout_rad}
    val_phases |= {round(v, 12) for v in c.p3_validation_deltas_rad}
    overlap = cal_phases & val_phases
    if overlap:
        raise ManifestLeakageAbort(f"P3 calibration result phases overlap validation: {overlap}")


def assert_onset_depths(c: CharacterizationConstants) -> None:
    if any(abs(d - 0.9999) < 1e-12 for d in c.onset_calibration_depths):
        raise ManifestLeakageAbort("calibration onset depths must not include 0.9999")
