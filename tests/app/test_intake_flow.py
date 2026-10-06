"""T-CX411–T-CX417: free-text intake product flow (D047, CONTRACTS_V0_3 §25)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.agent.intake import ContextDraft, ScriptedIntakePlanner
from signal_diag.app.cli import main
from signal_diag.app.composition import build_product_service
from signal_diag.app.errors import InvalidRequestError
from signal_diag.app.intake_flow import (
    INTAKE_DIAGNOSIS_QUESTION,
    IntakeAssembly,
    assemble_intake_submission,
    draft_confirmed_by_yes,
    wav_header_sample_rate,
)
from signal_diag.app.models import PlannerIdentity
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from tests.app.test_api import (
    CORPUS_PATH,
    PROFILE_PATH,
    _client,
    _contextual_wav_form,
    _encode_multipart,
    _ImmediateFinishPlanner,
)

CASES_PATH = Path(__file__).resolve().parent / "fixtures" / "intake_assembly_cases.json"


def _cases() -> list[dict[str, Any]]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert payload["schema"] == "intake_assembly_cases/1"
    cases: list[dict[str, Any]] = payload["cases"]
    return cases


def _assembly_dict(assembly: IntakeAssembly) -> dict[str, Any]:
    confirmed = assembly.confirmed
    return {
        "mode": confirmed.mode,
        "reference_file": confirmed.reference_file,
        "nominal_fundamental_hz": confirmed.nominal_fundamental_hz,
        "stimulus_kind": confirmed.stimulus_kind,
        "downgraded_from": assembly.downgraded_from,
        "unconfirmed_fields": list(assembly.unconfirmed_fields),
    }


def _wav(rate: int = 8000, frames: int = 800) -> bytes:
    t = np.arange(frames, dtype=np.float64) / rate
    samples = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32).reshape(-1, 1)
    return encode_pcm32_wav(samples, sample_rate_hz=rate)


def _service(draft: ContextDraft) -> DiagnosisApplicationService:
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
            rule_profile_loader=YamlRuleProfileLoader(
                {"profile_s1_distortion": PROFILE_PATH}
            ),
            knowledge_index=KnowledgeIndex(CORPUS_PATH),
            causal_policy_version="v9_11_mode_aware_no_fault_recovery",
            intake_planner_factory=lambda: ScriptedIntakePlanner(draft),
        )
    )


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_t_cx411_assembly_table(case: dict[str, Any]) -> None:
    selection = case["selection"]
    kwargs = {
        "mode": selection["mode"],
        "reference_file": selection["reference_file"],
        "nominal_fundamental_hz": selection["nominal_fundamental_hz"],
        "stimulus_kind": selection["stimulus_kind"],
        "filenames": tuple(case["filenames"]),
        "test_file": case["test_file"],
    }
    expected = case["expected"]
    if "error" in expected:
        with pytest.raises(InvalidRequestError):
            assemble_intake_submission(**kwargs)
        return
    assert _assembly_dict(assemble_intake_submission(**kwargs)) == expected


def test_t_cx412_unconfirmed_draft_fields_never_reach_submission() -> None:
    draft = ContextDraft(
        mode="nominal_single_tone",
        nominal_fundamental_hz=1000.0,
        stimulus_kind=None,
        missing_fields=("stimulus_kind",),
        questions=("Is the test signal a single sine tone?",),
        asked_fields=("stimulus_kind",),
    )
    confirmed = draft_confirmed_by_yes(draft)
    assert confirmed["stimulus_kind"] is None
    assembly = assemble_intake_submission(
        **confirmed, filenames=("only.wav",), test_file="only.wav"
    )
    assert assembly.confirmed.mode == "single_signal"
    assert assembly.confirmed.nominal_fundamental_hz is None
    assert assembly.confirmed.stimulus_kind is None
    assert assembly.downgraded_from == "nominal_single_tone"
    assert assembly.unconfirmed_fields == ("stimulus_kind",)


def test_t_cx412_yes_excludes_missing_and_asked_fields() -> None:
    draft = ContextDraft(
        mode="paired_reference",
        nominal_fundamental_hz=440.0,
        reference_file="old.wav",
        stimulus_kind="unknown",
        missing_fields=("nominal_fundamental_hz",),
        asked_fields=("reference_file",),
    )
    assert draft_confirmed_by_yes(draft) == {
        "mode": "paired_reference",
        "reference_file": None,
        "nominal_fundamental_hz": None,
        "stimulus_kind": None,
    }
    asked_mode = ContextDraft(mode="paired_reference", asked_fields=("mode",))
    assert draft_confirmed_by_yes(asked_mode)["mode"] is None


def test_t_cx413_nominal_hz_is_never_backfilled_from_audio() -> None:
    draft = ContextDraft(mode="nominal_single_tone", stimulus_kind="single_tone")
    confirmed = draft_confirmed_by_yes(draft)
    for rate in (8000, 48000):
        assembly = assemble_intake_submission(
            **confirmed, filenames=("tone.wav",), test_file="tone.wav"
        )
        assert wav_header_sample_rate(_wav(rate=rate)) == float(rate)
        assert assembly.confirmed.nominal_fundamental_hz is None
        assert assembly.confirmed.mode == "single_signal"
        assert assembly.unconfirmed_fields == ("nominal_fundamental_hz",)


def test_t_cx413_wav_header_sample_rate_reads_metadata_only() -> None:
    assert wav_header_sample_rate(_wav(rate=44100)) == 44100.0
    assert wav_header_sample_rate(b"") is None
    assert wav_header_sample_rate(b"RIFF\x00\x00\x00\x00WAVEjunk") is None
    assert wav_header_sample_rate(b"not a wav file at all") is None


@pytest.mark.asyncio
async def test_t_cx414_api_draft_then_confirmed_contextual_run() -> None:
    draft = ContextDraft(
        mode="nominal_single_tone",
        nominal_fundamental_hz=440.0,
        stimulus_kind="single_tone",
    )
    service = _service(draft)
    wav = _wav()
    async with _client(service) as client:
        drafted = await client.post(
            "/api/v1/intake/draft",
            json={
                "text": "the 440 Hz test tone sounds harsh",
                "filenames": ["tone.wav"],
                "test_file": "tone.wav",
                "sample_rates_hz": [8000.0],
            },
        )
        assert drafted.status_code == 200
        assert service._contextual_store._snapshots == {}
        assembly = assemble_intake_submission(
            **draft_confirmed_by_yes(ContextDraft.model_validate(drafted.json())),
            filenames=("tone.wav",),
            test_file="tone.wav",
        )
        fields = {
            "mode": assembly.confirmed.mode.encode(),
            "user_request": INTAKE_DIAGNOSIS_QUESTION.encode(),
            "channel": b"mixdown",
            "nominal_fundamental_hz": b"440",
            "stimulus_kind": b"single_tone",
            "context_origin": b"intake_confirmed",
        }
        body, content_type = _encode_multipart(
            fields=fields, files=[("test_file", "tone.wav", wav)]
        )
        accepted = await client.post(
            "/api/v1/contextual-runs/wav",
            content=body,
            headers={"Content-Type": content_type},
        )
        assert accepted.status_code == 202, accepted.text
        run_id = accepted.json()["run_id"]
        terminal = await service.wait_for_contextual_terminal(run_id)
        assert terminal.status == "completed"
        snapshot = (await client.get(f"/api/v1/contextual-runs/{run_id}")).json()
        assert snapshot["context_origin"] == "intake_confirmed"
        assert snapshot["user_request"] == INTAKE_DIAGNOSIS_QUESTION
        context = snapshot["stimulus_context"]
        assert context["mode"] == "nominal_single_tone"
        assert context["assertion_source"] == "user_supplied"
        assert context["nominal_fundamental_hz"] == 440.0
        report = json.loads(
            (await client.get(f"/api/v1/contextual-runs/{run_id}/report.json")).text
        )
        assert report["context_origin"] == "intake_confirmed"
        html = (await client.get(f"/api/v1/contextual-runs/{run_id}/report.html")).text
        assert "free-text draft, confirmed by the user" in html


@pytest.mark.asyncio
async def test_t_cx414_form_runs_keep_their_existing_outputs() -> None:
    service = _service(ContextDraft(mode="single_signal"))
    async with _client(service) as client:
        body, content_type = _contextual_wav_form(_wav(), mode="single_signal")
        accepted = await client.post(
            "/api/v1/contextual-runs/wav",
            content=body,
            headers={"Content-Type": content_type},
        )
        run_id = accepted.json()["run_id"]
        await service.wait_for_contextual_terminal(run_id)
        snapshot = (await client.get(f"/api/v1/contextual-runs/{run_id}")).json()
        report = json.loads(
            (await client.get(f"/api/v1/contextual-runs/{run_id}/report.json")).text
        )
        html = (await client.get(f"/api/v1/contextual-runs/{run_id}/report.html")).text
    assert "context_origin" not in snapshot
    assert "context_origin" not in report
    assert "free-text draft" not in html


@pytest.mark.asyncio
async def test_t_cx414_context_origin_rejects_other_values() -> None:
    service = _service(ContextDraft(mode="single_signal"))
    async with _client(service) as client:
        body, content_type = _encode_multipart(
            fields={
                "mode": b"single_signal",
                "user_request": INTAKE_DIAGNOSIS_QUESTION.encode(),
                "channel": b"mixdown",
                "context_origin": b"evaluation_manifest",
            },
            files=[("test_file", "tone.wav", _wav())],
        )
        response = await client.post(
            "/api/v1/contextual-runs/wav",
            content=body,
            headers={"Content-Type": content_type},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert service._contextual_store._snapshots == {}


def _write_wav(path: Path, rate: int = 8000) -> Path:
    path.write_bytes(_wav(rate=rate))
    return path


def test_t_cx415_cli_yes_diagnoses_with_confirmed_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = _write_wav(tmp_path / "new.wav")
    ref_file = _write_wav(tmp_path / "old.wav")
    draft = ContextDraft(mode="paired_reference", reference_file="old.wav")
    service = _service(draft)
    code = main(
        [
            "intake",
            "diagnose",
            "--text",
            "the new amp sounds harsh; old.wav is the old amp",
            "--test-file",
            str(test_file),
            "--file",
            str(ref_file),
            "--yes",
            "--output",
            "json",
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "draft mode: paired_reference" in captured.err
    report = json.loads(captured.out)
    assert report["stimulus_context"]["mode"] == "paired_reference"
    assert report["stimulus_context"]["assertion_source"] == "user_supplied"
    assert report["reference_source"]["display_name"] == "old.wav"
    assert report["context_origin"] == "intake_confirmed"
    assert report["user_request"] == INTAKE_DIAGNOSIS_QUESTION


def test_t_cx415_cli_explicit_flags_override_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = _write_wav(tmp_path / "tone.wav")
    draft = ContextDraft(mode="single_signal", missing_fields=("nominal_fundamental_hz",))
    service = _service(draft)
    code = main(
        [
            "intake",
            "diagnose",
            "--text",
            "it sounds harsh",
            "--test-file",
            str(test_file),
            "--mode",
            "nominal_single_tone",
            "--nominal-fundamental-hz",
            "440",
            "--stimulus-kind",
            "single_tone",
            "--output",
            "json",
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err
    context = json.loads(captured.out)["stimulus_context"]
    assert context["mode"] == "nominal_single_tone"
    assert context["nominal_fundamental_hz"] == 440.0


def test_t_cx415_cli_downgrade_is_announced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = _write_wav(tmp_path / "tone.wav")
    draft = ContextDraft(
        mode="nominal_single_tone",
        stimulus_kind="single_tone",
        missing_fields=("nominal_fundamental_hz",),
        questions=("What frequency is the test tone?",),
        asked_fields=("nominal_fundamental_hz",),
    )
    service = _service(draft)
    code = main(
        [
            "intake",
            "diagnose",
            "--text",
            "the test tone sounds harsh",
            "--test-file",
            str(test_file),
            "--yes",
            "--output",
            "json",
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "question (nominal_fundamental_hz): What frequency is the test tone?" in (
        captured.err
    )
    assert (
        "nominal_single_tone needs nominal_fundamental_hz, which is not confirmed; "
        "diagnosing as single_signal" in captured.err
    )
    assert json.loads(captured.out)["stimulus_context"]["mode"] == "single_signal"


def test_t_cx415_cli_non_tty_without_confirmation_refuses(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_file = _write_wav(tmp_path / "tone.wav")
    service = _service(ContextDraft(mode="single_signal"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main(
        ["intake", "diagnose", "--text", "harsh", "--test-file", str(test_file)],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "invalid_request" in captured.err
    assert "--yes" in captured.err
    assert service._contextual_store._snapshots == {}


def test_t_cx415_cli_rejects_flags_that_conflict_with_yes_free_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = _write_wav(tmp_path / "new.wav")
    service = _service(ContextDraft(mode="single_signal"))
    code = main(
        [
            "intake",
            "diagnose",
            "--text",
            "harsh",
            "--test-file",
            str(test_file),
            "--mode",
            "paired_reference",
            "--reference",
            "new.wav",
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "invalid_request" in captured.err
    assert service._contextual_store._snapshots == {}


def test_t_cx416_cli_interactive_keep_edit_skip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_file = _write_wav(tmp_path / "tone.wav")
    draft = ContextDraft(
        mode="nominal_single_tone",
        nominal_fundamental_hz=1000.0,
        stimulus_kind="single_tone",
    )
    service = _service(draft)
    # mode: keep; nominal_fundamental_hz: edit to 440; stimulus_kind: keep
    answers = iter(["k", "e", "440", "k"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    code = main(
        [
            "intake",
            "diagnose",
            "--text",
            "the 1 kHz tone sounds harsh",
            "--test-file",
            str(test_file),
            "--output",
            "json",
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err
    context = json.loads(captured.out)["stimulus_context"]
    assert context["mode"] == "nominal_single_tone"
    assert context["nominal_fundamental_hz"] == 440.0


def test_t_cx416_cli_interactive_skip_downgrades(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_file = _write_wav(tmp_path / "tone.wav")
    draft = ContextDraft(
        mode="nominal_single_tone",
        nominal_fundamental_hz=1000.0,
        stimulus_kind="single_tone",
    )
    service = _service(draft)
    # mode: keep; nominal_fundamental_hz: skip; stimulus_kind: keep
    answers = iter(["k", "s", "k"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    code = main(
        [
            "intake",
            "diagnose",
            "--text",
            "the 1 kHz tone sounds harsh",
            "--test-file",
            str(test_file),
            "--output",
            "json",
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err
    context = json.loads(captured.out)["stimulus_context"]
    assert context["mode"] == "single_signal"
    assert context["nominal_fundamental_hz"] is None
    assert "diagnosing as single_signal" in captured.err


def test_t_cx417_missing_credentials_never_fall_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = _write_wav(tmp_path / "tone.wav")
    code = main(
        [
            "intake",
            "diagnose",
            "--text",
            "harsh",
            "--test-file",
            str(test_file),
            "--yes",
        ],
        service_factory=lambda: build_product_service(environ={}),
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "planner_not_configured" in captured.err
    assert captured.out == ""
