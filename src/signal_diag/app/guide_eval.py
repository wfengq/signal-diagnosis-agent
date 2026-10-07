"""Test guide acceptance run (D057 4A).

``python -m signal_diag.app.guide_eval --out DIR`` checks the 40 authored
scenarios (``evaluation/assets/guide_cases.json``) offline: each expected plan, as a
draft, must pass the validator. ``--live`` asks the real model once per case
(needs ``DEEPSEEK_API_KEY``, never written out) and scores plan accuracy,
key-parameter accuracy, invented numbers and unnecessary questions.

The model draft may become visible by default only with plan accuracy ≥ 90 %,
key-parameter accuracy ≥ 90 % and zero number rejections.

``--cases heldout`` scores the 20 held-out scenarios frozen before prompt 1.1
(D059); that set decides acceptance. Rejected model drafts are kept in their
rows (``rejection_detail``, ``rejected_draft``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any

from signal_diag.agent.guide import GUIDE_PROMPT_VERSION
from signal_diag.app.guide_service import (
    ENABLE_FLAG,
    GuideRejection,
    GuideService,
    build_guide_service,
)
from signal_diag.app.test_plan import (
    DEFAULT_LEVEL_LABELS,
    DEFAULT_RATE,
    GuideRequest,
    PlanDraft,
    PlanParameters,
    validate_plan_draft,
)

EVAL_SCHEMA = "guide_eval/1"
PLAN_BAR = 0.9
PARAMETER_BAR = 0.9
CASE_SETS = {"dev": "guide_cases.json", "heldout": "guide_cases_heldout.json"}


def load_cases(case_set: str = "dev") -> list[dict[str, Any]]:
    path = files("signal_diag").joinpath("evaluation", "assets", CASE_SETS[case_set])
    return list(json.loads(path.read_text(encoding="utf-8"))["cases"])


def request_for(case: dict[str, Any]) -> GuideRequest:
    return GuideRequest(
        text=case["text"],
        filenames=tuple(case["filenames"]),
        sample_rates_hz=tuple(case["sample_rates_hz"]),
    )


def oracle_draft(case: dict[str, Any]) -> PlanDraft:
    """The expected plan written as a draft (what a correct model would return)."""
    expected = case["expected"]
    plan = expected["plan_id"]
    missing: list[str] = []
    if plan == "sweep_levels":
        stated = expected["sample_rate_hz"]
        defaults = ["level_labels"] + ([] if stated else ["sample_rate_hz"])
        if expected["connection"] is None:
            missing.append("connection")
        params = PlanParameters(
            sample_rate_hz=stated or DEFAULT_RATE,
            level_labels=DEFAULT_LEVEL_LABELS["zh"],
            connection=expected["connection"],
            defaults=tuple(defaults),
        )
    else:
        reference = expected["reference_file"]
        test = next((name for name in case["filenames"] if name != reference), None)
        if plan == "nominal_tone" and expected["nominal_fundamental_hz"] is None:
            missing.append("nominal_fundamental_hz")
        params = PlanParameters(
            test_file=test,
            reference_file=reference,
            nominal_fundamental_hz=expected["nominal_fundamental_hz"],
        )
    return PlanDraft(
        plan_id=plan,
        parameters=params,
        missing_fields=tuple(missing),
        questions=tuple(f"{field}?" for field in missing),
        rationale_quotes=(case["quote"],),
    )


def _parameters_correct(case: dict[str, Any], draft: PlanDraft) -> bool:
    expected, p = case["expected"], draft.parameters
    checks = []
    if expected["connection"] is not None:
        checks.append(p.connection == expected["connection"])
    if expected["sample_rate_hz"] is not None:
        checks.append(p.sample_rate_hz == expected["sample_rate_hz"])
    if expected["nominal_fundamental_hz"] is not None:
        checks.append(p.nominal_fundamental_hz == expected["nominal_fundamental_hz"])
    if expected["reference_file"] is not None:
        checks.append(p.reference_file == expected["reference_file"])
    return all(checks)


def score(
    case: dict[str, Any],
    source: str,
    draft: PlanDraft | None,
    reason: str | None,
    rejection: GuideRejection | None = None,
) -> dict[str, Any]:
    plan_ok = draft is not None and draft.plan_id == case["expected"]["plan_id"]
    return {
        "case_id": case["case_id"],
        "tags": case["tags"],
        "expected_plan": case["expected"]["plan_id"],
        "source": source,
        "fallback_reason": reason,
        "plan_id": draft.plan_id if draft else None,
        "plan_correct": plan_ok,
        "parameters_correct": plan_ok and draft is not None and _parameters_correct(case, draft),
        "unnecessary_questions": bool(case["complete"] and draft is not None and draft.questions),
        "draft": draft.model_dump(mode="json") if draft else None,
        "prompt_version": GUIDE_PROMPT_VERSION,
        "rejection_detail": rejection.detail if rejection else None,
        "rejected_draft": rejection.raw if rejection else None,
    }


def summarize(rows: list[dict[str, Any]], *, live: bool, case_set: str = "dev") -> dict[str, Any]:
    total = len(rows)
    plan = sum(row["plan_correct"] for row in rows) / total
    parameters = sum(row["parameters_correct"] for row in rows) / total
    reasons = Counter(row["fallback_reason"] for row in rows if row["fallback_reason"])
    complete = [row for row in rows if row["source"] == "model"]
    return {
        "schema": EVAL_SCHEMA,
        "live": live,
        "case_set": case_set,
        "prompt_version": GUIDE_PROMPT_VERSION,
        "cases": total,
        "model_calls": total if live else 0,
        "plan_accuracy": round(plan, 4),
        "parameter_accuracy": round(parameters, 4),
        "fallback_reasons": dict(reasons),
        "number_rejections": reasons.get("validation_failed:number", 0),
        "rejection_details": dict(
            Counter(row["rejection_detail"] for row in rows if row.get("rejection_detail"))
        ),
        "unnecessary_question_cases": sum(row["unnecessary_questions"] for row in complete),
        "by_expected_plan": {
            plan_id: f"{sum(r['plan_correct'] for r in rows if r['expected_plan'] == plan_id)}/"
            f"{sum(1 for r in rows if r['expected_plan'] == plan_id)}"
            for plan_id in sorted({r["expected_plan"] for r in rows})
        },
        "bars": {"plan_accuracy": PLAN_BAR, "parameter_accuracy": PARAMETER_BAR, "number_rejections": 0},
        "meets_bar": live
        and plan >= PLAN_BAR
        and parameters >= PARAMETER_BAR
        and reasons.get("validation_failed:number", 0) == 0,
    }


async def run(
    out: Path, *, live: bool, service: GuideService | None = None, case_set: str = "dev"
) -> dict[str, Any]:
    cases = load_cases(case_set)
    rows: list[dict[str, Any]] = []
    if not live:
        for case in cases:
            draft = oracle_draft(case)
            validate_plan_draft(draft, request_for(case))
            rows.append(score(case, "oracle", draft, None))
    else:
        if service is None:
            if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
                raise SystemExit("--live needs DEEPSEEK_API_KEY")
            service = build_guide_service({**os.environ, ENABLE_FLAG: "enabled"})
        rejections: list[GuideRejection] = []
        service = service.with_rejection_sink(rejections.append)
        try:
            for case in cases:
                rejections.clear()
                result = await service.draft(request_for(case), use_model=True)
                rejection = rejections[-1] if rejections else None
                rows.append(score(case, result.source, result.draft, result.fallback_reason, rejection))
        finally:
            await service.aclose()
    summary = summarize(rows, live=live, case_set=case_set)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m signal_diag.app.guide_eval")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--cases", choices=sorted(CASE_SETS), default="dev")
    args = parser.parse_args(argv)
    summary = asyncio.run(run(args.out, live=args.live, case_set=args.cases))
    keys = ("cases", "model_calls", "plan_accuracy", "parameter_accuracy", "number_rejections", "meets_bar")
    print(json.dumps({key: summary[key] for key in keys}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
