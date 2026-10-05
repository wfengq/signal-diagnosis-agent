# S1 回归满刻度检查：第一层表征 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task, only after operator authorization. Cursor 负责全部实现以及审阅后发现问题的修复；Claude Code 负责设计与独立审阅。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现第一层（方法灵敏度下限）表征工具：生成冻结清单中的材料，经完整工具路径测量，按预先固定的定义计分、拟合候选形式，并在冻结之后才允许运行验证侧。本计划只到“工具就绪、清单可生成”为止；正式的校准运行、形式与取值冻结、验证运行、下限审批各自另行授权（见“运行流程”）。

**Architecture:** 新包 `src/signal_diag/evaluation/full_scale_characterization/`。它位于评测层，只导入 `signal/`、`dsp/`、`tools/`，不导入 `rules/`、`agent/`、`app/`；产品代码不得导入它。材料在本包内用 NumPy 合成，经本包自带的整数 PCM 编码器写成 WAV 字节，再走 `load_wav_bytes → InputIdentity → measure_output → measure_full_scale_facts`，与产品工作台同一条路径。产物写入 `docs/evaluations/v0_3/full_scale_characterization/round_1/`，每个文件只写一次。

**Tech Stack:** 现有 Python 3.11/3.12、NumPy、Pydantic 2。不新增依赖。

**Spec:** 表征设计 `docs/superpowers/specs/2026-10-05-s1-regression-layer1-characterization-materials-scoring-design.md`（§10、§11 优先，其次 §9，再次 §2–§8）；削波语义设计 `docs/superpowers/specs/2026-10-05-s1-regression-clipping-comparison-semantics-design.md` §12–§14；合同 `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §23.4、§23.7；探查 `docs/OQ020_FULL_TOOLPATH_PROBE_2026-10-05.md`；已合并实现 PR #41（`0770514`）。

**Status:** 修订 1（2026-10-05），未经独立审阅。计划本身不授权实施；实施授权只覆盖 Task 0–9，不覆盖任何正式运行。
**Read-only baseline:** `0770514` on `codex/v0.2-real-world-validation`。执行前在当时基线上重新核对本计划引用的文件、接口与空闲测试 ID。

## Global Constraints

- 不修改 `src/signal_diag/` 下 `signal/`、`dsp/`、`tools/`、`rules/`、`knowledge/`、`agent/`、`app/` 的任何文件（产品树哈希因此不变，不需要追加代码身份登记行）。唯一的例外是 `tests/test_architecture_boundaries.py` 的前缀登记。
- 不修改冻结 V0.2 §§1–64、§22、§23 合同文本、D043、已合并的满刻度检查实现、已封存的评测与 Demo 资产。
- 不在 `src/` 下写入任何下限、临界区或批准域数值。拟合出的数值只出现在运行产物里，且不被产品加载。`PRODUCT_APPROVED_FULL_SCALE_FLOORS` 保持为空。
- 实施 PR 内不运行正式清单（round_1）的任何测量。测试只用 `tests/` 下的微型清单。
- 数值只来自确定性测量；LLM 不参与生成、挑选、拟合或解释。不调用 RealLLM，不 seal。
- 每对只施加一项扰动（组合扰动仅验证侧）；随机性全部来自清单里记录的种子。
- 验证侧材料在冻结记录存在之前不得生成、测量或读取（代码强制，见 Task 7）。
- 计划内的每一对都留在分母里：生成失败、测量无效、被拒绝比较单独计数。

---

## A. 运行前须批准的决定

表征设计 §7 有五项未勾选。本计划把它们落成下面的 B 节清单。**操作员批准本计划即批准 B 节与 C 节**；Task 0 把批准结果写回表征设计 §7。批准后再改任何一项，按表征设计 §1 固定规则 2 处理（记录理由、作废已看过的验证结果）。

本计划另作出以下落点决定，需操作员逐条同意：

1. **基础材料加起始相位轴（建议采纳）。** 设计里的基础材料只用相位 0，起始相位只作为敏感度扰动 P3。但状态翻转的位置取决于采样相位（语义设计 §12.5、§14）；100 Hz、48 kHz 时每周期恰好 480 个样本，所有周期的采样相位相同，只用相位 0 会让临界区的拟合只看到一种采样相位。建议：M2/M11、M3、M5 的基础材料加相位轴，校准 {0, 1.0, 2.0} rad，验证留出 {0.5, 3.0} rad；P3 不变。规模约增至三倍。不采纳则按设计原样只用相位 0，并在报告里披露。
2. **临界区候选形式增加 K4（§11 要求）。** 表征设计 §11 要求候选形式能表达对每周期样本数 N 的依赖，§9.2 的 K1–K3 都不能。新增：
   - **K4：** 形式同 K2，但把峰值换成“两样本等效电平” `e = peak_abs · cos(π / N)`：`thr − zb ≤ e ≤ thr + za` 即在区内。依据：连续两个样本都过阈值，要求跨峰两样本中较低者不低于阈值，其上界约为 `A · cos(π/N)`；翻转点约在 `thr / cos(π/N)`（§11 实测吻合）。N 用材料的生成参数计算（产品里来自用户声明的基频，报告须披露这一差别，见设计 §10.6）。
   - K4 若被选中，`FullScaleMethodFloor` 现有字段表达不了，下限审批时须修订模型与合同 §23.4 的取值形式（PR #41 计划落点决定 1 已预见）。表征本身不受影响。
3. **F3（按工况分别取值）的工况必须是可观测事实。** 产品看不到“材料族”。F3 的分工况条件只能写在产品可得的量上：每周期样本数 N、范围内周期数、较粗位深、计入数。按材料族分工况的 F3 不可选。
4. **分析范围长度的留出方式。** 设计 §5 说只按基频和削波程度留出，§8.2 / §10.3 又给范围长度列了留出值。本计划定为：校准侧来源组只在校准长度上运行；验证侧来源组在校准长度与留出长度上都运行。来源组键不含范围长度。
5. **临界区拟合按“两侧都在区内”求最小边距。** 产品规则是任一侧在区内即不判定，所以“至少一侧在区内”就够；但那样的最小解不唯一。本计划取“翻转对的两侧都须在区内”，最小解唯一，结果更保守（区更宽、覆盖率更低）。验证侧仍按产品规则判（任一侧在区内即排除）。
6. **32 位文件的 P7 步长取 2⁻²⁴**，与 PR #41 落点决定 15 一致：32 位码值上偏移 128 个码。
7. **产物存放与身份记录**（设计 §7 最后一项，原定实施授权时确定）：见 D 节与 Task 7。逐对结果以确定性 gzip（`mtime=0`）的 JSONL 提交入库；若压缩后单文件超过 50 MB，停下由操作员决定是否只入库摘要与哈希。
8. **M10 白噪声不进表征人口**（设计 §9.4）。它只用于实施验收时检验资格门，本计划不涉及。
9. **测试 ID。** 新登记 T-CX371–T-CX380（仅定义，Task 0），对应关系见文末。

## B. 冻结清单（候选数值，均为材料取值，不是容差）

### B.1 共用轴

| 轴 | 校准侧 | 验证侧留出 | 依据 |
|---|---|---|---|
| 采样率 | 44100、48000 | 不留出 | 设计 §8.2 |
| 基频 f0 | 100、440、880、2000、4000、8000 | 220、3000（内插）；50、997、12000（外推） | §10.3 |
| 文件时长 | 2.0 s | 同左 | §8.2 |
| 分析范围长度 | 2.0、0.1、0.01、0.005 s | 1.0、0.02（内插）；0.002（外推） | §10.3；用法见 A.4 |
| 起始相位（A.1 采纳时） | 0、1.0、2.0 rad | 0.5、3.0 rad | A.1 |
| 种子 | 每格 5 个：`1001–1005` | 每格 5 个：`2001–2005` | §8.2 |
| 满刻度阈值 | 0.99（唯一配置身份） | 同左 | §7 已定 |

分析范围固定为 `TimeRange(start_s=0.0, end_s=L)`；L = 2.0 时等于整个文件。

### B.2 材料族

“峰值”指量化前的正弦幅度。“削波深度” d = 削波电平 ÷ 削波前峰值，削波前幅度 = 电平 ÷ d。

| 族 | 校准侧 | 验证侧留出 | 角色 |
|---|---|---|---|
| M1 无削波 | 幅度 0.05、0.5、0.9 | 0.2、0.01 | 反例：计入数必须为 0 |
| M2/M11 近阈值正弦 | 峰值 0.98、0.989、0.9899、0.99、0.9901、0.9905、0.991、0.992、0.993、0.994、0.995、0.9975、1.0 | 0.9897、0.9915、0.9925、0.996（内插）；0.97（外推） | 主要工况：临界区 |
| M3 满刻度硬削波 | 电平 0.9901、0.995、1.0；深度 0.999、0.99、0.9、0.7 | 电平 0.991、0.99；深度 0.95、0.9999、0.5 | 主要工况：样本数下限 |
| M4 次满刻度平顶 | 电平 0.5、0.9；深度同 M3 | 电平 0.7、0.98、0.1；深度同 M3 留出 | 反例：计入数必须为 0 |
| M5 削波叠加谐波 | 谐波 {2:0.1}、{3:0.1}；电平 0.995、0.9；深度 0.99、0.9 | 谐波 {2:0.3}；深度 0.95 | 电平 ≥ 阈值者为主要工况，其余为反例 |
| M6 有谐波无削波 | 基波 0.5；{3:0.3}；奇次 3、5、7 按 1/n | 奇次到 15 按 1/n | 反例 |
| M7 | 不设取值；标记“每个峰过阈值的样本数 1–3 个”的格 | 同左 | 标记 |
| M8 | 由范围长度轴覆盖 | 同左 | — |
| M9 双声道 | 左 M1(0.5) + 右 M3(电平 0.995、深度 0.9)，及左右互换 | 左 M4(电平 0.9、深度 0.9) + 右 M3(同左) | 声道隔离 |

来源组键 = 族 + f0 + 采样率 + 削波程度（M1 为幅度，M2/M11 为峰值，M3/M4/M5 为 (电平, 深度[, 谐波])，M6 为谐波集，M9 为组合）+ 起始相位（A.1 采纳时）。f0、削波程度或相位任一取留出值的组进入验证侧，其余进入校准侧。改文件名、改种子、改扰动幅度不构成新组。

### B.3 空对

**容忍范围内（定下限与临界区；硬条件只对这一类）：**

| 代号 | 两侧 | 位深 |
|---|---|---|
| P0 | 同一编码，字节相同 | 16、24、32 各一对 |
| P4 | 舍入编码，位深不同：32↔24、32↔16、24↔16 | — |
| P7a | 舍入 ↔ 全部样本远离零偏一步 | 16、24、32 |
| P7b | 舍入 ↔ 全部样本向零偏一步 | 16、24、32 |
| P7c | 舍入 ↔ 截断（向零取整） | 16、24、32 |
| P7d | 舍入 ↔ 每个样本以固定种子随机 ±1 步 | 16、24、32，每格 5 个种子 |

“一步”在 16、24 位为一个码值，在 32 位为 128 个码值（A.6）。偏移后的码值截到合法范围内。

**敏感度（只披露，不进入下限，不计入通过条件）：**

| 代号 | 校准侧 | 验证侧留出 |
|---|---|---|
| P1 文件级样本偏移 | 1、3、37 | 2、101 |
| P3 起始相位 | 0.1、1.0、2.0 rad | 0.5、3.0 rad |
| P5 输出增益差（削波之后） | 相对 ±1e-5、±1e-4、±1e-3、±5e-3 | ±3e-5、±3e-4；±1e-2 |
| P6 单侧叠加噪声（削波之后） | RMS 1e-5、1e-4、1e-3 | 3e-5、3e-4；3e-3 |
| P8 8 位（域外） | 16↔8、32↔8 | 同左 |
| 组合（仅验证侧） | — | P1(1)+P6(1e-4)；P4(32↔16)+P5(1e-4)；两侧各加不同种子噪声 1e-4 |

敏感度空对的基础编码为 16 位舍入（P8 除外）。

### B.4 变化对（两侧同位深，16、24、32 各一份）

| 类型 | 校准侧 | 验证侧 |
|---|---|---|
| 起始（否 → 是） | 旧：M1 幅度 0.9；新：同一波形放大后在 0.995 削波，深度 0.9999、0.999、0.99、0.9 | 削波电平改为 0.9901，深度同左 |
| 加重（是 → 是） | 以 M3 各组为旧版；新版削波电平不变，削波前幅度相对增加 1e-4、1e-3、1e-2、5e-2、1e-1 | 同左 |
| 盲区（仅披露） | 不进校准 | 次满刻度：电平 0.9、0.98，深度 0.99 → 0.9；单样本：997 Hz、电平 0.9905、削波前幅度 0.991 |

### B.5 规模估算（推算，非实测）

采纳 A.1 时，校准侧约 1,400 份材料 × 4 个范围长度 × 约 60 对（容忍范围内约 30、敏感度约 30）≈ 33 万对；按文件与范围去重后约 31 万次 `measure_output`。不采纳 A.1 约为四成（相位轴只加在 M2/M11、M3、M5 上）。验证侧同一量级。每次测量是对 2 秒以内音频的确定性计算，无模型调用。精确数由 Task 3 的清单生成器给出并写入清单；操作员批准清单哈希时一并批准对数。

## C. 计分与拟合定义（写死，运行后不改）

### C.1 每对记录

清单字段（族、来源组、侧、扰动代号与档位、种子、两侧编码描述、范围长度、f0、采样率、N = sr/f0、范围内周期数、M7 标记），加上每侧：`counted_samples`、`over_threshold_uncounted`、`state`、`peak_abs`、`analyzed_samples`、`pcm_bit_depth`、`clipping_ratio`、`clipped_samples`、`full_scale_detected`、`flat_top_detected`、`clipping_mechanism`、`wav_sha256`、`bundle_digest`、`facts_digest`。对级字段：`count_diff = 新 − 旧`、`ratio_diff`、`flip = state 不同`、终态（`measured` / `rejected` / `invalid` / `generation_failed`）与原因码。

### C.2 健全性检查（任何一条失败即中止该轮，不出报告）

- P0 的任一对差值非零，或两侧 `wav_sha256` 不同。
- 交叉核对（设计 §10.6）：对每份材料的舍入编码，直接用 `count_full_scale_samples` 在阈值 `thr − step` 与 `thr + step` 下各计一次，二者之差须 ≥ 该材料全部容忍范围内空对的 `|count_diff|`。
- 事实与测量包不一致：对每一侧调用 `verify_full_scale_facts` 失败。

### C.3 固定最低要求

“否”侧 `peak_abs ≥ thr − step` 即在区内（§23.4）。`step` 取两侧较粗位深的步长（16 位 2⁻¹⁵，24 位 2⁻²³，32 位 2⁻²⁴）。报告分别给出应用前与应用后的翻转次数（§10.6）。

### C.4 候选形式（只能从中选）

- **批准域 D1：** `N ≥ n_min` 且 `范围内周期数 ≥ p_min`。候选值为校准网格中实际出现的 N 与周期数的去重值，逐一列举。
- **临界区：** K1、K2、K3、K4（A.2）、K0。每个候选都与固定最低要求取或。
- **样本数下限：** F1（比例差）、F2（样本数差）、F3（A.3 约束下按可观测条件分段取 F1 或 F2）、F0。
- 某个组合在校准侧无法满足全覆盖时，结论为该组合不成立；不得临时发明新形式。

### C.5 拟合算法（确定性，由工具输出，审阅者只选择）

对每个候选批准域 `(n_min, p_min)`，只用域内、容忍范围内的校准侧已测量对：

1. **临界区：** 对每种 K 形式，求使全部翻转对**两侧都在区内**的最小参数（A.5）。翻转对的每一侧都是一个须被覆盖的点。
   - K1：`z = max |peak − thr|`。
   - K2：`zb` = 阈值下方各点的最大距离，`za` = 阈值上方各点的最大距离（没有点的一侧取 0）。
   - K3：门槛 `c` 的候选值为翻转侧中“是”侧 `counted_samples + 1` 的去重值，另加 0（即不用门槛）。对每个候选 `c`，计入数低于 `c` 的“是”侧视为已覆盖，其余点按 K2 求 `(zb, za)`。输出全部 `(c, zb, za)` 行，由审阅者选一行。
   - K4：同 K2，以 `e = peak · cos(π/N)` 代替 `peak`。
   - 某形式求得的区覆盖了域内全部容忍范围内的对（覆盖率为 0）时，该形式记为 K0。
2. **样本数下限：** 在两侧都为“是”、两侧都在所选临界区外的对上，F1 = `max |ratio_diff|`，F2 = `max |count_diff|`，不加余量。F3 的分段边界只能取 C.4 中 N 与周期数的候选值。
3. **输出：** 每个 (域, K, F) 组合的参数、域内覆盖率（适用对 ÷ 计划对）、按族覆盖率、校准侧变化对的检出情况（按档）、被排除的对及原因。工具不排名、不推荐。

### C.6 验证侧计数（冻结后原样套用，不调整）

只对冻结记录中的 (域, K, F)：

- **硬条件一：** 域内、容忍范围内的适用空对中，两侧都在区外而状态翻转的对数，须为 0。
- **硬条件二：** 两侧都为“是”且都在区外的适用空对中，差值超过下限（严格大于）的对数，须为 0。
- **强制披露：** 域外的格；敏感度空对的差值分布与翻转数；盲区变化对；按族覆盖率；起始变化对在区外被判为起始的档与区内拿不到判定的对数；加重变化对按档被下限盖掉的对数与最小可检出变化；校准侧未见过的翻转。

任一硬条件不满足，该轮结论为未通过，产品保持纯描述性；不得缩小人口、调整数值或改准则后重算（设计 §7 退出条款）。

## D. 文件结构

| 文件 | 责任 |
|---|---|
| Create `src/signal_diag/evaluation/full_scale_characterization/__init__.py` | 包说明 |
| Create `.../models.py` | 清单、对、记录、冻结记录、报告的 Pydantic 模型（`frozen=True, extra="forbid"`） |
| Create `.../constants.py` | B 节的全部取值（唯一来源） |
| Create `.../synthesis.py` | 材料波形合成（float64） |
| Create `.../pcm.py` | 整数 PCM WAV 编码（16/24/32/8 位；舍入、截断、同向偏移、随机偏移） |
| Create `.../manifest.py` | 来源组、划分、对的枚举，规范 JSON 与哈希 |
| Create `.../executor.py` | 完整工具路径测量、按文件缓存、终态 |
| Create `.../checks.py` | C.2 健全性检查 |
| Create `.../fitting.py` | C.5 拟合 |
| Create `.../validation.py` | C.6 计数 |
| Create `.../reporting.py` | 校准与验证报告（JSON + Markdown） |
| Create `.../store.py` | 只写一次的产物目录与哈希登记 |
| Create `.../__main__.py` | 命令行入口 |
| Modify `tests/test_architecture_boundaries.py` | `_V03_ADDITIVE_PATH_PREFIXES` 追加 `src/signal_diag/evaluation/full_scale_characterization/` |
| Create `tests/evaluation/full_scale_characterization/` | 新测试（含 `mini_manifest.py` 微型清单） |
| Modify `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | 登记 T-CX371–T-CX380（Task 0） |
| Modify 表征设计 §7 | 勾选并引用本计划 B、C 节（Task 0） |

产物目录（运行阶段才创建）：

```text
docs/evaluations/v0_3/full_scale_characterization/round_1/
  manifest.json              # Task 3 生成；批准时记录其 sha256
  identity.json              # 代码与配置身份
  calibration_results.jsonl.gz
  calibration_report.{json,md}
  freeze_record.json         # 选定的 (域, K, F) 与数值、理由、上游哈希
  validation_results.jsonl.gz
  validation_report.{json,md}
  SHA256SUMS
```

`identity.json` 记录：`MEASUREMENT_VERSION`、`FULL_SCALE_FACTS_VERSION`、阈值 0.99、最少连续 2、`analyze_clipping` 的平顶默认值、以下文件的 sha256：`dsp/full_scale.py`、`dsp/clipping.py`、`tools/regression_full_scale.py`、`tools/regression_measurement.py`、`tools/service.py`、`signal/wav.py`；本包全部文件的合并摘要；`contextual_product_tree_sha256()`；Git 提交号。

---

### Task 0: 文档登记（仅定义）

- [ ] 在 `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` 登记 T-CX371–T-CX380（定义见文末），索引行写明“definitions; characterization runs and floor approval gated”。
- [ ] 在表征设计 §7 勾选五项，每项写“按实施计划 `2026-10-05-s1-regression-layer1-characterization.md` B/C 节，操作员 <日期> 批准”，并逐条记录 A 节落点决定的采纳情况。
- [ ] Commit — `docs: register layer-1 characterization test IDs and record §7 decisions`

### Task 1: 包骨架与分层（T-CX371）

- [ ] 写失败测试 `tests/evaluation/full_scale_characterization/test_layering.py`：

```python
def test_t_cx371_package_imports_only_lower_layers() -> None:
    for path in PACKAGE.rglob("*.py"):
        mods = _modules_imported_from(path)
        assert not [m for m in mods if m.startswith(
            ("signal_diag.rules", "signal_diag.agent", "signal_diag.app", "signal_diag.knowledge"))], path

def test_t_cx371_product_never_imports_characterization() -> None:
    for d in ("signal", "dsp", "tools", "rules", "knowledge", "agent", "app"):
        for path in (SRC_ROOT / d).rglob("*.py"):
            assert "full_scale_characterization" not in path.read_text("utf-8"), path

def test_t_cx371_no_floor_values_under_src() -> None:
    from signal_diag.rules.full_scale_check import PRODUCT_APPROVED_FULL_SCALE_FLOORS
    assert PRODUCT_APPROVED_FULL_SCALE_FLOORS == ()
```

- [ ] 追加前缀到 `_V03_ADDITIVE_PATH_PREFIXES`；创建空包。
- [ ] Commit — `feat(eval): full-scale characterization package skeleton (T-CX371)`

### Task 2: 合成与整数 PCM 编码（T-CX372）

**Interfaces:**

```python
def sine(*, f0: float, sr: int, duration_s: float, amplitude: float, phase_rad: float) -> np.ndarray
def clipped_sine(*, f0, sr, duration_s, level: float, depth: float, phase_rad, harmonics: Mapping[int, float] | None = None) -> np.ndarray
def harmonic_sine(*, f0, sr, duration_s, fundamental: float, harmonics: Mapping[int, float], phase_rad) -> np.ndarray
def encode_pcm_wav(channels: Sequence[np.ndarray], *, sr: int, bits: Literal[8, 16, 24, 32],
                   rounding: Literal["round", "trunc", "away_one_step", "toward_one_step", "random_one_step"] = "round",
                   seed: int | None = None) -> bytes
```

码值约定与加载器一致：16 位码值 = `round(x · 32768)` 截到 `[-32768, 32767]`，24 位 `2^23`，32 位 `2^31`，8 位为无符号偏置 128。`away_one_step` 在舍入码值上按符号远离零加一步（零码值不动），`toward_one_step` 向零减一步，`random_one_step` 以 `numpy.random.default_rng(seed)` 逐样本加 ±1 步；32 位的一步为 128 个码值。

- [ ] 写失败测试：
  - 对每个位深与舍入方式，`load_wav_bytes(encode_pcm_wav(...))` 解码出的码值与预期码值逐样本相等（由解码样本乘以缩放因子还原）。
  - 偏一步后与舍入码值之差的绝对值逐样本 ≤ 一步，且 `away`/`toward` 方向全部一致。
  - 相同种子两次编码字节相同；不同种子不同。
  - `clipped_sine` 的削波前幅度 = `level / depth`，输出绝对值 ≤ `level`。
- [ ] 实现；不得调用 `app/pcm_wav.py`。
- [ ] Commit — `feat(eval): characterization waveform synthesis and integer PCM encoder (T-CX372)`

### Task 3: 清单生成（T-CX373、T-CX374）

**Interfaces:** `build_manifest(constants=ROUND_1, *, include_phase_axis: bool) -> Manifest`；`manifest_sha256(m) -> str`（规范 JSON：键排序、无空白、`allow_nan=False`）。`Manifest` 含 `round_id`、`constants_digest`、`source_groups`（键、侧）、`pairs`（每对的完整生成描述，不含任何测量值）、各侧与各族的计划对数。

- [ ] 写失败测试（用 `ROUND_1` 与微型常量各测一次）：
  - T-CX373：同一常量两次生成的哈希相同；`constants.py` 任一取值改变则哈希改变。
  - T-CX373：每对只含一项扰动（组合扰动只出现在验证侧）；P7/P6/P5 的种子来自该侧的种子集合，两侧种子不重叠。
  - T-CX374：一个来源组的全部对只落在一侧；任一留出值只出现在验证侧；校准侧只出现校准长度；改文件名、种子、扰动幅度不产生新组键。
  - T-CX374：验证侧包含每个材料族至少一个组、全部组合扰动与全部盲区变化对；校准侧不含盲区与组合。
- [ ] 实现；命令 `python -m signal_diag.evaluation.full_scale_characterization manifest --round round_1 --out <dir>` 打印各侧、各族、各扰动的计划对数。
- [ ] Commit — `feat(eval): characterization manifest and leakage-safe split (T-CX373, T-CX374)`

### Task 4: 完整工具路径执行器（T-CX375）

**Interfaces:** `measure_pair(pair, *, cache) -> PairRecord`。每侧：合成 → `encode_pcm_wav` → `load_wav_bytes` → `InMemorySignalRepository` → `InputIdentity` → `measure_output`（`MeasurementSelection(clipping=ClippingInput(channel=..., time_range=..., full_scale_threshold=0.99), harmonic=HarmonicDistortionInput(channel=..., time_range=...))`）→ `measure_full_scale_facts` → `verify_full_scale_facts`。缓存键为 `(wav_sha256, channel, time_range)`。谐波结果不参与计分，只记录状态。

- [ ] 写失败测试：
  - 记录里的事实与直接调用 `measure_full_scale_facts` 得到的事实相等；`counted_samples` 与 `count_full_scale_samples` 对解码样本的结果相等。
  - 削波工具失败或无结果时终态为 `invalid`，原因码写明；合成或编码抛错时为 `generation_failed`；两种都留在分母里。
  - M9：左声道记录与同参数单声道材料的记录在事实上相等（声道隔离）。
  - 相同输入两次执行，记录逐字节相同。
- [ ] 实现。
- [ ] Commit — `feat(eval): full tool-path executor for characterization pairs (T-CX375)`

### Task 5: 健全性检查（T-CX376）

- [ ] 写失败测试：人为构造 P0 差值非零的记录、交叉核对不满足的记录、事实摘要不符的记录，各自导致 `SanityAbort`，异常信息写明对的标识；全部满足时通过。
- [ ] 实现 C.2。
- [ ] Commit — `feat(eval): characterization sanity aborts (T-CX376)`

### Task 6: 校准拟合与报告（T-CX377）

- [ ] 写失败测试（用手工构造的记录，数值只为验证逻辑）：
  - K1/K2/K4 的最小参数与手算一致；K3 输出全部候选 `c` 行且每行与手算一致；“两侧都在区内”规则生效；覆盖率为 0 时记为 K0。
  - F1/F2 等于适用对的最大差值，不加余量；只取两侧都为“是”且都在区外的对。
  - F3 的分段边界只取候选 N 与周期数；按材料族分段的输入被拒绝。
  - 固定最低要求应用前后的翻转数分别给出。
  - 拟合函数的输入类型只接受校准侧记录；传入任何验证侧记录抛错。
  - 报告列出所有 (域, K, F) 组合，不含排名、推荐或“通过”字样。
- [ ] 实现 C.4–C.5 与校准报告。
- [ ] Commit — `feat(eval): calibration fitting over pre-listed forms (T-CX377)`

### Task 7: 冻结记录与只写一次（T-CX378）

**Interfaces:** `FreezeRecord(round_id, manifest_sha256, identity_sha256, calibration_results_sha256, calibration_report_sha256, domain, zone_form, zone_params, floor_form, floor_params, rationale, approved_by, approved_at, digest)`。

- [ ] 写失败测试：
  - `store` 对已存在的产物文件拒绝写入；`SHA256SUMS` 与文件一致。
  - 冻结记录的上游哈希与磁盘文件不符时拒绝；所选形式不在 C.4 列表中时拒绝；参数不等于拟合输出中对应组合的值时拒绝（冻结只能“选”，不能“改”）。
  - 没有有效冻结记录时，生成或测量任何验证侧对都抛错；`identity.json` 与当前代码身份不一致时，校准与验证都拒绝运行。
- [ ] 实现。
- [ ] Commit — `feat(eval): freeze record and write-once characterization store (T-CX378)`

### Task 8: 验证计数与报告（T-CX379）

- [ ] 写失败测试（手工记录）：两条硬条件各有一例越限时结论为未通过；任一侧在区内的翻转对被排除且计入排除原因；最小可检出变化按档计算；盲区与敏感度只出现在披露区；报告不含任何会被读成产品判定的措辞（“regression detected”“通过下限”等）。
- [ ] 实现 C.6 与验证报告。
- [ ] Commit — `feat(eval): validation counting and report (T-CX379)`

### Task 9: 命令行、端到端微型运行与离线验收（T-CX380）

- [ ] 命令：`manifest`、`calibrate`、`report-calibration`、`freeze`、`validate`、`report-validation`，每个都校验上游产物哈希。
- [ ] 写测试：在临时目录用微型清单（2 个来源组、各 1 个范围长度）跑完整六步，产物齐全、哈希一致；重跑同一步被拒绝；第二次从头跑出的全部产物逐字节相同。
- [ ] 全量验证：

```bash
python -m pytest -q -rxXs -p no:cacheprovider
python -m ruff check --no-cache src tests scripts
python -m mypy --no-incremental src
git diff --check 0770514..HEAD
```

- [ ] 写 `docs/REGRESSION_LAYER1_CHARACTERIZATION_TOOL_OFFLINE_ACCEPTANCE.md`：基线与 tip；上述命令输出；T-CX371–T-CX380 对应测试名；`manifest` 命令对 `round_1` 打印的计划对数（只生成清单、不测量）；明确说明未运行任何正式测量、未产生任何下限数值。
- [ ] Commit — `test: characterization tool end-to-end on a mini manifest; offline acceptance`

---

## E. 运行流程（每一步单独授权，本计划不授权）

| 步 | 内容 | 产物 | 授权 |
|---|---|---|---|
| R0 | 生成 `round_1` 清单；操作员审阅对数并批准其 sha256 | `manifest.json`、`identity.json` | 清单批准 |
| R1 | 校准运行；健全性检查；校准报告 | `calibration_*` | 校准运行授权 |
| R2 | 审阅者从拟合输出中选定 (域, K, F) 并写理由；不得查看任何验证侧数据 | `freeze_record.json` | 形式与取值冻结批准 |
| R3 | 验证运行与报告 | `validation_*` | 验证运行授权 |
| R4 | 独立审阅；决定 OQ-021；若通过，起草下限记录（含 K4 时先修订模型与 §23.4 形式） | 审阅包 | 下限审批（§23.7 第 4 步） |

任一步未通过：产品继续纯描述性，旧产物保留；要再试一次须起 `round_2`，用新的验证来源组。

## F. 不在本计划内

正式清单的任何测量；任何下限、临界区或批准域数值的选择与批准；`FullScaleMethodFloor` 的模型修订；产品登记处的任何改动；OQ-021 的实现；次满刻度平顶判定；`observed_variable` 阻断的修订；THD；RealLLM；seal。

## T-CX 定义（Task 0 登记）

| ID | 定义 |
|---|---|
| T-CX371 | 表征包只导入下层；产品代码不导入表征包；产品登记处仍为空 |
| T-CX372 | 整数 PCM 编码与加载器码值一致；一步扰动逐样本不超过一步且方向一致；种子决定字节 |
| T-CX373 | 清单确定且可哈希；每对只含一项扰动；两侧种子不重叠 |
| T-CX374 | 按来源组划分；留出值只在验证侧；防泄漏规则成立 |
| T-CX375 | 执行器走完整工具路径；事实与产品路径一致；终态与分母完整；声道隔离；结果确定 |
| T-CX376 | P0、交叉核对与事实校验任一失败即中止 |
| T-CX377 | 拟合只在预列形式中求最小参数；不加余量；不读验证侧；报告不排名 |
| T-CX378 | 冻结只能选不能改；产物只写一次；无冻结记录不得触碰验证侧 |
| T-CX379 | 验证只计数；两条硬条件与强制披露齐全；无产品判定措辞 |
| T-CX380 | 端到端六步在微型清单上可重现，逐字节一致 |
