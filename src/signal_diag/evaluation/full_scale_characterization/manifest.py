"""Manifest generation and canonical hashing."""

from __future__ import annotations

import gc
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager

from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
    constants_digest,
)
from signal_diag.evaluation.full_scale_characterization.gate import (
    require_validation_access,
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
    count_param_leakage,
    scan_near_duplicates,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    Manifest,
    PairRecord,
    PlannedPairCounts,
    ScaleLimitExceeded,
    Side,
)
from signal_diag.evaluation.full_scale_characterization.pairs import (
    _identity_dict_to_pair_record,
    _r0_description_batches,
    canonical_pair_tuple_bytes,
    default_pair_templates,
    enumerate_pair_batches,
    iter_pair_identity_tuples,
    pair_tuple_for_hash,
    planned_pair_counts_from_formulas,
)
from signal_diag.evaluation.full_scale_characterization.store import encode_range_key


def manifest_sha256(manifest: Manifest) -> str:
    payload = manifest.model_dump(mode="json", exclude={"pairs"})
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _subtract_excluded_counts(
    counts: PlannedPairCounts,
    excluded: list[tuple[str, str, float]],
) -> PlannedPairCounts:
    """Remove A.15-excluded calibration pairs (family, code, range length) from the counts."""
    if not excluded:
        return counts
    by_side = dict(counts.by_side)
    by_side_family = {side: dict(fams) for side, fams in counts.by_side_family.items()}
    by_side_family_perturbation = {
        side: {fam: dict(perts) for fam, perts in families.items()}
        for side, families in counts.by_side_family_perturbation.items()
    }
    by_side_family_range = {
        side: {fam: dict(lengths) for fam, lengths in families.items()}
        for side, families in counts.by_side_family_range.items()
    }
    for family, perturbation, range_length in excluded:
        by_side["calibration"] = by_side.get("calibration", 0) - 1
        fams = by_side_family.setdefault("calibration", {})
        fams[family] = fams.get(family, 0) - 1
        perts = by_side_family_perturbation.setdefault("calibration", {}).setdefault(family, {})
        perts[perturbation] = perts.get(perturbation, 0) - 1
        lengths = by_side_family_range.setdefault("calibration", {}).setdefault(family, {})
        key = encode_range_key(range_length)
        lengths[key] = lengths.get(key, 0) - 1
    return PlannedPairCounts(
        by_side=by_side,
        by_side_family=by_side_family,
        by_side_family_perturbation=by_side_family_perturbation,
        by_side_family_range=by_side_family_range,
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


@contextmanager
def _gc_paused() -> Iterator[None]:
    """Pause cyclic GC while streaming ~10^6 short-lived acyclic pair dicts (speed only)."""
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def build_manifest(
    constants: CharacterizationConstants = ROUND_1,
) -> Manifest:
    with _gc_paused():
        return _build_manifest(constants)


def _build_manifest(
    constants: CharacterizationConstants,
) -> Manifest:
    """Build the manifest; A.15 runs over every calibration side for both modes.

    ``constants.expand_pairs`` (small test grids) also stores calibration
    PairRecords and runs the per-channel parameter-leakage check inline; the
    full round streams descriptions into the hash, and its parameter-leakage
    check runs on the R0 path (``count_param_leakage``).
    """
    assert_p3_phases_disjoint(constants)
    assert_onset_depths(constants)
    clear_wave_cache()
    groups = enumerate_source_groups(constants)
    wave_index = _validation_wave_index(groups, constants)
    excluded_ids, excluded_entries, excluded_families = scan_near_duplicates(
        groups, constants, wave_index=wave_index
    )
    counts = planned_pair_counts_from_formulas(groups, constants)
    counts = _subtract_excluded_counts(counts, excluded_families)
    _enforce_scale_limit(counts, constants)

    pair_hasher = hashlib.sha256()
    stored_pairs: list[PairRecord] = []
    if constants.expand_pairs:
        validation_index = build_validation_effective_index(groups)
        layouts = {g.group_key: g.m9_layout for g in groups}
        for batch in _r0_description_batches(groups, constants, batch_size=1024):
            kept = [d for d in batch if d["pair_id"] not in excluded_ids]
            assert_no_param_leakage(kept, validation_index, m9_layouts=layouts)
            for d in kept:
                pair_hasher.update(canonical_pair_tuple_bytes(pair_tuple_for_hash(d)))
                # Only calibration records are stored; validation descriptions enter the hash only.
                if d["side"] == "calibration":
                    stored_pairs.append(_identity_dict_to_pair_record(d))
    else:
        for identity in iter_pair_identity_tuples(groups, constants, skip_pair_ids=excluded_ids):
            pair_hasher.update(canonical_pair_tuple_bytes(pair_tuple_for_hash(identity)))

    return Manifest(
        round_id=constants.round_id,
        constants_digest=constants_digest(constants),
        source_groups=groups,
        pair_templates=default_pair_templates(),
        pairs_list_sha256=pair_hasher.hexdigest(),
        planned_pair_counts=counts,
        excluded_near_duplicates=excluded_entries,
        pairs=tuple(stored_pairs),
    )


def r0_param_leakage_hits(manifest: Manifest, constants: CharacterizationConstants) -> list[str]:
    """Streaming per-channel parameter-leakage check over every kept calibration pair (R0)."""
    excluded = frozenset(e.pair_id for e in manifest.excluded_near_duplicates)
    return count_param_leakage(manifest.source_groups, constants, skip_pair_ids=excluded)


def estimate_measurement_rows(manifest: Manifest, *, channels: int = 1) -> int:
    total_pairs = sum(manifest.planned_pair_counts.by_side.values())
    return total_pairs * 2 * channels


def estimate_shard_sizes_bytes(counts: PlannedPairCounts, *, bytes_per_row: int = 170) -> dict[str, int]:
    """Estimated compressed size per shard ``<side>/<family>/<range key>`` (A.16)."""
    shards: dict[str, int] = {}
    for side, families in counts.by_side_family_range.items():
        for family, lengths in families.items():
            for key, pair_count in lengths.items():
                shards[f"{side}/{family}/{key}"] = pair_count * 2 * bytes_per_row
    return shards


def iter_side_pairs(
    manifest: Manifest,
    constants: CharacterizationConstants,
    side: Side,
    *,
    validation_access: object = None,
) -> Iterator[PairRecord]:
    """Expand the run pairs of one side (near-duplicate exclusions removed).

    Validation-side expansion requires a ``ValidationAccess`` from a verified,
    complete freeze record; the check happens before anything is generated.
    """
    if side == "validation":
        require_validation_access(validation_access, what="expand validation pairs")
    if constants_digest(constants) != manifest.constants_digest:
        raise ValueError("constants do not match the manifest constants_digest")
    excluded = {e.pair_id for e in manifest.excluded_near_duplicates}

    batches = enumerate_pair_batches(
        manifest.source_groups,
        constants,
        batch_size=1024,
        side=side,
        validation_access=validation_access,
    )

    def _generate() -> Iterator[PairRecord]:
        for batch in batches:
            for identity in batch:
                if identity["pair_id"] in excluded:
                    continue
                yield _identity_dict_to_pair_record(identity)

    return _generate()
