"""Pure regression comparison rules for cross-run measurement bundles."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import Evidence, EvidenceValidity
from signal_diag.tools.regression_measurement import MeasurementBundle
from signal_diag.tools.results import ToolResult, ToolStatus

ComparisonSide = Literal["baseline", "candidate"]
DeclarationAnswer = Literal["yes", "no", "unknown"]
Repeatability = Literal["declared_deterministic", "unknown", "observed_variable"]
DifferenceKind = Literal["signed_absolute", "relative_increase"]
MetricStatus = Literal[
    "not_comparable",
    "descriptive_only",
    "regression_detected",
    "no_regression_detected",
]
CoverageStatus = Literal["satisfied", "blocked", "failed", "skipped"]

COMPARE_METRICS: tuple[tuple[str, ToolName, str | None], ...] = (
    ("clipping_ratio", "detect_clipping", None),
    ("thd_percent", "analyze_harmonic_distortion", "%"),
)


class ComparisonConditions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: Literal["preserve_behavior"] = "preserve_behavior"
    baseline_version: str = Field(max_length=256)
    candidate_version: str = Field(max_length=256)
    stimulus_key: str = Field(max_length=256)
    parameters_key: str = Field(max_length=256)
    same_input: DeclarationAnswer
    parameters_unchanged: DeclarationAnswer
    aligned_ranges: DeclarationAnswer
    repeatability: Repeatability
    original_input_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    nominal_fundamental_hz: float | None = None


class HarmonicFundamentalApplicability(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_fundamental_delta_hz: float = Field(ge=0.0)


class ComparisonRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    source_tool: ToolName
    unit: str | None = None
    difference: DifferenceKind
    allowed_min: float
    allowed_max: float
    denominator_floor: float | None = None
    applicability_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relative_rule(self) -> ComparisonRule:
        if self.difference == "relative_increase" and (
            self.denominator_floor is None
            or not (math.isfinite(self.denominator_floor) and self.denominator_floor > 0)
        ):
            raise ValueError("relative_increase requires positive finite denominator_floor")
        if not math.isfinite(self.allowed_min) or not math.isfinite(self.allowed_max):
            raise ValueError("allowed bounds must be finite")
        if self.allowed_min > self.allowed_max:
            raise ValueError("allowed_min must be <= allowed_max")
        return self


class ComparisonProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    rules: tuple[ComparisonRule, ...]
    harmonic_fundamental_applicability: HarmonicFundamentalApplicability | None = None
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    side: ComparisonSide
    run_id: str
    wav_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_id: str = Field(pattern=r"^ev_")
    source_tool: ToolName
    call_id: str = Field(pattern=r"^call_")
    metric: str
    value: float
    unit: str | None = None
    validity: EvidenceValidity
    channel: ChannelMode
    time_range: TimeRange | None = None


class MetricComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str
    baseline_ref: SourceRef | None = None
    candidate_ref: SourceRef | None = None
    difference: float | None = None
    difference_unit: str | None = None
    status: MetricStatus
    reason_codes: tuple[str, ...] = ()
    rule_ref: str | None = None


class CoverageEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    check_id: str
    status: CoverageStatus
    detail: str | None = None


class ClippingFactSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    side: ComparisonSide
    flat_top_detected: bool | None
    clipping_mechanism: bool | None
    tool_status: ToolStatus


class ComparisonRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    comparison_id: str
    baseline_bundle: MeasurementBundle
    candidate_bundle: MeasurementBundle
    conditions: ComparisonConditions
    profile_id: str | None = None
    profile_version: str | None = None
    applied_profile: ComparisonProfile | None = None
    metric_comparisons: tuple[MetricComparison, ...]
    required_checks: tuple[str, ...]
    coverage: tuple[CoverageEntry, ...]
    clipping_facts: tuple[ClippingFactSnapshot, ...]
    overall_regression_pass: bool | None = None
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def compare_measurements(
    baseline: MeasurementBundle,
    candidate: MeasurementBundle,
    *,
    conditions: ComparisonConditions,
    profile: ComparisonProfile | None = None,
    comparison_id: str | None = None,
) -> ComparisonRecord:
    """Compare two measurement bundles under optional fixture/product profile."""
    _validate_bundle_pair(baseline, candidate)
    clipping_facts = (
        _clipping_facts("baseline", baseline),
        _clipping_facts("candidate", candidate),
    )
    coverage: list[CoverageEntry] = []
    declarations_block = _declarations_block_regression(conditions)
    if declarations_block:
        coverage.append(
            CoverageEntry(
                check_id="declarations",
                status="blocked",
                detail=declarations_block,
            )
        )

    metric_rows: list[MetricComparison] = []
    for metric, source_tool, unit in COMPARE_METRICS:
        rule = _find_rule(profile, metric, source_tool, unit) if profile else None
        row = _compare_metric(
            metric=metric,
            source_tool=source_tool,
            expected_unit=unit,
            baseline=baseline,
            candidate=candidate,
            rule=rule,
            profile=profile,
            declarations_block=declarations_block,
        )
        metric_rows.append(row)
        coverage.append(_coverage_for_metric(metric, baseline, candidate, row))

    overall = _overall_pass(metric_rows, clipping_facts, declarations_block, profile)
    record_without_digest = ComparisonRecord(
        comparison_id=comparison_id or f"cmp_{uuid.uuid4().hex[:16]}",
        baseline_bundle=baseline,
        candidate_bundle=candidate,
        conditions=conditions,
        profile_id=profile.profile_id if profile else None,
        profile_version=profile.version if profile else None,
        applied_profile=profile,
        metric_comparisons=tuple(metric_rows),
        required_checks=("clipping_ratio", "thd_percent", "declarations", "tool_success"),
        coverage=tuple(coverage),
        clipping_facts=clipping_facts,
        overall_regression_pass=overall,
        digest="0" * 64,
    )
    return record_without_digest.model_copy(
        update={"digest": _record_digest(record_without_digest)},
    )


def validate_comparison_record(record: ComparisonRecord) -> None:
    """Recompute comparisons and reject tampered records."""
    expected = compare_measurements(
        record.baseline_bundle,
        record.candidate_bundle,
        conditions=record.conditions,
        profile=record.applied_profile,
        comparison_id=record.comparison_id,
    )
    _validate_source_refs(record)
    if expected.digest != record.digest:
        raise ValueError("comparison record digest mismatch")
    if expected.metric_comparisons != record.metric_comparisons:
        raise ValueError("comparison record metric results mismatch")


def _validate_source_refs(record: ComparisonRecord) -> None:
    for row in record.metric_comparisons:
        for ref, bundle, expected_side in (
            (row.baseline_ref, record.baseline_bundle, "baseline"),
            (row.candidate_ref, record.candidate_bundle, "candidate"),
        ):
            if ref is None:
                continue
            if ref.side != expected_side:
                raise ValueError("source ref side mismatch")
            if ref.run_id != bundle.identity.run_id:
                raise ValueError("source ref run_id mismatch")
            if ref.wav_sha256 != bundle.identity.wav_sha256:
                raise ValueError("source ref wav_sha256 mismatch")
            if ref.bundle_digest != bundle.digest:
                raise ValueError("source ref bundle_digest mismatch")
            tool = _tool_for_metric(bundle, ref.source_tool)
            evidence = _find_evidence(tool, ref.metric)
            if evidence is None:
                raise ValueError("source ref evidence missing from bundle")
            if evidence.evidence_id != ref.evidence_id:
                raise ValueError("source ref evidence_id mismatch across runs")
            if evidence.call_id != ref.call_id:
                raise ValueError("source ref call_id mismatch")
            if evidence.value != ref.value and not (
                isinstance(evidence.value, float)
                and isinstance(ref.value, float)
                and evidence.value == ref.value
            ):
                raise ValueError("source ref value mismatch")


def _validate_bundle_pair(baseline: MeasurementBundle, candidate: MeasurementBundle) -> None:
    if baseline.identity.sample_rate_hz != candidate.identity.sample_rate_hz:
        raise ValueError("baseline and candidate sample_rate_hz must match")
    if baseline.identity.channel != candidate.identity.channel:
        raise ValueError("baseline and candidate channel must match")
    if baseline.identity.resolved_start_sample != candidate.identity.resolved_start_sample:
        raise ValueError("resolved start sample must correspond between sides")
    if baseline.identity.resolved_end_sample != candidate.identity.resolved_end_sample:
        raise ValueError("resolved end sample must correspond between sides")
    base_snap = baseline.identity.tool_parameter_snapshot
    cand_snap = candidate.identity.tool_parameter_snapshot
    if base_snap != cand_snap:
        raise ValueError("tool_parameter_snapshot must match between sides")


def _declarations_block_regression(conditions: ComparisonConditions) -> str | None:
    for field in ("same_input", "parameters_unchanged", "aligned_ranges"):
        value = getattr(conditions, field)
        if value == "no":
            return f"{field}=no"
        if value == "unknown":
            return f"{field}=unknown"
    if conditions.repeatability == "observed_variable":
        return "repeatability=observed_variable"
    return None


def _clipping_facts(side: ComparisonSide, bundle: MeasurementBundle) -> ClippingFactSnapshot:
    result = bundle.clipping.result
    return ClippingFactSnapshot(
        side=side,
        flat_top_detected=result.flat_top_detected if result else None,
        clipping_mechanism=result.clipping_mechanism if result else None,
        tool_status=bundle.clipping.status,
    )


def _find_rule(
    profile: ComparisonProfile | None,
    metric: str,
    source_tool: ToolName,
    unit: str | None,
) -> ComparisonRule | None:
    if profile is None:
        return None
    for rule in profile.rules:
        if (
            rule.metric == metric
            and rule.source_tool == source_tool
            and rule.unit == unit
        ):
            return rule
    return None


def _compare_metric(
    *,
    metric: str,
    source_tool: ToolName,
    expected_unit: str | None,
    baseline: MeasurementBundle,
    candidate: MeasurementBundle,
    rule: ComparisonRule | None,
    profile: ComparisonProfile | None,
    declarations_block: str | None,
) -> MetricComparison:
    if metric == "thd_percent" and (
        baseline.harmonic.status != "success" or candidate.harmonic.status != "success"
    ):
        return MetricComparison(
            metric=metric,
            status="not_comparable",
            reason_codes=("harmonic_tool_not_success",),
        )
    try:
        base_ref = _source_ref(
            metric=metric,
            source_tool=source_tool,
            expected_unit=expected_unit,
            bundle=baseline,
            side="baseline",
        )
        cand_ref = _source_ref(
            metric=metric,
            source_tool=source_tool,
            expected_unit=expected_unit,
            bundle=candidate,
            side="candidate",
        )
        _assert_evidence_matches_tool_output(metric, source_tool, baseline, base_ref)
        _assert_evidence_matches_tool_output(metric, source_tool, candidate, cand_ref)
    except ValueError as error:
        if _is_admission_violation(str(error)):
            raise
        return MetricComparison(
            metric=metric,
            status="not_comparable",
            reason_codes=(str(error),),
        )

    if metric == "thd_percent":
        blocked = _thd_blocked(
            baseline=baseline,
            candidate=candidate,
            profile=profile,
            base_ref=base_ref,
            cand_ref=cand_ref,
        )
        if blocked:
            return MetricComparison(
                metric=metric,
                baseline_ref=base_ref,
                candidate_ref=cand_ref,
                status="not_comparable",
                reason_codes=(blocked,),
            )

    if declarations_block and rule is not None:
        return MetricComparison(
            metric=metric,
            baseline_ref=base_ref,
            candidate_ref=cand_ref,
            status="not_comparable",
            reason_codes=(declarations_block,),
        )

    difference, difference_unit, difference_block = _compute_difference(
        metric=metric,
        baseline_value=base_ref.value,
        candidate_value=cand_ref.value,
        rule=rule,
    )

    if profile is None or rule is None:
        return MetricComparison(
            metric=metric,
            baseline_ref=base_ref,
            candidate_ref=cand_ref,
            difference=difference,
            difference_unit=difference_unit,
            status="descriptive_only",
            reason_codes=("no_approved_profile",),
            rule_ref=None,
        )

    if difference is None:
        return MetricComparison(
            metric=metric,
            baseline_ref=base_ref,
            candidate_ref=cand_ref,
            status="not_comparable",
            reason_codes=(difference_block or "difference_not_defined",),
        )

    if rule.allowed_min <= difference <= rule.allowed_max:
        status: MetricStatus = "no_regression_detected"
    else:
        status = "regression_detected"
    return MetricComparison(
        metric=metric,
        baseline_ref=base_ref,
        candidate_ref=cand_ref,
        difference=difference,
        difference_unit=difference_unit,
        status=status,
        reason_codes=(),
        rule_ref=rule.rule_id,
    )


def _thd_blocked(
    *,
    baseline: MeasurementBundle,
    candidate: MeasurementBundle,
    profile: ComparisonProfile | None,
    base_ref: SourceRef,
    cand_ref: SourceRef,
) -> str | None:
    if baseline.harmonic.status != "success" or candidate.harmonic.status != "success":
        return "harmonic_tool_not_success"
    if base_ref.validity != "valid" or cand_ref.validity != "valid":
        return "harmonic_evidence_not_valid"
    if profile is None or profile.harmonic_fundamental_applicability is None:
        return "harmonic_applicability_not_configured"
    base_f0 = baseline.harmonic.result.fundamental_frequency_hz if baseline.harmonic.result else None
    cand_f0 = candidate.harmonic.result.fundamental_frequency_hz if candidate.harmonic.result else None
    if base_f0 is None or cand_f0 is None:
        return "harmonic_fundamental_missing"
    delta = abs(base_f0 - cand_f0)
    if delta > profile.harmonic_fundamental_applicability.max_fundamental_delta_hz:
        return "fundamental_incompatible"
    return None


def _source_ref(
    *,
    metric: str,
    source_tool: ToolName,
    expected_unit: str | None,
    bundle: MeasurementBundle,
    side: ComparisonSide,
) -> SourceRef:
    tool_result = _tool_for_metric(bundle, source_tool)
    if tool_result.status == "error":
        raise ValueError(f"{source_tool} tool error on {side}")
    evidence = _find_evidence(tool_result, metric)
    if evidence is None:
        raise ValueError(f"missing {metric} evidence on {side}")
    if evidence.source_tool != source_tool:
        raise ValueError("source_tool mismatch for evidence")
    if evidence.unit != expected_unit:
        raise ValueError(f"unit mismatch for {metric}")
    if evidence.validity != "valid":
        raise ValueError(f"invalid harmonic evidence for {metric}")
    value = _as_compare_float(evidence)
    if evidence.channel != bundle.identity.channel:
        raise ValueError("evidence channel mismatch")
    if not _time_range_matches(bundle.identity, evidence.time_range):
        raise ValueError("resolved range mismatch for evidence")
    return SourceRef(
        side=side,
        run_id=bundle.identity.run_id,
        wav_sha256=bundle.identity.wav_sha256,
        bundle_digest=bundle.digest,
        evidence_id=evidence.evidence_id,
        source_tool=evidence.source_tool,
        call_id=evidence.call_id,
        metric=evidence.metric,
        value=value,
        unit=evidence.unit,
        validity=evidence.validity,
        channel=evidence.channel,
        time_range=evidence.time_range,
    )


def _tool_for_metric(bundle: MeasurementBundle, source_tool: ToolName) -> ToolResult:
    if source_tool == "detect_clipping":
        return bundle.clipping
    if source_tool == "analyze_harmonic_distortion":
        return bundle.harmonic
    raise ValueError(f"unsupported source_tool {source_tool}")


def _find_evidence(tool_result: ToolResult, metric: str) -> Evidence | None:
    for item in tool_result.evidence:
        if item.metric == metric:
            return item
    return None


def _is_admission_violation(message: str) -> bool:
    tokens = (
        "unit mismatch",
        "source_tool mismatch",
        "bool cannot",
        "int cannot",
        "missing ",
        "evidence missing",
        "tool_parameter",
        "resolved",
        "evidence_id mismatch",
    )
    return any(token in message for token in tokens)


def _assert_evidence_matches_tool_output(
    metric: str,
    source_tool: ToolName,
    bundle: MeasurementBundle,
    ref: SourceRef,
) -> None:
    tool = _tool_for_metric(bundle, source_tool)
    if tool.result is None:
        return
    if metric == "clipping_ratio":
        expected = tool.result.clipping_ratio
    elif metric == "thd_percent":
        expected = tool.result.thd_percent
    else:
        return
    if expected is None:
        return
    if float(expected) != ref.value:
        raise ValueError(f"evidence value mismatch for {metric}")


def _as_compare_float(evidence: Evidence) -> float:
    value = evidence.value
    if isinstance(value, bool):
        # Admission API surfaces typed rejects as ValueError (not TypeError).
        raise ValueError("bool cannot substitute for float metric value")  # noqa: TRY004
    if isinstance(value, int):
        raise ValueError("int cannot substitute for float metric value")  # noqa: TRY004
    if not isinstance(value, float):
        raise ValueError("metric value must be float")  # noqa: TRY004
    if not math.isfinite(value):
        raise ValueError("metric value must be finite")
    return value


def _time_range_matches(identity, evidence_range: TimeRange | None) -> bool:
    snap = identity.tool_parameter_snapshot
    selection_range = snap.clipping.time_range or TimeRange()
    return selection_range == (evidence_range or TimeRange())


def _compute_difference(
    *,
    metric: str,
    baseline_value: float,
    candidate_value: float,
    rule: ComparisonRule | None,
) -> tuple[float | None, str | None, str | None]:
    if rule is None:
        diff = candidate_value - baseline_value
        unit = "percentage_points" if metric == "thd_percent" else None
        return diff, unit, None
    if rule.difference == "signed_absolute":
        diff = candidate_value - baseline_value
        unit = "percentage_points" if metric == "thd_percent" else None
        return diff, unit, None
    floor = rule.denominator_floor
    if floor is None or abs(baseline_value) <= floor:
        return None, None, "denominator_below_floor"
    relative = (candidate_value - baseline_value) / abs(baseline_value)
    if not math.isfinite(relative):
        return None, None, "non_finite_relative_difference"
    return relative, None, None


def _coverage_for_metric(
    metric: str,
    baseline: MeasurementBundle,
    candidate: MeasurementBundle,
    row: MetricComparison,
) -> CoverageEntry:
    tool_name: ToolName = (
        "detect_clipping" if metric == "clipping_ratio" else "analyze_harmonic_distortion"
    )
    tool = _tool_for_metric(baseline, tool_name)
    other = _tool_for_metric(candidate, tool_name)
    if tool.status == "error" or other.status == "error":
        return CoverageEntry(check_id=metric, status="failed", detail="tool_error")
    if row.status == "not_comparable":
        return CoverageEntry(check_id=metric, status="blocked", detail=row.reason_codes[0] if row.reason_codes else None)
    if row.status == "descriptive_only":
        return CoverageEntry(check_id=metric, status="skipped", detail="descriptive_only")
    return CoverageEntry(check_id=metric, status="satisfied")


def _overall_pass(
    metrics: list[MetricComparison],
    clipping_facts: tuple[ClippingFactSnapshot, ...],
    declarations_block: str | None,
    profile: ComparisonProfile | None,
) -> bool | None:
    if profile is None:
        return None
    if declarations_block:
        return False
    if any(item.tool_status == "error" for item in clipping_facts):
        return False
    ruled = [item for item in metrics if item.rule_ref is not None]
    if not ruled:
        return False
    if any(item.status == "regression_detected" for item in ruled):
        return False
    if any(item.status == "not_comparable" for item in metrics):
        return False
    return all(item.status == "no_regression_detected" for item in ruled)


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _record_digest(record: ComparisonRecord) -> str:
    payload = record.model_dump(mode="json")
    payload.pop("digest", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
