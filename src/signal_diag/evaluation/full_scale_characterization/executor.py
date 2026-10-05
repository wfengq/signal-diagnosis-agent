"""Full tool-path measurement for characterization pairs (T-CX375)."""

from __future__ import annotations

import hashlib
from typing import cast

from signal_diag.dsp.full_scale import count_full_scale_samples
from signal_diag.evaluation.full_scale_characterization.constants import M9ChannelLayout
from signal_diag.evaluation.full_scale_characterization.gate import (
    require_validation_access,
)
from signal_diag.evaluation.full_scale_characterization.materials import (
    synthesize_side_waveform,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    MeasuredPair,
    MeasurementRow,
    MeasurementRowSpec,
    PairRecord,
    PairRole,
    PairTerminalState,
    SanityAbort,
    SideGenerationSpec,
)
from signal_diag.evaluation.full_scale_characterization.pcm import (
    RoundingMode,
    StepBits,
    encode_pcm_wav,
)
from signal_diag.signal import InMemorySignalRepository, build_signal_record
from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.signal.segment import _resolve_sample_bounds, extract_segment
from signal_diag.signal.wav import InvalidWavError, UnsupportedWavError, load_wav_bytes
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.regression_full_scale import (
    FULL_SCALE_MIN_CONSECUTIVE_SAMPLES,
    measure_full_scale_facts,
    verify_full_scale_facts,
)
from signal_diag.tools.regression_measurement import (
    ComparisonSide,
    InputIdentity,
    MeasurementSelection,
    ToolParameterSnapshot,
    measure_output,
)

MeasurementCache = dict[tuple[str, ChannelMode, TimeRange, PairRole], MeasurementRow]


def _comparison_side(role: PairRole) -> ComparisonSide:
    return "baseline" if role == "old" else "candidate"


def _run_id(role: PairRole, wav_sha256: str) -> str:
    return f"run_{role}_{wav_sha256[:16]}"


def _build_identity(
    *,
    run_id: str,
    side: ComparisonSide,
    wav_sha256: str,
    signal_id: str,
    repository: InMemorySignalRepository,
    selection: MeasurementSelection,
) -> InputIdentity:
    record = repository.get(signal_id)
    time_range = selection.clipping.time_range or TimeRange()
    resolved_start, resolved_end = _resolve_sample_bounds(record, time_range)
    snapshot = ToolParameterSnapshot(
        clipping=selection.clipping,
        harmonic=selection.harmonic,
    )
    return InputIdentity(
        run_id=run_id,
        side=side,
        wav_sha256=wav_sha256,
        signal_id=signal_id,
        sample_rate_hz=record.meta.sample_rate_hz,
        source_channels=record.meta.channels,
        total_frames=record.meta.num_samples,
        resolved_start_sample=resolved_start,
        resolved_end_sample=resolved_end,
        channel=selection.clipping.channel,
        tool_parameter_snapshot=snapshot,
    )


def _invalid_row(
    spec: MeasurementRowSpec,
    *,
    wav_sha256: str,
    reason: str,
) -> MeasurementRow:
    return MeasurementRow(
        wav_sha256=wav_sha256,
        channel=spec.channel,
        time_range=spec.time_range,
        role=spec.role,
        terminal_state="invalid",
        terminal_reason=reason,
    )


def _generation_failed_row(spec: MeasurementRowSpec) -> MeasurementRow:
    return MeasurementRow(
        wav_sha256="0" * 64,
        channel=spec.channel,
        time_range=spec.time_range,
        role=spec.role,
        terminal_state="generation_failed",
        terminal_reason="generation_failed",
    )


def _encode_side(spec: SideGenerationSpec, *, file_duration_s: float, m9_layout: M9ChannelLayout | None) -> bytes:
    channels = synthesize_side_waveform(
        spec,
        file_duration_s=file_duration_s,
        m9_layout=m9_layout,
    )
    enc = spec.encoding
    step_bits = cast(StepBits | None, enc.step_bits)
    return encode_pcm_wav(
        list(channels),
        sr=spec.effective.sample_rate_hz,
        bits=enc.bits,
        rounding=cast(RoundingMode, enc.rounding),
        step_bits=step_bits,
        seed=enc.seed,
    )


def measure_row(
    spec: MeasurementRowSpec,
    *,
    cache: MeasurementCache | None = None,
    validation_access: object = None,
) -> MeasurementRow:
    """Run the full tool path for one measurement-table row.

    Validation-side specs require a ``ValidationAccess`` from a verified freeze record.
    """
    if spec.side == "validation":
        require_validation_access(validation_access, what="measure a validation row")
    store = cache if cache is not None else {}
    m9_layout = (
        M9ChannelLayout.model_validate(spec.m9_layout) if spec.m9_layout is not None else None
    )

    try:
        wav_bytes = _encode_side(
            spec.side_spec,
            file_duration_s=spec.file_duration_s,
            m9_layout=m9_layout,
        )
    except Exception:  # noqa: BLE001 — any synthesis/encode failure → generation_failed
        return _generation_failed_row(spec)

    wav_sha256 = hashlib.sha256(wav_bytes).hexdigest()
    cache_key = (wav_sha256, spec.channel, spec.time_range, spec.role)
    if cache_key in store:
        return store[cache_key]

    filename = spec.side_spec.encoding.filename
    repository = InMemorySignalRepository()
    try:
        try:
            loaded = load_wav_bytes(wav_bytes, filename=filename)
        except (InvalidWavError, UnsupportedWavError):
            row = _invalid_row(spec, wav_sha256=wav_sha256, reason="wav_load")
            store[cache_key] = row
            return row

        signal_id = f"sig_{wav_sha256[:32]}"
        record = build_signal_record(
            loaded.record.samples,
            sample_rate_hz=loaded.record.meta.sample_rate_hz,
            source_type="wav",
            filename=filename,
            signal_id=signal_id,
        )
        repository.put(record)

        selection = MeasurementSelection(
            clipping=ClippingInput(
                channel=spec.channel,
                time_range=spec.time_range,
                full_scale_threshold=spec.full_scale_threshold,
            ),
            harmonic=HarmonicDistortionInput(
                channel=spec.channel,
                time_range=spec.time_range,
            ),
        )
        comparison_side = _comparison_side(spec.role)
        identity = _build_identity(
            run_id=_run_id(spec.role, wav_sha256),
            side=comparison_side,
            wav_sha256=wav_sha256,
            signal_id=signal_id,
            repository=repository,
            selection=selection,
        )
        try:
            bundle = measure_output(
                repository=repository,
                identity=identity,
                selection=selection,
            )
        except Exception:  # noqa: BLE001 — measure_output failures → invalid/measure_output
            row = _invalid_row(spec, wav_sha256=wav_sha256, reason="measure_output")
            store[cache_key] = row
            return row

        if bundle.clipping.status != "success" or bundle.clipping.result is None:
            row = _invalid_row(spec, wav_sha256=wav_sha256, reason="clipping_tool")
            store[cache_key] = row
            return row

        facts = measure_full_scale_facts(
            repository=repository,
            bundle=bundle,
            pcm_bit_depth=loaded.source_info.bits_per_sample,
        )
        if facts is None:
            row = _invalid_row(spec, wav_sha256=wav_sha256, reason="clipping_tool")
            store[cache_key] = row
            return row

        try:
            verify_full_scale_facts(facts, bundle)
        except ValueError as error:
            raise SanityAbort(str(error)) from error

        clip = bundle.clipping.result
        row = MeasurementRow(
            wav_sha256=wav_sha256,
            channel=spec.channel,
            time_range=spec.time_range,
            role=spec.role,
            terminal_state="measured",
            counted_samples=facts.counted_samples,
            over_threshold_uncounted=facts.over_threshold_uncounted,
            state=facts.state,
            peak_abs=facts.peak_abs,
            analyzed_samples=facts.analyzed_samples,
            pcm_bit_depth=facts.pcm_bit_depth,
            clipping_ratio=clip.clipping_ratio,
            clipped_samples=clip.clipped_samples,
            full_scale_detected=clip.full_scale_detected,
            flat_top_detected=clip.flat_top_detected,
            clipping_mechanism=clip.clipping_mechanism,
            bundle_digest=bundle.digest,
            facts_digest=facts.digest,
            harmonic_tool_status=bundle.harmonic.status,
        )
        store[cache_key] = row
        return row
    finally:
        for meta in list(repository.list_meta()):
            repository.remove(meta.signal_id)


def row_specs_for_pair(
    pair: PairRecord,
    *,
    file_duration_s: float,
    full_scale_threshold: float,
    m9_layout: dict | None,
    validation_access: object = None,
) -> list[MeasurementRowSpec]:
    """Expand a manifest pair into per-channel row specs for both roles.

    Validation-side pairs require a ``ValidationAccess`` from a verified freeze record.
    """
    if pair.side == "validation":
        require_validation_access(validation_access, what=f"measure validation pair {pair.pair_id}")
    time_range = TimeRange(start_s=0.0, end_s=pair.range_length_s)
    channels: tuple[ChannelMode, ...] = (
        ("left", "right") if pair.family == "M9" else ("left",)
    )
    specs: list[MeasurementRowSpec] = []
    for channel in channels:
        for role, side_spec in (("old", pair.old_side), ("new", pair.new_side)):
            specs.append(
                MeasurementRowSpec(
                    side_spec=side_spec,
                    side=pair.side,
                    role=cast(PairRole, role),
                    channel=channel,
                    time_range=time_range,
                    file_duration_s=file_duration_s,
                    full_scale_threshold=full_scale_threshold,
                    m9_layout=m9_layout,
                )
            )
    return specs


def _pair_terminal_state(old_row: MeasurementRow, new_row: MeasurementRow) -> PairTerminalState:
    states = {old_row.terminal_state, new_row.terminal_state}
    if "generation_failed" in states:
        return "generation_failed"
    if "invalid" in states:
        return "invalid"
    return "measured"


def _pair_terminal_reason(old_row: MeasurementRow, new_row: MeasurementRow) -> str | None:
    terminal = _pair_terminal_state(old_row, new_row)
    if terminal == "measured":
        return None
    reasons = [
        r
        for r in (old_row.terminal_reason, new_row.terminal_reason)
        if r is not None
    ]
    return reasons[0] if reasons else terminal


def assemble_pair(
    pair: PairRecord,
    rows: dict[tuple[PairRole, ChannelMode], MeasurementRow],
    *,
    channel: ChannelMode,
) -> MeasuredPair:
    """Build pair-level scoring for one channel."""
    old_row = rows[("old", channel)]
    new_row = rows[("new", channel)]
    terminal = _pair_terminal_state(old_row, new_row)
    count_diff: int | None = None
    ratio_diff: float | None = None
    flip: bool | None = None
    if (
        terminal == "measured"
        and old_row.analyzed_samples is not None
        and new_row.counted_samples is not None
        and old_row.counted_samples is not None
        and new_row.analyzed_samples is not None
        and old_row.state is not None
        and new_row.state is not None
    ):
        count_diff = new_row.counted_samples - old_row.counted_samples
        ratio_diff = count_diff / float(old_row.analyzed_samples)
        flip = old_row.state != new_row.state
    return MeasuredPair(
        pair_id=pair.pair_id,
        channel=channel,
        range_length_s=pair.range_length_s,
        old_row=old_row,
        new_row=new_row,
        count_diff=count_diff,
        ratio_diff=ratio_diff,
        flip=flip,
        terminal_state=terminal,
        terminal_reason=_pair_terminal_reason(old_row, new_row),
    )


def direct_reference_counts(
    spec: MeasurementRowSpec,
    *,
    wav_bytes: bytes | None = None,
    validation_access: object = None,
) -> tuple[object, object]:
    """Re-run facts and sample counting for test verification (not cached)."""
    if spec.side == "validation":
        require_validation_access(validation_access, what="measure a validation row")
    m9_layout = (
        M9ChannelLayout.model_validate(spec.m9_layout) if spec.m9_layout is not None else None
    )
    wav_bytes = wav_bytes or _encode_side(
        spec.side_spec,
        file_duration_s=spec.file_duration_s,
        m9_layout=m9_layout,
    )
    loaded = load_wav_bytes(wav_bytes, filename=spec.side_spec.encoding.filename)
    signal_id = f"sig_{hashlib.sha256(wav_bytes).hexdigest()[:32]}"
    repository = InMemorySignalRepository()
    record = build_signal_record(
        loaded.record.samples,
        sample_rate_hz=loaded.record.meta.sample_rate_hz,
        source_type="wav",
        filename=spec.side_spec.encoding.filename,
        signal_id=signal_id,
    )
    repository.put(record)
    selection = MeasurementSelection(
        clipping=ClippingInput(
            channel=spec.channel,
            time_range=spec.time_range,
            full_scale_threshold=spec.full_scale_threshold,
        ),
        harmonic=HarmonicDistortionInput(
            channel=spec.channel,
            time_range=spec.time_range,
        ),
    )
    wav_sha256 = hashlib.sha256(wav_bytes).hexdigest()
    identity = _build_identity(
        run_id=_run_id(spec.role, wav_sha256),
        side=_comparison_side(spec.role),
        wav_sha256=wav_sha256,
        signal_id=signal_id,
        repository=repository,
        selection=selection,
    )
    bundle = measure_output(repository=repository, identity=identity, selection=selection)
    facts = measure_full_scale_facts(
        repository=repository,
        bundle=bundle,
        pcm_bit_depth=loaded.source_info.bits_per_sample,
    )
    segment = extract_segment(
        record,
        time_range=spec.time_range,
        channel=spec.channel,
    )
    counts = count_full_scale_samples(
        segment,
        full_scale_threshold=spec.full_scale_threshold,
        min_consecutive_samples=FULL_SCALE_MIN_CONSECUTIVE_SAMPLES,
    )
    return facts, counts
