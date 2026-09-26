# 工程案例研究：Signal Diagnosis Agent V0.2

> 对照英文原件 [PROJECT_CASE_STUDY.md](PROJECT_CASE_STUDY.md)，以英文契约为准。

## 问题

Scenario S1 提出一个狭窄但 nontrivial 的问题：“Why does this periodic
signal sound distorted?”（为什么这个周期信号听起来失真？）目标不是硬编码一条总是
运行 clipping、FFT、F0 与 THD 的流水线。产品必须让真实 LLM 选择
下一步有正当理由的动作，检查结构化观察，重规划，并在
证据充分时停止。

已接受的诊断空间故意狭窄：clipping、谐波失真，以及在需要时的
基本频率/基频证据。合成信号提供已知 ground truth；有界 PCM WAV 使垂直切片
可交互。

## 为何采用混合架构

产品主张明确要求真实 LLM 在公开路径上演示动态 Tool
选择。真实 LLM 不是可靠的 CI 预言机，因此设计将模型边界与控制器分离：

```text
PlannerModel
    |- RealLLMPlanner      product path
    `- ScriptedPlanner     deterministic test double
```

`DistortionDiagnosisRuntime` 拥有状态转换、Tool 执行、观察
传播、重试、非法动作处理、无进展检测、调用
限制与终止。它不强制固定 Tool 序列。DSP 拥有
数值计算，规则 profile 拥有阈值，LLM 看到的是紧凑
结构化 Evidence 而非原始数组。

这一拆分产生了两层截然不同的验证：

1. 确定性系统验收，覆盖路由、状态、Tool 执行、
   传播、错误与终止；
2. 真实模型行为评测，覆盖 first Tool、重规划、不必要
   动作、停止、grounding 与诊断质量。

## 端到端设计

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

- Signal 仓库不可变，并存储满量程 `float32` 波形。
- DSP 实现可解释的 clipping、频谱、自相关 F0，以及
  谐波分析。
- Tools 将 DSP 结果转换为带稳定 ID 的紧凑 Evidence。
- Rules 对照版本化演示 profile 评估 Evidence。
- Knowledge 检索在策展后的本地 Markdown 语料上确定性进行。
- Agent 选择动作，且必须引用同次运行的 Evidence/rules/knowledge。
- Evaluation 将 Agent 与诚实固定流水线比较。
- 应用层通过 CLI、API、Web UI、
  JSON 与 HTML 暴露同一服务。

## 改进系统的那些失败

项目保留了每一次实质性目标未达标，而不是事后优化叙述。

### 1. 首次官方运行表明“可调用”不等于“被使用”

**现象。** 首次官方 Agent 能诊断若干 cases，却
很少选择新实现的规则与知识动作。

**证据。** 不可变的
[80-slot Phase 4 bundle](evaluations/phase4/bench_official_s1_20260829t162243z/)
为 `completed/below_target`：causal macro F1 0.840，applicable-rule usage
0.513，required-knowledge usage 0，evidence grounding 0.895。

**根因。** Phase 3 证明规则与知识动作可调用且
正确，但真实 planner 并未一致选择它们。确定性
可用性并不能证明产品路径行为。

**决策。** 保持官方包不可变，将 harness 完成
与目标达成分离，并在新的留出运行前加入行为开发门禁。

**修复。** 冻结带显式规则、知识、grounding、重规划与停止指标的加法式
Phase 4.1 行为门禁；仅在开发 split 上调参。

**验证。** 原始包保持逐字节历史证据。
后续活动报告独立的 development/official 身份，而不是
覆盖本次运行。

**教训。** Tool 存在、控制器正确性与模型行为是
不同主张，需要不同证据。

### 2. Prompt 增补修好了使用率，却造成矛盾行为

**现象。** Planner 开始使用规则与知识，但边界、
组合与 inconclusive cases 变得内部不一致。

**证据。**
[v5 development bundle](evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/)
将 rule usage 提升到 0.854，required-knowledge usage 到 1.0，但 causal F1
降到 0.75，grounding 到 0.789，knowledge-citation utilization 到 0.2。
[v6 development bundle](evaluations/phase4_1/development/bench_phase4_1_dev_v6_gate2/)
将 causal F1 提升到 0.969，citation utilization 到 1.0，但 grounding
仍为 0.857，unsupported claims 达到 0.0625。

**根因。** 加法式 prompt 文本与旧示例互相竞争。5% THD
边界即使在谐波证据存在时仍可能被当作“无故障”；
组合失真可能在 clipping 后停止；inconclusive 示例可能
以空 claims 与未引用知识结束。

**决策。** 用连贯的版本化 prompts 取代仅追加补丁，
冻结每一个先前 prompt 身份，并在开发门禁未达标时诚实停止每次活动。

**修复。** v6 成为一份连贯 prompt，而不是 v4/v5 附录，带有
显式边界、组合假设与 inconclusive 引用策略。

**验证。** v6 改善了目标指标，但仍未达到冻结的
grounding 与 unsupported-claim bands，因此未运行官方 v1.1.0 留出，
并保留了 `below_target` 开发包。

**教训。** Prompt 文本是可执行策略。示例与散文必须表达
同一一致的状态机。

### 3. 在继续调 prompt 之前必须先修复评测完整性

**现象。** 仅调 prompt 的 v7 可能看起来改善了行为，却使用了
真实用户请求中不可用的信息。

**证据。** 独立审查发现诸如
`clipping_strong` 这类语义 ID、对其他方面等价的可见上下文却有不同 first-Tool 期望，
以及因果区分依赖隐藏匹配对照的组合 cases。

**根因。** 评测器知道 planner 无法合法观察的区分。在这些条件下更高分数
并不能证明更好推理。

**决策。** Dataset 1.2.0 引入不透明出站 ID、仅基于可见上下文的
first-Tool 公平性、全新 cases/seeds，以及带可见生成参数的单信号组合
失真。官方门禁还要求在加载留出输入或
创建 SDK client 之前，存在完整且身份匹配的开发包。

**修复。** 在冻结的
[Phase 4.2 design](superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md)
下实现 Dataset 1.2.0 与 v7 活动，
包括在任何官方 model/client 工作前做预检身份校验。

**验证。**
[v7 development bundle](evaluations/phase4_2/development/bench_phase4_2_dev_v7_v12_gate3/)
仍未达到 first-Tool selection（0.75）、observation-driven replanning
（0.719）、unnecessary Tool rate（0.405）与 required-knowledge usage（0.2）。
官方留出仍未打开。由于评测完整性现已
可信，这些失败可归因于行为而非标签
泄漏。

**教训。** 只有当模型无法从标识符或不可见评测器假设推断答案时，
留出分数才有意义。

### 4. 失败的 v8 运行暴露了契约/评分错配，而不只是模型未达标

**现象。** v8 正确选择了 first Tool 与知识，但仍
收到系统性 grounding、停止与 unsupported-claim 失败。

**证据。**
[v8 development bundle](evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4/)
记录 first-Tool selection 1.0 与 knowledge usage 1.0，但 evidence grounding
0.849，timely stopping 0.75，unsupported claim rate 0.211。

**根因。** T210 全局禁止了一种在场景下合法的 clipping 特定结束，
而遗留评分代理错误处理了所需的
invalid-Evidence -> NOT_APPLICABLE 规则转换。

**决策。** 不再堆叠另一份 prompt。冻结窄范围 Phase 4.3.1
合规修正：v8.1 澄清合法结束范围，scoring 2.0.0
承认冻结的 invalid-Evidence 语义。Runtime、PlannerContext、
dataset、目标 bands、provider 与 model 保持不变。

**修复。** 实现冻结的
[Phase 4.3.1 correction](superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md)：
连贯的 v8.1 策略加上版本化 scoring 2.0.0，历史 v4–v8
身份不变。

**验证。** v8.1 在授权一次性 80-slot 官方运行之前，于 40 个开发 slots 上通过全部 11 个目标 bands。
两个已接受包仍与每一个失败前驱分离。

**教训。** 当评测与冻结契约不一致时，显式修复评测器
或书面策略；不要训练模型去钻有缺陷代理的空子。

### 5. 已接受门禁对残余失败保持诚实

**开发。** v8.1 在 40 个开发 Agent slots 上通过全部 11 个目标 bands。

**官方。** 一次性 80-slot 留出运行为
`completed/meets_target`：

- causal macro F1: 1.0；
- evidence grounding: 1.0；
- first-Tool selection: 1.0；
- observation-driven replanning: 0.995；
- timely stopping: 1.0；
- unnecessary Tool action rate: 0.0；
- unsupported claim rate: 0.0；
- outcome accuracy: 79/80。

两个 slots 保留行为失败码。其中一个是唯一错误
outcome。聚合满足冻结目标 bands，但 UI、README 与
包继续披露这两个数字。

## 为何固定流水线仍然重要

固定流水线不是产品 Agent。它是运行预定分析序列的诚实基线。它为
Tool 数量、诊断质量与停止行为提供可复现比较。Agent 必须证明
其动态选择正当，而不能因为基线被故意削弱而获胜。

## 把核心做成可演示产品

Phase 5 增加了呈现层，而未把领域逻辑移入适配器：

- 严格、有界的 PCM WAV 解码；
- 五个公开合成 presets；
- 由 CLI 与 FastAPI 共享的一个 `DiagnosisApplicationService`；
- 带真实 queued/running/completed 生命周期状态的原生 Web UI；
- 实际按时间顺序的 Agent trace、Evidence、规则与知识分区；
- 规范 JSON 与自包含 HTML 报告；
- 打包的静态/评测资产与干净 wheel 安装；
- 本地 CPython 3.11/3.12 干净环境验收；
- 两次保留的真实模型产品 Demo 运行，一次 Web preset，一次 WAV CLI。

最终确定性套件包含 1006 个通过测试。真实 Demo 是
独立的产品路径检查，永不成为随机性 CI 要求。

## 增量外部有效性：从单 WAV 模糊性到上下文

已接受的 V0.2 官方基准主要使用合成信号。因此随后的
增量外部 WAV 研究测试了公开录音、在真实录音母带上的受控
失真，以及域外音频。它诚实完成为 `below_target`：系统能处理真实 WAV 输入，但
单 WAV 谐波测量不能一致地确定谐波是新引入还是源中本已存在。

回应不是重新标注这些失败，也不是降低冻结的 1% clipping
与 5% THD 演示阈值。V0.3 在同一 Scenario S1 边界内引入两种显式观察
模式：

- `paired_reference` 将测试录音与其干净参考比较；
- `nominal_single_tone` 使用声明的单音激励契约。

开发运行保留了连续失败，同时实现增加了
确定性情境 DSP、模式感知因果门禁、自动规则闭合，
以及保守恢复指引。v9.11 开发确认在验证重新封存前满足了其
冻结门禁。

最终情境验证冻结 20 个 cases，并以固定 60-slot 顺序一次性运行三个臂：
情境 Agent、无真相确定性固定
流水线，以及无上下文消融。情境 Agent 完成 19/20
slots，达到 16/17 outcome 与 causal exact-set accuracy，harmonic recall 5/5，
clipping recall 5/6，以及对消融的 +4 配对谐波因果优势。

独立审查随后发现评测器缺陷：两个 claim 级指标使用了
17-case outcome 分母，而不是其预注册的动态
总体。原始 `below_target` 输出被保留。TDD 修正加入了
claim 级同次运行引用核算，以及从不可变结果文件的确定性重放。正确评分产生 21/21 grounded claims 与
0/10 unsupported positive claims；全部聚合与角色门禁通过，得到
仅追加裁决 `meets_target`。

该结果故意狭窄。它表明声明的参考或
激励上下文，在一项小规模、许可可追溯的外部/情境研究上，实质改善了谐波归因。它不是官方基准、
工业验证、生产认证、通用音频诊断，也不是
情境最终外部测试。更早的 V0.2 外部 WAV
`below_target` 结果仍是证据链的一部分。

### 简历安全定位

简洁且可支撑的描述是：

> Built and evaluated a hybrid signal-diagnosis Agent combining deterministic
> DSP, versioned causal rules, and LLM planning; designed a sealed three-arm
> external/contextual WAV study where v9.11 achieved 16/17 outcome and causal
> exact-set accuracy, 21/21 grounded claims, and 0/10 unsupported positive
> claims, while preserving failed runs and an append-only scorer correction.

避免声称工业验证、生产就绪、行业标准
阈值、通用音频诊断器，或官方外部
基准。

## 本项目证明了什么

- 在 LLM 周围建立契约优先边界，而不把控制器变成
  产品 Agent。
- 数值与阈值溯源：DSP 计算；profiles 判定；LLM
  解释与规划。
- 跨 Evidence、rules、knowledge、决策与最终 claims 的可追溯性。
- 留出纪律、不可变基准资产，以及显式停止门禁。
- 愿意把评测器缺陷当作一等工程缺陷处理。
- 在一个已测服务之上使用薄呈现适配器，而不是复制
  业务逻辑。

## 局限与下一版本边界

V0.2 仍然狭窄。它不声称通用音频诊断、硬件
鉴定、生产采集覆盖、通用音高跟踪、
行业标准阈值、鉴权、持久化、向量检索，
或部署加固。扩展这些领域需要新的契约、
数据集、测试 ID 与评测门禁，而不是对已接受结果的非正式延伸。

## 证据地图

- [Frozen architecture](ARCHITECTURE_V0_2.md)
- [Frozen contracts](CONTRACTS_V0_2.md)
- [T001–T285 acceptance plan](TEST_PLAN_V0_2.md)
- [D001–D031 decisions](DECISIONS.md)
- [Historical and accepted evaluation bundles](evaluations/)
- [Accepted official v8.1 bundle](evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/)
- [Real product Demo](demo/phase5/v0_2_acceptance/README.md)
- [V0.3 contextual validation acceptance](evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md)
- [Formal specs and implementation plans](superpowers/)

### Demo 校验和可移植性说明

保留的 Demo README 记录了 Windows 验收工作树中的 JSON/HTML 哈希。Git 以 LF 行尾存储这些文本 blob，而 Windows
检出可能物化为 CRLF，因此原始文本文件哈希可能因检出而不同。
WAV 与 PNG 哈希是字节稳定的。官方评测包校验
使用其冻结的 LF 归一化校验和策略，不受影响。已接受的
Demo 文件及其原始表格保持不变。
