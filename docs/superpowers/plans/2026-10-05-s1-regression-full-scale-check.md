# S1 回归满刻度检查（V0.3 §23）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task, only after operator authorization. Cursor 负责全部实现以及审阅后发现问题的修复；Claude Code 负责设计与独立审阅。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 §23 的满刻度事实、三项用户声明、独立的满刻度检查记录、十条资格条件、判定表与固定文案；产品不带下限记录，因此产品输出仍无判定。

**Architecture:** `dsp/` 新增计数函数（判据与现有满刻度机制逐样本相同）；`tools/` 在测量当时调用它并产出与测量包并列的事实；`rules/` 做纯函数的资格判断、判定与校验；`app/` 负责声明入口、记录生成与生命周期、报告与页面。现有 `ComparisonRecord`、`MeasurementBundle` 及其摘要不改。

**Tech Stack:** 现有 Python 3.11/3.12、NumPy、Pydantic 2、FastAPI、原生 HTML/JS。不新增依赖。

**Spec:** `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §23（权威）；`docs/DECISIONS.md` D043；`docs/TEST_PLAN_V0_3_CONTEXTUAL.md` T-CX349–T-CX370；设计 `docs/superpowers/specs/2026-10-05-s1-regression-clipping-comparison-semantics-design.md` §12–§14；实测 `docs/OQ020_FULL_TOOLPATH_PROBE_2026-10-05.md`。

**Status:** 修订 2（2026-10-05）。修订 1 经操作员审阅通过后做了一次独立只读审阅，本修订按审阅意见修改；修订 2 本身未再经独立审阅。实施授权须由操作员另行向 Cursor 给出；在此之前任何 Task 不得开始。
**Read-only baseline:** `386a9b2` on `codex/v0.2-real-world-validation`（2026-10-05 读取）。执行前在当时基线上重新核对本计划引用的文件、行号与空闲测试 ID。

## Global Constraints

- 不修改 §22 文本、`ComparisonRecord` 的字段与校验、`required_checks`、整体通过逻辑、`MeasurementBundle` 及摘要、`MEASUREMENT_VERSION`、`InputIdentity`、`RetestLink`、每案例 16 次提交上限。
- 不修改 `src/signal_diag/dsp/clipping.py`、`tools/contracts.py`、`tools/service.py`；`ClippingOutput` 不加字段。
- 不修改 frozen V0.2 §§1–64、单文件诊断检测器与阈值、v9.11 prompt、因果策略、D037/D039、已封存的评测与 Demo 资产。
- 满刻度阈值取自 `ClippingInput.full_scale_threshold`；最少连续样本数固定为 `2`；位深下限固定为 `16`。
- 产品不带任何 `FullScaleMethodFloor`。带数值的下限记录只允许出现在 `tests/` 下，且不得被产品构造路径加载。本计划中的夹具数值只验证实现逻辑，不是容差、不是表征结果。
- 数值只来自确定性代码；LLM 不生成、不修改、不解释这些数值。检查结果不进入 `StructuredDiagnosis`，不改变诊断因果门。
- 本检查的判定与提示文案使用固定模板，除指标标识符 `clipping_ratio` 外不得出现 “clip” 字样。
- `rules/` 不导入 `app/`、`agent/`、`dsp/`；`tools/` 不导入 `rules/`、`app/`。
- 不运行第一层表征，不调用 RealLLM，不 seal。commit/push/PR 按操作员给 Cursor 的授权执行；不自行合并。

## Review Focus

以下五类输入最容易出错，各自的测试已写进对应任务：

1. 重复提交与锚点的分析范围、通道、采样率、阈值或版本号不同：不得计入，不得制造矛盾。Task 3。
2. “否”侧峰值在阈值下方一个量化步长以内（探针实测：100 Hz、16 位、幅度 0.99003，基线计入 0，加一步后 800）：必须落入临界区，不得判为发现回归。Task 4。
3. 高频下过阈值样本全是孤立单样本（探针实测：2 kHz、峰值 1.0，计入 0、未计入 8000）：状态为“否”，但属于临界区内。Task 1、Task 4。
4. 没有下限记录时同时存在阻断声明：状态必须是 `not_comparable`，不是 `descriptive_only`；无法评估的条件必须单列。Task 4。
5. 同一 `request_id` 的幂等重放、失败的提交：不得生成新的检查记录，不得取代已有记录。Task 5。

---

## File Structure

| 文件 | 责任 |
|---|---|
| Create `src/signal_diag/dsp/full_scale.py` | 满刻度计数（纯数值） |
| Create `src/signal_diag/tools/regression_full_scale.py` | `FullScaleFacts` 与测量当时的适配函数 |
| Create `src/signal_diag/rules/full_scale_check.py` | 声明、下限记录、检查记录模型；锚点解析；计入规则；资格、判定、校验；产品 profile 守卫 |
| Create `src/signal_diag/app/full_scale_wording.py` | 固定文案模板与逐记录的文案生成 |
| Modify `src/signal_diag/app/regression.py` | 上传声明字段、事实采集、检查记录生成与取代、快照字段、构造器参数 |
| Modify `src/signal_diag/app/regression_api.py` | 元数据接收声明 |
| Modify `src/signal_diag/app/regression_reporting.py` | 报告携带检查记录、校验、HTML 渲染 |
| Modify `src/signal_diag/app/static/regression.html`, `regression.js` | 声明输入与检查结果展示 |
| Modify `tests/test_architecture_boundaries.py` | `_V03_ADDITIVE_EXACT_PATHS` 追加三个新路径 |
| Create `tests/dsp/test_full_scale.py`, `tests/tools/test_regression_full_scale.py`, `tests/rules/test_full_scale_check.py`, `tests/rules/full_scale_fixtures.py`, `tests/app/test_full_scale_wording.py`, `tests/app/test_regression_full_scale_service.py` | 新测试 |
| Modify `tests/app/test_regression_reporting.py`, `test_regression_api.py`, `test_regression_ui.py` | 报告、API、页面的新增断言 |

测试函数名以 `test_t_cx<编号>_` 开头，对应 T-CX349–T-CX370。

**测试帮助函数约定。** 现有测试文件里的帮助函数不得修改（`tests/app/test_regression_reporting.py` 等会导入它们），而且它们编码的是 32 位 WAV。本计划的新测试一律使用 `tests/rules/full_scale_fixtures.py` 里新写的帮助函数；`tests/rules/` 是包，其它测试目录用 `from tests.rules.full_scale_fixtures import ...` 导入。该文件提供：

```python
def q16(value: float) -> float: ...                 # round(value * 32768) 截到 [-32768, 32767] 后再除以 32768
def wav16(samples: np.ndarray, *, sample_rate_hz: int = 48_000) -> bytes: ...     # 单声道，码值 = q16
def wav24(samples: np.ndarray, *, sample_rate_hz: int = 48_000) -> bytes: ...
def wav16_stereo(left: np.ndarray, right: np.ndarray, *, sample_rate_hz: int = 48_000) -> bytes: ...
def sine(*, frequency_hz: float = 100.0, amplitude: float = 0.5, duration_s: float = 2.0,
         sample_rate_hz: int = 48_000) -> np.ndarray: ...
def shaped(counted: int, peak: float, *, isolated: int = 0, duration_s: float = 2.0) -> np.ndarray: ...
    # 2 s、48 kHz 的 16 位可实现波形：幅度 0.25 的 100 Hz 正弦为底；
    # counted > 0 时把从第 1000 个样本起的 counted 个连续样本置为 q16(peak)；
    # isolated > 0 时另把 isolated 个互不相邻的样本置为 q16(peak)；
    # counted == 0 且 isolated == 0 时把底的幅度改为 peak（整段没有样本超过 q16(peak)）。
def measured(samples_or_wav, *, side="baseline", bits=16, time_range=None, channel="left",
             full_scale_threshold=0.99) -> tuple[MeasurementBundle, InMemorySignalRepository, int]: ...
    # 真实路径：load_wav_bytes -> InputIdentity -> measure_output；返回包、仓库、WAV 头里的位深
def make_submission(*, comparison_id: str, parent: str | None = None, kind: str | None = None,
                    baseline=(0, 0.5), candidate=(0, 0.5), baseline_isolated=0, candidate_isolated=0,
                    bits=(16, 16), declarations: FullScaleDeclarations | None = None,
                    time_range: TimeRange | None = None, baseline_samples=None, candidate_samples=None,
                    drop_facts: str | None = None, **condition_overrides) -> FullScaleSubmission: ...
    # 两侧各用 shaped(*pair)（或显式给的 samples）经 measured() 与 measure_full_scale_facts 生成，
    # 再用 compare_measurements 生成真实的 ComparisonRecord。事实不做任何事后改写，
    # 因此 verify_full_scale_facts 对夹具成立。bits 中的 8 只改写传入的 pcm_bit_depth 参数。
    # condition_overrides 覆盖 ComparisonConditions 字段（默认全部允许比较、versions "v1"/"v2"、
    # nominal_fundamental_hz=100.0）。drop_facts="candidate" 把该侧事实置为 None。
def eligible(*, baseline=(0, 0.5), candidate=(0, 0.5), periodic="yes", drop_repeats: str | None = None,
             repeat_baseline=None, repeat_candidate=None, **kw) -> tuple[FullScaleSubmission, tuple[FullScaleSubmission, ...]]: ...
    # 锚点 "a" + 一条两侧都声明独立的重复 "r1"（两侧波形默认与锚点相同）；
    # drop_repeats="candidate" 时重复只声明基线侧独立；repeat_* 给出则该侧重复用另一组 (counted, peak)。
def index(*subs: FullScaleSubmission) -> dict[str, FullScaleSubmission]: ...
def redigest(model): ...                             # 按该模型的摘要函数重算 digest 后返回副本
FIXTURE_FLOOR: FullScaleMethodFloor                  # 见 Task 3
```

测试里写的峰值是“请求值”，实际峰值是 `q16(请求值)`（例如 0.995 实现为 0.99499512，1.0 实现为 0.99996948）。下文断言中凡涉及峰值字面量，一律以事实对象里的值为准。

---

### Task 1: DSP 满刻度计数（T-CX349）

**Files:**
- Create: `src/signal_diag/dsp/full_scale.py`
- Test: `tests/dsp/test_full_scale.py`
- Modify: `tests/test_architecture_boundaries.py`（`_V03_ADDITIVE_EXACT_PATHS` 追加 `"src/signal_diag/dsp/full_scale.py"`）

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True, slots=True)
class FullScaleCount:
    counted_samples: int            # |x| >= threshold，且所在连续段长度 >= min_consecutive_samples
    over_threshold_uncounted: int   # |x| >= threshold，但所在连续段更短
    peak_abs: float
    analyzed_samples: int

def count_full_scale_samples(
    samples: np.ndarray,
    *,
    full_scale_threshold: float,
    min_consecutive_samples: int = 2,
) -> FullScaleCount: ...
```

- [ ] **Step 1: 写失败测试**

```python
def test_t_cx349_counts_runs_and_isolated_samples() -> None:
    x = np.array([0.0, 0.995, 0.5, 0.99, 0.991, 0.2, -1.0, -0.99, -0.995, 0.1], dtype=np.float32)
    got = count_full_scale_samples(x, full_scale_threshold=0.99)
    assert got == FullScaleCount(counted_samples=5, over_threshold_uncounted=1,
                                 peak_abs=1.0, analyzed_samples=10)

@pytest.mark.parametrize("freq,amp", [(100.0, 0.9905), (997.0, 0.991), (997.0, 0.9925),
                                      (2000.0, 1.0), (100.0, 0.5), (440.0, 0.9)])
def test_t_cx349_matches_existing_full_scale_mechanism(freq: float, amp: float) -> None:
    x = generate_sine(frequency_hz=freq, sample_rate_hz=48_000, duration_s=2.0,
                      amplitude=amp).record.samples[:, 0]
    got = count_full_scale_samples(x, full_scale_threshold=0.99)
    ref = analyze_clipping(x, full_scale_threshold=0.99)
    assert (got.counted_samples > 0) == ref.full_scale_detected
    assert got.peak_abs == ref.peak_abs
    assert got.counted_samples + got.over_threshold_uncounted == int(np.count_nonzero(np.abs(x) >= 0.99))

def test_t_cx349_isolated_peaks_are_uncounted() -> None:
    x = generate_sine(frequency_hz=2000.0, sample_rate_hz=48_000, duration_s=2.0,
                      amplitude=1.0).record.samples[:, 0]
    got = count_full_scale_samples(x, full_scale_threshold=0.99)
    assert got.counted_samples == 0 and got.over_threshold_uncounted == 8000

def test_t_cx349_rejects_bad_parameters() -> None:
    x = np.zeros(8, dtype=np.float32)
    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError):
            count_full_scale_samples(x, full_scale_threshold=bad)
    for bad in (1, True, 2.0):
        with pytest.raises(ValueError):
            count_full_scale_samples(x, full_scale_threshold=0.99, min_consecutive_samples=bad)
```

- [ ] **Step 2: 运行确认失败** — `python -m pytest tests/dsp/test_full_scale.py -q`，预期 ImportError。
- [ ] **Step 3: 实现。** 输入校验与 `analyze_clipping` 相同（复用 `preprocess._validated_1d`；阈值须有限且为正；最少连续样本数须为不小于 2 的整数、不接受 bool）。计入掩码直接调用 `dsp.clipping._qualified_runs(np.abs(values) >= threshold, min)`，不复制其逻辑，以保证与现有机制逐样本一致。
- [ ] **Step 4: 运行确认通过**，并运行 `python -m pytest tests/test_architecture_boundaries.py -q`。
- [ ] **Step 5: Commit** — `feat(dsp): full-scale sample count (T-CX349)`

### Task 2: 测量当时的满刻度事实（T-CX349、T-CX351）

**Files:**
- Create: `src/signal_diag/tools/regression_full_scale.py`
- Test: `tests/tools/test_regression_full_scale.py`
- Modify: `tests/test_architecture_boundaries.py`（追加 `"src/signal_diag/tools/regression_full_scale.py"`）

**Interfaces:**
- Consumes: `count_full_scale_samples`（Task 1）；`MeasurementBundle`、`InputIdentity`；`signal.extract_segment`。
- Produces:

```python
FULL_SCALE_FACTS_VERSION = "v0.3-full-scale-facts-1"
FULL_SCALE_MIN_CONSECUTIVE_SAMPLES = 2

class FullScaleFacts(BaseModel):          # frozen=True, extra="forbid"
    side: ComparisonSide
    run_id: str
    wav_sha256: str
    bundle_digest: str
    full_scale_threshold: float
    min_consecutive_samples: int
    counted_samples: int                  # ge=0
    over_threshold_uncounted: int         # ge=0
    state: Literal["yes", "no"]
    peak_abs: float
    analyzed_samples: int                 # gt=0
    pcm_bit_depth: Literal[8, 16, 24, 32]
    facts_version: str
    digest: str                           # 64 位十六进制

def measure_full_scale_facts(
    *, repository: SignalRepository, bundle: MeasurementBundle, pcm_bit_depth: int,
) -> FullScaleFacts | None: ...

def full_scale_facts_digest(facts: FullScaleFacts) -> str: ...
def verify_full_scale_facts(facts: FullScaleFacts, bundle: MeasurementBundle) -> None: ...  # raises ValueError
```

- [ ] **Step 1: 写失败测试**（用上面约定的 `sine`、`wav16`、`wav16_stereo`、`measured`；本任务先在夹具文件里实现这几个函数）

```python
def test_t_cx349_facts_follow_bundle_range_and_channel() -> None:
    bundle, repo, bits = measured(wav16(sine(amplitude=0.9905)), time_range=TimeRange(start_s=0.5, end_s=1.5))
    facts = measure_full_scale_facts(repository=repo, bundle=bundle, pcm_bit_depth=bits)
    ident = bundle.identity
    assert facts.analyzed_samples == ident.resolved_end_sample - ident.resolved_start_sample == 48_000
    assert facts.state == "yes" and facts.counted_samples == 1000 and facts.pcm_bit_depth == 16
    assert (facts.side, facts.run_id, facts.wav_sha256, facts.bundle_digest) == (
        ident.side, ident.run_id, ident.wav_sha256, bundle.digest)
    assert facts.full_scale_threshold == 0.99 and facts.min_consecutive_samples == 2
    assert facts.facts_version == "v0.3-full-scale-facts-1"
    assert facts.digest == full_scale_facts_digest(facts)

def test_t_cx349_facts_use_the_selected_channel() -> None:
    stereo = wav16_stereo(sine(amplitude=0.5), sine(amplitude=0.9905))
    left, repo_l, bits = measured(stereo, channel="left")
    right, repo_r, _ = measured(stereo, channel="right")
    assert measure_full_scale_facts(repository=repo_l, bundle=left, pcm_bit_depth=bits).state == "no"
    assert measure_full_scale_facts(repository=repo_r, bundle=right, pcm_bit_depth=bits).state == "yes"

def test_t_cx351_bundle_digest_unchanged_by_facts() -> None:
    bundle, repo, bits = measured(wav16(sine(amplitude=0.5)))
    before = bundle.digest
    measure_full_scale_facts(repository=repo, bundle=bundle, pcm_bit_depth=bits)
    verify_measurement_bundle_digest(bundle)
    assert bundle.digest == before and "full_scale_facts" not in bundle.model_dump()

def test_facts_absent_when_clipping_tool_failed() -> None:
    bundle, repo, bits = measured(wav16(sine(amplitude=0.5)))
    empty = InMemorySignalRepository()                       # 同一 identity、空仓库：削波工具状态为 error
    failed = measure_output(repository=empty, identity=bundle.identity,
                            selection=MeasurementSelection(**bundle.identity.tool_parameter_snapshot.model_dump()))
    assert failed.clipping.status != "success"
    assert measure_full_scale_facts(repository=empty, bundle=failed, pcm_bit_depth=bits) is None

def test_verify_rejects_tampered_or_inconsistent_facts() -> None:
    bundle, repo, bits = measured(wav16(sine(amplitude=0.9905)))
    facts = measure_full_scale_facts(repository=repo, bundle=bundle, pcm_bit_depth=bits)
    verify_full_scale_facts(facts, bundle)
    for update in ({"state": "no"}, {"peak_abs": 0.5}, {"analyzed_samples": 1},
                   {"bundle_digest": "0" * 64}, {"full_scale_threshold": 0.9}, {"counted_samples": 0}):
        with pytest.raises(ValueError):
            verify_full_scale_facts(redigest(facts.model_copy(update=update)), bundle)
    with pytest.raises(ValueError):                          # 样本数无法重算，只受摘要保护
        verify_full_scale_facts(facts.model_copy(update={"counted_samples": facts.counted_samples + 1}), bundle)
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。** 样本用 `extract_segment(record, time_range=selection.time_range, channel=selection.channel)` 取得，其中 selection 是 `bundle.identity.tool_parameter_snapshot.clipping`，与削波工具所用完全相同。`bundle.clipping.status != "success"` 或结果为空时返回 `None`。摘要算法与 `regression_measurement._canonical_json` 相同，排除 `digest` 字段。`verify_full_scale_facts` 检查：摘要；`side`/`run_id`/`wav_sha256`/`bundle_digest` 与包一致；`state == "yes"` 当且仅当 `counted_samples > 0`，且等于包内 `ClippingOutput.full_scale_detected`；`peak_abs` 等于包内 `peak_abs`；`analyzed_samples` 等于解析后的范围长度；阈值等于快照；`min_consecutive_samples == 2`；`facts_version` 为当前常量。
- [ ] **Step 4: 运行确认通过**（含 architecture 测试）。
- [ ] **Step 5: Commit** — `feat(tools): full-scale facts beside the measurement bundle (T-CX349, T-CX351)`

### Task 3: 规则层模型、锚点解析与计入规则（T-CX358、T-CX365、T-CX360）

**Files:**
- Create: `src/signal_diag/rules/full_scale_check.py`、`tests/rules/full_scale_fixtures.py`
- Test: `tests/rules/test_full_scale_check.py`
- Modify: `tests/test_architecture_boundaries.py`（追加 `"src/signal_diag/rules/full_scale_check.py"`）

**Interfaces:**
- Consumes: `FullScaleFacts`（Task 2）；`ComparisonRecord`、`ComparisonProfile`、`rules.regression._declarations_block_regression`。
- Produces:

```python
FULL_SCALE_MIN_PCM_BIT_DEPTH = 16
TOLERATED_DIFFERENCE_ID = "one_step_of_coarser_depth_one_sided_plus_depth_conversion"

class FullScaleDeclarations(BaseModel):       # frozen, extra="forbid"；三项默认 "unknown"
    periodic_test_signal: DeclarationAnswer = "unknown"
    baseline_independent_render: DeclarationAnswer = "unknown"
    candidate_independent_render: DeclarationAnswer = "unknown"

class FullScaleMethodFloor(BaseModel):        # frozen, extra="forbid"
    floor_id: str
    version: str
    facts_version: str
    full_scale_threshold: float
    min_consecutive_samples: int
    min_samples_per_period: float             # gt=0
    min_periods_in_range: float               # gt=0
    zone_below_threshold: float               # ge=0；“否”侧：peak_abs >= threshold - max(该值, step) 即区内
    zone_above_threshold: float               # ge=0；“是”侧：peak_abs <= threshold + 该值 即区内
    zone_min_counted_samples: int | None      # “是”侧：counted_samples < 该值 即区内
    count_floor_samples: int | None           # ge=0
    count_floor_ratio: float | None           # ge=0；两者至少其一非空
    tolerated_difference: Literal["one_step_of_coarser_depth_one_sided_plus_depth_conversion"]
    digest: str

def full_scale_floor_digest(floor: FullScaleMethodFloor) -> str: ...

class FullScaleSubmission(BaseModel):         # 一次已完成的比较在本检查眼中的样子
    comparison_id: str
    parent_comparison_id: str | None
    link_kind: Literal["repeat", "repair", "recommendation"] | None
    record: ComparisonRecord
    declarations: FullScaleDeclarations
    baseline_facts: FullScaleFacts | None
    candidate_facts: FullScaleFacts | None

class UncountedRepeat(BaseModel):
    comparison_id: str
    side: ComparisonSide
    reason: str                               # 见下方原因码

def resolve_anchor_id(comparison_id: str, submissions: Mapping[str, FullScaleSubmission]) -> str: ...
def select_counted_repeats(
    anchor: FullScaleSubmission, repeats: Sequence[FullScaleSubmission],
) -> tuple[tuple[FullScaleFacts, ...], tuple[FullScaleFacts, ...], tuple[UncountedRepeat, ...]]: ...
    # 返回（基线侧计入的重复事实，候选侧计入的重复事实，未计入清单）
def assert_product_profile_allowed(profile: ComparisonProfile | None) -> None: ...   # 含 clipping_ratio 规则则 ValueError

PRODUCT_APPROVED_FULL_SCALE_FLOORS: tuple[FullScaleMethodFloor, ...] = ()   # 产品侧已批准下限的登记处；现在为空
```

未计入原因码（字符串常量，按此顺序逐条判断、取第一条命中的）：`not_declared_independent`、`facts_missing`、`declarations_block`、`selection_mismatch`（`tool_parameter_snapshot` 不同，含通道、时间范围参数与阈值）、`range_mismatch`（解析后的起止样本不同）、`sample_rate_mismatch`、`version_mismatch`。`declarations_block`、`selection_mismatch`、`range_mismatch`、`sample_rate_mismatch`、`version_mismatch` 是整次提交的属性，两侧都按同一原因列出（已因前两条原因列出的那一侧不重复列）。

说明：下限记录的两个临界区边距加一个可选的最小计入数、两个可选的差值下限，足以表达设计列出的候选形式在批准域约束下的保守版本；表征若得出无法用它表达的形式，另起 `version` 修订模型，不在本计划内猜测。

- [ ] **Step 1: 补全夹具并写失败测试。** 在 `tests/rules/full_scale_fixtures.py` 里实现约定中的 `shaped`、`make_submission`、`eligible`、`index`、`redigest`，以及：

`FIXTURE_FLOOR = FullScaleMethodFloor(floor_id="fixture_floor", version="test-1", facts_version="v0.3-full-scale-facts-1", full_scale_threshold=0.99, min_consecutive_samples=2, min_samples_per_period=20.0, min_periods_in_range=10.0, zone_below_threshold=0.001, zone_above_threshold=0.001, zone_min_counted_samples=None, count_floor_samples=10, count_floor_ratio=None, tolerated_difference=TOLERATED_DIFFERENCE_ID, digest=<按摘要函数计算>)`，文件头注明“仅测试夹具，不是容差”。

```python
def test_t_cx365_anchor_resolution() -> None:
    subs = index(make_submission(comparison_id="a"),
                  make_submission(comparison_id="r1", parent="a", kind="repeat"),
                  make_submission(comparison_id="r2", parent="r1", kind="repeat"),
                  make_submission(comparison_id="fix", parent="a", kind="repair"),
                  make_submission(comparison_id="rec", parent="a", kind="recommendation"),
                  make_submission(comparison_id="r3", parent="fix", kind="repeat"))
    assert [resolve_anchor_id(k, subs) for k in ("a", "r1", "r2", "fix", "rec", "r3")] == \
           ["a", "a", "a", "fix", "rec", "fix"]

def test_t_cx358_counted_repeat_rules() -> None:
    anchor = make_submission(comparison_id="a")
    indep = FullScaleDeclarations(baseline_independent_render="yes", candidate_independent_render="yes")
    ok = make_submission(comparison_id="r1", parent="a", kind="repeat", declarations=indep)
    one_side = make_submission(comparison_id="r2", parent="a", kind="repeat",
                               declarations=FullScaleDeclarations(candidate_independent_render="yes"))
    other_range = make_submission(comparison_id="r3", parent="a", kind="repeat", declarations=indep,
                                  time_range=TimeRange(start_s=0.0, end_s=1.0))
    other_version = make_submission(comparison_id="r4", parent="a", kind="repeat", declarations=indep,
                                    candidate_version="v9")
    blocked = make_submission(comparison_id="r5", parent="a", kind="repeat", declarations=indep,
                              same_input="unknown")
    base, cand, uncounted = select_counted_repeats(anchor, (ok, one_side, other_range, other_version, blocked))
    assert len(base) == 1 and len(cand) == 2
    assert {(u.comparison_id, u.side, u.reason) for u in uncounted} == {
        ("r2", "baseline", "not_declared_independent"),
        ("r3", "baseline", "selection_mismatch"), ("r3", "candidate", "selection_mismatch"),
        ("r4", "baseline", "version_mismatch"), ("r4", "candidate", "version_mismatch"),
        ("r5", "baseline", "declarations_block"), ("r5", "candidate", "declarations_block")}

def test_t_cx358_other_reasons_and_byte_identical_marking() -> None:
    anchor = make_submission(comparison_id="a", baseline=(2000, 0.995), candidate=(2000, 0.995))
    indep = FullScaleDeclarations(baseline_independent_render="yes", candidate_independent_render="yes")
    same_bytes = make_submission(comparison_id="r1", parent="a", kind="repeat", declarations=indep,
                                 baseline=(2000, 0.995), candidate=(2000, 0.995))
    no_facts = make_submission(comparison_id="r2", parent="a", kind="repeat", declarations=indep,
                               drop_facts="candidate")
    other_threshold = make_submission(comparison_id="r3", parent="a", kind="repeat", declarations=indep,
                                      full_scale_threshold=0.98)
    _, _, uncounted = select_counted_repeats(anchor, (same_bytes, no_facts, other_threshold))
    assert ("r2", "candidate", "facts_missing") in {(u.comparison_id, u.side, u.reason) for u in uncounted}
    assert ("r3", "baseline", "selection_mismatch") in {(u.comparison_id, u.side, u.reason) for u in uncounted}
    rec = evaluate_full_scale_check(check_id="c", anchor=anchor, repeats=(same_bytes,), floor=None, supersedes=None)
    assert set(rec.byte_identical_repeats) == {("r1", "baseline"), ("r1", "candidate")}   # Task 4 完成后生效

def test_t_cx358_anchor_independence_declarations_are_ignored() -> None:
    anchor = make_submission(comparison_id="a", declarations=FullScaleDeclarations(
        baseline_independent_render="yes", candidate_independent_render="yes"))
    assert select_counted_repeats(anchor, ()) == ((), (), ())

def test_t_cx360_product_profile_guard() -> None:
    assert_product_profile_allowed(None)
    assert_product_profile_allowed(build_fixture_thd_profile())
    with pytest.raises(ValueError, match="clipping_ratio"):
        assert_product_profile_allowed(build_fixture_clipping_profile())

def test_declarations_default_unknown_and_forbid_extra() -> None:
    assert FullScaleDeclarations().model_dump() == {
        "periodic_test_signal": "unknown", "baseline_independent_render": "unknown",
        "candidate_independent_render": "unknown"}
    with pytest.raises(ValidationError):
        FullScaleDeclarations(approved=True)
```

（`make_submission(..., full_scale_threshold=0.98)` 与 `time_range=` 透传给 `measured`。`test_t_cx358_other_reasons_and_byte_identical_marking` 的最后两行依赖 Task 4，本任务内先标 `xfail(strict=True)`，Task 4 去掉标记。）

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。** `resolve_anchor_id` 沿 `parent_comparison_id` 回溯，仅当当前项 `link_kind == "repeat"` 时继续；父项缺失或出现环则 `ValueError`。`select_counted_repeats` 只处理 `link_kind == "repeat"` 的项，比较对象是锚点的 `record.baseline_bundle.identity` / `candidate_bundle.identity`（`tool_parameter_snapshot`、`resolved_start_sample`、`resolved_end_sample`、`sample_rate_hz`）与 `record.conditions` 的两个版本号。
- [ ] **Step 4: 运行确认通过**（含 architecture 测试）。
- [ ] **Step 5: Commit** — `feat(rules): full-scale check models, anchor resolution, counted repeats`

### Task 4: 资格、判定与校验（T-CX350、T-CX352、T-CX353、T-CX354、T-CX356、T-CX357、T-CX359、T-CX361、T-CX362、T-CX363、T-CX366、T-CX367）

**Files:**
- Modify: `src/signal_diag/rules/full_scale_check.py`
- Test: `tests/rules/test_full_scale_check.py`

**Interfaces:**
- Consumes: Task 3 的全部模型与函数。
- Produces:

```python
FullScaleTransition = Literal["no_to_no", "no_to_yes", "yes_to_yes_increase",
                              "yes_to_yes_equal", "yes_to_yes_decrease", "yes_to_no"]

class FullScaleCheckRecord(BaseModel):        # frozen, extra="forbid"
    check_id: str
    anchor_comparison_id: str
    anchor_digest: str
    repeat_comparison_ids: tuple[str, ...]
    uncounted_repeats: tuple[UncountedRepeat, ...]
    declarations: tuple[tuple[str, FullScaleDeclarations], ...]   # (comparison_id, 声明)，锚点在前
    baseline_renders: tuple[FullScaleFacts, ...]                  # 锚点文件在前，其后为计入的重复
    candidate_renders: tuple[FullScaleFacts, ...]
    counted_baseline_repeats: int
    counted_candidate_repeats: int
    byte_identical_repeats: tuple[tuple[str, ComparisonSide], ...]
    floor: FullScaleMethodFloor | None
    status: MetricStatus
    transition: FullScaleTransition | None    # 两侧事实都存在时给出，与是否合格无关
    count_difference: int | None              # candidate - baseline（锚点文件）
    unmet_conditions: tuple[str, ...]
    unevaluated_conditions: tuple[str, ...]
    supersedes: str | None
    digest: str

def evaluate_full_scale_check(
    *, check_id: str, anchor: FullScaleSubmission, repeats: Sequence[FullScaleSubmission],
    floor: FullScaleMethodFloor | None, supersedes: str | None,
) -> FullScaleCheckRecord: ...

def validate_full_scale_check_record(
    record: FullScaleCheckRecord, *, anchor: FullScaleSubmission, repeats: Sequence[FullScaleSubmission],
    approved_floors: Sequence[FullScaleMethodFloor] = PRODUCT_APPROVED_FULL_SCALE_FLOORS,
) -> None: ...                                # raises ValueError
```

字段定义：`anchor_digest` 是 `anchor.record.digest`。`repeat_comparison_ids` 是传入的全部 `repeats` 的 `comparison_id`，保持传入顺序（调用方按提交顺序传入该锚点下的全部重复，无论是否计入）。`byte_identical_repeats` 列出计入的重复中、该侧事实的 `wav_sha256` 与锚点同侧文件相同的 `(comparison_id, side)`。`counted_*_repeats` 只数重复，不含锚点文件。

条件码（`unmet_conditions` / `unevaluated_conditions` 的取值，按下表顺序输出）与不成立时的状态：

| 码 | 条件 | 不成立时 |
|---|---|---|
| `facts_missing:<side>` | 锚点两侧事实都存在 | `not_comparable` |
| `declarations_block:<原因>` | `_declarations_block_regression(anchor.record.conditions)` 为 `None`；原因取其返回值 | `not_comparable` |
| `repeat_missing:<side>` | 该侧计入的重复数 ≥ 1 | `descriptive_only` |
| `renders_inconsistent:<side>` | 该侧锚点文件与计入重复的 `counted_samples` 与 `state` 全部相同 | `not_comparable` |
| `same_version` | 两个版本号不同 | `descriptive_only` |
| `periodic_not_declared` | 锚点 `periodic_test_signal == "yes"` | `descriptive_only` |
| `bit_depth_below_16:<side>` | 锚点两侧文件 `pcm_bit_depth >= 16` | `descriptive_only` |
| `floor_missing` | 存在下限记录，且其 `facts_version`、阈值、最少连续样本数与两侧事实相同，且摘要自洽 | `descriptive_only` |
| `fundamental_not_declared` | `nominal_fundamental_hz` 已声明且为正的有限数 | `descriptive_only` |
| `samples_per_period_below_domain` | `sample_rate_hz / f0 >= min_samples_per_period` | `descriptive_only` |
| `periods_in_range_below_domain` | `analyzed_samples * f0 / sample_rate_hz >= min_periods_in_range` | `descriptive_only` |
| `critical_zone:<side>` | 该侧在临界区外 | `descriptive_only` |

规则：
- 列出全部不成立的条件。任何 `not_comparable` 码出现时状态为 `not_comparable`，否则有任何未满足或未评估条件时为 `descriptive_only`。
- `floor_missing` 时，`samples_per_period_below_domain`、`periods_in_range_below_domain` 与 `critical_zone_reviewed` 进入 `unevaluated_conditions`；`fundamental_not_declared` 仍照常评估。
- 临界区固定最低要求始终评估：`step = 1 / 2 ** (min(两侧锚点文件位深) - 1)`；“否”侧 `peak_abs >= threshold - step` 即输出 `critical_zone:<side>`。有下限记录时，“否”侧改用 `threshold - max(zone_below_threshold, step)`；“是”侧在 `peak_abs <= threshold + zone_above_threshold` 或 `counted_samples < zone_min_counted_samples`（非空时）时区内。
- 判定（仅在无未满足、无未评估条件时）：`no_to_no`、`yes_to_no`、`yes_to_yes_decrease`、`yes_to_yes_equal` → `no_regression_detected`；`no_to_yes` → `regression_detected`；`yes_to_yes_increase` 当差值超过下限时 `regression_detected`，否则 `no_regression_detected`。“超过下限”定义为：`count_floor_samples` 非空则要求 `diff > count_floor_samples`，`count_floor_ratio` 非空则要求 `diff / analyzed_samples > count_floor_ratio`，两者都非空时须同时满足。
- 某侧事实缺失时：只输出 `facts_missing:<side>`，凡需要该侧事实的条件（`renders_inconsistent`、`bit_depth_below_16`、`critical_zone`）对该侧跳过；下限身份只与存在的那一侧比对；`step` 用存在的那一侧的位深；`transition` 与 `count_difference` 为 `None`。两侧都缺失时 `periods_in_range_below_domain` 与临界区条件全部跳过。
- `fundamental_not_declared` 时两个批准域条件跳过（不输出、也不列为未评估）。
- `step = max(2.0 ** -(min_bits - 1), 2.0 ** -24)`。样本以 float32 保存，0.5–1.0 之间的分辨率是 2⁻²⁴，因此 32 位文件按 2⁻²⁴ 取步长。
- 记录摘要覆盖除 `digest` 外的全部字段。`validate_full_scale_check_record` 依次：核对记录摘要；要求 `record.floor` 为 `None` 或与 `approved_floors` 中某一条完全相等；对每份事实调用 `verify_full_scale_facts`（对应其所属的包）；再用记录内的 `floor`、`check_id`、`supersedes` 和传入的 `anchor`、`repeats` 重新调用 `evaluate_full_scale_check`，结果须与记录逐字段相等。

- [ ] **Step 1: 写失败测试。** 用 `eligible`、`make_submission` 与 `FIXTURE_FLOOR`。`eligible()` 的默认组合全部合格：声明周期测试信号、基频 100 Hz、版本 `"v1"`/`"v2"`、两侧各一次声明独立且波形相同的重复、16 位、2 s、48 kHz。

```python
def _status(anchor, repeats, floor=FIXTURE_FLOOR):
    r = evaluate_full_scale_check(check_id="chk_1", anchor=anchor, repeats=repeats, floor=floor, supersedes=None)
    return r.status, r.transition, r.unmet_conditions, r.unevaluated_conditions

@pytest.mark.parametrize("baseline,candidate,status,transition", [
    ((0, 0.5),      (0, 0.6),       "no_regression_detected", "no_to_no"),
    ((0, 0.5),      (2000, 0.995),  "regression_detected",    "no_to_yes"),
    ((2000, 0.995), (2011, 0.995),  "regression_detected",    "yes_to_yes_increase"),
    ((2000, 0.995), (2010, 0.995),  "no_regression_detected", "yes_to_yes_increase"),
    ((2000, 0.995), (2000, 0.995),  "no_regression_detected", "yes_to_yes_equal"),
    ((2000, 0.995), (1500, 0.995),  "no_regression_detected", "yes_to_yes_decrease"),
    ((2000, 0.995), (0, 0.5),       "no_regression_detected", "yes_to_no"),
])
def test_t_cx352_353_354_transition_table(baseline, candidate, status, transition) -> None:
    anchor, repeats = eligible(baseline=baseline, candidate=candidate)
    assert _status(anchor, repeats) == (status, transition, (), ())

@pytest.mark.parametrize("overrides,code,status", [
    ({"periodic": "unknown"},              "periodic_not_declared",           "descriptive_only"),
    ({"periodic": "no"},                   "periodic_not_declared",           "descriptive_only"),
    ({"candidate_version": "v1"},          "same_version",                    "descriptive_only"),
    ({"nominal_fundamental_hz": None},     "fundamental_not_declared",        "descriptive_only"),
    ({"nominal_fundamental_hz": 4000.0},   "samples_per_period_below_domain", "descriptive_only"),
    ({"nominal_fundamental_hz": 2.0},      "periods_in_range_below_domain",   "descriptive_only"),
    ({"bits": (8, 16)},                    "bit_depth_below_16:baseline",     "descriptive_only"),
    ({"full_scale_threshold": 0.98},       "floor_missing",                   "descriptive_only"),
    ({"drop_repeats": "candidate"},        "repeat_missing:candidate",        "descriptive_only"),
    ({"same_input": "unknown"},            "declarations_block:same_input=unknown", "not_comparable"),
    ({"repeatability": "observed_variable"}, "declarations_block:repeatability=observed_variable", "not_comparable"),
    ({"repeat_candidate": (2400, 0.995)},  "renders_inconsistent:candidate",  "not_comparable"),
    ({"drop_facts": "candidate"},          "facts_missing:candidate",         "not_comparable"),
])
def test_t_cx356_359_362_366_each_gate_blocks_a_large_onset(overrides, code, status) -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(20000, 1.0), **overrides)
    got_status, _, unmet, _ = _status(anchor, repeats)
    assert got_status == status and code in unmet

def test_t_cx357_no_side_within_one_step_is_inside_zone() -> None:
    # 16 位：基线峰值码 32440（0.98999023，低于阈值）、候选 800 个样本在码 32441（0.99002075）
    anchor, repeats = eligible(baseline=(0, 0.9899902), candidate=(800, 0.9900208))
    status, transition, unmet, _ = _status(anchor, repeats)
    assert status == "descriptive_only" and transition == "no_to_yes"
    assert "critical_zone:baseline" in unmet and "critical_zone:candidate" in unmet

def test_t_cx357_fixed_minimum_holds_without_floor() -> None:
    anchor, repeats = eligible(baseline=(0, 0.9899902), candidate=(800, 0.9900208))
    _, _, unmet, _ = _status(anchor, repeats, floor=None)
    assert "critical_zone:baseline" in unmet

def test_t_cx357_isolated_over_threshold_no_side_is_inside_zone() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), baseline_isolated=40, candidate=(2000, 0.995))
    # 2 kHz 型：基线有 40 个孤立的过阈值样本，计入 0
    assert anchor.baseline_facts.counted_samples == 0 and anchor.baseline_facts.over_threshold_uncounted == 40
    assert "critical_zone:baseline" in _status(anchor, repeats)[2]

def test_t_cx363_no_floor_means_no_judged_status() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(20000, 1.0))
    status, _, unmet, unevaluated = _status(anchor, repeats, floor=None)
    assert status == "descriptive_only" and unmet == ("floor_missing",)
    assert unevaluated == ("samples_per_period_below_domain", "periods_in_range_below_domain", "critical_zone_reviewed")
    mismatched = redigest(FIXTURE_FLOOR.model_copy(update={"full_scale_threshold": 0.98}))
    assert "floor_missing" in _status(anchor, repeats, floor=mismatched)[2]
    broken = FIXTURE_FLOOR.model_copy(update={"count_floor_samples": 0})        # 摘要不自洽
    assert "floor_missing" in _status(anchor, repeats, floor=broken)[2]

def test_t_cx366_not_comparable_precedes_descriptive_and_all_are_listed() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(20000, 1.0),
                                same_input="no", periodic="unknown", candidate_version="v1")
    status, _, unmet, _ = _status(anchor, repeats, floor=None)
    assert status == "not_comparable"
    assert {"declarations_block:same_input=no", "periodic_not_declared", "same_version", "floor_missing"} <= set(unmet)

def test_t_cx350_ratio_difference_never_changes_status() -> None:
    # 真实路径：两侧都是未削波的 100 Hz 正弦，幅度 0.01 的一侧 clipping_ratio 约 0.52，满刻度计入 0
    anchor, repeats = eligible(baseline_samples=sine(amplitude=0.5), candidate_samples=sine(amplitude=0.01))
    ratio = anchor.record.candidate_bundle.clipping.result.clipping_ratio
    assert ratio > 0.5 and anchor.candidate_facts.counted_samples == 0
    assert _status(anchor, repeats)[:2] == ("no_regression_detected", "no_to_no")

def test_t_cx356_periodic_declaration_is_read_from_the_anchor_only() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995), periodic="unknown")
    declared = repeats[0].model_copy(update={"declarations": repeats[0].declarations.model_copy(
        update={"periodic_test_signal": "yes"})})
    assert "periodic_not_declared" in _status(anchor, (declared,))[2]

def test_t_cx361_sub_full_scale_pair_gets_no_regression_signal() -> None:
    # 两侧都在阈值以下被削平：削波前幅度 1.2 的正弦分别削在 0.5 与 0.9
    anchor, repeats = eligible(baseline_samples=np.clip(sine(amplitude=1.2), -0.5, 0.5),
                               candidate_samples=np.clip(sine(amplitude=1.2), -0.9, 0.9))
    assert anchor.record.clipping_facts[0].flat_top_detected is True       # 辅助事实仍在比较记录里
    assert _status(anchor, repeats)[:2] == ("no_regression_detected", "no_to_no")

def test_t_cx367_validation_recomputes_and_rejects_tampering() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    rec = evaluate_full_scale_check(check_id="chk_1", anchor=anchor, repeats=repeats, floor=FIXTURE_FLOOR, supersedes=None)
    validate_full_scale_check_record(rec, anchor=anchor, repeats=repeats, approved_floors=(FIXTURE_FLOOR,))
    for update in ({"status": "no_regression_detected"}, {"unmet_conditions": ("same_version",)},
                   {"counted_candidate_repeats": 5}, {"transition": "no_to_no"}, {"repeat_comparison_ids": ()}):
        with pytest.raises(ValueError):
            validate_full_scale_check_record(redigest(rec.model_copy(update=update)), anchor=anchor,
                                             repeats=repeats, approved_floors=(FIXTURE_FLOOR,))
    with pytest.raises(ValueError):
        validate_full_scale_check_record(rec.model_copy(update={"digest": "0" * 64}), anchor=anchor,
                                         repeats=repeats, approved_floors=(FIXTURE_FLOOR,))

def test_t_cx363_unapproved_floor_fails_validation() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    rec = evaluate_full_scale_check(check_id="chk_1", anchor=anchor, repeats=repeats, floor=FIXTURE_FLOOR, supersedes=None)
    assert rec.status == "regression_detected"
    with pytest.raises(ValueError, match="floor"):
        validate_full_scale_check_record(rec, anchor=anchor, repeats=repeats)      # 默认登记处为空
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现**，严格按上面的条件表、规则与判定。
- [ ] **Step 4: 运行确认通过**；再跑 `python -m pytest tests/rules -q`，确认 `tests/rules/test_regression.py` 无变化地通过（T-CX351）。
- [ ] **Step 5: Commit** — `feat(rules): full-scale check eligibility, judgment and validation`

### Task 5: 服务层——声明、事实采集与记录生命周期（T-CX351、T-CX360、T-CX363、T-CX364、T-CX370）

**Files:**
- Modify: `src/signal_diag/app/regression.py`
- Test: `tests/app/test_regression_full_scale_service.py`

**Interfaces:**
- Consumes: Task 2–4。
- Produces（均为新增，带默认值，旧调用方不受影响）：
  - `ComparisonUpload.full_scale_declarations: FullScaleDeclarations = FullScaleDeclarations()`
  - `CaseComparisonItem.full_scale_declarations: FullScaleDeclarations = FullScaleDeclarations()`、`.baseline_full_scale: FullScaleFacts | None = None`、`.candidate_full_scale: FullScaleFacts | None = None`
  - `RegressionCaseSnapshot.full_scale_checks: tuple[FullScaleCheckRecord, ...] = ()`
  - `RegressionWorkbenchService.__init__(..., full_scale_floor: FullScaleMethodFloor | None = None)`
  - `build_regression_service()` 仍不带参数，内部以 `None` 传入 profile 与下限记录，并在构造前调用 `assert_product_profile_allowed(profile)`。
  - 模块级函数 `submissions_from_items(items: Sequence[CaseComparisonItem]) -> dict[str, FullScaleSubmission]`，供 Task 6 复用。

- [ ] **Step 1: 写失败测试。** 本测试文件自带 `_upload(**overrides) -> ComparisonUpload`：默认两侧都是 `wav16(sine(amplitude=0.5))`、条件全部允许比较、版本 `"v1"`/`"v2"`、默认选择；`overrides` 直接覆盖 `ComparisonUpload` 字段。同文件自带 `_conditions(**overrides) -> ComparisonConditions`（默认全部允许比较）。`service` 夹具为 `RegressionWorkbenchService(clock=lambda: NOW)`。不修改 `tests/app/test_regression_service.py`。

```python
async def test_t_cx364_one_record_per_completed_comparison_with_superseding(service) -> None:
    case = service.create_case("goal")
    s1 = await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    assert len(s1.full_scale_checks) == 1
    first = s1.full_scale_checks[0]
    assert first.anchor_comparison_id == s1.comparisons[0].comparison_id and first.supersedes is None
    link = RetestLink(kind="repeat", parent_comparison_id=first.anchor_comparison_id)
    indep = FullScaleDeclarations(baseline_independent_render="yes", candidate_independent_render="yes")
    s2 = await service.submit_comparison(case.case_id, _upload(full_scale_declarations=indep),
                                         request_id="r2", link=link)
    assert len(s2.full_scale_checks) == 2
    second = s2.full_scale_checks[1]
    assert second.supersedes == first.check_id and second.anchor_comparison_id == first.anchor_comparison_id
    assert (second.counted_baseline_repeats, second.counted_candidate_repeats) == (1, 1)
    assert s2.full_scale_checks[0] == first                      # 不可变

async def test_t_cx364_replay_and_failure_produce_no_record(service) -> None:
    case = service.create_case("goal")
    await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    again = await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    assert len(again.full_scale_checks) == 1
    with pytest.raises(InvalidRequestError):
        await service.submit_comparison(case.case_id, _upload(baseline_data=b"not a wav"), request_id="r2")
    assert len(service.get_case(case.case_id).full_scale_checks) == 1

async def test_t_cx364_records_do_not_consume_submit_quota(service) -> None:
    case = service.create_case("goal")
    for i in range(16):
        await service.submit_comparison(case.case_id, _upload(), request_id=f"r{i}")
    snap = service.get_case(case.case_id)
    assert len(snap.comparisons) == 16 and len(snap.full_scale_checks) == 16
    with pytest.raises(AppCapacityError):
        await service.submit_comparison(case.case_id, _upload(), request_id="r16")

async def test_t_cx363_product_builder_has_no_floor_and_no_judged_status() -> None:
    service = build_regression_service()
    case = service.create_case("goal")
    snap = await service.submit_comparison(case.case_id, _upload(), request_id="r1")
    check = snap.full_scale_checks[0]
    assert check.floor is None and "floor_missing" in check.unmet_conditions
    assert check.status in ("descriptive_only", "not_comparable")

def test_t_cx363_client_cannot_supply_floor_or_approval() -> None:
    for extra in ({"full_scale_floor": {}}, {"floor": {}}, {"approved": True}, {"full_scale_checks": []}):
        with pytest.raises(ValidationError):
            ComparisonUpload(**_upload().model_dump(), **extra)

def test_t_cx370_fingerprint_covers_declarations() -> None:
    a = _upload()
    b = _upload(full_scale_declarations=FullScaleDeclarations(periodic_test_signal="yes"))
    assert _upload_fingerprint(a) != _upload_fingerprint(b)
    assert _upload().full_scale_declarations == FullScaleDeclarations()

async def test_t_cx351_comparison_record_unchanged_by_full_scale(service) -> None:
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id, _upload(full_scale_declarations=FullScaleDeclarations(periodic_test_signal="yes")),
        request_id="r1")
    record = snap.comparisons[0].record
    validate_comparison_record(record)
    assert record.required_checks == ("clipping_ratio", "thd_percent", "declarations", "tool_success")
    assert record.overall_regression_pass is None
    assert snap.comparisons[0].baseline_full_scale.pcm_bit_depth == 16

async def test_bit_depth_comes_from_wav_header(service) -> None:
    case = service.create_case("goal")
    snap = await service.submit_comparison(case.case_id, _upload(baseline_data=wav24(sine(amplitude=0.5))),
                                           request_id="r1")
    item = snap.comparisons[0]
    assert (item.baseline_full_scale.pcm_bit_depth, item.candidate_full_scale.pcm_bit_depth) == (24, 16)
```

```python
async def test_report_shows_record_status_beside_not_comparable_check(service) -> None:
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id, _upload(conditions=_conditions(same_input="unknown")), request_id="r1")
    assert snap.full_scale_checks[0].status == "not_comparable"
    assert {m.status for m in snap.comparisons[0].record.metric_comparisons} == {"descriptive_only"}
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。**
  - `_execute_comparison_group` 改为返回一个内部数据类（`record`、`baseline_facts`、`candidate_facts`）；两次 `measure_output` 之后、`finally` 清空仓库之前，各调用一次 `measure_full_scale_facts`，位深取自 `baseline_loaded.source_info.bits_per_sample` / `candidate_loaded.source_info.bits_per_sample`。
  - 在追加 `CaseComparisonItem` 的同一个锁区间内：用 `submissions_from_items(case.comparisons)` 建索引，`resolve_anchor_id` 找到锚点，取该锚点下的全部重复（按提交顺序，无论是否计入），调用 `evaluate_full_scale_check(check_id=_new_id("fsc"), ..., floor=self._full_scale_floor, supersedes=<该锚点最近一条检查记录的 check_id 或 None>)`，追加到 `_CaseState.full_scale_checks`。
  - 幂等重放与失败路径在此之前已返回或抛出，不改动。配额计数逻辑不改动。
- [ ] **Step 4: 运行确认通过**；再跑 `python -m pytest tests/app/test_regression_service.py tests/app/test_regression_recommendations.py -q`，确认原有测试不改即通过（`test_injected_fixture_profile_can_enable_rules` 仍可向构造器注入夹具 profile）。
- [ ] **Step 5: Commit** — `feat(app): full-scale declarations, facts capture and check record lifecycle`

### Task 6: 固定文案与报告（T-CX354、T-CX355、T-CX360、T-CX367、T-CX368）

**Files:**
- Create: `src/signal_diag/app/full_scale_wording.py`
- Modify: `src/signal_diag/app/regression_reporting.py`
- Test: `tests/app/test_full_scale_wording.py`、`tests/app/test_regression_reporting.py`

**Interfaces:**
- Consumes: `FullScaleCheckRecord`、`submissions_from_items`、`validate_full_scale_check_record`。
- Produces:
  - `full_scale_check_lines(record: FullScaleCheckRecord) -> tuple[str, ...]`（该记录需展示的全部固定文案行，顺序即下方“必出的行”的书写顺序）
  - `build_case_report(snapshot, *, generated_at, approved_floors=PRODUCT_APPROVED_FULL_SCALE_FLOORS)`、`validate_regression_case_report_integrity(..., full_scale_checks=(), approved_floors=PRODUCT_APPROVED_FULL_SCALE_FLOORS)`；`RegressionCaseReport` 的模型校验器只用产品登记处
  - `CLIPPING_RATIO_NOTICE: str`、`FULL_SCALE_TEMPLATES: Mapping[str, str]`
  - `RegressionCaseReport.full_scale_checks: tuple[FullScaleCheckRecord, ...] = ()`；`schema_version` 保持 `"regression_case_report_v1"`（新增字段带默认值，旧载荷仍可解析）。

固定文案（英文，逐字使用；花括号为代入值）：

| 键 | 文案 |
|---|---|
| `status.regression_detected` | `Samples reaching the full-scale threshold increased.` |
| `status.no_regression_detected.no_increase` | `No increase found in samples reaching the full-scale threshold.` |
| `status.no_regression_detected.within_floor` | `The increase in samples reaching the full-scale threshold is not above the method floor.` |
| `status.no_regression_detected.decrease` | `Samples reaching the full-scale threshold decreased: {baseline} to {candidate}. No cause is stated.` |
| `status.descriptive_only` | `Descriptive only. No judgment is made for samples reaching the full-scale threshold.` |
| `status.not_comparable` | `Not comparable. No judgment is made for samples reaching the full-scale threshold.` |
| `notice.export_settings` | `This difference may come from export settings (bit depth, dither, gain, start point) and not necessarily from the version.` |
| `notice.values` | `Baseline: {baseline_counted} samples, peak {baseline_peak}. Candidate: {candidate_counted} samples, peak {candidate_peak}.` |
| `notice.floor` | `Difference {difference} samples; method floor {floor}.` |
| `notice.renders` | `Based on {baseline_n} consistent baseline render(s) and {candidate_n} consistent candidate render(s).` |
| `notice.declared` | `Periodic test signal, determinism, independent renders and the nominal fundamental are declared by the user, not verified. If the declared fundamental is wrong, the approved-domain limits do not apply.` |
| `notice.coverage` | `THD is not covered by this check. clipping_ratio is descriptive only.` |
| `notice.uncounted` | `Repeat {comparison_id} ({side}) is not counted: {reason}.` |
| `notice.byte_identical` | `Repeat {comparison_id} ({side}) is byte-identical to the original file.` |
| `notice.inconsistent` | `Renders declared deterministic differ on the {side} side: {values} samples.` |
| `notice.unmet` | `Conditions not met: {codes}.` |
| `notice.unevaluated` | `Conditions not evaluated (no approved method floor): {codes}.` |
| `notice.no_floor` | `This measurement configuration has no approved method floor.` |
| `CLIPPING_RATIO_NOTICE` | `clipping_ratio includes flat-top detection results and may be non-zero on low-frequency or low-level input that has no full-scale samples. It is not a measure of severity.` |

代入格式：峰值用 `f"{value:.6f}"`；样本数用十进制整数；`{codes}` 用 `", "` 连接；`{values}` 是该侧各次渲染的 `counted_samples`，用 `" / "` 连接、锚点文件在前；`{baseline_n}`、`{candidate_n}` 是渲染次数（锚点文件加计入的重复）；`{floor}` 在只有样本下限时为 `"{n} samples"`，只有比例下限时为 `"{r:.6f} of analyzed samples"`，两者都有时用 `" and "` 连接，没有下限记录时为 `"none"`。

必出的行，按此顺序：

1. 状态行。`no_regression_detected` 按转换选择：`yes_to_no`、`yes_to_yes_decrease` 用 `...decrease`；`yes_to_yes_increase` 用 `...within_floor`；其余用 `...no_increase`。
2. `notice.values`（两侧事实都存在时）。
3. `notice.floor`（转换为 `yes_to_yes_*` 时，无论是否有下限记录）。
4. `notice.renders`。
5. 每条 `renders_inconsistent:<side>` 一行 `notice.inconsistent`。
6. 每条未计入的重复一行 `notice.uncounted`；每条字节相同的计入重复一行 `notice.byte_identical`。
7. `notice.export_settings`（仅 `regression_detected`）。
8. `notice.declared`（`regression_detected` 与 `no_regression_detected`）。
9. `notice.unmet`、`notice.unevaluated`（各自非空时）；`notice.no_floor`（`floor is None` 时）。
10. `notice.coverage`。

- [ ] **Step 1: 写失败测试**

```python
def test_t_cx355_templates_never_say_clip() -> None:
    for key, text in FULL_SCALE_TEMPLATES.items():
        assert "clip" not in text.replace("clipping_ratio", "").lower(), key
    assert "clip" not in CLIPPING_RATIO_NOTICE.replace("clipping_ratio", "").lower()

def test_t_cx355_regression_lines() -> None:
    lines = full_scale_check_lines(_record(baseline=(0, 0.5), candidate=(2000, 0.995)))
    assert lines[0] == "Samples reaching the full-scale threshold increased."
    assert FULL_SCALE_TEMPLATES["notice.export_settings"] in lines
    assert FULL_SCALE_TEMPLATES["notice.declared"] in lines
    assert lines[-1] == FULL_SCALE_TEMPLATES["notice.coverage"]
    assert "Baseline: 0 samples, peak 0.500000. Candidate: 2000 samples, peak 0.994995." in lines
    assert "Based on 2 consistent baseline render(s) and 2 consistent candidate render(s)." in lines

def test_t_cx353_increase_within_floor_is_not_called_no_increase() -> None:
    lines = full_scale_check_lines(_record(baseline=(2000, 0.995), candidate=(2010, 0.995)))
    assert lines[0] == FULL_SCALE_TEMPLATES["status.no_regression_detected.within_floor"]
    assert "Difference 10 samples; method floor 10 samples." in lines

def test_t_cx358_359_uncounted_identical_and_inconsistent_lines() -> None:
    rec = _record(baseline=(0, 0.5), candidate=(2000, 0.995), repeat_candidate=(2400, 0.995), drop_repeats=None)
    lines = full_scale_check_lines(rec)
    assert "Renders declared deterministic differ on the candidate side: 2000 / 2400 samples." in lines
    assert "Repeat r1 (baseline) is byte-identical to the original file." in lines
    one_side = _record(baseline=(0, 0.5), candidate=(2000, 0.995), drop_repeats="candidate")
    assert "Repeat r1 (candidate) is not counted: not_declared_independent." in full_scale_check_lines(one_side)

def test_t_cx354_decrease_notice_is_on_the_status_line() -> None:
    lines = full_scale_check_lines(_record(baseline=(2000, 0.995), candidate=(0, 0.5)))
    assert lines[0] == "Samples reaching the full-scale threshold decreased: 2000 to 0. No cause is stated."

def test_no_floor_record_lines() -> None:
    lines = full_scale_check_lines(_record(baseline=(0, 0.5), candidate=(2000, 0.995), floor=None))
    assert lines[0].startswith("Descriptive only.")
    assert FULL_SCALE_TEMPLATES["notice.no_floor"] in lines
    assert any(line.startswith("Conditions not evaluated") for line in lines)
```

`tests/app/test_regression_reporting.py` 新增：

```python
def test_t_cx367_report_carries_and_validates_checks() -> None:
    snapshot = _snapshot_with_two_submits()               # 含 2 条检查记录
    report = build_case_report(snapshot, generated_at=NOW)
    assert report.full_scale_checks == snapshot.full_scale_checks
    parsed = RegressionCaseReport.model_validate_json(render_case_json(report))
    assert parsed.full_scale_checks == report.full_scale_checks
    payload = json.loads(render_case_json(report))
    payload["full_scale_checks"][1]["status"] = "regression_detected"
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(payload)

def test_t_cx367_report_rejects_dropped_repeat_and_fabricated_floor() -> None:
    payload = json.loads(render_case_json(build_case_report(_snapshot_with_two_submits(), generated_at=NOW)))
    dropped = copy.deepcopy(payload)
    dropped["full_scale_checks"][1]["repeat_comparison_ids"] = []
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(dropped)       # 第 2 条记录必须恰好带该锚点的前 1 条重复
    forged = copy.deepcopy(payload)
    forged["full_scale_checks"][1]["floor"] = FIXTURE_FLOOR.model_dump(mode="json")
    with pytest.raises(ValidationError):
        RegressionCaseReport.model_validate(forged)        # 下限不在产品登记处

def test_t_cx355_html_shows_current_and_superseded_checks() -> None:
    html = render_case_html(build_case_report(_snapshot_with_two_submits(), generated_at=NOW))
    assert "Full-scale check" in html and "Superseded" in html
    assert FULL_SCALE_TEMPLATES["notice.coverage"] in html and CLIPPING_RATIO_NOTICE in html
    assert "overall" not in html.casefold()                # T-CX360：报告不呈现整体通过，更不呈现为待定
    assert "descriptive_only" in html                      # 现有比较记录自己的状态仍然显示

def test_t_cx368_check_stays_out_of_diagnosis() -> None:
    from signal_diag.agent import diagnosis
    assert "full_scale" not in inspect.getsource(diagnosis)
    assert "FullScale" not in json.dumps(StructuredDiagnosis.model_json_schema())
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。** 测试帮助函数：`_record(**kw)` 是 `evaluate_full_scale_check(check_id="chk_1", anchor=..., repeats=..., floor=kw.pop("floor", FIXTURE_FLOOR), supersedes=None)` 作用于 `eligible(**kw)`；`_snapshot_with_two_submits()` 用 Task 5 的 `_upload` 向不带下限的服务提交一次锚点和一次两侧声明独立的重复，返回快照。

  `validate_regression_case_report_integrity` 对 `full_scale_checks` 的校验：用 `submissions_from_items(comparisons)` 建索引；按报告内顺序处理，对同一锚点的第 k 条记录（k 从 0 起），要求 `anchor_comparison_id` 在报告内且确为锚点、`repeat_comparison_ids` 恰好等于该锚点下按提交顺序的前 k 条重复、`supersedes` 为该锚点的第 k−1 条记录的 `check_id`（k = 0 时为 `None`）；随后以这 k 条重复调用 `validate_full_scale_check_record(..., approved_floors=approved_floors)`。每个锚点的记录数必须等于其重复数加一。

  HTML 新增 “Full-scale check” 区块：每个锚点的最新记录标为当前，较早的标为 “Superseded”；每条记录逐行输出 `full_scale_check_lines`；`CLIPPING_RATIO_NOTICE` 放在现有指标表下方；全部文本经 `_esc`。现有报告不显示整体通过，本任务也不新增。
- [ ] **Step 4: 运行确认通过**；`python -m pytest tests/app -q`。
- [ ] **Step 5: Commit** — `feat(app): fixed wording and report section for the full-scale check`

### Task 7: API 与页面（T-CX370、T-CX355）

**Files:**
- Modify: `src/signal_diag/app/regression_api.py`、`src/signal_diag/app/static/regression.html`、`src/signal_diag/app/static/regression.js`
- Test: `tests/app/test_regression_api.py`、`tests/app/test_regression_ui.py`

**Interfaces:**
- Consumes: `ComparisonUpload.full_scale_declarations`、`RegressionCaseSnapshot.full_scale_checks`、`full_scale_check_lines`。
- Produces: `RegressionComparisonMetadata.full_scale_declarations: FullScaleDeclarations = FullScaleDeclarations()`；案例 JSON 中每条检查记录附带服务端生成的 `lines: list[str]`（页面只显示，不拼接文案）。

- [ ] **Step 1: 写失败测试**（沿用 `tests/app/test_regression_api.py` 现有的 `regression_client` 夹具、`_metadata_bytes(**overrides)`、`_comparison_form`，以及 `tests/app/test_regression_ui.py` 的 `_static_text`；按它们现有的调用方式写，不改它们）

```python
async def test_t_cx370_api_accepts_declarations_and_defaults_unknown(regression_client) -> None:
    body = await _post_comparison(regression_client, _metadata_bytes())
    assert body["comparisons"][0]["full_scale_declarations"]["periodic_test_signal"] == "unknown"
    body = await _post_comparison(regression_client, _metadata_bytes(
        full_scale_declarations={"periodic_test_signal": "yes"}), request_id="r2")
    assert body["comparisons"][-1]["full_scale_declarations"]["periodic_test_signal"] == "yes"
    assert body["full_scale_checks"][-1]["lines"][0].startswith(("Descriptive only.", "Not comparable."))

async def test_t_cx370_api_rejects_unknown_declaration_fields(regression_client) -> None:
    response = await _post_comparison_raw(regression_client, _metadata_bytes(
        full_scale_declarations={"approved": True}))
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_request"

async def test_report_json_has_no_lines(regression_client) -> None:
    ...                                                     # GET report.json：full_scale_checks 各项不含 "lines"

def test_ui_has_declaration_inputs_and_no_wording_literals() -> None:
    html = _static_text("regression.html"); js = _static_text("regression.js")
    for element_id in ("fs-periodic", "fs-baseline-independent", "fs-candidate-independent"):
        assert f'id="{element_id}"' in html
    assert html.count('value="unknown" selected') >= 3
    assert "full_scale_checks" in js and "full_scale_declarations" in js and "lines" in js
    assert "full-scale threshold" not in js.casefold()      # 文案只来自服务端
    assert "overall pass" not in js.casefold()              # 现有断言保持成立
```

`_post_comparison` / `_post_comparison_raw` 是本测试文件内新增的小帮助函数：建案例、用 `_comparison_form` 组装表单并提交，前者返回 JSON、后者返回响应对象。

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。**
  - `RegressionComparisonMetadata` 增加声明字段；`_upload_from_parsed` 把它传入 `ComparisonUpload`。
  - 新增一个 `_snapshot_payload(snapshot) -> dict`：`snapshot.model_dump(mode="json")` 后给 `full_scale_checks` 的每一项加 `lines`。现在直接返回快照的四个端点（建案例、取案例、提交比较、请求建议）全部改走它。`lines` 不进入任何 Pydantic 模型；`report.json` 不带 `lines`。
  - 页面：三个声明各为一个 `<select>`，选项 `yes`/`no`/`unknown`，默认 `unknown`，标签写明 “declared, not verified”。`fs-periodic` 随每次提交发送；两个独立渲染选择只由“作为重复提交”的按钮读取，其它按钮一律发送 `unknown`。页面给出固定说明：只重复一侧时，另一侧重新上传原文件并选 `no`。检查结果区按服务端给的 `lines` 逐行渲染为文本节点（不用 `innerHTML`）。
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: Commit** — `feat(app): declarations input and full-scale check display`

### Task 8: 分层、保全与全量验证（T-CX351、T-CX368、T-CX369）

**Files:**
- Modify: `tests/test_architecture_boundaries.py`
- Create: `docs/REGRESSION_FULL_SCALE_CHECK_OFFLINE_ACCEPTANCE.md`

- [ ] **Step 1: 写失败测试**（加入 `tests/test_architecture_boundaries.py`）

```python
def test_t_cx369_full_scale_layering() -> None:
    assert find_forbidden_imports("dsp", SRC_ROOT / "dsp" / "full_scale.py") == []
    tools = _modules_imported_from(SRC_ROOT / "tools" / "regression_full_scale.py")
    assert not [m for m in tools if m.startswith(("signal_diag.rules", "signal_diag.app", "signal_diag.agent"))]
    rules = _modules_imported_from(SRC_ROOT / "rules" / "full_scale_check.py")
    assert not [m for m in rules if m.startswith(("signal_diag.app", "signal_diag.agent", "signal_diag.dsp"))]

def test_t_cx351_frozen_surfaces_untouched_by_full_scale() -> None:
    changed = set(_git_name_only("386a9b2..HEAD").stdout.splitlines())
    assert not changed & {"src/signal_diag/dsp/clipping.py", "src/signal_diag/tools/contracts.py",
                          "src/signal_diag/tools/service.py", "src/signal_diag/tools/regression_measurement.py",
                          "src/signal_diag/rules/regression.py", "src/signal_diag/agent/diagnosis.py"}

def test_t_cx363_no_floor_values_under_src() -> None:
    from signal_diag.rules.full_scale_check import PRODUCT_APPROVED_FULL_SCALE_FLOORS
    assert PRODUCT_APPROVED_FULL_SCALE_FLOORS == ()
    hits = []
    for path in SRC_ROOT.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "FullScaleMethodFloor":
                hits.append(str(path))
    assert hits == []
```

（`find_forbidden_imports` 的实际签名以该文件现有定义为准；基线提交号在执行时替换为当时核定的完整 SHA。）

- [ ] **Step 2: 运行**，确认三条测试通过；allowlist 已在 Task 1–3 各自追加，这里不再改。
- [ ] **Step 3: 全量验证**，逐条运行并保留输出：

```bash
python -m pytest -q -rxXs -p no:cacheprovider
python -m ruff check --no-cache src tests scripts
python -m mypy --no-incremental src
python scripts/verify_phase5_wheel.py
git diff --check 386a9b2..HEAD
```

预期：全部通过；`git diff --check` 无输出。

- [ ] **Step 4: 写离线验收记录** `docs/REGRESSION_FULL_SCALE_CHECK_OFFLINE_ACCEPTANCE.md`：基线与 tip 提交号；上面五条命令的结果；T-CX349–T-CX370 各自对应的测试函数名；一段明确说明——产品不带下限记录，产品输出无判定；夹具数值不是容差；未运行表征、未调用 RealLLM；本记录不构成产品收益证据。不得有行尾空格。
- [ ] **Step 5: Commit** — `test: layering and preservation gates for the full-scale check; offline acceptance record`

---

## T-CX 覆盖对照

| ID | Task |
|---|---|
| T-CX349 | 1、2 |
| T-CX350 | 4 |
| T-CX351 | 2、4、5、8 |
| T-CX352、353 | 4 |
| T-CX354 | 4、6 |
| T-CX355 | 6、7 |
| T-CX356、357、359、361、362、366 | 4 |
| T-CX358、365 | 3 |
| T-CX360 | 3、5、6 |
| T-CX363 | 4、5、8 |
| T-CX364 | 5 |
| T-CX367 | 4、6 |
| T-CX368 | 6、8 |
| T-CX369 | 1–3、8 |
| T-CX370 | 3、5、7 |

## 本计划作出、需操作员知悉的落点决定

合同 §23 没有规定到这一层的地方，本计划做了如下选择；任何一条不同意，改计划即可，不需要改合同：

1. **下限记录的具体字段。** 合同只写“经审阅的形式与取值”。本计划定为两个临界区边距、一个可选的最小计入数、两个可选的差值下限。表征得出的形式若超出它，届时修订模型。
2. **检查记录内保存完整的下限记录**（合同写的是“下限身份或空”）。这样报告在解析边界可以独立重算；下限记录自身带摘要。
3. **产品 profile 守卫的位置。** 放在 `build_regression_service()` 内调用 `assert_product_profile_allowed`；`RegressionWorkbenchService` 构造器不拒绝，以免破坏现有的夹具注入测试。
4. **报告的 `schema_version` 不变。** 新增字段带默认值。
5. **文案语言为英文**，与现有工作台页面一致；文案表即权威文本。
6. **事实里多存一个 `wav_sha256`**，用于标记与锚点文件字节相同的计入重复。
7. **`transition` 与 `count_difference` 在不合格时也给出**（只要两侧事实存在），供展示；状态仍由资格决定。
8. **事实由 `app/` 在 `measure_output` 返回后、仓库清空前调用 `tools/` 适配函数取得**，合同 §23.2 写的是“在 `measure_output` 期间”。这样 `tools/regression_measurement.py` 一行不改。
9. **校验函数多两个参数。** 合同写的是 `validate_full_scale_check_record(record)`；本计划由调用方传入锚点与重复，锚点解析在报告层完成。
10. **报告校验只接受产品登记处里的下限记录。** 登记处现在为空，所以任何带下限的报告都解析失败；测试显式传入夹具下限。这是对第 2 条的补充，用来落实合同“客户端不能上传下限或声称已批准”。
11. **两个差值下限都设置时须同时超过**才算超过下限。
12. **摘要不自洽的下限记录按没有下限处理。**
13. **“是”侧临界区是两个条件取或**（峰值在阈值上方边距内，或计入数低于最小计入数）。
14. **新增条件码 `critical_zone_reviewed`**，只出现在未评估清单里，表示临界区中由表征给出的那部分无法评估。
15. **固定最低要求的步长对 32 位文件取 2⁻²⁴**。合同写的是较粗位深的一个量化步长；样本以 float32 保存，更细的步长没有意义。这比合同字面更保守。
16. **第 3 条的守卫目前不会被触发**：产品构造函数传入的 profile 恒为 `None`。T-CX360 的“服务构造时拒绝”只在函数层面成立。
17. **新增一句状态文案**：增量未超过下限时不说“未发现增加”，而说增量不高于方法下限。

## 不在本计划内

第一层表征的实现与运行；任何下限、临界区或批准域数值；次满刻度平顶削波的判定；`observed_variable` 阻断的修订；THD 判定；复测 planner 的输入变更；RealLLM；seal；案例持久化。
