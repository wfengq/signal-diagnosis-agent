"""T-CX392: segment FAIL supports a conclusion using existing thresholds."""

from __future__ import annotations

from pathlib import Path

from signal_diag.evaluation.agent_increment.segment_support import (
    load_segment_profile,
    segment_supports,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.models import TimeRange
from signal_diag.tools.evidence import Evidence

_ROOT = Path(__file__).resolve().parents[3]
_DISTORTION = _ROOT / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
_SEGMENT = _ROOT / "src/signal_diag/rules/profiles/s1_segment_evidence_v1.yaml"


def test_t_cx392_segment_profile_reuses_distortion_thresholds() -> None:
    loader = YamlRuleProfileLoader(
        {
            "profile_s1_distortion": _DISTORTION,
            "profile_s1_segment_evidence": _SEGMENT,
        }
    )
    distortion = loader.load("profile_s1_distortion")
    segment = load_segment_profile()
    assert segment.profile_id == "profile_s1_segment_evidence"
    assert segment.version == "1.0.0-demo"
    left = [
        (rule.rule_id, rule.metric, rule.comparator, rule.threshold, rule.unit)
        for rule in distortion.rules
    ]
    right = [
        (rule.rule_id, rule.metric, rule.comparator, rule.threshold, rule.unit)
        for rule in segment.rules
    ]
    assert right == left
    assert "time_range" in segment.description
    assert "channel" in segment.description


def test_t_cx392_segment_fail_location_comes_from_cited_evidence() -> None:
    profile = load_segment_profile()
    span = TimeRange(start_s=1.0, end_s=1.25)
    evidence = Evidence(
        evidence_id="ev_detect_clipping_segment_000000_000",
        source_tool="detect_clipping",
        call_id="call_detect_clipping_000000",
        metric="clipping_ratio",
        value=0.2,
        unit=None,
        validity="valid",
        time_range=span,
        channel="left",
    )
    batch = RuleEngine().evaluate_profile(profile, (evidence,))
    supports = segment_supports(batch, {evidence.evidence_id: evidence})
    assert len(supports) == 1
    support = supports[0]
    assert support.fault == "clipping"
    assert support.time_range == span
    assert support.channel == "left"
    assert support.evidence_id == evidence.evidence_id
    assert support.evaluation_id.startswith("ruleval_")


def test_t_cx392_clean_segment_does_not_support_a_fault() -> None:
    profile = load_segment_profile()
    evidence = Evidence(
        evidence_id="ev_detect_clipping_segment_000001_000",
        source_tool="detect_clipping",
        call_id="call_detect_clipping_000001",
        metric="clipping_ratio",
        value=0.0,
        unit=None,
        validity="valid",
        time_range=TimeRange(start_s=0.0, end_s=0.25),
        channel="mixdown",
    )
    batch = RuleEngine().evaluate_profile(profile, (evidence,))
    assert segment_supports(batch, {evidence.evidence_id: evidence}) == ()
