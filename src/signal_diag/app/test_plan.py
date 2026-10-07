"""Test guide (D057, §31): plan catalog, draft validation, questionnaire, confirmation.

The guide decides only which test to run. Plans and connection steps come from
a fixed catalog; a model may only choose a plan, fill parameters and ask for
missing fields, and every draft is validated fail-closed. The deterministic
questionnaire is always available and replaces any rejected draft (a
questionnaire, never a stub planner). Draft values are never confirmed by
themselves (D047): only values the user sends back are.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import OrderedDict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.agent.intake import numbers_admissible_from_text

TEST_PLAN_VERSION = "test-plan-1.0"
Language = Literal["zh", "en"]
PlanId = Literal["sweep_levels", "existing_recording", "paired_reference", "nominal_tone"]
Connection = Literal["line_loopback", "acoustic_mic", "digital_capture"]
PLAN_IDS: tuple[str, ...] = ("sweep_levels", "existing_recording", "paired_reference", "nominal_tone")
CONNECTIONS: tuple[str, ...] = ("line_loopback", "acoustic_mic", "digital_capture")
SWEEP_RATES = (44_100, 48_000)
DEFAULT_RATE = 48_000
DEFAULT_LEVEL_LABELS = {
    "zh": ("低于平时", "平时音量", "出问题的音量"),
    "en": ("below normal", "normal", "problem level"),
}
FIELDS = (
    "sample_rate_hz",
    "level_labels",
    "connection",
    "test_file",
    "reference_file",
    "nominal_fundamental_hz",
)
MAX_QUESTIONS = 4
MAX_LABEL_CHARS = 64
_NO_RERECORD = (
    "只有这一段",
    "只有一段录音",
    "不能重新录",
    "没法重新录",
    "无法重新录",
    "不能再录",
    "设备不在",
    "can't re-record",
    "cannot re-record",
    "can't record again",
    "cannot record again",
    "only have this recording",
    "only have one recording",
)
_BANNED = ("标准", "合格", "达标", "认证", "IEC", "AES", "standard", "SLA", "compliant", "certified", "阈值", "threshold", "%")


class PlanRejected(ValueError):
    def __init__(self, check: str, detail: str) -> None:
        super().__init__(f"{check}: {detail}")
        self.check = check


class GuideRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1, max_length=2_000)
    filenames: tuple[str, ...] = Field(default=(), max_length=3)
    sample_rates_hz: tuple[float, ...] = ()


class PlanParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_rate_hz: int | None = None
    level_labels: tuple[str, ...] = ()
    connection: str | None = None
    test_file: str | None = None
    reference_file: str | None = None
    nominal_fundamental_hz: float | None = None
    defaults: tuple[str, ...] = ()


class PlanDraft(BaseModel):
    """What a model (or the questionnaire) proposes; nothing here is confirmed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str
    parameters: PlanParameters = PlanParameters()
    missing_fields: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    rationale_quotes: tuple[str, ...] = ()


# --- validation -------------------------------------------------------------


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def _admissible(value: float, request: GuideRequest) -> bool:
    numbers = (*numbers_admissible_from_text(request.text), *request.sample_rates_hz)
    return any(_same(value, number) for number in numbers)


def validate_plan_draft(draft: PlanDraft, request: GuideRequest) -> None:
    """Raise ``PlanRejected`` unless the draft passes every §31 check."""
    p = draft.parameters
    if draft.plan_id not in PLAN_IDS:
        raise PlanRejected("structure", f"unknown plan {draft.plan_id!r}")
    if p.connection is not None and p.connection not in CONNECTIONS:
        raise PlanRejected("structure", f"unknown connection {p.connection!r}")
    if not set(draft.missing_fields) <= set(FIELDS) or not set(p.defaults) <= set(FIELDS):
        raise PlanRejected("structure", "unknown field name")
    if len(draft.questions) > MAX_QUESTIONS:
        raise PlanRejected("structure", "too many questions")
    sweep = draft.plan_id == "sweep_levels"
    if p.sample_rate_hz is not None and p.sample_rate_hz not in SWEEP_RATES:
        raise PlanRejected("parameters", "sample rate must be 44100 or 48000")
    if (p.sample_rate_hz is not None or p.level_labels or p.connection) and not sweep:
        raise PlanRejected("parameters", "sweep parameters on a non-sweep plan")
    if len(p.level_labels) > 3 or len(set(p.level_labels)) != len(p.level_labels):
        raise PlanRejected("parameters", "1-3 unique level labels")
    if any(not label.strip() or len(label) > MAX_LABEL_CHARS for label in p.level_labels):
        raise PlanRejected("parameters", "level label length")
    files = set(request.filenames)
    for name in (p.test_file, p.reference_file):
        if name is not None and name not in files:
            raise PlanRejected("parameters", f"{name!r} is not an uploaded file")
    if p.reference_file is not None and p.reference_file == p.test_file:
        raise PlanRejected("parameters", "reference is the test file")
    # Numbers: from the user's text or file metadata, or a marked catalog default.
    if p.sample_rate_hz is not None:
        default = "sample_rate_hz" in p.defaults and p.sample_rate_hz == DEFAULT_RATE
        if not default and not _admissible(p.sample_rate_hz, request):
            raise PlanRejected("number", "sample rate is neither stated nor a marked default")
    if p.nominal_fundamental_hz is not None and not _admissible(p.nominal_fundamental_hz, request):
        raise PlanRejected("number", "nominal frequency is not written in the text")
    labels_default = "level_labels" in p.defaults and p.level_labels in DEFAULT_LEVEL_LABELS.values()
    if not labels_default:
        for label in p.level_labels:
            for number in numbers_admissible_from_text(label):
                if not _admissible(number, request):
                    raise PlanRejected("number", f"level label {label!r} invents a number")
    if not draft.rationale_quotes:
        raise PlanRejected("quote", "no quote from the user's text")
    for quote in draft.rationale_quotes:
        if not quote.strip() or quote not in request.text:
            raise PlanRejected("quote", "quotes must be exact substrings of the user's text")
    missing = set(draft.missing_fields)
    if draft.plan_id == "paired_reference":
        if len(files) < 2:
            raise PlanRejected("precondition", "paired reference needs two uploaded files")
        if p.reference_file is None and "reference_file" not in missing:
            raise PlanRejected("precondition", "reference file is neither chosen nor asked")
    if draft.plan_id == "nominal_tone" and p.nominal_fundamental_hz is None and (
        "nominal_fundamental_hz" not in missing
    ):
        raise PlanRejected("precondition", "nominal frequency is neither stated nor asked")
    if sweep and any(phrase.lower() in request.text.lower() for phrase in _NO_RERECORD):
        raise PlanRejected("precondition", "the user says the test cannot be recorded again")
    for question in draft.questions:
        lowered = question.lower()
        if any(word.lower() in lowered for word in _BANNED):
            raise PlanRejected("wording", "questions may not mention standards or thresholds")


# --- questionnaire ----------------------------------------------------------


class QuestionOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    answer: str
    label_zh: str
    label_en: str
    next: str | None = None
    plan_id: str | None = None
    connection: str | None = None


class Question(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    text_zh: str
    text_en: str
    options: tuple[QuestionOption, ...]


QUESTIONNAIRE: tuple[Question, ...] = (
    Question(
        question_id="can_replay",
        text_zh="能让设备播放一个测试文件，并把它的输出录下来吗？",
        text_en="Can the device play a test file while you record its output?",
        options=(
            QuestionOption(answer="yes", label_zh="能", label_en="Yes", next="connection"),
            QuestionOption(answer="no", label_zh="不能", label_en="No", next="has_reference"),
        ),
    ),
    Question(
        question_id="connection",
        text_zh="怎么把设备的输出录下来？",
        text_en="How will you record the device's output?",
        options=(
            QuestionOption(answer="line_loopback", label_zh="声卡线路环回", label_en="Line loopback through an audio interface", plan_id="sweep_levels", connection="line_loopback"),
            QuestionOption(answer="acoustic_mic", label_zh="音箱放音、麦克风录音", label_en="Speaker played into a microphone", plan_id="sweep_levels", connection="acoustic_mic"),
            QuestionOption(answer="digital_capture", label_zh="设备自带 USB 或数字录音", label_en="The device's own USB or digital capture", plan_id="sweep_levels", connection="digital_capture"),
        ),
    ),
    Question(
        question_id="has_reference",
        text_zh="有没有同一个信号的“正常”录音可以对比？",
        text_en="Do you have a 'good' recording of the same signal to compare with?",
        options=(
            QuestionOption(answer="yes", label_zh="有", label_en="Yes", plan_id="paired_reference"),
            QuestionOption(answer="no", label_zh="没有", label_en="No", next="known_tone"),
        ),
    ),
    Question(
        question_id="known_tone",
        text_zh="录音里播放的是已知频率的单音吗？",
        text_en="Is the recording a single tone of a known frequency?",
        options=(
            QuestionOption(answer="yes", label_zh="是", label_en="Yes", plan_id="nominal_tone"),
            QuestionOption(answer="no", label_zh="不是或不确定", label_en="No or not sure", plan_id="existing_recording"),
        ),
    ),
)
_QUESTIONS = {question.question_id: question for question in QUESTIONNAIRE}


def questionnaire_draft(answers: dict[str, str], *, language: Language = "zh") -> PlanDraft:
    """Walk the question tree from ``can_replay``; every step must be answered."""
    current = "can_replay"
    for _ in range(len(QUESTIONNAIRE)):
        question = _QUESTIONS[current]
        answer = answers.get(current)
        option = next((o for o in question.options if o.answer == answer), None)
        if option is None:
            raise PlanRejected("questionnaire", f"answer {current!r} with one of the options")
        if option.plan_id is not None:
            plan = option.plan_id
            if plan == "sweep_levels":
                params = PlanParameters(
                    sample_rate_hz=DEFAULT_RATE,
                    level_labels=DEFAULT_LEVEL_LABELS[language],
                    connection=option.connection,
                    defaults=("sample_rate_hz", "level_labels"),
                )
                return PlanDraft(plan_id=plan, parameters=params)
            missing = {
                "paired_reference": ("test_file", "reference_file"),
                "nominal_tone": ("test_file", "nominal_fundamental_hz"),
                "existing_recording": ("test_file",),
            }[plan]
            return PlanDraft(plan_id=plan, missing_fields=missing)
        assert option.next is not None
        current = option.next
    raise PlanRejected("questionnaire", "question tree did not end")


# --- confirmation and steps -------------------------------------------------


class ConfirmRequest(BaseModel):
    """Values the user confirmed; draft values only count when sent back here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str
    source: Literal["model", "questionnaire"]
    language: Language = "zh"
    sample_rate_hz: int | None = None
    level_labels: tuple[str, ...] = ()
    connection: str | None = None
    test_file: str | None = None
    reference_file: str | None = None
    nominal_fundamental_hz: float | None = None


class PlanRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_key: str = Field(pattern=r"^plan_")
    version: str = TEST_PLAN_VERSION
    plan_id: str
    source: Literal["model", "questionnaire"]
    language: Language
    parameters: dict[str, object]
    steps: tuple[str, ...]
    next_page: str


_CONNECTION_STEPS = {
    "zh": {
        "line_loopback": (
            "把声卡输出接到设备输入，把设备输出接回声卡输入；关闭声卡和电脑上的所有效果和自动增益。",
            "先用低音量播放一次，调整录音增益，让录音峰值留有余量、不碰满刻度。",
        ),
        "acoustic_mic": (
            "把麦克风放在音箱正前方约 30–50 厘米处，在尽量安静的房间里录音。",
            "关闭麦克风和电脑上的降噪、自动增益；录音电平不要碰满刻度。",
        ),
        "digital_capture": (
            "用设备自带的 USB 或数字输出录音，关闭软件里的所有效果和自动增益。",
            "确认录音软件的采样率与测试文件一致。",
        ),
    },
    "en": {
        "line_loopback": (
            "Connect the interface output to the device input and the device output back to the interface input; turn off every effect and automatic gain.",
            "Play once at a low level and set the recording gain so peaks stay well below full scale.",
        ),
        "acoustic_mic": (
            "Place the microphone 30–50 cm in front of the speaker and record in as quiet a room as possible.",
            "Turn off noise reduction and automatic gain; keep the recording level below full scale.",
        ),
        "digital_capture": (
            "Record through the device's own USB or digital output with every effect and automatic gain off.",
            "Make sure the recording software uses the test file's sample rate.",
        ),
    },
}


def _steps(confirmed: ConfirmRequest) -> tuple[str, ...]:
    zh = confirmed.language == "zh"
    plan = confirmed.plan_id
    if plan == "sweep_levels":
        rate = confirmed.sample_rate_hz
        labels = ("、" if zh else ", ").join(confirmed.level_labels)
        assert confirmed.connection is not None
        connection = _CONNECTION_STEPS[confirmed.language][confirmed.connection]
        if zh:
            return (
                f"在“扫频测试”页面下载 {rate} Hz 的测试文件（sweep-stimulus-1.0）。",
                *connection,
                f"按从低到高的顺序录 {len(confirmed.level_labels)} 个音量：{labels}。每次都从播放前开始录，到播放结束后停止。",
                "上传录音并分析；结果会给出各频段的失真，以及第一个超过演示阈值的音量。",
            )
        return (
            f"Download the {rate} Hz test file (sweep-stimulus-1.0) on the sweep test page.",
            *connection,
            f"Record {len(confirmed.level_labels)} levels from low to high: {labels}. Start before playback and stop after it ends.",
            "Upload and analyse; the result shows distortion per band and the first level above the demonstration threshold.",
        )
    if plan == "paired_reference":
        return (
            ("上传测试录音和参考录音，模式选“参考对比”。" if zh else "Upload the test and reference recordings and choose paired reference."),
            ("两段录音应是同一个信号、同样的电平和采样率。" if zh else "Both should carry the same signal at the same level and sample rate."),
        )
    if plan == "nominal_tone":
        hz = confirmed.nominal_fundamental_hz
        return (
            (f"上传录音，模式选“标称单音”，频率填 {hz:g} Hz。" if zh else f"Upload the recording, choose nominal tone and enter {hz:g} Hz."),
        )
    return (
        ("上传录音；可以用自由文字描述补充背景，按提示确认后诊断。" if zh else "Upload the recording; describe the context in free text and confirm before diagnosis."),
        ("没有参考录音或已知频率时，谐波失真不会被认定（D037）；需要更可靠的结论时，改做扫频测试。" if zh else "Without a reference or known frequency, harmonic distortion is not attributed (D037); run the sweep test for a firmer answer."),
    )


def confirm_plan(confirmed: ConfirmRequest) -> PlanRecord:
    """Validate the user's confirmed values and build steps and prefill."""
    plan = confirmed.plan_id
    if plan not in PLAN_IDS:
        raise PlanRejected("structure", f"unknown plan {plan!r}")
    if plan == "sweep_levels":
        if confirmed.sample_rate_hz not in SWEEP_RATES:
            raise PlanRejected("parameters", "confirm a sample rate of 44100 or 48000")
        labels = confirmed.level_labels
        if not 1 <= len(labels) <= 3 or len(set(labels)) != len(labels):
            raise PlanRejected("parameters", "confirm 1-3 unique level labels")
        if any(not label.strip() or len(label) > MAX_LABEL_CHARS for label in labels):
            raise PlanRejected("parameters", "level label length")
        if confirmed.connection not in CONNECTIONS:
            raise PlanRejected("parameters", "confirm a connection")
    elif confirmed.sample_rate_hz is not None or confirmed.level_labels or confirmed.connection:
        raise PlanRejected("parameters", "sweep parameters on a non-sweep plan")
    if plan == "paired_reference" and not (confirmed.test_file and confirmed.reference_file):
        raise PlanRejected("parameters", "confirm the test and reference files")
    if confirmed.reference_file is not None and confirmed.reference_file == confirmed.test_file:
        raise PlanRejected("parameters", "reference is the test file")
    hz = confirmed.nominal_fundamental_hz
    if plan == "nominal_tone" and (hz is None or not math.isfinite(hz) or hz <= 0):
        raise PlanRejected("parameters", "confirm a positive nominal frequency")
    if plan != "nominal_tone" and hz is not None:
        raise PlanRejected("parameters", "nominal frequency on another plan")
    parameters = {
        key: value
        for key, value in confirmed.model_dump(mode="json").items()
        if key not in ("plan_id", "source", "language") and value not in (None, [], ())
    }
    payload = json.dumps([TEST_PLAN_VERSION, plan, parameters], sort_keys=True, ensure_ascii=False)
    plan_key = "plan_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return PlanRecord(
        plan_key=plan_key,
        plan_id=plan,
        source=confirmed.source,
        language=confirmed.language,
        parameters=parameters,
        steps=_steps(confirmed),
        next_page=f"/sweep?plan={plan_key}" if plan == "sweep_levels" else f"/?plan={plan_key}",
    )


class PlanStore:
    """Confirmed plans in memory, and the runs started from them."""

    def __init__(self, limit: int = 64) -> None:
        self._limit = limit
        self._plans: OrderedDict[str, PlanRecord] = OrderedDict()
        self._runs: dict[str, str] = {}

    def put(self, record: PlanRecord) -> PlanRecord:
        self._plans[record.plan_key] = record
        self._plans.move_to_end(record.plan_key)
        while len(self._plans) > self._limit:
            dropped, _ = self._plans.popitem(last=False)
            self._runs = {run: key for run, key in self._runs.items() if key != dropped}
        return record

    def get(self, plan_key: str) -> PlanRecord | None:
        return self._plans.get(plan_key)

    def link(self, plan_key: str, run_id: str) -> None:
        if plan_key not in self._plans:
            raise KeyError(plan_key)
        if not re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", run_id):
            raise ValueError("invalid run id")
        self._runs[run_id] = plan_key

    def plan_for_run(self, run_id: str) -> PlanRecord | None:
        key = self._runs.get(run_id)
        return self._plans.get(key) if key else None


__all__ = [
    "CONNECTIONS",
    "DEFAULT_LEVEL_LABELS",
    "DEFAULT_RATE",
    "PLAN_IDS",
    "QUESTIONNAIRE",
    "TEST_PLAN_VERSION",
    "ConfirmRequest",
    "GuideRequest",
    "PlanDraft",
    "PlanParameters",
    "PlanRecord",
    "PlanRejected",
    "PlanStore",
    "confirm_plan",
    "questionnaire_draft",
    "validate_plan_draft",
]
