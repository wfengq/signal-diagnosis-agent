"""Manifest generation and canonical hashing."""

from __future__ import annotations

import hashlib
import json

from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
    constants_digest,
)
from signal_diag.evaluation.full_scale_characterization.groups import (
    enumerate_source_groups,
)
from signal_diag.evaluation.full_scale_characterization.leakage import (
    _validation_wave_index,
    assert_no_param_leakage,
    assert_onset_depths,
    assert_p3_phases_disjoint,
    build_validation_effective_index,
    clear_wave_cache,
    exclude_near_duplicate_sensitivity_pairs,
    scan_calibration_near_duplicate_exclusions,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    Manifest,
    PlannedPairCounts,
    ScaleLimitExceeded,
)
from signal_diag.evaluation.full_scale_characterization.pairs import (
    _identity_dict_to_pair_record,
    canonical_pair_tuple_bytes,
    default_pair_templates,
    enumerate_pair_batches,
    pair_tuple_for_hash,
    planned_pair_counts_from_formulas,
)


def manifest_sha256(manifest: Manifest) -> str:
    payload = manifest.model_dump(mode="json", exclude={"pairs"})
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _subtract_excluded_counts(
    counts: PlannedPairCounts,
    excluded_families: list[tuple[str, str]],
) -> PlannedPairCounts:
    if not excluded_families:
        return counts
    by_side = dict(counts.by_side)
    by_side_family = {side: dict(fams) for side, fams in counts.by_side_family.items()}
    by_side_family_perturbation = {
        side: {fam: dict(perts) for fam, perts in families.items()}
        for side, families in counts.by_side_family_perturbation.items()
    }
    for family, perturbation in excluded_families:
        by_side["calibration"] = by_side.get("calibration", 0) - 1
        by_side_family.setdefault("calibration", {})
        by_side_family["calibration"][family] = by_side_family["calibration"].get(family, 0) - 1
        perts = by_side_family_perturbation.setdefault("calibration", {}).setdefault(family, {})
        perts[perturbation] = perts.get(perturbation, 0) - 1
    return PlannedPairCounts(
        by_side=by_side,
        by_side_family=by_side_family,
        by_side_family_perturbation=by_side_family_perturbation,
    )


def _enforce_scale_limit(
    counts: PlannedPairCounts,
    c: CharacterizationConstants,
) -> None:
    if not c.scale_limit_enabled:
        return
    cal = counts.by_side.get("calibration", 0)
    val = counts.by_side.get("validation", 0)
    if cal == 0:
        return
    if val > cal * c.validation_max_pair_ratio_to_calibration:
        raise ScaleLimitExceeded(
            f"validation pairs {val} exceed {c.validation_max_pair_ratio_to_calibration}x "
            f"calibration pairs {cal}"
        )


def build_manifest(
    constants: CharacterizationConstants = ROUND_1,
) -> Manifest:
    assert_p3_phases_disjoint(constants)
    assert_onset_depths(constants)
    clear_wave_cache()
    groups = enumerate_source_groups(constants)

    if constants.round_id == "round_1":
        wave_index = _validation_wave_index(groups, constants)
        excluded_ids, excluded_accum, excluded_families = scan_calibration_near_duplicate_exclusions(
            groups,
            constants,
            wave_index=wave_index,
        )
        counts = planned_pair_counts_from_formulas(groups, constants)
        counts = _subtract_excluded_counts(counts, excluded_families)
        _enforce_scale_limit(counts, constants)

        validation_index = build_validation_effective_index(groups)
        pair_hasher = hashlib.sha256()
        for batch in enumerate_pair_batches(groups, constants, batch_size=2048):
            assert_no_param_leakage(batch, validation_index)
            for identity in batch:
                if identity["pair_id"] in excluded_ids:
                    continue
                pair_hasher.update(canonical_pair_tuple_bytes(pair_tuple_for_hash(identity)))

        return Manifest(
            round_id=constants.round_id,
            constants_digest=constants_digest(constants),
            source_groups=groups,
            pair_templates=default_pair_templates(),
            pairs_list_sha256=pair_hasher.hexdigest(),
            planned_pair_counts=counts,
            excluded_near_duplicates=excluded_accum,
            pairs=(),
        )

    stored_pairs: list = []
    excluded_accum: list = []
    pair_hasher = hashlib.sha256()
    wave_index = _validation_wave_index(groups, constants)
    validation_index = build_validation_effective_index(groups)
    excluded_families: list[tuple[str, str]] = []

    for batch in enumerate_pair_batches(groups, constants, batch_size=1024):
        assert_no_param_leakage(batch, validation_index)
        records = [_identity_dict_to_pair_record(d) for d in batch]
        records, excluded_part = exclude_near_duplicate_sensitivity_pairs(
            records,
            groups,
            constants,
            wave_index=wave_index,
        )
        kept_ids = {r.pair_id for r in records}
        for entry in excluded_part:
            excluded_accum.append(entry)
            src = next(d for d in batch if d["pair_id"] == entry.pair_id)
            excluded_families.append((src["family"], src["perturbation_code"]))
        for d in batch:
            if d["pair_id"] not in kept_ids:
                continue
            pair_hasher.update(canonical_pair_tuple_bytes(pair_tuple_for_hash(d)))
        stored_pairs.extend(records)

    counts = planned_pair_counts_from_formulas(groups, constants)
    counts = _subtract_excluded_counts(counts, excluded_families)
    _enforce_scale_limit(counts, constants)
    return Manifest(
        round_id=constants.round_id,
        constants_digest=constants_digest(constants),
        source_groups=groups,
        pair_templates=default_pair_templates(),
        pairs_list_sha256=pair_hasher.hexdigest(),
        planned_pair_counts=counts,
        excluded_near_duplicates=tuple(excluded_accum),
        pairs=tuple(stored_pairs),
    )


def estimate_measurement_rows(manifest: Manifest, *, channels: int = 1) -> int:
    total_pairs = sum(manifest.planned_pair_counts.by_side.values())
    return total_pairs * 2 * channels


def estimate_shard_sizes_bytes(counts: PlannedPairCounts, *, bytes_per_row: int = 170) -> dict[str, int]:
    shards: dict[str, int] = {}
    for side, families in counts.by_side_family.items():
        for family, pair_count in families.items():
            shards[f"{side}/{family}"] = pair_count * 2 * bytes_per_row
    return shards
