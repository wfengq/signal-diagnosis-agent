"""Pure Tool-to-profile mapping for v9.7 deterministic rule closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from signal_diag.signal.context import StimulusContext
from signal_diag.tools.contracts import ToolName

from .diagnosis import CausalPolicyVersion
from .models import Observation

RuleClosureProfileId = Literal[
    "profile_s1_distortion",
    "profile_s1_contextual_comparison",
    "profile_s1_contextual_comparison_v9_10",
]


@dataclass(frozen=True)
class RuleClosureRequest:
    profile_id: RuleClosureProfileId
    evidence_refs: tuple[str, ...]


class RuleClosureInvariantError(RuntimeError):
    """Raised when a relevant non-error Observation violates closure contracts."""


def automatic_profile_for_tool(tool_name: ToolName) -> RuleClosureProfileId | None:
    if tool_name == "detect_clipping":
        return "profile_s1_distortion"
    if tool_name == "analyze_harmonic_distortion":
        return "profile_s1_distortion"
    if tool_name == "analyze_contextual_distortion":
        return "profile_s1_contextual_comparison"
    return None


def automatic_profiles_for_tool(tool_name: ToolName) -> frozenset[RuleClosureProfileId]:
    """Profiles a Tool may emit via automatic rule closure across policies."""

    if tool_name == "analyze_contextual_distortion":
        return frozenset(
            {
                "profile_s1_contextual_comparison",
                "profile_s1_contextual_comparison_v9_10",
            }
        )
    profile = automatic_profile_for_tool(tool_name)
    return frozenset({profile}) if profile is not None else frozenset()


def required_rule_profile(
    *,
    causal_policy_version: CausalPolicyVersion,
    stimulus_context: StimulusContext,
    tool_name: ToolName,
) -> RuleClosureProfileId | None:
    if causal_policy_version not in {
        "v9_7_deterministic_rule_closure",
        "v9_8_claim_reference_recovery",
        "v9_9_paired_reference_recovery",
        "v9_10_contextual_clipping_recovery",
        "v9_11_mode_aware_no_fault_recovery",
    }:
        return None
    if tool_name == "analyze_harmonic_distortion":
        return (
            "profile_s1_distortion"
            if stimulus_context.mode == "single_signal"
            else None
        )
    if tool_name == "analyze_contextual_distortion":
        if stimulus_context.mode not in {
            "paired_reference",
            "nominal_single_tone",
        }:
            return None
        if causal_policy_version in {
            "v9_10_contextual_clipping_recovery",
            "v9_11_mode_aware_no_fault_recovery",
        }:
            return "profile_s1_contextual_comparison_v9_10"
        return "profile_s1_contextual_comparison"
    return automatic_profile_for_tool(tool_name)


def build_rule_closure_request(
    *,
    profile_id: RuleClosureProfileId,
    observation: Observation,
) -> RuleClosureRequest | None:
    if observation.status == "error":
        return None
    if not observation.evidence_refs:
        raise RuleClosureInvariantError(
            "relevant non-error Tool observation requires Evidence"
        )
    return RuleClosureRequest(profile_id, observation.evidence_refs)
