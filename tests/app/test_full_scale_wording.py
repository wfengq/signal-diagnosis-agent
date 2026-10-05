"""T-CX354–T-CX355: fixed full-scale check wording."""

from signal_diag.app.full_scale_wording import (
    CLIPPING_RATIO_NOTICE,
    FULL_SCALE_TEMPLATES,
    full_scale_check_lines,
)
from signal_diag.rules.full_scale_check import evaluate_full_scale_check
from tests.rules.full_scale_fixtures import FIXTURE_FLOOR, eligible


def _record(**kw):
    floor = kw.pop("floor", FIXTURE_FLOOR)
    anchor, repeats = eligible(**kw)
    return evaluate_full_scale_check(
        check_id="chk_1",
        anchor=anchor,
        repeats=repeats,
        floor=floor,
        supersedes=None,
    )


def test_t_cx355_templates_never_say_clip() -> None:
    for key, text in FULL_SCALE_TEMPLATES.items():
        assert "clip" not in text.replace("clipping_ratio", "").lower(), key
    assert "clip" not in CLIPPING_RATIO_NOTICE.replace("clipping_ratio", "").lower()


def test_t_cx355_regression_lines() -> None:
    lines = full_scale_check_lines(_record(baseline=(0, 0.5), candidate=(2000, 0.995)))
    assert lines[0] == "Samples reaching the full-scale threshold increased."
    assert FULL_SCALE_TEMPLATES["notice.export_settings"] in lines
    assert FULL_SCALE_TEMPLATES["notice.declared"] in lines
    assert lines[-1] == FULL_SCALE_TEMPLATES["notice.coverage"]
    assert (
        "Baseline: 0 samples, peak 0.500000. Candidate: 2000 samples, peak 0.994995." in lines
    )
    assert "Based on 2 consistent baseline render(s) and 2 consistent candidate render(s)." in lines


def test_t_cx353_increase_within_floor_is_not_called_no_increase() -> None:
    lines = full_scale_check_lines(_record(baseline=(2000, 0.995), candidate=(2010, 0.995)))
    assert lines[0] == FULL_SCALE_TEMPLATES["status.no_regression_detected.within_floor"]
    assert "Difference 10 samples; method floor 10 samples." in lines


def test_t_cx358_359_uncounted_identical_and_inconsistent_lines() -> None:
    rec = _record(
        baseline=(0, 0.5),
        candidate=(2000, 0.995),
        repeat_candidate=(2400, 0.995),
        drop_repeats=None,
    )
    lines = full_scale_check_lines(rec)
    assert (
        "Renders declared deterministic differ on the candidate side: 2000 / 2400 samples."
        in lines
    )
    assert "Repeat r1 (baseline) is byte-identical to the original file." in lines
    assert not any(line.startswith("Based on ") for line in lines)
    one_side = _record(baseline=(0, 0.5), candidate=(2000, 0.995), drop_repeats="candidate")
    assert (
        "Repeat r1 (candidate) is not counted: not_declared_independent."
        in full_scale_check_lines(one_side)
    )


def test_t_cx354_decrease_notice_is_on_the_status_line() -> None:
    lines = full_scale_check_lines(_record(baseline=(2000, 0.995), candidate=(0, 0.5)))
    assert (
        lines[0]
        == "Samples reaching the full-scale threshold decreased: 2000 to 0. No cause is stated."
    )


def test_no_floor_record_lines() -> None:
    lines = full_scale_check_lines(
        _record(baseline=(0, 0.5), candidate=(2000, 0.995), floor=None)
    )
    assert lines[0].startswith("Descriptive only.")
    assert FULL_SCALE_TEMPLATES["notice.no_floor"] in lines
    assert any(line.startswith("Conditions not evaluated") for line in lines)


def test_9d_declared_notice_on_no_regression_detected() -> None:
    lines = full_scale_check_lines(_record(baseline=(0, 0.5), candidate=(0, 0.6)))
    assert lines[0] == FULL_SCALE_TEMPLATES["status.no_regression_detected.no_increase"]
    assert FULL_SCALE_TEMPLATES["notice.declared"] in lines
