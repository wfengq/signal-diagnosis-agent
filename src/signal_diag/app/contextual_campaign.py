"""Product adapter and guarded CLI for contextual validation campaigns."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from signal_diag.agent.planner import (
    DEFAULT_DEEPSEEK_BASE_URL,
    RealLLMPlanner,
)
from signal_diag.app.composition import build_product_service
from signal_diag.app.service import DiagnosisApplicationService
from signal_diag.evaluation.contextual.campaign import (
    CampaignSlotArtifacts,
    FixedPipelineSlotExecutor,
    artifacts_from_agent_snapshot,
    finalize_campaign_output,
    preflight_contextual_validation,
    run_contextual_validation_campaign,
)
from signal_diag.evaluation.contextual.models import (
    ContextualExecutionSlot,
    ContextualRuntimeIdentity,
)


class RealAgentSlotExecutor:
    """Product-service-backed Agent executor; construction performs no model call."""

    def __init__(
        self,
        service: DiagnosisApplicationService,
        *,
        study_dir: Path,
        expected_identity: ContextualRuntimeIdentity,
    ) -> None:
        planner = service._dependencies.planner_factory()
        if not isinstance(planner, RealLLMPlanner):
            raise TypeError("contextual validation requires RealLLMPlanner")
        actual = {
            "provider": planner._provider,
            "model": planner.model_id,
            "base_url": planner._base_url or DEFAULT_DEEPSEEK_BASE_URL,
            "planner_class": type(planner).__name__,
            "prompt_version": planner.prompt_version,
            "causal_policy_version": service._dependencies.causal_policy_version,
        }
        expected = expected_identity.model_dump(mode="json", exclude={
            "prompt_sha256",
            "product_tree_sha256",
        })
        if actual != expected:
            raise ValueError("real executor runtime identity does not match active seal")
        self.service = service
        self.study_dir = study_dir.resolve()
        self.model = service._dependencies.planner_identity.model
        self.prompt_version = service._dependencies.planner_identity.prompt_version

    async def __call__(self, slot: ContextualExecutionSlot) -> CampaignSlotArtifacts:
        test_path = self._resolve_input(slot.test_wav_path)
        test_data = test_path.read_bytes()
        snapshot: object
        if slot.mode == "single_signal":
            submission = await self.service.submit_wav(
                test_data,
                filename=test_path.name,
                user_request="Diagnose supported S1 distortion conservatively.",
                channel="mixdown",
            )
            snapshot = await self.service.wait_for_terminal(submission.run_id)
        else:
            reference_path = (
                self._resolve_input(slot.reference_wav_path)
                if slot.reference_wav_path is not None
                else None
            )
            contextual_submission = await self.service.submit_contextual_wav(
                test_data,
                test_filename=test_path.name,
                mode=slot.mode,
                reference_data=(
                    reference_path.read_bytes() if reference_path is not None else None
                ),
                reference_filename=(
                    reference_path.name if reference_path is not None else None
                ),
                nominal_fundamental_hz=slot.nominal_fundamental_hz,
                stimulus_kind=slot.stimulus_kind,
                user_request="Diagnose supported S1 distortion conservatively.",
                channel="mixdown",
            )
            snapshot = await self.service.wait_for_contextual_terminal(
                contextual_submission.run_id
            )
        return artifacts_from_agent_snapshot(slot, snapshot)

    def _resolve_input(self, relative_path: str | None) -> Path:
        if relative_path is None:
            raise ValueError("missing required WAV path")
        candidate = (self.study_dir / relative_path).resolve()
        if candidate == self.study_dir or self.study_dir not in candidate.parents:
            raise ValueError("WAV path escapes the study directory")
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate


def build_real_agent_executor(
    *,
    study_dir: Path,
    expected_identity: ContextualRuntimeIdentity,
    environ: Mapping[str, str] | None = None,
) -> RealAgentSlotExecutor:
    """Build the real product executor without issuing a provider request."""

    env = dict(os.environ) if environ is None else dict(environ)
    return RealAgentSlotExecutor(
        build_product_service(environ=env),
        study_dir=study_dir,
        expected_identity=expected_identity,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m signal_diag.app.contextual_campaign",
        description="Guarded one-shot contextual validation campaign.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser(
        "preflight-validation", help="Verify the active seal without model calls"
    )
    run = sub.add_parser("run-validation", help="Run the authorized campaign once")
    for command in (preflight, run):
        command.add_argument("--study-dir", type=Path, required=True)
        command.add_argument("--seal", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    run.add_argument(
        "--authorization",
        choices=("authorized-structured-context-only",),
        required=True,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    preflight = preflight_contextual_validation(
        study_dir=args.study_dir,
        seal_dir=args.seal,
        output=args.output,
    )
    if args.command == "preflight-validation":
        print(json.dumps(preflight.record, sort_keys=True))
        return 0
    real_executor = build_real_agent_executor(
        study_dir=args.study_dir,
        expected_identity=preflight.runtime_identity,
    )
    state = asyncio.run(
        run_contextual_validation_campaign(
            plan=preflight.plan,
            output=args.output,
            executors={
                "contextual_agent": real_executor,
                "fixed_pipeline": FixedPipelineSlotExecutor(study_dir=args.study_dir),
                "no_context_ablation": real_executor,
            },
            preflight_record=preflight.record,
        )
    )
    if state.status == "infrastructure_stopped":
        print("infrastructure_stopped")
        return 3
    report = finalize_campaign_output(
        seal_dir=args.seal,
        output=args.output,
        acceptance_targets_path=args.study_dir.parent / "acceptance_targets.json",
    )
    print(json.dumps({"target_status": report["target_status"]}, sort_keys=True))
    return 0 if report["target_status"] == "meets_target" else 2


if __name__ == "__main__":
    sys.exit(main())
