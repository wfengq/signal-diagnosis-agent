"""T-CX408: v9.14 sizes its call plan to the runtime's rule-evaluation budget."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.prompts_v03 import (
    _S1_PROMPT_V9_11,
    _S1_PROMPT_V9_12,
    _S1_PROMPT_V9_13,
    _S1_PROMPT_V9_14,
    _V9_14_MONO_WINDOWS,
    _V9_14_STEREO_HALVES,
)
from signal_diag.evaluation.agent_increment.models import IncrementCase
from signal_diag.evaluation.agent_increment.offline import fault_localized
from signal_diag.evaluation.agent_increment.segment_support import (
    load_segment_profile,
    segment_supports,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.wav import load_wav_bytes
from signal_diag.tools.contracts import ClippingInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

_ROOT = Path(__file__).resolve().parents[2]
_STUDY = _ROOT / "docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1"
_V9_12_SHA256 = "a90ffd1846a478f9117e61c374645eac1739ee57c5f033515fe5977269e83d1c"
_V9_13_SHA256 = "80084c09ac5f620e5f28b1688d069e2d70cbbfecf9d0eacee261f6b5b5cfe65a"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_t_cx408_v914_prefixes_v911_and_pins_earlier_study_prompts() -> None:
    assert _S1_PROMPT_V9_14.version == "v0.3-s1-planner-9.14"
    assert _S1_PROMPT_V9_14.system_prompt.startswith(_S1_PROMPT_V9_11.system_prompt)
    assert _sha(_S1_PROMPT_V9_12.system_prompt) == _V9_12_SHA256
    assert _sha(_S1_PROMPT_V9_13.system_prompt) == _V9_13_SHA256
    assert PROMPT_VERSION == "v0.3-s1-planner-9.11"
    assert RealLLMPlanner._prompt_spec is _S1_PROMPT_V9_11


def test_t_cx408_every_plan_fits_the_runtime_budget() -> None:
    """D1 round 3: v9.13 planned 5-7 rule-backed calls against a cap of 4."""
    limits = AgentLimits()
    budget = min(limits.max_rule_evaluations, limits.max_tool_calls)
    assert _V9_14_MONO_WINDOWS <= budget
    assert 2 + _V9_14_STEREO_HALVES <= budget
    extra = _S1_PROMPT_V9_14.system_prompt.removeprefix(_S1_PROMPT_V9_11.system_prompt)
    assert f"at most {limits.max_rule_evaluations} " in extra
    assert f"{_V9_14_MONO_WINDOWS} equal consecutive windows" in extra
    for needle in (
        "stimulus_context.mode is single_signal",
        "stimulus_context.mode is paired_reference or nominal_single_tone",
        "signal_meta.channels",
        "signal_meta.duration_s",
        "analyze_contextual_distortion",
    ):
        assert needle in extra
    assert "fundamental frequency" in extra and "threshold" in extra


def _plan_evidence(path: Path, name: str) -> list[Evidence]:
    """Execute the v9.14 single-file plan deterministically (no model)."""
    record = load_wav_bytes(path.read_bytes(), filename=name).record
    repository = InMemorySignalRepository()
    repository.put(record)
    tools = SignalToolService(repository)
    signal_id = record.meta.signal_id
    duration = record.meta.duration_s

    def clip(channel: ChannelMode, span: TimeRange | None) -> list[Evidence]:
        result = tools.detect_clipping(signal_id, ClippingInput(time_range=span, channel=channel))
        return list(result.evidence)

    def flags(evidence: list[Evidence]) -> bool:
        batch = RuleEngine().evaluate_profile(load_segment_profile(), tuple(evidence))
        by_id = {item.evidence_id: item for item in evidence}
        return any(s.fault == "clipping" for s in segment_supports(batch, by_id))

    if record.meta.channels == 1:
        step = duration / _V9_14_MONO_WINDOWS
        evidence: list[Evidence] = []
        for index in range(_V9_14_MONO_WINDOWS):
            span = TimeRange(start_s=index * step, end_s=(index + 1) * step)
            evidence += clip("mixdown", span)
        return evidence
    left = clip("left", None)
    right = clip("right", None)
    target: ChannelMode = "left" if flags(left) else "right" if flags(right) else "mixdown"
    evidence = left + right
    step = duration / _V9_14_STEREO_HALVES
    for index in range(_V9_14_STEREO_HALVES):
        evidence += clip(target, TimeRange(start_s=index * step, end_s=(index + 1) * step))
    return evidence


def test_t_cx408_plan_localizes_every_dev_clipping_case_and_flags_no_clean_case() -> None:
    manifest = json.loads((_STUDY / "manifest.json").read_text(encoding="utf-8"))
    checked = 0
    for raw in manifest["cases"]:
        case = IncrementCase.model_validate(raw)
        if case.family != "T2" or case.split != "dev":
            continue
        evidence = _plan_evidence(_ROOT / case.files[0], case.test_file)
        batch = RuleEngine().evaluate_profile(load_segment_profile(), tuple(evidence))
        supports = segment_supports(batch, {item.evidence_id: item for item in evidence})
        clipping = tuple(s for s in supports if s.fault == "clipping" and s.time_range)
        if case.truth.conclusion == "clipping":
            assert fault_localized(clipping, case) is True, case.case_id
            checked += 1
        elif case.no_fault:
            assert clipping == (), case.case_id
    assert checked == 5
