"""Deterministic B2 segment scan. Window parameters are frozen with the study."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from signal_diag.evaluation.agent_increment.segment_support import (
    SegmentSupport,
    load_segment_profile,
    segment_supports,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.signal.models import ChannelMode, SignalRecord, TimeRange
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

B2_PARAMETER_ID = "b2-segment-scan-1.0"
B2_WINDOW_S = 0.25
B2_OVERLAP = 0.5
B2_HOP_S = B2_WINDOW_S * (1.0 - B2_OVERLAP)


class SegmentScan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: str
    supports: tuple[SegmentSupport, ...]
    tool_calls: int


def _channels(record: SignalRecord) -> tuple[ChannelMode, ...]:
    if record.meta.channels == 1:
        return ("mixdown",)
    return ("left", "right", "mixdown")


def _windows(record: SignalRecord) -> tuple[TimeRange, ...]:
    sample_rate = record.meta.sample_rate_hz
    total = int(record.samples.shape[0])
    window = max(1, round(B2_WINDOW_S * sample_rate))
    hop = max(1, round(B2_HOP_S * sample_rate))
    spans: list[TimeRange] = []
    start = 0
    while start < total:
        end = min(start + window, total)
        spans.append(TimeRange(start_s=start / sample_rate, end_s=end / sample_rate))
        if end == total:
            break
        start += hop
    return tuple(spans)


def scan_signal(record: SignalRecord) -> SegmentScan:
    """Call clipping and harmonic tools on every frozen window and channel."""
    repository = InMemorySignalRepository()
    repository.put(record)
    tools = SignalToolService(repository)
    evidence: list[Evidence] = []
    calls = 0
    for channel in _channels(record):
        for span in _windows(record):
            clipping = tools.detect_clipping(
                record.meta.signal_id,
                ClippingInput(time_range=span, channel=channel),
            )
            calls += 1
            evidence.extend(clipping.evidence)
            harmonic = tools.analyze_harmonic_distortion(
                record.meta.signal_id,
                HarmonicDistortionInput(time_range=span, channel=channel),
            )
            calls += 1
            evidence.extend(harmonic.evidence)
    by_id = {item.evidence_id: item for item in evidence}
    batch = RuleEngine().evaluate_profile(load_segment_profile(), tuple(evidence))
    return SegmentScan(
        parameter_id=B2_PARAMETER_ID,
        supports=segment_supports(batch, by_id),
        tool_calls=calls,
    )
