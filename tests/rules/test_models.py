"""Rule profile model and loader tests (T094, T095, T097)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleDefinition, RuleProfile

VALID_PROFILE_YAML = """\
profile_id: profile_test
version: 1.0.0-demo
description: Test profile for loader injection.
rules:
  - rule_id: rule_ratio
    metric: clipping_ratio
    source_tool: detect_clipping
    comparator: lte
    threshold: 0.01
    description: demo ratio
"""

YAML_BOOL_PROFILE = """\
profile_id: profile_test
version: 1.0.0-demo
description: YAML native bool thresholds must remain bool.
rules:
  - rule_id: rule_false
    metric: clipping_detected
    source_tool: detect_clipping
    comparator: eq
    threshold: false
    description: yaml false
  - rule_id: rule_true
    metric: valid
    source_tool: analyze_harmonic_distortion
    comparator: eq
    threshold: true
    description: yaml true
"""

SHIPPED_S1_PROFILE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)


def test_t093_rule_models_instantiate_frozen_profile() -> None:
    rule = RuleDefinition(
        rule_id="rule_ratio",
        metric="clipping_ratio",
        source_tool="detect_clipping",
        comparator="lte",
        threshold=0.01,
        description="demo ratio",
    )
    profile = RuleProfile(
        profile_id="profile_test",
        version="1",
        description="test",
        rules=(rule,),
    )
    assert profile.profile_id == "profile_test"
    assert profile.rules[0].threshold == 0.01
    dumped = profile.model_dump()
    assert dumped["rules"][0]["threshold"] == 0.01


def test_t093_threshold_scalar_categories_preserved() -> None:
    bool_rule = RuleDefinition(
        rule_id="rule_bool",
        metric="clipping_detected",
        source_tool="detect_clipping",
        comparator="eq",
        threshold=False,
        description="bool threshold",
    )
    assert bool_rule.threshold is False
    int_rule = RuleDefinition(
        rule_id="rule_int",
        metric="count",
        source_tool="detect_clipping",
        comparator="lte",
        threshold=1,
        description="int threshold",
    )
    assert int_rule.threshold == 1
    assert type(int_rule.threshold) is int
    float_rule = RuleDefinition(
        rule_id="rule_float",
        metric="thd_percent",
        source_tool="analyze_harmonic_distortion",
        comparator="lte",
        threshold=5.0,
        unit="%",
        description="float threshold",
    )
    assert float_rule.threshold == 5.0
    assert type(float_rule.threshold) is float


def test_t094_duplicate_rule_ids_are_rejected() -> None:
    rule = RuleDefinition(
        rule_id="rule_ratio",
        metric="clipping_ratio",
        source_tool="detect_clipping",
        comparator="lte",
        threshold=0.01,
        description="demo ratio",
    )
    with pytest.raises(ValidationError, match="duplicate rule_id"):
        RuleProfile(
            profile_id="profile_test",
            version="1",
            description="test",
            rules=(rule, rule),
        )


def test_t095_empty_profile_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RuleProfile(
            profile_id="profile_test",
            version="1",
            description="test",
            rules=(),
        )


def test_t097_loader_preserves_yaml_bool_thresholds(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(YAML_BOOL_PROFILE, encoding="utf-8")
    loaded = YamlRuleProfileLoader({"profile_test": profile_path}).load("profile_test")
    false_rule, true_rule = loaded.rules
    assert type(false_rule.threshold) is bool
    assert false_rule.threshold is False
    assert type(true_rule.threshold) is bool
    assert true_rule.threshold is True

    shipped = YamlRuleProfileLoader({"profile_s1_distortion": SHIPPED_S1_PROFILE}).load(
        "profile_s1_distortion"
    )
    by_id = {rule.rule_id: rule for rule in shipped.rules}
    assert type(by_id["rule_clipping_detected_absent"].threshold) is bool
    assert by_id["rule_clipping_detected_absent"].threshold is False
    assert type(by_id["rule_flat_top_absent"].threshold) is bool
    assert by_id["rule_flat_top_absent"].threshold is False
    assert type(by_id["rule_harmonic_analysis_valid"].threshold) is bool
    assert by_id["rule_harmonic_analysis_valid"].threshold is True


def test_t097_loader_uses_explicit_mapping(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(VALID_PROFILE_YAML, encoding="utf-8")
    loader = YamlRuleProfileLoader({"profile_test": profile_path})
    assert loader.load("profile_test").profile_id == "profile_test"
    with pytest.raises(KeyError):
        loader.load("profile_missing")


def test_t097_loader_rejects_profile_id_mismatch(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(VALID_PROFILE_YAML, encoding="utf-8")
    loader = YamlRuleProfileLoader({"profile_other": profile_path})
    with pytest.raises(ValueError, match="profile_id does not match"):
        loader.load("profile_other")


def test_t_cx_loader_can_register_contextual_profile_alongside_s1() -> None:
    contextual = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "signal_diag"
        / "rules"
        / "profiles"
        / "s1_contextual_comparison_v1.yaml"
    )
    loader = YamlRuleProfileLoader(
        {
            "profile_s1_distortion": SHIPPED_S1_PROFILE,
            "profile_s1_contextual_comparison": contextual,
        }
    )
    assert loader.load("profile_s1_distortion").version == "1.0.0-demo"
    assert loader.load("profile_s1_contextual_comparison").version == "1.0.0"
