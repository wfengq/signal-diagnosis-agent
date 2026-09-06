"""T-CX235: v9.10 policy-specific deterministic rule closure."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.agent.diagnosis import CausalPolicyVersion
from signal_diag.agent.models import Observation
from signal_diag.agent.rule_closure import (
    automatic_profile_for_tool,
    automatic_profiles_for_tool,
    build_rule_closure_request,
    required_rule_profile,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import DiagnosticMode, StimulusContext
from signal_diag.tools.evidence import Evidence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
V9_10_PROFILE = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_contextual_comparison_v9_10.yaml"
)


def _context(mode: DiagnosticMode) -> StimulusContext:
    if mode == "paired_reference":
        return StimulusContext(
            mode=mode,
            test_signal_id="sig_test",
            reference_signal_id="sig_reference",
            assertion_source="user_supplied",
        )
    if mode == "nominal_single_tone":
        return StimulusContext(
            mode=mode,
            test_signal_id="sig_test",
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            assertion_source="user_supplied",
        )
    return StimulusContext(
        mode=mode,
        test_signal_id="sig_test",
        assertion_source="user_supplied",
    )


def _evidence(
    evidence_id: str,
    call_id: str,
    metric: str,
    value: bool | float,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="analyze_contextual_distortion",
        call_id=call_id,
        metric=metric,
        value=value,
        validity="valid",
        channel="mixdown",
    )


@pytest.mark.parametrize(
    "policy",
    [
        "v9_7_deterministic_rule_closure",
        "v9_8_claim_reference_recovery",
        "v9_9_paired_reference_recovery",
    ],
)
@pytest.mark.parametrize("mode", ["paired_reference", "nominal_single_tone"])
def test_t_cx235_older_policies_keep_original_contextual_profile(
    policy: CausalPolicyVersion,
    mode: DiagnosticMode,
) -> None:
    assert required_rule_profile(
        causal_policy_version=policy,
        stimulus_context=_context(mode),
        tool_name="analyze_contextual_distortion",
    ) == "profile_s1_contextual_comparison"


@pytest.mark.parametrize("mode", ["paired_reference", "nominal_single_tone"])
def test_t_cx235_v9_10_selects_additive_profile_only_for_contextual_modes(
    mode: DiagnosticMode,
) -> None:
    policy: CausalPolicyVersion = "v9_10_contextual_clipping_recovery"
    assert required_rule_profile(
        causal_policy_version=policy,
        stimulus_context=_context(mode),
        tool_name="analyze_contextual_distortion",
    ) == "profile_s1_contextual_comparison_v9_10"
    assert required_rule_profile(
        causal_policy_version=policy,
        stimulus_context=_context("single_signal"),
        tool_name="analyze_contextual_distortion",
    ) is None


@pytest.mark.parametrize(
    ("ratio", "flat_top", "expected_judgment"),
    [(0.005, False, "pass"), (0.02, True, "fail")],
)
def test_t_cx235_new_rules_use_exact_triggering_observation_suffix(
    ratio: float,
    flat_top: bool,
    expected_judgment: str,
) -> None:
    stale = (
        _evidence("ev_stale_ratio", "call_context_stale", "test_clipping_ratio", 0.0),
        _evidence("ev_stale_flat", "call_context_stale", "test_flat_top_detected", False),
    )
    suffix = (
        _evidence("ev_current_ratio", "call_context_current", "test_clipping_ratio", ratio),
        _evidence(
            "ev_current_flat",
            "call_context_current",
            "test_flat_top_detected",
            flat_top,
        ),
    )
    observation = Observation(
        observation_id="obs_context_current",
        call_id="call_context_current",
        tool_name="analyze_contextual_distortion",
        normalized_arguments={},
        purpose="evaluate contextual clipping closure",
        status="success",
        evidence_refs=tuple(item.evidence_id for item in suffix),
    )
    request = build_rule_closure_request(
        profile_id="profile_s1_contextual_comparison_v9_10",
        observation=observation,
    )
    assert request is not None
    assert request.evidence_refs == ("ev_current_ratio", "ev_current_flat")

    profile = YamlRuleProfileLoader(
        {"profile_s1_contextual_comparison_v9_10": V9_10_PROFILE}
    ).load(request.profile_id)
    batch = RuleEngine().evaluate_profile(
        profile,
        (*stale, *suffix),
        evidence_filter=frozenset(request.evidence_refs),
    )
    by_rule = {evaluation.rule_id: evaluation for evaluation in batch.evaluations}

    ratio_evaluation = by_rule["rule_test_clipping_ratio_acceptable"]
    flat_evaluation = by_rule["rule_test_flat_top_absent"]
    assert ratio_evaluation.judgment == expected_judgment
    assert flat_evaluation.judgment == expected_judgment
    assert ratio_evaluation.evidence_refs == ("ev_current_ratio",)
    assert flat_evaluation.evidence_refs == ("ev_current_flat",)
    assert set(ratio_evaluation.evidence_refs + flat_evaluation.evidence_refs) == {
        item.evidence_id for item in suffix
    }


def test_t_cx235_automatic_profiles_include_v9_10_contextual() -> None:
    assert automatic_profile_for_tool("analyze_contextual_distortion") == (
        "profile_s1_contextual_comparison"
    )
    assert automatic_profiles_for_tool("analyze_contextual_distortion") == frozenset(
        {
            "profile_s1_contextual_comparison",
            "profile_s1_contextual_comparison_v9_10",
        }
    )
