"""Dev and held-out cases for study_s1_agent_increment_1.

Held-out T1 wording is one rendering of each template in its bucket.
HELD_OUT_SEED stays 20261006. Each held-out T1 case still draws one
two-way choice so later T2 draws keep the same random stream.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import numpy as np

from signal_diag.evaluation.agent_increment.audio import write_pcm16_wav
from signal_diag.evaluation.agent_increment.models import (
    CaseTruth,
    FaultSpan,
    IncrementCase,
)
from signal_diag.signal.wav import load_wav_bytes

STUDY_ID = "study_s1_agent_increment_1"
HELD_OUT_SEED = 20261006
TEMPLATE_ID = "heldout-templates-1.0"
SAMPLE_RATE_HZ = 8000

HELD_OUT_TEMPLATES: dict[str, tuple[str, ...]] = {
    "no_fault": (
        "这段 {hz} Hz 正弦听着干净，没有参考文件。",
        "单音 {hz} Hz，我听不出失真。",
        "听着干净的是这段 {hz} Hz 正弦，别的没带。",
        "哎我就觉得挺正常的，{hz} Hz 那个单音。",
        "今天风挺大的，不过这段 {hz} Hz 正弦我听着没事。",
        "正弦 {hz} Ｈｚ，听上去没失针。",
        "没参考。干净的正弦在后头，频率写的是 {hz} Hz。",
        "同事随口说了一句天气，我还是觉得这 {hz} Hz 单音没问题。",
    ),
    "insufficient": (
        "听着有点怪，你帮我看看。",
        "两个文件都传了，我说不清哪个是旧的。",
        "你帮我听听呗，反正我就觉得不对劲，今天还迟到了。",
        "怪的是这声音，哪儿不对我说不上来。",
    ),
    "blunt": (
        "参考文件是 {ref}，标称 {hz} Hz 正弦。",
        "旧录音 {ref} 是参考，测试音 {hz} Hz。",
        "参考就是 {ref}，正弦 {hz} Hz。",
        "标称 {hz} Hz 正弦，参考文件 {ref}。",
        "旧的那份 {ref} 拿来对照，测试音 {hz} Hz 正弦。",
        "参考文件 {ref}，单音 {hz} Hz。",
    ),
    "paraphrase": (
        "先前那份叫 {ref}。人耳觉得发毛。标称写的是 {hz} Hz，旁边还有一句无关的天气说明。",
        "同事说先听 {ref} 再听现在这份，单音 {hz} Hz，今天会议室很吵。",
        "发毛的是现在这份，{ref} 只是旧的对照，标称好像 {hz} Hz，窗外有人敲桌子。",
        "你先听 {ref} 呗，这新的听着毛毛的，写着 {hz} Hz 正弦，我还没吃午饭。",
        "参靠文件写的是 {ref}，正玄 {hz} Ｈｚ，听着发毛，顺便说一句空调有点响。",
        "倒过来听也一样，先是现在这份发毛，旧录音 {ref}，频率 {hz} Hz，茶水间有人聊天。",
    ),
    "clean_t2": (
        "整段听着平稳。",
        "没有听到破音。",
    ),
    "uncertain_t2": (
        "我不确定这是不是故障。",
        "也许只是录音电平高，你判断一下。",
    ),
    "segment_t2": (
        "好像只有中间一小段发毛。",
        "开头还行，后头某一小段破了。",
    ),
}

_DEV_T1_TEXT = (
    "1000 Hz 正弦，听着干净。",
    "这是 440 Hz 单音，我没听出发毛。",
    "测试音 1000 Hz，没有旧录音。",
    "正弦 880 Hz，作为干净对照。",
    "听着有点怪，你帮我看看。",
    "参考文件是 {ref}，标称 1000 Hz 正弦。",
    "先前那份叫 {ref}。新的放 1 kHz 测试音发毛，今天还下雨。",
    "旧录音 {ref} 放在一起，现在这份 1000 Hz 听着破。",
    "标称 1000 Hz 的测试音发毛。",
    "单音 1 kHz，没有参考。",
    "哎这个听着破，频率好像写了 440 Hz。",
    "会议室很吵，不过这是 1000 Hz 正弦。",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _contextual_tests(split: str) -> list[Path]:
    if split == "dev":
        folder = (
            _repo_root()
            / "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/wav"
        )
    else:
        folder = (
            _repo_root()
            / "docs/evaluations/v0_3/contextual/validation"
            / "study_v0_3_contextual_validation_1/wav"
        )
    return sorted(folder.glob("*_test.wav"))


_DEV_LABEL_SOURCE = (
    "docs/evaluations/v0_3/contextual/development/"
    "study_v0_3_contextual_dev_1/contextual_manifest.json"
)
_HELD_LABEL_SOURCE = (
    "docs/evaluations/v0_3/contextual/validation/"
    "study_v0_3_contextual_validation_1/contextual_manifest.json"
)


def _label_source(split: str) -> str:
    return _DEV_LABEL_SOURCE if split == "dev" else _HELD_LABEL_SOURCE


def _manifest_rows(split: str) -> dict[str, dict[str, object]]:
    payload = json.loads((_repo_root() / _label_source(split)).read_text(encoding="utf-8"))
    rows = payload["cases"]
    if not isinstance(rows, list):
        raise TypeError("contextual manifest cases must be a list")
    indexed: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("contextual manifest case must be an object")
        digest = row["test_wav_sha256"]
        if not isinstance(digest, str):
            raise TypeError("test_wav_sha256 must be a string")
        indexed[digest] = row
    return indexed


def _conclusion_from_row(row: dict[str, object]) -> tuple[str, tuple[str, ...]]:
    outcome = row["expected_outcome"]
    causal_raw = row["expected_causal_set"]
    if not isinstance(causal_raw, list) or not all(isinstance(item, str) for item in causal_raw):
        raise TypeError("expected_causal_set must be a list of strings")
    causal = tuple(causal_raw)
    if outcome == "no_supported_fault":
        return "no_supported_fault", ()
    if outcome == "inconclusive":
        return "inconclusive", ()
    if outcome == "supported_fault" and causal == ("clipping",):
        return "clipping", causal
    if outcome == "supported_fault" and causal == ("harmonic_distortion",):
        return "harmonic_distortion", causal
    if outcome == "supported_fault" and set(causal) == {"clipping", "harmonic_distortion"}:
        return "combined", causal
    raise ValueError(f"unmapped contextual label: {outcome} {causal}")


def _labeled_tests(split: str) -> list[tuple[Path, dict[str, object]]]:
    index = _manifest_rows(split)
    labeled: list[tuple[Path, dict[str, object]]] = []
    for path in _contextual_tests(split):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row = index.get(digest)
        if row is None:
            raise ValueError(f"no contextual label for {path.name}")
        labeled.append((path, row))
    return labeled


def _pool(split: str, outcome: str) -> list[tuple[Path, dict[str, object]]]:
    pool = [item for item in _labeled_tests(split) if item[1]["expected_outcome"] == outcome]
    if not pool:
        raise ValueError(f"no {split} wavs with expected_outcome={outcome}")
    return pool


def _reference_index(split: str) -> dict[str, Path]:
    folder = _contextual_tests(split)[0].parent
    indexed: dict[str, Path] = {}
    for path in sorted(folder.glob("*_ref.wav")):
        indexed[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    return indexed


def _reference_for(split: str, row: dict[str, object]) -> Path | None:
    digest = row.get("reference_wav_sha256")
    if not isinstance(digest, str) or not digest:
        return None
    return _reference_index(split).get(digest)


def _rel(path: Path) -> str:
    return path.resolve().relative_to(_repo_root()).as_posix()


def _render(template: str, *, hz: int, ref: str) -> str:
    return template.format(hz=hz, khz=hz / 1000, ref=ref)


def _t1_case(
    *,
    case_id: str,
    split: str,
    text: str,
    test_path: Path,
    ref_path: Path | None,
    truth: CaseTruth,
    favors_baseline: bool,
    no_fault: bool,
) -> IncrementCase:
    files = [_rel(test_path)]
    if ref_path is not None:
        files.append(_rel(ref_path))
    return IncrementCase(
        case_id=case_id,
        family="T1",
        split=split,  # type: ignore[arg-type]
        text=text,
        files=tuple(files),
        test_file=test_path.name,
        truth=truth,
        favors_baseline=favors_baseline,
        no_fault=no_fault,
    )


def _dev_t1() -> list[IncrementCase]:
    clean = _pool("dev", "no_supported_fault")
    unsure = _pool("dev", "inconclusive")
    faulty = [
        item
        for item in _pool("dev", "supported_fault")
        if _reference_for("dev", item[1]) is not None
    ]
    if not faulty:
        raise ValueError("dev supported-fault wavs have no manifest reference")
    cases: list[IncrementCase] = []
    specs = (
        (True, False, "single_signal", None, None, clean),
        (True, False, "single_signal", None, None, clean),
        (True, False, "single_signal", None, None, clean),
        (True, False, "single_signal", None, None, clean),
        (False, True, "single_signal", None, None, unsure),
        (False, False, "paired_reference", 1000.0, "single_tone", faulty),
        (False, False, "paired_reference", 1000.0, "single_tone", faulty),
        (False, False, "paired_reference", 1000.0, "single_tone", faulty),
        (False, False, "nominal_single_tone", 1000.0, "single_tone", faulty),
        (False, False, "nominal_single_tone", 1000.0, "single_tone", faulty),
        (False, False, "nominal_single_tone", 440.0, "single_tone", faulty),
        (False, False, "nominal_single_tone", 1000.0, "single_tone", faulty),
    )
    cursors = {"clean": 0, "unsure": 0, "faulty": 0}
    for index, (no_fault, insufficient, mode, nominal, stimulus, pool) in enumerate(specs):
        key = "clean" if no_fault else "unsure" if insufficient else "faulty"
        test_path, row = pool[cursors[key] % len(pool)]
        cursors[key] += 1
        ref_path = _reference_for("dev", row) if mode == "paired_reference" else None
        if mode == "paired_reference" and ref_path is None:
            raise ValueError(f"paired dev case has no manifest reference for {test_path.name}")
        ref_name = ref_path.name if ref_path is not None else ""
        text = _DEV_T1_TEXT[index].format(ref=ref_name)
        conclusion, cause_set = _conclusion_from_row(row)
        case_id = row["case_id"]
        if not isinstance(case_id, str):
            raise TypeError("contextual case_id must be a string")
        truth = CaseTruth(
            conclusion=conclusion,  # type: ignore[arg-type]
            cause_set=cause_set,
            mode=mode,  # type: ignore[arg-type]
            nominal_fundamental_hz=nominal,
            reference_file=ref_name or None,
            stimulus_kind=stimulus,  # type: ignore[arg-type]
            insufficient=insufficient,
            label_source=_DEV_LABEL_SOURCE,
            label_case_id=case_id,
        )
        cases.append(
            _t1_case(
                case_id=f"dev-t1-{index:02d}",
                split="dev",
                text=text,
                test_path=test_path,
                ref_path=ref_path,
                truth=truth,
                favors_baseline=index == 5,
                no_fault=no_fault,
            )
        )
    return cases


def _held_t1(rng: random.Random) -> list[IncrementCase]:
    pools = {
        "no_fault": _pool("heldout", "no_supported_fault"),
        "insufficient": _pool("heldout", "inconclusive"),
        "blunt": [
            item
            for item in _pool("heldout", "supported_fault")
            if _reference_for("heldout", item[1]) is not None
        ],
        "paraphrase": [
            item
            for item in _pool("heldout", "supported_fault")
            if _reference_for("heldout", item[1]) is not None
        ],
    }
    if not pools["blunt"]:
        raise ValueError("held-out supported-fault wavs have no manifest reference")
    buckets = (
        ("no_fault", 8, True, False, True),
        ("insufficient", 4, False, True, False),
        ("blunt", 6, False, False, True),
        ("paraphrase", 6, False, False, False),
    )
    cases: list[IncrementCase] = []
    cursor = 0
    for bucket, count, no_fault, insufficient, favors in buckets:
        for offset in range(count):
            test_path, row = pools[bucket][(cursor + offset) % len(pools[bucket])]
            cursor += 1
            ref_path = (
                _reference_for("heldout", row) if bucket in {"blunt", "paraphrase"} else None
            )
            if bucket in {"blunt", "paraphrase"} and ref_path is None:
                raise ValueError(f"paired held-out case has no manifest reference for {test_path.name}")
            ref_name = ref_path.name if ref_path is not None else "none.wav"
            rng.choice((0, 1))
            template = HELD_OUT_TEMPLATES[bucket][offset]
            hz = 1000 if cursor % 2 == 0 else 440
            text = _render(template, hz=hz, ref=ref_name)
            if bucket == "no_fault":
                mode = "nominal_single_tone"
                nominal: float | None = float(hz)
                stimulus = "single_tone"
                reference = None
            elif bucket == "insufficient":
                mode = "single_signal"
                nominal = None
                stimulus = None
                reference = None
            else:
                mode = "paired_reference"
                nominal = float(hz)
                stimulus = "single_tone"
                reference = ref_name
            conclusion, cause_set = _conclusion_from_row(row)
            case_id = row["case_id"]
            if not isinstance(case_id, str):
                raise TypeError("contextual case_id must be a string")
            cases.append(
                _t1_case(
                    case_id=f"held-t1-{len(cases):02d}",
                    split="heldout",
                    text=text,
                    test_path=test_path,
                    ref_path=ref_path,
                    truth=CaseTruth(
                        conclusion=conclusion,  # type: ignore[arg-type]
                        cause_set=cause_set,
                        mode=mode,  # type: ignore[arg-type]
                        nominal_fundamental_hz=nominal,
                        reference_file=reference,
                        stimulus_kind=stimulus,  # type: ignore[arg-type]
                        insufficient=insufficient,
                        label_source=_HELD_LABEL_SOURCE,
                        label_case_id=case_id,
                    ),
                    favors_baseline=favors and bucket == "blunt",
                    no_fault=no_fault,
                )
            )
    return cases


def _tone(duration_s: float, hz: float, *, amplitude: float = 0.4) -> np.ndarray:
    count = int(SAMPLE_RATE_HZ * duration_s)
    times = np.arange(count, dtype=np.float64) / SAMPLE_RATE_HZ
    return (amplitude * np.sin(2.0 * np.pi * hz * times)).astype(np.float32)


def _synthesize(kind: str, duration_s: float) -> tuple[np.ndarray, CaseTruth]:
    tone = _tone(duration_s, 440.0)
    if kind == "clean":
        samples = tone.reshape(-1, 1)
        truth = CaseTruth(
            conclusion="no_supported_fault",
            mode="single_signal",
        )
        return samples, truth
    if kind == "noise":
        samples = np.zeros((tone.shape[0], 1), dtype=np.float32)
        samples[:, 0] = 0.05
        truth = CaseTruth(
            conclusion="inconclusive",
            mode="single_signal",
            insufficient=True,
        )
        return samples, truth
    if kind == "segment_harmonic":
        times = np.arange(tone.shape[0], dtype=np.float64) / SAMPLE_RATE_HZ
        harmonic = 0.35 * np.sin(2.0 * np.pi * 880.0 * times)
        region = (times >= 1.0) & (times < 1.25)
        mixed = tone.copy()
        mixed[region] = mixed[region] + harmonic[region].astype(np.float32)
        truth = CaseTruth(
            conclusion="harmonic_distortion",
            cause_set=("harmonic_distortion",),
            mode="single_signal",
            fault_spans=(FaultSpan(start_s=1.0, end_s=1.25, channel="mixdown"),),
        )
        return mixed.reshape(-1, 1), truth
    if kind == "segment_clip":
        times = np.arange(tone.shape[0], dtype=np.float64) / SAMPLE_RATE_HZ
        mixed = tone.copy()
        mixed[(times >= 1.0) & (times < 1.05)] = 0.995
        truth = CaseTruth(
            conclusion="clipping",
            cause_set=("clipping",),
            mode="single_signal",
            fault_spans=(FaultSpan(start_s=1.0, end_s=1.05, channel="mixdown"),),
        )
        return mixed.reshape(-1, 1), truth
    if kind == "left_clip":
        left = tone.copy()
        times = np.arange(tone.shape[0], dtype=np.float64) / SAMPLE_RATE_HZ
        left[(times >= 0.5) & (times < 0.7)] = 0.995
        right = tone.copy()
        stereo = np.stack([left, right], axis=1)
        truth = CaseTruth(
            conclusion="clipping",
            cause_set=("clipping",),
            mode="single_signal",
            fault_spans=(FaultSpan(start_s=0.5, end_s=0.7, channel="left"),),
        )
        return stereo, truth
    raise ValueError(f"unknown synthetic kind {kind}")


def _overlay_fault(source: Path) -> tuple[np.ndarray, int]:
    loaded = load_wav_bytes(source.read_bytes(), filename=source.name)
    samples = np.array(loaded.record.samples, dtype=np.float32, copy=True)
    rate = loaded.record.meta.sample_rate_hz
    start = int(0.5 * rate)
    end = min(samples.shape[0], start + int(0.05 * rate))
    if end <= start:
        start = 0
        end = min(samples.shape[0], max(1, samples.shape[0] // 10))
    samples[start:end, 0] = 0.995
    return samples, rate


def _t2_plan(split: str) -> list[tuple[str, str, bool, bool]]:
    if split == "dev":
        return (
            [("clean", "clean_t2", True, False)] * 4
            + [("noise", "uncertain_t2", False, True)]
            + [("segment_harmonic", "segment_t2", False, True)] * 2
            + [("segment_clip", "segment_t2", False, False)] * 2
            + [("left_clip", "segment_t2", False, False)] * 2
            + [("overlay", "segment_t2", False, False)]
        )
    return (
        [("clean", "clean_t2", True, False)] * 8
        + [("noise", "uncertain_t2", False, False)] * 4
        + [("segment_harmonic", "segment_t2", False, True)] * 6
        + [("segment_clip", "segment_t2", False, False)] * 3
        + [("left_clip", "segment_t2", False, False)] * 2
        + [("overlay", "segment_t2", False, False)]
    )


def _build_t2(split: str, rng: random.Random, audio_root: Path) -> list[IncrementCase]:
    duration = 2.0
    overlay_sources = sorted(
        (_repo_root() / "docs/evaluations/v0_3/dev/study_v0_3_dev_1/wav").glob("*.wav")
    )
    cases: list[IncrementCase] = []
    prefix = "dev" if split == "dev" else "held"
    for index, (kind, bucket, no_fault, favors) in enumerate(_t2_plan(split)):
        filename = f"{prefix}_t2_{index:02d}.wav"
        target = audio_root / filename
        if kind == "overlay":
            source = overlay_sources[index % len(overlay_sources)]
            samples, rate = _overlay_fault(source)
        else:
            samples, _truth = _synthesize(kind, duration)
            rate = SAMPLE_RATE_HZ
        write_pcm16_wav(target, samples, sample_rate_hz=rate)
        if kind == "overlay":
            truth = CaseTruth(
                conclusion="clipping",
                cause_set=("clipping",),
                mode="single_signal",
                fault_spans=(FaultSpan(start_s=0.5, end_s=0.55, channel="mixdown"),),
            )
        else:
            truth = _synthesize(kind, duration)[1]
        template = rng.choice(HELD_OUT_TEMPLATES[bucket])
        text = template if split == "heldout" else _render(template, hz=440, ref="")
        if split == "dev" and kind == "clean":
            text = f"开发集干净对照 {index}。"
        cases.append(
            IncrementCase(
                case_id=f"{prefix}-t2-{index:02d}",
                family="T2",
                split=split,  # type: ignore[arg-type]
                text=text,
                files=(_rel(target),),
                test_file=filename,
                truth=truth,
                favors_baseline=favors,
                no_fault=no_fault,
            )
        )
    return cases


def build_cases(audio_root: Path, *, held_out_seed: int = HELD_OUT_SEED) -> list[IncrementCase]:
    rng = random.Random(held_out_seed)
    cases = _dev_t1()
    cases.extend(_build_t2("dev", rng, audio_root))
    cases.extend(_held_t1(rng))
    cases.extend(_build_t2("heldout", rng, audio_root))
    return cases


def manifest_payload(cases: list[IncrementCase]) -> dict[str, object]:
    return {
        "study_id": STUDY_ID,
        "held_out_seed": HELD_OUT_SEED,
        "template_id": TEMPLATE_ID,
        "cases": [case.model_dump(mode="json") for case in cases],
    }


def canonical_manifest(cases: list[IncrementCase]) -> str:
    return json.dumps(manifest_payload(cases), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def manifest_sha256(cases: list[IncrementCase]) -> str:
    return hashlib.sha256(canonical_manifest(cases).encode("utf-8")).hexdigest()


def proportion_report(cases: list[IncrementCase]) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    for case in cases:
        key = f"{case.split}:{case.family}"
        bucket = report.setdefault(
            key,
            {"count": 0, "no_fault": 0, "insufficient": 0, "favors_baseline": 0},
        )
        bucket["count"] += 1
        bucket["no_fault"] += int(case.no_fault)
        bucket["insufficient"] += int(case.truth.insufficient)
        bucket["favors_baseline"] += int(case.favors_baseline)
    return report


def write_study(study_dir: Path) -> str:
    """Write audio, manifest, and SHA256SUMS. Returns the manifest hash."""
    audio_root = study_dir / "wav"
    cases = build_cases(audio_root)
    text = canonical_manifest(cases)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    study_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = study_dir / "manifest.json"
    manifest_path.write_text(text, encoding="utf-8")
    lines = [f"{digest}  manifest.json"]
    for path in sorted(audio_root.glob("*.wav")):
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{file_hash}  wav/{path.name}")
    (study_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (study_dir / "manifest.sha256").write_text(digest + "\n", encoding="utf-8")
    return digest
