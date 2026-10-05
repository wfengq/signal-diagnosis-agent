"""Fixed English wording for full-scale check records (V0.3 §23)."""

from __future__ import annotations

from collections.abc import Mapping

from signal_diag.rules.full_scale_check import (
    FullScaleCheckRecord,
    FullScaleMethodFloor,
)

FULL_SCALE_TEMPLATES: Mapping[str, str] = {
    "status.regression_detected": "Samples reaching the full-scale threshold increased.",
    "status.no_regression_detected.no_increase": (
        "No increase found in samples reaching the full-scale threshold."
    ),
    "status.no_regression_detected.within_floor": (
        "The increase in samples reaching the full-scale threshold is not above the method floor."
    ),
    "status.no_regression_detected.decrease": (
        "Samples reaching the full-scale threshold decreased: {baseline} to {candidate}. "
        "No cause is stated."
    ),
    "status.descriptive_only": (
        "Descriptive only. No judgment is made for samples reaching the full-scale threshold."
    ),
    "status.not_comparable": (
        "Not comparable. No judgment is made for samples reaching the full-scale threshold."
    ),
    "notice.export_settings": (
        "This difference may come from export settings (bit depth, dither, gain, start point) "
        "and not necessarily from the version."
    ),
    "notice.values": (
        "Baseline: {baseline_counted} samples, peak {baseline_peak}. "
        "Candidate: {candidate_counted} samples, peak {candidate_peak}."
    ),
    "notice.floor": "Difference {difference} samples; method floor {floor}.",
    "notice.renders": (
        "Based on {baseline_n} consistent baseline render(s) and "
        "{candidate_n} consistent candidate render(s)."
    ),
    "notice.declared": (
        "Periodic test signal, determinism, independent renders and the nominal fundamental "
        "are declared by the user, not verified. If the declared fundamental is wrong, "
        "the approved-domain limits do not apply."
    ),
    "notice.coverage": "THD is not covered by this check. clipping_ratio is descriptive only.",
    "notice.uncounted": "Repeat {comparison_id} ({side}) is not counted: {reason}.",
    "notice.byte_identical": "Repeat {comparison_id} ({side}) is byte-identical to the original file.",
    "notice.inconsistent": (
        "Renders declared deterministic differ on the {side} side: {values} samples."
    ),
    "notice.unmet": "Conditions not met: {codes}.",
    "notice.unevaluated": "Conditions not evaluated (no approved method floor): {codes}.",
    "notice.no_floor": "This measurement configuration has no approved method floor.",
}

CLIPPING_RATIO_NOTICE = (
    "clipping_ratio includes flat-top detection results and may be non-zero on low-frequency "
    "or low-level input that has no full-scale samples. It is not a measure of severity."
)


def full_scale_check_lines(record: FullScaleCheckRecord) -> tuple[str, ...]:
    lines: list[str] = []
    baseline = record.baseline_renders[0] if record.baseline_renders else None
    candidate = record.candidate_renders[0] if record.candidate_renders else None

    lines.append(_status_line(record))

    if baseline is not None and candidate is not None:
        lines.append(
            FULL_SCALE_TEMPLATES["notice.values"].format(
                baseline_counted=baseline.counted_samples,
                baseline_peak=f"{baseline.peak_abs:.6f}",
                candidate_counted=candidate.counted_samples,
                candidate_peak=f"{candidate.peak_abs:.6f}",
            )
        )

    if record.transition is not None and record.transition.startswith("yes_to_yes"):
        diff = record.count_difference if record.count_difference is not None else 0
        lines.append(
            FULL_SCALE_TEMPLATES["notice.floor"].format(
                difference=diff,
                floor=_floor_text(record.floor),
            )
        )

    inconsistent = any(
        code.startswith("renders_inconsistent:") for code in record.unmet_conditions
    )
    if (
        baseline is not None
        and candidate is not None
        and not inconsistent
    ):
        lines.append(
            FULL_SCALE_TEMPLATES["notice.renders"].format(
                baseline_n=len(record.baseline_renders),
                candidate_n=len(record.candidate_renders),
            )
        )

    for code in record.unmet_conditions:
        if code.startswith("renders_inconsistent:"):
            side = code.split(":", 1)[1]
            values = " / ".join(
                str(facts.counted_samples)
                for facts in (
                    record.baseline_renders
                    if side == "baseline"
                    else record.candidate_renders
                )
            )
            lines.append(
                FULL_SCALE_TEMPLATES["notice.inconsistent"].format(side=side, values=values)
            )

    for entry in record.uncounted_repeats:
        lines.append(
            FULL_SCALE_TEMPLATES["notice.uncounted"].format(
                comparison_id=entry.comparison_id,
                side=entry.side,
                reason=entry.reason,
            )
        )
    for comparison_id, side in record.byte_identical_repeats:
        lines.append(
            FULL_SCALE_TEMPLATES["notice.byte_identical"].format(
                comparison_id=comparison_id,
                side=side,
            )
        )

    if record.status == "regression_detected":
        lines.append(FULL_SCALE_TEMPLATES["notice.export_settings"])
    if record.status in ("regression_detected", "no_regression_detected"):
        lines.append(FULL_SCALE_TEMPLATES["notice.declared"])

    if record.unmet_conditions:
        lines.append(
            FULL_SCALE_TEMPLATES["notice.unmet"].format(
                codes=", ".join(record.unmet_conditions)
            )
        )
    if record.unevaluated_conditions:
        lines.append(
            FULL_SCALE_TEMPLATES["notice.unevaluated"].format(
                codes=", ".join(record.unevaluated_conditions)
            )
        )
    if record.floor is None:
        lines.append(FULL_SCALE_TEMPLATES["notice.no_floor"])

    lines.append(FULL_SCALE_TEMPLATES["notice.coverage"])
    return tuple(lines)


def _status_line(record: FullScaleCheckRecord) -> str:
    if record.status == "regression_detected":
        return FULL_SCALE_TEMPLATES["status.regression_detected"]
    if record.status == "descriptive_only":
        return FULL_SCALE_TEMPLATES["status.descriptive_only"]
    if record.status == "not_comparable":
        return FULL_SCALE_TEMPLATES["status.not_comparable"]
    if record.status == "no_regression_detected":
        transition = record.transition
        if transition in ("yes_to_no", "yes_to_yes_decrease") and record.baseline_renders and record.candidate_renders:
            return FULL_SCALE_TEMPLATES["status.no_regression_detected.decrease"].format(
                baseline=record.baseline_renders[0].counted_samples,
                candidate=record.candidate_renders[0].counted_samples,
            )
        if transition == "yes_to_yes_increase":
            return FULL_SCALE_TEMPLATES["status.no_regression_detected.within_floor"]
        return FULL_SCALE_TEMPLATES["status.no_regression_detected.no_increase"]
    return FULL_SCALE_TEMPLATES["status.descriptive_only"]


def _floor_text(floor: FullScaleMethodFloor | None) -> str:
    if floor is None:
        return "none"
    parts: list[str] = []
    if floor.count_floor_samples is not None:
        parts.append(f"{floor.count_floor_samples} samples")
    if floor.count_floor_ratio is not None:
        parts.append(f"{floor.count_floor_ratio:.6f} of analyzed samples")
    return " and ".join(parts) if parts else "none"
