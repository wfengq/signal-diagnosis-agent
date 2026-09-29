"""T-CX234: additive v9.10 contextual rule-profile preservation."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from signal_diag.rules.loader import YamlRuleProfileLoader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_PROFILE = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_contextual_comparison_v1.yaml"
)
V9_10_PROFILE = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_contextual_comparison_v9_10.yaml"
)

ORIGINAL_PROFILE_SHA256 = (
    "19e0ea87abb8c200660b0aa83c7e10f9a6ac635d87c4aa9ea31c08bf9e840288"
)


def _loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader(
        {
            "profile_s1_contextual_comparison": ORIGINAL_PROFILE,
            "profile_s1_contextual_comparison_v9_10": V9_10_PROFILE,
        }
    )


def test_t_cx234_original_profile_bytes_are_preserved() -> None:
    assert sha256(ORIGINAL_PROFILE.read_bytes()).hexdigest() == ORIGINAL_PROFILE_SHA256


def test_t_cx234_additive_profile_copies_six_rules_and_adds_exactly_two() -> None:
    loader = _loader()
    original = loader.load("profile_s1_contextual_comparison")
    additive = loader.load("profile_s1_contextual_comparison_v9_10")

    assert additive.profile_id == "profile_s1_contextual_comparison_v9_10"
    assert additive.version == "1.0.0"
    assert len(original.rules) == 6
    assert tuple(rule.model_dump() for rule in additive.rules[:6]) == tuple(
        rule.model_dump() for rule in original.rules
    )

    added = additive.rules[6:]
    assert tuple(rule.rule_id for rule in added) == (
        "rule_test_clipping_ratio_acceptable",
        "rule_test_flat_top_absent",
    )
    assert [
        (rule.metric, rule.comparator, rule.threshold, rule.unit, rule.source_tool)
        for rule in added
    ] == [
        (
            "test_clipping_ratio",
            "lte",
            0.01,
            None,
            "analyze_contextual_distortion",
        ),
        (
            "test_flat_top_detected",
            "eq",
            False,
            None,
            "analyze_contextual_distortion",
        ),
    ]
    assert len(additive.rules) == 8
