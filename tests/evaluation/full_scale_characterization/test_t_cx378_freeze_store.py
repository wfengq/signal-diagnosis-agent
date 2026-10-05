"""T-CX378: write-once store, identity comparison, two-stage freeze, validation gate."""

from __future__ import annotations

import gzip
import json
from functools import cache
from pathlib import Path

import pytest

from signal_diag.evaluation.full_scale_characterization import identity as identity_mod
from signal_diag.evaluation.full_scale_characterization import store as store_mod
from signal_diag.evaluation.full_scale_characterization.checks import (
    measure_pair_checked,
    run_sanity_checks,
)
from signal_diag.evaluation.full_scale_characterization.executor import (
    assemble_pair,
    row_specs_for_pair,
)
from signal_diag.evaluation.full_scale_characterization.fitting import (
    fit_stage1,
    fit_stage2,
)
from signal_diag.evaluation.full_scale_characterization.freeze import (
    FreezeRecord,
    FreezeRejected,
    FreezeStage1,
    authorize_calibration,
    authorize_validation,
    draft_freeze_record,
    draft_freeze_stage1,
    rebuild_with_digest,
    selection_from_stage1,
    verify_freeze_record,
    verify_freeze_stage1,
    write_freeze_record,
    write_freeze_stage1,
)
from signal_diag.evaluation.full_scale_characterization.gate import (
    ValidationAccess,
    ValidationLocked,
)
from signal_diag.evaluation.full_scale_characterization.identity import (
    IdentityMismatch,
    compute_identity,
)
from signal_diag.evaluation.full_scale_characterization.manifest import (
    build_manifest,
    iter_side_pairs,
)
from signal_diag.evaluation.full_scale_characterization.models import Manifest
from signal_diag.evaluation.full_scale_characterization.pairs import (
    _r0_description_records,
)
from signal_diag.evaluation.full_scale_characterization.reporting import (
    stage1_report_json,
    stage1_report_markdown,
    stage2_report_json,
    stage2_report_markdown,
)
from signal_diag.evaluation.full_scale_characterization.store import (
    CharacterizationStore,
    ShardTooLarge,
    StoreIntegrityError,
    WriteOnceViolation,
)
from tests.evaluation.full_scale_characterization.mini_manifest import MINI
from tests.evaluation.full_scale_characterization.test_t_cx377_fitting import (
    _rid,
    _stage2_population,
)

APPROVAL = {"rationale": "test selection", "approved_by": "tester", "approved_at": "2026-10-05T00:00:00Z"}


@cache
def _manifest() -> Manifest:
    return build_manifest(MINI)


def _rows_payload() -> list[dict]:
    return [{"b": 2, "a": 1.5, "pair_id": f"p{i}"} for i in range(50)]


def _calibrated_store(root: Path, *, manifest_round_id: str = "mini") -> CharacterizationStore:
    store = CharacterizationStore(root)
    store.write_json(
        "manifest.json",
        {"manifest": {"round_id": manifest_round_id}, "pairs_list_sha256": "0" * 64},
    )
    store.write_json("identity.json", compute_identity(MINI))
    store.write_jsonl_gz("calibration_measurements/M2.jsonl.gz", _rows_payload())
    store.write_jsonl_gz("calibration_pairs/M2.jsonl.gz", _rows_payload())
    records = _stage2_population()
    rows = fit_stage1(records, constants=MINI)
    store.write_text("calibration_report_stage1.json", stage1_report_json(rows, round_id="mini"))
    store.write_text("calibration_report_stage1.md", stage1_report_markdown(rows, round_id="mini"))
    return store


def _with_stage1(
    root: Path, *, manifest_round_id: str = "mini"
) -> tuple[CharacterizationStore, FreezeStage1]:
    store = _calibrated_store(root, manifest_round_id=manifest_round_id)
    stage1 = draft_freeze_stage1(store, zone_row_id=_rid("K3c8"), **APPROVAL)
    write_freeze_stage1(store, stage1)
    records = _stage2_population()
    rows = fit_stage1(records, constants=MINI)
    selection = selection_from_stage1(stage1)
    stage2 = fit_stage2(records, selection=selection, stage1_rows=rows, constants=MINI)
    store.write_text(
        "calibration_report_stage2.json", stage2_report_json(stage2, round_id="mini", selection=selection)
    )
    store.write_text(
        "calibration_report_stage2.md", stage2_report_markdown(stage2, round_id="mini", selection=selection)
    )
    return store, stage1


def _frozen(root: Path, *, manifest_round_id: str = "mini") -> tuple[CharacterizationStore, FreezeRecord]:
    store, _ = _with_stage1(root, manifest_round_id=manifest_round_id)
    record = draft_freeze_record(store, floor_row_id="F3[periods<20.0|F2]", **APPROVAL)
    write_freeze_record(store, record)
    return store, record


# --- store -------------------------------------------------------------------


def test_t_cx378_store_refuses_to_overwrite_and_sums_match(tmp_path: Path) -> None:
    store = CharacterizationStore(tmp_path)
    store.write_json("manifest.json", {"x": 1})
    with pytest.raises(WriteOnceViolation):
        store.write_json("manifest.json", {"x": 2})
    with pytest.raises(WriteOnceViolation):
        store.write_bytes("manifest.json", b"{}")
    store.write_jsonl_gz("calibration_pairs/M3.jsonl.gz", _rows_payload())
    store.verify_sha256sums()
    sums = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert [line.split("  ")[1] for line in sums] == ["calibration_pairs/M3.jsonl.gz", "manifest.json"]
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == {"x": 1}


def test_t_cx378_store_detects_tampering_and_unlisted_files(tmp_path: Path) -> None:
    store = CharacterizationStore(tmp_path)
    store.write_json("manifest.json", {"x": 1})
    (tmp_path / "manifest.json").write_text('{"x": 9}\n', encoding="utf-8")
    with pytest.raises(StoreIntegrityError):
        store.verify_sha256sums()
    other = CharacterizationStore(tmp_path / "b")
    other.write_json("manifest.json", {"x": 1})
    (tmp_path / "b" / "identity.json").write_text("{}", encoding="utf-8")
    with pytest.raises(StoreIntegrityError):
        other.verify_sha256sums()


def test_t_cx378_store_rejects_paths_outside_layout(tmp_path: Path) -> None:
    store = CharacterizationStore(tmp_path)
    for bad in ("notes.txt", "../manifest.json", "calibration_pairs/../x.jsonl.gz", "SHA256SUMS"):
        with pytest.raises(ValueError):
            store.write_bytes(bad, b"x")


def test_t_cx378_gzip_shards_are_deterministic(tmp_path: Path) -> None:
    a = CharacterizationStore(tmp_path / "a")
    b = CharacterizationStore(tmp_path / "b")
    rows = _rows_payload()
    a.write_jsonl_gz("calibration_measurements/M2.jsonl.gz", rows)
    b.write_jsonl_gz("calibration_measurements/M2.jsonl.gz", [dict(reversed(r.items())) for r in rows])
    raw_a = (tmp_path / "a" / "calibration_measurements/M2.jsonl.gz").read_bytes()
    raw_b = (tmp_path / "b" / "calibration_measurements/M2.jsonl.gz").read_bytes()
    assert raw_a == raw_b
    lines = gzip.decompress(raw_a).decode("utf-8").splitlines()
    assert lines[0] == '{"a":1.5,"b":2,"pair_id":"p0"}'
    with pytest.raises(ValueError):
        a.write_jsonl_gz("calibration_pairs/M2.jsonl.gz", [{"x": float("nan")}])


def test_t_cx378_shard_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_mod, "SHARD_MAX_BYTES", 64)
    store = CharacterizationStore(tmp_path)
    with pytest.raises(ShardTooLarge):
        store.write_jsonl_gz("calibration_measurements/M2.jsonl.gz", _rows_payload())
    assert not (tmp_path / "calibration_measurements/M2.jsonl.gz").exists()
    store.write_jsonl_gz("calibration_measurements/M1.jsonl.gz", [{"a": 1}])


def test_t_cx378_validation_artifacts_need_validation_access(tmp_path: Path) -> None:
    store = CharacterizationStore(tmp_path)
    with pytest.raises(ValidationLocked):
        store.write_jsonl_gz("validation_pairs/M2.jsonl.gz", _rows_payload())
    with pytest.raises(ValidationLocked):
        store.write_text("validation_report.md", "x")


# --- identity ----------------------------------------------------------------


def test_t_cx378_identity_has_comparison_and_record_only_parts() -> None:
    ident = compute_identity(MINI)
    comparison = ident["comparison"]
    assert comparison["full_scale_threshold"] == 0.99
    assert comparison["min_consecutive_samples"] == 2
    assert comparison["analyze_clipping_defaults"]["flat_top_tolerance"] == 1e-4
    assert comparison["analyze_clipping_defaults"]["min_flat_top_samples"] == 3
    assert set(comparison["measurement_closure_sha256"]) == {
        "dsp/full_scale.py", "dsp/clipping.py", "dsp/preprocess.py",
        "tools/regression_full_scale.py", "tools/regression_measurement.py", "tools/service.py",
        "tools/contracts.py", "tools/results.py", "signal/wav.py", "signal/factory.py",
        "signal/segment.py", "signal/models.py",
    }
    package_files = set(comparison["package_files"])
    assert "zone.py" in package_files and "checks.py" in package_files and "freeze.py" in package_files
    assert "reporting.py" not in package_files and "__main__.py" not in package_files
    for key in ("measurement_version", "full_scale_facts_version", "package_sha256", "python_version", "numpy_version"):
        assert comparison[key]
    record_only = ident["record_only"]
    assert set(record_only) == {"git_commit", "contextual_product_tree_sha256", "reporting_sha256", "main_sha256"}


def test_t_cx378_identity_mismatch_blocks_calibration_and_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _ = _frozen(tmp_path)
    authorize_calibration(store, constants=MINI)
    assert isinstance(authorize_validation(store, constants=MINI), ValidationAccess)

    monkeypatch.setattr(identity_mod, "_numpy_version", lambda: "0.0.0")
    with pytest.raises(IdentityMismatch, match="numpy_version"):
        authorize_calibration(store, constants=MINI)
    with pytest.raises(IdentityMismatch, match="numpy_version"):
        authorize_validation(store, constants=MINI)
    monkeypatch.undo()

    real = identity_mod._closure_digests

    def altered() -> dict[str, str]:
        out = dict(real())
        out["dsp/clipping.py"] = "f" * 64
        return out

    monkeypatch.setattr(identity_mod, "_closure_digests", altered)
    with pytest.raises(IdentityMismatch, match="dsp/clipping.py"):
        authorize_calibration(store, constants=MINI)
    monkeypatch.undo()

    monkeypatch.setattr(identity_mod, "_git_commit", lambda: "deadbeef")
    monkeypatch.setattr(identity_mod, "_product_tree_sha256", lambda: "e" * 64)
    authorize_calibration(store, constants=MINI)
    assert isinstance(authorize_validation(store, constants=MINI), ValidationAccess)


def test_t_cx378_git_commit_unavailable_is_recorded_as_null(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_mod, "_git_commit", lambda: None)
    assert compute_identity(MINI)["record_only"]["git_commit"] is None


# --- freeze ------------------------------------------------------------------


def test_t_cx378_freeze_two_parts_round_trip(tmp_path: Path) -> None:
    store, record = _frozen(tmp_path)
    assert record.stage1_digest == record.stage1.digest
    assert record.stage1.zone_row_id == _rid("K3c8")
    assert record.stage1.zone_params.min_counted == 8
    assert record.floor_cut is not None and record.floor_cut.cut == 20.0
    on_disk = FreezeRecord.model_validate(store.read_json("freeze_record.json"))
    assert on_disk == record
    verify_freeze_record(store, record)
    store.verify_sha256sums()
    with pytest.raises(WriteOnceViolation):
        write_freeze_record(store, record)


def test_t_cx378_freeze_digest_is_self_checking() -> None:
    with pytest.raises(ValueError):
        FreezeStage1.model_validate(
            {**_stage1_dict(), "digest": "0" * 64}
        )


def _stage1_dict() -> dict:
    return {
        "round_id": "mini",
        "manifest_sha256": "a" * 64,
        "identity_sha256": "a" * 64,
        "calibration_measurements_sha256": "a" * 64,
        "calibration_pairs_sha256": "a" * 64,
        "stage1_report_sha256": "a" * 64,
        "domain": {"n_min": 480.0, "p_min": 1},
        "zone_form": "K2",
        "zone_row_id": "n=480.0;p=1;K2",
        "zone_params": {"form": "K2", "zone_below": 0.0, "zone_above": 0.0, "min_counted": None},
        **APPROVAL,
        "digest": "0" * 64,
    }


def test_t_cx378_stage1_rejects_upstream_hash_mismatch(tmp_path: Path) -> None:
    store = _calibrated_store(tmp_path)
    stage1 = draft_freeze_stage1(store, zone_row_id=_rid("K2"), **APPROVAL)
    for field in (
        "manifest_sha256",
        "identity_sha256",
        "calibration_measurements_sha256",
        "calibration_pairs_sha256",
        "stage1_report_sha256",
    ):
        with pytest.raises(FreezeRejected, match=field):
            verify_freeze_stage1(store, rebuild_with_digest(stage1, **{field: "b" * 64}))
    verify_freeze_stage1(store, stage1)
    # Disk changed after drafting: the record no longer matches.
    store.write_jsonl_gz("calibration_measurements/M3.jsonl.gz", [{"a": 1}])
    with pytest.raises(FreezeRejected, match="calibration_measurements_sha256"):
        write_freeze_stage1(store, stage1)


def test_t_cx378_stage1_can_only_select_not_edit(tmp_path: Path) -> None:
    store = _calibrated_store(tmp_path)
    with pytest.raises(FreezeRejected):
        draft_freeze_stage1(store, zone_row_id="n=480.0;p=1;K3c3", **APPROVAL)
    stage1 = draft_freeze_stage1(store, zone_row_id=_rid("K3c16", p=5), **APPROVAL)
    assert stage1.zone_form == "K3"
    with pytest.raises(FreezeRejected):
        verify_freeze_stage1(store, rebuild_with_digest(stage1, zone_row_id="n=480.0;p=1;K3c3"))
    edited_zone = stage1.zone_params.model_copy(update={"zone_above": stage1.zone_params.zone_above + 1e-6})
    with pytest.raises(FreezeRejected):
        verify_freeze_stage1(store, rebuild_with_digest(stage1, zone_params=edited_zone))
    with pytest.raises(FreezeRejected):
        verify_freeze_stage1(store, rebuild_with_digest(stage1, zone_form="K2"))
    with pytest.raises(FreezeRejected):
        verify_freeze_stage1(store, rebuild_with_digest(stage1, domain={"n_min": 480.0, "p_min": 1}))


def test_t_cx378_stage2_can_only_select_not_edit(tmp_path: Path) -> None:
    store, _ = _with_stage1(tmp_path)
    with pytest.raises(FreezeRejected):
        draft_freeze_record(store, floor_row_id="F3[periods<3.0|F2]", **APPROVAL)
    record = draft_freeze_record(store, floor_row_id="F2", **APPROVAL)
    verify_freeze_record(store, record)
    edited = record.floor_params.model_copy(update={"value": (record.floor_params.value or 0) + 1})
    with pytest.raises(FreezeRejected):
        verify_freeze_record(store, rebuild_with_digest(record, floor_params=edited))
    f3 = draft_freeze_record(store, floor_row_id="F3[periods<20.0|F1]", **APPROVAL)
    assert f3.floor_cut is not None
    bad_cut = f3.floor_cut.model_copy(update={"cut": 30.0})
    with pytest.raises(FreezeRejected):
        verify_freeze_record(store, rebuild_with_digest(f3, floor_cut=bad_cut))
    with pytest.raises(FreezeRejected):
        verify_freeze_record(store, rebuild_with_digest(record, stage2_report_sha256="c" * 64))


def test_t_cx378_stage2_accepts_only_the_written_stage1(tmp_path: Path) -> None:
    store, stage1 = _with_stage1(tmp_path)
    record = draft_freeze_record(store, floor_row_id="F2", **APPROVAL)
    other_stage1 = rebuild_with_digest(stage1, rationale="different text")
    forged = rebuild_with_digest(record, stage1=other_stage1, stage1_digest=other_stage1.digest)
    with pytest.raises(FreezeRejected):
        verify_freeze_record(store, forged)
    with pytest.raises(ValueError):
        FreezeRecord.model_validate({**record.model_dump(mode="json"), "stage1_digest": "d" * 64})


# --- validation gate ---------------------------------------------------------


def _validation_pair():
    """A validation-side description without access (the manifest stores calibration only)."""
    pair = next(p for p in _manifest().pairs if p.family == "M2" and p.perturbation_code == "P0")
    return pair.model_copy(update={"side": "validation", "pair_id": pair.pair_id + "-v"})


def test_t_cx378_no_freeze_record_locks_validation_entry_points(tmp_path: Path) -> None:
    pair = _validation_pair()
    with pytest.raises(ValidationLocked):
        row_specs_for_pair(pair, file_duration_s=MINI.file_duration_s, full_scale_threshold=0.99, m9_layout=None)
    with pytest.raises(ValidationLocked):
        measure_pair_checked(pair, file_duration_s=MINI.file_duration_s, full_scale_threshold=0.99, m9_layout=None)
    with pytest.raises(ValidationLocked):
        next(iter_side_pairs(_manifest(), MINI, "validation"))
    cal_pair = next(p for p in _manifest().pairs if p.family == "M2")
    calibration = list(iter_side_pairs(_manifest(), MINI, "calibration"))
    assert calibration == list(_manifest().pairs)
    assert row_specs_for_pair(
        cal_pair, file_duration_s=MINI.file_duration_s, full_scale_threshold=0.99, m9_layout=None
    )

    store = _calibrated_store(tmp_path)
    with pytest.raises(ValidationLocked):
        authorize_validation(store, constants=MINI)


def test_t_cx378_stage1_only_still_locks_validation(tmp_path: Path) -> None:
    store, _ = _with_stage1(tmp_path)
    with pytest.raises(ValidationLocked):
        authorize_validation(store, constants=MINI)


def test_t_cx378_full_freeze_unlocks_validation_entry_points(tmp_path: Path) -> None:
    store, _ = _frozen(tmp_path)
    access = authorize_validation(store, constants=MINI)
    pair = _validation_pair()
    rows = measure_pair_checked(
        pair,
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=0.99,
        m9_layout=None,
        validation_access=access,
    )
    measured = assemble_pair(pair, rows, channel="left")
    with pytest.raises(ValidationLocked):
        run_sanity_checks([(pair, measured)], file_duration_s=MINI.file_duration_s, full_scale_threshold=0.99)
    run_sanity_checks(
        [(pair, measured)],
        file_duration_s=MINI.file_duration_s,
        full_scale_threshold=0.99,
        validation_access=access,
    )
    pairs = list(iter_side_pairs(_manifest(), MINI, "validation", validation_access=access))
    excluded = {e.pair_id for e in _manifest().excluded_near_duplicates}
    expected = [
        p
        for p in _r0_description_records(_manifest().source_groups, MINI)
        if p.side == "validation" and p.pair_id not in excluded
    ]
    assert pairs == expected
    store.write_jsonl_gz("validation_pairs/M2.jsonl.gz", [{"a": 1}], validation_access=access)
    with pytest.raises(TypeError):
        ValidationAccess("x" * 64)  # type: ignore[call-arg]


def test_t_cx378_tampered_freeze_record_locks_validation(tmp_path: Path) -> None:
    store, _ = _frozen(tmp_path)
    path = tmp_path / "freeze_record.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rationale"] = "edited after the fact"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((ValidationLocked, StoreIntegrityError, FreezeRejected)):
        authorize_validation(store, constants=MINI)


def _rewrite_consistently(store: CharacterizationStore, relpath: str, payload: dict) -> None:
    """Replace an artifact and its SHA256SUMS line so only semantic checks can catch it."""
    from signal_diag.evaluation.full_scale_characterization.store import (
        canonical_json_document,
        sha256_bytes,
    )

    data = canonical_json_document(payload).encode("utf-8")
    (store.root / relpath).write_bytes(data)
    sums = store.read_sums()
    sums[relpath] = sha256_bytes(data)
    (store.root / "SHA256SUMS").write_text(
        "".join(f"{sums[p]}  {p}\n" for p in sorted(sums)), encoding="utf-8"
    )
    store.verify_sha256sums()


def test_t_cx378_consistently_rewritten_freeze_record_is_rejected(tmp_path: Path) -> None:
    store, record = _frozen(tmp_path)
    other_stage1 = rebuild_with_digest(record.stage1, rationale="rewritten after the fact")
    forged = rebuild_with_digest(record, stage1=other_stage1, stage1_digest=other_stage1.digest)
    _rewrite_consistently(store, "freeze_record.json", forged.model_dump(mode="json"))
    with pytest.raises(FreezeRejected):
        authorize_validation(store, constants=MINI)


def test_t_cx378_consistently_rewritten_floor_is_rejected(tmp_path: Path) -> None:
    store, record = _frozen(tmp_path)
    edited = record.floor_params.model_copy(
        update={"value_below_cut": (record.floor_params.value_below_cut or 0.0) + 5.0}
    )
    forged = rebuild_with_digest(record, floor_params=edited)
    _rewrite_consistently(store, "freeze_record.json", forged.model_dump(mode="json"))
    with pytest.raises(FreezeRejected):
        authorize_validation(store, constants=MINI)
