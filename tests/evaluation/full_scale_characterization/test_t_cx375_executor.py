"""T-CX375: full tool-path executor for characterization pairs."""

from __future__ import annotations

from unittest.mock import patch

from signal_diag.evaluation.full_scale_characterization.constants import M9ChannelLayout
from signal_diag.evaluation.full_scale_characterization.executor import (
    assemble_pair,
    direct_reference_counts,
    measure_row,
    row_specs_for_pair,
)
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.materials import (
    _layout_channel_params,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    MeasurementRowSpec,
    SideGenerationSpec,
)
from signal_diag.signal.models import TimeRange
from signal_diag.signal.wav import InvalidWavError
from tests.evaluation.full_scale_characterization.mini_manifest import MINI


def _first_mono_pair():
    manifest = build_manifest(MINI)
    pair = next(p for p in manifest.pairs if p.family == "M2" and p.perturbation_code == "P0")
    group = next(g for g in manifest.source_groups if g.group_key == pair.source_group_key)
    return pair, group, manifest


def _first_m9_pair():
    manifest = build_manifest(MINI)
    pair = next(p for p in manifest.pairs if p.family == "M9")
    group = next(g for g in manifest.source_groups if g.group_key == pair.source_group_key)
    return pair, group, manifest


def test_facts_match_direct_measure_full_scale_facts() -> None:
    pair, group, _ = _first_mono_pair()
    spec = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )[0]
    row = measure_row(spec)
    facts, counts = direct_reference_counts(spec)
    assert row.terminal_state == "measured"
    assert facts is not None
    assert row.counted_samples == facts.counted_samples
    assert row.over_threshold_uncounted == facts.over_threshold_uncounted
    assert row.state == facts.state
    assert row.peak_abs == facts.peak_abs
    assert row.analyzed_samples == facts.analyzed_samples
    assert row.facts_digest == facts.digest
    assert row.counted_samples == counts.counted_samples
    assert row.over_threshold_uncounted == counts.over_threshold_uncounted
    assert row.peak_abs == counts.peak_abs
    assert row.analyzed_samples == counts.analyzed_samples


def test_identical_input_produces_identical_row_digests() -> None:
    pair, group, _ = _first_mono_pair()
    spec = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )[0]
    first = measure_row(spec)
    second = measure_row(spec)
    assert first.model_dump() == second.model_dump()
    assert first.bundle_digest == second.bundle_digest
    assert first.facts_digest == second.facts_digest


def test_cache_returns_same_row_for_same_key() -> None:
    pair, group, _ = _first_mono_pair()
    spec = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )[0]
    cache: dict = {}
    a = measure_row(spec, cache=cache)
    b = measure_row(spec, cache=cache)
    assert a is b
    assert len(cache) == 1


def test_m9_left_channel_matches_mono_same_params() -> None:
    pair, group, _ = _first_m9_pair()
    layout = M9ChannelLayout.model_validate(group.m9_layout)
    left_params, _ = _layout_channel_params(
        layout,
        f0_hz=pair.f0_hz,
        sample_rate_hz=pair.sample_rate_hz,
        phase_rad=pair.old_side.effective.phase_rad,
    )
    mono_spec = MeasurementRowSpec(
        side_spec=SideGenerationSpec(
            encoding=pair.old_side.encoding,
            effective=left_params,
        ),
        role="old",
        channel="left",
        time_range=TimeRange(start_s=0.0, end_s=pair.range_length_s),
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
    )
    m9_spec = next(
        s
        for s in row_specs_for_pair(
            pair,
            file_duration_s=MINI.file_duration_s,
            full_scale_threshold=MINI.full_scale_threshold,
            m9_layout=group.m9_layout,
        )
        if s.role == "old" and s.channel == "left"
    )
    mono_row = measure_row(mono_spec)
    m9_row = measure_row(m9_spec)
    assert m9_row.wav_sha256 != mono_row.wav_sha256
    for field in (
        "counted_samples",
        "over_threshold_uncounted",
        "state",
        "peak_abs",
        "analyzed_samples",
        "terminal_state",
    ):
        assert getattr(m9_row, field) == getattr(mono_row, field)


def test_terminal_generation_failed() -> None:
    pair, group, _ = _first_mono_pair()
    spec = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )[0]
    broken = spec.model_copy(
        update={
            "side_spec": spec.side_spec.model_copy(
                update={
                    "effective": spec.side_spec.effective.model_copy(update={"family": "M99"})
                }
            )
        }
    )
    row = measure_row(broken)
    assert row.terminal_state == "generation_failed"
    assert row.terminal_reason == "generation_failed"


def test_terminal_invalid_wav_load() -> None:
    pair, group, _ = _first_mono_pair()
    spec = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )[0]
    with patch(
        "signal_diag.evaluation.full_scale_characterization.executor.load_wav_bytes",
        side_effect=InvalidWavError("bad"),
    ):
        row = measure_row(spec)
    assert row.terminal_state == "invalid"
    assert row.terminal_reason == "wav_load"


def test_terminal_invalid_clipping_tool() -> None:
    pair, group, _ = _first_mono_pair()
    spec = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )[0]
    from types import SimpleNamespace

    failed_bundle = SimpleNamespace(
        clipping=SimpleNamespace(status="error", result=None),
        harmonic=SimpleNamespace(status="invalid"),
    )
    with patch(
        "signal_diag.evaluation.full_scale_characterization.executor.measure_output",
        return_value=failed_bundle,
    ):
        row = measure_row(spec)
    assert row.terminal_state == "invalid"
    assert row.terminal_reason == "clipping_tool"


def test_terminal_invalid_measure_output() -> None:
    pair, group, _ = _first_mono_pair()
    spec = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )[0]
    with patch(
        "signal_diag.evaluation.full_scale_characterization.executor.measure_output",
        side_effect=RuntimeError("boom"),
    ):
        row = measure_row(spec)
    assert row.terminal_state == "invalid"
    assert row.terminal_reason == "measure_output"


def test_assemble_pair_stays_in_denominator_with_terminal_states() -> None:
    pair, group, _ = _first_mono_pair()
    specs = row_specs_for_pair(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=MINI.full_scale_threshold,
        m9_layout=group.m9_layout,
    )
    rows = {(s.role, s.channel): measure_row(s) for s in specs}
    measured = assemble_pair(pair, rows, channel="left")
    assert measured.terminal_state == "measured"
    assert measured.count_diff is not None
    assert measured.ratio_diff is not None
    assert measured.flip is not None

    failed_old = rows[("old", "left")].model_copy(
        update={"terminal_state": "generation_failed", "terminal_reason": "generation_failed"}
    )
    rows_fail = {**rows, ("old", "left"): failed_old}
    failed_pair = assemble_pair(pair, rows_fail, channel="left")
    assert failed_pair.terminal_state == "generation_failed"
    assert failed_pair.terminal_reason is not None
    assert failed_pair.count_diff is None
