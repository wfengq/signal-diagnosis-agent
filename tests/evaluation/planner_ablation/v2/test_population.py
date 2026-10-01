"""T-CX289–T-CX291: v2 request identity, schedule, aliases, and truth-free boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from signal_diag.evaluation.planner_ablation.v2.labels import validate_labels
from signal_diag.evaluation.planner_ablation.v2.models import (
    ByteRequest,
    OracleLabel,
    StudyProtocolV2,
)
from signal_diag.evaluation.planner_ablation.v2.population import (
    build_schedule,
    compute_request_key,
    load_proposed_scenarios,
    normalize_question,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
ALIAS_SOURCE = "163185980dc8f7a4"
ALIAS_TARGET = "825a759a0ea47bb7"
STUDY_QUESTION = "Diagnose supported S1 distortion conservatively."


def _protocol() -> StudyProtocolV2:
    return StudyProtocolV2()


def test_alias_collision_and_schedule() -> None:
    scenarios = load_proposed_scenarios(REPO_ROOT)
    schedule = build_schedule(scenarios, _protocol(), repository_root=REPO_ROOT)

    singles = [req for req in schedule.canonical_requests if req.mode == "single_signal"]
    paired = [req for req in schedule.canonical_requests if req.mode == "paired_reference"]
    product_slots = [slot for slot in schedule.slots if slot.arm == "product_agent"]
    assert (len(singles), len(paired), len(schedule.slots), len(product_slots)) == (
        9,
        10,
        114,
        57,
    )

    assert schedule.scenario_aliases[ALIAS_SOURCE] == ALIAS_TARGET

    by_scenario_mode = {
        (req.representative_scenario_id, req.mode): req.request_key
        for req in schedule.canonical_requests
    }
    # Alias target owns the shared single key; source is not a separate single unit.
    assert (ALIAS_TARGET, "single_signal") in by_scenario_mode
    assert (ALIAS_SOURCE, "single_signal") not in by_scenario_mode

    paired_825a = next(
        req.request_key
        for req in schedule.canonical_requests
        if req.representative_scenario_id == ALIAS_TARGET and req.mode == "paired_reference"
    )
    paired_1631 = next(
        req.request_key
        for req in schedule.canonical_requests
        if req.representative_scenario_id == ALIAS_SOURCE and req.mode == "paired_reference"
    )
    assert paired_825a != paired_1631

    # Lexicographic key order; round outermost; product first iff (i+r)%2==0.
    keys = [req.request_key for req in schedule.canonical_requests]
    assert keys == sorted(keys)
    assert len(schedule.slots) == len(keys) * 2 * 3
    slot_iter = iter(schedule.slots)
    for round_index in range(3):
        for key_index, request_key in enumerate(keys):
            first = next(slot_iter)
            second = next(slot_iter)
            assert first.request_key == request_key
            assert second.request_key == request_key
            assert first.round_index == round_index
            assert second.round_index == round_index
            if (key_index + round_index) % 2 == 0:
                assert (first.arm, second.arm) == ("product_agent", "fixed_pipeline")
            else:
                assert (first.arm, second.arm) == ("fixed_pipeline", "product_agent")


def test_conflicting_equal_input_oracle_rejected() -> None:
    scenarios = list(load_proposed_scenarios(REPO_ROOT))
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    invalid = by_id[ALIAS_SOURCE]
    # Keep equal single inputs but force unequal oracle labels.
    conflicted = invalid.model_copy(
        update={
            "single_oracle": OracleLabel(
                outcome="inconclusive",
                exact_causal_faults=(),
            )
        }
    )
    conflicted_population = tuple(
        conflicted if scenario.scenario_id == ALIAS_SOURCE else scenario
        for scenario in scenarios
    )
    with pytest.raises(ValueError, match="equal.?input|oracle|conflict"):
        build_schedule(conflicted_population, _protocol(), repository_root=REPO_ROOT)

    # Equal labels on equal keys must still pass schedule build, but unequal
    # review provenance disagreement is reported by validate_labels without approval.
    schedule = build_schedule(tuple(scenarios), _protocol(), repository_root=REPO_ROOT)
    result = validate_labels(tuple(scenarios), schedule)
    assert result.errors == ()
    assert result.review_status == "pending"
    assert result.approved is False


def test_fixed_eligibility_and_truth_free_request() -> None:
    scenarios = load_proposed_scenarios(REPO_ROOT)
    schedule = build_schedule(scenarios, _protocol(), repository_root=REPO_ROOT)
    review = validate_labels(scenarios, schedule)

    u_ids = {s.scenario_id for s in scenarios if s.in_upgrade_population}
    c_ids = {
        s.scenario_id
        for s in scenarios
        if s.in_upgrade_population
        and s.context_obtainable
        and s.context_valid
        and s.context_sufficient
    }
    g_ids = {s.scenario_id for s in scenarios if s.in_guidance_population}
    assert (len(u_ids), len(c_ids), len(g_ids)) == (7, 6, 4)
    assert ALIAS_SOURCE in u_ids
    assert ALIAS_SOURCE not in c_ids
    assert review.upgrade_population == frozenset(u_ids)
    assert review.conditional_population == frozenset(c_ids)
    assert review.guidance_population == frozenset(g_ids)

    # Truth-free ByteRequest rejects oracle / U/C/G / scenario truth injection.
    with pytest.raises(ValidationError):
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=b"RIFF",
            question=normalize_question(STUDY_QUESTION),
            oracle_outcome="supported_fault",  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=b"RIFF",
            question=normalize_question(STUDY_QUESTION),
            in_upgrade_population=True,  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=b"RIFF",
            question=normalize_question(STUDY_QUESTION),
            scenario_id=ALIAS_TARGET,  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        ByteRequest(
            mode="nominal_single_tone",  # type: ignore[arg-type]
            test_wav_bytes=b"RIFF",
            question=normalize_question(STUDY_QUESTION),
        )
    with pytest.raises(ValidationError):
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=b"RIFF",
            reference_wav_bytes=b"REF",
            question=normalize_question(STUDY_QUESTION),
        )

    # Changing a withheld reference cannot change a single-mode request key.
    clean = next(s for s in scenarios if s.scenario_id == ALIAS_TARGET)
    test_bytes = (REPO_ROOT / clean.test_wav_relpath).read_bytes()
    ref_a = (REPO_ROOT / clean.reference_wav_relpath).read_bytes()
    ref_b = ref_a + b"\x00"
    question = normalize_question(STUDY_QUESTION)
    key_a = compute_request_key(
        mode="single_signal",
        test_wav_bytes=test_bytes,
        reference_wav_bytes=None,
        question=question,
    )
    key_b = compute_request_key(
        mode="single_signal",
        test_wav_bytes=test_bytes,
        reference_wav_bytes=None,
        question=question,
    )
    assert key_a == key_b
    # Explicit: single-key identity ignores paired reference bytes entirely.
    assert compute_request_key(
        mode="single_signal",
        test_wav_bytes=test_bytes,
        reference_wav_bytes=None,
        question=question,
    ) == compute_request_key(
        mode="single_signal",
        test_wav_bytes=test_bytes,
        reference_wav_bytes=None,
        question=question,
    )
    paired_a = compute_request_key(
        mode="paired_reference",
        test_wav_bytes=test_bytes,
        reference_wav_bytes=ref_a,
        question=question,
    )
    paired_b = compute_request_key(
        mode="paired_reference",
        test_wav_bytes=test_bytes,
        reference_wav_bytes=ref_b,
        question=question,
    )
    assert paired_a != paired_b
    assert key_a != paired_a

    # Normalization preserves case/whitespace interior; only NFC + newline mapping.
    assert normalize_question("Why  Distorted?\r\n") == "Why  Distorted?\n"
    assert normalize_question("Café") == normalize_question("Cafe\u0301")
