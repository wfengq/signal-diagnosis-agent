"""Phase C Task 8: offline retest contrast evaluation and service chain."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from signal_diag.agent.retest_planner import (
    CompactFinding,
    RetestContext,
    RetestOption,
    RetestSelection,
    build_retest_context,
)
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.regression import (
    RegressionWorkbenchService,
    RetestLink,
)
from signal_diag.app.regression_reporting import build_case_report
from signal_diag.evaluation.regression import (
    RetestEvaluationCase,
    RetestEvaluationResult,
    RetestTruthLabel,
    RevealedRetestOutcome,
    choose_fixed_retest,
    reveal_outcome_for_selection,
    score_retest_cases,
)
from signal_diag.signal import generate_sine
from tests.app.test_regression_recommendations import (
    NOW,
    _conditions,
    _configured_service,
    _FakeSDK,
    _planner_with_sdk,
)
from tests.app.test_regression_service import _upload

NOW_EVAL = datetime(2026, 10, 5, 6, 0, tzinfo=UTC)


def _mono_wav() -> bytes:
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.5,
        amplitude=0.4,
    )
    return encode_pcm32_wav(case.record.samples, sample_rate_hz=48_000)


async def _comparison_record(**condition_overrides: object):
    service = RegressionWorkbenchService(clock=lambda: NOW_EVAL)
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions(**condition_overrides)),
        request_id="cmp-eval",
    )
    await service.aclose()
    return snap.comparisons[0].record


def _case_from_record(
    case_id: str,
    record,
    *,
    useful_option_ids: tuple[str, ...],
    revealed: tuple[RevealedRetestOutcome, ...],
) -> RetestEvaluationCase:
    return RetestEvaluationCase(
        case_id=case_id,
        context=build_retest_context(record),
        revealed_outcomes=revealed,
        truth=RetestTruthLabel(useful_option_ids=useful_option_ids),
    )


def _manual_context(
    *,
    eligible: tuple[RetestOption, ...],
    findings: tuple[CompactFinding, ...] = (),
) -> RetestContext:
    return RetestContext(
        comparison_id="cmp_manual",
        comparison_digest="a" * 64,
        compact_findings=findings,
        eligible_options=eligible,
    )


@pytest.mark.asyncio
async def test_fixed_strategy_valid_suggestion_scores_useful_retest() -> None:
    record = await _comparison_record(same_input="unknown")
    eval_case = _case_from_record(
        "case_ok",
        record,
        useful_option_ids=("opt_complete_conditions",),
        revealed=(
            RevealedRetestOutcome(
                option_id="opt_complete_conditions",
                resolved=True,
            ),
        ),
    )
    selection = choose_fixed_retest(eval_case.context)
    assert selection.option_id == "opt_complete_conditions"
    revealed = reveal_outcome_for_selection(eval_case, selection)
    result = RetestEvaluationResult(
        case_id="case_ok",
        arm="fixed_strategy",
        status="completed",
        selection=selection,
        revealed=revealed,
        call_count=0,
    )
    summary = score_retest_cases((eval_case,), (result,))
    counts = summary.by_arm["fixed_strategy"]
    assert counts.scheduled == 1
    assert counts.completed == 1
    assert counts.valid_selection == 1
    assert counts.useful_retest == 1


@pytest.mark.asyncio
async def test_wrong_selection_not_counted_useful() -> None:
    record = await _comparison_record(same_input="unknown")
    eval_case = _case_from_record(
        "case_wrong",
        record,
        useful_option_ids=("opt_complete_conditions",),
        revealed=(
            RevealedRetestOutcome(
                option_id="opt_complete_conditions",
                resolved=True,
            ),
        ),
    )
    result = RetestEvaluationResult(
        case_id="case_wrong",
        arm="fixed_strategy",
        status="completed",
        selection=RetestSelection(
            option_id="opt_repeat_conditions",
            basis_refs=("decl_same_input",),
            abstain_reason_code=None,
        ),
        revealed=RevealedRetestOutcome(
            option_id="opt_repeat_conditions",
            resolved=True,
        ),
        call_count=0,
    )
    summary = score_retest_cases((eval_case,), (result,))
    assert summary.by_arm["fixed_strategy"].useful_retest == 0


@pytest.mark.asyncio
async def test_no_suggestion_legal_abstain() -> None:
    ctx = _manual_context(eligible=(), findings=())
    selection = choose_fixed_retest(ctx)
    assert selection.abstain_reason_code == "no_eligible_options"
    eval_case = RetestEvaluationCase(
        case_id="case_none",
        context=ctx,
        revealed_outcomes=(),
        truth=RetestTruthLabel(useful_option_ids=()),
    )
    result = RetestEvaluationResult(
        case_id="case_none",
        arm="fixed_strategy",
        status="completed",
        selection=selection,
        revealed=None,
    )
    summary = score_retest_cases((eval_case,), (result,))
    counts = summary.by_arm["fixed_strategy"]
    assert counts.legal_abstain == 1
    assert counts.useful_retest == 0


def test_missing_conditions_complete_priority() -> None:
    complete = RetestOption(
        option_id="opt_complete_conditions",
        kind="complete_conditions",
        required_inputs=("declared_conditions",),
        keep_conditions=("baseline_version",),
        explanation_template="Complete conditions.",
    )
    repeat = RetestOption(
        option_id="opt_repeat_conditions",
        kind="repeat_conditions",
        required_inputs=("baseline_wav", "candidate_wav"),
        keep_conditions=("stimulus_key",),
        explanation_template="Repeat.",
    )
    ctx = _manual_context(
        eligible=(complete, repeat),
        findings=(
            CompactFinding(
                finding_id="decl_same_input",
                kind="declaration",
                code="same_input=unknown",
            ),
        ),
    )
    selection = choose_fixed_retest(ctx)
    assert selection.option_id == "opt_complete_conditions"


def test_retest_unresolved_not_useful() -> None:
    ctx = _manual_context(
        eligible=(
            RetestOption(
                option_id="opt_complete_conditions",
                kind="complete_conditions",
                required_inputs=("declared_conditions",),
                keep_conditions=("baseline_version",),
                explanation_template="Complete.",
            ),
        ),
        findings=(
            CompactFinding(
                finding_id="decl_same_input",
                kind="declaration",
                code="same_input=unknown",
            ),
        ),
    )
    eval_case = RetestEvaluationCase(
        case_id="case_unresolved",
        context=ctx,
        revealed_outcomes=(
            RevealedRetestOutcome(
                option_id="opt_complete_conditions",
                resolved=False,
            ),
        ),
        truth=RetestTruthLabel(useful_option_ids=("opt_complete_conditions",)),
    )
    selection = choose_fixed_retest(ctx)
    result = RetestEvaluationResult(
        case_id="case_unresolved",
        arm="fixed_strategy",
        status="completed",
        selection=selection,
        revealed=eval_case.revealed_outcomes[0],
    )
    summary = score_retest_cases((eval_case,), (result,))
    assert summary.by_arm["fixed_strategy"].useful_retest == 0
    assert summary.by_arm["fixed_strategy"].valid_selection == 1


def test_execution_failure_counts_error() -> None:
    ctx = _manual_context(
        eligible=(
            RetestOption(
                option_id="opt_complete_conditions",
                kind="complete_conditions",
                required_inputs=("declared_conditions",),
                keep_conditions=("baseline_version",),
                explanation_template="Complete.",
            ),
        ),
        findings=(
            CompactFinding(
                finding_id="decl_same_input",
                kind="declaration",
                code="same_input=unknown",
            ),
        ),
    )
    eval_case = RetestEvaluationCase(
        case_id="case_fail",
        context=ctx,
        revealed_outcomes=(),
        truth=RetestTruthLabel(useful_option_ids=("opt_complete_conditions",)),
    )
    result = RetestEvaluationResult(
        case_id="case_fail",
        arm="real_adapter_fake_transport",
        status="failed",
        selection=None,
        revealed=None,
        call_count=1,
    )
    summary = score_retest_cases((eval_case,), (result,))
    counts = summary.by_arm["real_adapter_fake_transport"]
    assert counts.error == 1
    assert counts.completed == 0


def test_two_planned_cases_completed_denominator_is_two() -> None:
    ctx = _manual_context(
        eligible=(
            RetestOption(
                option_id="opt_complete_conditions",
                kind="complete_conditions",
                required_inputs=("declared_conditions",),
                keep_conditions=("baseline_version",),
                explanation_template="Complete.",
            ),
        ),
        findings=(
            CompactFinding(
                finding_id="decl_same_input",
                kind="declaration",
                code="same_input=unknown",
            ),
        ),
    )
    case_ok = RetestEvaluationCase(
        case_id="ok",
        context=ctx,
        revealed_outcomes=(
            RevealedRetestOutcome(
                option_id="opt_complete_conditions",
                resolved=True,
            ),
        ),
        truth=RetestTruthLabel(useful_option_ids=("opt_complete_conditions",)),
    )
    case_bad = RetestEvaluationCase(
        case_id="bad",
        context=ctx,
        revealed_outcomes=(),
        truth=RetestTruthLabel(useful_option_ids=("opt_complete_conditions",)),
    )
    selection = choose_fixed_retest(ctx)
    results = (
        RetestEvaluationResult(
            case_id="ok",
            arm="fixed_strategy",
            status="completed",
            selection=selection,
            revealed=case_ok.revealed_outcomes[0],
        ),
        RetestEvaluationResult(
            case_id="bad",
            arm="fixed_strategy",
            status="failed",
            selection=None,
        ),
    )
    summary = score_retest_cases((case_ok, case_bad), results)
    counts = summary.by_arm["fixed_strategy"]
    assert counts.scheduled == 2
    assert counts.completed == 1
    assert counts.error == 1


def test_missing_planned_result_counts_missing() -> None:
    ctx = _manual_context(
        eligible=(),
        findings=(),
    )
    eval_case = RetestEvaluationCase(
        case_id="only",
        context=ctx,
        revealed_outcomes=(),
        truth=RetestTruthLabel(useful_option_ids=()),
    )
    result = RetestEvaluationResult(
        case_id="only",
        arm="fixed_strategy",
        status="missing",
    )
    summary = score_retest_cases((eval_case,), (result,))
    assert summary.by_arm["fixed_strategy"].missing == 1


def test_score_rejects_duplicate_case_arm() -> None:
    ctx = _manual_context(eligible=(), findings=())
    eval_case = RetestEvaluationCase(
        case_id="dup",
        context=ctx,
        revealed_outcomes=(),
        truth=RetestTruthLabel(useful_option_ids=()),
    )
    row = RetestEvaluationResult(
        case_id="dup",
        arm="fixed_strategy",
        status="missing",
    )
    with pytest.raises(ValueError, match="duplicate"):
        score_retest_cases((eval_case,), (row, row))


def test_real_adapter_arm_label_only_not_product_intelligence() -> None:
    """real_adapter_fake_transport scores transport wiring, not model quality."""
    ctx = _manual_context(eligible=(), findings=())
    eval_case = RetestEvaluationCase(
        case_id="adapter",
        context=ctx,
        revealed_outcomes=(),
        truth=RetestTruthLabel(useful_option_ids=()),
    )
    result = RetestEvaluationResult(
        case_id="adapter",
        arm="real_adapter_fake_transport",
        status="completed",
        selection=RetestSelection(
            option_id=None,
            basis_refs=(),
            abstain_reason_code="no_eligible_options",
        ),
        call_count=1,
    )
    summary = score_retest_cases((eval_case,), (result,))
    assert "real_adapter_fake_transport" in summary.by_arm
    assert "advantage" not in summary.model_dump()
    assert summary.by_arm["real_adapter_fake_transport"].legal_abstain == 1


def test_empty_cases_yields_zero_counts() -> None:
    summary = score_retest_cases((), ())
    assert summary.by_arm == {}


@pytest.mark.asyncio
async def test_service_chain_oracle_never_reaches_planner() -> None:
    sdk = _FakeSDK()
    service = _configured_service(sdk)
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions(same_input="unknown")),
        request_id="cmp-chain",
    )
    comparison_id = snap.comparisons[0].comparison_id
    sdk.completions.text = json.dumps(
        {
            "option_id": "opt_complete_conditions",
            "basis_refs": ["decl_same_input"],
            "abstain_reason_code": None,
        }
    )
    after_rec = await service.request_recommendation(
        case.case_id,
        comparison_id,
        request_id="rec-chain",
    )
    completed = [
        row
        for row in after_rec.recommendations
        if row.status == "completed" and row.comparison_id == comparison_id
    ]
    assert len(completed) == 1
    recommendation_id = completed[0].recommendation_id
    retest_snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions(same_input="yes")),
        request_id="retest-chain",
        link=RetestLink(
            kind="recommendation",
            parent_comparison_id=comparison_id,
            recommendation_id=recommendation_id,
        ),
    )
    report = build_case_report(retest_snap, generated_at=NOW)
    assert report.case_id == case.case_id
    assert len(report.comparisons) >= 2
    assert len(sdk.completions.calls) == 1
    user_payload = json.loads(
        sdk.completions.calls[0]["messages"][1]["content"]
    )
    forbidden_keys = {
        "truth",
        "useful_option_ids",
        "revealed_outcomes",
        "resolved",
        "RetestTruthLabel",
    }
    dumped = json.dumps(user_payload)
    for token in forbidden_keys:
        assert token not in dumped
    assert set(user_payload.keys()) <= {
        "comparison_id",
        "comparison_digest",
        "compact_findings",
        "eligible_options",
    }
    await service.aclose()


@pytest.mark.asyncio
async def test_fixed_arm_contrast_matches_catalog_not_sdk() -> None:
    record = await _comparison_record(same_input="unknown")
    ctx = build_retest_context(record)
    fixed = choose_fixed_retest(ctx)
    sdk = _FakeSDK()
    planner = _planner_with_sdk(sdk)
    sdk.completions.text = json.dumps(
        {
            "option_id": "opt_complete_conditions",
            "basis_refs": ["decl_same_input"],
            "abstain_reason_code": None,
        }
    )
    adapter = await planner.choose(ctx)
    await planner.aclose()
    assert fixed.option_id == adapter.option_id
    assert fixed.option_id == "opt_complete_conditions"
    assert len(sdk.completions.calls) == 1
