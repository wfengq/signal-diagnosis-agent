"""T-CX466–T-CX470: explanation packet, menu, validation and template (D055)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import cache
from pathlib import Path

import numpy as np
import pytest

from signal_diag.agent.models import AgentRunResult
from signal_diag.app.engine_comparison import engine_cases, run_engine
from signal_diag.app.explanation import (
    SECTION_ORDER,
    ExplanationDraft,
    ExplanationPacket,
    ExplanationRejected,
    ExplanationSection,
    ExplanationSentence,
    ExplanationStep,
    contextual_packet,
    display,
    sweep_packet,
    template_explanation,
    validate_explanation,
)
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.sweep import SweepDiagnosis, diagnose_sweep
from signal_diag.dsp.sweep import generate_stimulus
from signal_diag.knowledge import KnowledgeIndex

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
CASES = {
    "clipping": "857fac53e4d2e57e",
    "harmonic": "a4a0853be9983f8c",
    "both": "6fb80bbda391c26c",
    "inconclusive": "163185980dc8f7a4",
    "no_fault": "825a759a0ea47bb7",
}


@cache
def _runs() -> dict[str, tuple[AgentRunResult, str]]:
    wanted = {value: key for key, value in CASES.items()}
    runs: dict[str, tuple[AgentRunResult, str]] = {}
    single = None
    for case in engine_cases(ROOT):
        if case.case_id in wanted or (single is None and case.mode == "single_signal"):
            reference = case.load_reference() if case.load_reference else None
            result = asyncio.run(
                run_engine(
                    case.load_test(),
                    reference,
                    mode=case.mode,
                    nominal_fundamental_hz=case.nominal_fundamental_hz,
                )
            )
            if case.case_id in wanted:
                runs[wanted[case.case_id]] = (result, case.mode)
            else:
                single = (result, case.mode)
    assert single is not None
    runs["single"] = single
    return runs


def _packet(name: str) -> ExplanationPacket:
    result, mode = _runs()[name]
    return contextual_packet(result, mode=mode)


def _sweep_wav(device: Callable[[np.ndarray], np.ndarray]) -> bytes:
    stimulus, _ = generate_stimulus(48_000)
    recording = np.concatenate([np.zeros(9_600), device(stimulus), np.zeros(14_400)])
    return encode_pcm32_wav(recording.astype(np.float32).reshape(-1, 1), sample_rate_hz=48_000)


@cache
def _sweeps() -> dict[str, SweepDiagnosis]:
    rng = np.random.default_rng(20261007)
    return {
        "levels": diagnose_sweep(
            [
                (_sweep_wav(lambda s: np.tanh(0.4 * s) / 4), "-20 dB"),
                (_sweep_wav(lambda s: np.tanh(2.0 * s) / 4), "-6 dB"),
                (_sweep_wav(lambda s: np.tanh(6.0 * s) / 4), "0 dB"),
            ]
        ),
        "clean": diagnose_sweep([(_sweep_wav(lambda s: s), "-12 dB")]),
        "full_scale": diagnose_sweep([(_sweep_wav(lambda s: np.clip(2.5 * s, -1, 1)), "hot")]),
        "noisy": diagnose_sweep(
            [(_sweep_wav(lambda s: s + 0.05 * rng.standard_normal(len(s))), "noisy")]
        ),
        "wrong": diagnose_sweep(
            [(_sweep_wav(lambda s: 0.3 * rng.standard_normal(len(s))), "wrong")]
        ),
    }


def _sweep_packet(name: str) -> ExplanationPacket:
    return sweep_packet(_sweeps()[name], KnowledgeIndex(CORPUS))


def _replace(draft: ExplanationDraft, kind: str, **update: object) -> ExplanationDraft:
    sections = tuple(
        section.model_copy(update=update) if section.kind == kind else section
        for section in draft.sections
    )
    return draft.model_copy(update={"sections": sections})


def test_t_cx466_display_values() -> None:
    assert display(6.7041, "%") == "6.70%"
    assert display(1000.0, "Hz") == "1000 Hz"
    assert display(698.2275, "Hz") == "698.2 Hz"
    assert display(-6.0, "dB") == "-6.0 dB"
    assert display(0.23826) == "0.2383"
    assert display(5.5e-05) == "0.000055"
    assert display(True) is None and display("not_applicable") is None


def test_t_cx466_contextual_packet_is_compact_and_deterministic() -> None:
    result, mode = _runs()["both"]
    first = contextual_packet(result, mode=mode)
    assert first == contextual_packet(result, mode=mode)
    assert first.digest() == contextual_packet(result, mode=mode).digest()
    assert first.packet_version == "explain-packet-1.0"
    assert set(first.claim_ids) == {claim.claim_id for claim in result.diagnosis.claims}  # type: ignore[union-attr]
    kinds = {item.kind for item in first.items}
    assert {"run", "claim", "rule_evaluation", "evidence", "knowledge"} <= kinds
    evaluation_ids = {item.ref_id for item in first.items if item.kind == "rule_evaluation"}
    cited = {ref for claim in result.diagnosis.claims for ref in claim.rule_refs}  # type: ignore[union-attr]
    assert evaluation_ids == cited
    for item in first.items:
        assert all(len(value) < 40 for value in item.values)
    failing = next(
        item for item in first.items if item.label == "rule_even_harmonic_growth_acceptable"
    )
    assert failing.judgment == "fail" and failing.threshold == "5.00%"
    assert failing.supports == ("harmonic_distortion",)


def test_t_cx466_sweep_packet_has_levels_bands_and_knowledge() -> None:
    packet = _sweep_packet("levels")
    levels = [item for item in packet.items if item.kind == "level"]
    assert [item.label for item in levels] == ["-20 dB", "-6 dB", "0 dB"]
    harmonic = next(item for item in packet.items if item.label == "harmonic_distortion")
    assert harmonic.level in {"-6 dB", "0 dB"} and any(v.endswith("Hz") for v in harmonic.values)
    assert any(item.kind == "knowledge" and "harmonic_distortion" in item.supports for item in packet.items)
    assert packet == _sweep_packet("levels")


def test_t_cx467_next_step_menu_follows_the_verdict() -> None:
    def steps(packet: ExplanationPacket) -> set[str]:
        return {option.step_id for option in packet.next_steps}

    assert "lower_playback_level" in steps(_packet("clipping"))
    assert "lower_playback_level" not in steps(_packet("no_fault"))
    assert {"add_reference_recording", "state_nominal_tone", "run_sweep_test"} <= steps(
        _packet("single")
    )
    assert {"run_sweep_test", "check_reference_match"} <= steps(_packet("inconclusive"))
    assert steps(_packet("no_fault")) == set()
    assert {"lower_playback_level", "check_recorder_gain", "add_sweep_levels"} <= steps(
        _sweep_packet("full_scale")
    )
    assert "add_sweep_levels" not in steps(_sweep_packet("levels"))
    assert "rerecord_quieter" in steps(_sweep_packet("noisy"))
    assert "check_stimulus_file" in steps(_sweep_packet("wrong"))
    assert steps(_sweep_packet("clean")) == set()
    for packet in (_packet("clipping"), _sweep_packet("noisy")):
        ids = {item.ref_id for item in packet.items}
        for option in packet.next_steps:
            assert set(option.trigger_refs) <= ids


def _bad(draft: ExplanationDraft, packet: ExplanationPacket, check: str) -> None:
    with pytest.raises(ExplanationRejected) as caught:
        validate_explanation(draft, packet)
    assert caught.value.check == check, caught.value


def test_t_cx468_validator_rejects_each_violation() -> None:
    packet = _packet("both")
    good = template_explanation(packet, "zh")
    validate_explanation(good, packet)
    claims = packet.claim_ids
    growth = next(i for i in packet.items if i.label == "rule_even_harmonic_growth_acceptable")
    _bad(good.model_copy(update={"sections": good.sections[:3]}), packet, "structure")
    _bad(
        good.model_copy(update={"sections": (good.sections[1], good.sections[0], *good.sections[2:])}),
        packet,
        "structure",
    )
    sentence = ExplanationSentence(text="结论：检测到削波和谐波失真。", refs=("claim_unknown",))
    _bad(_replace(good, "conclusion", sentences=(sentence,)), packet, "citation")
    only_first = ExplanationSentence(text="结论：检测到削波。", refs=(claims[0],))
    _bad(_replace(good, "conclusion", sentences=(only_first,)), packet, "conclusion")
    wrong_number = ExplanationSentence(
        text=f"偶次谐波增长 12.5%，超过演示阈值 {growth.threshold}。", refs=(growth.ref_id,)
    )
    _bad(_replace(good, "evidence", sentences=(wrong_number,)), packet, "number")
    rounded = ExplanationSentence(
        text=f"偶次谐波增长约 {float(growth.observed.rstrip('%')):.1f}%，超过演示阈值 5%。",  # type: ignore[union-attr]
        refs=(growth.ref_id,),
    )
    validate_explanation(_replace(good, "evidence", sentences=(rounded,)), packet)
    no_demo = ExplanationSentence(text="偶次谐波增长超过阈值。", refs=(growth.ref_id,))
    _bad(_replace(good, "evidence", sentences=(no_demo,)), packet, "wording")
    standard = ExplanationSentence(text="结果不合格。", refs=claims)
    _bad(_replace(good, "conclusion", sentences=(standard,)), packet, "wording")
    with_id = ExplanationSentence(text=f"见 {claims[0]}。", refs=claims)
    _bad(_replace(good, "conclusion", sentences=(with_id,)), packet, "ids_in_text")
    long_text = ExplanationSentence(text="削波" * 120, refs=claims)
    _bad(_replace(good, "conclusion", sentences=(long_text,)), packet, "length")
    menu_step = ExplanationStep(step_id="use_one_clock", text="用同一时钟。", refs=claims)
    _bad(_replace(good, "next_steps", steps=(menu_step,)), packet, "next_step")
    untriggered = ExplanationStep(
        step_id="lower_playback_level", text="降低播放电平。", refs=(growth.ref_id,)
    )
    _bad(_replace(good, "next_steps", steps=(untriggered,)), packet, "next_step")


def test_t_cx468_fault_wording_must_match_the_verdict() -> None:
    no_fault = _packet("no_fault")
    good = template_explanation(no_fault, "zh")
    claim = no_fault.claim_ids
    for text in ("结论：检测到削波。", "Conclusion: harmonic distortion is present."):
        sentence = ExplanationSentence(text=text, refs=claim)
        _bad(_replace(good, "conclusion", sentences=(sentence,)), no_fault, "fault_mismatch")
    negated = ExplanationSentence(text="结论：未发现受支持的故障，没有削波。", refs=claim)
    validate_explanation(_replace(good, "conclusion", sentences=(negated,)), no_fault)

    inconclusive = _packet("inconclusive")
    good = template_explanation(inconclusive, "zh")
    claim = inconclusive.claim_ids
    for text in ("结论：没有问题。", "Conclusion: no fault was found."):
        sentence = ExplanationSentence(text=text, refs=claim)
        _bad(_replace(good, "conclusion", sentences=(sentence,)), inconclusive, "fault_mismatch")
    evaluation = next(i for i in inconclusive.items if i.kind == "rule_evaluation")
    fine = ExplanationSentence(text="分析前提不满足，一切正常。", refs=(evaluation.ref_id,))
    _bad(_replace(good, "evidence", sentences=(fine,)), inconclusive, "fault_mismatch")


def test_t_cx468_units_and_rounding() -> None:
    packet = _sweep_packet("levels")
    good = template_explanation(packet, "zh")
    claim = next(i for i in packet.items if i.kind == "claim" and i.label == "harmonic_distortion")
    band = next(v for v in claim.values if v.endswith("Hz"))
    hz = float(band.split()[0])
    as_khz = ExplanationSentence(
        text=f"{claim.level}：在 {hz / 1000:g} kHz 频段检测到谐波失真。",
        refs=tuple(i.ref_id for i in packet.items if i.kind == "claim"),
    )
    validate_explanation(_replace(good, "conclusion", sentences=(as_khz,)), packet)
    wrong_unit = as_khz.model_copy(update={"text": f"{claim.level}：在 {hz:g} dB 检测到谐波失真。"})
    _bad(_replace(good, "conclusion", sentences=(wrong_unit,)), packet, "number")


@pytest.mark.parametrize("language", ["zh", "en"])
def test_t_cx469_template_passes_on_every_recorded_case(language: str) -> None:
    count = 0
    for case in engine_cases(ROOT):
        reference = case.load_reference() if case.load_reference else None
        result = asyncio.run(
            run_engine(
                case.load_test(),
                reference,
                mode=case.mode,
                nominal_fundamental_hz=case.nominal_fundamental_hz,
            )
        )
        packet = contextual_packet(result, mode=case.mode)
        draft = template_explanation(packet, language)  # type: ignore[arg-type]
        validate_explanation(draft, packet)
        assert tuple(section.kind for section in draft.sections) == SECTION_ORDER
        count += 1
    assert count == 152


@pytest.mark.parametrize("language", ["zh", "en"])
def test_t_cx469_template_passes_on_sweep_cases(language: str) -> None:
    for name in _sweeps():
        packet = _sweep_packet(name)
        validate_explanation(template_explanation(packet, language), packet)  # type: ignore[arg-type]


def test_t_cx470_template_is_deterministic_and_grounded() -> None:
    packet = _packet("both")
    first = template_explanation(packet, "zh")
    assert first == template_explanation(packet, "zh")
    meaning = next(section for section in first.sections if section.kind == "meaning")
    knowledge = {item.ref_id for item in packet.items if item.kind == "knowledge"}
    assert all(set(sentence.refs) & knowledge for sentence in meaning.sentences)
    steps = next(section for section in first.sections if section.kind == "next_steps")
    assert [step.step_id for step in steps.steps] == [o.step_id for o in packet.next_steps][:4]
    conclusion = next(section for section in first.sections if section.kind == "conclusion")
    assert "削波" in conclusion.sentences[0].text or "削波" in conclusion.sentences[1].text
    assert isinstance(first.sections[0], ExplanationSection)
