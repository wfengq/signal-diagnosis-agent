"""Run steps behind the characterization CLI (T-CX380).

Each step checks the store's SHA256SUMS and identity before doing anything,
reads its inputs only from artifacts already written, and writes its outputs
once.  The CLI module only parses arguments.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from signal_diag.evaluation.full_scale_characterization.checks import (
    measure_pair_checked,
    run_sanity_checks,
)
from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
    constants_digest,
)
from signal_diag.evaluation.full_scale_characterization.executor import (
    MeasurementCache,
    assemble_pair,
)
from signal_diag.evaluation.full_scale_characterization.fitting import (
    K_ROW_IDS,
    P_MIN_CANDIDATES,
    STAGE1_MAX_ROWS,
    STAGE2_MAX_ROWS,
    Stage1Row,
    fit_stage1,
    fit_stage2,
    n_min_candidates,
)
from signal_diag.evaluation.full_scale_characterization.freeze import (
    FREEZE_RECORD,
    FREEZE_STAGE1,
    FreezeRecord,
    FreezeStage1,
    authorize_calibration,
    authorize_validation,
    draft_freeze_record,
    draft_freeze_stage1,
    selection_from_stage1,
    verify_freeze_stage1,
    write_freeze_record,
    write_freeze_stage1,
)
from signal_diag.evaluation.full_scale_characterization.gate import ValidationAccess
from signal_diag.evaluation.full_scale_characterization.identity import compute_identity
from signal_diag.evaluation.full_scale_characterization.manifest import (
    build_manifest,
    estimate_measurement_rows,
    estimate_shard_sizes_bytes,
    iter_side_pairs,
    manifest_sha256,
    r0_param_leakage_hits,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    Manifest,
    ManifestLeakageAbort,
    MeasuredPair,
    MeasurementRow,
    PairRecord,
    SanityAbort,
)
from signal_diag.evaluation.full_scale_characterization.pairs import TOLERANCE_CODES
from signal_diag.evaluation.full_scale_characterization.store import (
    SHARD_MAX_BYTES,
    CharacterizationStore,
    WriteOnceViolation,
    decode_range_key,
    encode_range_key,
    shard_path,
)
from signal_diag.evaluation.full_scale_characterization.validation import (
    count_validation,
    write_abort_record,
)
from signal_diag.evaluation.full_scale_characterization.zone import (
    ScoredPair,
    _side_facts,
    is_primary_condition,
    periods_in_range,
)

SideName = Literal["calibration", "validation"]


def load_constants(path: Path | None) -> CharacterizationConstants:
    if path is None:
        return ROUND_1
    return CharacterizationConstants.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def fit_row_counts(constants: CharacterizationConstants) -> tuple[int, int]:
    """(stage-1 rows, stage-2 maximum rows) implied by the fixed C.4 tables."""
    n_count = len(n_min_candidates(constants))
    stage1 = n_count * len(P_MIN_CANDIDATES) * len(K_ROW_IDS)
    # Most F3 cuts when the smallest n_min and p_min are selected.
    stage2 = 3 + 2 * ((n_count - 1) + (len(P_MIN_CANDIDATES) - 1))
    return stage1, stage2


# ---------------------------------------------------------------------------
# manifest


def dry_run_lines(constants: CharacterizationConstants) -> list[str]:
    manifest = build_manifest(constants)
    lines = [f"round_id={manifest.round_id}", f"manifest_sha256={manifest_sha256(manifest)}"]
    lines.append("planned_pair_counts:")
    for side in sorted(manifest.planned_pair_counts.by_side):
        lines.append(f"  {side}: {manifest.planned_pair_counts.by_side[side]}")
    lines.append("by_side/family/perturbation:")
    for side, families in sorted(manifest.planned_pair_counts.by_side_family_perturbation.items()):
        for family in sorted(families):
            for pert, count in sorted(families[family].items()):
                lines.append(f"  {side}/{family}/{pert}: {count}")
    lines.append(f"estimated_measurement_rows={estimate_measurement_rows(manifest)}")
    shards = estimate_shard_sizes_bytes(manifest.planned_pair_counts)
    for shard, nbytes in sorted(shards.items()):
        lines.append(f"estimated_shard_gzip_bytes {shard}: {nbytes}")
    over = sorted(shard for shard, nbytes in shards.items() if nbytes > SHARD_MAX_BYTES)
    lines.append(f"shards_over_limit={len(over)} (limit {SHARD_MAX_BYTES} B)")
    lines.append(f"excluded_near_duplicates={len(manifest.excluded_near_duplicates)}")
    hits = r0_param_leakage_hits(manifest, constants)
    lines.append(f"param_leakage_hits={len(hits)}")
    lines.extend(f"  {hit}" for hit in hits[:20])
    stage1, stage2 = fit_row_counts(constants)
    lines.append(f"stage1_rows={stage1} (limit {STAGE1_MAX_ROWS})")
    lines.append(f"stage2_rows_max={stage2} (limit {STAGE2_MAX_ROWS})")
    return lines


def step_manifest(store: CharacterizationStore, constants: CharacterizationConstants) -> None:
    """R0: write manifest.json (constants + manifest without per-pair expansion) and identity.json."""
    for name in ("manifest.json", "identity.json"):
        if store.exists(name):
            raise WriteOnceViolation(f"{name} already exists")
    manifest = build_manifest(constants)
    hits = r0_param_leakage_hits(manifest, constants)
    if hits:
        raise ManifestLeakageAbort(f"{len(hits)} parameter-leakage hits; first: {hits[0]}")
    store.write_json(
        "manifest.json",
        {
            "constants": constants.model_dump(mode="json"),
            "manifest": manifest.model_dump(mode="json", exclude={"pairs"}),
            "manifest_sha256": manifest_sha256(manifest),
        },
    )
    store.write_json("identity.json", compute_identity(constants))


def _load_manifest(store: CharacterizationStore) -> tuple[Manifest, CharacterizationConstants]:
    payload = store.read_json("manifest.json")
    constants = CharacterizationConstants.model_validate(payload["constants"])
    manifest = Manifest.model_validate(payload["manifest"])
    if manifest_sha256(manifest) != payload["manifest_sha256"]:
        raise ValueError("manifest.json: manifest_sha256 does not match its content")
    if constants_digest(constants) != manifest.constants_digest:
        raise ValueError("manifest.json: constants do not match constants_digest")
    return manifest, constants


def _checked(store: CharacterizationStore) -> tuple[Manifest, CharacterizationConstants]:
    store.verify_sha256sums()
    manifest, constants = _load_manifest(store)
    authorize_calibration(store, constants=constants)
    return manifest, constants


# ---------------------------------------------------------------------------
# measurement


def _measure_side(
    store: CharacterizationStore,
    manifest: Manifest,
    constants: CharacterizationConstants,
    side: SideName,
    access: ValidationAccess | None,
) -> list[tuple[PairRecord, MeasuredPair]]:
    layouts = {g.group_key: g.m9_layout for g in manifest.source_groups}
    cache: MeasurementCache = {}
    items: list[tuple[PairRecord, MeasuredPair]] = []
    pair_layouts: dict[str, dict[str, Any]] = {}
    try:
        for pair in iter_side_pairs(manifest, constants, side, validation_access=access):
            layout = layouts.get(pair.source_group_key)
            if layout is not None:
                pair_layouts[pair.pair_id] = layout
            rows = measure_pair_checked(
                pair,
                file_duration_s=constants.file_duration_s,
                full_scale_threshold=constants.full_scale_threshold,
                m9_layout=layout,
                cache=cache,
                validation_access=access,
            )
            channels = sorted({channel for _, channel in rows})
            for channel in channels:
                items.append((pair, assemble_pair(pair, rows, channel=channel)))
        run_sanity_checks(
            items,
            file_duration_s=constants.file_duration_s,
            full_scale_threshold=constants.full_scale_threshold,
            m9_layouts=pair_layouts,
            validation_access=access,
        )
    except SanityAbort as error:
        write_abort_record(store, error, stage=side)
        raise
    return items


def _pair_line(
    pair: PairRecord,
    measured: MeasuredPair,
    old_ref: dict[str, Any],
    new_ref: dict[str, Any],
    threshold: float,
) -> dict[str, Any]:
    scored = _scored(pair.model_dump(mode="json"), measured, threshold)
    return {
        "pair_id": pair.pair_id,
        "channel": measured.channel,
        "side": pair.side,
        "kind": pair.kind,
        "family": pair.family,
        "source_group_key": pair.source_group_key,
        "perturbation_code": pair.perturbation_code,
        "perturbation_detail": pair.perturbation_detail,
        "seed": pair.seed,
        "is_combo": pair.is_combo,
        "is_blind": pair.is_blind,
        "is_tolerance": scored.is_tolerance,
        "is_primary": scored.is_primary,
        "old_encoding": pair.old_side.encoding.model_dump(mode="json"),
        "new_encoding": pair.new_side.encoding.model_dump(mode="json"),
        "range_length_s": pair.range_length_s,
        "f0_hz": pair.f0_hz,
        "sample_rate_hz": pair.sample_rate_hz,
        "samples_per_period": pair.sample_rate_hz / pair.f0_hz,
        "periods_in_range": periods_in_range(scored) if scored.measured else None,
        "m7_marked": pair.old_side.effective.m7_marked or pair.new_side.effective.m7_marked,
        "level": pair.old_side.effective.level,
        "old_row": old_ref,
        "new_row": new_ref,
        "count_diff": measured.count_diff,
        "ratio_diff": measured.ratio_diff,
        "flip": measured.flip,
        "terminal_state": measured.terminal_state,
        "terminal_reason": measured.terminal_reason,
    }


def _scored(pair_json: dict[str, Any], measured: MeasuredPair, threshold: float) -> ScoredPair:
    return ScoredPair(
        pair_id=pair_json["pair_id"],
        channel=measured.channel,
        side=pair_json["side"],
        kind=pair_json["kind"],
        family=pair_json["family"],
        perturbation_code=pair_json["perturbation_code"],
        perturbation_detail=pair_json["perturbation_detail"],
        is_tolerance=pair_json["perturbation_code"] in TOLERANCE_CODES,
        is_primary=is_primary_condition(
            pair_json["family"], pair_json["old_side"]["effective"].get("level"), threshold
        ),
        f0_hz=pair_json["f0_hz"],
        sample_rate_hz=pair_json["sample_rate_hz"],
        range_length_s=pair_json["range_length_s"],
        terminal_state=measured.terminal_state,
        old=_side_facts(measured.old_row),
        new=_side_facts(measured.new_row),
    )


def _shard_key(family: str, range_length_s: float) -> str:
    return f"{family}/{encode_range_key(range_length_s)}"


def _write_shards(
    store: CharacterizationStore,
    side: SideName,
    items: Sequence[tuple[PairRecord, MeasuredPair]],
    threshold: float,
    access: ValidationAccess | None,
) -> None:
    """Measurement and pair tables per side x family x range length (A.16).

    Pair lines reference measurement rows as ``{"shard": "<family>/<range key>", "row": n}``.
    """
    rows: dict[tuple[str, float], list[dict[str, Any]]] = {}
    index: dict[tuple[str, float], dict[str, int]] = {}
    pairs: dict[tuple[str, float], list[dict[str, Any]]] = {}

    def row_ref(cell: tuple[str, float], row: MeasurementRow) -> dict[str, Any]:
        line = row.model_dump(mode="json")
        key = json.dumps(line, sort_keys=True)
        cell_index = index.setdefault(cell, {})
        if key not in cell_index:
            cell_index[key] = len(cell_index)
            rows.setdefault(cell, []).append({"row": cell_index[key], **line})
        return {"shard": _shard_key(*cell), "row": cell_index[key]}

    for pair, measured in items:
        cell = (pair.family, pair.range_length_s)
        old_ref = row_ref(cell, measured.old_row)
        new_ref = row_ref(cell, measured.new_row)
        pairs.setdefault(cell, []).append(_pair_line(pair, measured, old_ref, new_ref, threshold))
    for family, length in sorted(pairs):
        store.write_jsonl_gz(
            shard_path(side, "measurements", family, length),
            rows[(family, length)],
            validation_access=access,
        )
        store.write_jsonl_gz(
            shard_path(side, "pairs", family, length),
            pairs[(family, length)],
            validation_access=access,
        )


def _require_absent(store: CharacterizationStore, side: SideName) -> None:
    if store.list_dir(f"{side}_measurements") or store.list_dir(f"{side}_pairs"):
        raise WriteOnceViolation(f"{side} shards already exist")
    if store.exists("abort_record.json"):
        raise WriteOnceViolation("abort_record.json exists; this round was aborted")


def step_calibrate(store: CharacterizationStore) -> None:
    manifest, constants = _checked(store)
    _require_absent(store, "calibration")
    items = _measure_side(store, manifest, constants, "calibration", None)
    _write_shards(store, "calibration", items, constants.full_scale_threshold, None)


def step_validate(store: CharacterizationStore) -> None:
    store.verify_sha256sums()
    manifest, constants = _load_manifest(store)
    access = authorize_validation(store, constants=constants)
    _require_absent(store, "validation")
    items = _measure_side(store, manifest, constants, "validation", access)
    _write_shards(store, "validation", items, constants.full_scale_threshold, access)


def load_scored(store: CharacterizationStore, side: SideName) -> list[ScoredPair]:
    """Rebuild pair records from the sharded measurement and pair tables of one side."""
    tables: dict[str, dict[int, MeasurementRow]] = {}

    def lines(relpath: str) -> list[dict[str, Any]]:
        return [json.loads(line) for line in gzip.decompress(store.read_bytes(relpath)).decode().splitlines()]

    def resolve(ref: dict[str, Any]) -> MeasurementRow:
        shard = ref["shard"]
        if shard not in tables:
            family, key = shard.split("/")
            relpath = shard_path(side, "measurements", family, decode_range_key(key))
            tables[shard] = {
                entry["row"]: MeasurementRow.model_validate({k: v for k, v in entry.items() if k != "row"})
                for entry in lines(relpath)
            }
        return tables[shard][ref["row"]]

    out: list[ScoredPair] = []
    for pairs_path in store.list_dir(f"{side}_pairs"):
        for p in lines(pairs_path):
            out.append(
                ScoredPair(
                    pair_id=p["pair_id"],
                    channel=p["channel"],
                    side=p["side"],
                    kind=p["kind"],
                    family=p["family"],
                    perturbation_code=p["perturbation_code"],
                    perturbation_detail=p["perturbation_detail"],
                    is_tolerance=p["is_tolerance"],
                    is_primary=p["is_primary"],
                    f0_hz=p["f0_hz"],
                    sample_rate_hz=p["sample_rate_hz"],
                    range_length_s=p["range_length_s"],
                    terminal_state=p["terminal_state"],
                    old=_side_facts(resolve(p["old_row"])),
                    new=_side_facts(resolve(p["new_row"])),
                )
            )
    return out


# ---------------------------------------------------------------------------
# reports and freezes


def _stage1_rows(store: CharacterizationStore) -> tuple[Stage1Row, ...]:
    return tuple(Stage1Row.model_validate(r) for r in store.read_json("calibration_report_stage1.json")["rows"])


def step_report_stage1(store: CharacterizationStore) -> None:
    from signal_diag.evaluation.full_scale_characterization.reporting import (
        stage1_report_json,
        stage1_report_markdown,
    )

    _, constants = _checked(store)
    scored = load_scored(store, "calibration")
    if not scored:
        raise ValueError("no calibration shards; run calibrate first")
    rows = fit_stage1(scored, constants=constants)
    store.write_text("calibration_report_stage1.json", stage1_report_json(rows, round_id=constants.round_id))
    store.write_text("calibration_report_stage1.md", stage1_report_markdown(rows, round_id=constants.round_id))


def step_report_stage2(store: CharacterizationStore) -> None:
    from signal_diag.evaluation.full_scale_characterization.reporting import (
        stage2_report_json,
        stage2_report_markdown,
    )

    _, constants = _checked(store)
    if not store.exists(FREEZE_STAGE1):
        raise FileNotFoundError(f"{FREEZE_STAGE1} is required before stage 2")
    stage1 = FreezeStage1.model_validate(store.read_json(FREEZE_STAGE1))
    verify_freeze_stage1(store, stage1)
    selection = selection_from_stage1(stage1)
    rows = fit_stage2(
        load_scored(store, "calibration"),
        selection=selection,
        stage1_rows=_stage1_rows(store),
        constants=constants,
    )
    store.write_text(
        "calibration_report_stage2.json",
        stage2_report_json(rows, round_id=constants.round_id, selection=selection),
    )
    store.write_text(
        "calibration_report_stage2.md",
        stage2_report_markdown(rows, round_id=constants.round_id, selection=selection),
    )


def step_freeze_stage1(
    store: CharacterizationStore, *, zone_row_id: str, rationale: str, approved_by: str, approved_at: str
) -> None:
    _checked(store)
    record = draft_freeze_stage1(
        store, zone_row_id=zone_row_id, rationale=rationale, approved_by=approved_by, approved_at=approved_at
    )
    write_freeze_stage1(store, record)


def step_freeze(
    store: CharacterizationStore, *, floor_row_id: str, rationale: str, approved_by: str, approved_at: str
) -> None:
    _checked(store)
    record = draft_freeze_record(
        store, floor_row_id=floor_row_id, rationale=rationale, approved_by=approved_by, approved_at=approved_at
    )
    write_freeze_record(store, record)


def step_report_validation(store: CharacterizationStore) -> None:
    from signal_diag.evaluation.full_scale_characterization.reporting import (
        validation_report_json,
        validation_report_markdown,
    )

    store.verify_sha256sums()
    _, constants = _load_manifest(store)
    access = authorize_validation(store, constants=constants)
    if not store.list_dir("validation_pairs"):
        raise FileNotFoundError("no validation shards; run validate first")
    freeze = FreezeRecord.model_validate(store.read_json(FREEZE_RECORD))
    result = count_validation(
        load_scored(store, "validation"),
        freeze=freeze,
        validation_access=access,
        calibration_records=load_scored(store, "calibration"),
        constants=constants,
    )
    store.write_text(
        "validation_report.json",
        validation_report_json(result, round_id=constants.round_id),
        validation_access=access,
    )
    store.write_text(
        "validation_report.md",
        validation_report_markdown(result, round_id=constants.round_id),
        validation_access=access,
    )
