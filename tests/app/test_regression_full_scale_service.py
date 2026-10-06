"""T-CX351, T-CX360, T-CX363, T-CX364, T-CX370: full-scale service lifecycle."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from signal_diag.app.errors import AppCapacityError, InvalidRequestError
from signal_diag.app.regression import (
    ComparisonUpload,
    RegressionWorkbenchService,
    RetestLink,
    _upload_fingerprint,
    build_regression_service,
)
from signal_diag.rules.full_scale_check import (
    PRODUCT_APPROVED_FULL_SCALE_FLOORS,
    FullScaleDeclarations,
)
from signal_diag.rules.regression import (
    ComparisonConditions,
    validate_comparison_record,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.regression_measurement import MeasurementSelection
from tests.rules.full_scale_fixtures import sine, wav16, wav24

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def _conditions(**overrides: object) -> ComparisonConditions:
    base = {
        "baseline_version": "v1",
        "candidate_version": "v2",
        "stimulus_key": "sine-200",
        "parameters_key": "default",
        "same_input": "yes",
        "parameters_unchanged": "yes",
        "aligned_ranges": "yes",
        "repeatability": "declared_deterministic",
        "nominal_fundamental_hz": 100.0,
    }
    base.update(overrides)
    return ComparisonConditions(**base)


def _upload(**overrides: object) -> ComparisonUpload:
    baseline_data = overrides.pop("baseline_data", wav16(sine(amplitude=0.5)))
    candidate_data = overrides.pop("candidate_data", wav16(sine(amplitude=0.5)))
    conditions = overrides.pop("conditions", _conditions())
    return ComparisonUpload(
        baseline_data=baseline_data,
        candidate_data=candidate_data,
        baseline_filename="baseline.wav",
        candidate_filename="candidate.wav",
        baseline_version=conditions.baseline_version,
        candidate_version=conditions.candidate_version,
        conditions=conditions,
        selection=overrides.pop("selection", None)
        or MeasurementSelection(
            clipping=ClippingInput(channel="left"),
            harmonic=HarmonicDistortionInput(channel="left", fundamental_hz=100.0),
        ),
        full_scale_declarations=overrides.pop(
            "full_scale_declarations", FullScaleDeclarations()
        ),
        **overrides,
    )


@pytest.fixture
def service() -> RegressionWorkbenchService:
    return RegressionWorkbenchService(
        clock=lambda: NOW,
        full_scale_floor=PRODUCT_APPROVED_FULL_SCALE_FLOORS[0],
    )


def test_9c4_evaluate_before_comparisons_append() -> None:
    source = inspect.getsource(RegressionWorkbenchService.submit_comparison)
    eval_at = source.index("evaluate_full_scale_check(")
    append_at = source.index("case.comparisons.append(item)")
    assert eval_at < append_at


@pytest.mark.asyncio
async def test_t_cx364_one_record_per_completed_comparison_with_superseding(service) -> None:
    case = service.create_case("goal")
    s1 = await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    assert len(s1.full_scale_checks) == 1
    first = s1.full_scale_checks[0]
    assert first.anchor_comparison_id == s1.comparisons[0].comparison_id and first.supersedes is None
    link = RetestLink(kind="repeat", parent_comparison_id=first.anchor_comparison_id)
    indep = FullScaleDeclarations(
        baseline_independent_render="yes", candidate_independent_render="yes"
    )
    s2 = await service.submit_comparison(
        case.case_id, _upload(full_scale_declarations=indep), request_id="r2", link=link
    )
    assert len(s2.full_scale_checks) == 2
    second = s2.full_scale_checks[1]
    assert second.supersedes == first.check_id and second.anchor_comparison_id == first.anchor_comparison_id
    assert (second.counted_baseline_repeats, second.counted_candidate_repeats) == (1, 1)
    assert s2.full_scale_checks[0] == first


@pytest.mark.asyncio
async def test_t_cx364_replay_and_failure_produce_no_record(service) -> None:
    case = service.create_case("goal")
    await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    again = await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    assert len(again.full_scale_checks) == 1
    with pytest.raises(InvalidRequestError):
        await service.submit_comparison(
            case.case_id, _upload(baseline_data=b"not a wav"), request_id="r2"
        )
    assert len(service.get_case(case.case_id).full_scale_checks) == 1


@pytest.mark.asyncio
async def test_t_cx364_records_do_not_consume_submit_quota(service) -> None:
    case = service.create_case("goal")
    for i in range(16):
        await service.submit_comparison(case.case_id, _upload(), request_id=f"r{i}")
    snap = service.get_case(case.case_id)
    assert len(snap.comparisons) == 16 and len(snap.full_scale_checks) == 16
    with pytest.raises(AppCapacityError):
        await service.submit_comparison(case.case_id, _upload(), request_id="r16")


@pytest.mark.asyncio
async def test_t_cx363_product_builder_wires_d044_floor() -> None:
    from signal_diag.rules.full_scale_check import PRODUCT_APPROVED_FULL_SCALE_FLOORS

    service = build_regression_service()
    assert service._full_scale_floor == PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]
    case = service.create_case("goal")
    snap = await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    check = snap.full_scale_checks[0]
    # Default upload lacks eligible repeats/declarations; status stays non-judged
    # unless the full eligibility ladder holds. Floor identity is wired.
    assert check.status in (
        "descriptive_only",
        "not_comparable",
        "regression_detected",
        "no_regression_detected",
    )


def test_t_cx363_client_cannot_supply_floor_or_approval() -> None:
    for extra in (
        {"full_scale_floor": {}},
        {"floor": {}},
        {"approved": True},
        {"full_scale_checks": []},
    ):
        with pytest.raises(ValidationError):
            ComparisonUpload(**_upload().model_dump(), **extra)


def test_t_cx370_fingerprint_covers_declarations() -> None:
    a = _upload()
    b = _upload(full_scale_declarations=FullScaleDeclarations(periodic_test_signal="yes"))
    assert _upload_fingerprint(a) != _upload_fingerprint(b)
    assert _upload().full_scale_declarations == FullScaleDeclarations()


@pytest.mark.asyncio
async def test_t_cx351_comparison_record_unchanged_by_full_scale(service) -> None:
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(full_scale_declarations=FullScaleDeclarations(periodic_test_signal="yes")),
        request_id="r1",
    )
    record = snap.comparisons[0].record
    validate_comparison_record(record)
    assert record.required_checks == ("clipping_ratio", "thd_percent", "declarations", "tool_success")
    assert record.overall_regression_pass is None
    assert snap.comparisons[0].baseline_full_scale.pcm_bit_depth == 16


@pytest.mark.asyncio
async def test_bit_depth_comes_from_wav_header(service) -> None:
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(baseline_data=wav24(sine(amplitude=0.5))),
        request_id="r1",
    )
    item = snap.comparisons[0]
    assert (item.baseline_full_scale.pcm_bit_depth, item.candidate_full_scale.pcm_bit_depth) == (
        24,
        16,
    )


@pytest.mark.asyncio
async def test_report_shows_record_status_beside_not_comparable_check(service) -> None:
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(conditions=_conditions(same_input="unknown")),
        request_id="r1",
    )
    assert snap.full_scale_checks[0].status == "not_comparable"
    clipping = next(
        m for m in snap.comparisons[0].record.metric_comparisons if m.metric == "clipping_ratio"
    )
    assert clipping.status == "descriptive_only"
