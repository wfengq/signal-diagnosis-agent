"""One-shot post-run scorer for agent_campaign_1 (authorized real-model run)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from signal_diag.evaluation.external.manifest import load_external_manifest, manifest_sha256
from signal_diag.evaluation.external.models import (
    ExternalAttemptRecord,
    ExternalProvenanceRecord,
    ExternalProtectedAssetsAudit,
    ExternalStudyReport,
    ReferenceSummary,
    ReviewAgreement,
)
from signal_diag.evaluation.external.reporting import verify_external_bundle, write_external_bundle
from signal_diag.evaluation.external.runner import (
    _agent_config,
    _baseline_config,
    _execute_agent_slot,
    _execute_baseline_slot,
    _load_sealed_study,
    _reject_scripted_planner,
    _build_production_planner,
    _default_client_factory,
)
from signal_diag.evaluation.external.scoring import (
    aggregate_external_scores,
    evaluate_external_targets,
    score_external_trace,
)


def _study_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_attempts(path: Path) -> tuple[ExternalAttemptRecord, ...]:
    records: list[ExternalAttemptRecord] = []
    for file in sorted(path.glob("*.json")):
        records.append(
            ExternalAttemptRecord.model_validate_json(file.read_text(encoding="utf-8"))
        )
    return tuple(records)


def _load_reference_summaries(seal_dir: Path) -> dict[str, ReferenceSummary]:
    summaries: dict[str, ReferenceSummary] = {}
    for line in (seal_dir / "reference_summaries.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        summaries[payload["case_id"]] = ReferenceSummary.model_validate(payload["summary"])
    return summaries


def _load_review_agreement(seal_dir: Path) -> ReviewAgreement:
    return ReviewAgreement.model_validate_json(
        (seal_dir / "review_agreement.json").read_text(encoding="utf-8")
    )


def _build_provenance(
    cases: tuple[object, ...],
    reference_summaries: dict[str, ReferenceSummary],
) -> tuple[ExternalProvenanceRecord, ...]:
    records: list[ExternalProvenanceRecord] = []
    for case in cases:
        summary = reference_summaries[case.case_id]  # type: ignore[attr-defined]
        records.append(
            ExternalProvenanceRecord(
                case_id=case.case_id,  # type: ignore[attr-defined]
                provenance_ref=case.provenance_ref,  # type: ignore[attr-defined]
                source_recording_key=case.source_recording_key,  # type: ignore[attr-defined]
                capture_configuration_key=case.capture_configuration_key,  # type: ignore[attr-defined]
                original_sha256=summary.input_sha256,
                derived_sha256=case.wav_sha256,  # type: ignore[attr-defined]
                redistribution_permitted=case.source_group != "B",  # type: ignore[attr-defined]
            )
        )
    return tuple(records)


async def _recover_traces(
    cases: tuple[object, ...],
    asset_root: Path,
    manifest: object,
    *,
    started_at: datetime,
) -> tuple[list[object], list[object]]:
    agent_config = _agent_config(manifest, started_at_utc=started_at)  # type: ignore[arg-type]
    baseline_config = _baseline_config(manifest, started_at_utc=started_at)  # type: ignore[arg-type]
    agent_traces: list[object] = []
    baseline_traces: list[object] = []
    client = _default_client_factory()
    planner = _reject_scripted_planner(_build_production_planner(client))
    for run_slot, case in enumerate(cases, start=1):
        baseline_trace, _ = await _execute_baseline_slot(
            case,  # type: ignore[arg-type]
            asset_root,
            baseline_config,
            run_slot,
        )
        baseline_traces.append(baseline_trace)
        agent_trace, _ = await _execute_agent_slot(
            case,  # type: ignore[arg-type]
            asset_root,
            agent_config,
            run_slot,
            planner,
        )
        agent_traces.append(agent_trace)
    return agent_traces, baseline_traces


async def main() -> None:
    study = _study_root()
    seal_dir = study / "final_seal"
    asset_root = study
    agent_dir = study / "agent_campaign_1"
    baseline_dir = study / "baseline_runs"
    bundle_dir = study / "bundle_agent_campaign_1"

    metadata, manifest = _load_sealed_study(seal_dir)
    final_cases = tuple(case for case in manifest.cases if case.split == "final_external_test")
    if len(final_cases) != 28:
        raise ValueError(f"expected 28 final cases, got {len(final_cases)}")

    agent_attempts = _load_attempts(agent_dir / "attempts" / "agent")
    baseline_attempts = _load_attempts(baseline_dir / "attempts" / "fixed_pipeline")
    if len(agent_attempts) != 28 or len(baseline_attempts) != 28:
        raise ValueError("expected 28 agent and 28 baseline attempts")

    started_at = agent_attempts[0].started_at_utc
    agent_traces, baseline_traces = await _recover_traces(
        final_cases,
        asset_root,
        manifest,
        started_at=started_at,
    )

    traces_dir = agent_dir / "traces"
    traces_dir.mkdir(exist_ok=True)
    for trace in agent_traces:
        path = traces_dir / f"{trace.case_id}_agent.json"  # type: ignore[attr-defined]
        path.write_text(
            json.dumps(trace.model_dump(mode="json"), sort_keys=True) + "\n",  # type: ignore[attr-defined]
            encoding="utf-8",
        )
    baseline_traces_dir = baseline_dir / "traces"
    baseline_traces_dir.mkdir(exist_ok=True)
    for trace in baseline_traces:
        path = baseline_traces_dir / f"{trace.case_id}_fixed_pipeline.json"  # type: ignore[attr-defined]
        path.write_text(
            json.dumps(trace.model_dump(mode="json"), sort_keys=True) + "\n",  # type: ignore[attr-defined]
            encoding="utf-8",
        )

    agent_scores = tuple(
        score_external_trace(case, trace)  # type: ignore[arg-type]
        for case, trace in zip(final_cases, agent_traces, strict=True)
    )
    baseline_scores = tuple(
        score_external_trace(case, trace)  # type: ignore[arg-type]
        for case, trace in zip(final_cases, baseline_traces, strict=True)
    )
    all_scores = agent_scores + baseline_scores
    agent_aggregate = aggregate_external_scores(final_cases, agent_scores, ())
    aggregate = aggregate_external_scores(final_cases, all_scores, ())
    review_agreement = _load_review_agreement(seal_dir)
    reference_summaries = _load_reference_summaries(seal_dir)
    final_reference = {
        case.case_id: reference_summaries[case.case_id] for case in final_cases
    }
    target_status = evaluate_external_targets(agent_aggregate, review_agreement)
    harness_status = (
        "external_validation_completed"
        if target_status == "meets_target"
        else "external_validation_completed/below_target"
    )
    protected = ExternalProtectedAssetsAudit.model_validate_json(
        (seal_dir / "protected_assets.json").read_text(encoding="utf-8")
    )
    report = ExternalStudyReport(
        study_id=manifest.study_id,
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        seal_id=metadata.seal_id,
        harness_status=harness_status,
        target_status=target_status,
        manifest=manifest,
        manifest_sha256=manifest_sha256(manifest),
        provenance=_build_provenance(final_cases, reference_summaries),
        reference_summaries=final_reference,
        review_agreement=review_agreement,
        attempts=agent_attempts + baseline_attempts,
        scores=all_scores,
        traces=tuple(agent_traces) + tuple(baseline_traces),  # type: ignore[arg-type]
        aggregate=aggregate,
        protected_assets=protected,
    )

    summary = {
        "seal_id": metadata.seal_id,
        "manifest_sha256": metadata.manifest_sha256,
        "agent_attempts": len(agent_attempts),
        "baseline_attempts": len(baseline_attempts),
        "agent_behavior_results": sum(
            1 for item in agent_attempts if item.status == "behavior_result"
        ),
        "baseline_behavior_results": sum(
            1 for item in baseline_attempts if item.status == "behavior_result"
        ),
        "target_status": target_status,
        "harness_status": harness_status,
        "agent_outcome_accuracy": (
            None
            if agent_aggregate.outcome_accuracy is None
            else {
                "numerator": agent_aggregate.outcome_accuracy.numerator,
                "denominator": agent_aggregate.outcome_accuracy.denominator,
                "value": agent_aggregate.outcome_accuracy.value,
            }
        ),
        "baseline_outcome_accuracy": (
            None
            if aggregate_external_scores(final_cases, baseline_scores, ()).outcome_accuracy
            is None
            else {
                "numerator": aggregate_external_scores(
                    final_cases, baseline_scores, ()
                ).outcome_accuracy.numerator,  # type: ignore[union-attr]
                "denominator": aggregate_external_scores(
                    final_cases, baseline_scores, ()
                ).outcome_accuracy.denominator,  # type: ignore[union-attr]
                "value": aggregate_external_scores(
                    final_cases, baseline_scores, ()
                ).outcome_accuracy.value,  # type: ignore[union-attr]
            }
        ),
        "token_cost_captured": False,
        "bundle_dir": bundle_dir.as_posix(),
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
    }
    (agent_dir / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_external_bundle(report, bundle_dir)
    verify_external_bundle(bundle_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
