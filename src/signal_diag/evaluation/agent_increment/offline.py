"""Scripted three-arm offline run. It never opens a model connection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from signal_diag.agent.intake import (
    INTAKE_PLANNER_IDENTITY,
    ConfirmedContext,
    ContextDraft,
    IntakeRequest,
)
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_12
from signal_diag.evaluation.agent_increment.budget import (
    DEV_STAGE_CAP,
    HELD_OUT_STAGE_CAP,
)
from signal_diag.evaluation.agent_increment.campaign import (
    dry_run_summary,
    write_report,
)
from signal_diag.evaluation.agent_increment.cases import STUDY_ID
from signal_diag.evaluation.agent_increment.intake_baseline import (
    B1_RULE_TABLE_ID,
    parse_b1,
)
from signal_diag.evaluation.agent_increment.models import (
    ArmOutcome,
    CaseTruth,
    IncrementCase,
)
from signal_diag.evaluation.agent_increment.scoring import FamilyScore, score_family
from signal_diag.evaluation.agent_increment.segment_baseline import (
    B2_PARAMETER_ID,
    scan_signal,
)
from signal_diag.evaluation.agent_increment.segment_support import (
    SEGMENT_PROFILE_ID,
    SegmentSupport,
    load_segment_profile,
    segment_supports,
)
from signal_diag.evaluation.agent_increment.simulated_user import (
    confirm_proposed_fields,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.signal.models import ChannelMode, SignalRecord, TimeRange
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.wav import load_wav_bytes
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

_PROMPT_SHA256 = hashlib.sha256(_S1_PROMPT_V9_12.system_prompt.encode("utf-8")).hexdigest()


def load_study_cases(study_dir: Path) -> list[IncrementCase]:
    payload = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
    return [IncrementCase.model_validate(item) for item in payload["cases"]]


def _repo_root(study_dir: Path) -> Path:
    return study_dir.resolve().parents[4]


def _request(case: IncrementCase) -> IntakeRequest:
    names = tuple(Path(path).name for path in case.files)
    return IntakeRequest(text=case.text, filenames=names, test_file=case.test_file)


def _truth_draft(truth: CaseTruth) -> ContextDraft:
    return ContextDraft(
        mode=truth.mode,
        nominal_fundamental_hz=truth.nominal_fundamental_hz,
        reference_file=truth.reference_file,
        stimulus_kind=truth.stimulus_kind,
        missing_fields=(),
        questions=(),
    )


def _same(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return abs(left - right) <= 1e-6


def _context_grade(confirmed: ConfirmedContext, truth: CaseTruth) -> tuple[int, int, bool]:
    checks = (
        confirmed.mode == truth.mode,
        _same(confirmed.nominal_fundamental_hz, truth.nominal_fundamental_hz),
        confirmed.reference_file == truth.reference_file,
        confirmed.stimulus_kind == truth.stimulus_kind,
    )
    correct = sum(1 for item in checks if item)
    return correct, len(checks), correct == len(checks)


def _t1_outcome(
    case: IncrementCase,
    arm: str,
    confirmed: ConfirmedContext,
    corrections: int,
) -> ArmOutcome:
    correct, graded, all_match = _context_grade(confirmed, case.truth)
    return ArmOutcome(
        case_id=case.case_id,
        family="T1",
        arm=arm,  # type: ignore[arg-type]
        conclusion_correct=all_match,
        unsupported_positive=False,
        evidence_traceable=True,
        context_fields_correct=correct,
        context_fields_graded=graded,
        correction_count=corrections,
        localization_correct=None,
        tool_calls=0,
    )


def _run_t1(case: IncrementCase) -> list[ArmOutcome]:
    request = _request(case)
    truth = _truth_draft(case.truth)
    b1 = confirm_proposed_fields(parse_b1(request), truth)
    agent = confirm_proposed_fields(parse_b1(request), truth)
    weak = ConfirmedContext(
        mode="single_signal",
        nominal_fundamental_hz=None,
        reference_file=None,
        stimulus_kind=None,
    )
    return [
        _t1_outcome(case, "agent", agent.confirmed, agent.correction_count),
        _t1_outcome(case, "strong_fixed", b1.confirmed, b1.correction_count),
        _t1_outcome(case, "weak_fixed", weak, 0),
    ]


def _load_record(study_dir: Path, case: IncrementCase) -> SignalRecord:
    path = _repo_root(study_dir) / case.files[0]
    return load_wav_bytes(path.read_bytes(), filename=path.name).record


def _judge(record: SignalRecord, spans: tuple[TimeRange, ...] | None) -> tuple[tuple[SegmentSupport, ...], int]:
    repository = InMemorySignalRepository()
    repository.put(record)
    tools = SignalToolService(repository)
    evidence: list[Evidence] = []
    calls = 0
    channels: tuple[ChannelMode, ...] = (
        ("mixdown",) if record.meta.channels == 1 else ("left", "right", "mixdown")
    )
    selected = spans
    if selected is None:
        selected = (TimeRange(start_s=0.0, end_s=record.meta.duration_s),)
    for channel in channels:
        for span in selected:
            clipping = tools.detect_clipping(
                record.meta.signal_id,
                ClippingInput(time_range=span, channel=channel),
            )
            calls += 1
            evidence.extend(clipping.evidence)
            harmonic = tools.analyze_harmonic_distortion(
                record.meta.signal_id,
                HarmonicDistortionInput(time_range=span, channel=channel),
            )
            calls += 1
            evidence.extend(harmonic.evidence)
    by_id = {item.evidence_id: item for item in evidence}
    batch = RuleEngine().evaluate_profile(load_segment_profile(), tuple(evidence))
    return segment_supports(batch, by_id), calls


def _agent_spans(record: SignalRecord) -> tuple[TimeRange, ...]:
    duration = record.meta.duration_s
    windows = (0.0, 1.0, max(0.0, duration - 0.25))
    spans: list[TimeRange] = []
    for start in windows:
        end = min(duration, start + 0.25)
        if end > start:
            spans.append(TimeRange(start_s=start, end_s=end))
    return tuple(spans)


def _localized(supports: tuple[SegmentSupport, ...], case: IncrementCase) -> bool | None:
    if not case.truth.fault_spans:
        return None
    for span in case.truth.fault_spans:
        for support in supports:
            if support.fault != case.truth.conclusion:
                continue
            if support.channel != span.channel and support.channel != "mixdown":
                continue
            located = support.time_range
            if located is None or located.end_s is None:
                continue
            if located.start_s < span.end_s and span.start_s < located.end_s:
                return True
    return False


def _t2_outcome(
    case: IncrementCase,
    arm: str,
    supports: tuple[SegmentSupport, ...],
    tool_calls: int,
) -> ArmOutcome:
    positive = tuple(
        item for item in supports if item.fault in {"clipping", "harmonic_distortion"}
    )
    expected = case.truth.conclusion
    if expected in {"inconclusive", "no_supported_fault"}:
        correct = not positive
        unsupported = bool(positive)
    else:
        correct = any(item.fault == expected for item in positive)
        unsupported = False
    traceable = all(item.evidence_id and item.evaluation_id for item in positive)
    return ArmOutcome(
        case_id=case.case_id,
        family="T2",
        arm=arm,  # type: ignore[arg-type]
        conclusion_correct=correct,
        unsupported_positive=unsupported,
        evidence_traceable=traceable,
        context_fields_correct=0,
        context_fields_graded=0,
        correction_count=0,
        localization_correct=_localized(positive, case),
        tool_calls=tool_calls,
    )


def _run_t2(study_dir: Path, case: IncrementCase) -> list[ArmOutcome]:
    record = _load_record(study_dir, case)
    weak_supports, weak_calls = _judge(record, None)
    strong = scan_signal(record)
    agent_supports, agent_calls = _judge(record, _agent_spans(record))
    return [
        _t2_outcome(case, "agent", agent_supports, agent_calls),
        _t2_outcome(case, "strong_fixed", strong.supports, strong.tool_calls),
        _t2_outcome(case, "weak_fixed", weak_supports, weak_calls),
    ]


def study_identity() -> dict[str, object]:
    profile = load_segment_profile()
    return {
        "study_id": STUDY_ID,
        "model": "deepseek-v4-flash",
        "prompt_version": _S1_PROMPT_V9_12.version,
        "prompt_sha256": _PROMPT_SHA256,
        "intake_identity": INTAKE_PLANNER_IDENTITY,
        "rule_profile_id": SEGMENT_PROFILE_ID,
        "rule_profile_version": profile.version,
        "b1_rule_table_id": B1_RULE_TABLE_ID,
        "b2_parameter_id": B2_PARAMETER_ID,
        "http_calls": 0,
        "scripted_stand_in": True,
    }


def run_offline(study_dir: Path, output_dir: Path) -> dict[str, object]:
    cases = load_study_cases(study_dir)
    outcomes: list[ArmOutcome] = []
    for case in cases:
        if case.family == "T1":
            outcomes.extend(_run_t1(case))
        else:
            outcomes.extend(_run_t2(study_dir, case))
    families: list[FamilyScore] = []
    for family in ("T1", "T2"):
        rows = [row for row in outcomes if row.family == family and row.case_id.startswith("held-")]
        if rows:
            families.append(score_family(rows))
    dev_count = sum(case.split == "dev" for case in cases)
    held_count = sum(case.split == "heldout" for case in cases)
    payload: dict[str, object] = {
        "identity": study_identity(),
        "case_count": len(cases),
        "dry_run_dev": dry_run_summary(case_count=dev_count, stage_cap=DEV_STAGE_CAP),
        "dry_run_heldout": dry_run_summary(case_count=held_count, stage_cap=HELD_OUT_STAGE_CAP),
        "families": [item.model_dump(mode="json") for item in families],
        "arms": ["agent", "strong_fixed", "weak_fixed"],
    }
    write_report(output_dir, payload)
    return payload
