# D055 修订：解释层措辞检查与验收记录（设计）

日期：2026-10-07
状态：草案，等待操作员批准（§8）。
上位依据：D055（第 3 阶段解释层，§30）、D052、AGENTS.md。
起因：真实模型验收 `docs/evaluations/v0_3/explanation/live_1/`（wfengq/signal-diagnosis-agent#87）通过率 0.82，低于 0.9 的门槛。

## 1. 要解决什么

`live_1` 共调用模型 50 次，41 份解释通过校验，9 份退回模板：

| 原因 | 次数 |
|---|---|
| `validation_failed:wording` | 8 |
| `validation_failed:fault_mismatch` | 1 |

结果文件只记了检查名。没有记被拒的原文，也没有记命中的是哪个词。因此单看 `live_1`，无法区分模型真的违规和校验误杀。

本设计做两件事：
- 补上验收记录，让下一次运行能看到每次拒绝的具体原因；
- 修正措辞检查里两处已经能从代码和数据确认的误杀来源。

提示词（`v0.3-s1-explain-1.0`）、材料包、模板、0.9 门槛和人工抽查要求都不变。

## 2. 已确认的事实

### 2.1 材料包自己带着“标准”一词

解释材料包里的知识条目来自知识库，其中两段原文是：

- `knowledge/corpus/clipping.md`：“thresholds are configured demonstration limits, not universal standards.”
- `knowledge/corpus/harmonic_distortion.md`：“limits are demonstration thresholds, not universal standards.”

这是一句免责声明，意思是“这些是演示值，不是通用标准”。模型照着材料复述这句话很正常。但措辞检查只要看到 `standard` 就拒绝，不管前面有没有否定。

用 `live_1` 的 50 个案例离线核对（重新生成材料包，不调用模型）：

| 材料包里有 “standard/标准” | 案例数 | 其中措辞检查失败 |
|---|---|---|
| 有 | 22 | **8** |
| 没有 | 28 | **0** |

8 次措辞失败全部出现在带这句免责声明的案例上。这还不能逐条证明就是这句话触发的（原文没保存，见 §3），但相关性非常强。

### 2.2 英文按子串匹配

当前检查用 `word.lower() in text.lower()`，因此：

- `SLA` 命中 slightly、translate、isolated；
- `IEC` 命中 pieces；
- `limit` 命中 limited、limitation，这时又会要求句子里出现 demo，否则拒绝。

材料包里就有“explain the limitation”这样的原文（`sweep_noisy` 等案例）。这类误杀在 `live_1` 里有没有发生无法确认，但它是确定的缺陷。

### 2.3 那 1 次 `fault_mismatch`

案例 `0b4fabbb2d7eae08`，结论为“无法判定”。原因同样无法从 `live_1` 确认。本设计不改这项检查，只靠 §3 的记录在下一次运行里看清楚。

## 3. 改动一：验收记录写清拒绝原因

- `ExplanationRejected` 保留 `detail`（例如 `forbidden wording 'standard'`、`number 12 is not a cited value`）。现在只在异常消息里，不能单独取用。
- `ExplanationService` 增加一个仅供程序内部使用的关键字参数 `rejection_sink`（默认无）。每次模型输出被拒（非法 JSON 或校验失败）时，把下面三项交给它：
  - 检查名；
  - 详细原因；
  - 模型原文。

  API、CLI、网页和报告都不传这个参数，对外输出不变。
- `explanation_eval` 用这个参数，在 `results.jsonl` 的每一行增加：
  - `rejection_detail`（未被拒时为 `null`）；
  - `rejected_draft`（模型原文，未被拒时为 `null`）。

  `summary.json` 增加 `rejection_details` 计数（按详细原因统计）。
- `REPORT.md` 由 Cursor 照常撰写。有了这些字段，报告可以直接列出被拒原文和命中的词。

模型原文只是模型返回的解释文字，不含密钥。写入前沿用现有的密钥扫描。

## 4. 改动二：措辞检查（`explain-validator-1.1`）

### 4.1 英文按整词匹配

- 英文禁用词和阈值词改用整词匹配，允许复数：
  - `\bstandards?\b`、`\bSLAs?\b`、`\bIEC\b`、`\bAES\b`、`\bcompliant\b`、`\bcertified\b`；
  - `\bthresholds?\b`、`\blimits?\b`。
- limited、limitation、slightly、pieces 这类普通单词不再触发。
- 中文没有词边界，仍按子串匹配。禁用词表本身不变，不删任何词。

### 4.2 只放行一种句式：对“标准”的否定式免责声明

放行条件必须同时满足以下三条：

1. 命中的禁用词是 `standard(s)` 或 `标准`。其他禁用词（合格、达标、认证、IEC、AES、SLA、compliant、certified）一律不放行。
2. 禁用词前面紧挨着否定，中间最多隔两个限定词：
   - 英文：`not` 或 `rather than`，接 0–2 个 `a / an / any / universal / industry / official / general`，再接 `standard(s)`；
   - 中文：`不是`、`并非` 或 `而非`，接 0–2 个 `任何 / 通用 / 行业 / 官方 / 的`，再接 `标准`。
3. 同一句里有 `演示` 或 `demo`，也就是说这句话确实在说“这是演示值”。

这些写法照常拒绝（都要写成测试）：
- meets the standard
- not meeting the standard
- 符合标准
- 不符合标准
- 未达标
- 行业标准要求…
- not universal standards（句中没有 demo）

这些写法放行：
- These are demonstration thresholds, not universal standards.
- 这些阈值是演示值，不是通用标准。

阈值词规则不变：提到阈值时，句中必须出现“演示/demo”。

### 4.3 版本

- 新增常量 `EXPLAIN_VALIDATOR_VERSION = "explain-validator-1.1"`（1.0 指 `live_1` 使用的版本）。
- `ExplanationResult` 和 `summary.json` 各增加一个字段 `validator_version`。这是对外 JSON 的新增字段，不改动已有字段。
- `code_identity_amendment.json` 照规则追加一行。

## 5. 验收

- `live_1` 原样保留，结论仍是“未达门槛”。它的被拒原文没有保存，无法事后重算，报告里照实写明。
- 由 Cursor 在新代码上跑 `live_2`：
  - 同样 50 个案例，同一个提示词和模型；
  - 门槛仍为 0.9；
  - 人工抽查改用 `live_2` 的 20 份样本。
- `live_2` 达到门槛、且人工抽查没有发现错误陈述之前，`SIGNAL_DIAG_EXPLAIN_MODEL` 不开。
- 如果 `live_2` 仍未达门槛，就看 `rejection_detail`：
  - 若是模型真的写了违规措辞，下一步是另起设计，修改提示词（`explain-1.1`）；
  - 不再继续放宽校验。

## 6. 合同与测试

- §30 增加小节 §30.1：记录 §4 的规则和版本号，以及 §3 的记录字段。不改动 §30 已有正文的含义。
- 新测试编号：
  - T-CX494：英文整词匹配。普通单词不误杀，禁用词复数仍被拒。
  - T-CX495：“标准”的免责声明放行，§4.2 列出的反例全部被拒。
  - T-CX496：`rejection_sink` 能收到检查名、原因和原文；API 返回内容不变。
  - T-CX497：验收脚本输出 `rejection_detail`、`rejected_draft`、`rejection_details` 和 `validator_version`。离线运行不调用模型。
- 已有的 §30 测试（T-CX466–T-CX476）全部保持通过，不改断言。

## 7. 不改变的东西

- 提示词、材料包版本（`explain-packet-1.0`）、模板（`explain-template-1.0`）、下一步菜单不变。
- 知识库原文不变（属于 V0.2 资产）。
- 数字、引用、故障一致性、结论覆盖等其他检查不变。
- 0.9 门槛和人工抽查要求不变。
- 不跑真实模型；`live_2` 由 Cursor 执行。

## 8. 操作员决定

1. **放行范围**
   - A（推荐）：按 §4.2 只放行“标准”的否定式免责声明，并要求同句有“演示/demo”。
   - B：不放行，只做整词匹配和记录。这样 §2.1 那 8 例大概率仍会失败，要等 `live_2` 的原文再决定。
2. **验收脚本保存模型原文**
   - A（推荐）：被拒时保存完整原文（`rejected_draft`）。
   - B：只保存检查名和详细原因。
3. **版本字段**
   - A（推荐）：`ExplanationResult` 和 `summary.json` 增加 `validator_version`。
   - B：只靠代码身份行区分，不加字段。
4. **验收方式**
   - A（推荐）：`live_2` 完整重跑 50 例，门槛和人工抽查都不变。
   - B：只重跑 `live_1` 失败的 9 例（不推荐：通过率的分母会变，与 `live_1` 不可比）。
