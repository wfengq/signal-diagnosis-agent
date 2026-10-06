"""Dry-run entry for the agent-increment study. It does not call a model."""

from __future__ import annotations

import argparse
import json

from signal_diag.evaluation.agent_increment.budget import (
    DEV_STAGE_CAP,
    HELD_OUT_STAGE_CAP,
)
from signal_diag.evaluation.agent_increment.campaign import dry_run_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m signal_diag.evaluation.agent_increment")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--split", choices=("dev", "heldout"), required=True)
    parser.add_argument("--cases", type=int, required=True)
    args = parser.parse_args(argv)
    if not args.dry_run:
        raise SystemExit("this entry only prints a dry-run estimate")
    cap = DEV_STAGE_CAP if args.split == "dev" else HELD_OUT_STAGE_CAP
    print(json.dumps(dry_run_summary(case_count=args.cases, stage_cap=cap), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
