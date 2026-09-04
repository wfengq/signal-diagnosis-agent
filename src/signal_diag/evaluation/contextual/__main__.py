"""CLI entry for the isolated contextual evaluation harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from signal_diag.evaluation.contextual.calibration import (
    calibrate_even_growth_threshold,
    stable_code_sha,
)
from signal_diag.evaluation.contextual.manifest import (
    load_contextual_manifest,
    validate_contextual_manifest,
)
from signal_diag.evaluation.contextual.sealing import (
    seal_contextual_bundle,
    verify_contextual_bundle,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m signal_diag.evaluation.contextual",
        description="Isolated contextual evaluation harness (offline).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate_cmd = sub.add_parser("validate-manifest", help="Validate a manifest JSON")
    validate_cmd.add_argument("--manifest", type=Path, required=True)

    calibrate_cmd = sub.add_parser(
        "calibrate",
        help="Calibrate even-growth threshold from development growth samples",
    )
    calibrate_cmd.add_argument("--manifest", type=Path, required=True)
    calibrate_cmd.add_argument("--controls-json", type=Path, required=True)
    calibrate_cmd.add_argument("--positives-json", type=Path, required=True)
    calibrate_cmd.add_argument("--output", type=Path, required=True)

    seal_cmd = sub.add_parser("seal", help="Write an append-only seal bundle")
    seal_cmd.add_argument("--manifest", type=Path, required=True)
    seal_cmd.add_argument("--destination", type=Path, required=True)
    seal_cmd.add_argument("--meta-json", type=Path, required=True)

    verify_cmd = sub.add_parser("verify", help="Verify a sealed contextual bundle")
    verify_cmd.add_argument("--bundle", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-manifest":
        manifest = load_contextual_manifest(args.manifest)
        validate_contextual_manifest(manifest)
        print("ok")
        return 0
    if args.command == "calibrate":
        manifest = load_contextual_manifest(args.manifest)
        controls = tuple(json.loads(args.controls_json.read_text(encoding="utf-8")))
        positives = tuple(json.loads(args.positives_json.read_text(encoding="utf-8")))
        report = calibrate_even_growth_threshold(
            manifest=manifest,
            control_growth_percents=controls,
            positive_growth_percents=positives,
            code_sha256=stable_code_sha("signal_diag.evaluation.contextual"),
        )
        args.output.write_text(
            report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        print(report.calibration_status)
        return 0 if report.calibration_status == "selected" else 2
    if args.command == "seal":
        manifest = load_contextual_manifest(args.manifest)
        meta = json.loads(args.meta_json.read_text(encoding="utf-8"))
        seal_contextual_bundle(
            destination=args.destination,
            manifest=manifest,
            wav_checksums=meta["wav_checksums"],
            source_decisions=meta["source_decisions"],
            product_code_sha256=meta["product_code_sha256"],
            prompt_sha256=meta["prompt_sha256"],
            profile_s1_sha256=meta["profile_s1_sha256"],
            profile_contextual_sha256=meta["profile_contextual_sha256"],
            scoring_identity=meta["scoring_identity"],
            slot_plan=meta["slot_plan"],
            execution_counters=meta["execution_counters"],
        )
        print(args.destination)
        return 0
    if args.command == "verify":
        verify_contextual_bundle(args.bundle)
        print("ok")
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
