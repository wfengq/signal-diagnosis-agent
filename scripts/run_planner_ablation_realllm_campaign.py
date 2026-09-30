#!/usr/bin/env python3
"""Wave 4: run the sealed planner-ablation RealLLM campaign once (arm-major).

Requires DEEPSEEK_API_KEY. Never falls back to ScriptedPlanner.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any

from signal_diag.app.composition import build_product_service
from signal_diag.app.planner_ablation_adapter import AppProductSlotExecutor
from signal_diag.evaluation.planner_ablation.baseline import (
    PlannerAblationFixedPipelineBaseline,
)
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
)
from signal_diag.evaluation.planner_ablation.models import (
    FixedPipelineOutcome,
    PlannerAblationBaselineRequest,
    ProductSlotRequest,
)
from signal_diag.evaluation.planner_ablation.report_fields import (
    derive_context_guidance_from_baseline,
)
from signal_diag.evaluation.planner_ablation.sealing import verify_planner_ablation_bundle
from signal_diag.evaluation.planner_ablation.study_score import (
    build_study_comparison_metrics,
    project_fixed_outcome,
    project_product_outcome,
    score_planner_ablation_study,
    study_input_from_verified_manifest,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.wav import load_wav_bytes
from signal_diag.tools.service import SignalToolService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STUDY_ROOT = (
    PROJECT_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1"
)
SEAL_DIR = STUDY_ROOT / "protocol_seal"
USER_REQUEST = "Diagnose supported S1 distortion conservatively."


class CampaignPreflightError(RuntimeError):
    """Unsafe to start the RealLLM campaign."""


class CampaignInfrastructureError(RuntimeError):
    """Infrastructure failure; sealed stop rule requires campaign halt."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _jsonable(value: object) -> object:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _profiles() -> YamlRuleProfileLoader:
    package = files("signal_diag")
    profiles = Path(str(package.joinpath("rules", "profiles")))
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": profiles / "s1_distortion_v1.yaml",
            "profile_s1_contextual_comparison_v9_10": (
                profiles / "s1_contextual_comparison_v9_10.yaml"
            ),
        }
    )


def preflight(*, seal_dir: Path = SEAL_DIR) -> dict[str, Any]:
    verify_planner_ablation_bundle(seal_dir)
    manifest = json.loads((seal_dir / "manifest.json").read_text(encoding="utf-8"))
    study = study_input_from_verified_manifest(manifest)
    if study.protocol.study_id != PLANNER_ABLATION_STUDY_ID:
        raise CampaignPreflightError("foreign study identity in sealed protocol")
    if study.protocol.scoring_identity != PLANNER_ABLATION_SCORING_IDENTITY:
        raise CampaignPreflightError("foreign scoring identity in sealed protocol")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise CampaignPreflightError(
            "DEEPSEEK_API_KEY is missing; RealLLM campaign refuses to start and "
            "does not fall back to ScriptedPlanner"
        )

    service = build_product_service()
    try:
        if not service._dependencies.planner_configured:
            raise CampaignPreflightError("product service reports planner_configured=False")
        planner = service._dependencies.planner_factory()
        planner_class = type(planner).__name__
        if planner_class != "RealLLMPlanner":
            raise CampaignPreflightError(
                f"planner factory returned {planner_class}, expected RealLLMPlanner"
            )
    finally:
        # sync close path may not exist; best-effort
        close = getattr(service, "aclose", None)
        if close is not None:
            pass

    return {
        "status": "preflight_ok",
        "checked_at": _utc_now(),
        "study_id": study.protocol.study_id,
        "scoring_identity": study.protocol.scoring_identity,
        "schedule_keys": len(study.schedule),
        "oracle_rows": len(study.oracle),
        "scorable_slot_count": manifest.get("scorable_slot_count"),
        "planner_class": "RealLLMPlanner",
        "deepseek_model": os.environ.get("DEEPSEEK_MODEL") or "deepseek-v4-flash",
        "deepseek_base_url_set": bool(os.environ.get("DEEPSEEK_BASE_URL")),
        "scripted_fallback": False,
    }


def _case_source_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = manifest.get("case_sources", [])
    if not isinstance(rows, list):
        raise CampaignPreflightError("sealed manifest missing case_sources")
    return {str(row["case_id"]): row for row in rows}


def _read_wav(relpath: str, expected_sha: str) -> bytes:
    path = PROJECT_ROOT / relpath
    payload = path.read_bytes()
    digest = sha256(payload).hexdigest()
    if digest != expected_sha:
        raise CampaignPreflightError(f"wav digest mismatch for {relpath}")
    return payload


async def _run_product_arm(
    *,
    executor: AppProductSlotExecutor,
    study_schedule: list[Any],
    sources: dict[str, dict[str, Any]],
    out_dir: Path,
    ledger: dict[str, Any],
    ledger_path: Path,
) -> tuple[list[dict[str, object]], list[float]]:
    slots: list[dict[str, object]] = []
    latencies: list[float] = []
    for index, key in enumerate(study_schedule):
        slot_id = f"product_agent:{key.case_id}/{key.mode}"
        ledger["started_slots"].append(slot_id)
        _write_json(ledger_path, ledger)
        source = sources[key.case_id]
        test_bytes = _read_wav(
            str(source["test_wav_relpath"]), str(source["test_wav_sha256"])
        )
        reference_bytes = None
        if key.mode == "paired_reference":
            reference_bytes = _read_wav(
                str(source["reference_wav_relpath"]),
                str(source["reference_wav_sha256"]),
            )
        request = ProductSlotRequest(
            case_id=key.case_id,
            test_wav_bytes=test_bytes,
            test_filename=Path(str(source["test_wav_relpath"])).name,
            mode=key.mode,
            reference_wav_bytes=reference_bytes,
            reference_filename=(
                Path(str(source["reference_wav_relpath"])).name
                if reference_bytes is not None
                else None
            ),
            user_request=USER_REQUEST,
        )
        started = time.perf_counter()
        try:
            outcome = await executor.execute_product_slot(request)
        except Exception as exc:  # noqa: BLE001 - sealed infra stop boundary
            elapsed = time.perf_counter() - started
            error = f"{type(exc).__name__}: {exc}"
            record = {
                "slot_index": index,
                "case_id": key.case_id,
                "mode": key.mode,
                "latency_s": elapsed,
                "infrastructure_failure": True,
                "raw": {"error": error},
            }
            _write_json(out_dir / f"{index:02d}_{key.case_id}_{key.mode}.json", record)
            ledger["status"] = "infrastructure_stopped"
            ledger["stopped_after"] = slot_id
            ledger["terminal_slots"] = len(ledger["terminal_slot_ids"]) + 1
            ledger["terminal_slot_ids"].append(slot_id)
            _write_json(ledger_path, ledger)
            raise CampaignInfrastructureError(
                f"product_agent infrastructure failure at {slot_id}: {error}"
            ) from exc
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        if outcome.planner_class != "RealLLMPlanner":
            raise CampaignPreflightError(
                "product slot executed without RealLLMPlanner provenance: "
                f"{outcome.planner_class}"
            )
        if outcome.execution_identity != "product_campaign":
            raise CampaignPreflightError(
                "product slot execution_identity is not product_campaign"
            )
        projected = project_product_outcome(outcome, case_id=key.case_id)
        # Behavioral failed terminals still occupy denominators (seal stop_rules).
        projected["terminal_reached"] = True
        projected["infrastructure_failure"] = False
        record = {
            "slot_index": index,
            "case_id": key.case_id,
            "mode": key.mode,
            "latency_s": elapsed,
            "infrastructure_failure": False,
            "terminal_status": outcome.terminal_status,
            "projected": {
                k: v
                for k, v in projected.items()
                if k not in {"evidence", "rule_evaluation_batches", "claims"}
            },
            "claims": projected.get("claims"),
            "raw": outcome.model_dump(mode="json"),
        }
        _write_json(out_dir / f"{index:02d}_{key.case_id}_{key.mode}.json", record)
        slots.append(projected)
        ledger["terminal_slot_ids"].append(slot_id)
        ledger["terminal_slots"] = len(ledger["terminal_slot_ids"])
        _write_json(ledger_path, ledger)
    return slots, latencies


async def _run_fixed_arm(
    *,
    study_schedule: list[Any],
    sources: dict[str, dict[str, Any]],
    out_dir: Path,
    ledger: dict[str, Any],
    ledger_path: Path,
) -> tuple[list[dict[str, object]], list[float]]:
    slots: list[dict[str, object]] = []
    latencies: list[float] = []
    for index, key in enumerate(study_schedule):
        slot_id = f"fixed_pipeline:{key.case_id}/{key.mode}"
        ledger["started_slots"].append(slot_id)
        _write_json(ledger_path, ledger)
        source = sources[key.case_id]
        repository = InMemorySignalRepository()
        test_path = PROJECT_ROOT / str(source["test_wav_relpath"])
        test_record = load_wav_bytes(
            test_path.read_bytes(), filename=test_path.name
        ).record
        repository.put(test_record)
        reference_id = None
        if key.mode == "paired_reference":
            ref_path = PROJECT_ROOT / str(source["reference_wav_relpath"])
            ref_record = load_wav_bytes(
                ref_path.read_bytes(), filename=ref_path.name
            ).record
            repository.put(ref_record)
            reference_id = ref_record.meta.signal_id
        baseline = PlannerAblationFixedPipelineBaseline(
            repository=repository,
            tool_service=SignalToolService(repository),
            rule_engine=RuleEngine(),
            profile_loader=_profiles(),
        )
        request = PlannerAblationBaselineRequest(
            case_id=key.case_id,
            signal_id=test_record.meta.signal_id,
            stimulus_context=StimulusContext(
                mode=key.mode,
                test_signal_id=test_record.meta.signal_id,
                reference_signal_id=reference_id,
                assertion_source="evaluation_manifest",
            ),
        )
        started = time.perf_counter()
        try:
            result = await baseline.run(request)
        except Exception as exc:  # noqa: BLE001 - sealed infra stop boundary
            elapsed = time.perf_counter() - started
            error = f"{type(exc).__name__}: {exc}"
            record = {
                "slot_index": index,
                "case_id": key.case_id,
                "mode": key.mode,
                "latency_s": elapsed,
                "infrastructure_failure": True,
                "raw": {"error": error},
            }
            _write_json(out_dir / f"{index:02d}_{key.case_id}_{key.mode}.json", record)
            ledger["status"] = "infrastructure_stopped"
            ledger["stopped_after"] = slot_id
            ledger["terminal_slots"] = len(ledger["terminal_slot_ids"]) + 1
            ledger["terminal_slot_ids"].append(slot_id)
            _write_json(ledger_path, ledger)
            raise CampaignInfrastructureError(
                f"fixed_pipeline infrastructure failure at {slot_id}: {error}"
            ) from exc
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        guidance = derive_context_guidance_from_baseline(mode=key.mode, baseline=result)
        outcome = FixedPipelineOutcome(
            case_id=key.case_id,
            mode=key.mode,
            baseline_result=result,
            context_guidance=guidance,
        )
        projected = project_fixed_outcome(outcome)
        projected["terminal_reached"] = True
        projected["infrastructure_failure"] = False
        record = {
            "slot_index": index,
            "case_id": key.case_id,
            "mode": key.mode,
            "latency_s": elapsed,
            "infrastructure_failure": False,
            "projected": {
                k: v
                for k, v in projected.items()
                if k not in {"evidence", "rule_evaluation_batches", "claims"}
            },
            "claims": projected.get("claims"),
            "raw": outcome.model_dump(mode="json"),
        }
        _write_json(out_dir / f"{index:02d}_{key.case_id}_{key.mode}.json", record)
        slots.append(projected)
        ledger["terminal_slot_ids"].append(slot_id)
        ledger["terminal_slots"] = len(ledger["terminal_slot_ids"])
        _write_json(ledger_path, ledger)
    return slots, latencies


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


async def run_campaign(*, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"campaign output already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    preflight_info = preflight()
    _write_json(output_dir / "preflight.json", preflight_info)

    manifest = json.loads((SEAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    study = study_input_from_verified_manifest(manifest)
    sources = _case_source_map(manifest)
    schedule = list(study.schedule)
    planned_slots = len(schedule) * 2
    ledger_path = output_dir / "execution_ledger.json"
    ledger: dict[str, Any] = {
        "status": "running",
        "arm_order": ["product_agent", "fixed_pipeline"],
        "planned_slots": planned_slots,
        "terminal_slots": 0,
        "started_slots": [],
        "terminal_slot_ids": [],
        "scripted_fallback": False,
        "campaign_retry": "forbidden",
    }
    _write_json(ledger_path, ledger)

    service = build_product_service()
    executor = AppProductSlotExecutor(service)
    try:
        product_dir = output_dir / "product_slots"
        fixed_dir = output_dir / "fixed_slots"
        product_slots, product_latency = await _run_product_arm(
            executor=executor,
            study_schedule=schedule,
            sources=sources,
            out_dir=product_dir,
            ledger=ledger,
            ledger_path=ledger_path,
        )
        fixed_slots, fixed_latency = await _run_fixed_arm(
            study_schedule=schedule,
            sources=sources,
            out_dir=fixed_dir,
            ledger=ledger,
            ledger_path=ledger_path,
        )
    except CampaignInfrastructureError as exc:
        summary = {
            "status": "infrastructure_stopped",
            "stopped_at": _utc_now(),
            "study_id": PLANNER_ABLATION_STUDY_ID,
            "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
            "error": str(exc),
            "scripted_fallback": False,
            "study_conclusion": None,
            "scored": False,
        }
        _write_json(output_dir / "run_summary.json", summary)
        raise
    finally:
        await service.aclose()

    product_mean = _mean(product_latency)
    fixed_mean = _mean(fixed_latency)
    latency_improvement = (
        0.0 if product_mean <= 0.0 else max(0.0, (product_mean - fixed_mean) / product_mean)
    )

    built = build_study_comparison_metrics(
        study=study,
        product_slots=product_slots,
        fixed_slots=fixed_slots,
        fixed_latency_improvement_ratio=latency_improvement,
    )
    conclusion = score_planner_ablation_study(
        study=study,
        product_slots=product_slots,
        fixed_slots=fixed_slots,
        fixed_latency_improvement_ratio=latency_improvement,
    )
    ledger["status"] = "completed"
    _write_json(ledger_path, ledger)
    metrics_payload = built.metrics.model_dump(mode="json")
    summary = {
        "status": "completed",
        "completed_at": _utc_now(),
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "arm_order": ["product_agent", "fixed_pipeline"],
        "product_slots": len(product_slots),
        "fixed_slots": len(fixed_slots),
        "product_mean_latency_s": product_mean,
        "fixed_mean_latency_s": fixed_mean,
        "fixed_latency_improvement_ratio": latency_improvement,
        "study_conclusion": conclusion.value,
        "metrics": metrics_payload,
        "scripted_fallback": False,
        "scored": True,
    }
    _write_json(output_dir / "run_summary.json", summary)
    _write_json(
        output_dir / "study_conclusion.json",
        {
            "study_conclusion": conclusion.value,
            "metrics": metrics_payload,
            "population_identity": built.population_identity,
            "fixed_latency_improvement_ratio": latency_improvement,
            "scored_at": _utc_now(),
        },
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="verify seal and credentials without executing slots",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STUDY_ROOT / "agent_realllm_campaign_1",
        help="additive campaign artifact directory",
    )
    args = parser.parse_args()
    try:
        if args.preflight_only:
            info = preflight()
            print(json.dumps(info, indent=2, sort_keys=True))
            return 0
        summary = asyncio.run(run_campaign(output_dir=args.output_dir.resolve()))
    except CampaignInfrastructureError as exc:
        print(json.dumps({"status": "infrastructure_stopped", "error": str(exc)}))
        return 2
    except CampaignPreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "error": str(exc)}))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
