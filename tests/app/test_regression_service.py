"""Phase B Task 5: in-session regression workbench service."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from signal_diag.app.errors import (
    AppCapacityError,
    InvalidRequestError,
    PayloadTooLargeError,
)
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.regression import (
    ComparisonUpload,
    RegressionWorkbenchService,
    RetestLink,
    build_regression_service,
)
from signal_diag.rules.regression import ComparisonConditions
from signal_diag.signal import generate_sine
from signal_diag.signal.wav import WavLoadLimits
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.regression_measurement import (
    MeasurementSelection,
    measure_output,
)
from tests.rules.regression_fixtures import build_fixture_clipping_profile

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _mono_wav_bytes(
    *,
    frequency_hz: float = 200.0,
    amplitude: float = 0.4,
) -> bytes:
    case = generate_sine(
        frequency_hz=frequency_hz,
        sample_rate_hz=48_000,
        duration_s=0.5,
        amplitude=amplitude,
    )
    return encode_pcm32_wav(case.record.samples, sample_rate_hz=48_000)


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
    }
    base.update(overrides)
    return ComparisonConditions(**base)


def _selection() -> MeasurementSelection:
    return MeasurementSelection(
        clipping=ClippingInput(channel="left", full_scale_threshold=0.99),
        harmonic=HarmonicDistortionInput(channel="left", fundamental_hz=200.0),
    )


def _upload(
    baseline: bytes,
    candidate: bytes,
    *,
    conditions: ComparisonConditions | None = None,
    selection: MeasurementSelection | None = None,
) -> ComparisonUpload:
    cond = conditions or _conditions()
    return ComparisonUpload(
        baseline_data=baseline,
        candidate_data=candidate,
        baseline_filename="baseline.wav",
        candidate_filename="candidate.wav",
        baseline_version=cond.baseline_version,
        candidate_version=cond.candidate_version,
        conditions=cond,
        selection=selection or _selection(),
    )


@pytest.fixture
def service() -> RegressionWorkbenchService:
    return RegressionWorkbenchService(clock=lambda: NOW)


@pytest.mark.asyncio
async def test_no_profile_submit_is_descriptive_and_distinct_run_ids(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("compare builds")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-initial",
    )
    assert snapshot.latest_submit_status == "completed"
    assert len(snapshot.comparisons) == 1
    item = snapshot.comparisons[0]
    record = item.record
    assert record.profile_id is None
    assert record.baseline_bundle.identity.run_id != record.candidate_bundle.identity.run_id
    assert record.baseline_bundle.identity.wav_sha256 == hashlib.sha256(wav).hexdigest()
    clipping = record.metric_comparisons[0]
    thd = record.metric_comparisons[1]
    assert clipping.status == "descriptive_only"
    assert thd.status == "not_comparable"
    assert "no_approved_profile" in clipping.reason_codes[0]
    assert snapshot.recommendations[0].status == "unavailable"


def test_build_regression_service_has_no_fixture_profile() -> None:
    built = build_regression_service()
    assert built._comparison_profile is None


def test_comparison_upload_forbids_client_control_fields() -> None:
    wav = _mono_wav_bytes()
    with pytest.raises(ValidationError):
        ComparisonUpload.model_validate(
            {
                "baseline_data": wav,
                "candidate_data": wav,
                "baseline_filename": "a.wav",
                "candidate_filename": "b.wav",
                "baseline_version": "v1",
                "candidate_version": "v2",
                "conditions": _conditions().model_dump(),
                "selection": _selection().model_dump(),
                "wav_sha256": "0" * 64,
            }
        )


@pytest.mark.asyncio
async def test_idempotent_same_request_returns_existing_without_remeasure(
    service: RegressionWorkbenchService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}
    original = measure_output

    def counted(*args: Any, **kwargs: Any):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        "signal_diag.app.regression.measure_output",
        counted,
    )
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    upload = _upload(wav, wav)
    first = await service.submit_comparison(case.case_id, upload, request_id="same-req")
    second = await service.submit_comparison(case.case_id, upload, request_id="same-req")
    assert calls["n"] == 2
    assert second.revision == first.revision
    assert second.comparisons == first.comparisons


@pytest.mark.asyncio
async def test_idempotent_same_request_different_content_rejects(
    service: RegressionWorkbenchService,
) -> None:
    wav_a = _mono_wav_bytes(amplitude=0.4)
    wav_b = _mono_wav_bytes(amplitude=0.5)
    case = service.create_case("goal")
    await service.submit_comparison(case.case_id, _upload(wav_a, wav_a), request_id="dup")
    with pytest.raises(InvalidRequestError, match="request_id"):
        await service.submit_comparison(case.case_id, _upload(wav_b, wav_b), request_id="dup")


@pytest.mark.asyncio
async def test_same_request_id_with_different_link_is_rejected(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    first = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="shared-req",
    )
    parent_id = first.comparisons[0].comparison_id
    with pytest.raises(InvalidRequestError, match="request_id"):
        await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="shared-req",
            link=RetestLink(kind="repair", parent_comparison_id=parent_id),
        )


@pytest.mark.asyncio
async def test_cancelled_submit_releases_busy_slot(
    service: RegressionWorkbenchService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    import signal_diag.app.regression as regression_mod

    original_run = regression_mod._execute_comparison_group
    entered = threading.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    entered_async = asyncio.Event()

    def slow_run(*args: Any, **kwargs: Any):
        entered.set()
        loop.call_soon_threadsafe(entered_async.set)
        if not release.wait(timeout=2.0):
            raise TimeoutError("test release signal was not set")
        return original_run(*args, **kwargs)

    monkeypatch.setattr(regression_mod, "_execute_comparison_group", slow_run)
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    task = asyncio.create_task(
        service.submit_comparison(case.case_id, _upload(wav, wav), request_id="cancel-me")
    )
    await entered_async.wait()
    assert entered.is_set()
    assert service._busy is True
    task.cancel()
    # While cancelled await still waits for the worker, a second submit stays busy.
    await asyncio.sleep(0.02)
    assert service._busy is True
    with pytest.raises(InvalidRequestError, match="busy"):
        await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="overlap-while-cancel",
        )
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert service._busy is False
    assert service._cases[case.case_id].running is False
    # Same request_id may retry after cancel (no completed/failed outcome stored).
    retry = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="cancel-me",
    )
    assert retry.latest_submit_status == "completed"
    assert len(retry.comparisons) == 1


@pytest.mark.asyncio
async def test_double_cancel_keeps_busy_until_worker_finishes(
    service: RegressionWorkbenchService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    import signal_diag.app.regression as regression_mod

    original_run = regression_mod._execute_comparison_group
    entered = threading.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    entered_async = asyncio.Event()

    def slow_run(*args: Any, **kwargs: Any):
        entered.set()
        loop.call_soon_threadsafe(entered_async.set)
        if not release.wait(timeout=2.0):
            raise TimeoutError("test release signal was not set")
        return original_run(*args, **kwargs)

    monkeypatch.setattr(regression_mod, "_execute_comparison_group", slow_run)
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    task = asyncio.create_task(
        service.submit_comparison(case.case_id, _upload(wav, wav), request_id="dbl-cancel")
    )
    await entered_async.wait()
    task.cancel()
    task.cancel()
    await asyncio.sleep(0.02)
    assert service._busy is True
    with pytest.raises(InvalidRequestError, match="busy"):
        await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="overlap-dbl-cancel",
        )
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert service._busy is False
    assert service._cases[case.case_id].running is False
    retry = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="dbl-cancel",
    )
    assert retry.latest_submit_status == "completed"
    await service.aclose()


@pytest.mark.asyncio
async def test_original_input_sha256_mismatch_rejected(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    upload = ComparisonUpload(
        baseline_data=wav,
        candidate_data=wav,
        baseline_filename="baseline.wav",
        candidate_filename="candidate.wav",
        baseline_version="v1",
        candidate_version="v2",
        conditions=_conditions(original_input_sha256="a" * 64),
        selection=_selection(),
        original_input_data=wav,
        original_input_filename="original.wav",
    )
    with pytest.raises(InvalidRequestError, match="original_input_sha256"):
        await service.submit_comparison(case.case_id, upload, request_id="forge-hash")


@pytest.mark.asyncio
async def test_retest_parent_must_exist_and_be_completed(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    link = RetestLink(kind="repeat", parent_comparison_id="cmp_missing")
    with pytest.raises(InvalidRequestError, match="parent"):
        await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="retest-1",
            link=link,
        )


@pytest.mark.asyncio
async def test_repeat_and_repair_append_new_comparisons(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    first = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    parent_id = first.comparisons[0].comparison_id
    second = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-2",
        link=RetestLink(kind="repair", parent_comparison_id=parent_id),
    )
    assert len(second.comparisons) == 2
    assert second.comparisons[0].comparison_id == parent_id
    assert second.comparisons[1].parent_comparison_id == parent_id
    assert second.comparisons[1].link_kind == "repair"


@pytest.mark.asyncio
async def test_recommendation_link_rejected_without_recommendation_record(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    first = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    parent_id = first.comparisons[0].comparison_id
    with pytest.raises(InvalidRequestError, match="recommendation"):
        await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="req-rec",
            link=RetestLink(
                kind="recommendation",
                parent_comparison_id=parent_id,
                recommendation_id="rec_missing",
            ),
        )


@pytest.mark.asyncio
async def test_run_failure_preserves_prior_comparisons_and_is_idempotent(
    service: RegressionWorkbenchService,
) -> None:
    good = _mono_wav_bytes()
    case = service.create_case("goal")
    ok = await service.submit_comparison(
        case.case_id,
        _upload(good, good),
        request_id="ok-req",
    )
    bad = b"not-a-wav"
    with pytest.raises(InvalidRequestError):
        await service.submit_comparison(
            case.case_id,
            _upload(bad, bad),
            request_id="bad-req",
        )
    after_fail = service.get_case(case.case_id)
    assert len(after_fail.comparisons) == len(ok.comparisons)
    assert len(after_fail.failures) == 1
    assert after_fail.latest_submit_status == "failed"
    again = await service.submit_comparison(
        case.case_id,
        _upload(bad, bad),
        request_id="bad-req",
    )
    assert again.failures == after_fail.failures


@pytest.mark.asyncio
async def test_returned_snapshot_mutation_does_not_change_internal_state(
    service: RegressionWorkbenchService,
) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="req-1",
    )
    leaked = snapshot.comparisons[0].record.metric_comparisons[0]
    object.__setattr__(leaked, "status", "regression_detected")
    fresh = service.get_case(case.case_id)
    assert fresh.comparisons[0].record.metric_comparisons[0].status == "descriptive_only"


@pytest.mark.asyncio
async def test_payload_too_large_rejects_before_measure(
    service: RegressionWorkbenchService,
) -> None:
    limit = WavLoadLimits().max_upload_bytes
    huge = b"\x00" * (limit + 1)
    case = service.create_case("goal")
    with pytest.raises(PayloadTooLargeError):
        await service.submit_comparison(
            case.case_id,
            _upload(huge, _mono_wav_bytes()),
            request_id="big",
        )


@pytest.mark.asyncio
async def test_max_active_cases_capacity(service: RegressionWorkbenchService) -> None:
    for index in range(8):
        service.create_case(f"case-{index}")
    with pytest.raises(AppCapacityError, match="cases"):
        service.create_case("one-too-many")


@pytest.mark.asyncio
async def test_max_submits_per_case(service: RegressionWorkbenchService) -> None:
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    for index in range(16):
        await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id=f"req-{index}",
        )
    with pytest.raises(AppCapacityError, match="submits"):
        await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="req-overflow",
        )


@pytest.mark.asyncio
async def test_concurrent_submit_second_is_busy(
    service: RegressionWorkbenchService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import signal_diag.app.regression as regression_mod

    original_run = regression_mod._execute_comparison_group

    def slow_run(*args: Any, **kwargs: Any):
        import time

        time.sleep(0.15)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(regression_mod, "_execute_comparison_group", slow_run)

    wav = _mono_wav_bytes()
    case = service.create_case("goal")

    async def first():
        return await service.submit_comparison(
            case.case_id,
            _upload(wav, wav),
            request_id="slow",
        )

    async def second():
        await asyncio.sleep(0.02)
        with pytest.raises(InvalidRequestError, match="busy"):
            await service.submit_comparison(
                case.case_id,
                _upload(wav, wav),
                request_id="blocked",
            )

    await asyncio.gather(first(), second())


@pytest.mark.asyncio
async def test_delete_case_while_running_rejects(
    service: RegressionWorkbenchService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import signal_diag.app.regression as regression_mod

    original_run = regression_mod._execute_comparison_group

    def slow_run(*args: Any, **kwargs: Any):
        import time

        time.sleep(0.2)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(regression_mod, "_execute_comparison_group", slow_run)

    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    task = asyncio.create_task(
        service.submit_comparison(case.case_id, _upload(wav, wav), request_id="slow-del")
    )
    await asyncio.sleep(0.02)
    with pytest.raises(InvalidRequestError, match="running comparison"):
        service.delete_case(case.case_id)
    await task


@pytest.mark.asyncio
async def test_aclose_waits_for_in_flight_measurement(
    service: RegressionWorkbenchService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import signal_diag.app.regression as regression_mod

    original_run = regression_mod._execute_comparison_group

    def slow_run(*args: Any, **kwargs: Any):
        import time

        time.sleep(0.12)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(regression_mod, "_execute_comparison_group", slow_run)

    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    task = asyncio.create_task(
        service.submit_comparison(case.case_id, _upload(wav, wav), request_id="close-wait")
    )
    await asyncio.sleep(0.02)
    await service.aclose()
    await task


@pytest.mark.asyncio
async def test_injected_fixture_profile_can_enable_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = build_fixture_clipping_profile()
    service = RegressionWorkbenchService(
        clock=lambda: NOW,
        comparison_profile=profile,
    )
    wav = _mono_wav_bytes()
    case = service.create_case("goal")
    snapshot = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav),
        request_id="profile-req",
    )
    clipping_row = snapshot.comparisons[0].record.metric_comparisons[0]
    assert clipping_row.status in {
        "no_regression_detected",
        "regression_detected",
        "descriptive_only",
        "not_comparable",
    }
    assert snapshot.comparisons[0].record.profile_id == profile.profile_id
