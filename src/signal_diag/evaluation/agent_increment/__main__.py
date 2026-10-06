"""Entry for the agent-increment study.

``--dry-run`` only prints an estimate and never calls a model. ``--run`` starts a
live stage (D1 dev or H1 held-out) and needs DEEPSEEK_API_KEY; it is only run
under a separate operator authorization. ``--freeze-prompts`` writes the stage F
record that a held-out run requires.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from signal_diag.evaluation.agent_increment.budget import (
    DEV_STAGE_CAP,
    HELD_OUT_STAGE_CAP,
)
from signal_diag.evaluation.agent_increment.campaign import dry_run_summary

_STUDY_DIR = Path("docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m signal_diag.evaluation.agent_increment")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--freeze-prompts", action="store_true")
    parser.add_argument("--split", choices=("dev", "heldout"))
    parser.add_argument("--cases", type=int)
    parser.add_argument("--study-dir", type=Path, default=_STUDY_DIR)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approved-by")
    parser.add_argument("--approved-at")
    args = parser.parse_args(argv)

    if args.dry_run:
        if args.split is None or args.cases is None:
            parser.error("--dry-run requires --split and --cases")
        cap = DEV_STAGE_CAP if args.split == "dev" else HELD_OUT_STAGE_CAP
        print(json.dumps(dry_run_summary(case_count=args.cases, stage_cap=cap), sort_keys=True))
        return 0

    from signal_diag.evaluation.agent_increment import live_campaign

    if args.freeze_prompts:
        if not args.approved_by or not args.approved_at:
            parser.error("--freeze-prompts requires --approved-by and --approved-at")
        path = live_campaign.freeze_prompts(
            args.study_dir, approved_by=args.approved_by, approved_at=args.approved_at
        )
        print(path)
        return 0

    if args.split is None:
        parser.error("--run requires --split")
    out = args.out or live_campaign.default_output_dir(
        args.study_dir, args.split, datetime.now(UTC)
    )
    api_key = live_campaign.require_live_credentials(os.environ.get("DEEPSEEK_API_KEY"))
    base_url = "https://api.deepseek.com"
    payload = asyncio.run(
        live_campaign.run_campaign(
            split=args.split,
            study_dir=args.study_dir,
            output_dir=out,
            api_key=api_key,
            client_factory=lambda: live_campaign.build_live_sdk_client(
                api_key=api_key, base_url=base_url
            ),
            base_url=base_url,
        )
    )
    print(json.dumps({"output_dir": str(out), **payload}, ensure_ascii=False, sort_keys=True))
    return 0 if not payload["incomplete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
