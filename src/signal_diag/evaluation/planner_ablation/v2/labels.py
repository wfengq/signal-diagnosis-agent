"""Offline label review helpers for planner-ablation protocol revision (dev_2)."""

from __future__ import annotations

from collections.abc import Sequence

from signal_diag.evaluation.planner_ablation.v2.models import (
    STUDY_ID_V2,
    LabelReviewResult,
    ScenarioDefinition,
    Schedule,
)


def validate_labels(
    scenarios: Sequence[ScenarioDefinition],
    schedule: Schedule,
) -> LabelReviewResult:
    """Validate oracle/alias/U-C-G consistency. Returns pending review provenance."""
    errors: list[str] = []
    provenance = [
        "proposal_source=design_§5_mode_specific_oracle",
        "prior_output_exposure=disclosed",
        "independent_offline_review=required_before_seal",
        f"study_id={STUDY_ID_V2}",
    ]

    if not scenarios:
        errors.append("empty population")

    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    if len(by_id) != len(scenarios):
        errors.append("duplicate scenario_id in population")

    # Every schedule representative must exist in the offline population.
    for req in schedule.canonical_requests:
        if req.representative_scenario_id not in by_id:
            errors.append(
                f"schedule representative missing from population: "
                f"{req.representative_scenario_id}"
            )

    for alias_source, alias_target in schedule.scenario_aliases.items():
        source = by_id.get(alias_source)
        target = by_id.get(alias_target)
        if source is None or target is None:
            errors.append(f"missing alias endpoints: {alias_source}->{alias_target}")
            continue
        if source.single_oracle.fingerprint() != target.single_oracle.fingerprint():
            errors.append(
                "conflicting equal-input oracle labels for alias "
                f"{alias_source}->{alias_target}"
            )
        if source.test_wav_sha256 != target.test_wav_sha256:
            errors.append(
                f"alias {alias_source}->{alias_target} has unequal single test bytes"
            )

    # Expected clean/invalid single alias when both members are present.
    if "163185980dc8f7a4" in by_id and "825a759a0ea47bb7" in by_id:
        mapped = schedule.scenario_aliases.get("163185980dc8f7a4")
        if mapped != "825a759a0ea47bb7":
            errors.append(
                "missing alias 163185980dc8f7a4 -> 825a759a0ea47bb7 for shared single"
            )

    upgrade = {s.scenario_id for s in scenarios if s.in_upgrade_population}
    conditional = {s.scenario_id for s in scenarios if s.in_conditional_population}
    guidance = {s.scenario_id for s in scenarios if s.in_guidance_population}

    for scenario in scenarios:
        if scenario.in_conditional_population and not scenario.in_upgrade_population:
            errors.append(
                f"{scenario.scenario_id} cannot be in C without membership in U"
            )
        if (
            scenario.scenario_id == "163185980dc8f7a4"
            and scenario.in_conditional_population
        ):
            errors.append("invalid-reference control must stay outside C")
        if scenario.in_guidance_population and scenario.scenario_id not in {
            "a4a0853be9983f8c",
            "2be730b9113701de",
            "393940e92c58cf0b",
            "04f4068ec91d2621",
        }:
            errors.append(f"unexpected guidance member: {scenario.scenario_id}")
        if (
            scenario.in_upgrade_population
            and scenario.upgrade_target is None
            and scenario.scenario_id != "163185980dc8f7a4"
        ):
            errors.append(
                f"upgrade member {scenario.scenario_id} missing upgrade_target"
            )
        if (
            scenario.scenario_id == "163185980dc8f7a4"
            and scenario.upgrade_target is not None
        ):
            errors.append("invalid-reference control must not declare a resolution target")

        # Source/master consistency: identical ids must share source mapping.
        for other in scenarios:
            if other.scenario_id == scenario.scenario_id:
                continue
            if other.source_id == scenario.source_id and (
                other.parent_master_id != scenario.parent_master_id
            ):
                errors.append(
                    "inconsistent source/master mapping for "
                    f"{scenario.source_id}: {scenario.scenario_id} vs {other.scenario_id}"
                )

    # Fabricated approval is rejected even if a scenario review_record claims it.
    for scenario in scenarios:
        if scenario.review_record.status == "approved":
            errors.append(
                f"fabricated approval on {scenario.scenario_id}; "
                "independent offline review has not closed"
            )

    review_status = "pending"
    approved = False
    if errors:
        review_status = "rejected"

    return LabelReviewResult(
        errors=tuple(errors),
        review_status=review_status,
        approved=approved,
        review_provenance=tuple(provenance),
        upgrade_population=frozenset(upgrade),
        conditional_population=frozenset(conditional),
        guidance_population=frozenset(guidance),
    )
