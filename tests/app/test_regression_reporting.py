"""Phase B Task 6: regression case reporting."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.regression import RegressionWorkbenchService
from signal_diag.app.regression_reporting import (
    build_case_report,
    render_case_html,
    render_case_json,
)
from signal_diag.rules.regression import (
    validate_comparison_record,
)
from signal_diag.signal import generate_sine
from tests.app.test_regression_service import _upload

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
    with pytest.raises(ValueError, match="outside this case"):
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
    record = snapshot.comparisons[0].record
    payload = json.loads(record.model_dump_json())
    payload["metric_comparisons"][0]["difference"] = 999.0
    from signal_diag.rules.regression import ComparisonRecord

    tampered = ComparisonRecord.model_validate(payload)
    with pytest.raises(ValueError, match="mismatch"):
        validate_comparison_record(tampered)
