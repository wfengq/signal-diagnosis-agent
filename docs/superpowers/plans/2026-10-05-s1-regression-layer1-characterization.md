# S1 回归满刻度检查：第一层表征 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task, only after operator authorization. Cursor 负责全部实现以及审阅后发现问题的修复；Claude Code 负责设计与独立审阅。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现第一层（方法灵敏度下限）表征工具：生成冻结清单中的材料，经完整工具路径测量，按预先固定的定义计分、拟合候选形式，并在冻结之后才允许运行验证侧。本计划只到“工具就绪、清单可生成”为止；正式的校准运行、形式与取值冻结、验证运行、下限审批各自另行授权（见 E 节）。

**Architecture:** 新包 `src/signal_diag/evaluation/full_scale_characterization/`。它位于评测层，只导入 `signal/`、`dsp/`、`tools/`，不导入 `rules/`、`agent/`、`app/`、`knowledge/`；产品代码不得导入它。材料在本包内用 NumPy 合成，经本包自带的整数 PCM 编码器写成 WAV 字节，再走 `load_wav_bytes → 确定性 signal_id 重建 → InputIdentity → measure_output → measure_full_scale_facts`，与产品工作台同一条测量路径。产物写入 `docs/evaluations/v0_3/full_scale_characterization/round_1/`，每个文件只写一次。

**Tech Stack:** 现有 Python 3.11/3.12、NumPy、Pydantic 2。不新增依赖。

**Spec:** 表征设计 `docs/superpowers/specs/2026-10-05-s1-regression-layer1-characterization-materials-scoring-design.md`（§12 优先，其次 §11、§10、§9、§2–§8）；削波语义设计 `docs/superpowers/specs/2026-10-05-s1-regression-clipping-comparison-semantics-design.md` §12–§14；合同 `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §23.4、§23.5、§23.7；`docs/OPEN_QUESTIONS.md` OQ-021、OQ-022；探查 `docs/OQ020_FULL_TOOLPATH_PROBE_2026-10-05.md`；已合并实现 PR #41（`0770514`）。

**Status:** 修订 2（2026-10-05）。修订 1 经一次独立只读审阅（结论“修改后可批准”，10 条 Major 及若干 Minor），修订 2 逐条处理，对照见文末 G 节；修订 2 本身未再经独立审阅。A 节 13 条落点决定均已由操作员决定（A.1–A.9 于修订 1 决定，A.10–A.13 于审阅后决定）。B、C 节与计划整体尚未批准。计划本身不授权实施；实施授权只覆盖 Task 0–9，不覆盖任何正式运行。
**Read-only baseline:** `61cad20` on `codex/v0.2-real-world-validation`。执行前在当时基线上重新核对本计划引用的文件、接口与空闲测试 ID。

## Global Constraints

- 不修改 `src/signal_diag/` 下 `signal/`、`dsp/`、`tools/`、`rules/`、`knowledge/`、`agent/`、`app/` 的任何文件（产品树哈希因此不变，不需要追加代码身份登记行）。`tests/test_architecture_boundaries.py` 只追加一个前缀。
- 不修改冻结 V0.2 §§1–64、§22、§23 合同文本、D043、已合并的满刻度检查实现、已封存的评测与 Demo 资产。OQ-021、OQ-022 只登记，不在本计划内实现。
- 不在 `src/` 下写入任何下限、临界区或批准域数值。拟合出的数值只出现在运行产物里，且不被产品加载。`PRODUCT_APPROVED_FULL_SCALE_FLOORS` 保持为空。
- 实施 PR 内不运行正式清单（round_1）的任何测量，也不把 round_1 清单写入仓库。测试只用 `tests/` 下的微型清单。
- 数值只来自确定性测量；LLM 不参与生成、挑选、拟合或解释。不调用 RealLLM，不 seal。
- 敏感度空对每对只施加一项扰动，组合扰动仅在验证侧。容忍范围内的 P9（位深转换加一步）按合同 §23.4 “one step … plus bit-depth conversion” 的叠加读法（A.10）本身就是容忍定义，不算组合扰动。随机性全部来自清单里记录的种子。
- 验证侧材料在冻结记录存在之前不得生成、测量或读取（代码强制，见 Task 7）。
- 计划内的每一对都留在分母里：生成失败、测量无效、被拒绝比较单独计数。

---

## A. 运行前须批准的决定

表征设计 §7 有五项未勾选。本计划把它们落成 B 节清单。**操作员批准本计划即批准 B 节与 C 节**；Task 0 把批准结果写回表征设计 §7。批准后再改任何一项，按表征设计 §1 固定规则 2 处理（记录理由、作废已看过的验证结果）。

1. **基础材料加起始相位轴。** 状态翻转的位置取决于采样相位（语义设计 §12.5、§14）；100 Hz、48 kHz 时每周期恰好 480 个样本，所有周期的采样相位相同。M2/M11、M3、M5 的基础材料加相位轴，校准 {0, 1.0, 2.0} rad，验证留出 {0.5, 3.0} rad。round_1 固定启用，不提供关闭开关。
2. **临界区候选形式增加 K4（表征设计 §11 要求）。** 形式同 K2，但把峰值换成“两样本等效电平” `e = peak_abs · cos(π / N)`。依据：连续两个样本都过阈值，要求跨峰两样本中较低者不低于阈值，其上界约为 `A · cos(π/N)`；翻转点约在 `thr / cos(π/N)`。N 用材料的生成参数计算（产品里来自用户声明的基频，报告须披露）。K4 若被选中，`FullScaleMethodFloor` 现有字段表达不了，下限审批时须修订模型与合同 §23.4 的取值形式。
3. **F3 的分段条件必须是产品可观测的量**，并限定为一个变量（N 或范围内周期数）上的单一切点、两段（C.4）。F3 若被选中，同样须在下限审批时修订模型与 §23.4。
4. **分析范围长度不进来源组键。** 分析范围都从文件开头取，短范围是长范围的前缀，把长度并入组键会让同一段波形同时出现在两侧。校准侧来源组只跑校准长度；验证侧来源组跑 B.1 列出的验证长度。
5. **临界区拟合要求翻转对的两侧都在区内。** 最小解唯一。合同 §23.4 “must contain every signal that a tolerated difference can move across” 本来就是这一要求。验证侧仍按产品规则判（任一侧在区内即排除）。
6. **32 位文件的一步取 2⁻²⁴**（与 PR #41 落点决定 15 一致），即 128 个 32 位码值。32 位编码先把码值量化到 128 的整数倍，保证经加载器 float32 解码后，偏移恰为一步（M4）。
7. **产物以“测量表 + 对表”存放**（A.13），确定性 gzip（`mtime=0`）入库；单文件压缩后超过 50 MB 停下由操作员决定。
8. **M10 白噪声不进表征人口**（表征设计 §9.4）。
9. **测试 ID：** 新登记 T-CX371–T-CX380（仅定义，Task 0）。
10. **合同 §23.4 的容忍范围按叠加理解：** “一个较粗位深量化步长的差异”与“位深转换”可以同时出现。容忍类因此新增 P9（B.3）。审阅实测（完整工具路径）：100 Hz、48 kHz、幅度 0.989993、相位 π/480，16 位舍入峰值 0.98995972、计入 0，低于固定最低要求界线 0.99 − 2⁻¹⁵ = 0.9899695；同一波形 32 位舍入后整体远离零偏一个 16 位步长，计入 800。这类翻转由拟合出的 `zone_below` 覆盖（产品用 `max(zone_below, step)`），不会让产品判错；但固定最低要求作为与抽样无关的理论保证不再充分，另登记 OQ-022，与 OQ-021 一起在下限审批前决定。
11. **校准侧起始变化对的深度 0.9999 改为 0.9995**，0.9999 只留在验证侧。0.9999 是 M3 的验证留出深度，原表会让校准侧看到验证组的同一段波形（M6）。这改动了已批准的表征设计 §9.5，记入表征设计 §12。
12. **验证侧取留出值子网格**（B.2 末），规模与校准侧同量级；精确对数由清单生成器给出，操作员批准。
13. **结果存储形态：** 测量表每个“文件 × 声道 × 范围 × 侧”一行，对表只引用测量表行号与对级字段（C.1）。

**决定记录（操作员，2026-10-05）：**

| 条 | 决定 |
|---|---|
| A.1 起始相位轴 | 采纳 |
| A.2 新增 K4 | 采纳 |
| A.3 F3 只用可观测量分段 | 采纳（修订 2 进一步限定为单一切点两段） |
| A.4 范围长度不进来源组键 | 采纳 |
| A.5 拟合时翻转对两侧都在区内 | 采纳 |
| A.6 32 位步长 2⁻²⁴ | 采纳（修订 2 补充 128 码对齐） |
| A.7 gzip 入库，单文件超 50 MB 停 | 采纳（修订 2 改为测量表 + 对表，见 A.13） |
| A.8 M10 不进表征人口 | 采纳 |
| A.9 登记 T-CX371–T-CX380 | 采纳 |
| A.10 容忍范围按叠加理解 | 采纳；另开 OQ-022 |
| A.11 校准侧起始变化对 0.9999 → 0.9995 | 采纳 |
| A.12 验证侧留出值子网格 | 采纳 |
| A.13 测量表 + 对表 | 采纳 |

## B. 冻结清单（候选数值，均为材料取值，不是容差）

### B.1 共用轴

| 轴 | 校准侧 | 验证侧 | 依据 |
|---|---|---|---|
| 采样率 | 44100、48000 | 同左 | 表征设计 §8.2 |
| 基频 f0 | 100、440、880、2000、4000、8000 | 留出 220、3000（内插）；50、997、12000（外推） | §10.3 |
| 文件时长 | 2.0 s | 同左 | §8.2 |
| 分析范围长度 | 2.0、0.1、0.01、0.005 s | 2.0、0.005（校准长度子集）；留出 1.0、0.02（内插）、0.002（外推） | §10.3；A.4 |
| 起始相位 | 0、1.0、2.0 rad | 留出 0.5、3.0 rad | A.1 |
| 种子 | `1001–1005` | `2001–2005` | §8.2 |
| 满刻度阈值 | 0.99（唯一配置身份） | 同左 | §7 已定 |

分析范围固定为 `TimeRange(start_s=0.0, end_s=L)`；L = 2.0 时等于整个文件。

### B.2 材料族

合成规则（全部 float64，再交给编码器）：

- 正弦：`A · sin(2π f0 t + φ)`，`t = n / sr`。
- M3/M5 削波：先生成削波前波形 `w`（M3 为单位正弦；M5 为 `sin(2π f0 t + φ) + Σ r_k sin(2π k f0 t + k φ)`），按 `max|w|`（对生成的样本数值求得）把它缩放到峰值 `level / depth`，再截到 `±level`。
- M6：基波幅度 0.5，`r_k` 为相对基波的幅度，不缩放。
- M9：两个声道各按对应族生成，交错写入双声道 WAV。

| 族 | 校准侧 | 验证侧留出 | 角色 |
|---|---|---|---|
| M1 无削波 | 幅度 0.05、0.5、0.9 | 0.2、0.01 | 反例：计入数必须为 0 |
| M2/M11 近阈值正弦 | 峰值 0.98、0.989、0.9899、0.99、0.9901、0.9905、0.991、0.992、0.993、0.994、0.995、0.9975、1.0 | 0.9897、0.9915、0.9925、0.996（内插）；0.97（外推） | 主要工况：临界区 |
| M3 满刻度硬削波 | 电平 0.9901、0.995、1.0；深度 0.999、0.99、0.9、0.7 | 电平 0.991、0.99；深度 0.95、0.9999、0.5 | 主要工况：样本数下限 |
| M4 次满刻度平顶 | 电平 0.5、0.9；深度同 M3 | 电平 0.7、0.98、0.1；深度同 M3 留出 | 反例：计入数必须为 0 |
| M5 削波叠加谐波 | 谐波 {2:0.1}、{3:0.1}；电平 0.995、0.9；深度 0.99、0.9 | 谐波 {2:0.3}；深度 0.95；电平不留出（0.995、0.9） | 电平 ≥ 阈值者为主要工况，其余为反例 |
| M6 有谐波无削波 | {3:0.3}；奇次 3、5、7 按 1/n | 奇次到 15 按 1/n | 反例 |
| M7 | 标记：按生成参数推算每个峰过阈值的样本数为 1–3 个的格 | 同左 | 标记 |
| M8 | 由范围长度轴覆盖 | 同左 | — |
| M9 双声道 | 左 M1(0.5) + 右 M3(电平 0.995、深度 0.9)，及左右互换 | 左 M4(电平 0.9、深度 0.9) + 右 M3(同左) | 声道隔离 |

**来源组键** = 族 + f0 + 采样率 + 削波程度（M1 为幅度，M2/M11 为峰值，M3/M4 为 (电平, 深度)，M5 为 (谐波, 电平, 深度)，M6 为谐波集，M9 为组合）+ 起始相位。改文件名、改种子、改扰动幅度不构成新组。

**校准侧** = 所有维度都取校准值的组合（M2/M11、M3、M5 含相位轴；其余族相位固定为 0）。

**验证侧（A.12 留出值子网格）** = 下列组合的并集，其余维度取下表的固定子集；采样率两个都取：

1. 恰有一个维度取留出值，其余维度取固定子集；
2. f0 与削波程度两个维度同时取留出值，相位为 0。

| 维度 | 验证侧非留出维度的固定子集 |
|---|---|
| f0 | 100、880、4000 |
| 起始相位 | 0、2.0 |
| M2/M11 峰值 | 0.9899、0.99、0.9905、0.992、0.995、1.0 |
| M3 电平 / 深度 | 0.9901、0.995、1.0 / 0.99、0.9 |
| M4 电平 / 深度 | 0.5、0.9 / 0.99、0.9 |
| M5 谐波 / 电平 / 深度 | {2:0.1}、{3:0.1} / 0.995、0.9 / 0.9 |
| M1 幅度、M6 谐波 | 全部校准值 |

### B.3 空对

“一步”：16、24 位为一个码值；32 位为 128 个码值（A.6）。偏移后的码值截到合法范围。

**容忍范围内（定下限与临界区；硬条件只对这一类）：**

| 代号 | 两侧 | 位深 |
|---|---|---|
| P0 | 同一编码，字节相同 | 16、24、32 各一对 |
| P4 | 舍入编码，位深不同 | 32↔24、32↔16、24↔16 |
| P7a | 舍入 ↔ 全部样本远离零偏一步 | 16、24、32 |
| P7b | 舍入 ↔ 全部样本向零偏一步 | 16、24、32 |
| P7c | 舍入 ↔ 截断（向零取整） | 16、24、32 |
| P7d | 舍入 ↔ 每个样本以固定种子随机 ±1 步 | 16、24、32，每格 5 个种子 |
| P9a | 较粗位深舍入 ↔ 较细位深舍入后远离零偏一个**较粗位深**步长 | 32↔16、24↔16、32↔24 |
| P9b | 同上，向零偏一个较粗位深步长 | 同上 |
| P9c | 较粗位深截断 ↔ 较细位深舍入 | 同上 |
| P5t | 16 位舍入 ↔ 16 位输出增益差：校准侧 ±1e-5，验证侧留出 ±3e-5 | 仅 16 位（逐样本差不超过一个 16 位步长，按 §10.1 属容忍类） |

**敏感度（只披露，不进入下限，不计入通过条件）：** 基础编码为 16 位舍入（P8 除外）。

| 代号 | 校准侧 | 验证侧留出 | 定义 |
|---|---|---|---|
| P1 文件级样本偏移 | 1、3、37 | 2、101 | 生成 `2 s + k/sr` 的连续波形，丢弃前 k 个样本 |
| P3 起始相位 | Δ = 0.1、1.0、2.0 rad | Δ = 0.5、3.0 rad | 只施加在基础相位为 0 的组上，结果相位即 Δ |
| P5 输出增益差（削波之后） | 相对 ±1e-4、±1e-3、±5e-3 | ±3e-4；±1e-2 | — |
| P6 单侧叠加噪声（削波之后） | RMS 1e-5、1e-4、1e-3 | 3e-5、3e-4；3e-3 | 种子来自该侧种子集 |
| P8 8 位（域外） | 16↔8、32↔8 | 同左 | — |
| 组合（仅验证侧） | — | P1(1)+P6(1e-4)；P4(32↔16)+P5(1e-4)；两侧各加不同种子噪声 1e-4 | — |

P3 只施加在相位 0 的组上，保证校准侧的结果相位只有 0.1、1.0、2.0，不会叠加出留出相位 3.0。P5 的若干档会近似复现内插留出峰值（例如 0.995 × (1 + 1e-3) ≈ 0.996），P5 属敏感度类、不参与拟合，报告须披露这一近似。

### B.4 变化对

两侧同位深（16、24、32 各一份），相位 0，在该侧的全部范围长度上运行。

| 类型 | 校准侧 | 验证侧 |
|---|---|---|
| 起始（否 → 是） | 旧：M1 幅度 0.9；新：同一波形按 M3 规则在 0.995 削波，深度 0.9995、0.999、0.99、0.9（A.11） | 电平 0.995，深度 0.9999；电平 0.9901，深度 0.9995、0.999、0.99、0.9 |
| 加重（是 → 是） | 以该侧 M3 各组为旧版；新版电平不变，削波前峰值相对增加 1e-4、1e-3、1e-2、5e-2、1e-1 | 同左 |
| 盲区（仅披露） | 不进校准 | 次满刻度：电平 0.9、0.98，深度 0.99 → 0.9；单样本：997 Hz、电平 0.9905、削波前峰值 0.991 |

### B.5 规模估算（推算，非实测）

校准侧约 1,400 份材料 × 4 个范围长度 × 约 75 对（容忍约 45、敏感度约 30）≈ 42 万对；去重后约 40 万行测量。验证侧按 B.2 子网格与校准侧同量级。审阅实测 `measure_output` 在 2.0 s 范围约 30–130 ms，0.1 s 及更短约 2–9 ms，校准侧单进程约 2–3 小时。精确数由 Task 3 的清单生成器给出；验证侧计划对数超过校准侧 2 倍时停下由操作员决定。

## C. 计分与拟合定义（写死，运行后不改）

### C.1 记录

**测量表**（每个“WAV 文件 × 声道 × 分析范围 × 侧”一行）：行号、`wav_sha256`、声道、范围、侧、`signal_id`、`run_id`、终态与原因码，以及：`counted_samples`、`over_threshold_uncounted`、`state`、`peak_abs`、`analyzed_samples`、`pcm_bit_depth`、`clipping_ratio`、`clipped_samples`、`full_scale_detected`、`flat_top_detected`、`clipping_mechanism`、`bundle_digest`、`facts_digest`、谐波工具状态。

**对表**（每对一行）：清单字段（族、来源组、侧、扰动代号与档位、种子、两侧编码描述、范围长度、f0、采样率、`N = sr / f0`、范围内周期数 `analyzed_samples · f0 / sr`、M7 标记）、旧侧与新侧的测量表行号，以及：

- `count_diff = 新 − 旧`；
- `ratio_diff = count_diff / 旧侧 analyzed_samples`（与产品 `_judgment_status` 的比例公式一致；不是 `clipping_ratio` 之差）；
- `flip = 两侧 state 不同`；
- 对的终态（`measured` / `rejected` / `invalid` / `generation_failed`）与原因码。

确定性：`signal_id = "sig_" + wav_sha256[:32]`，用 `build_signal_record(..., signal_id=...)` 以加载器解码出的样本重建记录；`run_id = "run_" + <侧> + "_" + wav_sha256[:16]`。

### C.2 健全性检查

任何一条失败即中止该轮，写出中止记录（触发的对、检查项、数值），不出报告，旧产物保留：

1. P0 的任一对 `count_diff` 非零，或两侧 `wav_sha256` 不同。
2. 对每个容忍范围内的对，以舍入侧 `x` 为参照，`δ` 取该对较粗位深的步长，记 `δ' = δ`；P9 的两侧差异是一步加一次位深转换（截断转换的误差可达一步），取 `δ' = 2δ`，用 `count_full_scale_samples` 直接对解码样本检验夹逼式 `count(x, thr + δ') ≤ count(y) ≤ count(x, thr − δ')`。
3. 等式检验：P7a 的计数等于 `count(x, thr − δ)`，P7b 的计数等于 `count(x, thr + δ)`。这一条证明单向最坏情形确在扰动集里。
4. P7 各对（单项一步扰动）中出现翻转，且“否”侧不在固定最低要求内（C.3，k = 1）：按推导这不可能发生，出现即说明编码器有缺陷。
5. 任一侧 `verify_full_scale_facts` 失败。

P9 的翻转落在 k = 1 的固定最低要求之外**不中止**，按 C.3 单独计数并报告（A.10，OQ-022）。

### C.3 固定最低要求

与产品 `_in_critical_zone` 及 `_quantization_step` 逐字等价：“否”侧 `peak_abs ≥ thr − k · step` 即在区内，`step = max(2^-(b-1), 2^-24)`，b 取两侧较粗位深；产品现行 k = 1。报告对 k = 1 与 k = 2 分别给出：应用前的翻转数、应用后仍在区外的翻转数，并按扰动代号分列。k = 2 的数字只作 OQ-022 的依据，不改变拟合与判定。

### C.4 候选形式（只能从中选）

- **批准域 D1：** `N ≥ n_min` 且 `范围内周期数 ≥ p_min`。候选值为校准网格中实际出现的 N 与周期数的去重值，逐一列举。
- **临界区 K1–K4、K0**（定义见 C.5），每个都与 k = 1 的固定最低要求取或。
- **样本数下限：**
  - F1：`ratio_diff` 下限；
  - F2：`count_diff` 下限；
  - F3：在 N 或范围内周期数中的一个变量上取单一切点（候选值同 D1），两段，两段同为 F2，或两段同为 F1；
  - F0：不设下限。
- 某组合在校准侧无法满足全覆盖时，结论为该组合不成立；不得临时发明新形式。

### C.5 拟合算法（确定性；工具输出全部组合，审阅者只选择）

对每个候选批准域 `(n_min, p_min)`，只用域内、容忍范围内的校准侧已测量对。

**临界区。** 判定方式与产品一致：按状态区分，不按峰值在阈值哪一侧区分。

- “否”侧在区内：`peak ≥ thr − max(zb, k·step)`（无上界）；K4 用 `e ≥ thr − zb`，再与固定最低要求取或。
- “是”侧在区内：`peak ≤ thr + za`；K4 用 `e ≤ thr + za`；K3 另加 `counted < c`。

拟合步骤：

1. 待覆盖点 = 全部翻转对的两侧（A.5）。
2. 剔除已被固定最低要求（k = 1）覆盖的“否”侧点。
3. K2：`zb = max(thr − peak)`，取自剩余“否”侧点；`za = max(peak − thr)`，取自“是”侧点。没有点的一边取 0。
4. K1：`zb = za = max(K2 的 zb, za)`。
5. K3：门槛 `c` 的候选值为翻转对“是”侧 `counted_samples + 1` 的去重值，另加 0（不用门槛）。对每个候选 `c`，计入数低于 `c` 的“是”侧视为已覆盖，其余点按 K2 求 `(zb, za)`。每个 `(c, zb, za)` 一行，带行标识。
6. K4：同 K2，以 `e` 代替 `peak`。
7. K0：拟合出的区使域内主要工况（M2/M11、M3、M5 中电平 ≥ 阈值者）没有任何一对两侧都在区外。

**样本数下限。** 只用两侧都为“是”且两侧都在所选临界区外的对。

- F1 = `max |ratio_diff|`，F2 = `max |count_diff|`，不加余量。
- F3 对每个切点分两段，各段分别取 max。

**输出。** 对每个 (域, K[行], F[切点]) 组合，给出：

- 参数；
- 域内覆盖率（适用对 ÷ 域内计划对），以及按族覆盖率；
- 校准侧变化对的检出情况（按档）；
- 被排除的对及原因。

工具不排名、不推荐。

**对拍测试。** `tests/` 下用 `FullScaleMethodFloor` 夹具，把本包的临界区与判定函数（K1–K3、F1、F2）和产品 `rules.full_scale_check._in_critical_zone`、`_quantization_step`、`_judgment_status` 逐例对拍。本包不导入 `rules/`，对拍只在测试里进行。

### C.6 验证侧计数（冻结后原样套用，不调整）

只对冻结记录中的 (域, K 行, F 切点)：

- **硬条件一：** 域内、容忍范围内的适用空对中，两侧都在区外而状态翻转的对数，须为 0。
- **硬条件二：** 两侧都为“是”且都在区外的适用空对中，`|count_diff|`（F1 用 `|ratio_diff|`）严格大于下限的对数，须为 0。空对的新旧方向是任意的，所以用绝对值。
- **强制披露：**
  - 域外的格；
  - 敏感度空对的差值分布与翻转数，包括 P5 近似复现留出峰值的说明；
  - 盲区变化对；
  - 按族覆盖率；
  - 起始变化对在区外被判为起始的档，以及在区内拿不到判定的对数；
  - 加重变化对按档被下限盖掉的对数，以及最小可检出变化；
  - 校准侧未见过的翻转；
  - C.3 中 k = 1 与 k = 2 的翻转计数；
  - M11 的说明：从现有输出无法区分削平与未削平（表征设计 §10.4）；
  - 基频来源的差别：表征用生成参数，产品用用户声明且不核对（§10.6）。

任一硬条件不满足，该轮结论为未通过，产品保持纯描述性；不得缩小人口、调整数值或改准则后重算。验证运行中健全性检查失败时同样写出中止记录。

## D. 文件结构

| 文件 | 责任 |
|---|---|
| Create `src/signal_diag/evaluation/full_scale_characterization/__init__.py` | 包说明 |
| Create `.../models.py` | 清单、测量行、对、冻结记录、报告的 Pydantic 模型（`frozen=True, extra="forbid"`） |
| Create `.../constants.py` | B 节的全部取值（唯一来源） |
| Create `.../synthesis.py` | 材料波形合成（float64，B.2 合成规则） |
| Create `.../pcm.py` | 整数 PCM WAV 编码（8/16/24/32 位；舍入、截断、同向偏一步、随机偏一步；32 位 128 码对齐） |
| Create `.../manifest.py` | 来源组、划分、对的枚举，规范 JSON 与哈希 |
| Create `.../executor.py` | 完整工具路径测量、确定性身份、按行缓存、终态 |
| Create `.../checks.py` | C.2 健全性检查 |
| Create `.../zone.py` | C.3/C.5 的区判定与 F 判定（纯函数，供拟合、验证与对拍共用） |
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
  manifest.json                 # R0 生成；批准时记录其 sha256
  identity.json                 # 代码与配置身份
  calibration_measurements.jsonl.gz
  calibration_pairs.jsonl.gz
  calibration_report.{json,md}
  freeze_record.json
  validation_measurements.jsonl.gz
  validation_pairs.jsonl.gz
  validation_report.{json,md}
  abort_record.json             # 仅在中止时出现
  SHA256SUMS
```

`identity.json` 分两部分：

- **比对项**（校准与验证运行前都比对，不一致即拒绝运行）：
  - `MEASUREMENT_VERSION`、`FULL_SCALE_FACTS_VERSION`；
  - 阈值 0.99、最少连续样本数 2、`analyze_clipping` 的平顶默认值；
  - 以下文件的 sha256：`dsp/full_scale.py`、`dsp/clipping.py`、`dsp/preprocess.py`、`tools/regression_full_scale.py`、`tools/regression_measurement.py`、`tools/service.py`、`signal/wav.py`、`signal/factory.py`、`signal/segment.py`；
  - `contextual_product_tree_sha256()`；
  - 本包测量相关模块（`constants.py`、`synthesis.py`、`pcm.py`、`manifest.py`、`executor.py`）的合并摘要。
- **只记录项**：Git 提交号、本包其余模块的摘要。

测量相关模块的任何改动都要求起 `round_2`；报告模块的修复不影响比对。

---

### Task 0: 文档登记（仅定义）

- [ ] 在 `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` 登记 T-CX371–T-CX380（定义见 F 节后），索引行写明“definitions; characterization runs and floor approval gated”。
- [ ] 在表征设计 §7 勾选五项，每项写“按实施计划 `2026-10-05-s1-regression-layer1-characterization.md` B/C 节，操作员 <日期> 批准”。
- [ ] Commit — `docs: register layer-1 characterization test IDs and record §7 decisions`

### Task 1: 包骨架与分层（T-CX371）

- [ ] 写失败测试 `tests/evaluation/full_scale_characterization/test_layering.py`：
  - 本包任何模块不导入 `signal_diag.rules`、`.agent`、`.app`、`.knowledge`；
  - `signal/`、`dsp/`、`tools/`、`rules/`、`knowledge/`、`agent/`、`app/` 下没有文件提到 `full_scale_characterization`；
  - `PRODUCT_APPROVED_FULL_SCALE_FLOORS == ()`。
- [ ] 追加前缀；创建空包。
- [ ] Commit — `feat(eval): full-scale characterization package skeleton (T-CX371)`

### Task 2: 合成与整数 PCM 编码（T-CX372）

**Interfaces:**

```python
def sine(*, f0: float, sr: int, duration_s: float, amplitude: float, phase_rad: float) -> np.ndarray
def clipped(*, f0, sr, duration_s, level: float, depth: float, phase_rad: float,
            harmonics: Mapping[int, float] | None = None) -> np.ndarray
def harmonic_sine(*, f0, sr, duration_s, fundamental: float, harmonics: Mapping[int, float], phase_rad: float) -> np.ndarray
def encode_pcm_wav(channels: Sequence[np.ndarray], *, sr: int, bits: Literal[8, 16, 24, 32],
                   rounding: Literal["round", "trunc", "away_one_step", "toward_one_step", "random_one_step"] = "round",
                   step_bits: Literal[16, 24, 32] | None = None, seed: int | None = None) -> bytes
```

码值约定与加载器一致：

- 16 位码值 = `round(x · 32768)`，截到 `[-32768, 32767]`；24 位缩放 `2^23`；8 位为无符号偏置 128。
- 32 位先求 `round(x · 2^31)`，再就近量化到 128 的整数倍。
- `step_bits` 用于 P9：在较细位深文件上偏移一个较粗位深的步长；缺省为本文件的步长。

- [ ] 写失败测试：
  - 16/24/8 位：`load_wav_bytes` 解码样本乘以缩放因子后，逐样本等于预期码值。32 位：解码样本逐样本等于 `float32(code / 2^31)`。
  - 解码域中，偏一步的样本与舍入样本之差的绝对值逐样本 ≤ 对应步长；`away`/`toward` 方向全部一致；32 位解码域偏移恰为 2⁻²⁴（|x| ≥ 0.5 的样本）。
  - 相同种子两次编码字节相同；不同种子不同。
  - `clipped` 的削波前峰值等于 `level / depth`（数值求 max），输出绝对值 ≤ `level`；M5 先加谐波再缩放、再削波。
  - 不得调用 `app/pcm_wav.py`。
- [ ] 实现。
- [ ] Commit — `feat(eval): characterization waveform synthesis and integer PCM encoder (T-CX372)`

### Task 3: 清单生成（T-CX373、T-CX374）

**Interfaces:** `build_manifest(constants=ROUND_1) -> Manifest`；`manifest_sha256(m) -> str`（规范 JSON：键排序、无空白、`allow_nan=False`）。`Manifest` 含 `round_id`、`constants_digest`、`source_groups`（键、侧）、`pairs`（每对的完整生成描述，不含任何测量值）、各侧与各族的计划对数。

- [ ] 写失败测试（用 `ROUND_1` 与微型常量各测一次）：
  - T-CX373：同一常量两次生成的哈希相同；`constants.py` 任一取值改变则哈希改变。
  - T-CX373：每个敏感度对只含一项扰动（组合只在验证侧）；容忍类只含 B.3 列出的代号；种子来自该侧的种子集，两侧不重叠。
  - T-CX374：一个来源组的全部对只落在一侧；校准侧只出现校准长度；改文件名、种子、扰动幅度不产生新组键。
  - T-CX374（防泄漏，按有效生成参数检查）：校准侧任一对任一侧的有效参数（f0、采样率、相位取模 2π、峰值、电平、深度、谐波），与验证组键的参数组合都不相同；P3 结果相位不等于任何留出相位；起始变化对的校准深度不含 0.9999。
  - T-CX374：验证侧包含每个材料族至少一个组、全部组合扰动与全部盲区变化对；校准侧不含盲区与组合。
  - 验证侧计划对数超过校准侧 2 倍时 `build_manifest` 抛出 `ScaleLimitExceeded`。
- [ ] 实现；命令 `python -m signal_diag.evaluation.full_scale_characterization manifest --round round_1 --dry-run` 只打印各侧、各族、各扰动的计划对数和预计测量行数，不写文件。写文件属于 R0。
- [ ] Commit — `feat(eval): characterization manifest and leakage-safe split (T-CX373, T-CX374)`

### Task 4: 完整工具路径执行器（T-CX375）

**Interfaces:** `measure_row(spec, *, cache) -> MeasurementRow`；`assemble_pair(pair, rows) -> PairRecord`。

每侧的步骤：

1. 合成，再用 `encode_pcm_wav` 编码。
2. `load_wav_bytes` 加载，再用 `build_signal_record(samples, sample_rate_hz=..., signal_id="sig_" + wav_sha256[:32], ...)` 重建记录，放入 `InMemorySignalRepository`。
3. `signal.segment._resolve_sample_bounds` 求起止样本，组装 `InputIdentity`（确定的 `run_id`）。
4. 调用 `measure_output`，参数为 `MeasurementSelection(clipping=ClippingInput(channel, time_range, full_scale_threshold=0.99), harmonic=HarmonicDistortionInput(channel, time_range))`。
5. 依次调用 `measure_full_scale_facts` 和 `verify_full_scale_facts`。

其余约定：

- 缓存键为 `(wav_sha256, channel, time_range, side)`。
- 谐波结果不参与计分，只记录状态。审阅实测：基频 2–12 kHz 时谐波多为 invalid，但削波结果全部为 success，摘要正常。

**终态映射：**

| 情形 | 终态 |
|---|---|
| 合成或编码抛错 | `generation_failed` |
| `load_wav_bytes` 抛错 | `invalid`，原因码 `wav_load` |
| 削波工具不成功或无结果 | `invalid`，原因码 `clipping_tool` |
| `measure_output` 抛错 | `invalid`，原因码 `measure_output` |
| `verify_full_scale_facts` 抛错 | 触发健全性中止（C.2 第 5 条） |

- [ ] 写失败测试：
  - 行里的事实与直接调用 `measure_full_scale_facts` 得到的事实相等；`counted_samples` 与 `count_full_scale_samples` 对解码样本的结果相等。
  - 各终态按上表落位，且都留在分母里。
  - M9：左声道行与同参数单声道材料的行，在计数、峰值、状态、`analyzed_samples` 上相等（摘要与 `wav_sha256` 必然不同，不比较）。
  - 同一输入两次执行，行逐字节相同（包括 `bundle_digest`、`facts_digest`）。
- [ ] 实现。
- [ ] Commit — `feat(eval): full tool-path executor for characterization pairs (T-CX375)`

### Task 5: 健全性检查（T-CX376）

- [ ] 写失败测试：对 C.2 的每一条，分别构造违反该条的记录，各自导致 `SanityAbort`，异常信息写明对的标识与检查项；全部满足时通过；P9 在 k = 1 区外的翻转不中止，并被计数。
- [ ] 实现 C.2。
- [ ] Commit — `feat(eval): characterization sanity aborts (T-CX376)`

### Task 6: 区判定、校准拟合与报告（T-CX377）

- [ ] 写失败测试（手工记录，数值只为验证逻辑）：
  - `zone.py` 与产品对拍：K1–K3、F1、F2 的判定，对一组覆盖边界的手工事实，与 `rules.full_scale_check._in_critical_zone`、`_quantization_step`、`_judgment_status` 逐例一致（对拍测试放在 `tests/`，可导入 `rules`）。
  - K1/K2/K4 的最小参数与手算一致；K3 输出全部候选 `c` 行，每行都与手算一致；剔除固定最低要求已覆盖点的规则生效；K0 按 C.5 第 7 步判定。
  - F1/F2 等于适用对 `|ratio_diff|`、`|count_diff|` 的最大值，不加余量；F3 只接受 N 或周期数上的单一切点；按材料族分段的输入被拒绝。
  - C.3 中 k = 1、k = 2 的翻转数分别给出。
  - 拟合函数只接受校准侧记录，传入任何验证侧记录抛错。
  - 报告列出全部 (域, K 行, F 切点) 组合，不含排名、推荐或“通过”字样。
- [ ] 实现 C.3–C.5 与校准报告。
- [ ] Commit — `feat(eval): critical-zone functions and calibration fitting (T-CX377)`

### Task 7: 冻结记录与只写一次（T-CX378）

**Interfaces:** `FreezeRecord(round_id, manifest_sha256, identity_sha256, calibration_measurements_sha256, calibration_pairs_sha256, calibration_report_sha256, domain, zone_form, zone_row_id, zone_params, floor_form, floor_cut, floor_params, rationale, approved_by, approved_at, digest)`。

- [ ] 写失败测试：
  - `store` 对已存在的产物文件拒绝写入；`SHA256SUMS` 与文件一致。
  - 冻结记录的上游哈希与磁盘文件不符时拒绝；所选形式、K3 行标识或 F3 切点不在拟合输出中时拒绝；参数不等于拟合输出中对应组合的值时拒绝（只能选，不能改）。
  - 没有有效冻结记录时，生成或测量任何验证侧对都抛错。
  - `identity.json` 的比对项与当前不一致时，校准与验证都拒绝运行；只记录项（提交号等）变化时照常运行。
- [ ] 实现。
- [ ] Commit — `feat(eval): freeze record and write-once characterization store (T-CX378)`

### Task 8: 验证计数与报告（T-CX379）

- [ ] 写失败测试（手工记录）：
  - 两条硬条件各有一例越限时，结论为未通过；硬条件二用绝对值。
  - 任一侧在区内的翻转对被排除，并计入排除原因。
  - 最小可检出变化按档计算。
  - C.6 的全部强制披露项都出现，盲区与敏感度只出现在披露区。
  - 健全性中止时写出 `abort_record.json`，不出报告。
  - 报告不含会被读成产品判定的措辞（“regression detected”“通过下限”等）。
- [ ] 实现 C.6 与验证报告。
- [ ] Commit — `feat(eval): validation counting and report (T-CX379)`

### Task 9: 命令行、端到端微型运行与离线验收（T-CX380）

- [ ] 命令：`manifest`、`calibrate`、`report-calibration`、`freeze`、`validate`、`report-validation`，每个都校验上游产物哈希；`manifest --dry-run` 不写文件。
- [ ] 写测试：在临时目录用微型清单（2 个来源组、各 1 个范围长度）跑完整六步：
  - 产物齐全、哈希一致；
  - 重跑同一步被拒绝；
  - 从头再跑一遍，全部产物逐字节相同。
- [ ] 全量验证：

```bash
python -m pytest -q -rxXs -p no:cacheprovider
python -m pytest -q tests/test_architecture_boundaries.py
python -m ruff check --no-cache src tests scripts
python -m mypy --no-incremental src
python scripts/verify_phase5_wheel.py
git diff --check 61cad20..HEAD
```

- [ ] 写 `docs/REGRESSION_LAYER1_CHARACTERIZATION_TOOL_OFFLINE_ACCEPTANCE.md`，内容包括：
  - 基线与 tip；
  - 上述命令的输出（wheel 冒烟若本地无法运行，如实标注，以 CI 为准）；
  - T-CX371–T-CX380 对应的测试名；
  - `manifest --dry-run` 对 round_1 打印的计划对数，并注明未写文件、不构成 R0 清单批准；
  - 明确说明未运行任何正式测量、未产生任何下限数值。
- [ ] Commit — `test: characterization tool end-to-end on a mini manifest; offline acceptance`

---

## E. 运行流程（每一步单独授权，本计划不授权）

| 步 | 内容 | 产物 | 授权 |
|---|---|---|---|
| R0 | 生成 `round_1` 清单与身份；操作员审阅对数并批准其 sha256 | `manifest.json`、`identity.json` | 清单批准 |
| R1 | 校准运行；健全性检查；校准报告 | `calibration_*` | 校准运行授权 |
| R2 | 审阅者从拟合输出中选定 (域, K 行, F 切点) 并写理由；不得查看任何验证侧数据 | `freeze_record.json` | 形式与取值冻结批准 |
| R3 | 验证运行与报告 | `validation_*` | 验证运行授权 |
| R4 | 独立审阅；决定 OQ-021、OQ-022；若通过，起草下限记录（选中 K4 或 F3 时先修订模型与 §23.4 形式） | 审阅包 | 下限审批（§23.7 第 4 步） |

任一步未通过：产品继续纯描述性，旧产物保留；要再试一次须起 `round_2`，用新的验证来源组。

## F. 不在本计划内

正式清单的任何测量；任何下限、临界区或批准域数值的选择与批准；`FullScaleMethodFloor` 的模型修订；产品登记处的任何改动；OQ-021、OQ-022 的实现；次满刻度平顶判定；`observed_variable` 阻断的修订；THD；RealLLM；seal。

## T-CX 定义（Task 0 登记）

| ID | 定义 |
|---|---|
| T-CX371 | 表征包只导入下层；产品代码不导入表征包；产品登记处仍为空 |
| T-CX372 | 整数 PCM 编码与加载器码值一致（32 位与 float32 解码一致）；一步扰动在解码域逐样本不超过一步且方向一致；种子决定字节 |
| T-CX373 | 清单确定且可哈希；敏感度对只含一项扰动；容忍类只含列出的代号；两侧种子不重叠 |
| T-CX374 | 按来源组划分；按有效生成参数无泄漏；验证侧子网格齐全且规模受限 |
| T-CX375 | 执行器走完整工具路径；身份与摘要确定；终态与分母完整；声道隔离 |
| T-CX376 | P0、夹逼、单向最坏等式、单步翻转与事实校验任一失败即中止；P9 区外翻转只计数 |
| T-CX377 | 区判定与产品逐例一致；拟合只在预列形式中求最小参数；不加余量；不读验证侧；报告不排名 |
| T-CX378 | 冻结只能选不能改；产物只写一次；无冻结记录不得触碰验证侧；身份比对项与只记录项分开 |
| T-CX379 | 验证只计数；两条硬条件与强制披露齐全；中止有记录；无产品判定措辞 |
| T-CX380 | 端到端六步在微型清单上可重现，逐字节一致 |

## G. 修订 2 对独立审阅发现的处理

| 发现 | 处理 |
|---|---|
| M1 容忍范围未覆盖“一步加位深转换” | A.10：新增 P9；C.2 不对 P9 区外翻转中止；C.3 报告 k = 1/2；另开 OQ-022 |
| M2 K 拟合与产品按状态区分的语义不一致 | C.5 改为按状态判定，先剔除固定最低要求已覆盖点；新增对拍测试 |
| M3 交叉核对恒成立且步长不清 | C.2 改为逐对夹逼，加单向最坏等式与单步翻转检查；δ 明确 |
| M4 32 位一步经 float32 解码不总是一步 | A.6、Task 2：32 位码值量化到 128 的整数倍；测试改为与 float32 解码比较 |
| M5 signal_id 随机导致不可重现 | C.1、Task 4：确定的 `signal_id`、`run_id`；缓存键含侧 |
| M6 三条泄漏路径 | P3 只施加在相位 0 的组上；A.11 校准起始深度 0.9995；P5 近似复现须披露；T-CX374 按有效参数检查 |
| M7 `ratio_diff` 未定义 | C.1 定义为 `count_diff / 旧侧 analyzed_samples`；硬条件二用绝对值 |
| M8 identity 含提交号导致无法验证 | D 节：分比对项与只记录项 |
| M9 F3 不唯一且模型表达不了 | C.4 限定单一切点两段；A.3 写明需修订模型 |
| M10 验证侧规模被低估；M5 验证电平缺失 | A.12 子网格与 2 倍上限；B.2 补 M5 验证电平；A.13 测量表 + 对表 |
| Minor：K0 不可达 | C.5 第 7 步重新定义 |
| Minor：P5 小档归类 | B.3 把 16 位 ±1e-5、±3e-5 归入容忍类 P5t |
| Minor：C.6 缺两项披露 | C.6 补 M11 与基频来源 |
| Minor：生成参数不完整 | B.2 合成规则；B.3 P1/P3 定义；B.2 M7 按生成参数；B.4 变化对的相位与长度 |
| Minor：Task 4 接口细节 | Task 4 用 `_resolve_sample_bounds`；终态映射表；M9 比较字段 |
| Minor：冻结记录引用 K3 行 | Task 7 `zone_row_id`、`floor_cut` |
| Minor：验证中止记录 | C.6、Task 8 |
| Minor：Task 9 缺 wheel 与架构测试；dry-run | Task 9 |
| Minor：`include_phase_axis` | A.1 固定启用 |
