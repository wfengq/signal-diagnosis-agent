"""Offline regression retest evaluation (contrast arms, no product benefit claims)."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict

from signal_diag.agent.retest_planner import (
    CompactFinding,
    RetestContext,
    RetestOption,
    RetestSelection,
)

RetestArm = Literal["fixed_strategy", "real_adapter_fake_transport"]

_KIND_PRIORITY: tuple[str, ...] = (
    "complete_conditions",
    "repeat_conditions",
    "lower_both_inputs",
)


class RevealedRetestOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    option_id: str
    resolved: bool


class RetestTruthLabel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    useful_option_ids: tuple[str, ...]


class RetestEvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    context: RetestContext
    revealed_outcomes: tuple[RevealedRetestOutcome, ...]
    truth: RetestTruthLabel


class RetestEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    arm: RetestArm
    status: Literal["completed", "failed", "missing"]
    selection: RetestSelection | None = None
    revealed: RevealedRetestOutcome | None = None
    elapsed_s: float | None = None
    call_count: int = 0


class ArmCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scheduled: int = 0
    completed: int = 0
    valid_selection: int = 0
    useful_retest: int = 0
    legal_abstain: int = 0
    error: int = 0
    missing: int = 0


class RetestEvaluationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    by_arm: dict[str, ArmCounts]


def choose_fixed_retest(context: RetestContext) -> RetestSelection:
    """Explicit contrast arm: deterministic catalog priority, not product wiring."""
    if not context.eligible_options:
        return RetestSelection(
            option_id=None,
            basis_refs=(),
            abstain_reason_code="no_eligible_options",
        )
    finding_ids = tuple(f.finding_id for f in context.compact_findings)
    if not finding_ids:
        return RetestSelection(
            option_id=None,
            basis_refs=(),
            abstain_reason_code="insufficient_basis",
        )
    by_kind: dict[str, RetestOption] = {}
    for option in context.eligible_options:
        by_kind.setdefault(option.kind, option)
    chosen: RetestOption | None = None
    for kind in _KIND_PRIORITY:
        if kind in by_kind:
            chosen = by_kind[kind]
            break
    if chosen is None:
        chosen = context.eligible_options[0]
    return RetestSelection(
        option_id=chosen.option_id,
        basis_refs=finding_ids,
        abstain_reason_code=None,
    )


def _truth_for_case(
    cases: tuple[RetestEvaluationCase, ...],
    case_id: str,
) -> RetestTruthLabel:
    for case in cases:
        if case.case_id == case_id:
            return case.truth
    raise ValueError("case_id not in planned set")


def score_retest_cases(
    cases: tuple[RetestEvaluationCase, ...],
    results: tuple[RetestEvaluationResult, ...],
) -> RetestEvaluationSummary:
    if not cases:
        return RetestEvaluationSummary(by_arm={})

    planned_ids = [case.case_id for case in cases]
    if len(planned_ids) != len(set(planned_ids)):
        raise ValueError("duplicate case_id in cases")

    planned_set = frozenset(planned_ids)
    seen_keys: set[tuple[str, RetestArm]] = set()
    by_arm: dict[RetestArm, dict[str, RetestEvaluationResult]] = defaultdict(dict)

    for result in results:
        if result.case_id not in planned_set:
            raise ValueError("result case_id not in planned set")
        key = (result.case_id, result.arm)
        if key in seen_keys:
            raise ValueError("duplicate (case_id, arm) in results")
        seen_keys.add(key)
        by_arm[result.arm][result.case_id] = result

    summary: dict[str, ArmCounts] = {}
    scheduled = len(cases)
    for arm, result_map in by_arm.items():
        tallies = {
            "scheduled": scheduled,
            "completed": 0,
            "valid_selection": 0,
            "useful_retest": 0,
            "legal_abstain": 0,
            "error": 0,
            "missing": 0,
        }
        for case_id in planned_ids:
            row = result_map.get(case_id)
            if row is None or row.status == "missing":
                tallies["missing"] += 1
                continue
            if row.status == "failed":
                tallies["error"] += 1
                continue
            if row.status != "completed":
                raise ValueError(f"unexpected result status: {row.status!r}")
            tallies["completed"] += 1
            selection = row.selection
            if selection is None:
                continue
            if selection.option_id is not None:
                tallies["valid_selection"] += 1
                truth = _truth_for_case(cases, case_id)
                if (
                    selection.option_id in truth.useful_option_ids
                    and row.revealed is not None
                    and row.revealed.option_id == selection.option_id
                    and row.revealed.resolved
                ):
                    tallies["useful_retest"] += 1
            elif selection.abstain_reason_code is not None:
                tallies["legal_abstain"] += 1
        summary[arm] = ArmCounts(**tallies)

    return RetestEvaluationSummary(by_arm=summary)


def reveal_outcome_for_selection(
    case: RetestEvaluationCase,
    selection: RetestSelection,
) -> RevealedRetestOutcome | None:
    if selection.option_id is None:
        return None
    for outcome in case.revealed_outcomes:
        if outcome.option_id == selection.option_id:
            return outcome
    return None
