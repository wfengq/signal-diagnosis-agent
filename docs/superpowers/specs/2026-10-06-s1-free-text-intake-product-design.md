# S1 自由文本接诊产品化设计（草案）

日期：2026-10-06
状态：草案，待操作员审批。本文件不授权任何实现、真实模型运行或合同修改。
上位依据：AGENTS.md（Scope gates）、`docs/CONTRACTS_V0_3_CONTEXTUAL.md` §17–§18、§24.1，D037、D045。
结果依据：`docs/evaluations/v0_3/agent_increment/STUDY_S1_AGENT_INCREMENT_1_REPORT.md`。

## 1. 为什么做

H1 留出集上，T1（自由文本 → 上下文）agent 22/24、最强固定流程（B1 正则接诊）17/24，增量 +5，过了预注册的 +3 线。T2（定位）增量为 0，不在本设计范围内。

T1 的能力目前只在研究工具里完整走通。产品里虽然已有接诊入口（#53），但它停在“草稿”：

| 现状 | 位置 |
|---|---|
| `POST /api/v1/intake/draft` 返回草稿 JSON | `app/api.py` |
| `signal-diag intake draft` 只打印草稿 JSON | `app/cli.py` |
| Web UI “Free-text intake”面板只显示原始 JSON，提示用户“把确认的字段手动抄到上面的表单再提交” | `static/index.html`、`static/app.js` 的 `requestIntakeDraft()` |
| UI 只发送文件名，`sample_rates_hz` 恒为空 | 同上 |
| 没有确认界面，没有“从草稿直接诊断”的路径；CLI 也没有 | — |

所以用户今天拿不到 T1 的好处：草稿要靠自己读 JSON、再手动转填。本切片把这一段补成一个完整、可演示的流程。

## 2. 目标与非目标

目标：

1. Web UI：写描述 + 选文件 → 得到草稿 → 逐字段确认或修改（展示模型提的问题）→ 一键诊断。
2. CLI：同样的“草稿 → 确认 → 诊断”，可交互，也可全部用参数给出（便于脚本和测试）。
3. 诊断仍走已有的 `POST /api/v1/contextual-runs/wav` / `submit_contextual_wav`，校验不变。

非目标：

- 不改诊断 planner：产品默认仍为 `v0.3-s1-planner-9.11`，不切 v9.15。
- 不做 T2 定位的产品化。
- 不加规则、阈值、DSP 或新诊断模式。
- 不改 intake prompt（仍为 `v0.3-s1-intake-1.1`）和请求设置。
- 不做持久化、鉴权、部署。
- 不新增真实模型运行，除非 §8 的验收小样本获单独授权。

## 3. 不变的约束

这些都来自 §24.1 和 D037，本设计只是把它们落到界面上：

1. **草稿是用户的说法，不是测量结果。** 未确认的字段不进入诊断。
2. **标称频率只能来自文字或用户输入**，绝不由测得的 F0 回填。草稿里的数字已经由 §24.1 的可采纳规则过滤（必须等于文字中出现的数，或其 kHz 换算）。
3. **模型只看文字和文件元数据**（文件名、哪个是测试文件、采样率）。WAV 字节不发给 intake 模型。
4. **默认单文件。** 必要字段没确认就降级为 `single_signal`（D037），并照常给出 `context_guidance`。
5. **`assertion_source` 保持 `user_supplied`。** 用户确认后的上下文就是用户提供的上下文。
6. **缺凭据不回退。** intake 和诊断都需要已配置的真实 planner；缺凭据返回 `planner_not_configured`，不回退到 `ScriptedPlanner`，也不回退到正则接诊。

## 4. 流程

```text
用户：描述文本 + 1–2 个 WAV（第一个为测试文件，可改）
  │
  ├─(浏览器本地) 读 WAV 头 → 采样率；字节留在页面内存
  │
  ▼
POST /api/v1/intake/draft  {text, filenames, test_file, sample_rates_hz}
  │   模型只见文字与元数据
  ▼
ContextDraft（mode / nominal_fundamental_hz / reference_file / stimulus_kind /
             missing_fields / questions / asked_fields）
  │
  ▼
确认表单：每个字段显示草稿值和来源（“来自您的描述”），可改；
          questions 原样显示在对应字段旁；
          每个字段须用户确认（勾选或修改即视为确认）
  │
  ▼
ConfirmedContext → 组装 → POST /api/v1/contextual-runs/wav（现有校验）
  │   test 字节、可选 reference 字节、mode、nominal Hz、stimulus_kind
  ▼
现有 contextual 结果视图（含 context_guidance 与升级入口，§17–§18）
```

### 4.1 由确认结果组装提交

| 用户确认的 mode | 必要字段 | 字段未全部确认时 |
|---|---|---|
| `paired_reference` | `reference_file`（必须是已选文件之一，且不是测试文件） | 降级为 `single_signal`，不带参考字节 |
| `nominal_single_tone` | `nominal_fundamental_hz`（>0）且 `stimulus_kind = single_tone` | 降级为 `single_signal`，不带标称字段 |
| `single_signal` | 无 | — |

降级时界面明确写出“因为 X 未确认，按单文件诊断”。不做静默降级。组装规则放在一个纯函数里（服务端一份、`app.js` 一份），两边由同一组表驱动测试覆盖（见 §7）。

`stimulus_kind = unknown` 或空：不能走 `nominal_single_tone`，确认表单里需要用户选 `single_tone` 才能提交该模式。

### 4.2 提交给诊断的问题文本

待决（§9 决策 1）。推荐：沿用现有中性诊断问题（与 contextual 表单当前默认一致），不把用户描述原文作为 `user_request` 送进诊断 planner。理由：描述里的上下文已经结构化并经确认；原文再进诊断 prompt 会让 planner 看到未确认的说法，违背约束 1。

## 5. Web UI 改动

只改 `static/index.html`、`static/app.js`（以及样式）。

1. 接诊面板改为三步：**描述与文件** → **确认上下文** → **诊断**。删掉“手动抄到上面的表单”的提示。
2. 文件选择后，在浏览器里只解析 WAV 头（RIFF/fmt 块）取采样率，填入 `sample_rates_hz`；解析失败就留空，不阻塞。字节只保存在页面内存里（与 §18 的 held-bytes 做法相同）。
3. 允许用户指定哪个文件是测试文件（默认第一个）。
4. 确认表单：
   - mode：单选，默认选草稿值；
   - 标称频率：数字输入，预填草稿值，旁注“来自您的描述”；
   - 参考文件：下拉，只列除测试文件外的已选文件；
   - 激励类型：`single_tone` / 不确定；
   - `questions` 显示在对应字段旁（按 `asked_fields` 对位，对不上的放在表单顶部）；
   - `missing_fields` 里的字段默认未确认，并高亮。
5. “诊断”按钮显示即将提交的最终模式（含降级说明），再提交。
6. 结果沿用现有 contextual 结果视图；`context_guidance` 的升级入口照常工作。
7. 原始草稿 JSON 收进一个默认折叠的“查看草稿原文”，便于演示和排错。

## 6. CLI 改动

新增 `signal-diag intake diagnose`，保留 `intake draft` 不变：

```text
signal-diag intake diagnose --text "..." --test-file a.wav [--file b.wav]
    [--yes | --interactive]
    [--mode ...] [--reference b.wav] [--nominal-fundamental-hz F] [--stimulus-kind single_tone]
    [--output text|json] [--html-output PATH] [--channel ...]
```

- 先调 intake 得到草稿并打印（字段、问题、缺失项）。
- `--interactive`（终端为 TTY 时的默认）：逐字段问“保留 / 修改 / 不确认”。
- `--yes`：接受草稿中已有、且不在 `missing_fields` 里的字段；其余视为未确认。
- 显式参数（`--mode`、`--reference` 等）覆盖草稿，视为用户确认。
- 组装规则与 §4.1 相同（同一个服务端纯函数），然后调用 `submit_contextual_wav`，输出与 `diagnose contextual` 一致。
- 非 TTY 且既无 `--yes` 也无显式参数时报错退出，不猜。

CLI 交互方式待决（§9 决策 3）。

## 7. 合同与测试

合同（追加，不改已有文字）：在 `CONTRACTS_V0_3_CONTEXTUAL.md` 新增 §25“Free-text intake product flow (D047)”，写明：

- §4.1 的组装与降级表；
- 字段只有经用户确认才进入 `ConfirmedContext`；
- 诊断问题文本的规则（按决策 1）；
- UI 只发送 WAV 头元数据，字节不离开浏览器直到诊断提交；
- CLI `intake diagnose` 的参数与非 TTY 行为。

新决策 D047（设计批准后写入）。

测试 ID 从 T-CX411 起（全部离线，intake 用 `intake_planner_factory` 注入脚本化草稿，诊断用现有测试 planner 替身，均为显式注入，不是回退）：

| ID | 内容 |
|---|---|
| T-CX411 | 组装纯函数：§4.1 表格逐行（含每种降级），以及 reference 等于测试文件、未知 reference 名、`stimulus_kind=unknown` 被拒 |
| T-CX412 | 未确认字段不进入提交：草稿含 nominal 但未确认 → 提交为 `single_signal` 且无标称字段 |
| T-CX413 | 标称频率不从测量回填：草稿无数字时，提交中 `nominal_fundamental_hz` 为空，与 WAV 内容无关 |
| T-CX414 | API 端到端：draft → 组装 → `contextual-runs/wav`，结果 `assertion_source == user_supplied`，模式与确认一致 |
| T-CX415 | CLI `intake diagnose --yes` 与显式参数覆盖；非 TTY 无确认参数时退出码非 0 |
| T-CX416 | CLI 交互：脚本化 stdin 走完“保留/修改/不确认”三种分支 |
| T-CX417 | 缺凭据：intake 与诊断均返回 `planner_not_configured`，无任何回退路径被调用 |
| T-CX418 | Web UI（Playwright，离线桩）：选文件 → 草稿 → 确认 → 诊断，显示降级说明；WAV 字节只出现在诊断提交请求中，不在 draft 请求中 |
| T-CX419 | `app.js` 与服务端组装规则一致：同一组表驱动用例在浏览器内执行，结果与 T-CX411 相同 |

身份记录：本切片不改 `agent/`。若实现最终未触及 `agent/` 与产品树哈希覆盖的路径，就不追加 `code_identity_amendment.json`；若触及，照旧追加一行并在 `test_v03_prompt_v9_11.py` 钉住上一行哈希。

## 8. 验收

1. 离线：上表测试全部通过；全量 pytest、Ruff、mypy、架构测试、`git diff --check`。
2. 浏览器证明：本地 `signal-diag serve` + Playwright 截图三步流程（桩 planner），截图入 PR。
3. 真实模型小样本（需单独授权，交 Cursor）：用 **开发集** T1 的 6 例（不碰留出集），走 CLI `intake diagnose --yes`，每例上限 = 1 次 intake + 现有单次诊断的模型调用上限，阶段总上限在交接 prompt 里写死并由工具强制。只核对：流程跑通、确认后的模式与研究中 agent 草稿一致、无密钥泄漏。这不是新的质量数字，不与 H1 比较，也不替代 V0.2 的 79/80。

## 9. 待操作员决定

1. **诊断问题文本**：
   - A（推荐）：用现有中性诊断问题，描述原文不进诊断 planner；
   - B：把描述原文作为 `user_request`。
2. **报告来源标注**：
   - A（推荐）：报告上下文区追加一行“上下文来源：自由文本草稿，经用户确认”（仅展示，`assertion_source` 仍为 `user_supplied`）；
   - B：报告不变。
3. **CLI 交互**：
   - A（推荐）：TTY 默认交互，`--yes` 与显式参数用于脚本；
   - B：只做参数式，不做交互。
4. **§8 第 3 步真实小样本**：做 / 不做（不做则验收只到离线 + 浏览器证明）。

## 10. 风险

- **用户“一路确认”**：确认表单可能被不读就点过。缓解：`missing_fields` 默认不确认；降级说明写在诊断按钮上。
- **浏览器解析 WAV 头**：只读头部，失败留空，不影响诊断（采样率只用于草稿元数据）。
- **两份组装逻辑漂移**：由 T-CX419 用同一组用例约束。
- **范围蔓延到 T2 / planner 切换**：本设计明确不做；如要做，另写设计。
