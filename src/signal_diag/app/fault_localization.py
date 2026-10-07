"""Product fault time localization by deterministic segment scan (D050).

Runs after a contextual diagnosis. It never changes the agent's conclusion,
claims or Evidence: it produces its own segment Evidence and rule evaluations
from the versioned ``profile_s1_segment_evidence`` and reports where each fault
the rules support occurs. Windows match the agent-increment study's B2 scan.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.app.guarded_tools import GuardedSignalToolService
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluation, RuleProfile
from signal_diag.signal.models import ChannelMode, SignalRecord, TimeRange
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.evidence import Evidence

SCAN_VERSION = "product-segment-scan-1.0"
WINDOW_S = 0.25
OVERLAP = 0.5
SEGMENT_PROFILE_ID = "profile_s1_segment_evidence"

FaultKind = Literal["clipping", "harmonic_distortion"]
ScanMode = Literal["single_signal", "nominal_single_tone", "paired_reference"]

_FAULT_BY_RULE: dict[str, FaultKind] = {
    "rule_clipping_detected_absent": "clipping",
    "rule_clipping_ratio_acceptable": "clipping",
    "rule_flat_top_absent": "clipping",
    "rule_thd_acceptable": "harmonic_distortion",
}


class LocalizedInterval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fault: FaultKind
    channel: ChannelMode
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    agrees_with_diagnosis: bool
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    evaluation_refs: tuple[str, ...] = Field(min_length=1)


class FaultLocalization(BaseModel):
    """Scan result. ``evidence`` and ``rule_evaluations`` hold what intervals cite."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scan_version: str
    window_s: float
    overlap: float
    channels: tuple[ChannelMode, ...]
    harmonic_scanned: bool
    windows_scanned: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    intervals: tuple[LocalizedInterval, ...]
    evidence: tuple[Evidence, ...]
    rule_evaluations: tuple[RuleEvaluation, ...]


def _segment_profile() -> RuleProfile:
    packaged = files("signal_diag").joinpath("rules", "profiles", "s1_segment_evidence_v1.yaml")
    loader = YamlRuleProfileLoader({SEGMENT_PROFILE_ID: Path(str(packaged))})
    return loader.load(SEGMENT_PROFILE_ID)


def _channels(record: SignalRecord) -> tuple[ChannelMode, ...]:
    return ("mixdown",) if record.meta.channels == 1 else ("left", "right", "mixdown")


def scan_windows(record: SignalRecord) -> tuple[TimeRange, ...]:
    """Fixed windows of ``WINDOW_S`` with ``OVERLAP``; the last one ends at the file end."""
    rate = record.meta.sample_rate_hz
    total = int(record.samples.shape[0])
    window = max(1, round(WINDOW_S * rate))
    hop = max(1, round(WINDOW_S * (1.0 - OVERLAP) * rate))
    spans: list[TimeRange] = []
    start = 0
    while start < total:
        end = min(start + window, total)
        spans.append(TimeRange(start_s=start / rate, end_s=end / rate))
        if end == total:
            break
        start += hop
    return tuple(spans)


def _merge(
    supports: Iterable[tuple[FaultKind, ChannelMode, float, float, str, str]],
    diagnosed_faults: frozenset[str],
) -> tuple[LocalizedInterval, ...]:
    """Merge overlapping or touching FAIL windows per fault and channel."""
    grouped: dict[tuple[FaultKind, ChannelMode], list[tuple[float, float, str, str]]] = {}
    for fault, channel, start, end, evidence_id, evaluation_id in supports:
        grouped.setdefault((fault, channel), []).append((start, end, evidence_id, evaluation_id))
    intervals: list[LocalizedInterval] = []
    for (fault, channel), items in sorted(grouped.items()):
        runs: list[list[tuple[float, float, str, str]]] = []
        for item in sorted(items):
            if runs and item[0] <= max(entry[1] for entry in runs[-1]):
                runs[-1].append(item)
            else:
                runs.append([item])
        for run in runs:
            intervals.append(
                LocalizedInterval(
                    fault=fault,
                    channel=channel,
                    start_s=min(entry[0] for entry in run),
                    end_s=max(entry[1] for entry in run),
                    agrees_with_diagnosis=fault in diagnosed_faults,
                    evidence_refs=tuple(dict.fromkeys(entry[2] for entry in run)),
                    evaluation_refs=tuple(dict.fromkeys(entry[3] for entry in run)),
                )
            )
    return tuple(intervals)


def localize_faults(
    record: SignalRecord,
    *,
    mode: ScanMode,
    nominal_fundamental_hz: float | None,
    diagnosed_faults: frozenset[str],
) -> FaultLocalization:
    """Scan every window and channel; harmonics only with a declared single tone (D037)."""
    repository = InMemorySignalRepository()
    repository.put(record)
    tools = GuardedSignalToolService(repository)
    harmonic_scanned = mode == "nominal_single_tone" and nominal_fundamental_hz is not None
    channels = _channels(record)
    windows = scan_windows(record)
    evidence: list[Evidence] = []
    calls = 0
    for channel in channels:
        for span in windows:
            clipping = tools.detect_clipping(
                record.meta.signal_id, ClippingInput(time_range=span, channel=channel)
            )
            calls += 1
            evidence.extend(clipping.evidence)
            if harmonic_scanned:
                harmonic = tools.analyze_harmonic_distortion(
                    record.meta.signal_id,
                    HarmonicDistortionInput(
                        time_range=span,
                        channel=channel,
                        fundamental_hz=nominal_fundamental_hz,
                    ),
                )
                calls += 1
                evidence.extend(harmonic.evidence)
    by_id = {item.evidence_id: item for item in evidence}
    batch = RuleEngine().evaluate_profile(_segment_profile(), tuple(evidence))
    supports: list[tuple[FaultKind, ChannelMode, float, float, str, str]] = []
    cited_evaluations: list[RuleEvaluation] = []
    for evaluation in batch.evaluations:
        fault = _FAULT_BY_RULE.get(evaluation.rule_id)
        if fault is None or evaluation.judgment != "fail":
            continue
        if fault == "harmonic_distortion" and not harmonic_scanned:
            continue
        if len(evaluation.evidence_refs) != 1:
            continue
        item = by_id[evaluation.evidence_refs[0]]
        located = item.time_range
        if located is None or located.end_s is None:
            continue
        supports.append(
            (
                fault,
                item.channel,
                located.start_s,
                located.end_s,
                item.evidence_id,
                evaluation.evaluation_id,
            )
        )
        cited_evaluations.append(evaluation)
    intervals = _merge(supports, diagnosed_faults)
    cited = {ref for interval in intervals for ref in interval.evidence_refs}
    return FaultLocalization(
        scan_version=SCAN_VERSION,
        window_s=WINDOW_S,
        overlap=OVERLAP,
        channels=channels,
        harmonic_scanned=harmonic_scanned,
        windows_scanned=len(windows) * len(channels),
        tool_calls=calls,
        intervals=intervals,
        evidence=tuple(item for item in evidence if item.evidence_id in cited),
        rule_evaluations=tuple(cited_evaluations),
    )


__all__ = [
    "OVERLAP",
    "SCAN_VERSION",
    "WINDOW_S",
    "FaultLocalization",
    "LocalizedInterval",
    "localize_faults",
    "scan_windows",
]
