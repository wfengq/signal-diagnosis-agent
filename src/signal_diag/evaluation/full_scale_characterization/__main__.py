"""CLI entry point for layer-1 characterization (T-CX380).

Commands: manifest, calibrate, report-calibration, freeze, validate,
report-validation.  Every command except ``manifest --dry-run`` works in the
round directory given by ``--out`` and refuses to rewrite existing artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from signal_diag.evaluation.full_scale_characterization import runs
from signal_diag.evaluation.full_scale_characterization.fitting import (
    CalibrationOnlyError,
    RowLimitExceeded,
)
from signal_diag.evaluation.full_scale_characterization.freeze import FreezeRejected
from signal_diag.evaluation.full_scale_characterization.gate import ValidationLocked
from signal_diag.evaluation.full_scale_characterization.identity import IdentityMismatch
from signal_diag.evaluation.full_scale_characterization.models import (
    ManifestLeakageAbort,
    SanityAbort,
    ScaleLimitExceeded,
)
from signal_diag.evaluation.full_scale_characterization.store import (
    CharacterizationStore,
    ShardTooLarge,
    StoreIntegrityError,
    WriteOnceViolation,
)

_BLOCKING = (
    CalibrationOnlyError,
    FileNotFoundError,
    FreezeRejected,
    IdentityMismatch,
    ManifestLeakageAbort,
    RowLimitExceeded,
    SanityAbort,
    ScaleLimitExceeded,
    ShardTooLarge,
    StoreIntegrityError,
    ValidationLocked,
    WriteOnceViolation,
    ValueError,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signal_diag.evaluation.full_scale_characterization")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser("manifest", help="R0: write manifest.json and identity.json")
    source = manifest.add_mutually_exclusive_group()
    source.add_argument("--round", choices=("round_1",))
    source.add_argument("--constants-json", type=Path)
    manifest.add_argument("--dry-run", action="store_true")
    manifest.add_argument("--out", type=Path)

    for name in ("calibrate", "validate", "report-validation"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--out", type=Path, required=True)

    report = sub.add_parser("report-calibration")
    report.add_argument("--stage", choices=("1", "2"), required=True)
    report.add_argument("--out", type=Path, required=True)

    freeze = sub.add_parser("freeze", help="select a fitted row by id; values are taken from the report")
    freeze.add_argument("--stage", choices=("1", "2"), required=True)
    selector = freeze.add_mutually_exclusive_group(required=True)
    selector.add_argument("--zone-row-id", help="stage 1: (domain, K row) row id")
    selector.add_argument("--floor-row-id", help="stage 2: F row id (F3 ids carry the cut)")
    freeze.add_argument("--rationale", required=True)
    freeze.add_argument("--approved-by", required=True)
    freeze.add_argument("--approved-at", required=True)
    freeze.add_argument("--out", type=Path, required=True)
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.command == "manifest":
        constants = runs.load_constants(args.constants_json)
        if args.dry_run:
            lines = runs.dry_run_lines(constants)
            for line in lines:
                print(line)
            if "param_leakage_hits=0" not in lines:
                print("BLOCKED: parameter leakage hits", file=sys.stderr)
                return 3
            stage1, stage2 = runs.fit_row_counts(constants)
            if stage1 > runs.STAGE1_MAX_ROWS or stage2 > runs.STAGE2_MAX_ROWS:
                print("BLOCKED: fitting row limit exceeded", file=sys.stderr)
                return 2
            return 0
        if args.out is None:
            print("--out is required unless --dry-run", file=sys.stderr)
            return 1
        runs.step_manifest(CharacterizationStore(args.out), constants)
        return 0

    store = CharacterizationStore(args.out)
    if args.command == "calibrate":
        runs.step_calibrate(store)
    elif args.command == "report-calibration":
        if args.stage == "1":
            runs.step_report_stage1(store)
        else:
            runs.step_report_stage2(store)
    elif args.command == "freeze":
        approval = {
            "rationale": args.rationale,
            "approved_by": args.approved_by,
            "approved_at": args.approved_at,
        }
        if args.stage == "1":
            if args.zone_row_id is None:
                print("freeze --stage 1 needs --zone-row-id", file=sys.stderr)
                return 1
            runs.step_freeze_stage1(store, zone_row_id=args.zone_row_id, **approval)
        else:
            if args.floor_row_id is None:
                print("freeze --stage 2 needs --floor-row-id", file=sys.stderr)
                return 1
            runs.step_freeze(store, floor_row_id=args.floor_row_id, **approval)
    elif args.command == "validate":
        runs.step_validate(store)
    elif args.command == "report-validation":
        runs.step_report_validation(store)
    else:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except _BLOCKING as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
