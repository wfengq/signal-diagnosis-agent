"""CLI entry point for layer-1 characterization (manifest dry-run in Task 3)."""

from __future__ import annotations

import argparse
import sys

from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.manifest import (
    build_manifest,
    estimate_measurement_rows,
    estimate_shard_sizes_bytes,
    manifest_sha256,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    ManifestLeakageAbort,
    ScaleLimitExceeded,
)


def _cmd_manifest_dry_run() -> int:
    try:
        manifest = build_manifest(ROUND_1)
    except ScaleLimitExceeded as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except ManifestLeakageAbort as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 3

    print(f"round_id={manifest.round_id}")
    print(f"manifest_sha256={manifest_sha256(manifest)}")
    print("planned_pair_counts:")
    for side in sorted(manifest.planned_pair_counts.by_side):
        print(f"  {side}: {manifest.planned_pair_counts.by_side[side]}")
    print("by_side/family/perturbation:")
    for side, families in sorted(manifest.planned_pair_counts.by_side_family_perturbation.items()):
        for family in sorted(families):
            for pert, count in sorted(families[family].items()):
                print(f"  {side}/{family}/{pert}: {count}")
    est_rows = estimate_measurement_rows(manifest)
    print(f"estimated_measurement_rows={est_rows}")
    shards = estimate_shard_sizes_bytes(manifest.planned_pair_counts)
    for shard, nbytes in sorted(shards.items()):
        print(f"estimated_shard_gzip_bytes {shard}: {nbytes}")
    print(f"excluded_near_duplicates={len(manifest.excluded_near_duplicates)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signal_diag.evaluation.full_scale_characterization")
    sub = parser.add_subparsers(dest="command", required=True)
    manifest_parser = sub.add_parser("manifest")
    manifest_parser.add_argument("--round", required=True)
    manifest_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "manifest":
        if args.round != "round_1":
            print("only round_1 is supported", file=sys.stderr)
            return 1
        if not args.dry_run:
            print("manifest without --dry-run is not authorized in Task 3", file=sys.stderr)
            return 1
        return _cmd_manifest_dry_run()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
