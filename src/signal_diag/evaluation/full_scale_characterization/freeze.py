"""Two-part freeze record and run authorisation (plan A.14, C.5, Task 7; T-CX378).

Part one fixes the (domain, K row) selected from the stage-1 output; part two
fixes the F row selected from the stage-2 output.  Both parts can only *select*
fitted rows: parameters must equal the fitted output field by field, and every
upstream artifact hash must match the files on disk.  Validation-side work is
unlocked only by :func:`authorize_validation` on a complete, verified record.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
)
from signal_diag.evaluation.full_scale_characterization.fitting import (
    Stage1Row,
    Stage1Selection,
    Stage2Row,
    select_stage1,
)
from signal_diag.evaluation.full_scale_characterization.gate import (
    ValidationAccess,
    ValidationLocked,
    issue_validation_access,
)
from signal_diag.evaluation.full_scale_characterization.identity import (
    assert_identity_matches,
    compute_identity,
)
from signal_diag.evaluation.full_scale_characterization.store import (
    CharacterizationStore,
)
from signal_diag.evaluation.full_scale_characterization.zone import (
    CutVariable,
    F3Base,
    FloorForm,
    FloorParams,
    ZoneForm,
    ZoneParams,
)

STAGE1_REPORT = "calibration_report_stage1.json"
STAGE2_REPORT = "calibration_report_stage2.json"
FREEZE_STAGE1 = "freeze_record_stage1.json"
FREEZE_RECORD = "freeze_record.json"

_SHA = r"^[0-9a-f]{64}$"


class FreezeRejected(ValueError):
    """A freeze record does not match the artifacts or fitted output on disk."""


def _digest_of(model: BaseModel) -> str:
    payload = model.model_dump(mode="json", exclude={"digest"})
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FreezeDomain(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    n_min: float
    p_min: int


class FloorCut(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    variable: CutVariable
    cut: float
    base: F3Base


class FreezeStage1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    round_id: str
    manifest_sha256: str = Field(pattern=_SHA)
    identity_sha256: str = Field(pattern=_SHA)
    calibration_measurements_sha256: str = Field(pattern=_SHA)
    calibration_pairs_sha256: str = Field(pattern=_SHA)
    stage1_report_sha256: str = Field(pattern=_SHA)
    domain: FreezeDomain
    zone_form: ZoneForm
    zone_row_id: str
    zone_params: ZoneParams
    rationale: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_at: str = Field(min_length=1)
    digest: str = Field(pattern=_SHA)

    @model_validator(mode="after")
    def _check_digest(self) -> FreezeStage1:
        if self.digest != _digest_of(self):
            raise ValueError("freeze stage-1 digest mismatch")
        return self


class FreezeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage1: FreezeStage1
    stage1_digest: str = Field(pattern=_SHA)
    stage2_report_sha256: str = Field(pattern=_SHA)
    floor_form: FloorForm
    floor_cut: FloorCut | None
    floor_params: FloorParams
    rationale: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_at: str = Field(min_length=1)
    digest: str = Field(pattern=_SHA)

    @model_validator(mode="after")
    def _check_digest(self) -> FreezeRecord:
        if self.stage1_digest != self.stage1.digest:
            raise ValueError("stage1_digest does not match the embedded stage-1 record")
        if self.digest != _digest_of(self):
            raise ValueError("freeze record digest mismatch")
        return self


_M = TypeVar("_M", FreezeStage1, FreezeRecord)


def rebuild_with_digest(record: _M, **updates: Any) -> _M:
    """Copy with updates and a recomputed digest; every field is re-validated."""
    fields = record.model_dump(mode="python", exclude={"digest"})
    for key, value in updates.items():
        fields[key] = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
    return _with_digest(type(record), fields)


class _Stage1Body(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    round_id: str
    manifest_sha256: str
    identity_sha256: str
    calibration_measurements_sha256: str
    calibration_pairs_sha256: str
    stage1_report_sha256: str
    domain: FreezeDomain
    zone_form: ZoneForm
    zone_row_id: str
    zone_params: ZoneParams
    rationale: str
    approved_by: str
    approved_at: str


class _RecordBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage1: FreezeStage1
    stage1_digest: str
    stage2_report_sha256: str
    floor_form: FloorForm
    floor_cut: FloorCut | None
    floor_params: FloorParams
    rationale: str
    approved_by: str
    approved_at: str


_mirrors: dict[type[BaseModel], type[BaseModel]] = {
    FreezeStage1: _Stage1Body,
    FreezeRecord: _RecordBody,
}


def _with_digest(cls: type[_M], fields: dict[str, Any]) -> _M:
    body = _mirrors[cls].model_validate(fields)
    return cls.model_validate({**body.model_dump(mode="python"), "digest": _digest_of(body)})


# ---------------------------------------------------------------------------
# Upstream hashes and fitted output


def _upstream_stage1_hashes(store: CharacterizationStore) -> dict[str, str]:
    return {
        "manifest_sha256": store.file_sha256("manifest.json"),
        "identity_sha256": store.file_sha256("identity.json"),
        "calibration_measurements_sha256": store.directory_sha256("calibration_measurements"),
        "calibration_pairs_sha256": store.directory_sha256("calibration_pairs"),
        "stage1_report_sha256": store.file_sha256(STAGE1_REPORT),
    }


def _stage1_rows(store: CharacterizationStore) -> tuple[Stage1Row, ...]:
    report = store.read_json(STAGE1_REPORT)
    return tuple(Stage1Row.model_validate(r) for r in report["rows"])


def _stage2_report(store: CharacterizationStore) -> tuple[Stage1Selection, tuple[Stage2Row, ...]]:
    report = store.read_json(STAGE2_REPORT)
    selection = Stage1Selection.model_validate(report["stage1_selection"])
    rows = tuple(Stage2Row.model_validate(r) for r in report["rows"])
    return selection, rows


def selection_from_stage1(record: FreezeStage1) -> Stage1Selection:
    return Stage1Selection(
        row_id=record.zone_row_id,
        n_min=record.domain.n_min,
        p_min=record.domain.p_min,
        k_row=record.zone_row_id.rsplit(";", 1)[-1],
        zone=record.zone_params,
    )


def _floor_cut_of(floor: FloorParams) -> FloorCut | None:
    if floor.form != "F3":
        return None
    assert floor.cut_variable is not None and floor.cut is not None and floor.f3_base is not None
    return FloorCut(variable=floor.cut_variable, cut=floor.cut, base=floor.f3_base)


# ---------------------------------------------------------------------------
# Stage 1


def draft_freeze_stage1(
    store: CharacterizationStore,
    *,
    zone_row_id: str,
    rationale: str,
    approved_by: str,
    approved_at: str,
) -> FreezeStage1:
    """Build part one from the stage-1 output on disk (selection only)."""
    try:
        selection = select_stage1(_stage1_rows(store), zone_row_id)
    except ValueError as error:
        raise FreezeRejected(str(error)) from error
    return _with_digest(
        FreezeStage1,
        {
            "round_id": store.read_json(STAGE1_REPORT)["round_id"],
            **_upstream_stage1_hashes(store),
            "domain": FreezeDomain(n_min=selection.n_min, p_min=selection.p_min),
            "zone_form": selection.zone.form,
            "zone_row_id": selection.row_id,
            "zone_params": selection.zone,
            "rationale": rationale,
            "approved_by": approved_by,
            "approved_at": approved_at,
        },
    )


def verify_freeze_stage1(store: CharacterizationStore, record: FreezeStage1) -> None:
    actual = _upstream_stage1_hashes(store)
    for key, value in actual.items():
        if getattr(record, key) != value:
            raise FreezeRejected(f"{key} does not match the file on disk")
    try:
        fitted = select_stage1(_stage1_rows(store), record.zone_row_id)
    except ValueError as error:
        raise FreezeRejected(str(error)) from error
    if fitted != selection_from_stage1(record) or record.zone_form != fitted.zone.form:
        raise FreezeRejected(
            f"stage-1 record for {record.zone_row_id!r} differs from the fitted row; "
            "parameters can only be selected, not edited"
        )


def write_freeze_stage1(store: CharacterizationStore, record: FreezeStage1) -> None:
    verify_freeze_stage1(store, record)
    store.write_json(FREEZE_STAGE1, record)


def _read_stage1(store: CharacterizationStore) -> FreezeStage1:
    try:
        return FreezeStage1.model_validate(store.read_json(FREEZE_STAGE1))
    except ValidationError as error:
        raise FreezeRejected(f"{FREEZE_STAGE1} is invalid: {error}") from error


# ---------------------------------------------------------------------------
# Stage 2


def draft_freeze_record(
    store: CharacterizationStore,
    *,
    floor_row_id: str,
    rationale: str,
    approved_by: str,
    approved_at: str,
) -> FreezeRecord:
    """Build the complete record from the written part one and the stage-2 output."""
    stage1 = _read_stage1(store)
    _, rows = _stage2_report(store)
    row = next((r for r in rows if r.row_id == floor_row_id), None)
    if row is None:
        raise FreezeRejected(f"stage-2 row {floor_row_id!r} is not in the stage-2 output")
    return _with_digest(
        FreezeRecord,
        {
            "stage1": stage1,
            "stage1_digest": stage1.digest,
            "stage2_report_sha256": store.file_sha256(STAGE2_REPORT),
            "floor_form": row.floor.form,
            "floor_cut": _floor_cut_of(row.floor),
            "floor_params": row.floor,
            "rationale": rationale,
            "approved_by": approved_by,
            "approved_at": approved_at,
        },
    )


def verify_freeze_record(store: CharacterizationStore, record: FreezeRecord) -> None:
    written_stage1 = _read_stage1(store)
    if record.stage1 != written_stage1 or record.stage1_digest != written_stage1.digest:
        raise FreezeRejected("part two does not embed the written part one")
    verify_freeze_stage1(store, record.stage1)
    if record.stage2_report_sha256 != store.file_sha256(STAGE2_REPORT):
        raise FreezeRejected("stage2_report_sha256 does not match the file on disk")
    report_selection, rows = _stage2_report(store)
    if report_selection != selection_from_stage1(record.stage1):
        raise FreezeRejected("stage-2 output was fitted for a different stage-1 selection")
    matches = [r for r in rows if r.floor == record.floor_params]
    if not matches:
        raise FreezeRejected("floor parameters are not a fitted stage-2 row")
    if record.floor_form != record.floor_params.form:
        raise FreezeRejected("floor_form differs from the selected row")
    if record.floor_cut != _floor_cut_of(record.floor_params):
        raise FreezeRejected("floor_cut is not the selected row's F3 cut")


def write_freeze_record(store: CharacterizationStore, record: FreezeRecord) -> None:
    verify_freeze_record(store, record)
    store.write_json(FREEZE_RECORD, record)


# ---------------------------------------------------------------------------
# Run authorisation


def authorize_calibration(
    store: CharacterizationStore, *, constants: CharacterizationConstants = ROUND_1
) -> None:
    """Refuse calibration when identity comparison items differ."""
    assert_identity_matches(store.read_json("identity.json"), compute_identity(constants))


def authorize_validation(
    store: CharacterizationStore, *, constants: CharacterizationConstants = ROUND_1
) -> ValidationAccess:
    """Issue validation access only for a complete, verified two-part freeze record."""
    if not store.exists(FREEZE_RECORD):
        part = "only part one" if store.exists(FREEZE_STAGE1) else "no freeze record"
        raise ValidationLocked(f"validation locked: {part} present")
    store.verify_sha256sums()
    assert_identity_matches(store.read_json("identity.json"), compute_identity(constants))
    try:
        record = FreezeRecord.model_validate(store.read_json(FREEZE_RECORD))
    except ValidationError as error:
        raise ValidationLocked(f"{FREEZE_RECORD} is invalid: {error}") from error
    verify_freeze_record(store, record)
    return issue_validation_access(record.digest, record.stage1.round_id)


__all__ = [
    "FloorCut",
    "FreezeDomain",
    "FreezeRecord",
    "FreezeRejected",
    "FreezeStage1",
    "authorize_calibration",
    "authorize_validation",
    "draft_freeze_record",
    "draft_freeze_stage1",
    "rebuild_with_digest",
    "selection_from_stage1",
    "verify_freeze_record",
    "verify_freeze_stage1",
    "write_freeze_record",
    "write_freeze_stage1",
]

