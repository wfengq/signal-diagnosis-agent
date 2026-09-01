"""Checkpoint J — external runner execution (EV-T044–EV-T046)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from signal_diag.agent.models import (
    AgentDecision,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.planner import PlannerModel, RealLLMPlanner, ScriptedPlanner
from signal_diag.evaluation.external.manifest import canonical_json_bytes
from signal_diag.evaluation.external.models import ExternalDatasetManifest
from signal_diag.evaluation.external.runner import (
    ExternalAuthorizationError,
    ExternalPreflightError,
    run_external_agent,
    run_external_baseline,
)
from tests.evaluation.external.conftest import make_external_case
from tests.evaluation.external.test_validation import (
    materialize_manifest_assets,
    write_pcm24_wav,
)

_CASE_ID = "0123456789abcdef"
_STARTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _one_case_manifest() -> ExternalDatasetManifest:
    from tests.evaluation.external.conftest import make_external_manifest

    return make_external_manifest(
        cases=(
            make_external_case(
                case_id=_CASE_ID,
                split="final_external_test",
                source_group="A",
                external_class="inconclusive",
                confidence="reference_supported",
                parent_master_id=None,
                transform=None,
                acceptable_outcomes=("inconclusive",),
                causal_faults=(),
                analysis_wav_path=(
                    f"assets/final_external_test/extwav_final_external_test_{_CASE_ID}.wav"
                ),
                provenance_ref=f"prov_{_CASE_ID}",
                review_ref=f"review_{_CASE_ID}",
            ),
        ),
    )


def _write_sealed_study(
    manifest: ExternalDatasetManifest,
    destination: Path,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    manifest_bytes = canonical_json_bytes(manifest)
    (destination / "study_manifest.json").write_bytes(manifest_bytes)
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    (destination / "seal.sha256").write_text(
        f"{digest}  study_manifest.json\n",
        encoding="utf-8",
    )
    return destination


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    manifest = _one_case_manifest()
    asset_root = tmp_path / "asset_root"
    manifest = materialize_manifest_assets(manifest, asset_root)
    return asset_root


@pytest.fixture
def one_case_seal(tmp_path: Path, fixture_root: Path) -> Path:
    manifest = _one_case_manifest()
    manifest = materialize_manifest_assets(manifest, fixture_root)
    return _write_sealed_study(manifest, tmp_path / "sealed")


class _InconclusivePlanner:
    def __init__(self) -> None:
        self._finished = False

    async def decide(self, context: PlannerContext) -> AgentDecision:
        if not self._finished:
            self._finished = True
            return CallToolDecision(
                task_assessment=TaskAssessment(
                    task_type="distortion_analysis",
                    objective="inspect clipping",
                ),
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
            )
        return FinishDecision(
            outcome="inconclusive",
            claims=(),
            confidence_label="low",
            limitations=("insufficient evidence for a supported fault",),
        )


class _FailingPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        error = RuntimeError("provider transport failed")
        error._signal_diag_provider_error = True  # type: ignore[attr-defined]
        raise error


@dataclass
class CountingFactory:
    planner: PlannerModel
    calls: int = 0
    constructed_types: list[str] = field(default_factory=list)

    def __call__(self, client: object) -> PlannerModel:
        self.calls += 1
        self.constructed_types.append(type(self.planner).__name__)
        return self.planner


@pytest.mark.asyncio
async def test_ev_t044_shared_wav_materialization(
    one_case_seal: Path,
    fixture_root: Path,
    tmp_path: Path,
) -> None:
    output_base = tmp_path / "runs"
    baseline = await run_external_baseline(
        one_case_seal,
        fixture_root,
        output_base / "baseline",
        started_at_utc=_STARTED,
    )
    agent = await run_external_agent(
        one_case_seal,
        fixture_root,
        output_base / "agent",
        planner_factory=CountingFactory(_InconclusivePlanner()),
        authorized=True,
        client_factory=lambda: object(),
        import_openai=lambda: object(),
        started_at_utc=_STARTED,
    )
    assert len(baseline.materialized) == 1
    assert len(agent.materialized) == 1
    assert baseline.materialized[0] == agent.materialized[0]
    assert baseline.materialized[0].signal_id.startswith("sig_ext_")
    assert baseline.materialized[0].filename == (
        f"extwav_final_external_test_{_CASE_ID}.wav"
    )
    assert baseline.traces[0].execution_path == "fixed_pipeline"
    assert agent.traces[0].execution_path == "agent"


@pytest.mark.asyncio
async def test_ev_t045_provider_failure_consumes_slot_without_fallback(
    one_case_seal: Path,
    fixture_root: Path,
    tmp_path: Path,
) -> None:
    factory = CountingFactory(_FailingPlanner())
    output = tmp_path / "agent"
    report = await run_external_agent(
        one_case_seal,
        fixture_root,
        output,
        planner_factory=factory,
        authorized=True,
        client_factory=lambda: object(),
        import_openai=lambda: object(),
        started_at_utc=_STARTED,
    )
    assert factory.calls == 1
    assert len(report.attempts) == 1
    assert report.attempts[0].status == "infrastructure_error"
    assert report.traces == ()
    assert "ScriptedPlanner" not in factory.constructed_types
    attempt_path = output / "attempts" / "agent" / f"{_CASE_ID}.json"
    assert attempt_path.is_file()


@pytest.mark.asyncio
async def test_ev_t046_real_model_gate_is_explicit_before_provider_construction(
    one_case_seal: Path,
    fixture_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = CountingFactory(_FailingPlanner())
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ExternalAuthorizationError):
        await run_external_agent(
            one_case_seal,
            fixture_root,
            tmp_path / "agent",
            planner_factory=factory,
            authorized=False,
            client_factory=lambda: (_ for _ in ()).throw(AssertionError("no client")),
            started_at_utc=_STARTED,
        )
    assert factory.calls == 0

    with pytest.raises(ExternalPreflightError, match="DEEPSEEK_API_KEY"):
        await run_external_agent(
            one_case_seal,
            fixture_root,
            tmp_path / "agent_authorized",
            planner_factory=factory,
            authorized=True,
            client_factory=lambda: (_ for _ in ()).throw(AssertionError("no client")),
            import_openai=lambda: object(),
            started_at_utc=_STARTED,
        )
    assert factory.calls == 0


@pytest.mark.asyncio
async def test_preflight_rejects_scripted_planner_from_factory(
    one_case_seal: Path,
    fixture_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    factory = CountingFactory(ScriptedPlanner([]))
    with pytest.raises(ExternalPreflightError, match="ScriptedPlanner"):
        await run_external_agent(
            one_case_seal,
            fixture_root,
            tmp_path / "agent",
            planner_factory=factory,
            authorized=True,
            client_factory=lambda: object(),
            import_openai=lambda: object(),
            started_at_utc=_STARTED,
        )
    assert factory.calls == 1


@pytest.mark.asyncio
async def test_preflight_verifies_wav_digest_before_execution(
    one_case_seal: Path,
    fixture_root: Path,
    tmp_path: Path,
) -> None:
    wav_path = (
        fixture_root
        / f"assets/final_external_test/extwav_final_external_test_{_CASE_ID}.wav"
    )
    write_pcm24_wav(wav_path, frames=96_000, seed=99)
    with pytest.raises(ValueError, match="wav_sha256 mismatch"):
        await run_external_baseline(
            one_case_seal,
            fixture_root,
            tmp_path / "baseline",
            started_at_utc=_STARTED,
        )


@pytest.mark.asyncio
async def test_existing_attempt_slot_blocks_rerun(
    one_case_seal: Path,
    fixture_root: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "baseline"
    await run_external_baseline(
        one_case_seal,
        fixture_root,
        output,
        started_at_utc=_STARTED,
    )
    with pytest.raises(FileExistsError, match="attempt slot already consumed"):
        await run_external_baseline(
            one_case_seal,
            fixture_root,
            output,
            started_at_utc=_STARTED,
        )


@pytest.mark.asyncio
async def test_baseline_writes_attempt_before_trace_finalization(
    one_case_seal: Path,
    fixture_root: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "baseline"
    report = await run_external_baseline(
        one_case_seal,
        fixture_root,
        output,
        started_at_utc=_STARTED,
    )
    assert len(report.attempts) == 1
    assert report.attempts[0].status == "behavior_result"
    assert len(report.traces) == 1
    pending = output / "attempts" / "fixed_pipeline" / f"{_CASE_ID}.pending.json"
    assert not pending.exists()


def test_production_planner_factory_builds_real_llm_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.external.runner import _build_production_planner

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    planner = _build_production_planner(object())
    assert isinstance(planner, RealLLMPlanner)
