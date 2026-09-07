"""T-CX208+: contextual validation campaign runner."""

from __future__ import annotations

import json
import math
import struct
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from signal_diag.evaluation.contextual.models import ArmResult


def _sine_wav_bytes(*, rate: int = 8_000, frequency_hz: float = 200.0) -> bytes:
    payload = BytesIO()
    samples = [
        int(0.4 * 32767 * math.sin(2.0 * math.pi * frequency_hz * i / rate))
        for i in range(rate)
    ]
    with wave.open(payload, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return payload.getvalue()


def test_t_cx208_execution_input_schema_excludes_truth_and_payload_data() -> None:
    from signal_diag.evaluation.contextual.models import ContextualExecutionInput

    item = ContextualExecutionInput(
        case_id="case_a",
        mode="paired_reference",
        test_wav_path="wav/test.wav",
        reference_wav_path="wav/reference.wav",
    )

    payload = item.model_dump(mode="json")
    assert set(payload) == {
        "case_id",
        "mode",
        "test_wav_path",
        "reference_wav_path",
        "nominal_fundamental_hz",
        "stimulus_kind",
    }
    forbidden = {
        "role",
        "expected_outcome",
        "expected_causal_set",
        "confidence_tier",
        "scoreable",
        "source_id",
        "license_id",
        "transform_identity",
        "samples",
        "frequencies_hz",
    }
    assert forbidden.isdisjoint(ContextualExecutionInput.model_fields)


@pytest.mark.parametrize("bad_hz", [None, 0.0, -1.0, math.inf, math.nan])
def test_t_cx209_nominal_execution_input_requires_finite_positive_hz(
    bad_hz: float | None,
) -> None:
    from signal_diag.evaluation.contextual.models import ContextualExecutionInput

    with pytest.raises(ValidationError):
        ContextualExecutionInput(
            case_id="case_nominal",
            mode="nominal_single_tone",
            test_wav_path="wav/test.wav",
            nominal_fundamental_hz=bad_hz,
            stimulus_kind="single_tone",
        )


def test_t_cx209_mode_specific_execution_input_requirements() -> None:
    from signal_diag.evaluation.contextual.models import ContextualExecutionInput

    nominal = ContextualExecutionInput(
        case_id="case_nominal",
        mode="nominal_single_tone",
        test_wav_path="wav/test.wav",
        nominal_fundamental_hz=440.0,
        stimulus_kind="single_tone",
    )
    paired = ContextualExecutionInput(
        case_id="case_paired",
        mode="paired_reference",
        test_wav_path="wav/test.wav",
        reference_wav_path="wav/reference.wav",
    )
    single = ContextualExecutionInput(
        case_id="case_single",
        mode="single_signal",
        test_wav_path="wav/test.wav",
    )

    assert nominal.nominal_fundamental_hz == 440.0
    assert paired.reference_wav_path == "wav/reference.wav"
    assert single.reference_wav_path is None

    with pytest.raises(ValidationError):
        ContextualExecutionInput(
            case_id="bad_pair",
            mode="paired_reference",
            test_wav_path="wav/test.wav",
        )
    with pytest.raises(ValidationError):
        ContextualExecutionInput(
            case_id="bad_single",
            mode="single_signal",
            test_wav_path="wav/test.wav",
            reference_wav_path="wav/reference.wav",
        )


def test_t_cx210_execution_plan_freezes_arm_major_order_and_unique_cases() -> None:
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionInput,
        ContextualExecutionPlan,
    )

    first = ContextualExecutionInput(
        case_id="case_a",
        mode="single_signal",
        test_wav_path="wav/a.wav",
    )
    second = ContextualExecutionInput(
        case_id="case_b",
        mode="single_signal",
        test_wav_path="wav/b.wav",
    )
    plan = ContextualExecutionPlan(cases=(first, second))

    assert plan.arm_order == (
        "contextual_agent",
        "fixed_pipeline",
        "no_context_ablation",
    )
    assert [slot.case_id for slot in plan.slots] == [
        "case_a",
        "case_b",
        "case_a",
        "case_b",
        "case_a",
        "case_b",
    ]
    assert [slot.arm for slot in plan.slots] == [
        "contextual_agent",
        "contextual_agent",
        "fixed_pipeline",
        "fixed_pipeline",
        "no_context_ablation",
        "no_context_ablation",
    ]
    assert plan.slots[-1].mode == "single_signal"

    with pytest.raises(ValidationError):
        ContextualExecutionPlan(cases=(first, first))


def _slot_artifacts(slot: Any, *, infrastructure: bool = False) -> Any:
    from signal_diag.evaluation.contextual.campaign import CampaignSlotArtifacts

    arm_result = ArmResult(
        case_id=slot.case_id,
        arm=slot.arm,
        status="infrastructure_failure" if infrastructure else "ok",
        predicted_outcome=None if infrastructure else "inconclusive",
        infrastructure_failure=infrastructure,
    )
    return CampaignSlotArtifacts(
        arm_result=arm_result,
        attempts={"attempt_count": 1},
        trace={"events": []},
        result={"status": arm_result.status},
        summary={"case_id": slot.case_id, "arm": slot.arm},
    )


def _runtime_identity() -> Any:
    from signal_diag.evaluation.contextual.models import ContextualRuntimeIdentity

    return ContextualRuntimeIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        planner_class="RealLLMPlanner",
        prompt_version="v0.3-s1-planner-9.11",
        prompt_sha256="a" * 64,
        causal_policy_version="v9_11_mode_aware_no_fault_recovery",
        product_tree_sha256="b" * 64,
    )


def test_t_cx258_arm_result_records_same_run_claim_population_counts() -> None:
    from types import SimpleNamespace

    from signal_diag.evaluation.contextual.campaign import _arm_result_from_result
    from signal_diag.evaluation.contextual.models import ContextualExecutionSlot

    slot = ContextualExecutionSlot(
        case_id="case_a",
        arm="contextual_agent",
        mode="single_signal",
        test_wav_path="wav/a.wav",
    )
    result = SimpleNamespace(
        diagnosis=SimpleNamespace(
            outcome="supported_fault",
            claims=(
                SimpleNamespace(
                    fault_type="clipping",
                    evidence_refs=("ev_1",),
                    rule_refs=("rule_1",),
                ),
                SimpleNamespace(
                    fault_type="inconclusive",
                    evidence_refs=("missing",),
                    rule_refs=("rule_1",),
                ),
            ),
        ),
        evidence=(SimpleNamespace(evidence_id="ev_1"),),
        rule_evaluation_batches=(
            SimpleNamespace(
                evaluations=(SimpleNamespace(evaluation_id="rule_1"),)
            ),
        ),
        tool_history=(),
    )

    arm_result = _arm_result_from_result(slot, result)

    assert arm_result.claim_count == 2
    assert arm_result.grounded_claim_count == 1
    assert arm_result.predicted_positive_fault_claim_count == 1
    assert arm_result.unsupported_positive_fault_claim_count == 0


@pytest.mark.asyncio
async def test_t_cx212_campaign_executes_exact_arm_major_order_once(
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        run_contextual_validation_campaign,
    )
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionInput,
        ContextualExecutionPlan,
    )

    plan = ContextualExecutionPlan(
        cases=(
            ContextualExecutionInput(
                case_id="case_a", mode="single_signal", test_wav_path="wav/a.wav"
            ),
            ContextualExecutionInput(
                case_id="case_b", mode="single_signal", test_wav_path="wav/b.wav"
            ),
        )
    )
    observed: list[tuple[str, str]] = []

    async def execute(slot: Any) -> Any:
        observed.append((slot.arm, slot.case_id))
        return _slot_artifacts(slot)

    output = tmp_path / "campaign"
    state = await run_contextual_validation_campaign(
        plan=plan,
        output=output,
        executors={arm: execute for arm in plan.arm_order},
        preflight_record={"status": "passed"},
    )

    assert observed == [(slot.arm, slot.case_id) for slot in plan.slots]
    assert state.status == "execution_complete_unscored"
    assert state.terminal_slots == 6
    for slot in plan.slots:
        case_dir = output / "arms" / slot.arm / slot.case_id
        assert {path.name for path in case_dir.iterdir()} == {
            "attempts.json",
            "trace.json",
            "result.json",
            "case_summary.json",
        }


@pytest.mark.asyncio
async def test_t_cx213_behavior_failure_continues_but_infrastructure_stops(
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        CampaignSlotArtifacts,
        run_contextual_validation_campaign,
    )
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionInput,
        ContextualExecutionPlan,
    )

    plan = ContextualExecutionPlan(
        cases=(
            ContextualExecutionInput(
                case_id="behavior", mode="single_signal", test_wav_path="wav/a.wav"
            ),
            ContextualExecutionInput(
                case_id="infra", mode="single_signal", test_wav_path="wav/b.wav"
            ),
            ContextualExecutionInput(
                case_id="not_run", mode="single_signal", test_wav_path="wav/c.wav"
            ),
        )
    )
    observed: list[str] = []

    async def execute(slot: Any) -> Any:
        observed.append(slot.case_id)
        if slot.case_id == "behavior":
            artifacts = _slot_artifacts(slot)
            return CampaignSlotArtifacts(
                arm_result=artifacts.arm_result,
                attempts=artifacts.attempts,
                trace=artifacts.trace,
                result={"status": "behavior_error"},
                summary=artifacts.summary,
            )
        return _slot_artifacts(slot, infrastructure=slot.case_id == "infra")

    state = await run_contextual_validation_campaign(
        plan=plan,
        output=tmp_path / "stopped",
        executors={arm: execute for arm in plan.arm_order},
        preflight_record={"status": "passed"},
    )

    assert observed == ["behavior", "infra"]
    assert state.status == "infrastructure_stopped"
    assert state.terminal_slots == 2
    assert state.stopped_after == "contextual_agent:infra"


@pytest.mark.asyncio
async def test_t_cx214_campaign_refuses_existing_output(tmp_path: Path) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        run_contextual_validation_campaign,
    )
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionInput,
        ContextualExecutionPlan,
    )

    output = tmp_path / "existing"
    output.mkdir()
    plan = ContextualExecutionPlan(
        cases=(
            ContextualExecutionInput(
                case_id="case_a", mode="single_signal", test_wav_path="wav/a.wav"
            ),
        )
    )

    async def execute(slot: Any) -> Any:
        return _slot_artifacts(slot)

    with pytest.raises(FileExistsError):
        await run_contextual_validation_campaign(
            plan=plan,
            output=output,
            executors={arm: execute for arm in plan.arm_order},
            preflight_record={"status": "passed"},
        )


def test_t_cx215_preflight_refuses_historical_v2_before_execution(
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        CampaignPreflightError,
        preflight_contextual_validation,
    )

    repo = Path(__file__).resolve().parents[3]
    study = (
        repo
        / "docs"
        / "evaluations"
        / "v0_3"
        / "contextual"
        / "validation"
        / "study_v0_3_contextual_validation_1"
    )
    with pytest.raises(CampaignPreflightError, match="validation_seal_v4"):
        preflight_contextual_validation(
            study_dir=study,
            seal_dir=study / "validation_seal_v2",
            output=tmp_path / "run",
            environ={"DEEPSEEK_API_KEY": "present-but-not-persisted"},
        )


def test_t_cx216_real_executor_builder_uses_real_planner_without_calling_model() -> None:
    from signal_diag.agent.planner import RealLLMPlanner
    from signal_diag.app.contextual_campaign import build_real_agent_executor

    executor = build_real_agent_executor(
        study_dir=Path.cwd(),
        expected_identity=_runtime_identity(),
        environ={"DEEPSEEK_API_KEY": "present-but-not-persisted"}
    )

    assert isinstance(
        executor.service._dependencies.planner_factory(), RealLLMPlanner
    )
    assert executor.model == "deepseek-v4-flash"
    assert executor.prompt_version == "v0.3-s1-planner-9.11"


@pytest.mark.asyncio
async def test_t_cx217_real_executor_maps_product_snapshot_without_truth(
    tmp_path: Path,
) -> None:
    from signal_diag.agent.models import AgentRunResult
    from signal_diag.agent.planner import RealLLMPlanner
    from signal_diag.app.contextual_campaign import RealAgentSlotExecutor
    from signal_diag.app.models import PlannerIdentity
    from signal_diag.evaluation.contextual.models import ContextualExecutionSlot

    wav = tmp_path / "wav" / "test.wav"
    wav.parent.mkdir()
    wav.write_bytes(b"local-wav-bytes")
    result = AgentRunResult(
        run_id="run_test",
        status="inconclusive",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="planner_finished",
    )

    class FakeService:
        def __init__(self) -> None:
            self._dependencies = SimpleNamespace(
                planner_factory=lambda: RealLLMPlanner(
                    provider="deepseek",
                    api_key="present-but-not-persisted",
                    client=SimpleNamespace(),
                ),
                planner_identity=PlannerIdentity(
                    provider="deepseek",
                    model="deepseek-v4-flash",
                    prompt_version="v0.3-s1-planner-9.11",
                    phase4_certified_default=False,
                ),
                causal_policy_version="v9_11_mode_aware_no_fault_recovery",
            )
            self.submitted: bytes | None = None

        async def submit_wav(self, data: bytes, **kwargs: Any) -> Any:
            self.submitted = data
            return SimpleNamespace(run_id="run_test")

        async def wait_for_terminal(self, run_id: str) -> Any:
            assert run_id == "run_test"
            return SimpleNamespace(
                status="completed",
                result=result,
                trace_events=(),
                application_error=None,
            )

    service = FakeService()
    executor = RealAgentSlotExecutor(  # type: ignore[arg-type]
        service,
        study_dir=tmp_path,
        expected_identity=_runtime_identity(),
    )
    artifacts = await executor(
        ContextualExecutionSlot(
            case_id="case_a",
            arm="contextual_agent",
            mode="single_signal",
            test_wav_path="wav/test.wav",
        )
    )

    assert service.submitted == b"local-wav-bytes"
    assert artifacts.arm_result.case_id == "case_a"
    assert artifacts.arm_result.predicted_outcome is None
    serialized = artifacts.model_dump_json()
    assert "local-wav-bytes" not in serialized
    assert "expected_outcome" not in serialized
    assert "expected_causal_set" not in serialized


@pytest.mark.asyncio
async def test_t_cx218_fixed_executor_uses_wav_and_declared_context_only(
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.contextual.campaign import FixedPipelineSlotExecutor
    from signal_diag.evaluation.contextual.models import ContextualExecutionSlot

    wav = tmp_path / "wav" / "test.wav"
    wav.parent.mkdir()
    wav.write_bytes(_sine_wav_bytes())
    executor = FixedPipelineSlotExecutor(study_dir=tmp_path)

    artifacts = await executor(
        ContextualExecutionSlot(
            case_id="case_nominal",
            arm="fixed_pipeline",
            mode="nominal_single_tone",
            test_wav_path="wav/test.wav",
            nominal_fundamental_hz=200.0,
            stimulus_kind="single_tone",
        )
    )

    assert artifacts.arm_result.case_id == "case_nominal"
    assert artifacts.arm_result.arm == "fixed_pipeline"
    assert artifacts.arm_result.status == "ok"
    serialized = artifacts.model_dump_json()
    assert "expected_outcome" not in serialized
    assert "expected_causal_set" not in serialized
    assert '"samples":' not in serialized


def test_t_cx219_preflight_refuses_existing_output_before_execution(
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        CampaignPreflightError,
        preflight_contextual_validation,
    )

    output = tmp_path / "already_exists"
    output.mkdir()
    with pytest.raises(CampaignPreflightError, match="output already exists"):
        preflight_contextual_validation(
            study_dir=tmp_path,
            seal_dir=tmp_path / "validation_seal_v4",
            output=output,
            environ={"DEEPSEEK_API_KEY": "present-but-not-persisted"},
        )


def test_t_cx220_scoring_occurs_after_execution_and_applies_all_hard_gates() -> None:
    from signal_diag.evaluation.contextual.campaign import score_completed_campaign
    from signal_diag.evaluation.contextual.manifest import load_contextual_manifest

    repo = Path(__file__).resolve().parents[3]
    validation = repo / "docs" / "evaluations" / "v0_3" / "contextual" / "validation"
    manifest = load_contextual_manifest(
        validation / "study_v0_3_contextual_validation_1" / "contextual_manifest.json"
    )
    targets = __import__("json").loads(
        (validation / "acceptance_targets.json").read_text(encoding="utf-8")
    )
    results: list[ArmResult] = []
    for arm in ("contextual_agent", "fixed_pipeline", "no_context_ablation"):
        for case in manifest.cases:
            causal = case.expected_causal_set
            outcome = case.expected_outcome
            if arm == "no_context_ablation" and case.case_id in {
                slot.case_id for slot in manifest.paired_harmonic_slots
            }:
                causal = tuple(item for item in causal if item != "harmonic_distortion")
                outcome = "supported_fault" if causal else "inconclusive"
            results.append(
                ArmResult(
                    case_id=case.case_id,
                    arm=arm,  # type: ignore[arg-type]
                    status="ok",
                    predicted_outcome=outcome,
                    predicted_causal_set=causal,
                    evidence_refs_complete=True,
                    claim_count=max(1, len(causal)),
                    grounded_claim_count=max(1, len(causal)),
                    predicted_positive_fault_claim_count=len(causal),
                    unsupported_positive_fault_claim_count=0,
                )
            )

    report = score_completed_campaign(
        manifest=manifest,
        results=results,
        acceptance_targets=targets,
    )

    assert report["target_status"] == "meets_target"
    assert report["gates"]["planner_completion"] is True
    assert all(report["role_hard_gates"].values())


def test_t_cx259_empty_positive_population_blocks_unsupported_claim_gate() -> None:
    from signal_diag.evaluation.contextual.campaign import score_completed_campaign
    from signal_diag.evaluation.contextual.manifest import load_contextual_manifest

    repo = Path(__file__).resolve().parents[3]
    validation = repo / "docs" / "evaluations" / "v0_3" / "contextual" / "validation"
    manifest = load_contextual_manifest(
        validation / "study_v0_3_contextual_validation_1" / "contextual_manifest.json"
    )
    targets = __import__("json").loads(
        (validation / "acceptance_targets.json").read_text(encoding="utf-8")
    )
    results = [
        ArmResult(
            case_id=case.case_id,
            arm=arm,  # type: ignore[arg-type]
            status="ok",
            predicted_outcome="inconclusive",
            claim_count=1,
            grounded_claim_count=1,
        )
        for arm in ("contextual_agent", "fixed_pipeline", "no_context_ablation")
        for case in manifest.cases
    ]

    report = score_completed_campaign(
        manifest=manifest,
        results=results,
        acceptance_targets=targets,
    )

    assert (
        report["scores"]["contextual_agent"]["aggregate"][
            "unsupported_claim_rate"
        ]["denominator"]
        == 0
    )
    assert report["gates"]["unsupported_claim_rate"] is False


def test_t_cx260_reconstructs_claim_populations_from_immutable_results() -> None:
    from signal_diag.evaluation.contextual.campaign import (
        reconstruct_arm_results_from_campaign,
        score_completed_campaign,
    )
    from signal_diag.evaluation.contextual.manifest import load_contextual_manifest

    repo = Path(__file__).resolve().parents[3]
    root = repo / "docs" / "evaluations" / "v0_3" / "contextual"
    study = root / "validation" / "study_v0_3_contextual_validation_1"
    run = study / "agent_v9_11_validation_run_1"
    manifest = load_contextual_manifest(study / "contextual_manifest.json")
    targets = __import__("json").loads(
        (root / "validation" / "acceptance_targets.json").read_text(
            encoding="utf-8"
        )
    )

    results = reconstruct_arm_results_from_campaign(run, manifest)
    report = score_completed_campaign(
        manifest=manifest,
        results=results,
        acceptance_targets=targets,
    )

    agent = [item for item in results if item.arm == "contextual_agent"]
    assert sum(item.claim_count for item in agent) == 21
    assert sum(item.grounded_claim_count for item in agent) == 21
    assert sum(item.predicted_positive_fault_claim_count for item in agent) == 10
    assert sum(item.unsupported_positive_fault_claim_count for item in agent) == 0
    assert report["target_status"] == "meets_target"


def test_t_cx221_cli_requires_explicit_real_model_authorization() -> None:
    from signal_diag.app.contextual_campaign import _build_parser

    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "run-validation",
                "--study-dir",
                "study",
                "--seal",
                "seal",
                "--output",
                "run",
            ]
        )
    args = parser.parse_args(
        [
            "run-validation",
            "--study-dir",
            "study",
            "--seal",
            "seal",
            "--output",
            "run",
            "--authorization",
            "authorized-structured-context-only",
        ]
    )
    assert args.authorization == "authorized-structured-context-only"


def test_t_cx222_campaign_test_ids_are_registered_once() -> None:
    import re

    repo = Path(__file__).resolve().parents[3]
    text = (repo / "docs" / "TEST_PLAN_V0_3_CONTEXTUAL.md").read_text(
        encoding="utf-8"
    )
    ids = re.findall(r"^\| (T-CX\d+) \|", text, flags=re.MULTILINE)
    for number in range(208, 231):
        assert ids.count(f"T-CX{number}") == 1


def test_t_cx223_historical_v3_retains_case_keyed_wav_checksums() -> None:
    from signal_diag.evaluation.contextual.sealing import verify_contextual_bundle

    repo = Path(__file__).resolve().parents[3]
    study = (
        repo
        / "docs"
        / "evaluations"
        / "v0_3"
        / "contextual"
        / "validation"
        / "study_v0_3_contextual_validation_1"
    )
    seal = study / "validation_seal_v3"  # historical checksum-key evidence
    verify_contextual_bundle(seal)
    checksums = json.loads((seal / "wav_checksums.json").read_text("utf-8"))
    execution_inputs = json.loads(
        (seal / "execution_inputs.json").read_text("utf-8")
    )
    case_ids = {item["case_id"] for item in execution_inputs}
    assert len(case_ids) == 20
    assert {key.split(":", 1)[1] for key in checksums} == case_ids
    assert all(key.startswith(("test:", "ref:")) for key in checksums)


@pytest.mark.asyncio
async def test_t_cx224_executor_exception_is_sanitized_and_stops_campaign(
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        run_contextual_validation_campaign,
    )
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionInput,
        ContextualExecutionPlan,
    )

    plan = ContextualExecutionPlan(
        cases=(
            ContextualExecutionInput(
                case_id="infra", mode="single_signal", test_wav_path="wav/a.wav"
            ),
        )
    )

    async def execute(slot: Any) -> Any:
        raise ConnectionError("provider unavailable key=must-not-survive")

    output = tmp_path / "stopped"
    state = await run_contextual_validation_campaign(
        plan=plan,
        output=output,
        executors={arm: execute for arm in plan.arm_order},
        preflight_record={"status": "passed"},
    )

    assert state.status == "infrastructure_stopped"
    payload = (
        output / "arms" / "contextual_agent" / "infra" / "result.json"
    ).read_text(encoding="utf-8")
    assert "must-not-survive" not in payload
    assert "internal_error" in payload


def test_t_cx225_harness_identity_covers_provider_facing_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.contextual.calibration import (
        contextual_implementation_sha256,
    )

    original_read = Path.read_bytes
    before = contextual_implementation_sha256()

    def changed(path: Path) -> bytes:
        payload = original_read(path)
        if path.as_posix().endswith("app/contextual_campaign.py"):
            return payload + b"# identity probe\n"
        return payload

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert contextual_implementation_sha256() != before


def test_t_cx226_real_executor_rejects_runtime_identity_drift() -> None:
    from signal_diag.app.contextual_campaign import build_real_agent_executor

    with pytest.raises(ValueError, match="runtime identity"):
        build_real_agent_executor(
            study_dir=Path.cwd(),
            expected_identity=_runtime_identity(),
            environ={
                "DEEPSEEK_API_KEY": "present-but-not-persisted",
                "DEEPSEEK_MODEL": "unexpected-model",
            },
        )


def test_t_cx227_preflight_rejects_non_authoritative_v3_path(tmp_path: Path) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        CampaignPreflightError,
        preflight_contextual_validation,
    )

    alternate = tmp_path / "other" / "validation_seal_v4"
    with pytest.raises(CampaignPreflightError, match="authoritative"):
        preflight_contextual_validation(
            study_dir=tmp_path,
            seal_dir=alternate,
            output=tmp_path / "output",
            environ={"DEEPSEEK_API_KEY": "present-but-not-persisted"},
        )


@pytest.mark.asyncio
async def test_t_cx228_campaign_copies_seal_identity_at_start(tmp_path: Path) -> None:
    from signal_diag.evaluation.contextual.campaign import (
        run_contextual_validation_campaign,
    )
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionInput,
        ContextualExecutionPlan,
    )

    plan = ContextualExecutionPlan(
        cases=(
            ContextualExecutionInput(
                case_id="case_a", mode="single_signal", test_wav_path="wav/a.wav"
            ),
        )
    )

    async def execute(slot: Any) -> Any:
        return _slot_artifacts(slot)

    record = {
        "status": "passed",
        "seal": "validation_seal_v4",
        "seal_index_sha256": "a" * 64,
        "prompt_sha256": "b" * 64,
        "evaluation_harness_sha256": "c" * 64,
        "runtime_identity": _runtime_identity().model_dump(mode="json"),
    }
    output = tmp_path / "campaign"
    await run_contextual_validation_campaign(
        plan=plan,
        output=output,
        executors={arm: execute for arm in plan.arm_order},
        preflight_record=record,
    )

    copied = __import__("json").loads(
        (output / "seal_identity.json").read_text(encoding="utf-8")
    )
    assert copied["seal_index_sha256"] == "a" * 64
    assert copied["runtime_identity"]["model"] == "deepseek-v4-flash"


def test_t_cx229_live_cli_exposes_preflight_and_run_subcommands() -> None:
    from signal_diag.app.contextual_campaign import _build_parser

    parser = _build_parser()
    preflight = parser.parse_args(
        [
            "preflight-validation",
            "--study-dir",
            "study",
            "--seal",
            "seal",
            "--output",
            "run",
        ]
    )
    run = parser.parse_args(
        [
            "run-validation",
            "--study-dir",
            "study",
            "--seal",
            "seal",
            "--output",
            "run",
            "--authorization",
            "authorized-structured-context-only",
        ]
    )
    assert preflight.command == "preflight-validation"
    assert run.command == "run-validation"


def test_t_cx230_finalization_writes_run_summary(tmp_path: Path) -> None:
    import json

    from signal_diag.evaluation.contextual.campaign import finalize_campaign_output
    from signal_diag.evaluation.contextual.manifest import load_contextual_manifest

    repo = Path(__file__).resolve().parents[3]
    validation = repo / "docs" / "evaluations" / "v0_3" / "contextual" / "validation"
    study = validation / "study_v0_3_contextual_validation_1"
    manifest = load_contextual_manifest(study / "contextual_manifest.json")
    output = tmp_path / "complete"
    output.mkdir()
    (output / "execution_ledger.json").write_text(
        json.dumps({"status": "execution_complete_unscored"}), encoding="utf-8"
    )
    for arm in ("contextual_agent", "fixed_pipeline", "no_context_ablation"):
        for case in manifest.cases:
            item = ArmResult(
                case_id=case.case_id,
                arm=arm,  # type: ignore[arg-type]
                status="ok",
                predicted_outcome=case.expected_outcome,
                predicted_causal_set=case.expected_causal_set,
                evidence_refs_complete=True,
            )
            case_dir = output / "arms" / arm / case.case_id
            case_dir.mkdir(parents=True)
            (case_dir / "case_summary.json").write_text(
                json.dumps({"arm_result": item.model_dump(mode="json")}),
                encoding="utf-8",
            )

    finalize_campaign_output(
        seal_dir=study / "validation_seal_v3",
        output=output,
        acceptance_targets_path=validation / "acceptance_targets.json",
    )

    summary = json.loads((output / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["executed_slots"] == 60
    assert summary["target_status"] in {"meets_target", "below_target"}
