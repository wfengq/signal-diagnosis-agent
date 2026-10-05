"""Phase B Task 6: regression case reporting."""

from __future__ import annotations

import copy
import inspect
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import StructuredDiagnosis
from signal_diag.app.full_scale_wording import (
    CLIPPING_RATIO_NOTICE,
    FULL_SCALE_TEMPLATES,
)
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.regression import (
    CaseComparisonItem,
    ComparisonUpload,
    RegressionCaseSnapshot,
    RegressionWorkbenchService,
    RetestLink,
    submissions_from_items,
)
from signal_diag.app.regression_reporting import (
    RegressionCaseReport,
    build_case_report,
    render_case_html,
    render_case_json,
    validate_regression_case_report_integrity,
)
from signal_diag.rules.full_scale_check import (
    FullScaleDeclarations,
    FullScaleMethodFloor,
    evaluate_full_scale_check,
    resolve_anchor_id,
)
from signal_diag.rules.regression import (
    ComparisonConditions,
    validate_comparison_record,
)
from signal_diag.signal import generate_sine
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.regression_measurement import MeasurementSelection
from tests.app.test_regression_service import _upload
from tests.rules.full_scale_fixtures import FIXTURE_FLOOR, sine, wav16

NOW = datetime(2026, 10, 4, 15, 0, tzinfo=UTC)


def _mono_wav_bytes() -> bytes:
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.5,
        amplitude=0.4,
    )
    return encode_pcm32_wav(case.record.samples, sample_rate_hz=48_000)


@pytest.fixture
def service() -> RegressionWorkbenchService:
    return RegressionWorkbenchService(clock=lambda: NOW)


@pytest.mark.asyncio
async def test_build_case_report_validates_records(service: RegressionWorkbenchService) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal <script>")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    report = build_case_report(snapshot, generated_at=NOW)
    assert report.case_id == snapshot.case_id
    assert len(report.comparisons) == 1
    validate_comparison_record(report.comparisons[0].record)


@pytest.mark.asyncio
async def test_html_escapes_untrusted_text(service: RegressionWorkbenchService) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case('goal "<img onerror=alert(1)>"')
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    html = render_case_html(build_case_report(snapshot, generated_at=NOW))
    assert "<script>" not in html
    assert "&lt;img" in html or "onerror" not in html
    assert "Reporting measurement changes only" in html
    assert "overall pass" not in html.casefold()
    assert "pass-badge" not in html


@pytest.mark.asyncio
async def test_json_preserves_source_refs(service: RegressionWorkbenchService) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    payload = json.loads(
        render_case_json(build_case_report(snapshot, generated_at=NOW))
    )
    record = payload["comparisons"][0]["record"]
    clipping = record["metric_comparisons"][0]
    assert clipping["baseline_ref"]["evidence_id"].startswith("ev_")
    assert clipping["candidate_ref"]["evidence_id"].startswith("ev_")


@pytest.mark.asyncio
async def test_tampered_rule_ref_rejected(service: RegressionWorkbenchService) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    item = snapshot.comparisons[0]
    row = item.record.metric_comparisons[0]
    forged_row = row.model_copy(update={"rule_ref": "forged_rule"})
    forged_record = item.record.model_copy(
        update={
            "metric_comparisons": (
                forged_row,
                item.record.metric_comparisons[1],
            )
        }
    )
    broken = snapshot.model_copy(
        update={
            "comparisons": (
                item.model_copy(update={"record": forged_record}),
            )
        }
    )
    with pytest.raises(ValueError, match="mismatch"):
        build_case_report(broken, generated_at=NOW)


@pytest.mark.asyncio
async def test_cross_case_run_reference_rejected(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case_a = service.create_case("a")
    case_b = service.create_case("b")
    snap_a = await service.submit_comparison(
        case_a.case_id,
        _upload(wav, wav),
        request_id="req-a",
    )
    snap_b = await service.submit_comparison(
        case_b.case_id,
        _upload(wav, wav),
        request_id="req-b",
    )
    foreign_run = snap_b.comparisons[0].record.baseline_bundle.identity.run_id
    item = snap_a.comparisons[0]
    row = item.record.metric_comparisons[0]
    assert row.baseline_ref is not None
    forged_ref = row.baseline_ref.model_copy(update={"run_id": foreign_run})
    forged_row = row.model_copy(update={"baseline_ref": forged_ref})
    forged_record = item.record.model_copy(
        update={
            "metric_comparisons": (
                forged_row,
                item.record.metric_comparisons[1],
            )
        }
    )
    broken = snap_a.model_copy(
        update={
            "comparisons": (
                item.model_copy(update={"record": forged_record}),
            )
        }
    )
    with pytest.raises(ValueError, match="digest mismatch|run_id mismatch"):
        build_case_report(broken, generated_at=NOW)


@pytest.mark.asyncio
async def test_model_validate_rejects_tampered_difference_via_report(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    report = build_case_report(snapshot, generated_at=NOW)
    payload = json.loads(report.model_dump_json())
    payload["comparisons"][0]["record"]["metric_comparisons"][0]["difference"] = 999.0
    with pytest.raises(ValueError, match="mismatch"):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_model_validate_rejects_outer_comparison_id_mismatch(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    report = build_case_report(snapshot, generated_at=NOW)
    payload = json.loads(report.model_dump_json())
    payload["comparisons"][0]["comparison_id"] = "cmp_forged_outer"
    with pytest.raises(ValueError, match="comparison_id"):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_model_validate_rejects_forged_parent_comparison_id(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    report = build_case_report(snapshot, generated_at=NOW)
    payload = json.loads(report.model_dump_json())
    payload["comparisons"][0]["parent_comparison_id"] = "cmp_missing_parent"
    with pytest.raises(ValueError, match="parent"):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_transplant_foreign_comparison_with_cleared_recommendations_rejected(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case_a = service.create_case("a")
    case_b = service.create_case("b")
    snap_a = await service.submit_comparison(
        case_a.case_id,
        _upload(wav, wav),
        request_id="req-a",
    )
    snap_b = await service.submit_comparison(
        case_b.case_id,
        _upload(wav, wav),
        request_id="req-b",
    )
    foreign_item = snap_b.comparisons[0]
    broken = snap_a.model_copy(
        update={
            "comparisons": (foreign_item,),
            "recommendations": (),
        }
    )
    with pytest.raises(ValueError, match="case_id"):
        build_case_report(broken, generated_at=NOW)


@pytest.mark.asyncio
async def test_transplant_foreign_comparison_and_recommendations_rejected(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case_a = service.create_case("a")
    case_b = service.create_case("b")
    snap_a = await service.submit_comparison(
        case_a.case_id,
        _upload(wav, wav),
        request_id="req-a",
    )
    snap_b = await service.submit_comparison(
        case_b.case_id,
        _upload(wav, wav),
        request_id="req-b",
    )
    broken = snap_a.model_copy(
        update={
            "comparisons": (snap_b.comparisons[0],),
            "recommendations": snap_b.recommendations,
        }
    )
    with pytest.raises(ValueError, match="case_id"):
        build_case_report(broken, generated_at=NOW)


@pytest.mark.asyncio
async def test_transplant_foreign_comparison_with_stale_recommendations_rejected(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case_a = service.create_case("a")
    case_b = service.create_case("b")
    snap_a = await service.submit_comparison(
        case_a.case_id,
        _upload(wav, wav),
        request_id="req-a",
    )
    snap_b = await service.submit_comparison(
        case_b.case_id,
        _upload(wav, wav),
        request_id="req-b",
    )
    foreign_item = snap_b.comparisons[0]
    broken = snap_a.model_copy(
        update={
            "comparisons": (foreign_item,),
        }
    )
    with pytest.raises(ValueError, match="case_id|comparison_id"):
        build_case_report(broken, generated_at=NOW)


def test_model_validate_rejects_forged_comparison_record() -> None:
    wav = _mono_wav_bytes()
    service = RegressionWorkbenchService(clock=lambda: NOW)
    case = service.create_case("goal")
    import asyncio

    snapshot = asyncio.run(
        service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="req-1",
        )
    )
    report = build_case_report(snapshot, generated_at=NOW)
    payload = json.loads(report.model_dump_json())
    payload["comparisons"][0]["record"]["metric_comparisons"][0]["difference"] = 999.0
    with pytest.raises(ValueError, match="mismatch"):
        RegressionCaseReport.model_validate(payload)


def _fs_conditions() -> ComparisonConditions:
    return ComparisonConditions(
        baseline_version="v1",
        candidate_version="v2",
        stimulus_key="sine",
        parameters_key="default",
        same_input="yes",
        parameters_unchanged="yes",
        aligned_ranges="yes",
        repeatability="declared_deterministic",
        nominal_fundamental_hz=100.0,
    )


def _fs_selection() -> MeasurementSelection:
    return MeasurementSelection(
        clipping=ClippingInput(channel="left"),
        harmonic=HarmonicDistortionInput(channel="left", fundamental_hz=100.0),
    )


def _fs_upload(**overrides: object) -> ComparisonUpload:
    wav = wav16(sine(amplitude=0.5))
    return ComparisonUpload(
        baseline_data=overrides.get("baseline_data", wav),
        candidate_data=overrides.get("candidate_data", wav),
        baseline_filename="b.wav",
        candidate_filename="c.wav",
        baseline_version="v1",
        candidate_version="v2",
        conditions=overrides.get("conditions", _fs_conditions()),
        selection=overrides.get("selection", _fs_selection()),
        full_scale_declarations=overrides.get(
            "full_scale_declarations", FullScaleDeclarations()
        ),
    )


async def _snapshot_with_two_submits(
    service: RegressionWorkbenchService,
) -> RegressionCaseSnapshot:
    case = service.create_case("goal")
    snap = await service.submit_comparison(case.case_id, _fs_upload(), request_id="r1")
    link = RetestLink(kind="repeat", parent_comparison_id=snap.comparisons[0].comparison_id)
    indep = FullScaleDeclarations(
        baseline_independent_render="yes", candidate_independent_render="yes"
    )
    return await service.submit_comparison(
        case.case_id,
        _fs_upload(full_scale_declarations=indep),
        request_id="r2",
        link=link,
    )


async def _snapshot_with_unreferenced_repeat(
    service: RegressionWorkbenchService,
) -> RegressionCaseSnapshot:
    """Anchor + repeat without independent-render declarations (facts stored, not counted)."""
    case = service.create_case("unreferenced")
    snap = await service.submit_comparison(case.case_id, _fs_upload(), request_id="r1")
    link = RetestLink(kind="repeat", parent_comparison_id=snap.comparisons[0].comparison_id)
    return await service.submit_comparison(
        case.case_id, _fs_upload(), request_id="r2", link=link
    )


def _rebuild_checks(
    items: tuple[CaseComparisonItem, ...] | list[CaseComparisonItem],
    *,
    floor: FullScaleMethodFloor | None,
) -> tuple:
    index = submissions_from_items(items)
    checks = []
    for position, item in enumerate(items):
        anchor_id = resolve_anchor_id(item.comparison_id, index)
        repeats = tuple(
            index[row.comparison_id]
            for row in items[: position + 1]
            if row.link_kind == "repeat"
            and resolve_anchor_id(row.comparison_id, index) == anchor_id
        )
        prior = [check for check in checks if check.anchor_comparison_id == anchor_id]
        checks.append(
            evaluate_full_scale_check(
                check_id=f"chk_{position}",
                anchor=index[anchor_id],
                repeats=repeats,
                floor=floor,
                supersedes=prior[-1].check_id if prior else None,
            )
        )
    return tuple(checks)


@pytest.mark.asyncio
async def test_t_cx367_report_carries_and_validates_checks(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    report = build_case_report(snapshot, generated_at=NOW)
    assert report.full_scale_checks == snapshot.full_scale_checks
    parsed = RegressionCaseReport.model_validate_json(render_case_json(report))
    assert parsed.full_scale_checks == report.full_scale_checks
    payload = json.loads(render_case_json(report))
    payload["full_scale_checks"][1]["status"] = "regression_detected"
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_t_cx367_report_rejects_dropped_repeat_and_fabricated_floor(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    payload = json.loads(
        render_case_json(build_case_report(snapshot, generated_at=NOW))
    )
    dropped = copy.deepcopy(payload)
    dropped["full_scale_checks"][1]["repeat_comparison_ids"] = []
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(dropped)
    forged = copy.deepcopy(payload)
    forged["full_scale_checks"][1]["floor"] = FIXTURE_FLOOR.model_dump(mode="json")
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(forged)


@pytest.mark.asyncio
async def test_t_cx355_html_shows_current_and_superseded_checks(service) -> None:
    html = render_case_html(
        build_case_report(await _snapshot_with_two_submits(service), generated_at=NOW)
    )
    assert "Full-scale check" in html and "Superseded" in html
    assert FULL_SCALE_TEMPLATES["notice.coverage"] in html and CLIPPING_RATIO_NOTICE in html
    assert "overall" not in html.casefold()
    assert "descriptive_only" in html


def test_t_cx368_check_stays_out_of_diagnosis() -> None:
    from signal_diag.agent import diagnosis

    assert "full_scale" not in inspect.getsource(diagnosis)
    assert "FullScale" not in json.dumps(StructuredDiagnosis.model_json_schema())


@pytest.mark.asyncio
async def test_9b2_rejects_dropped_anchor_candidate_facts(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    payload = json.loads(
        render_case_json(build_case_report(snapshot, generated_at=NOW))
    )
    payload["comparisons"][0]["candidate_full_scale"] = None
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_9b1_report_rejects_swapped_facts_on_unreferenced_repeat(service) -> None:
    snapshot = await _snapshot_with_unreferenced_repeat(service)
    items = list(snapshot.comparisons)
    repeat = items[1]
    assert repeat.full_scale_declarations.baseline_independent_render == "unknown"
    items[1] = repeat.model_copy(
        update={
            "baseline_full_scale": repeat.candidate_full_scale,
            "candidate_full_scale": repeat.baseline_full_scale,
        }
    )
    checks = _rebuild_checks(items, floor=None)
    with pytest.raises(ValueError, match="side"):
        validate_regression_case_report_integrity(
            case_id=snapshot.case_id,
            comparisons=tuple(items),
            failures=snapshot.failures,
            recommendations=snapshot.recommendations,
            full_scale_checks=checks,
        )


@pytest.mark.asyncio
async def test_9b2_rejects_dropped_anchor_facts_after_recompute(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    items = list(snapshot.comparisons)
    items[0] = items[0].model_copy(update={"candidate_full_scale": None})
    checks = _rebuild_checks(items, floor=None)
    with pytest.raises(ValueError, match="presence"):
        validate_regression_case_report_integrity(
            case_id=snapshot.case_id,
            comparisons=tuple(items),
            failures=snapshot.failures,
            recommendations=snapshot.recommendations,
            full_scale_checks=checks,
        )


@pytest.mark.asyncio
async def test_9b2_rejects_dropped_facts_on_unreferenced_repeat(service) -> None:
    snapshot = await _snapshot_with_unreferenced_repeat(service)
    items = list(snapshot.comparisons)
    items[1] = items[1].model_copy(update={"candidate_full_scale": None})
    checks = _rebuild_checks(items, floor=None)
    with pytest.raises(ValueError, match="presence"):
        validate_regression_case_report_integrity(
            case_id=snapshot.case_id,
            comparisons=tuple(items),
            failures=snapshot.failures,
            recommendations=snapshot.recommendations,
            full_scale_checks=checks,
        )


@pytest.mark.asyncio
async def test_9b7_report_layer_requires_applicable_floor(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    with_floor = _rebuild_checks(snapshot.comparisons, floor=FIXTURE_FLOOR)
    validate_regression_case_report_integrity(
        case_id=snapshot.case_id,
        comparisons=snapshot.comparisons,
        failures=snapshot.failures,
        recommendations=snapshot.recommendations,
        full_scale_checks=with_floor,
        approved_floors=(FIXTURE_FLOOR,),
    )
    dropped = _rebuild_checks(snapshot.comparisons, floor=None)
    with pytest.raises(ValueError, match="floor"):
        validate_regression_case_report_integrity(
            case_id=snapshot.case_id,
            comparisons=snapshot.comparisons,
            failures=snapshot.failures,
            recommendations=snapshot.recommendations,
            full_scale_checks=dropped,
            approved_floors=(FIXTURE_FLOOR,),
        )


@pytest.mark.asyncio
async def test_9b4_rejects_empty_checks_when_facts_present(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    payload = json.loads(
        render_case_json(build_case_report(snapshot, generated_at=NOW))
    )
    payload["full_scale_checks"] = []
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_9b4_rejects_missing_checks_for_one_anchor(service) -> None:
    case = service.create_case("two-anchors")
    first = await service.submit_comparison(
        case.case_id, _fs_upload(), request_id="a1"
    )
    second = await service.submit_comparison(
        case.case_id, _fs_upload(), request_id="a2"
    )
    report = build_case_report(second, generated_at=NOW)
    payload = json.loads(render_case_json(report))
    payload["full_scale_checks"] = [
        check
        for check in payload["full_scale_checks"]
        if check["anchor_comparison_id"] == first.comparisons[0].comparison_id
    ]
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_9b5_rejects_repeat_used_as_anchor(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    payload = json.loads(
        render_case_json(build_case_report(snapshot, generated_at=NOW))
    )
    repeat_id = payload["comparisons"][1]["comparison_id"]
    forged = copy.deepcopy(payload["full_scale_checks"][-1])
    forged["anchor_comparison_id"] = repeat_id
    forged["check_id"] = "forged_repeat_anchor"
    forged["supersedes"] = None
    forged["repeat_comparison_ids"] = []
    from signal_diag.rules.full_scale_check import (
        FullScaleCheckRecord,
        _check_record_digest,
    )

    model = FullScaleCheckRecord.model_validate(forged)
    forged["digest"] = _check_record_digest(model)
    payload["full_scale_checks"].append(forged)
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_9b6_rejects_duplicate_check_ids(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    payload = json.loads(
        render_case_json(build_case_report(snapshot, generated_at=NOW))
    )
    payload["full_scale_checks"][1]["check_id"] = payload["full_scale_checks"][0][
        "check_id"
    ]
    from signal_diag.rules.full_scale_check import (
        FullScaleCheckRecord,
        _check_record_digest,
    )

    model = FullScaleCheckRecord.model_validate(payload["full_scale_checks"][1])
    payload["full_scale_checks"][1]["digest"] = _check_record_digest(model)
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)


@pytest.mark.asyncio
async def test_9b8_declaration_mismatch_without_recompute_fails(service) -> None:
    snapshot = await _snapshot_with_two_submits(service)
    payload = json.loads(
        render_case_json(build_case_report(snapshot, generated_at=NOW))
    )
    payload["comparisons"][1]["full_scale_declarations"][
        "baseline_independent_render"
    ] = "no"
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)
