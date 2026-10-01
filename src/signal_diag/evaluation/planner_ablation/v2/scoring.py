"""V2 planner-ablation metrics from verified study records (dev_2).

Study-only. Production verified construction is Task 6 ``verify_manifest``.
This module exposes a clearly marked synthetic test stub only.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from hashlib import sha256
from math import ceil

from signal_diag.agent.diagnosis import (
    DiagnosisValidationError,
    validate_finish_decision,
)
from signal_diag.agent.models import FinishDecision
from signal_diag.evaluation.planner_ablation.models import StudyContextGuidanceView
from signal_diag.evaluation.planner_ablation.v2.labels import validate_labels
from signal_diag.evaluation.planner_ablation.v2.models import (
    PINNED_CAUSAL_POLICY_V2,
    ArmModeRoundCell,
    ArmModeTotals,
    DescriptiveAcrossRoundSummary,
    GuidanceCell,
    LabelReviewResult,
    LatencyStats,
    MetricTables,
    OptionalRate,
    OracleLabel,
    PrerequisiteReport,
    ScenarioDefinition,
    Schedule,
    ScoredArm,
    SlotKey,
    StudyMode,
    StudyProtocolV2,
    StudyTerminal,
    UpgradeCell,
    VerifiedStudyV2,
)
from signal_diag.evaluation.planner_ablation.v2.population import canonical_json
from signal_diag.evaluation.planner_ablation.v2.provenance import (
    ProvenanceRejection,
    terminal_to_scored_record,
    validate_scored_product_ingestion,
)
from signal_diag.evaluation.planner_ablation.v2.timing import (
    TimingValidationError,
    validate_request_timing,
)
from signal_diag.rules.models import RuleEvaluation

_POSITIVE_FAULTS = frozenset({"clipping", "harmonic_distortion"})
_INVALID_REF_SCENARIO = "163185980dc8f7a4"


class ScoringError(ValueError):
    """Raised when scored inputs violate structural invariants."""


def build_synthetic_verified_study_v2_for_tests(
    *,
    protocol: StudyProtocolV2,
    schedule: Schedule,
    scenarios: Sequence[ScenarioDefinition],
    label_review: LabelReviewResult | None = None,
    input_identity: str | None = None,
    code_identity: str | None = None,
) -> VerifiedStudyV2:
    """TEST-ONLY synthetic VerifiedStudyV2.

    Not a production verified-input constructor. Task 6 owns ``verify_manifest``.
    """
    scenarios_t = tuple(scenarios)
    review = label_review if label_review is not None else validate_labels(
        scenarios_t, schedule
    )
    payload = {
        "protocol": protocol.model_dump(mode="json"),
        "schedule_digest": schedule.schedule_digest,
        "scenario_ids": [s.scenario_id for s in scenarios_t],
        "construction_path": "synthetic_test_stub",
    }
    verified = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return VerifiedStudyV2(
        protocol=protocol,
        schedule=schedule,
        scenarios=scenarios_t,
        label_review=review,
        verified_identity=verified,
        input_identity=input_identity or ("a" * 64),
        code_identity=code_identity or ("b" * 64),
        construction_path="synthetic_test_stub",
        pinned_causal_policy="v9_11_mode_aware_no_fault_recovery",
    )


def _rate(numerator: int, denominator: int) -> OptionalRate:
    if denominator == 0:
        return OptionalRate(
            numerator=0, denominator=0, value=None, evaluable=False
        )
    return OptionalRate(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator,
        evaluable=True,
    )


def _nearest_rank(samples: Sequence[float], percentile: float) -> float:
    ordered = sorted(samples)
    rank = ceil(percentile * len(ordered))
    return ordered[rank - 1]


def _latency_stats(samples: Sequence[float]) -> LatencyStats:
    if not samples:
        return LatencyStats(count=0)
    return LatencyStats(
        count=len(samples),
        mean_s=sum(samples) / len(samples),
        median_s=_nearest_rank(samples, 0.50),
        p95_s=_nearest_rank(samples, 0.95),
        max_s=max(samples),
    )


def _scenario_by_id(study: VerifiedStudyV2) -> dict[str, ScenarioDefinition]:
    return {s.scenario_id: s for s in study.scenarios}


def _request_meta(
    study: VerifiedStudyV2,
) -> dict[str, tuple[StudyMode, str, OracleLabel]]:
    """request_key -> (mode, representative_scenario_id, oracle)."""
    scenarios = _scenario_by_id(study)
    out: dict[str, tuple[StudyMode, str, OracleLabel]] = {}
    for req in study.schedule.canonical_requests:
        scenario = scenarios[req.representative_scenario_id]
        oracle = (
            scenario.single_oracle
            if req.mode == "single_signal"
            else scenario.paired_oracle
        )
        out[req.request_key] = (req.mode, req.representative_scenario_id, oracle)
    return out


def _paired_key_by_scenario(study: VerifiedStudyV2) -> dict[str, str]:
    keys: dict[str, str] = {}
    for req in study.schedule.canonical_requests:
        if req.mode == "paired_reference":
            keys[req.representative_scenario_id] = req.request_key
    return keys


def _single_key_by_scenario(study: VerifiedStudyV2) -> dict[str, str]:
    keys: dict[str, str] = {}
    for req in study.schedule.canonical_requests:
        if req.mode == "single_signal":
            keys[req.representative_scenario_id] = req.request_key
    # Alias sources share the target's single key.
    for source, target in study.schedule.scenario_aliases.items():
        if target in keys:
            keys[source] = keys[target]
    return keys


def _slot_key(terminal: StudyTerminal) -> SlotKey:
    if terminal.slot_key is not None:
        return terminal.slot_key
    if terminal.request_key is None:
        raise ScoringError("terminal missing slot_key and request_key")
    return SlotKey(
        request_key=terminal.request_key,
        arm=terminal.arm,
        round_index=0,
    )


def _index_records(
    study: VerifiedStudyV2,
    records: Sequence[StudyTerminal],
) -> tuple[dict[SlotKey, StudyTerminal], list[str], bool]:
    """Index by slot. Returns (index, structural_errors, complete)."""
    errors: list[str] = []
    indexed: dict[SlotKey, StudyTerminal] = {}
    for terminal in records:
        key = _slot_key(terminal)
        if key in indexed:
            errors.append(
                f"duplicate_record:{key.request_key}/{key.arm}/r{key.round_index}"
            )
            continue
        if key not in set(study.schedule.slots):
            errors.append(
                f"unexpected_record:{key.request_key}/{key.arm}/r{key.round_index}"
            )
            continue
        if terminal.arm != key.arm:
            errors.append(f"arm_mismatch:{key.request_key}")
        if terminal.request_key is not None and terminal.request_key != key.request_key:
            errors.append(f"request_key_mismatch:{key.request_key}")
        if terminal.mode not in ("single_signal", "paired_reference"):
            errors.append(f"invalid_mode:{key.request_key}")
        indexed[key] = terminal

    missing = [slot for slot in study.schedule.slots if slot not in indexed]
    for slot in missing:
        errors.append(
            f"missing_record:{slot.request_key}/{slot.arm}/r{slot.round_index}"
        )
    complete = not errors and len(indexed) == len(study.schedule.slots)
    return indexed, errors, complete


def _predicted_causal_faults(terminal: StudyTerminal) -> frozenset[str]:
    if terminal.outcome != "supported_fault":
        return frozenset()
    faults: set[str] = set()
    for claim in terminal.claims:
        if claim.fault_type in _POSITIVE_FAULTS:
            faults.add(claim.fault_type)
    return frozenset(faults)


def _outcome_only_match(terminal: StudyTerminal, oracle: OracleLabel) -> bool:
    if terminal.status != "completed" or terminal.outcome is None:
        return False
    return terminal.outcome == oracle.outcome


def _quality_match(terminal: StudyTerminal, oracle: OracleLabel) -> bool:
    if not _outcome_only_match(terminal, oracle):
        return False
    return _predicted_causal_faults(terminal) == frozenset(oracle.exact_causal_faults)


def _flatten_rule_evals(terminal: StudyTerminal) -> tuple[RuleEvaluation, ...]:
    return tuple(
        item
        for batch in terminal.rule_evaluation_batches
        for item in batch.evaluations
    )


def _same_run_ids(terminal: StudyTerminal) -> tuple[frozenset[str], frozenset[str]]:
    evidence_ids = frozenset(item.evidence_id for item in terminal.evidence)
    rule_ids = frozenset(item.evaluation_id for item in _flatten_rule_evals(terminal))
    return evidence_ids, rule_ids


def _claim_refs_same_run(terminal: StudyTerminal) -> bool:
    evidence_ids, rule_ids = _same_run_ids(terminal)
    for claim in terminal.claims:
        if claim.fault_type not in _POSITIVE_FAULTS and claim.fault_type not in {
            "no_supported_fault",
            "inconclusive",
        }:
            continue
        if claim.fault_type in _POSITIVE_FAULTS and (
            not claim.evidence_refs and not claim.rule_refs
        ):
            return False
        for ref in claim.evidence_refs:
            if ref not in evidence_ids:
                return False
        for ref in claim.rule_refs:
            if ref not in rule_ids:
                return False
    return True


def _reference_run_ownership_ok(terminal: StudyTerminal) -> bool:
    """Independently validate paired reference ownership (not semantic support)."""
    context = terminal.stimulus_context
    if terminal.mode == "paired_reference":
        if context is None:
            return False
        if context.mode != "paired_reference":
            return False
        if context.reference_signal_id is None:
            return False
        return context.reference_signal_id != context.test_signal_id
    return not (context is not None and context.reference_signal_id is not None)


def _finish_semantics_ok(terminal: StudyTerminal) -> bool:
    """Revalidate finish with unchanged v9.11 validator."""
    if terminal.status != "completed" or terminal.outcome is None:
        return True
    if terminal.task_assessment is None:
        return False
    limitations = terminal.limitations or ("reconstructed for study scoring",)
    decision = FinishDecision(
        task_assessment=terminal.task_assessment,
        outcome=terminal.outcome,
        claims=terminal.claims,
        confidence_label="medium",
        limitations=tuple(limitations),
    )
    rule_evals = _flatten_rule_evals(terminal)
    try:
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(
                item.evidence_id for item in terminal.evidence
            ),
            known_rule_evaluation_ids=frozenset(
                item.evaluation_id for item in rule_evals
            ),
            task_assessment=terminal.task_assessment,
            evidence=terminal.evidence,
            rule_evaluations=rule_evals,
            stimulus_context=terminal.stimulus_context,
            causal_policy_version=PINNED_CAUSAL_POLICY_V2,  # type: ignore[arg-type]
        )
    except DiagnosisValidationError:
        return False
    return True


def _semantic_support_ok(terminal: StudyTerminal) -> bool:
    if not _claim_refs_same_run(terminal):
        return False
    if not _reference_run_ownership_ok(terminal):
        return False
    return _finish_semantics_ok(terminal)


def _is_useful(terminal: StudyTerminal, oracle: OracleLabel) -> bool:
    if terminal.status != "completed" or terminal.outcome is None:
        return False
    if oracle.outcome == "inconclusive":
        return False
    if terminal.outcome == "inconclusive":
        return False
    if not _quality_match(terminal, oracle):
        return False
    if terminal.outcome not in {"supported_fault", "no_supported_fault"}:
        return False
    return _semantic_support_ok(terminal)


def _is_complete(terminal: StudyTerminal) -> bool:
    return (
        terminal.status == "completed"
        and terminal.outcome is not None
        and terminal.task_assessment is not None
    )


def _positive_claims(terminal: StudyTerminal) -> tuple:
    return tuple(c for c in terminal.claims if c.fault_type in _POSITIVE_FAULTS)


def _claim_grounded(terminal: StudyTerminal, claim) -> bool:
    evidence_ids, rule_ids = _same_run_ids(terminal)
    if not claim.evidence_refs and not claim.rule_refs:
        return False
    for ref in claim.evidence_refs:
        if ref not in evidence_ids:
            return False
    for ref in claim.rule_refs:
        if ref not in rule_ids:
            return False
    return True


def _tool_action_count(terminal: StudyTerminal) -> int:
    """Count actual tool events including repeats and failures."""
    if terminal.tool_history:
        return len(terminal.tool_history)
    return len(terminal.observations)


def _latency_sample(terminal: StudyTerminal) -> float | None:
    """Include behavioral failures; skip missing/invalid timing."""
    if terminal.timing is None:
        return None
    elapsed = terminal.timing.elapsed_s
    if not math.isfinite(elapsed) or elapsed <= 0.0:
        return None
    if terminal.status == "failed":
        kind = terminal.failure_cause.kind if terminal.failure_cause else "unknown"
        if kind not in {"behavioral", "decode_failure"}:
            return None
    return elapsed


def _expected_guidance(
    terminal: StudyTerminal,
) -> StudyContextGuidanceView | None:
    """Deterministic expected guidance shape for G correctness (product rules)."""
    if terminal.mode != "single_signal":
        return None
    if terminal.status != "completed" or terminal.outcome != "inconclusive":
        return None
    harmonic_metrics = {
        "thd_percent",
        "even_order_present",
        "fundamental_relative_energy",
        "even_harmonic_growth",
        "odd_harmonic_growth",
        "test_thd_percent",
    }
    has_harmonic = any(
        item.validity == "valid" and item.metric in harmonic_metrics
        for item in terminal.evidence
    )
    code = (
        "harmonic_attribution_requires_context"
        if has_harmonic
        else "insufficient_evidence_for_supported_fault"
    )
    return StudyContextGuidanceView(
        reason_codes=(code,),
        unlockable_modes=("paired_reference", "nominal_single_tone"),
        required_inputs={
            "paired_reference": ("reference_wav",),
            "nominal_single_tone": (
                "nominal_fundamental_hz",
                "stimulus_kind=single_tone",
            ),
        },
        summary=code,
    )


def _guidance_emitted_and_correct(terminal: StudyTerminal) -> bool:
    if terminal.guidance is None:
        return False
    expected = _expected_guidance(terminal)
    if expected is None:
        return False
    # Template conformance: reason codes and unlockable modes must match.
    if set(terminal.guidance.reason_codes) != set(expected.reason_codes):
        return False
    if tuple(terminal.guidance.unlockable_modes) != expected.unlockable_modes:
        return False
    return dict(terminal.guidance.required_inputs) == expected.required_inputs


def _single_meets_upgrade_target(
    terminal: StudyTerminal | None,
    scenario: ScenarioDefinition,
) -> bool:
    if terminal is None or scenario.upgrade_target is None:
        return False
    if not _is_complete(terminal):
        return False
    target = scenario.upgrade_target
    faults = _predicted_causal_faults(terminal)
    if target == "harmonic_attribution":
        return (
            terminal.outcome == "supported_fault"
            and "harmonic_distortion" in faults
            and _semantic_support_ok(terminal)
        )
    if target == "additional_harmonic_coverage":
        return (
            terminal.outcome == "supported_fault"
            and faults == frozenset({"clipping", "harmonic_distortion"})
            and _semantic_support_ok(terminal)
        )
    if target == "supported_no_fault_natural_control":
        return (
            terminal.outcome == "no_supported_fault"
            and _semantic_support_ok(terminal)
        )
    return False


def _paired_resolves_target(
    terminal: StudyTerminal,
    scenario: ScenarioDefinition,
) -> bool:
    if scenario.upgrade_target is None:
        return False
    if not _quality_match(terminal, scenario.paired_oracle):
        return False
    if not _semantic_support_ok(terminal):
        return False
    target = scenario.upgrade_target
    faults = _predicted_causal_faults(terminal)
    if target == "harmonic_attribution":
        return "harmonic_distortion" in faults
    if target == "additional_harmonic_coverage":
        return faults == frozenset({"clipping", "harmonic_distortion"})
    if target == "supported_no_fault_natural_control":
        return terminal.outcome == "no_supported_fault"
    return False


def calculate_metrics(
    study: VerifiedStudyV2,
    records: Sequence[StudyTerminal],
) -> MetricTables:
    """Derive count-before-rate metric tables from verified records."""
    indexed, structural_errors, complete = _index_records(study, records)
    request_meta = _request_meta(study)
    scenarios = _scenario_by_id(study)
    paired_keys = _paired_key_by_scenario(study)
    single_keys = _single_key_by_scenario(study)

    rounds = study.protocol.rounds
    arms: tuple[ScoredArm, ...] = ("product_agent", "fixed_pipeline")
    modes: tuple[StudyMode, ...] = ("single_signal", "paired_reference")

    # Group scheduled slots.
    slots_by_arm_mode_round: dict[
        tuple[ScoredArm, StudyMode, int], list[SlotKey]
    ] = defaultdict(list)
    for slot in study.schedule.slots:
        mode = request_meta[slot.request_key][0]
        slots_by_arm_mode_round[(slot.arm, mode, slot.round_index)].append(slot)

    cells: list[ArmModeRoundCell] = []
    for arm in arms:
        for mode in modes:
            for round_index in range(rounds):
                slot_list = slots_by_arm_mode_round.get((arm, mode, round_index), [])
                denom = len(slot_list)
                quality_n = 0
                outcome_n = 0
                useful_n = 0
                complete_n = 0
                grounded_n = 0
                claim_total = 0
                unsupported_n = 0
                positive_n = 0
                claim_data_complete = True
                safety_ok = True
                latency_samples: list[float] = []
                tool_actions = 0
                correct_keys: set[str] = set()

                for slot in slot_list:
                    terminal = indexed.get(slot)
                    _, _, oracle = request_meta[slot.request_key]
                    if terminal is None:
                        claim_data_complete = False
                        safety_ok = False
                        continue
                    if terminal.mode != mode:
                        claim_data_complete = False
                        safety_ok = False
                    sample = _latency_sample(terminal)
                    if sample is not None:
                        latency_samples.append(sample)
                    tool_actions += _tool_action_count(terminal)

                    if _is_complete(terminal):
                        complete_n += 1
                    if _outcome_only_match(terminal, oracle):
                        outcome_n += 1
                    if _quality_match(terminal, oracle):
                        quality_n += 1
                        correct_keys.add(slot.request_key)
                    if _is_useful(terminal, oracle):
                        useful_n += 1

                    if _is_complete(terminal):
                        for claim in terminal.claims:
                            claim_total += 1
                            if _claim_grounded(terminal, claim):
                                grounded_n += 1
                        positives = _positive_claims(terminal)
                        for claim in positives:
                            positive_n += 1
                            if not _claim_grounded(terminal, claim):
                                unsupported_n += 1
                        # Semantic safety for completed diagnoses.
                        if not _semantic_support_ok(terminal):
                            safety_ok = False
                        if positives and not _claim_refs_same_run(terminal):
                            safety_ok = False

                if positive_n == 0:
                    safety_ok = False
                unsupported = _rate(unsupported_n, positive_n)
                grounding = _rate(grounded_n, claim_total)
                mean_tools = (
                    tool_actions / denom if denom > 0 else None
                )
                cells.append(
                    ArmModeRoundCell(
                        arm=arm,
                        mode=mode,
                        round_index=round_index,
                        scheduled_denominator=denom,
                        quality=_rate(quality_n, denom),
                        outcome_accuracy=_rate(outcome_n, denom),
                        usefulness=_rate(useful_n, denom),
                        completion=_rate(complete_n, denom),
                        unsupported_positive_claims=unsupported,
                        grounding=grounding,
                        positive_claim_count=positive_n,
                        claim_data_complete=claim_data_complete,
                        safety_ok=safety_ok and claim_data_complete,
                        latency=_latency_stats(latency_samples),
                        tool_action_count=tool_actions,
                        mean_tool_actions=mean_tools,
                        quality_correct_keys=frozenset(correct_keys),
                    )
                )

    # Upgrade / guidance per arm/round (cross-mode endpoints).
    # Verified label_review snapshot is authoritative, including explicit empties.
    upgrade_pop = study.label_review.upgrade_population
    conditional_pop = study.label_review.conditional_population
    guidance_pop = study.label_review.guidance_population

    upgrade_cells: list[UpgradeCell] = []
    guidance_cells: list[GuidanceCell] = []
    for arm in arms:
        for round_index in range(rounds):
            s_count = 0
            incremental = 0
            already_met = 0
            invalid_abstention: bool | None = None
            for scenario_id in sorted(upgrade_pop):
                scenario = scenarios[scenario_id]
                paired_key = paired_keys.get(scenario_id)
                if paired_key is None:
                    continue
                slot = SlotKey(
                    request_key=paired_key, arm=arm, round_index=round_index
                )
                paired_terminal = indexed.get(slot)
                single_key = single_keys.get(scenario_id)
                single_terminal = None
                if single_key is not None:
                    single_terminal = indexed.get(
                        SlotKey(
                            request_key=single_key,
                            arm=arm,
                            round_index=round_index,
                        )
                    )

                if scenario_id == _INVALID_REF_SCENARIO:
                    if paired_terminal is not None and _quality_match(
                        paired_terminal, scenario.paired_oracle
                    ):
                        invalid_abstention = True
                    elif paired_terminal is not None:
                        invalid_abstention = False
                    continue

                if paired_terminal is None:
                    continue
                if scenario_id not in conditional_pop:
                    continue
                if _paired_resolves_target(paired_terminal, scenario):
                    s_count += 1
                    if _single_meets_upgrade_target(single_terminal, scenario):
                        already_met += 1
                    else:
                        incremental += 1

            u_size = len(upgrade_pop)
            c_size = len(conditional_pop)
            upgrade_cells.append(
                UpgradeCell(
                    arm=arm,
                    round_index=round_index,
                    u_size=u_size,
                    c_size=c_size,
                    s_count=s_count,
                    s_over_u=_rate(s_count, u_size),
                    s_over_c=_rate(s_count, c_size),
                    invalid_reference_abstention_correct=invalid_abstention,
                    incremental_gain_count=incremental,
                    already_met_not_incremental_count=already_met,
                )
            )

            emitted = 0
            emitted_correct = 0
            for scenario_id in sorted(guidance_pop):
                single_key = single_keys.get(scenario_id)
                if single_key is None:
                    continue
                slot = SlotKey(
                    request_key=single_key, arm=arm, round_index=round_index
                )
                terminal = indexed.get(slot)
                if terminal is None:
                    continue
                if terminal.guidance is not None:
                    emitted += 1
                    if _guidance_emitted_and_correct(terminal):
                        emitted_correct += 1
            g_size = len(guidance_pop)
            guidance_cells.append(
                GuidanceCell(
                    arm=arm,
                    round_index=round_index,
                    g_size=g_size,
                    emitted_count=emitted,
                    emitted_and_correct=_rate(emitted_correct, g_size),
                    conditional_template_ok=_rate(emitted_correct, emitted),
                )
            )

    # Across-round arm/mode totals (27/30).
    arm_mode_totals: list[ArmModeTotals] = []
    for arm in arms:
        for mode in modes:
            mode_cells = [
                c for c in cells if c.arm == arm and c.mode == mode
            ]
            denom = sum(c.scheduled_denominator for c in mode_cells)
            q_n = sum(c.quality.numerator for c in mode_cells)
            u_n = sum(c.usefulness.numerator for c in mode_cells)
            c_n = sum(c.completion.numerator for c in mode_cells)
            arm_mode_totals.append(
                ArmModeTotals(
                    arm=arm,
                    mode=mode,
                    scheduled_denominator=denom,
                    quality=_rate(q_n, denom),
                    usefulness=_rate(u_n, denom),
                    completion=_rate(c_n, denom),
                )
            )

    descriptive: list[DescriptiveAcrossRoundSummary] = []
    for arm in arms:
        mode_avgs: dict[str, list[float]] = {
            "quality": [],
            "usefulness": [],
            "completion": [],
        }
        for mode in modes:
            for round_index in range(rounds):
                cell = next(
                    c
                    for c in cells
                    if c.arm == arm
                    and c.mode == mode
                    and c.round_index == round_index
                )
                if cell.quality.evaluable and cell.quality.value is not None:
                    mode_avgs["quality"].append(cell.quality.value)
                if cell.usefulness.evaluable and cell.usefulness.value is not None:
                    mode_avgs["usefulness"].append(cell.usefulness.value)
                if cell.completion.evaluable and cell.completion.value is not None:
                    mode_avgs["completion"].append(cell.completion.value)
        # Equal mode weighting: average of per-mode means.
        def _equal_mode(vals_by_round: list[float]) -> float | None:
            if not vals_by_round:
                return None
            # Group into modes of `rounds` each.
            if len(vals_by_round) < rounds * 2:
                return sum(vals_by_round) / len(vals_by_round)
            single = vals_by_round[:rounds]
            paired = vals_by_round[rounds:]
            return (sum(single) / len(single) + sum(paired) / len(paired)) / 2.0

        descriptive.append(
            DescriptiveAcrossRoundSummary(
                arm=arm,
                equal_mode_quality=_equal_mode(mode_avgs["quality"]),
                equal_mode_usefulness=_equal_mode(mode_avgs["usefulness"]),
                equal_mode_completion=_equal_mode(mode_avgs["completion"]),
            )
        )

    # Partial campaigns remain descriptive-only for comparison.
    campaign_complete = complete and not structural_errors
    return MetricTables(
        cells=tuple(cells),
        upgrade_cells=tuple(upgrade_cells),
        guidance_cells=tuple(guidance_cells),
        arm_mode_totals=tuple(arm_mode_totals),
        descriptive_summaries=tuple(descriptive),
        descriptive_record_count=len(records),
        scheduled_slot_count=len(study.schedule.slots),
        campaign_records_complete=campaign_complete,
        partial_campaign=not campaign_complete,
    )


def evaluate_prerequisites(
    study: VerifiedStudyV2,
    records: Sequence[StudyTerminal],
) -> PrerequisiteReport:
    """Derive matching/safety/completeness; fail closed with reason codes."""
    reasons: list[str] = []
    identity_ok = (
        study.protocol.study_id == "study_s1_planner_ablation_dev_2"
        and study.protocol.scoring_identity
        == "signal_diag.planner_ablation_scoring"
        and study.protocol.scoring_version == "2.0.0-dev.1"
        and study.pinned_causal_policy == PINNED_CAUSAL_POLICY_V2
    )
    if not identity_ok:
        reasons.append("identity_mismatch")

    label_review_ok = study.label_review.approved
    if not label_review_ok:
        reasons.append("label_review_not_approved")

    construction_path_ok = study.construction_path == "verify_manifest"
    if not construction_path_ok:
        reasons.append("unverified_construction_path")

    oracle_ok = not study.label_review.errors
    if not oracle_ok:
        reasons.append("oracle_label_errors")
    # Reconstruct label check for schedule consistency.
    recomputed = validate_labels(study.scenarios, study.schedule)
    if recomputed.errors and not study.label_review.errors:
        oracle_ok = False
        reasons.append("oracle_revalidation_failed")

    indexed, structural_errors, complete = _index_records(study, records)
    campaign_complete = complete
    if not campaign_complete:
        reasons.append("campaign_incomplete")
        for err in structural_errors[:12]:
            if err.startswith("duplicate"):
                reasons.append("duplicate_records")
            elif err.startswith("missing"):
                reasons.append("missing_records")
            elif err.startswith("unexpected"):
                reasons.append("cross_schedule_or_round_records")

    timing_ok = True
    for terminal in indexed.values():
        if terminal.timing is None:
            timing_ok = False
            reasons.append("missing_timing")
            break
        try:
            validate_request_timing(terminal.timing)
        except TimingValidationError:
            timing_ok = False
            reasons.append("invalid_timing")
            break
    if not indexed and records:
        timing_ok = False
        if "missing_timing" not in reasons:
            reasons.append("missing_timing")

    pinned_gate_identity_ok = (
        study.pinned_causal_policy == PINNED_CAUSAL_POLICY_V2
    )
    if not pinned_gate_identity_ok:
        reasons.append("pinned_gate_identity_mismatch")

    # Matching: schema + timing + shared request coverage + gate identity.
    matching_ok = True
    report_parity_ok = True
    if campaign_complete:
        request_meta = _request_meta(study)
        for slot, terminal in indexed.items():
            mode = request_meta[slot.request_key][0]
            if terminal.mode != mode:
                matching_ok = False
                reasons.append("mode_schema_mismatch")
                break
            if terminal.arm != slot.arm:
                matching_ok = False
                reasons.append("arm_schema_mismatch")
                break
            # Guidance field shape when present.
            if terminal.guidance is not None and not terminal.guidance.reason_codes:
                report_parity_ok = False
                reasons.append("guidance_shape_invalid")
                break
    else:
        matching_ok = False
        report_parity_ok = False

    if not timing_ok:
        matching_ok = False
    if not pinned_gate_identity_ok:
        matching_ok = False

    metrics = calculate_metrics(study, records)
    product_safety_ok = all(
        c.safety_ok for c in metrics.cells if c.arm == "product_agent"
    )
    fixed_safety_ok = all(
        c.safety_ok for c in metrics.cells if c.arm == "fixed_pipeline"
    )
    if not product_safety_ok:
        reasons.append("product_safety_failed")
    if not fixed_safety_ok:
        reasons.append("fixed_safety_failed")

    positive_claims_evaluable = all(
        c.positive_claim_count > 0 and c.claim_data_complete and c.unsupported_positive_claims.evaluable
        for c in metrics.cells
    )
    if not positive_claims_evaluable:
        reasons.append("positive_claims_not_evaluable")

    provenance_ok = True
    if campaign_complete:
        for terminal in indexed.values():
            scored_record = terminal_to_scored_record(
                terminal,
                study_id=study.protocol.study_id,
                scoring_identity=study.protocol.scoring_identity,
                verified_online_context=(
                    terminal.provenance.execution_identity == "product_campaign"
                    and not terminal.provenance.offline_session
                ),
            )
            try:
                validate_scored_product_ingestion(scored_record)
            except ProvenanceRejection:
                provenance_ok = False
                reasons.append("provenance_rejected")
                break

    # Deduplicate reason codes while preserving order.
    seen: set[str] = set()
    unique_reasons: list[str] = []
    for code in reasons:
        if code not in seen:
            seen.add(code)
            unique_reasons.append(code)

    all_passed = (
        identity_ok
        and label_review_ok
        and construction_path_ok
        and provenance_ok
        and timing_ok
        and oracle_ok
        and report_parity_ok
        and matching_ok
        and campaign_complete
        and product_safety_ok
        and fixed_safety_ok
        and positive_claims_evaluable
        and pinned_gate_identity_ok
    )
    return PrerequisiteReport(
        identity_ok=identity_ok,
        timing_ok=timing_ok,
        oracle_ok=oracle_ok,
        report_parity_ok=report_parity_ok,
        matching_ok=matching_ok,
        campaign_complete=campaign_complete,
        product_safety_ok=product_safety_ok,
        fixed_safety_ok=fixed_safety_ok,
        positive_claims_evaluable=positive_claims_evaluable,
        pinned_gate_identity_ok=pinned_gate_identity_ok,
        reason_codes=tuple(unique_reasons),
        all_passed=all_passed,
    )
