"""T-CX438–T-CX439: fault localization in contextual runs, reports and CLI (D050)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.app import service as service_module
from signal_diag.app.cli import main
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    dump_contextual_snapshot,
    render_contextual_report_html,
    render_contextual_report_json,
)
from signal_diag.app.models import PlannerIdentity
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from tests.app.test_api import CORPUS_PATH, PROFILE_PATH, _ImmediateFinishPlanner

QUESTION = "Why does this signal sound distorted?"


def _service() -> DiagnosisApplicationService:
    return DiagnosisApplicationService(
        ApplicationDependencies(
            repository=InMemorySignalRepository(),
            planner_factory=lambda: _ImmediateFinishPlanner(),
            planner_identity=PlannerIdentity(
                provider="deepseek",
                model="deepseek-v4-flash",
                prompt_version="v0.3-s1-planner-9.11",
                phase4_certified_default=False,
            ),
            planner_configured=True,
            rule_engine=RuleEngine(),
            rule_profile_loader=YamlRuleProfileLoader({"profile_s1_distortion": PROFILE_PATH}),
            knowledge_index=KnowledgeIndex(CORPUS_PATH),
            causal_policy_version="v9_11_mode_aware_no_fault_recovery",
        )
    )


def _clipped_wav() -> bytes:
    """2 s at 8 kHz: clean tone, then hard clipping from 1.0 s to 1.5 s."""
    rate = 8_000
    t = np.arange(2 * rate) / rate
    samples = 0.3 * np.sin(2 * np.pi * 440.0 * t)
    burst = np.clip(0.9 * np.sin(2 * np.pi * 440.0 * t), -0.4, 0.4)
    samples[rate : rate + rate // 2] = burst[rate : rate + rate // 2]
    return encode_pcm32_wav(samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=rate)


async def _run(service: DiagnosisApplicationService) -> Any:
    submission = await service.submit_contextual_wav(
        _clipped_wav(),
        test_filename="burst.wav",
        mode="single_signal",
        reference_data=None,
        reference_filename=None,
        nominal_fundamental_hz=None,
        stimulus_kind=None,
        user_request=QUESTION,
    )
    return await service.wait_for_contextual_terminal(submission.run_id)


@pytest.mark.asyncio
async def test_t_cx438_scan_runs_after_the_diagnosis_and_leaves_it_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    real = service_module.localize_faults

    def spy(record: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real(record, **kwargs)

    monkeypatch.setattr(service_module, "localize_faults", spy)
    service = _service()
    snapshot = await _run(service)
    await service.aclose()
    assert snapshot.status == "completed"
    assert len(calls) == 1
    assert calls[0]["mode"] == "single_signal"
    assert calls[0]["diagnosed_faults"] == frozenset()  # scripted finish is inconclusive
    localization = snapshot.fault_localization
    assert localization is not None
    result = snapshot.result
    assert result is not None
    agent_evidence = {item.evidence_id for item in result.evidence}
    assert not agent_evidence & {item.evidence_id for item in localization.evidence}
    assert result.diagnosis is not None and result.diagnosis.outcome == "inconclusive"
    assert result.diagnosis.claims == ()

    monkeypatch.setattr(service_module, "localize_faults", lambda record, **kwargs: None)
    baseline_service = _service()
    baseline = await _run(baseline_service)
    await baseline_service.aclose()
    assert baseline.fault_localization is None
    assert baseline.result is not None
    unchanged = ("run_id",)
    assert baseline.result.diagnosis is not None
    assert baseline.result.diagnosis.model_dump(exclude=set(unchanged)) == (
        result.diagnosis.model_dump(exclude=set(unchanged))
    )
    assert [item.source_tool for item in baseline.result.evidence] == [
        item.source_tool for item in result.evidence
    ]


@pytest.mark.asyncio
async def test_t_cx439_reports_show_the_locations() -> None:
    service = _service()
    snapshot = await _run(service)
    localization = snapshot.fault_localization
    assert localization is not None
    clipping = [i for i in localization.intervals if i.fault == "clipping"]
    assert len(clipping) == 1
    assert clipping[0].agrees_with_diagnosis is False
    assert 0.8 <= clipping[0].start_s <= 1.0 and 1.5 <= clipping[0].end_s <= 1.7

    dumped = dump_contextual_snapshot(snapshot)
    assert dumped["fault_localization"]["scan_version"] == "product-segment-scan-1.1"
    report = build_contextual_diagnosis_report(
        snapshot, generated_at=snapshot.finished_at  # type: ignore[arg-type]
    )
    payload = json.loads(render_contextual_report_json(report))
    assert payload["fault_localization"]["intervals"][0]["fault"] == "clipping"
    html = render_contextual_report_html(report)
    assert 'id="fault-localization"' in html
    assert "review needed" in html

    unset = snapshot.model_copy(update={"fault_localization": None})
    assert "fault_localization" not in dump_contextual_snapshot(unset)
    unset_report = build_contextual_diagnosis_report(
        unset, generated_at=snapshot.finished_at  # type: ignore[arg-type]
    )
    assert "fault_localization" not in json.loads(render_contextual_report_json(unset_report))
    assert 'id="fault-localization"' not in render_contextual_report_html(unset_report)
    await service.aclose()


def test_t_cx439_cli_prints_the_locations(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    wav = tmp_path / "burst.wav"
    wav.write_bytes(_clipped_wav())
    code = main(
        ["diagnose", "contextual", str(wav), "--mode", "single_signal"],
        service_factory=_service,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "fault_localization: product-segment-scan-1.1" in out
    assert "clipping mixdown" in out and "(review needed)" in out


def test_t_cx439_page_renders_the_panel() -> None:
    static = Path(__file__).resolve().parents[2] / "src/signal_diag/app/static"
    html = (static / "index.html").read_text(encoding="utf-8")
    script = (static / "app.js").read_text(encoding="utf-8")
    assert 'id="localization-panel"' in html
    assert html.index('id="summary-card"') < html.index('id="localization-panel"')
    assert "function renderLocalization" in script
    assert "fault_localization" in script
    assert "需要复核" in script
    assert 'id="localization-scope"' in html
    assert "localization.harmonic_basis" in script
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert sink not in script


def _paired_wavs() -> tuple[bytes, bytes]:
    rate = 8_000
    t = np.arange(2 * rate) / rate
    reference = 0.4 * np.sin(2 * np.pi * 220.0 * t) + 0.1 * np.sin(2 * np.pi * 440.0 * t)
    test = reference.copy()
    span = slice(rate, rate + rate // 2)
    burst = test[span]
    test[span] = burst + 0.6 * burst**2 / np.max(np.abs(burst))

    def encode(samples: np.ndarray) -> bytes:
        return encode_pcm32_wav(samples.astype(np.float32).reshape(-1, 1), sample_rate_hz=rate)

    return encode(test), encode(reference)


async def _run_paired(service: DiagnosisApplicationService) -> Any:
    test, reference = _paired_wavs()
    submission = await service.submit_contextual_wav(
        test,
        test_filename="burst.wav",
        mode="paired_reference",
        reference_data=reference,
        reference_filename="clean.wav",
        nominal_fundamental_hz=None,
        stimulus_kind=None,
        user_request=QUESTION,
    )
    return await service.wait_for_contextual_terminal(submission.run_id)


@pytest.mark.asyncio
async def test_t_cx445_paired_runs_report_the_basis_and_withhold_undiagnosed_harmonics() -> None:
    service = _service()
    snapshot = await _run_paired(service)
    await service.aclose()
    localization = snapshot.fault_localization
    assert localization is not None
    assert localization.harmonic_basis == "reference_growth"
    assert localization.comparison_overlap == 0.0
    assert localization.windows_not_comparable is not None
    # The scripted planner finishes inconclusive, so reference growth is withheld (§27.1).
    assert [i for i in localization.intervals if i.fault == "harmonic_distortion"] == []
    assert localization.harmonic_windows_withheld is not None
    assert localization.harmonic_windows_withheld >= 1

    dumped = dump_contextual_snapshot(snapshot)["fault_localization"]
    assert dumped["harmonic_basis"] == "reference_growth"
    assert dumped["windows_not_comparable"] == localization.windows_not_comparable
    report = build_contextual_diagnosis_report(
        snapshot, generated_at=snapshot.finished_at  # type: ignore[arg-type]
    )
    html = render_contextual_report_html(report)
    assert "compared with the same span of the reference" in html
    assert "could not be compared" in html
    assert "not shown because the diagnosis did not support harmonic distortion" in html
    assert "No segment rule failed" not in html


@pytest.mark.asyncio
async def test_t_cx445_single_file_output_omits_the_paired_fields() -> None:
    service = _service()
    snapshot = await _run(service)
    await service.aclose()
    dumped = dump_contextual_snapshot(snapshot)["fault_localization"]
    for name in ("harmonic_basis", "comparison_overlap", "windows_not_comparable"):
        assert name not in dumped
    report = build_contextual_diagnosis_report(
        snapshot, generated_at=snapshot.finished_at  # type: ignore[arg-type]
    )
    payload = json.loads(render_contextual_report_json(report))["fault_localization"]
    assert "harmonic_basis" not in payload
    assert "harmonic windows not scanned" in render_contextual_report_html(report)


def test_t_cx445_page_and_cli_follow_the_basis(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    script = (
        Path(__file__).resolve().parents[2] / "src/signal_diag/app/static/app.js"
    ).read_text(encoding="utf-8")
    assert "LOCALIZATION_SCOPE[localization.harmonic_basis]" in script
    assert "reference_growth:" in script and "nominal_thd:" in script
    assert "windows_not_comparable" in script
    assert "harmonic_windows_withheld" in script

    test, reference = _paired_wavs()
    (tmp_path / "burst.wav").write_bytes(test)
    (tmp_path / "clean.wav").write_bytes(reference)
    code = main(
        [
            "diagnose",
            "contextual",
            str(tmp_path / "burst.wav"),
            "--mode",
            "paired_reference",
            "--reference",
            str(tmp_path / "clean.wav"),
        ],
        service_factory=_service,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "harmonic_basis: reference_growth" in out
    assert "windows_not_comparable:" in out
    assert "harmonic_windows_withheld:" in out
    assert "no segment rule failed" not in out
    assert "harmonic_distortion mixdown" not in out
