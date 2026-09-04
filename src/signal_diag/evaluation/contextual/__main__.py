"""CLI entry for the isolated contextual evaluation harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from signal_diag.evaluation.contextual.calibration import (
    calibrate_even_growth_threshold,
    contextual_implementation_sha256,
)
from signal_diag.evaluation.contextual.manifest import (
    load_contextual_manifest,
    validate_contextual_manifest,
)
from signal_diag.evaluation.contextual.qualification import qualify_development_study
from signal_diag.evaluation.contextual.sealing import (
    seal_contextual_bundle,
    verify_contextual_bundle,
)
from signal_diag.evaluation.contextual.shadow_replay import write_shadow_replay_report
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m signal_diag.evaluation.contextual",
        description="Isolated contextual evaluation harness (offline).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate_cmd = sub.add_parser("validate-manifest", help="Validate a manifest JSON")
    validate_cmd.add_argument("--manifest", type=Path, required=True)

    qualify_cmd = sub.add_parser(
        "qualify-development",
        help="Re-run deterministic development qualification gates",
    )
    qualify_cmd.add_argument("--study-dir", type=Path, required=True)
    qualify_cmd.add_argument(
        "--growth-threshold-percent",
        type=float,
        default=None,
        help="Even-growth threshold; defaults to frozen contextual profile value",
    )
    qualify_cmd.add_argument("--output", type=Path, required=True)

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

    shadow_cmd = sub.add_parser(
        "shadow-replay-rule-closure",
        help="Replay preserved Observation Evidence through v9.7 rule closure",
    )
    shadow_cmd.add_argument("--run-dir", type=Path, required=True)
    shadow_cmd.add_argument("--destination", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-manifest":
        manifest = load_contextual_manifest(args.manifest)
        validate_contextual_manifest(manifest)
        print("ok")
        return 0
    if args.command == "qualify-development":
        threshold = args.growth_threshold_percent
        if threshold is None:
            profile_path = (
                Path(__file__).resolve().parents[2]
                / "rules"
                / "profiles"
                / "s1_contextual_comparison_v1.yaml"
            )
            profile = YamlRuleProfileLoader(
                {"profile_s1_contextual_comparison": profile_path}
            ).load("profile_s1_contextual_comparison")
            growth = next(
                rule
                for rule in profile.rules
                if rule.rule_id == "rule_even_harmonic_growth_acceptable"
            )
            threshold = float(growth.threshold)
        qualify_report = qualify_development_study(
            study_dir=args.study_dir,
            growth_threshold_percent=threshold,
        )
        args.output.write_text(
            json.dumps(qualify_report, indent=2) + "\n", encoding="utf-8"
        )
        print("ok" if qualify_report["all_gates_passed"] else "failed")
        return 0 if qualify_report["all_gates_passed"] else 2
    if args.command == "calibrate":
        manifest = load_contextual_manifest(args.manifest)
        controls = tuple(json.loads(args.controls_json.read_text(encoding="utf-8")))
        positives = tuple(json.loads(args.positives_json.read_text(encoding="utf-8")))
        calibration_report = calibrate_even_growth_threshold(
            manifest=manifest,
            control_growth_percents=controls,
            positive_growth_percents=positives,
            code_sha256=contextual_implementation_sha256(),
        )
        args.output.write_text(
            calibration_report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        print(calibration_report.calibration_status)
        return 0 if calibration_report.calibration_status == "selected" else 2
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
    if args.command == "shadow-replay-rule-closure":
        profile_root = Path(__file__).resolve().parents[2] / "rules" / "profiles"
        write_shadow_replay_report(
            run_dir=args.run_dir,
            destination=args.destination,
            rule_engine=RuleEngine(),
            profile_loader=YamlRuleProfileLoader(
                {
                    "profile_s1_distortion": (
                        profile_root / "s1_distortion_v1.yaml"
                    ),
                    "profile_s1_contextual_comparison": (
                        profile_root / "s1_contextual_comparison_v1.yaml"
                    ),
                }
            ),
        )
        print("shadow_replay_complete")
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
