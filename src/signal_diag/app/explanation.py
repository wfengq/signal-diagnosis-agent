"""Explanation layer (D055, §30): packet, next-step menu, validation and template.

The explanation reads a finished run and never changes its verdict. A packet is
built deterministically from the run's claims, cited Evidence or facts, rule
evaluations, localization and knowledge. A model may only rephrase it: every
sentence cites packet items, every number equals a cited display value, and
next steps come from a deterministic menu. Anything else is rejected and the
deterministic template is used instead (a template, never a stub planner).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.agent.models import AgentRunResult
from signal_diag.app.fault_localization import FaultLocalization
from signal_diag.app.sweep import SweepDiagnosis
from signal_diag.knowledge import KnowledgeIndex
from signal_diag.knowledge.models import KnowledgeChunk

PACKET_VERSION = "explain-packet-1.0"
TEMPLATE_VERSION = "explain-template-1.0"
Language = Literal["zh", "en"]
RunKind = Literal["contextual", "sweep"]
FaultType = Literal["clipping", "harmonic_distortion", "no_supported_fault", "inconclusive"]
ItemKind = Literal[
    "run", "claim", "evidence", "fact", "rule_evaluation", "knowledge", "localization", "level"
]
SectionKind = Literal["conclusion", "evidence", "meaning", "next_steps"]
SECTION_ORDER: tuple[SectionKind, ...] = ("conclusion", "evidence", "meaning", "next_steps")
MAX_SENTENCES = 4
MAX_CHARS = 200
_KNOWLEDGE_FAULT: dict[str, FaultType] = {
    "clipping": "clipping",
    "harmonic_distortion": "harmonic_distortion",
    "inconclusive": "inconclusive",
}


class PacketItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ref_id: str = Field(min_length=1)
    kind: ItemKind
    label: str
    detail: str = ""
    values: tuple[str, ...] = ()
    supports: tuple[FaultType, ...] = ()
    level: str | None = None
    band: str | None = None
    observed: str | None = None
    threshold: str | None = None
    comparator: str | None = None
    judgment: str | None = None


class NextStepOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str
    trigger_refs: tuple[str, ...] = Field(min_length=1)


class ExplanationPacket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    packet_version: str = PACKET_VERSION
    run_kind: RunKind
    run_id: str
    mode: str
    outcome: str
    claim_ids: tuple[str, ...]
    items: tuple[PacketItem, ...]
    next_steps: tuple[NextStepOption, ...]

    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def item(self, ref_id: str) -> PacketItem | None:
        return next((item for item in self.items if item.ref_id == ref_id), None)


class ExplanationSentence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    refs: tuple[str, ...]


class ExplanationStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str
    text: str = Field(min_length=1)
    refs: tuple[str, ...]


class ExplanationSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SectionKind
    sentences: tuple[ExplanationSentence, ...] = ()
    steps: tuple[ExplanationStep, ...] = ()


class ExplanationDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sections: tuple[ExplanationSection, ...]


class ExplanationRejected(ValueError):
    """The draft failed a validation check; ``check`` names it."""

    def __init__(self, check: str, detail: str) -> None:
        super().__init__(f"{check}: {detail}")
        self.check = check


# --- display values ---------------------------------------------------------


def display(value: object, unit: str | None = None) -> str | None:
    """The one textual form of a number that explanations may quote."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    number = float(value)
    if unit == "%":
        return f"{number:.2f}%"
    if unit == "Hz":
        if abs(number) >= 1000 or number.is_integer():
            return f"{number:.0f} Hz"
        return f"{number:.1f} Hz"
    if unit in ("dB", "ppm"):
        return f"{number:.1f} {unit}"
    if unit == "s":
        return f"{number:.2f} s"
    if isinstance(value, int):
        return str(value)
    if number == 0 or abs(number) >= 0.01:
        return f"{number:.4g}" if abs(number) < 1e4 else f"{number:.0f}"
    return f"{number:.6f}"


def _values(*entries: tuple[object, str | None]) -> tuple[str, ...]:
    shown = (display(value, unit) for value, unit in entries)
    return tuple(dict.fromkeys(text for text in shown if text is not None))


# --- packet builders ---------------------------------------------------------


def _evaluation_item(
    ref_id: str,
    rule_id: str,
    judgment: str,
    comparator: str,
    observed: object,
    threshold: object,
    unit: str | None,
    profile: str,
    supports: tuple[str, ...],
    *,
    level: str | None = None,
    band_hz: float | None = None,
) -> PacketItem:
    band = display(band_hz, "Hz") if band_hz is not None else None
    shown_observed = display(observed, unit)
    shown_threshold = display(threshold, unit)
    return PacketItem(
        ref_id=ref_id,
        kind="rule_evaluation",
        label=rule_id,
        detail=f"{profile} (demonstration threshold)",
        values=tuple(
            text for text in (level, band, shown_observed, shown_threshold) if text is not None
        ),
        supports=supports,  # type: ignore[arg-type]
        level=level,
        band=band,
        observed=shown_observed,
        threshold=shown_threshold,
        comparator=comparator,
        judgment=judgment,
    )


def _knowledge_items(chunks: Iterable[KnowledgeChunk]) -> list[PacketItem]:
    items: dict[str, PacketItem] = {}
    for chunk in chunks:
        fault = next((_KNOWLEDGE_FAULT[tag] for tag in chunk.tags if tag in _KNOWLEDGE_FAULT), None)
        if fault is None:
            stem = chunk.chunk_id.removeprefix("chunk_").rsplit("_", 1)[0]
            fault = _KNOWLEDGE_FAULT.get(stem)
        items[chunk.chunk_id] = PacketItem(
            ref_id=chunk.chunk_id,
            kind="knowledge",
            label=chunk.title,
            detail=" ".join(chunk.excerpt.split()),
            supports=(fault,) if fault else (),
        )
    return list(items.values())


def contextual_packet(
    result: AgentRunResult,
    *,
    mode: str,
    fault_localization: FaultLocalization | None = None,
) -> ExplanationPacket:
    """Packet for a finished contextual run (engine or planner path)."""
    diagnosis = result.diagnosis
    if diagnosis is None:
        raise ValueError("run has no diagnosis to explain")
    evidence = {item.evidence_id: item for item in result.evidence}
    evaluations = {
        item.evaluation_id: item for batch in result.rule_evaluation_batches for item in batch.evaluations
    }
    supports: dict[str, set[str]] = {}
    for claim in diagnosis.claims:
        for ref in (*claim.evidence_refs, *claim.rule_refs):
            supports.setdefault(ref, set()).add(claim.fault_type)
        for ref in claim.rule_refs:
            for ev_ref in evaluations[ref].evidence_refs if ref in evaluations else ():
                supports.setdefault(ev_ref, set()).add(claim.fault_type)

    items: list[PacketItem] = [
        PacketItem(
            ref_id=f"run_{result.run_id}",
            kind="run",
            label=f"{mode} / {diagnosis.outcome}",
            detail="; ".join(diagnosis.limitations),
        )
    ]
    for claim in diagnosis.claims:
        items.append(
            PacketItem(
                ref_id=claim.claim_id,
                kind="claim",
                label=claim.fault_type,
                detail=claim.statement,
                supports=(claim.fault_type,),
            )
        )
    cited_evaluations = [ref for ref in dict.fromkeys(r for c in diagnosis.claims for r in c.rule_refs)]
    for ref in cited_evaluations:
        evaluation = evaluations.get(ref)
        if evaluation is None:
            continue
        unit = next(
            (evidence[e].unit for e in evaluation.evidence_refs if e in evidence and evidence[e].unit),
            None,
        )
        items.append(
            _evaluation_item(
                evaluation.evaluation_id,
                evaluation.rule_id,
                evaluation.judgment,
                evaluation.comparator,
                evaluation.observed_value,
                evaluation.threshold,
                unit,
                f"{evaluation.profile_id} {evaluation.profile_version}",
                tuple(sorted(supports.get(ref, ()))),
            )
        )
    cited_evidence = dict.fromkeys(
        [
            *(r for c in diagnosis.claims for r in c.evidence_refs),
            *(e for ref in cited_evaluations if ref in evaluations for e in evaluations[ref].evidence_refs),
        ]
    )
    inconclusive = tuple(c.fault_type for c in diagnosis.claims if c.fault_type == "inconclusive")
    for reason in result.evidence:
        if reason.metric == "invalid_reason" and inconclusive:
            cited_evidence.setdefault(reason.evidence_id, None)
            supports.setdefault(reason.evidence_id, set()).add("inconclusive")
    for ref in cited_evidence:
        item = evidence.get(ref)
        if item is None:
            continue
        items.append(
            PacketItem(
                ref_id=item.evidence_id,
                kind="evidence",
                label=item.metric,
                detail=item.validity if isinstance(item.value, (bool, int, float)) else str(item.value),
                values=_values((item.value, item.unit)),
                supports=tuple(sorted(supports.get(ref, ()))),  # type: ignore[arg-type]
            )
        )
    if fault_localization is not None:
        for index, interval in enumerate(fault_localization.intervals):
            items.append(
                PacketItem(
                    ref_id=f"loc_{index}",
                    kind="localization",
                    label=f"{interval.fault} on {interval.channel}",
                    values=_values((interval.start_s, "s"), (interval.end_s, "s")),
                    supports=(interval.fault,) if interval.agrees_with_diagnosis else (),
                )
            )
    items.extend(
        _knowledge_items(chunk for retrieval in result.knowledge_retrievals for chunk in retrieval.chunks)
    )
    packet = ExplanationPacket(
        run_kind="contextual",
        run_id=result.run_id,
        mode=mode,
        outcome=diagnosis.outcome,
        claim_ids=tuple(claim.claim_id for claim in diagnosis.claims),
        items=tuple(items),
        next_steps=(),
    )
    return packet.model_copy(update={"next_steps": _contextual_menu(packet, result)})


def sweep_packet(diagnosis: SweepDiagnosis, knowledge: KnowledgeIndex) -> ExplanationPacket:
    """Packet for a sweep run, with knowledge retrieved by fault tags."""
    items: list[PacketItem] = [
        PacketItem(
            ref_id=diagnosis.run_id,
            kind="run",
            label=f"sweep / {diagnosis.outcome}",
            detail=diagnosis.summary,
            values=tuple(level.level_label for level in diagnosis.levels if diagnosis.onset_level == level.level_label),
        )
    ]
    faults: set[str] = set()
    for index, level in enumerate(diagnosis.levels):
        level_faults = tuple(dict.fromkeys(claim.fault_type for claim in level.claims))
        faults.update(level_faults)
        items.append(
            PacketItem(
                ref_id=f"lvl_{index + 1}",
                kind="level",
                label=level.level_label,
                detail=level.outcome,
                values=(level.level_label,),
                supports=level_faults,
            )
        )
        units = {fact.fact_id: fact.unit for fact in level.measurement.facts}
        facts = {fact.fact_id: fact for fact in level.measurement.facts}
        bands = {band.center_hz: band for band in level.measurement.bands}
        evaluations = {item.evaluation_id: item for item in level.rule_evaluations}
        for claim in level.claims:
            orders = tuple(
                str(bands[center].dominant_order)
                for center in claim.bands_hz
                if center in bands and bands[center].dominant_order is not None
            )
            span = level.measurement.clipped_frequency_hz if claim.fault_type == "clipping" else None
            items.append(
                PacketItem(
                    ref_id=claim.claim_id,
                    kind="claim",
                    label=claim.fault_type,
                    level=level.level_label,
                    detail=f"{level.level_label}: {claim.statement}",
                    values=tuple(
                        dict.fromkeys(
                            (
                                level.level_label,
                                *_values(*((center, "Hz") for center in claim.bands_hz)),
                                *orders,
                                *(_values((span[0], "Hz"), (span[1], "Hz")) if span else ()),
                            )
                        )
                    ),
                    supports=(claim.fault_type,),
                )
            )
            for ref in claim.rule_refs:
                evaluation = evaluations[ref]
                unit = next((units[f] for f in evaluation.fact_refs if units.get(f)), None)
                items.append(
                    _evaluation_item(
                        evaluation.evaluation_id,
                        evaluation.rule_id,
                        evaluation.judgment,
                        evaluation.comparator,
                        evaluation.observed_value,
                        evaluation.threshold,
                        unit,
                        f"{evaluation.profile_id} {evaluation.profile_version}",
                        (claim.fault_type,),
                        level=level.level_label,
                        band_hz=evaluation.band_hz,
                    )
                )
            for ref in claim.fact_refs:
                fact = facts[ref]
                band = _values((fact.band_hz, "Hz")) if fact.band_hz is not None else ()
                items.append(
                    PacketItem(
                        ref_id=fact.fact_id,
                        kind="fact",
                        label=fact.metric,
                        values=(level.level_label, *band, *_values((fact.value, fact.unit))),
                        supports=(claim.fault_type,),
                    )
                )
    tags = [tag for fault, tag in (("clipping", "clipping"), ("harmonic_distortion", "harmonic-distortion"), ("inconclusive", "inconclusive")) if fault in faults]
    if tags:
        items.extend(_knowledge_items(knowledge.retrieve(query_text="", tags=tags, max_results=6).chunks))
    unique = tuple({item.ref_id: item for item in items}.values())
    packet = ExplanationPacket(
        run_kind="sweep",
        run_id=diagnosis.run_id,
        mode="sweep",
        outcome=diagnosis.outcome,
        claim_ids=tuple(claim.claim_id for level in diagnosis.levels for claim in level.claims),
        items=unique,
        next_steps=(),
    )
    return packet.model_copy(update={"next_steps": _sweep_menu(packet, diagnosis)})


# --- next-step menu -----------------------------------------------------------


def _claims_of(packet: ExplanationPacket, fault: str) -> tuple[str, ...]:
    return tuple(item.ref_id for item in packet.items if item.kind == "claim" and item.label == fault)


def _contextual_menu(packet: ExplanationPacket, result: AgentRunResult) -> tuple[NextStepOption, ...]:
    menu: list[NextStepOption] = []
    clipping = _claims_of(packet, "clipping")
    if clipping:
        menu.append(NextStepOption(step_id="lower_playback_level", trigger_refs=clipping))
    if packet.mode == "single_signal":
        menu.append(NextStepOption(step_id="add_reference_recording", trigger_refs=packet.claim_ids))
        menu.append(NextStepOption(step_id="state_nominal_tone", trigger_refs=packet.claim_ids))
    inconclusive = _claims_of(packet, "inconclusive")
    if inconclusive or packet.mode == "single_signal":
        menu.append(NextStepOption(step_id="run_sweep_test", trigger_refs=inconclusive or packet.claim_ids))
    if packet.mode == "paired_reference" and inconclusive:
        invalid = tuple(
            item.ref_id
            for item in packet.items
            if item.kind == "rule_evaluation"
            and item.label == "rule_contextual_analysis_valid"
            and item.judgment == "fail"
        )
        if invalid:
            menu.append(NextStepOption(step_id="check_reference_match", trigger_refs=invalid))
    del result
    return tuple(menu)


def _failing(packet: ExplanationPacket, rule_id: str) -> tuple[str, ...]:
    return tuple(
        item.ref_id
        for item in packet.items
        if item.kind == "rule_evaluation" and item.label == rule_id and item.judgment != "pass"
    )


def _sweep_menu(packet: ExplanationPacket, diagnosis: SweepDiagnosis) -> tuple[NextStepOption, ...]:
    menu: list[NextStepOption] = []
    faults = _claims_of(packet, "clipping") + _claims_of(packet, "harmonic_distortion")
    if faults:
        menu.append(NextStepOption(step_id="lower_playback_level", trigger_refs=faults))
    if _claims_of(packet, "clipping"):
        menu.append(NextStepOption(step_id="check_recorder_gain", trigger_refs=_claims_of(packet, "clipping")))
    if faults and len(diagnosis.levels) == 1:
        menu.append(NextStepOption(step_id="add_sweep_levels", trigger_refs=faults))
    for step, rule in (
        ("record_whole_stimulus", "rule_sweep_analysis_valid"),
        ("check_stimulus_file", "rule_sweep_alignment_acceptable"),
        ("use_one_clock", "rule_sweep_drift_acceptable"),
        ("rerecord_quieter", "rule_sweep_snr_acceptable"),
    ):
        refs = _failing(packet, rule)
        if refs:
            menu.append(NextStepOption(step_id=step, trigger_refs=refs))
    return tuple(menu)


# --- validation -------------------------------------------------------------

_NUMBER = re.compile(
    r"(?<![A-Za-z0-9_.])([-−]?\d+(?:\.\d+)?)\s*(kHz|Hz|dBFS|dB|ppm|ms|s|%)?",
)
_ID_IN_TEXT = re.compile(r"\b(?:claim|ev|ruleval|swr|swf|swc|swm|swrun|chunk|know|loc|lvl|run)_[0-9a-z]")
_BANNED = ("标准", "合格", "达标", "认证", "IEC", "AES", "standard", "SLA", "compliant", "certified")
_THRESHOLD_WORDS = ("阈值", "限值", "门限", "threshold", "limit")
_DEMO_WORDS = ("演示", "demo")
_FAULT_TERMS: dict[str, tuple[str, ...]] = {
    "clipping": ("削波", "截幅", "clipping", "clipped"),
    "harmonic_distortion": ("谐波失真", "harmonic distortion"),
    "no_supported_fault": (
        "未发现受支持的故障",
        "没有发现故障",
        "没有问题",
        "一切正常",
        "no supported fault",
        "no fault",
        "no problem",
    ),
    "inconclusive": ("无法判定", "无法下结论", "不能确定", "inconclusive", "cannot be judged"),
}
_NEGATIONS = ("没有", "未", "不", "无", "非", "no ", "not ", "without ", "neither ", "nor ")


def _parse_numbers(text: str) -> list[tuple[float, str | None, int]]:
    numbers: list[tuple[float, str | None, int]] = []
    for match in _NUMBER.finditer(text.replace("−", "-")):
        raw, unit = match.group(1), match.group(2)
        value = float(raw)
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if unit == "kHz":
            value, unit, decimals = value * 1000, "Hz", max(0, decimals - 3)
        elif unit == "ms":
            value, unit, decimals = value / 1000, "s", decimals + 3
        elif unit == "dBFS":
            unit = "dB"
        numbers.append((value, unit, decimals))
    return numbers


def _number_allowed(number: tuple[float, str | None, int], allowed: list[tuple[float, str | None, int]]) -> bool:
    value, unit, decimals = number
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9
    for candidate, candidate_unit, _ in allowed:
        if unit is not None and candidate_unit != unit:
            continue
        if abs(candidate - value) <= tolerance:
            return True
    return False


def _affirmed(text: str, term: str) -> bool:
    lowered = text.lower()
    start = 0
    while (index := lowered.find(term.lower(), start)) >= 0:
        before = lowered[max(0, index - 8) : index]
        if not any(negation in before for negation in _NEGATIONS):
            return True
        start = index + 1
    return False


def _check_sentence(
    text: str, refs: Sequence[str], packet: ExplanationPacket, section: SectionKind
) -> None:
    if len(text) > MAX_CHARS:
        raise ExplanationRejected("length", f"sentence longer than {MAX_CHARS} characters")
    if not refs:
        raise ExplanationRejected("citation", "sentence without references")
    items = []
    for ref in refs:
        item = packet.item(ref)
        if item is None:
            raise ExplanationRejected("citation", f"unknown reference {ref}")
        items.append(item)
    if _ID_IN_TEXT.search(text):
        raise ExplanationRejected("ids_in_text", "identifiers belong in refs, not in text")
    lowered = text.lower()
    for word in _BANNED:
        if word.lower() in lowered:
            raise ExplanationRejected("wording", f"forbidden wording {word!r}")
    if any(word in lowered for word in _THRESHOLD_WORDS) and not any(
        word in lowered for word in _DEMO_WORDS
    ):
        raise ExplanationRejected("wording", "thresholds must be called demonstration values")
    allowed = [number for item in items for value in item.values for number in _parse_numbers(value)]
    for number in _parse_numbers(text):
        if not _number_allowed(number, allowed):
            raise ExplanationRejected("number", f"number {number[0]:g} is not a cited value")
    supported = {fault for item in items for fault in item.supports}
    for fault, terms in _FAULT_TERMS.items():
        negatable = fault in ("clipping", "harmonic_distortion")
        # Rule and metric names name faults ("clipping ratio"); only the
        # conclusion and meaning may not assert a fault they do not cite.
        if negatable and section not in ("conclusion", "meaning"):
            continue
        mentioned = any(
            (_affirmed(text, term) if negatable else term.lower() in lowered) for term in terms
        )
        if mentioned and fault not in supported:
            raise ExplanationRejected("fault_mismatch", f"mentions {fault} without citing it")


def validate_explanation(draft: ExplanationDraft, packet: ExplanationPacket) -> None:
    """Raise ``ExplanationRejected`` unless the draft passes every §30 check."""
    kinds = tuple(section.kind for section in draft.sections)
    if kinds != SECTION_ORDER:
        raise ExplanationRejected("structure", f"sections must be {SECTION_ORDER}")
    by_kind = {section.kind: section for section in draft.sections}
    for section in draft.sections:
        if section.kind == "next_steps":
            if section.sentences:
                raise ExplanationRejected("structure", "next_steps holds steps only")
            if len(section.steps) > MAX_SENTENCES:
                raise ExplanationRejected("structure", "too many steps")
            continue
        if section.steps:
            raise ExplanationRejected("structure", f"{section.kind} holds sentences only")
        if len(section.sentences) > MAX_SENTENCES:
            raise ExplanationRejected("structure", f"too many sentences in {section.kind}")
        for sentence in section.sentences:
            _check_sentence(sentence.text, sentence.refs, packet, section.kind)
    conclusion = by_kind["conclusion"].sentences
    if not conclusion:
        raise ExplanationRejected("structure", "conclusion is empty")
    claim_ids = set(packet.claim_ids)
    for sentence in conclusion:
        if not claim_ids & set(sentence.refs):
            raise ExplanationRejected("conclusion", "each conclusion sentence cites a claim")
    covered = {ref for sentence in conclusion for ref in sentence.refs}
    if not claim_ids <= covered:
        raise ExplanationRejected("conclusion", "conclusion must cite every claim")
    menu = {option.step_id: option for option in packet.next_steps}
    seen: set[str] = set()
    for step in by_kind["next_steps"].steps:
        option = menu.get(step.step_id)
        if option is None:
            raise ExplanationRejected("next_step", f"{step.step_id} is not on the menu")
        if step.step_id in seen:
            raise ExplanationRejected("next_step", f"{step.step_id} repeated")
        seen.add(step.step_id)
        if not set(option.trigger_refs) & set(step.refs):
            raise ExplanationRejected("next_step", f"{step.step_id} must cite its trigger")
        _check_sentence(step.text, step.refs, packet, "next_steps")


# --- template ---------------------------------------------------------------

_FAULT_TEXT = {
    "zh": {
        "clipping": "检测到削波",
        "harmonic_distortion": "检测到谐波失真",
        "no_supported_fault": "未发现受支持的故障",
        "inconclusive": "无法判定，规则既不支持某种故障，也不能确认没有故障",
    },
    "en": {
        "clipping": "clipping is supported",
        "harmonic_distortion": "harmonic distortion is supported",
        "no_supported_fault": "no supported fault was found",
        "inconclusive": "the result is inconclusive: the rules neither support a fault nor confirm that none is present",
    },
}
_JUDGMENT = {
    "zh": {"pass": "通过", "fail": "不通过", "not_applicable": "不适用"},
    "en": {"pass": "pass", "fail": "fail", "not_applicable": "not applicable"},
}
_COMPARATOR = {"lt": "<", "lte": "≤", "gt": ">", "gte": "≥", "eq": "=", "neq": "≠"}
RULE_LABELS: dict[str, tuple[str, str]] = {
    "rule_clipping_ratio_acceptable": ("削波比例", "clipping ratio"),
    "rule_test_clipping_ratio_acceptable": ("测试录音的削波比例", "test clipping ratio"),
    "rule_reference_clipping_ratio_acceptable": ("参考录音的削波比例", "reference clipping ratio"),
    "rule_flat_top_absent": ("平顶检查", "flat-top check"),
    "rule_test_flat_top_absent": ("测试录音的平顶检查", "test flat-top check"),
    "rule_reference_flat_top_absent": ("参考录音的平顶检查", "reference flat-top check"),
    "rule_clipping_detected_absent": ("削波事件检查", "clipping event check"),
    "rule_harmonic_analysis_valid": ("谐波分析有效性", "harmonic analysis validity"),
    "rule_thd_acceptable": ("THD", "THD"),
    "rule_nominal_thd_acceptable": ("标称单音的 THD", "nominal-tone THD"),
    "rule_contextual_analysis_valid": ("对比分析有效性", "comparison validity"),
    "rule_contextual_f0_compatible": ("基频一致性", "fundamental match"),
    "rule_even_harmonic_growth_acceptable": ("偶次谐波增长", "even-harmonic growth"),
    "rule_sweep_analysis_valid": ("录音完整性", "recording completeness"),
    "rule_sweep_alignment_acceptable": ("与测试信号的匹配度", "match with the test signal"),
    "rule_sweep_drift_acceptable": ("时钟漂移", "clock drift"),
    "rule_sweep_snr_acceptable": ("信噪比", "signal-to-noise ratio"),
    "rule_sweep_full_scale_acceptable": ("满刻度比例", "full-scale share"),
    "rule_sweep_band_thd_acceptable": ("频段 THD", "band THD"),
}
INVALID_REASONS: dict[str, tuple[str, str]] = {
    "fundamental_incompatible": ("参考与测试的基频不一致", "the reference and test fundamentals differ"),
    "fundamental_incompatible_with_declaration": (
        "测得的基频与声明的频率不一致",
        "the measured fundamental differs from the declared frequency",
    ),
    "alignment_quality_below_threshold": ("参考与测试无法对齐", "the reference and test could not be aligned"),
    "reference_clipping_invalidates_comparison": ("参考录音本身有削波", "the reference itself is clipped"),
    "reference_fundamental_invalid": ("参考录音没有稳定的基频", "the reference has no stable fundamental"),
    "test_fundamental_invalid": ("测试录音没有稳定的基频", "the test recording has no stable fundamental"),
    "reference_too_short": ("参考录音太短", "the reference is too short"),
    "test_too_short": ("测试录音太短", "the test recording is too short"),
    "sample_rate_mismatch": ("两段录音的采样率不同", "the two recordings have different sample rates"),
}
_MEANING = {
    "zh": {
        "clipping": "削波会把波形峰值削平，并带来宽频的谐波能量。",
        "harmonic_distortion": "THD 衡量谐波能量相对基波的大小；规则限值是演示设置，不是通用规范。",
        "no_supported_fault": "在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。",
        "inconclusive": "信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。",
    },
    "en": {
        "clipping": "Clipping flattens waveform peaks and introduces broadband harmonic energy.",
        "harmonic_distortion": "THD summarizes harmonic energy relative to the fundamental; rule limits are demonstration settings, not universal norms.",
        "no_supported_fault": "Within what this run measured every demonstration rule passes; other levels or signals may still distort.",
        "inconclusive": "Harmonic analysis is inconclusive when the signal lacks a stable fundamental or validity checks fail.",
    },
}
STEP_TEXT = {
    "zh": {
        "lower_playback_level": "降低播放电平后重新测试，确认失真是否随电平减小。",
        "check_recorder_gain": "调低录音设备的输入增益，避免录音本身达到满刻度。",
        "add_reference_recording": "补充一段同一信号的干净参考录音，才能判断谐波是否增加。",
        "state_nominal_tone": "如果测试信号是单音，请注明它的频率，以便按标称单音分析。",
        "run_sweep_test": "用扫频测试复测，按频段和电平定位失真。",
        "check_reference_match": "确认参考录音与测试录音使用的是同一个测试信号。",
        "add_sweep_levels": "再录一到两个更低的音量，找出失真从哪一档开始。",
        "rerecord_quieter": "在更安静的环境中重录，或提高播放电平，让扫频明显高于噪声。",
        "check_stimulus_file": "确认播放的是本产品下载的扫频文件，并且没有被处理过。",
        "use_one_clock": "尽量让播放和录音使用同一个声卡或同一个时钟。",
        "record_whole_stimulus": "从播放开始前录到播放结束后，确保录下完整的扫频。",
    },
    "en": {
        "lower_playback_level": "Lower the playback level and test again to see whether the distortion drops.",
        "check_recorder_gain": "Lower the recorder's input gain so the recording itself stays below full scale.",
        "add_reference_recording": "Add a clean reference recording of the same signal so harmonic growth can be judged.",
        "state_nominal_tone": "If the test signal is a single tone, state its frequency for a nominal-tone analysis.",
        "run_sweep_test": "Retest with the sweep test to locate distortion by band and level.",
        "check_reference_match": "Check that the reference and test recordings use the same test signal.",
        "add_sweep_levels": "Record one or two lower levels as well to find where distortion starts.",
        "rerecord_quieter": "Record again in a quieter place or at a higher playback level so the sweep stands well above the noise.",
        "check_stimulus_file": "Check that the played file is the product's sweep file, unprocessed.",
        "use_one_clock": "Play and record on the same audio interface or clock where possible.",
        "record_whole_stimulus": "Start recording before playback and stop after it ends so the whole sweep is captured.",
    },
}


def _conclusion(packet: ExplanationPacket, language: Language) -> list[ExplanationSentence]:
    sentences: list[ExplanationSentence] = []
    claims = [item for item in packet.items if item.kind == "claim"]
    if packet.run_kind == "sweep":
        by_level: dict[str, list[PacketItem]] = {}
        for claim in claims:
            by_level.setdefault(claim.level or "", []).append(claim)
        for level, level_claims in by_level.items():
            parts = []
            for claim in level_claims:
                text = _FAULT_TEXT[language][claim.label]
                bands = [value for value in claim.values if value.endswith("Hz")]
                if claim.label == "harmonic_distortion" and bands:
                    joined = "、".join(bands) if language == "zh" else ", ".join(bands)
                    text += f"（{joined}）" if language == "zh" else f" ({joined})"
                parts.append(text)
            joiner = "；" if language == "zh" else "; "
            head = f"{level}：" if language == "zh" else f"{level}: "
            sentences.append(
                ExplanationSentence(
                    text=head + joiner.join(parts) + ("。" if language == "zh" else "."),
                    refs=tuple(claim.ref_id for claim in level_claims),
                )
            )
        run = next((item for item in packet.items if item.kind == "run"), None)
        onset = run.values[0] if run is not None and run.values else None
        if onset is not None and len(by_level) > 1:
            onset_claims = tuple(claim.ref_id for claim in by_level.get(onset, ()))
            text = f"失真从 {onset} 档开始出现。" if language == "zh" else f"Distortion starts at {onset}."
            sentences.append(ExplanationSentence(text=text, refs=(run.ref_id, *onset_claims)))  # type: ignore[union-attr]
        if len(sentences) > MAX_SENTENCES:
            merged_refs = tuple(ref for sentence in sentences[MAX_SENTENCES - 1 :] for ref in sentence.refs)
            sentences = [*sentences[: MAX_SENTENCES - 1], ExplanationSentence(
                text=sentences[MAX_SENTENCES - 1].text, refs=merged_refs)]
        return sentences
    for claim in claims[:MAX_SENTENCES]:
        text = _FAULT_TEXT[language][claim.label]
        sentences.append(
            ExplanationSentence(
                text=(text + "。") if language == "zh" else (text[:1].upper() + text[1:] + "."),
                refs=(claim.ref_id,),
            )
        )
    extra = tuple(claim.ref_id for claim in claims[MAX_SENTENCES:])
    if extra:
        last = sentences[-1]
        sentences[-1] = last.model_copy(update={"refs": last.refs + extra})
    return sentences


def _band_sentences(items: list[PacketItem], language: Language) -> list[ExplanationSentence]:
    """One sentence per level: the band with the highest failing THD."""
    by_level: dict[str, list[PacketItem]] = {}
    for item in items:
        by_level.setdefault(item.level or "", []).append(item)
    sentences = []
    for level, level_items in by_level.items():
        worst = max(level_items, key=lambda item: float((item.observed or "0").rstrip("%")))
        if language == "zh":
            text = (
                f"{level}：频段 THD 最高 {worst.observed}（{worst.band}），"
                f"高于演示阈值 {worst.threshold}。"
            )
        else:
            text = (
                f"{level}: band THD peaks at {worst.observed} ({worst.band}), "
                f"above the demo threshold {worst.threshold}."
            )
        sentences.append(
            ExplanationSentence(text=text, refs=tuple(item.ref_id for item in level_items))
        )
    return sentences


def _evaluation_sentence(item: PacketItem, language: Language) -> ExplanationSentence:
    labels = RULE_LABELS.get(item.label)
    name = (labels[0] if language == "zh" else labels[1]) if labels else (
        item.label.removeprefix("rule_").replace("_", " ")
    )
    prefix = " ".join(part for part in (item.level, item.band) if part)
    comparator = _COMPARATOR.get(item.comparator or "", item.comparator or "")
    judgment = _JUDGMENT[language].get(item.judgment or "", item.judgment or "")
    if language == "zh":
        parts = [f"{prefix} " if prefix else "", f"{name}"]
        if item.observed is not None:
            parts.append(f"实测 {item.observed}，")
        else:
            parts.append("：")
        if item.threshold is not None:
            parts.append(f"演示阈值 {comparator} {item.threshold}，")
        parts.append(f"判定为{judgment}。")
    else:
        parts = [f"{prefix}: " if prefix else "", name[:1].upper() + name[1:]]
        if item.observed is not None:
            parts.append(f" measured {item.observed}")
        if item.threshold is not None:
            parts.append(f" against the demo threshold {comparator} {item.threshold}")
        parts.append(f": {judgment}.")
    return ExplanationSentence(text="".join(parts), refs=(item.ref_id,))


def template_explanation(packet: ExplanationPacket, language: Language = "zh") -> ExplanationDraft:
    """Deterministic explanation that passes ``validate_explanation`` by construction."""
    evaluations = [item for item in packet.items if item.kind == "rule_evaluation"]
    bands = [item for item in evaluations if item.band is not None and item.judgment == "fail"]
    others = [item for item in evaluations if item not in bands]
    failing = [item for item in others if item.judgment == "fail"]
    passing = [item for item in others if item.judgment == "pass"]
    evidence = _band_sentences(bands, language) + [
        _evaluation_sentence(item, language) for item in (failing or ([] if bands else passing))
    ]
    reason = next((item for item in packet.items if item.label == "invalid_reason"), None)
    if reason is not None and reason.detail in INVALID_REASONS:
        text = INVALID_REASONS[reason.detail][0 if language == "zh" else 1]
        evidence.insert(
            0,
            ExplanationSentence(
                text=f"原因：{text}。" if language == "zh" else f"Reason: {text}.",
                refs=(reason.ref_id,),
            ),
        )
    evidence = evidence[:MAX_SENTENCES]
    claim_faults = [item.label for item in packet.items if item.kind == "claim"]
    if any(fault in ("clipping", "harmonic_distortion") for fault in claim_faults):
        claim_faults = [fault for fault in claim_faults if fault != "no_supported_fault"]
    meaning: list[ExplanationSentence] = []
    for fault in dict.fromkeys(claim_faults):
        knowledge = next(
            (item for item in packet.items if item.kind == "knowledge" and fault in item.supports and "Interpretation" in item.label),
            None,
        ) or next((item for item in packet.items if item.kind == "knowledge" and fault in item.supports), None)
        claim = next(item for item in packet.items if item.kind == "claim" and item.label == fault)
        refs = (knowledge.ref_id, claim.ref_id) if knowledge else (claim.ref_id,)
        meaning.append(ExplanationSentence(text=_MEANING[language][fault], refs=refs))
    steps = tuple(
        ExplanationStep(step_id=option.step_id, text=STEP_TEXT[language][option.step_id], refs=option.trigger_refs)
        for option in packet.next_steps[:MAX_SENTENCES]
    )
    draft = ExplanationDraft(
        sections=(
            ExplanationSection(kind="conclusion", sentences=tuple(_conclusion(packet, language))),
            ExplanationSection(kind="evidence", sentences=tuple(evidence)),
            ExplanationSection(kind="meaning", sentences=tuple(meaning[:MAX_SENTENCES])),
            ExplanationSection(kind="next_steps", steps=steps),
        )
    )
    validate_explanation(draft, packet)
    return draft


__all__ = [
    "PACKET_VERSION",
    "SECTION_ORDER",
    "STEP_TEXT",
    "TEMPLATE_VERSION",
    "ExplanationDraft",
    "ExplanationPacket",
    "ExplanationRejected",
    "ExplanationSection",
    "ExplanationSentence",
    "ExplanationStep",
    "Language",
    "NextStepOption",
    "PacketItem",
    "contextual_packet",
    "display",
    "sweep_packet",
    "template_explanation",
    "validate_explanation",
]
