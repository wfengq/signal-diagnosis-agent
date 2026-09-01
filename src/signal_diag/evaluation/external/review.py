"""Delayed blinded self-review support for the external WAV study."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Hashable, Sequence
from datetime import datetime, timedelta

from signal_diag.evaluation.external.models import (
    SINGLE_REVIEWER_DISCLOSURE,
    BlindPackage,
    BlindPackageCase,
    ExternalCase,
    ExternalDatasetManifest,
    LabelConfidence,
    ReferenceSummary,
    ReviewAgreement,
    ReviewRecord,
    ReviewRound,
)


def build_blind_package(
    manifest: ExternalDatasetManifest,
    round1: ReviewRound,
    *,
    alias_salt: bytes,
    created_at: datetime,
) -> BlindPackage:
    if round1.round_number != 1:
        raise ValueError("blind package requires round 1")
    records = {record.case_id: record for record in round1.records}
    cases: list[BlindPackageCase] = []
    for case in manifest.cases:
        if (
            case.case_id not in records
            or case.case_id not in round1.reference_summaries
        ):
            raise ValueError(f"round 1 is incomplete for case {case.case_id}")
        alias = hashlib.sha256(alias_salt + case.case_id.encode("ascii")).hexdigest()[
            :16
        ]
        cases.append(
            BlindPackageCase(
                review_alias=f"review_{alias}",
                analysis_wav_path=f"audio/review_{alias}.wav",
                reference_summary=round1.reference_summaries[case.case_id],
            )
        )
    package_id = hashlib.sha256(
        alias_salt + created_at.isoformat().encode()
    ).hexdigest()
    return BlindPackage(
        package_id=package_id, created_at_utc=created_at, cases=tuple(cases)
    )


def score_delayed_review(round1: ReviewRound, round2: ReviewRound) -> ReviewAgreement:
    if round1.round_number != 1 or round2.round_number != 2:
        raise ValueError("expected review rounds 1 and 2")
    first = {record.case_id: record for record in round1.records}
    second = {record.case_id: record for record in round2.records}
    if first.keys() != second.keys() or not first:
        raise ValueError("review rounds must contain the same non-empty case set")
    for case_id, record2 in second.items():
        if record2.reviewed_at_utc - first[case_id].reviewed_at_utc < timedelta(
            days=14
        ):
            raise ValueError("round 2 requires 14 complete days after round 1")

    ordered = sorted(first)
    outcomes1 = [first[key].outcome for key in ordered]
    outcomes2 = [second[key].outcome for key in ordered]
    raw = sum(a == b for a, b in zip(outcomes1, outcomes2, strict=True)) / len(ordered)
    eligible = [
        key
        for key in ordered
        if first[key].confidence in {"strong_ground_truth", "reference_supported"}
        and second[key].confidence in {"strong_ground_truth", "reference_supported"}
    ]
    causal = None
    if eligible:
        causal = sum(
            first[key].causal_faults == second[key].causal_faults for key in eligible
        ) / len(eligible)
    outcome_kappa = _cohen_kappa(outcomes1, outcomes2)
    confidence_kappa = _weighted_kappa(
        [record.confidence for record in (first[key] for key in ordered)],
        [record.confidence for record in (second[key] for key in ordered)],
    )
    undefined = None
    if outcome_kappa is None or confidence_kappa is None:
        undefined = "kappa is undefined when expected disagreement is zero"
    return ReviewAgreement(
        review_mode="delayed_blind_review",
        evaluation_status="evaluated",
        raw_outcome_agreement=raw,
        causal_set_agreement=causal,
        outcome_cohen_kappa=outcome_kappa,
        confidence_quadratic_kappa=confidence_kappa,
        undefined_kappa_reason=undefined,
    )


def audit_single_reviewer_provenance(
    manifest: ExternalDatasetManifest,
    round1: ReviewRound,
) -> ReviewAgreement:
    if round1.round_number != 1:
        raise ValueError("provenance audit requires round 1")
    records = {record.case_id: record for record in round1.records}
    if set(records) != {case.case_id for case in manifest.cases}:
        raise ValueError("round 1 must cover every manifest case")
    masters = {
        case.parent_master_id: case.wav_sha256
        for case in manifest.cases
        if case.source_group == "B" and case.external_class == "clean"
    }
    for case in manifest.cases:
        if case.source_group in {"A", "C"} and case.confidence == "strong_ground_truth":
            raise ValueError(
                f"A/C case {case.case_id} cannot be strong_ground_truth"
            )
        if case.confidence == "strong_ground_truth":
            if case.source_group != "B" or case.transform is None:
                raise ValueError(
                    f"strong_ground_truth requires B transform provenance for {case.case_id}"
                )
            if case.transform.output_sha256 != case.wav_sha256:
                raise ValueError(
                    f"transform output_sha256 must match wav_sha256 for {case.case_id}"
                )
            master_digest = masters.get(case.parent_master_id)
            if (
                master_digest is not None
                and case.transform.input_sha256 != master_digest
            ):
                raise ValueError(
                    f"transform input_sha256 must match clean parent for {case.case_id}"
                )
            if not case.transform.parameters_identity:
                raise ValueError(
                    f"transform parameters_identity required for {case.case_id}"
                )
    return ReviewAgreement(
        review_mode="single_reviewer_provenance_audit",
        evaluation_status="not_evaluated",
        disclosure=SINGLE_REVIEWER_DISCLOSURE,
    )


def resolve_adjudicated_confidence(
    case: ExternalCase,
    round1: ReviewRecord,
    round2: ReviewRecord,
    reference: ReferenceSummary,
) -> LabelConfidence:
    if round1.outcome != round2.outcome or round1.causal_faults != round2.causal_faults:
        return (
            "weak_observation"
            if case.source_group in {"A", "C"}
            else min(
                (case.confidence, round1.confidence, round2.confidence),
                key=_confidence_rank,
            )
        )
    candidate = min(
        (case.confidence, round1.confidence, round2.confidence), key=_confidence_rank
    )
    if candidate == "strong_ground_truth" and (
        case.source_group != "B" or case.transform is None or not reference.applicable
    ):
        return "reference_supported"
    return candidate


def _confidence_rank(value: LabelConfidence) -> int:
    return {
        "unknown": 0,
        "weak_observation": 1,
        "reference_supported": 2,
        "strong_ground_truth": 3,
    }[value]


def _cohen_kappa(left: Sequence[Hashable], right: Sequence[Hashable]) -> float | None:
    count = len(left)
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / count
    left_counts, right_counts = Counter(left), Counter(right)
    expected = (
        sum(
            left_counts[key] * right_counts[key]
            for key in set(left_counts) | set(right_counts)
        )
        / count**2
    )
    if expected == 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def _weighted_kappa(
    left: list[LabelConfidence], right: list[LabelConfidence]
) -> float | None:
    ranks = [_confidence_rank(value) for value in left]
    other = [_confidence_rank(value) for value in right]
    count = len(ranks)
    observed = sum((a - b) ** 2 / 9 for a, b in zip(ranks, other, strict=True)) / count
    left_counts, right_counts = Counter(ranks), Counter(other)
    expected = (
        sum(
            left_counts[a] * right_counts[b] * ((a - b) ** 2 / 9)
            for a in range(4)
            for b in range(4)
        )
        / count**2
    )
    if expected == 0.0:
        return None
    return 1.0 - observed / expected
