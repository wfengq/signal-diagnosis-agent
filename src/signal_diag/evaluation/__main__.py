"""Operational Phase 4 evaluation CLI. CONTRACTS §49."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from signal_diag.evaluation.dataset import load_dataset_manifest, validate_dataset
from signal_diag.evaluation.models import BenchmarkReport
from signal_diag.evaluation.reporting import write_benchmark_bundle
from signal_diag.evaluation.runner import (
    _campaign_identity_matches,
    _official_benchmark_config,
    _official_dependencies,
    _official_manifest_path,
    _phase4_1_benchmark_config,
    _phase4_1_manifest_path,
    _run_deterministic_benchmark,
    _run_official_benchmark,
    _run_phase4_1_development_benchmark,
    _run_phase4_1_official_benchmark,
    _scripted_benchmark_config,
    _write_invalid_configuration_report,
)
from signal_diag.signal.repository import InMemorySignalRepository

_DEFAULT_OUTPUT_DIR = Path("docs") / "evaluations" / "phase4"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m signal_diag.evaluation",
        description="Phase 4 evaluation operational commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-dataset",
        help="Load and validate a dataset manifest.",
    )
    validate.add_argument("--manifest", type=Path, default=None)

    deterministic = subparsers.add_parser(
        "run-deterministic",
        help="Run the scripted Agent harness and fixed baseline.",
    )
    deterministic.add_argument("--manifest", type=Path, default=None)
    deterministic.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    deterministic.add_argument("--benchmark-id", type=str, default=None)

    real = subparsers.add_parser(
        "run-real",
        help="Run the official DeepSeek held-out benchmark.",
    )
    real.add_argument("--manifest", type=Path, default=None)
    real.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    real.add_argument("--benchmark-id", type=str, default=None)
    real.add_argument(
        "--campaign",
        choices=("phase4", "phase4.1-development", "phase4.1-official"),
        default="phase4",
    )

    render = subparsers.add_parser(
        "render-report",
        help="Validate an existing report JSON and write a new bundle.",
    )
    render.add_argument("--input", type=Path, required=True)
    render.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    return parser


def _load_manifest(path: Path | None) -> object:
    return load_dataset_manifest(path or _official_manifest_path())


def _stamp_id(prefix: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ").lower()
    return f"bench_{prefix}_{stamp}"


def _validate_dataset(manifest_path: Path | None) -> int:
    from signal_diag.evaluation.models import DatasetManifest

    manifest = _load_manifest(manifest_path)
    if not isinstance(manifest, DatasetManifest):
        raise TypeError("expected DatasetManifest")
    repository = InMemorySignalRepository()
    tool_service, rule_engine, profile_loader, _index = _official_dependencies(
        repository
    )
    report = validate_dataset(
        manifest,
        repository,
        tool_service,
        rule_engine,
        profile_loader,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if report.valid else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-dataset":
        return _validate_dataset(args.manifest)
    if args.command == "run-deterministic":
        from signal_diag.evaluation.models import DatasetManifest

        manifest = _load_manifest(args.manifest)
        if not isinstance(manifest, DatasetManifest):
            raise TypeError("expected DatasetManifest")
        config = _scripted_benchmark_config(
            manifest,
            benchmark_id=args.benchmark_id or _stamp_id("deterministic"),
            started_at_utc=datetime.now(UTC),
        )
        report = asyncio.run(
            _run_deterministic_benchmark(manifest, config, args.output_dir)
        )
        print(report.benchmark_status)
        return 0
    if args.command == "run-real":
        from signal_diag.evaluation.models import DatasetManifest, EvaluationSplit

        if args.campaign == "phase4":
            manifest = _load_manifest(args.manifest)
            if not isinstance(manifest, DatasetManifest):
                raise TypeError("expected DatasetManifest")
            config = _official_benchmark_config(
                benchmark_id=args.benchmark_id or _stamp_id("real"),
                started_at_utc=datetime.now(UTC),
            )
            if (
                manifest.dataset_id != config.dataset_id
                or manifest.version != config.dataset_version
            ):
                config = config.model_copy(
                    update={
                        "dataset_id": manifest.dataset_id,
                        "dataset_version": manifest.version,
                        "rule_profile_id": manifest.rule_profile_id,
                        "rule_profile_version": manifest.rule_profile_version,
                    }
                )
            report = asyncio.run(
                _run_official_benchmark(manifest, config, args.output_dir)
            )
            print(report.benchmark_status)
            return 0

        config = _phase4_1_benchmark_config(
            benchmark_id=args.benchmark_id or _stamp_id("real"),
            started_at_utc=datetime.now(UTC),
        )
        campaign_manifest = load_dataset_manifest(_phase4_1_manifest_path())
        manifest = (
            load_dataset_manifest(args.manifest)
            if args.manifest is not None
            else campaign_manifest
        )
        if not isinstance(manifest, DatasetManifest):
            raise TypeError("expected DatasetManifest")
        if not _campaign_identity_matches(manifest, config):
            score_split: EvaluationSplit = (
                "development"
                if args.campaign == "phase4.1-development"
                else "held_out"
            )
            extra = (
                ("development split; not official held-out evidence",)
                if score_split == "development"
                else ()
            )
            report = _write_invalid_configuration_report(
                campaign_manifest,
                config,
                args.output_dir,
                score_split=score_split,
                message="--manifest does not match the selected campaign identity",
                extra_warnings=extra,
            )
            print(report.benchmark_status)
            return 0
        runner = (
            _run_phase4_1_development_benchmark
            if args.campaign == "phase4.1-development"
            else _run_phase4_1_official_benchmark
        )
        report = asyncio.run(runner(manifest, config, args.output_dir))
        print(report.benchmark_status)
        return 0
    if args.command == "render-report":
        report = BenchmarkReport.model_validate_json(
            Path(args.input).read_text(encoding="utf-8")
        )
        write_benchmark_bundle(report, args.output_dir)
        return 0
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
