"""Product fault time localization by deterministic segment scan (D050, D051).

Runs after a contextual diagnosis. It never changes the agent's conclusion,
claims or Evidence: it produces its own segment Evidence and rule evaluations
from versioned rule profiles and reports where each fault the rules support
occurs. Clipping and declared-tone windows match the agent-increment study's B2
scan; ``paired_reference`` compares each window with the same span of the
reference under the product's contextual comparison profile.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from signal_diag.app.guarded_tools import GuardedSignalToolService
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluation, RuleProfile
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.factory import build_signal_record
from signal_diag.signal.models import ChannelMode, SignalRecord, TimeRange
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.contracts import (
    ClippingInput,
    ContextualDistortionInput,
    HarmonicDistortionInput,
)
from signal_diag.tools.evidence import Evidence

SCAN_VERSION = "product-segment-scan-1.1"
WINDOW_S = 0.25
OVERLAP = 0.5
COMPARISON_OVERLAP = 0.0
SEGMENT_PROFILE_ID = "profile_s1_segment_evidence"
COMPARISON_PROFILE_ID = "profile_s1_contextual_comparison_v9_10"

FaultKind = Literal["clipping", "harmonic_distortion"]
HarmonicBasis = Literal["nominal_thd", "reference_growth"]
ScanMode = Literal["single_signal", "nominal_single_tone", "paired_reference"]

# The product's whole-file paired gate, applied per window (D051).
_PAIRED_GATE = (
    "rule_contextual_analysis_valid",
    "rule_contextual_f0_compatible",
    "rule_reference_clipping_ratio_acceptable",
    "rule_reference_flat_top_absent",
)
_PAIRED_GROWTH = "rule_even_harmonic_growth_acceptable"

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
    harmonic_basis: HarmonicBasis | None = None
    comparison_overlap: float | None = None
    windows_not_comparable: int | None = Field(default=None, ge=0)
    harmonic_windows_withheld: int | None = Field(default=None, ge=0)


def _packaged_profile(profile_id: str, filename: str) -> RuleProfile:
    packaged = files("signal_diag").joinpath("rules", "profiles", filename)
    return YamlRuleProfileLoader({profile_id: Path(str(packaged))}).load(profile_id)


def _channels(record: SignalRecord) -> tuple[ChannelMode, ...]:
    # Left/right selection exists only for stereo (signal.segment).
    return ("left", "right", "mixdown") if record.meta.channels == 2 else ("mixdown",)


def scan_windows(record: SignalRecord, *, overlap: float = OVERLAP) -> tuple[TimeRange, ...]:
    """Fixed windows of ``WINDOW_S`` with ``overlap``; the last one ends at the file end."""
    rate = record.meta.sample_rate_hz
    total = int(record.samples.shape[0])
    window = max(1, round(WINDOW_S * rate))
    hop = max(1, round(WINDOW_S * (1.0 - overlap) * rate))
    spans: list[TimeRange] = []
    start = 0
    while start < total:
        end = min(start + window, total)
        spans.append(TimeRange(start_s=start / rate, end_s=end / rate))
        if end == total:
            break
        start += hop
    return tuple(spans)


_Support = tuple[FaultKind, ChannelMode, float, float, tuple[str, ...], tuple[str, ...]]
_Window = tuple[float, float, tuple[str, ...], tuple[str, ...]]


def _merge(
    supports: Iterable[_Support],
    diagnosed_faults: frozenset[str],
) -> tuple[LocalizedInterval, ...]:
    """Merge overlapping or touching supporting windows per fault and channel."""
    grouped: dict[tuple[FaultKind, ChannelMode], list[_Window]] = {}
    for fault, channel, start, end, evidence_ids, evaluation_ids in supports:
        grouped.setdefault((fault, channel), []).append((start, end, evidence_ids, evaluation_ids))
    intervals: list[LocalizedInterval] = []
    for (fault, channel), items in sorted(grouped.items()):
        runs: list[list[_Window]] = []
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
                    evidence_refs=tuple(dict.fromkeys(ref for entry in run for ref in entry[2])),
                    evaluation_refs=tuple(
                        dict.fromkeys(ref for entry in run for ref in entry[3])
                    ),
                )
            )
    return tuple(intervals)


def _broadcast_reference(reference: SignalRecord, test: SignalRecord) -> SignalRecord:
    """A mono reference serves every channel of a stereo test file."""
    if test.meta.channels != 2 or reference.meta.channels != 1:
        return reference
    return build_signal_record(
        np.repeat(reference.samples, 2, axis=1),
        sample_rate_hz=reference.meta.sample_rate_hz,
        source_type=reference.meta.source_type,
        filename=reference.meta.filename,
    )


def _paired_supports(
    tools: GuardedSignalToolService,
    context: StimulusContext,
    channels: tuple[ChannelMode, ...],
    windows: tuple[TimeRange, ...],
) -> tuple[list[_Support], list[Evidence], list[RuleEvaluation], int, int]:
    """Compare each window with the same span of the reference (§27.1)."""
    profile = _packaged_profile(COMPARISON_PROFILE_ID, "s1_contextual_comparison_v9_10.yaml")
    engine = RuleEngine()
    supports: list[_Support] = []
    evidence: list[Evidence] = []
    cited: list[RuleEvaluation] = []
    calls = 0
    not_comparable = 0
    for channel in channels:
        for span in windows:
            if span.end_s is None:  # scan_windows always bounds its windows
                continue
            result = tools.analyze_contextual_distortion(
                context, ContextualDistortionInput(time_range=span, channel=channel)
            )
            calls += 1
            if not result.evidence:
                not_comparable += 1
                continue
            judged = {
                item.rule_id: item
                for item in engine.evaluate_profile(profile, result.evidence).evaluations
            }
            gate = [judged.get(rule_id) for rule_id in _PAIRED_GATE]
            passed = [item for item in gate if item is not None and item.judgment == "pass"]
            if len(passed) != len(_PAIRED_GATE):
                not_comparable += 1
                continue
            growth = judged.get(_PAIRED_GROWTH)
            if growth is None or growth.judgment != "fail":
                continue
            window_evaluations = (*passed, growth)
            refs = tuple(
                dict.fromkeys(ref for item in window_evaluations for ref in item.evidence_refs)
            )
            evidence.extend(item for item in result.evidence if item.evidence_id in refs)
            cited.extend(window_evaluations)
            supports.append(
                (
                    "harmonic_distortion",
                    channel,
                    span.start_s,
                    span.end_s,
                    refs,
                    tuple(item.evaluation_id for item in window_evaluations),
                )
            )
    return supports, evidence, cited, calls, not_comparable


def localize_faults(
    record: SignalRecord,
    *,
    mode: ScanMode,
    nominal_fundamental_hz: float | None,
    diagnosed_faults: frozenset[str],
    reference: SignalRecord | None = None,
) -> FaultLocalization:
    """Scan every window and channel; harmonics only with declared context (D037)."""
    if mode == "paired_reference" and reference is None:
        raise ValueError("paired_reference localization requires the reference record")
    repository = InMemorySignalRepository()
    repository.put(record)
    tools = GuardedSignalToolService(repository)
    nominal_scan = mode == "nominal_single_tone" and nominal_fundamental_hz is not None
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
            if nominal_scan:
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
    batch = RuleEngine().evaluate_profile(
        _packaged_profile(SEGMENT_PROFILE_ID, "s1_segment_evidence_v1.yaml"), tuple(evidence)
    )
    supports: list[_Support] = []
    cited_evaluations: list[RuleEvaluation] = []
    for evaluation in batch.evaluations:
        fault = _FAULT_BY_RULE.get(evaluation.rule_id)
        if fault is None or evaluation.judgment != "fail":
            continue
        if fault == "harmonic_distortion" and not nominal_scan:
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
                (item.evidence_id,),
                (evaluation.evaluation_id,),
            )
        )
        cited_evaluations.append(evaluation)
    not_comparable: int | None = None
    withheld: int | None = None
    if mode == "paired_reference" and reference is not None:
        paired_reference = _broadcast_reference(reference, record)
        repository.put(paired_reference)
        context = StimulusContext(
            mode="paired_reference",
            test_signal_id=record.meta.signal_id,
            reference_signal_id=paired_reference.meta.signal_id,
            assertion_source="user_supplied",
        )
        paired, paired_evidence, paired_evaluations, paired_calls, not_comparable = (
            _paired_supports(
                tools, context, channels, scan_windows(record, overlap=COMPARISON_OVERLAP)
            )
        )
        calls += paired_calls
        # §27.1: per-window reference growth is shown only when the diagnosis
        # supports harmonic distortion; otherwise only the window count is kept.
        if "harmonic_distortion" in diagnosed_faults:
            supports.extend(paired)
            evidence.extend(paired_evidence)
            cited_evaluations.extend(paired_evaluations)
            withheld = 0
        else:
            withheld = len(paired)
    intervals = _merge(supports, diagnosed_faults)
    cited = {ref for interval in intervals for ref in interval.evidence_refs}
    basis: HarmonicBasis | None = None
    if nominal_scan:
        basis = "nominal_thd"
    elif mode == "paired_reference":
        basis = "reference_growth"
    return FaultLocalization(
        scan_version=SCAN_VERSION,
        window_s=WINDOW_S,
        overlap=OVERLAP,
        channels=channels,
        harmonic_scanned=basis is not None,
        windows_scanned=len(windows) * len(channels),
        tool_calls=calls,
        intervals=intervals,
        evidence=tuple(item for item in evidence if item.evidence_id in cited),
        rule_evaluations=tuple(cited_evaluations),
        harmonic_basis=basis,
        comparison_overlap=COMPARISON_OVERLAP if mode == "paired_reference" else None,
        windows_not_comparable=not_comparable,
        harmonic_windows_withheld=withheld,
    )


__all__ = [
    "COMPARISON_OVERLAP",
    "OVERLAP",
    "SCAN_VERSION",
    "WINDOW_S",
    "FaultLocalization",
    "LocalizedInterval",
    "localize_faults",
    "scan_windows",
]
