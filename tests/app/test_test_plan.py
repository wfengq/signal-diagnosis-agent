"""T-CX483–T-CX487: test guide catalog, validation, questionnaire and confirmation (D057)."""

from __future__ import annotations

import pytest

from signal_diag.app.test_plan import (
    CONNECTIONS,
    DEFAULT_LEVEL_LABELS,
    PLAN_IDS,
    QUESTIONNAIRE,
    ConfirmRequest,
    GuideRequest,
    PlanDraft,
    PlanParameters,
    PlanRejected,
    PlanStore,
    confirm_plan,
    questionnaire_draft,
    validate_plan_draft,
)

SPEAKER = GuideRequest(text="我的音箱一开大声就破音，我可以用声卡把它录下来，采样率 44.1 kHz。")
TONE = GuideRequest(text="我录了一段 1 kHz 的正弦波，只有这一段录音，听起来有点毛。", filenames=("tone.wav",))
PAIR = GuideRequest(text="新版本听起来比旧版本发糊", filenames=("new.wav", "old.wav"))


def _sweep(**update: object) -> PlanDraft:
    params = PlanParameters(
        sample_rate_hz=44_100,
        level_labels=("低于平时", "平时音量", "出问题的音量"),
        connection="line_loopback",
        defaults=("level_labels",),
    )
    draft = PlanDraft(plan_id="sweep_levels", parameters=params, rationale_quotes=("一开大声就破音",))
    return draft.model_copy(update=update)


def _bad(draft: PlanDraft, request: GuideRequest, check: str) -> None:
    with pytest.raises(PlanRejected) as caught:
        validate_plan_draft(draft, request)
    assert caught.value.check == check, caught.value


def test_t_cx483_catalog_and_steps() -> None:
    assert PLAN_IDS == ("sweep_levels", "existing_recording", "paired_reference", "nominal_tone")
    assert CONNECTIONS == ("line_loopback", "acoustic_mic", "digital_capture")
    for connection in CONNECTIONS:
        for language in ("zh", "en"):
            record = confirm_plan(
                ConfirmRequest(
                    plan_id="sweep_levels",
                    source="questionnaire",
                    language=language,  # type: ignore[arg-type]
                    sample_rate_hz=48_000,
                    level_labels=DEFAULT_LEVEL_LABELS[language],
                    connection=connection,
                )
            )
            text = " ".join(record.steps)
            assert "48000 Hz" in text and record.next_page.startswith("/sweep?plan=plan_")
            assert "单调" not in text and "monoton" not in text.lower()
            assert ("第一个超过演示阈值" in text) if language == "zh" else ("first level above" in text)
    nominal = confirm_plan(
        ConfirmRequest(plan_id="nominal_tone", source="model", nominal_fundamental_hz=1000.0)
    )
    assert "1000 Hz" in nominal.steps[0] and nominal.next_page.startswith("/?plan=")


def test_t_cx484_valid_drafts_pass() -> None:
    validate_plan_draft(_sweep(), SPEAKER)
    default_rate = _sweep(
        parameters=PlanParameters(
            sample_rate_hz=48_000,
            level_labels=DEFAULT_LEVEL_LABELS["zh"],
            connection="acoustic_mic",
            defaults=("sample_rate_hz", "level_labels"),
        )
    )
    validate_plan_draft(default_rate, GuideRequest(text="音箱一开大声就破音"))
    tone = PlanDraft(
        plan_id="nominal_tone",
        parameters=PlanParameters(test_file="tone.wav", nominal_fundamental_hz=1000.0),
        rationale_quotes=("1 kHz 的正弦波",),
    )
    validate_plan_draft(tone, TONE)
    pair = PlanDraft(
        plan_id="paired_reference",
        parameters=PlanParameters(test_file="new.wav", reference_file="old.wav"),
        rationale_quotes=("新版本听起来比旧版本发糊",),
    )
    validate_plan_draft(pair, PAIR)
    asked = PlanDraft(
        plan_id="nominal_tone",
        missing_fields=("nominal_fundamental_hz",),
        questions=("单音的频率是多少？",),
        rationale_quotes=("正弦波",),
    )
    validate_plan_draft(asked, TONE)


def test_t_cx485_validator_rejects_each_violation() -> None:
    _bad(_sweep(plan_id="impedance_test"), SPEAKER, "structure")
    bad_connection = _sweep(parameters=_sweep().parameters.model_copy(update={"connection": "bluetooth"}))
    _bad(bad_connection, SPEAKER, "structure")
    _bad(_sweep(missing_fields=("volume",)), SPEAKER, "structure")
    _bad(_sweep(questions=("a", "b", "c", "d", "e")), SPEAKER, "structure")
    rate_96k = _sweep(parameters=_sweep().parameters.model_copy(update={"sample_rate_hz": 96_000}))
    _bad(rate_96k, SPEAKER, "parameters")
    unstated = _sweep(parameters=_sweep().parameters.model_copy(update={"sample_rate_hz": 48_000}))
    _bad(unstated, SPEAKER, "number")
    invented = _sweep(
        parameters=_sweep().parameters.model_copy(update={"level_labels": ("-20 dB", "-6 dB"), "defaults": ()})
    )
    _bad(invented, SPEAKER, "number")
    duplicate = _sweep(parameters=_sweep().parameters.model_copy(update={"level_labels": ("a", "a")}))
    _bad(duplicate, SPEAKER, "parameters")
    _bad(_sweep(rationale_quotes=("音箱完全坏了",)), SPEAKER, "quote")
    _bad(_sweep(rationale_quotes=()), SPEAKER, "quote")
    defaulted = PlanParameters(
        sample_rate_hz=48_000,
        level_labels=DEFAULT_LEVEL_LABELS["zh"],
        connection="line_loopback",
        defaults=("sample_rate_hz", "level_labels"),
    )
    _bad(_sweep(parameters=defaulted, rationale_quotes=("只有这一段录音",)), TONE, "precondition")
    _bad(_sweep(questions=("THD 超过 5% 了吗？",)), SPEAKER, "wording")
    wrong_hz = PlanDraft(
        plan_id="nominal_tone",
        parameters=PlanParameters(nominal_fundamental_hz=440.0),
        rationale_quotes=("正弦波",),
    )
    _bad(wrong_hz, TONE, "number")
    no_hz = PlanDraft(plan_id="nominal_tone", rationale_quotes=("正弦波",))
    _bad(no_hz, TONE, "precondition")
    one_file = PlanDraft(
        plan_id="paired_reference", missing_fields=("reference_file",), rationale_quotes=("正弦波",)
    )
    _bad(one_file, TONE, "precondition")
    no_files_yet = PlanDraft(plan_id="paired_reference", rationale_quotes=("发糊",))
    validate_plan_draft(no_files_yet, GuideRequest(text="新版本听起来比旧版本发糊"))
    foreign = PlanDraft(
        plan_id="paired_reference",
        parameters=PlanParameters(test_file="new.wav", reference_file="other.wav"),
        rationale_quotes=("发糊",),
    )
    _bad(foreign, PAIR, "parameters")
    same = foreign.model_copy(update={"parameters": PlanParameters(test_file="new.wav", reference_file="new.wav")})
    _bad(same, PAIR, "parameters")
    sweep_on_tone = PlanDraft(
        plan_id="existing_recording",
        parameters=PlanParameters(sample_rate_hz=44_100),
        rationale_quotes=("正弦波",),
    )
    _bad(sweep_on_tone, TONE, "parameters")


def test_t_cx486_questionnaire_reaches_every_plan() -> None:
    assert QUESTIONNAIRE[0].question_id == "can_replay"
    for connection in CONNECTIONS:
        draft = questionnaire_draft({"can_replay": "yes", "connection": connection})
        assert draft.plan_id == "sweep_levels" and draft.parameters.connection == connection
        assert draft.parameters.defaults == ("sample_rate_hz", "level_labels")
    assert questionnaire_draft({"can_replay": "no", "has_reference": "yes"}).plan_id == "paired_reference"
    tone = questionnaire_draft({"can_replay": "no", "has_reference": "no", "known_tone": "yes"})
    assert tone.plan_id == "nominal_tone" and "nominal_fundamental_hz" in tone.missing_fields
    plain = questionnaire_draft({"can_replay": "no", "has_reference": "no", "known_tone": "no"})
    assert plain.plan_id == "existing_recording"
    english = questionnaire_draft({"can_replay": "yes", "connection": "acoustic_mic"}, language="en")
    assert english.parameters.level_labels == DEFAULT_LEVEL_LABELS["en"]
    for answers in ({}, {"can_replay": "maybe"}, {"can_replay": "yes"}):
        with pytest.raises(PlanRejected):
            questionnaire_draft(answers)


def test_t_cx487_only_sent_values_are_confirmed_and_plans_link_to_runs() -> None:
    with pytest.raises(PlanRejected):
        confirm_plan(ConfirmRequest(plan_id="sweep_levels", source="model"))
    with pytest.raises(PlanRejected):
        confirm_plan(ConfirmRequest(plan_id="sweep_levels", source="model", sample_rate_hz=48_000, level_labels=("a",)))
    with pytest.raises(PlanRejected):
        confirm_plan(
            ConfirmRequest(plan_id="paired_reference", source="model", test_file="a.wav", reference_file="a.wav")
        )
    assert confirm_plan(ConfirmRequest(plan_id="paired_reference", source="model")).next_page.startswith("/?plan=")
    with pytest.raises(PlanRejected):
        confirm_plan(ConfirmRequest(plan_id="nominal_tone", source="model", nominal_fundamental_hz=-5.0))
    with pytest.raises(PlanRejected):
        confirm_plan(ConfirmRequest(plan_id="existing_recording", source="model", connection="acoustic_mic"))
    request = ConfirmRequest(
        plan_id="sweep_levels",
        source="model",
        sample_rate_hz=44_100,
        level_labels=("-20 dB", "0 dB"),
        connection="digital_capture",
    )
    first, second = confirm_plan(request), confirm_plan(request)
    assert first == second and first.version == "test-plan-1.0"
    assert first.parameters == {
        "sample_rate_hz": 44_100,
        "level_labels": ["-20 dB", "0 dB"],
        "connection": "digital_capture",
    }
    store = PlanStore(limit=1)
    store.put(first)
    store.link(first.plan_key, "swrun_abc")
    assert store.plan_for_run("swrun_abc") == first
    with pytest.raises(KeyError):
        store.link("plan_missing", "run_x")
    with pytest.raises(ValueError):
        store.link(first.plan_key, "../etc")
    other = confirm_plan(ConfirmRequest(plan_id="existing_recording", source="questionnaire"))
    store.put(other)
    assert store.get(first.plan_key) is None and store.plan_for_run("swrun_abc") is None
