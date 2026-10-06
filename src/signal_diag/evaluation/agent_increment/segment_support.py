"""Map segment rule FAILs to a fault location taken from cited Evidence."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluationBatch, RuleProfile
from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.tools.evidence import Evidence

SEGMENT_PROFILE_ID = "profile_s1_segment_evidence"

_FAULT_BY_RULE: dict[str, Literal["clipping", "harmonic_distortion"]] = {
    "rule_clipping_detected_absent": "clipping",
    "rule_clipping_ratio_acceptable": "clipping",
    "rule_flat_top_absent": "clipping",
    "rule_thd_acceptable": "harmonic_distortion",
}


class SegmentSupport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fault: Literal["clipping", "harmonic_distortion"]
    time_range: TimeRange | None
    channel: ChannelMode
    evidence_id: str
    evaluation_id: str


def segment_profile_path() -> Path:
    packaged = files("signal_diag").joinpath("rules", "profiles", "s1_segment_evidence_v1.yaml")
    return Path(str(packaged))


def load_segment_profile() -> RuleProfile:
    return YamlRuleProfileLoader({SEGMENT_PROFILE_ID: segment_profile_path()}).load(
        SEGMENT_PROFILE_ID
    )


def segment_supports(
    batch: RuleEvaluationBatch,
    evidence_by_id: dict[str, Evidence],
) -> tuple[SegmentSupport, ...]:
    """A segment rule FAIL supports its fault at the cited Evidence location."""
    found: list[SegmentSupport] = []
    for evaluation in batch.evaluations:
        fault = _FAULT_BY_RULE.get(evaluation.rule_id)
        if fault is None or evaluation.judgment != "fail":
            continue
        if len(evaluation.evidence_refs) != 1:
            continue
        evidence_id = evaluation.evidence_refs[0]
        evidence = evidence_by_id[evidence_id]
        found.append(
            SegmentSupport(
                fault=fault,
                time_range=evidence.time_range,
                channel=evidence.channel,
                evidence_id=evidence.evidence_id,
                evaluation_id=evaluation.evaluation_id,
            )
        )
    return tuple(found)
