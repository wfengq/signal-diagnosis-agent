"""T-CX390: deterministic B1 intake baseline shares validation and the simulated user."""

from __future__ import annotations

from signal_diag.agent.intake import (
    ContextDraft,
    IntakeRequest,
    ScriptedIntakePlanner,
    validate_context_draft,
)
from signal_diag.evaluation.agent_increment.intake_baseline import (
    B1_RULE_TABLE,
    B1_RULE_TABLE_ID,
    parse_b1,
)
from signal_diag.evaluation.agent_increment.simulated_user import (
    confirm_proposed_fields,
)


def _request(text: str, files: tuple[str, ...] = ("new.wav", "old.wav")) -> IntakeRequest:
    return IntakeRequest(
        text=text,
        filenames=files,
        test_file=files[0],
    )


def test_t_cx390_rule_table_is_frozen() -> None:
    assert B1_RULE_TABLE_ID == "b1-intake-1.0"
    assert B1_RULE_TABLE["reference_markers"] == (
        "参考",
        "旧",
        "之前",
        "原来",
        "原先",
        "reference",
        "old",
        "previous",
        "prior",
    )
    assert B1_RULE_TABLE["frequency_pattern"] == r"(\d+(?:\.\d+)?)\s*(k?Hz)"
    assert B1_RULE_TABLE["stimulus_markers"] == ("正弦", "测试音", "单音", "sine", "test tone")
    assert B1_RULE_TABLE["window_s"] is None


def test_t_cx390_b1_is_deterministic_and_validated() -> None:
    request = _request("旧功放录音是参考，新功放放 1 kHz 正弦发毛")
    first = parse_b1(request)
    second = parse_b1(request)
    assert first == second
    validate_context_draft(first, request)
    assert first.mode == "paired_reference"
    assert first.reference_file == "old.wav"
    assert first.nominal_fundamental_hz == 1000.0
    assert first.stimulus_kind == "single_tone"


def test_t_cx390_b1_leaves_absent_frequency_empty() -> None:
    request = _request("听着发毛", ("only.wav",))
    draft = parse_b1(request)
    validate_context_draft(draft, request)
    assert draft.nominal_fundamental_hz is None
    assert "nominal_fundamental_hz" in draft.missing_fields


def test_t_cx390_agent_and_b1_share_simulated_user_and_validator() -> None:
    request = _request("参考 old.wav，标称 1000 Hz 测试音")
    truth = ContextDraft(
        mode="paired_reference",
        nominal_fundamental_hz=440.0,
        reference_file="old.wav",
        stimulus_kind="single_tone",
        missing_fields=(),
        questions=(),
    )
    b1 = parse_b1(request)
    agent = ContextDraft(
        mode="paired_reference",
        nominal_fundamental_hz=1000.0,
        reference_file="old.wav",
        stimulus_kind="single_tone",
        missing_fields=(),
        questions=(),
    )
    validate_context_draft(b1, request)
    validate_context_draft(agent, request)
    b1_confirmed = confirm_proposed_fields(b1, truth)
    agent_confirmed = confirm_proposed_fields(agent, truth)
    assert b1_confirmed.confirmed.nominal_fundamental_hz == 440.0
    assert agent_confirmed.confirmed.nominal_fundamental_hz == 440.0
    assert b1_confirmed.correction_count == 1
    assert agent_confirmed.correction_count == 1
    assert ScriptedIntakePlanner(agent).identity.startswith("scripted")
