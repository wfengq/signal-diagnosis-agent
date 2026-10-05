"""T-CX379: validation-side counting, disclosures, abort record, report wording."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import pytest

from signal_diag.evaluation.full_scale_characterization.checks import (
    measure_pair_checked,
)
from signal_diag.evaluation.full_scale_characterization.executor import assemble_pair
from signal_diag.evaluation.full_scale_characterization.freeze import (
    FreezeRecord,
    authorize_validation,
)
from signal_diag.evaluation.full_scale_characterization.gate import ValidationLocked
from signal_diag.evaluation.full_scale_characterization.manifest import (
    build_manifest,
    iter_side_pairs,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    Manifest,
    SanityAbort,
)
from signal_diag.evaluation.full_scale_characterization.reporting import (
    validation_report_json,
    validation_report_markdown,
)
from signal_diag.evaluation.full_scale_characterization.store import (
    WriteOnceViolation,
)
from signal_diag.evaluation.full_scale_characterization.validation import (
    AggravationTierCounts,
    ValidationResult,
    count_validation,
    finalize_validation,
    minimum_detectable_tier,
)
from signal_diag.evaluation.full_scale_characterization.zone import ScoredPair
from tests.evaluation.full_scale_characterization.mini_manifest import MINI
from tests.evaluation.full_scale_characterization.test_t_cx377_fitting import (
    THR,
    _stage2_population,
    rec,
)
from tests.evaluation.full_scale_characterization.test_t_cx378_freeze_store import (
    _frozen,
)

FORBIDDEN = (
    "rank", "recommend", "pass", "best", "通过", "推荐", "排名", "最佳", "regression detected", "合格",
)


def _v(*args, **kwargs) -> ScoredPair:
    return rec(*args, side="validation", **kwargs)


@cache
def _manifest() -> Manifest:
    return build_manifest(MINI)


@pytest.fixture
def frozen(tmp_path: Path):
    store, record = _frozen(tmp_path)
    access = authorize_validation(store, constants=MINI)
    return store, record, access


def _clean_population() -> list[ScoredPair]:
    return [
        _v(("yes", 1.0, 400), ("yes", 1.0, 404), code="P7d", family="M3"),
        _v(("yes", 1.0, 400), ("yes", 1.0, 410), code="P4", family="M3"),  # |10| is not > 10
        _v(("no", 0.5, 0), ("no", 0.5, 0), code="P0", family="M1"),
    ]


def _count(records: list[ScoredPair], frozen) -> ValidationResult:
    _, record, access = frozen
    return count_validation(
        records,
        freeze=record,
        validation_access=access,
        calibration_records=_stage2_population(),
        constants=MINI,
    )


def test_t_cx379_frozen_fixture_values(frozen) -> None:
    _, record, _ = frozen
    assert isinstance(record, FreezeRecord)
    assert record.floor_params.form == "F3"
    assert record.floor_params.cut_variable == "periods" and record.floor_params.cut == 20.0
    assert record.floor_params.value_below_cut == 10.0
    assert record.stage1.zone_params.min_counted == 8


def test_t_cx379_clean_population_meets_hard_conditions(frozen) -> None:
    result = _count(_clean_population(), frozen)
    assert result.hard_conditions_met
    assert result.hard_condition_1.violation_count == 0
    assert result.hard_condition_2.violation_count == 0
    assert result.hard_condition_2.applicable_pairs == 2


def test_t_cx379_hard_condition_1_violation_is_listed(frozen) -> None:
    flip = _v(("no", 0.9, 0), ("yes", 1.0, 50), code="P7d", family="M2")
    result = _count([*_clean_population(), flip], frozen)
    assert not result.hard_conditions_met
    assert [v.pair_id for v in result.hard_condition_1.violations] == [flip.pair_id]
    assert result.hard_condition_2.violation_count == 0


def test_t_cx379_hard_condition_2_uses_absolute_difference_and_f3_segment(frozen) -> None:
    negative = _v(("yes", 1.0, 400), ("yes", 1.0, 389), code="P4", family="M3")  # |-11| > 10
    long_range = _v(("yes", 1.0, 400), ("yes", 1.0, 407), code="P9c", family="M3", analyzed=9600)  # 7 > 6
    within = _v(("yes", 1.0, 400), ("yes", 1.0, 406), code="P9a", family="M3", analyzed=9600)
    result = _count([*_clean_population(), negative, long_range, within], frozen)
    assert not result.hard_conditions_met
    ids = [v.pair_id for v in result.hard_condition_2.violations]
    assert ids == sorted([negative.pair_id, long_range.pair_id])
    by_id = {v.pair_id: v for v in result.hard_condition_2.violations}
    assert by_id[negative.pair_id].count_diff == -11
    assert by_id[negative.pair_id].floor_value == 10.0
    assert by_id[long_range.pair_id].floor_value == 6.0


def test_t_cx379_flip_in_zone_excluded_and_out_of_domain_listed(frozen) -> None:
    in_zone_flip = _v(("no", THR - 0.001, 0), ("yes", 1.0, 50), code="P7a", family="M2")
    out_dom = _v(("no", 0.9, 0), ("yes", 1.0, 50), code="P7b", family="M2", f0=200.0)
    result = _count([*_clean_population(), in_zone_flip, out_dom], frozen)
    assert result.hard_conditions_met
    assert result.excluded_by_reason["flip_in_zone"] == 1
    assert result.excluded_by_reason["out_of_domain"] == 1
    assert list(result.out_of_domain_cells.values()) == [1]
    (cell,) = result.out_of_domain_cells
    assert "M2" in cell and "f0=200.0" in cell


def test_t_cx379_minimum_detectable_change_by_tier() -> None:
    def tier(judged: int, masked: int) -> AggravationTierCounts:
        return AggravationTierCounts(total=judged, judged=judged, masked=masked, detected=judged - masked)

    tiers = {
        "rel_peak=0.0001": tier(2, 2),
        "rel_peak=0.001": tier(2, 1),
        "rel_peak=0.01": tier(2, 0),
        "rel_peak=0.05": tier(2, 0),
        "rel_peak=0.1": tier(2, 0),
    }
    assert minimum_detectable_tier(tiers) == "rel_peak=0.01"
    tiers["rel_peak=0.05"] = tier(2, 1)
    assert minimum_detectable_tier(tiers) == "rel_peak=0.1"
    tiers["rel_peak=0.1"] = tier(2, 1)
    assert minimum_detectable_tier(tiers) is None
    tiers["rel_peak=0.1"] = tier(0, 0)
    assert minimum_detectable_tier(tiers) is None


def _disclosure_population() -> tuple[list[ScoredPair], dict[str, ScoredPair]]:
    named = {
        "sens": _v(("no", 0.9, 0), ("yes", 1.0, 30), code="P5", family="M2", detail="gain=0.01"),
        "combo": _v(("yes", 1.0, 400), ("yes", 1.0, 480), code="COMBO_P4_P5", family="M3"),
        "p8": _v(("yes", 1.0, 400), ("yes", 1.0, 300), code="P8", family="M3"),
        "blind": _v(("no", 0.98, 0), ("no", 0.98, 0), code="BLIND_SUB", family="M4", kind="blind_change", detail="sublevel"),
        "onset_hit": _v(("no", 0.9, 0), ("yes", 0.995, 50), code="ONSET", family="M1", kind="onset_change", detail="level=0.9901;depth=0.9"),
        "onset_zone": _v(("no", 0.9, 0), ("yes", THR + 0.0001, 2), code="ONSET", family="M1", kind="onset_change", detail="level=0.995;depth=0.9999"),
        "aggr_small": _v(("yes", 1.0, 400), ("yes", 1.0, 403), code="AGGR", family="M3", kind="aggravation_change", detail="rel_peak=0.0001"),
        "aggr_big": _v(("yes", 1.0, 400), ("yes", 1.0, 480), code="AGGR", family="M3", kind="aggravation_change", detail="rel_peak=0.1"),
        "unseen": _v(("no", THR - 1.5 * 2**-15, 0), ("yes", THR + 0.0005, 3), code="P9b", family="M2"),
    }
    return [*_clean_population(), *named.values()], named


def test_t_cx379_disclosures_are_complete_and_kept_out_of_hard_conditions(frozen) -> None:
    records, named = _disclosure_population()
    result = _count(records, frozen)
    hard_ids = {v.pair_id for v in result.hard_condition_1.violations} | {
        v.pair_id for v in result.hard_condition_2.violations
    }
    for key in ("sens", "combo", "p8", "blind", "onset_hit", "onset_zone", "aggr_small", "aggr_big"):
        assert named[key].pair_id not in hard_ids
    assert result.hard_conditions_met

    d = result.disclosures
    assert set(d.sensitivity_by_code) == {"P5", "COMBO_P4_P5", "P8"}
    assert d.sensitivity_by_code["P5"].flips == 1
    assert d.sensitivity_by_code["P8"].count_diff_min == -100
    assert d.sensitivity_by_code["COMBO_P4_P5"].count_diff_max == 80
    assert "P5" in d.p5_near_reproduction_note
    assert [b.pair_id for b in d.blind_changes] == [named["blind"].pair_id]
    assert d.onset_by_tier["level=0.9901;depth=0.9"].detected_outside_zone == 1
    assert d.onset_by_tier["level=0.995;depth=0.9999"].in_zone_no_judgment == 1
    assert d.aggravation_by_tier["rel_peak=0.0001"].masked == 1
    assert d.aggravation_by_tier["rel_peak=0.1"].detected == 1
    assert d.minimum_detectable_tier == "rel_peak=0.1"
    assert "M3" in d.coverage_by_family
    assert [u.pair_id for u in d.flips_unseen_in_calibration] == [named["unseen"].pair_id]
    assert d.fixed_minimum_flips_by_code["P9b"].model_dump() == {"flips": 1, "outside_k1": 1, "outside_k2": 0}
    assert "M11" in d.m11_note
    assert "declared" in d.fundamental_source_note

    md = validation_report_markdown(result, round_id="mini")
    js = validation_report_json(result, round_id="mini")
    hard_part, disclosure_part = md.split("## Disclosures", 1)
    for key in ("sens", "combo", "p8", "blind"):
        assert named[key].pair_id not in hard_part
    for heading in (
        "Out-of-domain cells",
        "Sensitivity pairs",
        "P5 near-reproduction",
        "Blind-spot change pairs",
        "Coverage by family",
        "Onset change pairs",
        "Aggravation change pairs",
        "Minimum detectable change",
        "Flips not seen in calibration",
        "Fixed minimum k=1 / k=2",
        "M11",
        "Fundamental source",
    ):
        assert heading in disclosure_part, heading
    payload = json.loads(js)
    assert set(payload) >= {"hard_condition_1", "hard_condition_2", "disclosures", "hard_conditions_met"}
    for text in (md, js):
        lowered = text.lower()
        for word in FORBIDDEN:
            assert word not in lowered, word


def test_t_cx379_count_requires_validation_access(frozen, tmp_path: Path) -> None:
    _, record, access = frozen
    with pytest.raises(ValidationLocked):
        count_validation(
            _clean_population(), freeze=record, validation_access=None,
            calibration_records=[], constants=MINI,
        )
    other_store, _ = _frozen(tmp_path / "other")
    other_access = authorize_validation(other_store, constants=MINI)
    forged = record.model_copy(update={"digest": "f" * 64})
    with pytest.raises(ValidationLocked):
        count_validation(
            _clean_population(), freeze=forged, validation_access=other_access,
            calibration_records=[], constants=MINI,
        )
    with pytest.raises(ValueError):
        count_validation(
            [rec(("no", 0.5, 0), ("no", 0.5, 0))], freeze=record, validation_access=access,
            calibration_records=[], constants=MINI,
        )


def _measured_validation_p0(access):
    pair = next(
        p for p in iter_side_pairs(_manifest(), MINI, "validation", validation_access=access)
        if p.family == "M3" and p.perturbation_code == "P0"
    )
    rows = measure_pair_checked(
        pair, file_duration_s=MINI.file_duration_s, full_scale_threshold=0.99, m9_layout=None,
        validation_access=access,
    )
    return pair, assemble_pair(pair, rows, channel="left")


def test_t_cx379_finalize_writes_report_once(frozen) -> None:
    store, record, access = frozen
    pair, measured = _measured_validation_p0(access)
    result = finalize_validation(
        store, freeze=record, validation_access=access, items=[(pair, measured)],
        calibration_records=_stage2_population(), constants=MINI,
    )
    assert result.hard_conditions_met
    assert store.exists("validation_report.json") and store.exists("validation_report.md")
    assert not store.exists("abort_record.json")
    store.verify_sha256sums()
    with pytest.raises(WriteOnceViolation):
        finalize_validation(
            store, freeze=record, validation_access=access, items=[(pair, measured)],
            calibration_records=_stage2_population(), constants=MINI,
        )


def test_t_cx379_sanity_abort_writes_abort_record_and_no_report(frozen) -> None:
    store, record, access = frozen
    pair, measured = _measured_validation_p0(access)
    tampered = measured.model_copy(
        update={"new_row": measured.new_row.model_copy(update={"wav_sha256": "f" * 64})}
    )
    with pytest.raises(SanityAbort):
        finalize_validation(
            store, freeze=record, validation_access=access, items=[(pair, tampered)],
            calibration_records=_stage2_population(), constants=MINI,
        )
    assert not store.exists("validation_report.json")
    assert not store.exists("validation_report.md")
    abort = store.read_json("abort_record.json")
    assert abort["stage"] == "validation"
    assert abort["pair_id"] == pair.pair_id
    assert abort["check"].startswith("C.2#1")
    assert "wav_sha256" in abort["values"]
    store.verify_sha256sums()
    with pytest.raises(WriteOnceViolation):
        finalize_validation(
            store, freeze=record, validation_access=access, items=[(pair, tampered)],
            calibration_records=_stage2_population(), constants=MINI,
        )
