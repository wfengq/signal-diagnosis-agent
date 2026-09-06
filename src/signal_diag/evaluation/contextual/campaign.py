"""Append-only orchestration for contextual validation campaigns."""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable, Mapping
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict

from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_9
from signal_diag.evaluation.contextual.baseline import ContextualFixedPipelineBaseline
from signal_diag.evaluation.contextual.calibration import (
    contextual_implementation_sha256,
    contextual_product_tree_sha256,
)
from signal_diag.evaluation.contextual.manifest import manifest_sha256
from signal_diag.evaluation.contextual.models import (
    CONTEXTUAL_SCORING_ID,
    CONTEXTUAL_SCORING_VERSION,
    ArmKind,
    ArmResult,
    ContextualBaselineRequest,
    ContextualExecutionPlan,
    ContextualExecutionSlot,
    ContextualManifest,
    ContextualRuntimeIdentity,
)
from signal_diag.evaluation.contextual.scoring import score_contextual_run
from signal_diag.evaluation.contextual.sealing import verify_contextual_bundle
from signal_diag.evaluation.models import CausalFault
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.wav import load_wav_bytes
from signal_diag.tools.service import SignalToolService

SlotExecutor = Callable[[ContextualExecutionSlot], Awaitable["CampaignSlotArtifacts"]]


class CampaignPreflightError(RuntimeError):
    """Raised before any executor or provider call when a campaign is unsafe."""


class FixedPipelineSlotExecutor:
    """Truth-free deterministic baseline over local WAV and declared context."""

    def __init__(self, *, study_dir: Path) -> None:
        self.study_dir = study_dir.resolve()

    async def __call__(self, slot: ContextualExecutionSlot) -> CampaignSlotArtifacts:
        repository = InMemorySignalRepository()
        test_path = _resolve_input(self.study_dir, slot.test_wav_path)
        test_record = load_wav_bytes(
            test_path.read_bytes(), filename=test_path.name
        ).record
        repository.put(test_record)
        reference_id: str | None = None
        if slot.reference_wav_path is not None:
            reference_path = _resolve_input(self.study_dir, slot.reference_wav_path)
            reference_record = load_wav_bytes(
                reference_path.read_bytes(), filename=reference_path.name
            ).record
            repository.put(reference_record)
            reference_id = reference_record.meta.signal_id
        context = StimulusContext(
            mode=slot.mode,
            test_signal_id=test_record.meta.signal_id,
            reference_signal_id=reference_id,
            nominal_fundamental_hz=slot.nominal_fundamental_hz,
            stimulus_kind=slot.stimulus_kind,
            assertion_source="evaluation_manifest",
        )
        package = files("signal_diag")
        profiles = Path(str(package.joinpath("rules", "profiles")))
        baseline = ContextualFixedPipelineBaseline(
            repository=repository,
            tool_service=SignalToolService(repository),
            rule_engine=RuleEngine(),
            profile_loader=YamlRuleProfileLoader(
                {
                    "profile_s1_distortion": profiles / "s1_distortion_v1.yaml",
                    "profile_s1_contextual_comparison": (
                        profiles / "s1_contextual_comparison_v1.yaml"
                    ),
                }
            ),
        )
        result = await baseline.run(
            ContextualBaselineRequest(
                case_id=slot.case_id,
                signal_id=test_record.meta.signal_id,
                stimulus_context=context,
            )
        )
        arm_result = _arm_result_from_result(slot, result)
        return CampaignSlotArtifacts(
            arm_result=arm_result,
            attempts={"attempt_count": 1, "provider_attempts": 0},
            trace={"events": []},
            result=_model_json(result),
            summary={
                "case_id": slot.case_id,
                "arm": slot.arm,
                "mode": slot.mode,
                "arm_result": arm_result.model_dump(mode="json"),
            },
        )


def preflight_contextual_validation(
    *,
    study_dir: Path,
    seal_dir: Path,
    output: Path,
    environ: Mapping[str, str] | None = None,
) -> CampaignPreflight:
    """Validate the active campaign identity without constructing an executor."""

    if seal_dir.name != "validation_seal_v3":
        raise CampaignPreflightError(
            "contextual validation requires active validation_seal_v3"
        )
    study_dir = study_dir.resolve()
    seal_dir = seal_dir.resolve()
    if seal_dir != study_dir / "validation_seal_v3":
        raise CampaignPreflightError("seal is not the authoritative active v3 path")
    if output.exists():
        raise CampaignPreflightError(f"campaign output already exists: {output}")
    try:
        supersession = json.loads(
            (study_dir / "VALIDATION_SEAL_SUPERSESSION.json").read_text(
                encoding="utf-8"
            )
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        raise CampaignPreflightError(str(error)) from error
    active = supersession.get("active_seal", {})
    if (
        active.get("directory") != "validation_seal_v3"
        or active.get("status") != "active_model_not_run"
    ):
        raise CampaignPreflightError("historical validation seal is not active")
    env = dict(os.environ) if environ is None else dict(environ)
    if not env.get("DEEPSEEK_API_KEY"):
        raise CampaignPreflightError("DEEPSEEK_API_KEY is not configured")
    try:
        verify_contextual_bundle(seal_dir)
        manifest = ContextualManifest.model_validate_json(
            (seal_dir / "manifest.json").read_text(encoding="utf-8")
        )
        execution_inputs = json.loads(
            (seal_dir / "execution_inputs.json").read_text(encoding="utf-8")
        )
        plan = ContextualExecutionPlan(cases=tuple(execution_inputs))
        meta = json.loads((seal_dir / "seal_meta.json").read_text(encoding="utf-8"))
        checksums = json.loads(
            (seal_dir / "wav_checksums.json").read_text(encoding="utf-8")
        )
        slot_plan = json.loads(
            (seal_dir / "slot_plan.json").read_text(encoding="utf-8")
        )
        ledger = json.loads(
            (study_dir / "execution_ledger.json").read_text(encoding="utf-8")
        )
        targets = json.loads(
            (study_dir.parent / "acceptance_targets.json").read_text(
                encoding="utf-8"
            )
        )
        runtime_identity = ContextualRuntimeIdentity.model_validate_json(
            (seal_dir / "runtime_identity.json").read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        raise CampaignPreflightError(str(error)) from error

    if len(plan.cases) != 20 or len(plan.slots) != 60:
        raise CampaignPreflightError("validation requires exactly 20 cases / 60 slots")
    manifest_ids = tuple(case.case_id for case in manifest.cases)
    input_ids = tuple(case.case_id for case in plan.cases)
    planned_ids = tuple(item["case_id"] for item in slot_plan)
    if input_ids != manifest_ids or planned_ids != manifest_ids:
        raise CampaignPreflightError("sealed case order mismatch")
    if meta.get("manifest_sha256") != manifest_sha256(manifest):
        raise CampaignPreflightError("sealed manifest identity mismatch")
    frozen = targets["frozen_identity"]
    seal_index_sha256 = sha256((seal_dir / "seal.sha256").read_bytes()).hexdigest()
    if (
        active.get("directory") != "validation_seal_v3"
        or active.get("status") != "active_model_not_run"
        or active.get("seal_id_sha256") != seal_index_sha256
    ):
        raise CampaignPreflightError("active seal supersession identity mismatch")
    expected_meta = {
        "product_code_sha256": frozen["implementation_sha256"],
        "prompt_sha256": frozen["prompt_sha256"],
        "profile_s1_sha256": frozen["profile_s1_distortion"]["sha256"],
        "profile_contextual_sha256": frozen[
            "profile_s1_contextual_comparison"
        ]["sha256"],
        "scoring_identity": frozen["scoring_identity"],
    }
    for field, expected in expected_meta.items():
        if meta.get(field) != expected:
            raise CampaignPreflightError(f"frozen identity mismatch: {field}")
    if meta.get("evaluation_harness_sha256") != contextual_implementation_sha256():
        raise CampaignPreflightError("active evaluation harness identity mismatch")
    prompt_sha256 = sha256(
        _S1_PROMPT_V9_9.system_prompt.encode("utf-8")
    ).hexdigest()
    profile_root = Path(str(files("signal_diag").joinpath("rules", "profiles")))
    live_identity = ContextualRuntimeIdentity(
        provider="deepseek",
        model=str(frozen["model"]),
        base_url="https://api.deepseek.com",
        planner_class="RealLLMPlanner",
        prompt_version=_S1_PROMPT_V9_9.version,
        prompt_sha256=prompt_sha256,
        causal_policy_version="v9_9_paired_reference_recovery",
        product_tree_sha256=contextual_product_tree_sha256(),
    )
    if runtime_identity != live_identity:
        raise CampaignPreflightError("sealed runtime identity does not match live product")
    if (
        runtime_identity.provider != frozen["provider"]
        or runtime_identity.model != frozen["model"]
        or runtime_identity.planner_class != frozen["planner_class"]
        or runtime_identity.prompt_version != frozen["prompt_version"]
        or runtime_identity.prompt_sha256 != frozen["prompt_sha256"]
        or runtime_identity.causal_policy_version != frozen["causal_policy_version"]
        or sha256((profile_root / "s1_distortion_v1.yaml").read_bytes()).hexdigest()
        != frozen["profile_s1_distortion"]["sha256"]
        or sha256(
            (profile_root / "s1_contextual_comparison_v1.yaml").read_bytes()
        ).hexdigest()
        != frozen["profile_s1_contextual_comparison"]["sha256"]
        or f"{CONTEXTUAL_SCORING_ID}@{CONTEXTUAL_SCORING_VERSION}"
        != frozen["scoring_identity"]
    ):
        raise CampaignPreflightError("frozen product identity does not match live files")
    counters = meta.get("execution_counters", {})
    if counters != {
        "completed_cases": 0,
        "executed_arms": 0,
        "planned_arms": 60,
        "planned_cases": 20,
    }:
        raise CampaignPreflightError("active seal is not zero-execution")
    if any(item.get("attempts") != 0 for item in ledger.get("arms", {}).values()):
        raise CampaignPreflightError("source execution ledger is not zero-execution")

    manifest_by_id = {case.case_id: case for case in manifest.cases}
    for item in plan.cases:
        sealed_case = manifest_by_id[item.case_id]
        if item.mode != sealed_case.mode:
            raise CampaignPreflightError(f"mode mismatch: {item.case_id}")
        for kind, relative, expected in (
            ("test", item.test_wav_path, sealed_case.test_wav_sha256),
            ("ref", item.reference_wav_path, sealed_case.reference_wav_sha256),
        ):
            if relative is None:
                continue
            path = _resolve_input(study_dir.resolve(), relative)
            actual = sha256(path.read_bytes()).hexdigest()
            if checksums.get(f"{kind}:{item.case_id}") != expected or actual != expected:
                raise CampaignPreflightError(f"WAV identity mismatch: {item.case_id}")
    record = {
        "status": "preflight_passed_model_not_run",
        "seal": seal_dir.name,
        "case_count": len(plan.cases),
        "slot_count": len(plan.slots),
        "prompt_sha256": meta["prompt_sha256"],
        "evaluation_harness_sha256": meta.get("evaluation_harness_sha256"),
        "seal_index_sha256": seal_index_sha256,
        "runtime_identity": runtime_identity.model_dump(mode="json"),
        "credential_present": True,
        "credential_persisted": False,
    }
    return CampaignPreflight(
        plan=plan,
        runtime_identity=runtime_identity,
        record=record,
    )


class CampaignPreflight(BaseModel):
    """Truth-free execution plan and sanitized preflight evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: ContextualExecutionPlan
    runtime_identity: ContextualRuntimeIdentity
    record: dict[str, Any]


class CampaignSlotArtifacts(BaseModel):
    """Sanitized terminal artifacts returned by one slot executor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    arm_result: ArmResult
    attempts: dict[str, Any]
    trace: dict[str, Any]
    result: dict[str, Any]
    summary: dict[str, Any]


def _model_json(value: object) -> Any:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    if isinstance(value, tuple | list):
        return [_model_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _model_json(item) for key, item in value.items()}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _resolve_input(study_dir: Path, relative_path: str | None) -> Path:
    if relative_path is None:
        raise ValueError("missing required WAV path")
    candidate = (study_dir / relative_path).resolve()
    if candidate == study_dir or study_dir not in candidate.parents:
        raise ValueError("WAV path escapes the study directory")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _arm_result_from_result(
    slot: ContextualExecutionSlot,
    result: object,
) -> ArmResult:
    diagnosis = getattr(result, "diagnosis", None)
    claims = diagnosis.claims if diagnosis is not None else ()
    evidence_ids = {item.evidence_id for item in getattr(result, "evidence", ())}
    rule_ids = {
        evaluation.evaluation_id
        for batch in getattr(result, "rule_evaluation_batches", ())
        for evaluation in batch.evaluations
    }
    refs_complete = bool(claims) and all(
        bool(claim.evidence_refs)
        and set(claim.evidence_refs) <= evidence_ids
        and set(claim.rule_refs) <= rule_ids
        for claim in claims
    )
    causal = tuple(
        cast(CausalFault, fault)
        for fault in ("clipping", "harmonic_distortion")
        if any(claim.fault_type == fault for claim in claims)
    )
    tools = [item.tool_name for item in getattr(result, "tool_history", ())]
    disallowed = (
        "analyze_contextual_distortion"
        if slot.mode == "single_signal"
        else "analyze_harmonic_distortion"
    )
    return ArmResult(
        case_id=slot.case_id,
        arm=slot.arm,
        status="ok",
        predicted_outcome=diagnosis.outcome if diagnosis is not None else None,
        predicted_causal_set=causal,
        evidence_refs_complete=refs_complete,
        unnecessary_tool=disallowed in tools or len(tools) != len(set(tools)),
    )


def artifacts_from_agent_snapshot(
    slot: ContextualExecutionSlot,
    snapshot: object,
    *,
    failure_diagnostic: dict[str, str | int | None] | None = None,
) -> CampaignSlotArtifacts:
    snapshot_status = getattr(snapshot, "status", None)
    result = getattr(snapshot, "result", None)
    application_error = getattr(snapshot, "application_error", None)
    if snapshot_status != "completed" or result is None:
        arm_result = ArmResult(
            case_id=slot.case_id,
            arm=slot.arm,
            status="infrastructure_failure",
            infrastructure_failure=True,
        )
        result_payload: dict[str, Any] = {
            "status": "infrastructure_failure",
            "application_error": _model_json(application_error),
        }
        if failure_diagnostic is not None:
            result_payload["failure_diagnostic"] = dict(failure_diagnostic)
    else:
        arm_result = _arm_result_from_result(slot, result)
        result_payload = _model_json(result)
    trace_events = getattr(snapshot, "trace_events", ())
    summary = {
        "case_id": slot.case_id,
        "arm": slot.arm,
        "mode": slot.mode,
        "arm_result": arm_result.model_dump(mode="json"),
    }
    return CampaignSlotArtifacts(
        arm_result=arm_result,
        attempts={
            "attempt_count": 1,
            "provider_attempts": 1,
            **(
                {"failure_diagnostic": dict(failure_diagnostic)}
                if failure_diagnostic is not None
                else {}
            ),
        },
        trace={"events": _model_json(trace_events)},
        result=result_payload,
        summary=summary,
    )


class CampaignRunState(BaseModel):
    """Terminal state of one campaign invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["execution_complete_unscored", "infrastructure_stopped"]
    terminal_slots: int
    planned_slots: int
    stopped_after: str | None = None


def _metric_value(value: object) -> float | None:
    return None if isinstance(value, str) else float(cast(Any, value).value)


def score_completed_campaign(
    *,
    manifest: ContextualManifest,
    results: list[ArmResult],
    acceptance_targets: dict[str, Any],
) -> dict[str, Any]:
    """Apply frozen scoring only after all three arms have terminal results."""

    expected_keys = {
        (arm, case.case_id)
        for arm in ("contextual_agent", "fixed_pipeline", "no_context_ablation")
        for case in manifest.cases
    }
    actual_keys = {(item.arm, item.case_id) for item in results}
    if len(results) != 60 or actual_keys != expected_keys:
        raise ValueError("completed campaign scoring requires exactly 60 unique slots")
    agent = [item for item in results if item.arm == "contextual_agent"]
    fixed = [item for item in results if item.arm == "fixed_pipeline"]
    ablation = [item for item in results if item.arm == "no_context_ablation"]
    agent_score = score_contextual_run(
        manifest,
        agent,
        arm="contextual_agent",
        ablation_results=ablation,
    )
    fixed_score = score_contextual_run(manifest, fixed, arm="fixed_pipeline")
    ablation_score = score_contextual_run(
        manifest, ablation, arm="no_context_ablation"
    )
    aggregate = agent_score.aggregate
    metrics = acceptance_targets["metrics"]
    planner_numerator = sum(
        item.status == "ok"
        and not item.infrastructure_failure
        and item.predicted_outcome is not None
        for item in agent
    )
    precision_h = _metric_value(aggregate.harmonic_precision)
    recall_h = _metric_value(aggregate.harmonic_recall)
    precision_c = _metric_value(aggregate.clipping_precision)
    recall_c = _metric_value(aggregate.clipping_recall)
    f1_h = (
        0.0
        if precision_h is None or recall_h is None or precision_h + recall_h == 0
        else 2 * precision_h * recall_h / (precision_h + recall_h)
    )
    f1_c = (
        0.0
        if precision_c is None or recall_c is None or precision_c + recall_c == 0
        else 2 * precision_c * recall_c / (precision_c + recall_c)
    )
    macro_f1 = (f1_h + f1_c) / 2
    gates = {
        "planner_completion": planner_numerator / 20
        >= metrics["planner_completion"]["threshold"],
        "outcome_accuracy": aggregate.outcome_accuracy.value
        >= metrics["outcome_accuracy"]["threshold"],
        "causal_exact_set_accuracy": aggregate.causal_exact_set_accuracy.value
        >= metrics["causal_exact_set_accuracy"]["threshold"],
        "causal_macro_f1": macro_f1 >= metrics["causal_macro_f1"]["threshold"],
        "harmonic_precision": precision_h is not None
        and precision_h >= metrics["harmonic_precision"]["threshold"],
        "harmonic_recall": recall_h is not None
        and recall_h >= metrics["harmonic_recall"]["threshold"],
        "clipping_precision": precision_c is not None
        and precision_c >= metrics["clipping_precision"]["threshold"],
        "clipping_recall": recall_c is not None
        and recall_c >= metrics["clipping_recall"]["threshold"],
        "evidence_grounding": aggregate.evidence_grounding.value == 1.0,
        "unsupported_claim_rate": aggregate.unsupported_claim_rate.value == 0.0,
        "natural_even_harmonic_false_positives": (
            aggregate.natural_even_harmonic_fp == 0
        ),
        "inconclusive_appropriateness": (
            aggregate.inconclusive_appropriateness.numerator
            >= metrics["inconclusive_appropriateness"]["min_numerator"]
        ),
        "unnecessary_tool_action_rate": aggregate.unnecessary_tool_rate.value
        <= metrics["unnecessary_tool_action_rate"]["threshold"],
        "paired_harmonic_ablation_delta": (
            aggregate.ablation_correct_delta is not None
            and aggregate.ablation_correct_delta
            >= metrics["paired_harmonic_ablation_delta"]["min_correct_delta"]
        ),
    }
    agent_by_id = {item.case_id: item for item in agent}
    cases_by_role: dict[str, list[Any]] = {}
    for case in manifest.cases:
        cases_by_role.setdefault(case.role, []).append(case)

    def exact(case: Any) -> bool:
        result = agent_by_id[case.case_id]
        return (
            result.status == "ok"
            and not result.infrastructure_failure
            and frozenset(result.predicted_causal_set)
            == frozenset(case.expected_causal_set)
        )

    no_fault = cases_by_role["clean"] + cases_by_role["natural_even_control"]
    natural = cases_by_role["natural_even_control"]
    inconclusive = (
        cases_by_role["controlled_inconclusive"]
        + cases_by_role["domain_out_inconclusive"]
    )
    role_gates = {
        "no_supported_fault_controls": sum(
            agent_by_id[case.case_id].predicted_outcome == "no_supported_fault"
            for case in no_fault
        )
        >= 4,
        "clipping_only": sum(exact(case) for case in cases_by_role["clipping"])
        >= 3,
        "harmonic_only": sum(exact(case) for case in cases_by_role["harmonic"])
        >= 2,
        "combined": sum(exact(case) for case in cases_by_role["combined"]) >= 2,
        "natural_even_controls": all(
            agent_by_id[case.case_id].predicted_outcome == "no_supported_fault"
            and "harmonic_distortion"
            not in agent_by_id[case.case_id].predicted_causal_set
            for case in natural
        ),
        "inconclusive": sum(
            agent_by_id[case.case_id].predicted_outcome == "inconclusive"
            for case in inconclusive
        )
        >= 5,
        "paired_harmonic_ablation": gates["paired_harmonic_ablation_delta"],
    }
    meets = all(gates.values()) and all(role_gates.values())
    return {
        "target_status": "meets_target" if meets else "below_target",
        "planner_completion": {"numerator": planner_numerator, "denominator": 20},
        "causal_macro_f1": macro_f1,
        "gates": gates,
        "role_hard_gates": role_gates,
        "scores": {
            "contextual_agent": agent_score.model_dump(mode="json"),
            "fixed_pipeline": fixed_score.model_dump(mode="json"),
            "no_context_ablation": ablation_score.model_dump(mode="json"),
        },
    }


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_new_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_json_bytes(value))


def _replace_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise FileExistsError(f"stale campaign temporary file: {temporary}")
    with temporary.open("xb") as stream:
        stream.write(_json_bytes(value))
    temporary.replace(path)


def finalize_campaign_output(
    *,
    seal_dir: Path,
    output: Path,
    acceptance_targets_path: Path,
) -> dict[str, Any]:
    """Read truth and score only after all 60 execution slots are terminal."""

    ledger = json.loads((output / "execution_ledger.json").read_text(encoding="utf-8"))
    if ledger.get("status") != "execution_complete_unscored":
        raise ValueError("incomplete campaign cannot be scored")
    manifest = ContextualManifest.model_validate_json(
        (seal_dir / "manifest.json").read_text(encoding="utf-8")
    )
    results: list[ArmResult] = []
    for arm in ("contextual_agent", "fixed_pipeline", "no_context_ablation"):
        for case in manifest.cases:
            summary = json.loads(
                (
                    output
                    / "arms"
                    / arm
                    / case.case_id
                    / "case_summary.json"
                ).read_text(encoding="utf-8")
            )
            results.append(ArmResult.model_validate(summary["arm_result"]))
    targets = json.loads(acceptance_targets_path.read_text(encoding="utf-8"))
    report = score_completed_campaign(
        manifest=manifest,
        results=results,
        acceptance_targets=targets,
    )
    _write_new_json(output / "metrics.json", report)
    _write_new_json(
        output / "run_summary.json",
        {
            "status": "campaign_scored",
            "target_status": report["target_status"],
            "planned_slots": 60,
            "executed_slots": 60,
            "arm_order": [
                "contextual_agent",
                "fixed_pipeline",
                "no_context_ablation",
            ],
            "metrics": report,
        },
    )
    _write_new_json(
        output / "audit_report.json",
        {
            "status": "campaign_scored",
            "target_status": report["target_status"],
            "executed_slots": 60,
            "raw_wav_persisted": False,
            "truth_loaded_after_execution": True,
        },
    )
    status_path = output / "STATUS.md"
    status_text = (
        "# Contextual validation campaign\n\n"
        f"Target status: `{report['target_status']}`\n\n"
        "All 60 slots completed once in frozen arm-major order.\n"
    )
    with status_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(status_text)
    return report


async def run_contextual_validation_campaign(
    *,
    plan: ContextualExecutionPlan,
    output: Path,
    executors: Mapping[ArmKind, SlotExecutor],
    preflight_record: dict[str, Any],
) -> CampaignRunState:
    """Execute an already-preflighted plan once in frozen arm-major order."""

    if output.exists():
        raise FileExistsError(f"campaign output already exists: {output}")
    missing = [arm for arm in plan.arm_order if arm not in executors]
    if missing:
        raise ValueError(f"missing executor for arm: {missing[0]}")
    output.mkdir(parents=True)
    _write_new_json(output / "preflight.json", preflight_record)
    seal_identity = {
        key: preflight_record[key]
        for key in (
            "seal",
            "seal_index_sha256",
            "prompt_sha256",
            "evaluation_harness_sha256",
            "runtime_identity",
        )
        if key in preflight_record
    }
    _write_new_json(output / "seal_identity.json", seal_identity)
    ledger_path = output / "execution_ledger.json"
    ledger: dict[str, Any] = {
        "status": "running",
        "planned_slots": len(plan.slots),
        "terminal_slots": 0,
        "started_slots": [],
        "terminal_slot_ids": [],
    }
    _write_new_json(ledger_path, ledger)

    stopped_after: str | None = None
    for slot in plan.slots:
        slot_id = f"{slot.arm}:{slot.case_id}"
        ledger["started_slots"].append(slot_id)
        _replace_json(ledger_path, ledger)
        try:
            artifacts = await executors[slot.arm](slot)
        except Exception:  # noqa: BLE001 - fail closed without persisting exception text
            infra_result = ArmResult(
                case_id=slot.case_id,
                arm=slot.arm,
                status="infrastructure_failure",
                infrastructure_failure=True,
            )
            artifacts = CampaignSlotArtifacts(
                arm_result=infra_result,
                attempts={"attempt_count": 1},
                trace={"events": []},
                result={
                    "status": "infrastructure_failure",
                    "application_error": {"code": "internal_error"},
                },
                summary={
                    "case_id": slot.case_id,
                    "arm": slot.arm,
                    "mode": slot.mode,
                    "arm_result": infra_result.model_dump(mode="json"),
                },
            )
        if artifacts.arm_result.case_id != slot.case_id:
            raise ValueError("executor result case_id does not match slot")
        if artifacts.arm_result.arm != slot.arm:
            raise ValueError("executor result arm does not match slot")
        case_dir = output / "arms" / slot.arm / slot.case_id
        _write_new_json(case_dir / "attempts.json", artifacts.attempts)
        _write_new_json(case_dir / "trace.json", artifacts.trace)
        _write_new_json(case_dir / "result.json", artifacts.result)
        _write_new_json(case_dir / "case_summary.json", artifacts.summary)
        ledger["terminal_slots"] += 1
        ledger["terminal_slot_ids"].append(slot_id)
        if artifacts.arm_result.infrastructure_failure:
            stopped_after = slot_id
            ledger["status"] = "infrastructure_stopped"
            ledger["stopped_after"] = slot_id
            _replace_json(ledger_path, ledger)
            break
        _replace_json(ledger_path, ledger)

    if stopped_after is None:
        ledger["status"] = "execution_complete_unscored"
        _replace_json(ledger_path, ledger)
    return CampaignRunState(
        status=ledger["status"],
        terminal_slots=ledger["terminal_slots"],
        planned_slots=ledger["planned_slots"],
        stopped_after=stopped_after,
    )
