"""T-CX167–T-CX174: pure v9.7 deterministic rule-closure mapping."""

from __future__ import annotations

import pytest

from signal_diag.agent.diagnosis import _CONTEXTUAL_CAUSAL_POLICIES, CausalPolicyVersion
from signal_diag.agent.models import Observation, ToolStatus
from signal_diag.agent.rule_closure import (
    RuleClosureInvariantError,
    build_rule_closure_request,
    required_rule_profile,
)
from signal_diag.signal.context import DiagnosticMode, StimulusContext
from signal_diag.tools.contracts import ToolName


def make_context(mode: DiagnosticMode) -> StimulusContext:
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


def make_observation(
    *,
    tool_name: ToolName,
    status: ToolStatus,
    evidence_refs: tuple[str, ...],
) -> Observation:
    return Observation(
        observation_id="obs_closure_test",
        call_id="call_closure_test",
        tool_name=tool_name,
        normalized_arguments={},
        purpose="test deterministic closure",
        status=status,
        evidence_refs=evidence_refs,
        error_message="tool failed" if status == "error" else None,
    )


def test_t_cx167_v9_7_policy_literal_and_contextual_membership() -> None:
    allowed: tuple[CausalPolicyVersion, ...] = (
        "v9_4_legacy",
        "v9_5_contextual",
        "v9_6_contextual",
        "v9_7_deterministic_rule_closure",
    )
    assert "v9_7_deterministic_rule_closure" in allowed
    assert "v9_7_deterministic_rule_closure" in _CONTEXTUAL_CAUSAL_POLICIES
    assert "v9_6_contextual" in _CONTEXTUAL_CAUSAL_POLICIES
    assert "v9_5_contextual" in _CONTEXTUAL_CAUSAL_POLICIES


@pytest.mark.parametrize("mode", ["single_signal", "nominal_single_tone", "paired_reference"])
def test_t_cx168_clipping_maps_to_distortion_in_every_mode(
    mode: DiagnosticMode,
) -> None:
    assert required_rule_profile(
        causal_policy_version="v9_7_deterministic_rule_closure",
        stimulus_context=make_context(mode),
        tool_name="detect_clipping",
    ) == "profile_s1_distortion"


def test_t_cx169_paired_contextual_maps_to_contextual_profile() -> None:
    assert required_rule_profile(
        causal_policy_version="v9_7_deterministic_rule_closure",
        stimulus_context=make_context("paired_reference"),
        tool_name="analyze_contextual_distortion",
    ) == "profile_s1_contextual_comparison"


def test_t_cx170_nominal_contextual_maps_to_contextual_profile() -> None:
    assert required_rule_profile(
        causal_policy_version="v9_7_deterministic_rule_closure",
        stimulus_context=make_context("nominal_single_tone"),
        tool_name="analyze_contextual_distortion",
    ) == "profile_s1_contextual_comparison"


def test_t_cx171_single_signal_harmonic_maps_to_distortion() -> None:
    assert required_rule_profile(
        causal_policy_version="v9_7_deterministic_rule_closure",
        stimulus_context=make_context("single_signal"),
        tool_name="analyze_harmonic_distortion",
    ) == "profile_s1_distortion"
    for mode in ("paired_reference", "nominal_single_tone"):
        assert (
            required_rule_profile(
                causal_policy_version="v9_7_deterministic_rule_closure",
                stimulus_context=make_context(mode),
                tool_name="analyze_harmonic_distortion",
            )
            is None
        )


@pytest.mark.parametrize(
    ("tool_name", "mode"),
    [
        ("analyze_spectrum", "single_signal"),
        ("estimate_fundamental", "paired_reference"),
        ("analyze_contextual_distortion", "single_signal"),
    ],
)
def test_t_cx172_spectrum_fundamental_and_mismatched_tools_create_no_closure(
    tool_name: ToolName,
    mode: DiagnosticMode,
) -> None:
    assert (
        required_rule_profile(
            causal_policy_version="v9_7_deterministic_rule_closure",
            stimulus_context=make_context(mode),
            tool_name=tool_name,
        )
        is None
    )
    error_obs = make_observation(
        tool_name="detect_clipping",
        status="error",
        evidence_refs=(),
    )
    assert (
        build_rule_closure_request(
            profile_id="profile_s1_distortion",
            observation=error_obs,
        )
        is None
    )


def test_t_cx173_invalid_observation_with_evidence_returns_request() -> None:
    observation = make_observation(
        tool_name="detect_clipping",
        status="invalid",
        evidence_refs=("ev_invalid_1", "ev_invalid_2"),
    )
    request = build_rule_closure_request(
        profile_id="profile_s1_distortion",
        observation=observation,
    )
    assert request is not None
    assert request.profile_id == "profile_s1_distortion"
    assert request.evidence_refs == ("ev_invalid_1", "ev_invalid_2")


def test_t_cx174_request_keeps_complete_ordered_observation_refs() -> None:
    observation = make_observation(
        tool_name="analyze_contextual_distortion",
        status="success",
        evidence_refs=("ev_context_valid", "ev_growth", "ev_test_thd"),
    )
    request = build_rule_closure_request(
        profile_id="profile_s1_contextual_comparison",
        observation=observation,
    )
    assert request is not None
    assert request.evidence_refs == (
        "ev_context_valid",
        "ev_growth",
        "ev_test_thd",
    )


def test_t_cx174_empty_non_error_evidence_raises_invariant() -> None:
    observation = make_observation(
        tool_name="detect_clipping",
        status="success",
        evidence_refs=(),
    )
    with pytest.raises(RuleClosureInvariantError):
        build_rule_closure_request(
            profile_id="profile_s1_distortion",
            observation=observation,
        )


@pytest.mark.parametrize(
    "policy",
    ["v9_4_legacy", "v9_5_contextual", "v9_6_contextual"],
)
def test_t_cx167_legacy_policies_return_no_automatic_profile(
    policy: CausalPolicyVersion,
) -> None:
    assert (
        required_rule_profile(
            causal_policy_version=policy,
            stimulus_context=make_context("paired_reference"),
            tool_name="detect_clipping",
        )
        is None
    )
