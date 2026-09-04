"""T-CX046–T-CX055: contextual rule profile loading and evaluation."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.tools.evidence import Evidence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
S1_PROFILE = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)
CONTEXTUAL_PROFILE = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_contextual_comparison_v1.yaml"
)

EXPECTED_RULE_IDS = (
    "rule_contextual_analysis_valid",
    "rule_contextual_f0_compatible",
    "rule_reference_clipping_ratio_acceptable",
    "rule_reference_flat_top_absent",
    "rule_even_harmonic_growth_acceptable",
    "rule_nominal_thd_acceptable",
)


def _loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": S1_PROFILE,
            "profile_s1_contextual_comparison": CONTEXTUAL_PROFILE,
        }
    )


def _evidence(
    *,
    metric: str,
    value: bool | float | str,
    unit: str | None = None,
    validity: str = "valid",
    evidence_id: str = "ev_cx_001",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="analyze_contextual_distortion",
        call_id="call_analyze_contextual_distortion_000000",
        metric=metric,
        value=value,
        unit=unit,
        validity=validity,  # type: ignore[arg-type]
        channel="mixdown",
    )


def test_t_cx046_v02_profile_bytes_unchanged() -> None:
    digest = sha256(S1_PROFILE.read_bytes()).hexdigest()
    assert digest == (
        "1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1"
    )


def test_t_cx047_v02_thresholds_unchanged() -> None:
    profile = _loader().load("profile_s1_distortion")
    by_id = {rule.rule_id: rule for rule in profile.rules}
    assert by_id["rule_clipping_ratio_acceptable"].threshold == 0.01
    assert by_id["rule_thd_acceptable"].threshold == 5.0
    assert by_id["rule_thd_acceptable"].unit == "%"
    assert profile.version == "1.0.0-demo"


def test_t_cx048_contextual_profile_loads_independently() -> None:
    profile = _loader().load("profile_s1_contextual_comparison")
    assert profile.profile_id == "profile_s1_contextual_comparison"
    assert profile.version == "1.0.0"
    assert tuple(rule.rule_id for rule in profile.rules) == EXPECTED_RULE_IDS


def test_t_cx049_all_metrics_bind_to_contextual_tool() -> None:
    profile = _loader().load("profile_s1_contextual_comparison")
    assert all(
        rule.source_tool == "analyze_contextual_distortion" for rule in profile.rules
    )


def test_t_cx050_growth_threshold_matches_frozen_calibration() -> None:
    profile = _loader().load("profile_s1_contextual_comparison")
    growth = next(
        rule
        for rule in profile.rules
        if rule.rule_id == "rule_even_harmonic_growth_acceptable"
    )
    assert growth.threshold == 5.0
    assert growth.unit == "%"
    assert growth.comparator == "lte"


def test_t_cx051_nominal_thd_reuses_five_percent() -> None:
    profile = _loader().load("profile_s1_contextual_comparison")
    thd = next(
        rule for rule in profile.rules if rule.rule_id == "rule_nominal_thd_acceptable"
    )
    assert thd.threshold == 5.0
    assert thd.unit == "%"
    assert thd.metric == "test_thd_percent"


def test_t_cx052_valid_context_passes_and_growth_fails() -> None:
    profile = _loader().load("profile_s1_contextual_comparison")
    engine = RuleEngine()
    batch = engine.evaluate_profile(
        profile,
        [
            _evidence(metric="context_valid", value=True, evidence_id="ev_valid"),
            _evidence(metric="f0_relative_delta", value=0.01, evidence_id="ev_f0"),
            _evidence(
                metric="reference_clipping_ratio",
                value=0.0,
                evidence_id="ev_ref_ratio",
            ),
            _evidence(
                metric="reference_flat_top_detected",
                value=False,
                evidence_id="ev_ref_flat",
            ),
            _evidence(
                metric="even_harmonic_growth_percent",
                value=6.5,
                unit="%",
                evidence_id="ev_growth",
            ),
            _evidence(
                metric="test_thd_percent",
                value=4.0,
                unit="%",
                evidence_id="ev_thd",
            ),
        ],
    )
    by_id = {item.rule_id: item for item in batch.evaluations}
    assert by_id["rule_contextual_analysis_valid"].judgment == "pass"
    assert by_id["rule_contextual_f0_compatible"].judgment == "pass"
    assert by_id["rule_reference_clipping_ratio_acceptable"].judgment == "pass"
    assert by_id["rule_reference_flat_top_absent"].judgment == "pass"
    assert by_id["rule_even_harmonic_growth_acceptable"].judgment == "fail"
    assert by_id["rule_nominal_thd_acceptable"].judgment == "pass"


def test_t_cx053_invalid_evidence_yields_not_applicable() -> None:
    profile = _loader().load("profile_s1_contextual_comparison")
    engine = RuleEngine()
    batch = engine.evaluate_profile(
        profile,
        [
            _evidence(metric="context_valid", value=False, evidence_id="ev_invalid"),
            _evidence(
                metric="even_harmonic_growth_percent",
                value="not_applicable",
                unit="%",
                validity="not_applicable",
                evidence_id="ev_growth_na",
            ),
        ],
    )
    by_id = {item.rule_id: item for item in batch.evaluations}
    assert by_id["rule_contextual_analysis_valid"].judgment == "fail"
    assert by_id["rule_even_harmonic_growth_acceptable"].judgment == "not_applicable"
    assert by_id["rule_even_harmonic_growth_acceptable"].reason == (
        "evidence is not applicable"
    )


def test_t_cx054_growth_boundary_passes_at_frozen_threshold() -> None:
    profile = _loader().load("profile_s1_contextual_comparison")
    engine = RuleEngine()
    batch = engine.evaluate_profile(
        profile,
        [
            _evidence(
                metric="even_harmonic_growth_percent",
                value=5.0,
                unit="%",
                evidence_id="ev_boundary",
            )
        ],
    )
    growth = next(
        item
        for item in batch.evaluations
        if item.rule_id == "rule_even_harmonic_growth_acceptable"
    )
    assert growth.judgment == "pass"


def test_t_cx055_composition_registers_both_profiles() -> None:
    from signal_diag.app import composition

    assert composition._PROFILE_ID == "profile_s1_distortion"
    assert composition._CONTEXTUAL_PROFILE_ID == "profile_s1_contextual_comparison"
    assert composition._contextual_profile_path().is_file()
    assert composition._profile_path().is_file()
