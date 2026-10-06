"""Paired increment scoring for design §4.2."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict

from signal_diag.evaluation.agent_increment.models import ArmName, ArmOutcome, Family

IncrementLabel = Literal[
    "measurable_increment",
    "no_significant_increment",
    "negative",
    "not_held_out_line",
]


class FamilyScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    family: str
    case_count: int
    increment: int
    increment_label: IncrementLabel
    unsupported_positive_count: int
    evidence_traceability: float
    safety_hard_pass: bool
    t1_field_accuracy: float | None
    t1_correction_count: int | None
    t1_downstream_increment: int | None = None
    t2_localization_accuracy: float | None
    t2_agent_tool_calls: int | None
    t2_strong_tool_calls: int | None


def _label(case_count: int, increment: int) -> IncrementLabel:
    if case_count != 24:
        return "not_held_out_line"
    if increment >= 3:
        return "measurable_increment"
    if increment >= 0:
        return "no_significant_increment"
    return "negative"


def score_family(rows: list[ArmOutcome]) -> FamilyScore:
    if not rows:
        raise ValueError("family score requires outcomes")
    family: Family = rows[0].family
    grouped: dict[str, dict[ArmName, ArmOutcome]] = defaultdict(dict)
    for row in rows:
        if row.family != family:
            raise ValueError("score_family received more than one family")
        grouped[row.case_id][row.arm] = row
    agent_correct = 0
    strong_correct = 0
    agent_downstream = 0
    strong_downstream = 0
    unsupported = 0
    traceable = 0
    total_rows = 0
    field_correct = 0
    field_graded = 0
    corrections = 0
    localized = 0
    localized_graded = 0
    agent_tools = 0
    strong_tools = 0
    for case_id, arms in grouped.items():
        if set(arms) != {"agent", "strong_fixed", "weak_fixed"}:
            raise ValueError(f"case {case_id} is missing an arm")
        agent = arms["agent"]
        strong = arms["strong_fixed"]
        if family == "T1":
            agent_correct += int(agent.draft_all_correct)
            strong_correct += int(strong.draft_all_correct)
            agent_downstream += int(agent.conclusion_correct)
            strong_downstream += int(strong.conclusion_correct)
        else:
            agent_correct += int(agent.conclusion_correct)
            strong_correct += int(strong.conclusion_correct)
        for outcome in arms.values():
            total_rows += 1
            unsupported += int(outcome.unsupported_positive)
            traceable += int(outcome.evidence_traceable)
        field_correct += agent.context_fields_correct
        field_graded += agent.context_fields_graded
        corrections += agent.correction_count
        if agent.localization_correct is not None:
            localized_graded += 1
            localized += int(agent.localization_correct)
        agent_tools += agent.tool_calls
        strong_tools += arms["strong_fixed"].tool_calls
    increment = agent_correct - strong_correct
    traceability = traceable / total_rows
    safety = unsupported == 0 and traceability == 1.0
    if family == "T1":
        accuracy = None if field_graded == 0 else field_correct / field_graded
        return FamilyScore(
            family=family,
            case_count=len(grouped),
            increment=increment,
            increment_label=_label(len(grouped), increment),
            unsupported_positive_count=unsupported,
            evidence_traceability=traceability,
            safety_hard_pass=safety,
            t1_field_accuracy=accuracy,
            t1_correction_count=corrections,
            t1_downstream_increment=agent_downstream - strong_downstream,
            t2_localization_accuracy=None,
            t2_agent_tool_calls=None,
            t2_strong_tool_calls=None,
        )
    localization = None if localized_graded == 0 else localized / localized_graded
    return FamilyScore(
        family=family,
        case_count=len(grouped),
        increment=increment,
        increment_label=_label(len(grouped), increment),
        unsupported_positive_count=unsupported,
        evidence_traceability=traceability,
        safety_hard_pass=safety,
        t1_field_accuracy=None,
        t1_correction_count=None,
        t2_localization_accuracy=localization,
        t2_agent_tool_calls=agent_tools,
        t2_strong_tool_calls=strong_tools,
    )
