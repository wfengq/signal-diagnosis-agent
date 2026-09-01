"""Checkpoint H — delayed blind review (EV-T036–EV-T039)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from signal_diag.evaluation.external.models import (
    ExternalCase,
    ReferenceSummary,
    ReviewRecord,
    ReviewRound,
)
from signal_diag.evaluation.external.review import (
    build_blind_package,
    resolve_adjudicated_confidence,
    score_delayed_review,
)
from tests.evaluation.external.conftest import make_external_case, make_transform
from tests.evaluation.external.test_validation import (
    build_valid_manifest,
    materialize_manifest_assets,
)

UTC_NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
ROUND1_START = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _reference_summary(*, applicable: bool = True) -> ReferenceSummary:
    return ReferenceSummary(
        input_sha256="a" * 64,
        applicable=applicable,
        clipping_ratio=0.02 if applicable else None,
        flat_top_detected=False if applicable else None,
        f0_hz=220.0 if applicable else None,
        thd_percent=1.5 if applicable else None,
        order_2_relative_amplitude=0.1 if applicable else None,
    )


def _review_record(
    *,
    case_id: str,
    round_number: int,
    outcome: str = "supported_fault",
    causal_faults: tuple[str, ...] = ("clipping",),
    confidence: str = "strong_ground_truth",
    reviewed_at: datetime | None = None,
) -> ReviewRecord:
    return ReviewRecord(
        review_alias=f"alias_{case_id}",
        case_id=case_id,
        round_number=round_number,  # type: ignore[arg-type]
        outcome=outcome,  # type: ignore[arg-type]
        causal_faults=causal_faults,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        applicability="applicable",
        reason_codes=(),
        reviewed_at_utc=reviewed_at or ROUND1_START,
    )


def _round1_records(
    manifest_cases: tuple[ExternalCase, ...],
) -> tuple[ReviewRecord, ...]:
    return tuple(
        _review_record(
            case_id=case.case_id,
            round_number=1,
            outcome=case.acceptable_outcomes[0]
            if case.acceptable_outcomes
            else "inconclusive",
            causal_faults=case.causal_faults,
            confidence=case.confidence,
            reviewed_at=ROUND1_START + timedelta(hours=index),
        )
        for index, case in enumerate(manifest_cases)
    )


def _round2_records(
    manifest_cases: tuple[ExternalCase, ...],
    *,
    days_after: int = 14,
) -> tuple[ReviewRecord, ...]:
    base = ROUND1_START + timedelta(days=days_after)
    return tuple(
        _review_record(
            case_id=case.case_id,
            round_number=2,
            outcome=case.acceptable_outcomes[0]
            if case.acceptable_outcomes
            else "inconclusive",
            causal_faults=case.causal_faults,
            confidence=case.confidence,
            reviewed_at=base + timedelta(hours=index),
        )
        for index, case in enumerate(manifest_cases)
    )


@pytest.fixture
def final_manifest(tmp_path: Path):
    manifest = build_valid_manifest()
    final_cases = tuple(
        case for case in manifest.cases if case.split == "final_external_test"
    )
    manifest = manifest.model_copy(update={"cases": final_cases})
    materialize_manifest_assets(manifest, tmp_path / "assets_root")
    return manifest


@pytest.fixture
def round1(final_manifest) -> ReviewRound:
    summaries = {case.case_id: _reference_summary() for case in final_manifest.cases}
    return ReviewRound(
        round_number=1,
        records=_round1_records(final_manifest.cases),
        reference_summaries=summaries,
    )


def test_ev_t036_blind_package_excludes_truth_and_source_fields(
    final_manifest,
    round1: ReviewRound,
) -> None:
    payload = build_blind_package(
        manifest=final_manifest,
        round1=round1,
        alias_salt=b"fixed-test-salt",
        created_at=UTC_NOW,
    ).model_dump(mode="json")
    text = json.dumps(payload)
    for forbidden in (
        "SMARD",
        "alpha",
        "parent_master",
        "final_external_test",
        '"external_class"',
        "tail_proportion",
    ):
        assert forbidden not in text


def test_blind_package_uses_deterministic_aliases(
    final_manifest,
    round1: ReviewRound,
) -> None:
    first = build_blind_package(
        manifest=final_manifest,
        round1=round1,
        alias_salt=b"fixed-test-salt",
        created_at=UTC_NOW,
    )
    second = build_blind_package(
        manifest=final_manifest,
        round1=round1,
        alias_salt=b"fixed-test-salt",
        created_at=UTC_NOW,
    )
    assert first.cases == second.cases
    assert len({case.review_alias for case in first.cases}) == len(first.cases)


def test_ev_t037_round2_before_fourteen_days_is_rejected(
    final_manifest,
    round1: ReviewRound,
) -> None:
    round2 = ReviewRound(
        round_number=2,
        records=_round2_records(final_manifest.cases, days_after=13),
    )
    with pytest.raises(ValueError, match="14 complete days"):
        score_delayed_review(round1, round2)


def test_round2_after_fourteen_days_is_accepted(
    final_manifest,
    round1: ReviewRound,
) -> None:
    round2 = ReviewRound(
        round_number=2,
        records=_round2_records(final_manifest.cases, days_after=14),
    )
    agreement = score_delayed_review(round1, round2)
    assert agreement.raw_outcome_agreement == 1.0
    assert agreement.causal_set_agreement == 1.0


def test_ev_t038_disagreement_never_upgrades_confidence() -> None:
    case = make_external_case(
        source_group="A",
        external_class="clean",
        confidence="reference_supported",
        acceptable_outcomes=("no_supported_fault",),
        causal_faults=(),
        parent_master_id=None,
        transform=None,
    )
    round1 = _review_record(
        case_id=case.case_id,
        round_number=1,
        outcome="no_supported_fault",
        causal_faults=(),
        confidence="reference_supported",
    )
    round2 = _review_record(
        case_id=case.case_id,
        round_number=2,
        outcome="no_supported_fault",
        causal_faults=(),
        confidence="strong_ground_truth",
        reviewed_at=ROUND1_START + timedelta(days=14),
    )
    resolved = resolve_adjudicated_confidence(
        case,
        round1,
        round2,
        _reference_summary(),
    )
    assert resolved == "reference_supported"


def test_ev_t038_unresolved_a_case_downgrades_to_weak_or_unknown() -> None:
    case = make_external_case(
        source_group="A",
        external_class="inconclusive",
        confidence="reference_supported",
        acceptable_outcomes=("inconclusive",),
        causal_faults=(),
        parent_master_id=None,
        transform=None,
    )
    round1 = _review_record(
        case_id=case.case_id,
        round_number=1,
        outcome="inconclusive",
        causal_faults=(),
        confidence="reference_supported",
    )
    round2 = _review_record(
        case_id=case.case_id,
        round_number=2,
        outcome="supported_fault",
        causal_faults=("clipping",),
        confidence="reference_supported",
        reviewed_at=ROUND1_START + timedelta(days=14),
    )
    resolved = resolve_adjudicated_confidence(
        case,
        round1,
        round2,
        _reference_summary(),
    )
    assert resolved in {"weak_observation", "unknown"}


def test_ev_t038_transform_proven_b_strong_can_remain_strong() -> None:
    case = make_external_case(
        source_group="B",
        external_class="clipping",
        confidence="strong_ground_truth",
        transform=make_transform(),
    )
    round1 = _review_record(
        case_id=case.case_id,
        round_number=1,
        outcome="supported_fault",
        causal_faults=("clipping",),
        confidence="strong_ground_truth",
    )
    round2 = _review_record(
        case_id=case.case_id,
        round_number=2,
        outcome="supported_fault",
        causal_faults=("clipping",),
        confidence="strong_ground_truth",
        reviewed_at=ROUND1_START + timedelta(days=14),
    )
    resolved = resolve_adjudicated_confidence(
        case,
        round1,
        round2,
        _reference_summary(applicable=True),
    )
    assert resolved == "strong_ground_truth"


def test_ev_t039_agreement_statistics_match_deterministic_fixture() -> None:
    cases = (
        make_external_case(case_id="0000000000000001"),
        make_external_case(
            case_id="0000000000000002",
            external_class="harmonic",
            causal_faults=("harmonic_distortion",),
            transform=make_transform(
                kind="second_harmonic",
                tail_proportion=None,
                alpha=0.15,
                post_gain=0.8,
                parameters_identity="harmonic_a0.15_pg0.8",
            ),
        ),
        make_external_case(
            case_id="0000000000000003",
            source_group="A",
            external_class="clean",
            confidence="reference_supported",
            acceptable_outcomes=("no_supported_fault",),
            causal_faults=(),
            parent_master_id=None,
            transform=None,
        ),
    )
    assert len(cases) == 3
    round1 = ReviewRound(
        round_number=1,
        records=(
            _review_record(
                case_id="0000000000000001",
                round_number=1,
                outcome="supported_fault",
                causal_faults=("clipping",),
                confidence="strong_ground_truth",
            ),
            _review_record(
                case_id="0000000000000002",
                round_number=1,
                outcome="supported_fault",
                causal_faults=("harmonic_distortion",),
                confidence="strong_ground_truth",
            ),
            _review_record(
                case_id="0000000000000003",
                round_number=1,
                outcome="no_supported_fault",
                causal_faults=(),
                confidence="reference_supported",
            ),
        ),
    )
    round2 = ReviewRound(
        round_number=2,
        records=(
            _review_record(
                case_id="0000000000000001",
                round_number=2,
                outcome="supported_fault",
                causal_faults=("clipping",),
                confidence="strong_ground_truth",
                reviewed_at=ROUND1_START + timedelta(days=14),
            ),
            _review_record(
                case_id="0000000000000002",
                round_number=2,
                outcome="no_supported_fault",
                causal_faults=(),
                confidence="reference_supported",
                reviewed_at=ROUND1_START + timedelta(days=14, hours=1),
            ),
            _review_record(
                case_id="0000000000000003",
                round_number=2,
                outcome="no_supported_fault",
                causal_faults=(),
                confidence="weak_observation",
                reviewed_at=ROUND1_START + timedelta(days=14, hours=2),
            ),
        ),
    )
    agreement = score_delayed_review(round1, round2)
    assert agreement.raw_outcome_agreement == pytest.approx(2 / 3)
    assert agreement.causal_set_agreement == pytest.approx(1 / 2)
    assert agreement.outcome_cohen_kappa == pytest.approx(0.4)
    assert agreement.confidence_quadratic_kappa == pytest.approx(0.5)


def test_ev_t039_undefined_kappa_returns_none_with_reason() -> None:
    round1 = ReviewRound(
        round_number=1,
        records=(
            _review_record(
                case_id="0000000000000001",
                round_number=1,
                outcome="supported_fault",
                causal_faults=("clipping",),
                confidence="strong_ground_truth",
            ),
        ),
    )
    round2 = ReviewRound(
        round_number=2,
        records=(
            _review_record(
                case_id="0000000000000001",
                round_number=2,
                outcome="supported_fault",
                causal_faults=("clipping",),
                confidence="strong_ground_truth",
                reviewed_at=ROUND1_START + timedelta(days=14),
            ),
        ),
    )
    agreement = score_delayed_review(round1, round2)
    assert agreement.raw_outcome_agreement == 1.0
    assert agreement.outcome_cohen_kappa is None
    assert agreement.undefined_kappa_reason is not None
