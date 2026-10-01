#!/usr/bin/env python3
"""Study-only v2 planner-ablation campaign entry (offline harness / online refusal).

Requires explicit ``--mode`` and ``--output-dir``. Offline mode attaches fail-on-call
provider instrumentation and writes harness artifacts only to a fresh directory.
Online mode rejects missing verified seal, matching authorization reference, or
complete budget preflight **before** constructing any network client.

This script does not create a real protocol seal and does not call RealLLM
providers. An authorization-reference field is an audit link, not self-issued
permission. Missing production request/token bounds remain documented blockers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from signal_diag.agent.policies import AgentLimits
from signal_diag.evaluation.planner_ablation.v2.campaign import (
    CampaignPreflightError,
    inspect_limits,
    reject_online_preflight,
    snapshot_effective_configuration,
)
from signal_diag.evaluation.planner_ablation.v2.models import StudyProtocolV2
from signal_diag.evaluation.planner_ablation.v2.population import (
    build_schedule,
    load_proposed_scenarios,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FailOnCallProvider:
    """Offline instrumentation: any provider call is a hard failure."""

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        self.calls += 1
        raise AssertionError("provider must not be called in offline v2 campaign mode")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("offline", "online"),
        required=True,
        help="Execution mode. Online is refused without seal/auth/budget.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Fresh output directory for harness artifacts (required).",
    )
    parser.add_argument(
        "--verified-seal-digest",
        default=None,
        help="Online-only audit digest of a verified seal (not a self-issued grant).",
    )
    parser.add_argument(
        "--authorization-reference",
        default=None,
        help="Online-only audit link to operator authorization (not permission itself).",
    )
    return parser.parse_args(argv)


def _ensure_fresh_output(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CampaignPreflightError(f"output directory must be fresh/empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)


def _run_offline(output_dir: Path) -> dict[str, Any]:
    _ensure_fresh_output(output_dir)
    provider = FailOnCallProvider()

    limits_config = snapshot_effective_configuration(limits=AgentLimits())
    budget = inspect_limits(limits_config)
    protocol = StudyProtocolV2()
    scenarios = load_proposed_scenarios(PROJECT_ROOT)
    schedule = build_schedule(scenarios, protocol, repository_root=PROJECT_ROOT)
    product_slots = sum(1 for slot in schedule.slots if slot.arm == "product_agent")

    _write_json(output_dir / "effective_configuration.json", limits_config.model_dump(mode="json"))
    _write_json(output_dir / "budget_assessment.json", budget.model_dump(mode="json"))
    _write_json(
        output_dir / "schedule_summary.json",
        {
            "study_id": protocol.study_id,
            "schedule_digest": schedule.schedule_digest,
            "planned_slots": len(schedule.slots),
            "product_slots": product_slots,
            "canonical_requests": len(schedule.canonical_requests),
            "deadline_s": protocol.deadline_s,
            "execution_identity": "harness_only",
            "campaign_retry_policy": "forbidden",
        },
    )
    _write_json(
        output_dir / "provider_spy.json",
        {
            "provider_calls": provider.calls,
            "instrumentation": "fail_on_call",
            "network_client_constructed": False,
        },
    )
    _write_json(
        output_dir / "status.json",
        {
            "status": "offline_harness_artifacts_written",
            "provider_calls": provider.calls,
            "budget_execution_blocked": budget.execution_blocked,
            "seal_ready": budget.seal_ready,
            "note": (
                "Missing production request/token/transport bounds remain "
                "seal/execution blockers. Full slot dispatch is exercised by "
                "study unit tests and a later offline-acceptance grant; this "
                "entry point refuses online client construction."
            ),
            "budget_blockers": list(budget.blockers),
        },
    )
    if provider.calls != 0:
        raise CampaignPreflightError("offline harness recorded unexpected provider calls")
    return {
        "status": "offline_harness_artifacts_written",
        "provider_calls": provider.calls,
        "planned_slots": len(schedule.slots),
        "product_slots": product_slots,
        "execution_blocked_budget": budget.execution_blocked,
        "budget_blockers": list(budget.blockers),
        "accepted_conclusion_available": False,
        "network_client_constructed": False,
    }


def _run_online_refusal(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    # Refuse before any network client exists. Optional artifact dir records the refusal.
    _ensure_fresh_output(output_dir)
    config = snapshot_effective_configuration(limits=AgentLimits())
    budget = inspect_limits(config)
    _write_json(output_dir / "effective_configuration.json", config.model_dump(mode="json"))
    _write_json(output_dir / "budget_assessment.json", budget.model_dump(mode="json"))
    try:
        reject_online_preflight(
            verified_seal_digest=args.verified_seal_digest,
            authorization_reference=args.authorization_reference,
            budget=budget,
        )
    except CampaignPreflightError as error:
        _write_json(
            output_dir / "online_refusal.json",
            {
                "refused": True,
                "reason": str(error),
                "network_client_constructed": False,
                "authorization_reference_is_audit_link_only": True,
            },
        )
        raise
        raise CampaignPreflightError(
            "online mode passed preflight unexpectedly; refusing to construct "
            "network client (resource-policy production generation requires a "
            "later grant; unresolved resource blockers remain)"
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = args.output_dir.resolve()
    try:
        if args.mode == "online":
            result = _run_online_refusal(args, output_dir)
        else:
            result = _run_offline(output_dir)
    except CampaignPreflightError as error:
        print(f"campaign_refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
