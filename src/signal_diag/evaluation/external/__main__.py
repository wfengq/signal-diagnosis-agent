"""Explicit, gated CLI for the external WAV validity study."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
import wave
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from signal_diag.evaluation.external.manifest import load_external_manifest
from signal_diag.evaluation.external.models import (
    DerivationSpec,
    ExternalStudyReport,
    FinalSealInputs,
    ReviewRound,
    ReviewTargets,
    SourceCatalog,
)
from signal_diag.evaluation.external.pcm import derive_analysis_wav, read_pcm_window
from signal_diag.evaluation.external.reference import analyze_reference
from signal_diag.evaluation.external.reporting import (
    verify_external_bundle,
    write_external_bundle,
)
from signal_diag.evaluation.external.review import (
    build_blind_package,
    score_delayed_review,
)
from signal_diag.evaluation.external.runner import (
    run_external_agent,
    run_external_baseline,
)
from signal_diag.evaluation.external.sealing import (
    seal_final_external_test,
    verify_protected_assets,
)
from signal_diag.evaluation.external.source import (
    acquire_assets,
    validate_source_catalog,
)
from signal_diag.evaluation.external.validation import validate_external_manifest

_FORBIDDEN_DEFAULT_PATH_MARKERS = (
    "phase4_3_1",
    "phase4",
    "v0_2_acceptance",
    "phase5",
)
_CAMPAIGN_BYTE_LIMIT = 5 * 1024**3


class _UrllibOpener:
    def open(self, url: str):
        return closing(urllib.request.urlopen(url))


def _reject_forbidden_default_path(path: Path, label: str) -> None:
    normalized = path.as_posix().lower()
    for marker in _FORBIDDEN_DEFAULT_PATH_MARKERS:
        if marker in normalized:
            raise ValueError(f"{label} must not default into historical Phase 4/5 paths")


def _validate_output_path(path: Path, label: str) -> None:
    _reject_forbidden_default_path(path, label)
    if path.exists():
        raise FileExistsError(f"{label} already exists: {path}")


def _load_json_model(path: Path, model_type: type[object]) -> object:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return model_type.model_validate(payload)  # type: ignore[attr-defined]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m signal_diag.evaluation.external",
        description="External WAV validity study operational commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_catalog = subparsers.add_parser(
        "validate-source-catalog",
        help="Validate a source catalog against the approved host policy.",
    )
    validate_catalog.add_argument("--catalog", type=Path, required=True)

    acquire = subparsers.add_parser(
        "acquire",
        help="Acquire public source assets with explicit network authorization.",
    )
    acquire.add_argument("--catalog", type=Path, required=True)
    acquire.add_argument("--destination", type=Path, required=True)
    acquire.add_argument(
        "--allow-network",
        action="store_true",
        help="Explicitly authorize network access for downloads.",
    )
    acquire.add_argument(
        "--max-total-bytes",
        type=int,
        default=_CAMPAIGN_BYTE_LIMIT,
    )

    derive = subparsers.add_parser(
        "derive",
        help="Derive a loader-compatible mono PCM analysis WAV.",
    )
    derive.add_argument("--source", type=Path, required=True)
    derive.add_argument("--destination", type=Path, required=True)
    derive.add_argument("--channel-index", type=int, required=True)
    derive.add_argument("--start-frame", type=int, required=True)
    derive.add_argument("--stop-frame", type=int, required=True)

    reference = subparsers.add_parser(
        "reference",
        help="Run evaluator-only reference analysis on one analysis WAV.",
    )
    reference.add_argument("--wav", type=Path, required=True)
    reference.add_argument("--output", type=Path, required=True)
    reference.add_argument("--fmin-hz", type=float, default=50.0)
    reference.add_argument("--fmax-hz", type=float, default=1000.0)

    validate_manifest = subparsers.add_parser(
        "validate-manifest",
        help="Validate an external study manifest for a stage.",
    )
    validate_manifest.add_argument("--manifest", type=Path, required=True)
    validate_manifest.add_argument("--asset-root", type=Path, required=True)
    validate_manifest.add_argument(
        "--stage",
        choices=("development", "validation", "final_preflight"),
        required=True,
    )

    build_review = subparsers.add_parser(
        "build-review-package",
        help="Build a delayed blind review package from round 1 labels.",
    )
    build_review.add_argument("--manifest", type=Path, required=True)
    build_review.add_argument("--round1", type=Path, required=True)
    build_review.add_argument("--output", type=Path, required=True)
    build_review.add_argument("--alias-salt", type=str, required=True)
    build_review.add_argument("--created-at", type=str, default=None)

    score_review = subparsers.add_parser(
        "score-review",
        help="Score delayed blind review agreement between rounds 1 and 2.",
    )
    score_review.add_argument("--round1", type=Path, required=True)
    score_review.add_argument("--round2", type=Path, required=True)
    score_review.add_argument("--output", type=Path, required=True)

    seal_final = subparsers.add_parser(
        "seal-final",
        help="Write-once seal for the final external test manifest.",
    )
    seal_final.add_argument("--manifest", type=Path, required=True)
    seal_final.add_argument("--asset-root", type=Path, required=True)
    seal_final.add_argument("--repo-root", type=Path, required=True)
    seal_final.add_argument("--checksum-file", type=Path, required=True)
    seal_final.add_argument("--round1", type=Path, required=True)
    seal_final.add_argument("--round2", type=Path, required=True)
    seal_final.add_argument("--review-targets", type=Path, required=True)
    seal_final.add_argument("--destination", type=Path, required=True)
    seal_final.add_argument("--sealed-at", type=str, default=None)

    run_baseline = subparsers.add_parser(
        "run-baseline",
        help="Run the frozen fixed pipeline on sealed final cases.",
    )
    run_baseline.add_argument("--seal", type=Path, required=True)
    run_baseline.add_argument("--asset-root", type=Path, required=True)
    run_baseline.add_argument("--output", type=Path, required=True)

    run_agent = subparsers.add_parser(
        "run-agent",
        help="Run the frozen real-model Agent campaign on sealed final cases.",
    )
    run_agent.add_argument("--seal", type=Path, required=True)
    run_agent.add_argument("--asset-root", type=Path, required=True)
    run_agent.add_argument("--output", type=Path, required=True)
    run_agent.add_argument(
        "--authorize-real-model",
        action="store_true",
        help="Explicitly authorize one-time real-model execution.",
    )

    write_report = subparsers.add_parser(
        "write-report",
        help="Write an append-only external study bundle from a report JSON file.",
    )
    write_report.add_argument("--input", type=Path, required=True)
    write_report.add_argument("--destination", type=Path, required=True)

    verify_bundle = subparsers.add_parser(
        "verify-bundle",
        help="Verify checksums and safety rules for an external study bundle.",
    )
    verify_bundle.add_argument("--bundle", type=Path, required=True)

    verify_preservation = subparsers.add_parser(
        "verify-preservation",
        help="Verify protected V0.2 assets against a frozen checksum file.",
    )
    verify_preservation.add_argument("--repo-root", type=Path, required=True)
    verify_preservation.add_argument("--checksum-file", type=Path, required=True)
    return parser


def _parse_timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-source-catalog":
            catalog = _load_json_model(args.catalog, SourceCatalog)
            validate_source_catalog(catalog)  # type: ignore[arg-type]
            print("valid")
            return 0

        if args.command == "acquire":
            _validate_output_path(args.destination, "destination")
            if not args.allow_network:
                print("acquire requires --allow-network", file=sys.stderr)
                return 2
            catalog = _load_json_model(args.catalog, SourceCatalog)
            assets = acquire_assets(
                catalog,  # type: ignore[arg-type]
                args.destination,
                opener=_UrllibOpener(),
                allow_network=args.allow_network,
                max_total_bytes=args.max_total_bytes,
            )
            print(json.dumps([asset.model_dump(mode="json") for asset in assets], indent=2))
            return 0

        if args.command == "derive":
            _validate_output_path(args.destination, "destination")
            spec = DerivationSpec(
                channel_index=args.channel_index,
                start_frame=args.start_frame,
                stop_frame=args.stop_frame,
            )
            derived = derive_analysis_wav(args.source, spec, args.destination)
            print(json.dumps(derived.model_dump(mode="json"), indent=2, sort_keys=True))
            return 0

        if args.command == "reference":
            _validate_output_path(args.output, "output")
            with wave.open(str(args.wav), "rb") as handle:
                frame_count = handle.getnframes()
            window = read_pcm_window(
                args.wav,
                DerivationSpec(
                    channel_index=0,
                    start_frame=0,
                    stop_frame=frame_count,
                ),
            )
            summary = analyze_reference(
                np.asarray(window.samples[:, 0]),
                window.sample_rate_hz,
                fmin_hz=args.fmin_hz,
                fmax_hz=args.fmax_hz,
            )
            args.output.write_text(
                json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return 0

        if args.command == "validate-manifest":
            manifest = load_external_manifest(args.manifest)
            report = validate_external_manifest(
                manifest,
                args.asset_root,
                stage=args.stage,
            )
            print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
            return 0 if report.valid else 1

        if args.command == "build-review-package":
            _validate_output_path(args.output, "output")
            manifest = load_external_manifest(args.manifest)
            round1 = _load_json_model(args.round1, ReviewRound)
            package = build_blind_package(
                manifest,
                round1,  # type: ignore[arg-type]
                alias_salt=args.alias_salt.encode("utf-8"),
                created_at=_parse_timestamp(args.created_at),
            )
            args.output.write_text(
                json.dumps(package.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return 0

        if args.command == "score-review":
            _validate_output_path(args.output, "output")
            round1 = _load_json_model(args.round1, ReviewRound)
            round2 = _load_json_model(args.round2, ReviewRound)
            agreement = score_delayed_review(round1, round2)  # type: ignore[arg-type]
            args.output.write_text(
                json.dumps(agreement.model_dump(mode="json"), indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            return 0

        if args.command == "seal-final":
            _validate_output_path(args.destination, "destination")
            inputs = FinalSealInputs(
                manifest=load_external_manifest(args.manifest),
                asset_root=args.asset_root,
                repo_root=args.repo_root,
                checksum_file=args.checksum_file,
                round1=_load_json_model(args.round1, ReviewRound),  # type: ignore[arg-type]
                round2=_load_json_model(args.round2, ReviewRound),  # type: ignore[arg-type]
                review_targets=_load_json_model(args.review_targets, ReviewTargets),  # type: ignore[arg-type]
                sealed_at_utc=_parse_timestamp(args.sealed_at),
            )
            seal = seal_final_external_test(inputs, args.destination)
            print(json.dumps(seal.model_dump(mode="json"), indent=2, sort_keys=True))
            return 0

        if args.command == "run-baseline":
            _validate_output_path(args.output, "output")
            runner_report = asyncio.run(
                run_external_baseline(args.seal, args.asset_root, args.output)
            )
            print(runner_report.execution_path)
            return 0

        if args.command == "run-agent":
            _validate_output_path(args.output, "output")
            if not args.authorize_real_model:
                print("run-agent requires --authorize-real-model", file=sys.stderr)
                return 2
            if not os.environ.get("DEEPSEEK_API_KEY"):
                print("DEEPSEEK_API_KEY is required for run-agent", file=sys.stderr)
                return 2
            runner_report = asyncio.run(
                run_external_agent(
                    args.seal,
                    args.asset_root,
                    args.output,
                    authorized=True,
                )
            )
            print(runner_report.execution_path)
            return 0

        if args.command == "write-report":
            _validate_output_path(args.destination, "destination")
            study_report = _load_json_model(args.input, ExternalStudyReport)
            write_external_bundle(study_report, args.destination)  # type: ignore[arg-type]
            print("bundle_written")
            return 0

        if args.command == "verify-bundle":
            verify_external_bundle(args.bundle)
            print("verified")
            return 0

        if args.command == "verify-preservation":
            verify_protected_assets(args.repo_root, args.checksum_file)
            print("preserved")
            return 0

        parser.error(f"unknown command {args.command}")
        return 2
    except (FileExistsError, PermissionError, ValueError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
