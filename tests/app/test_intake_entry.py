"""T-CX389: intake draft entry does not diagnose until confirmation."""

from __future__ import annotations

import json

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from signal_diag.agent.intake import (
    ConfirmedContext,
    ContextDraft,
    IntakeRequest,
    ScriptedIntakePlanner,
    to_contextual_submit_kwargs,
)
from signal_diag.app.api import create_app
from signal_diag.app.cli import main
from signal_diag.app.composition import build_product_service
from signal_diag.app.errors import InvalidRequestError
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.service import DiagnosisApplicationService
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository


def _draft() -> ContextDraft:
    return ContextDraft(
        mode="paired_reference",
        nominal_fundamental_hz=1000.0,
        reference_file="old.wav",
        stimulus_kind="single_tone",
        missing_fields=(),
        questions=(),
    )


def _service() -> DiagnosisApplicationService:
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    profile = root / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
    corpus = root / "src/signal_diag/knowledge/corpus"
    from signal_diag.app.models import PlannerIdentity
    from signal_diag.app.service import ApplicationDependencies
    from signal_diag.knowledge.index import KnowledgeIndex

    return DiagnosisApplicationService(
        ApplicationDependencies(
            repository=InMemorySignalRepository(),
            planner_factory=lambda: None,  # type: ignore[return-value, arg-type]
            planner_identity=PlannerIdentity(
                provider="deepseek",
                model="deepseek-v4-flash",
                prompt_version="v0.3-s1-planner-9.11",
                phase4_certified_default=False,
            ),
            planner_configured=True,
            rule_engine=RuleEngine(),
            rule_profile_loader=YamlRuleProfileLoader({"profile_s1_distortion": profile}),
            knowledge_index=KnowledgeIndex(corpus),
            causal_policy_version="v9_11_mode_aware_no_fault_recovery",
            intake_planner_factory=lambda: ScriptedIntakePlanner(_draft()),
        )
    )


@pytest.mark.asyncio
async def test_t_cx389_draft_endpoint_does_not_open_a_diagnosis_run() -> None:
    service = _service()
    app = create_app(service)
    body = {
        "text": "新功放放 1 kHz 测试音发毛，旧功放的录音也附上了",
        "filenames": ["new.wav", "old.wav"],
        "test_file": "new.wav",
        "sample_rates_hz": [48000.0, 48000.0],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/intake/draft", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "paired_reference"
    assert payload["nominal_fundamental_hz"] == 1000.0
    assert service._contextual_store._snapshots == {}
    await service.aclose()


@pytest.mark.asyncio
async def test_t_cx389_missing_credentials_return_planner_not_configured() -> None:
    service = build_product_service(environ={})
    app = create_app(service)
    body = {
        "text": "听着发毛",
        "filenames": ["only.wav"],
        "test_file": "only.wav",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/intake/draft", json=body)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "planner_not_configured"
    await service.aclose()


@pytest.mark.asyncio
async def test_t_cx389_confirmed_fields_use_existing_contextual_validation() -> None:
    service = _service()
    confirmed = ConfirmedContext(
        mode="single_signal",
        nominal_fundamental_hz=1000.0,
        reference_file=None,
        stimulus_kind="single_tone",
    )
    fields = to_contextual_submit_kwargs(confirmed)
    samples = np.zeros((16, 1), dtype=np.float32)
    wav = encode_pcm32_wav(samples, sample_rate_hz=8000)
    with pytest.raises(InvalidRequestError, match="nominal"):
        await service.submit_contextual_wav(
            wav,
            test_filename="only.wav",
            mode=fields["mode"],  # type: ignore[arg-type]
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=fields["nominal_fundamental_hz"],  # type: ignore[arg-type]
            stimulus_kind=fields["stimulus_kind"],  # type: ignore[arg-type]
            user_request="why is this distorted",
        )
    assert service._contextual_store._snapshots == {}
    clean = ConfirmedContext(
        mode="single_signal",
        nominal_fundamental_hz=None,
        reference_file=None,
        stimulus_kind=None,
    )
    request = IntakeRequest(
        text="听着发毛",
        filenames=("only.wav",),
        test_file="only.wav",
    )
    draft = ContextDraft(
        mode="single_signal",
        nominal_fundamental_hz=None,
        reference_file=None,
        stimulus_kind=None,
        missing_fields=("nominal_fundamental_hz",),
        questions=("标称频率？",),
    )
    assert draft.nominal_fundamental_hz != request.text
    submitted = to_contextual_submit_kwargs(clean)
    assert submitted["nominal_fundamental_hz"] is None
    assert "missing_fields" not in submitted
    await service.aclose()


def test_t_cx389_cli_draft_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    service = _service()
    code = main(
        [
            "intake",
            "draft",
            "--text",
            "新功放放 1 kHz 测试音发毛，旧功放的录音也附上了",
            "--file",
            "new.wav",
            "--file",
            "old.wav",
            "--test-file",
            "new.wav",
        ],
        service_factory=lambda: service,
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["reference_file"] == "old.wav"
    assert service._contextual_store._snapshots == {}
