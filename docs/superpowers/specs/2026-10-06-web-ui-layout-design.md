# Web UI 布局与中文界面设计

日期：2026-10-06
状态：操作员 2026-10-06 批准，授权实现。§6 两项操作员 2026-10-06 均选推荐（评测摘要移到底部并默认折叠；回归工作台本次不改）。
上位依据：AGENTS.md、`docs/CONTRACTS_V0_2.md` §63（Web UI 合同）、`CONTRACTS_V0_3_CONTEXTUAL.md` §17–§18、§25，D037、D047。
操作员选择（2026-10-06）：接诊放首位、结果区重排、宽屏两栏、界面改中文。

## 1. 现状问题

以 #70 浏览器证明的整页截图为准：

- 页面是一条约 4,300 px 高的单栏，13 个面板依次排开。
- 新的“描述问题”接诊流程排在手动表单之后。
- 诊断结论只是“Outcome: inconclusive”这样的一行文字，和 Trace、Evidence、Rules 等技术面板分量相同。
- 没有内容的面板也会显示，例如“No evidence.”。
- 界面全是英文。

## 2. 改动

只改 `static/index.html`、`static/app.js`、`static/styles.css`。不改 API、报告、服务端、DSP、规则或 prompt。

### 2.1 接诊放首位

- 页面顶部第一块是“描述问题”三步流程（§25 不变）。
- 原手动表单整体收进 `<details id="manual-panel">`，标题为“高级：手动设置上下文”，默认折叠。表单本身、元素 id 和提交逻辑不变；示例预设也在这里。
- 两条路径共用同一个结果区。

### 2.2 结果区重排

- 新增一张“诊断摘要”卡片放在结果区最上方，只用 snapshot 里已有的字段：
  - 结论：`outcome`，用中文名，括号保留原值；
  - 置信度；
  - 诊断模式；
  - 上下文来源：只在 `context_origin` 存在时显示；
  - 第一条 claim 的 `statement`；
  - 报告下载链接。
- 运行状态（Lifecycle）缩成摘要卡上的状态标签。`#lifecycle-panel` 和 `aria-live` 保留。
- 上下文升级（`context_guidance` 与升级控件）紧跟摘要卡，因为它是用户的下一步操作。
- 以下面板改为默认折叠的 `<details>`，放在“技术细节”分组里：
  - 声明上下文、比较资格、因果限制、波形预览、Trace、Evidence、Rules、Knowledge；
  - 折叠后 id 不变，内容渲染逻辑不变。
- 本次运行没有内容的技术面板，在运行结束后整块隐藏，例如没有 Evidence。运行前不显示任何技术面板。
- “已验收评测”（V0.2 79/80 摘要）移到页面底部，单独一块，默认折叠；文字原样保留（T279/T280）。

### 2.3 宽屏两栏

- 视口宽度 ≥ 1100 px 时，左栏是输入（接诊和手动表单），右栏是结果；右栏在滚动时保持可见（`position: sticky`）。
- 窄屏仍是单栏：先输入、后结果。
- 只用 CSS grid，不引入框架（T276 禁止框架和 CDN）。

### 2.4 中文界面

- `<html lang="zh-CN">`。标题、按钮、标签、提示、面板标题、模式名改为中文。
- 被冻结测试或合同钉住的英文原文保留，以“中文（English）”或中文在前、英文原句在后的方式并列：
  - 安全提示 `local single-user/no-auth`；
  - 演示阈值说明（`demonstration`、`1% clipping`、`5% THD`）；
  - 默认问题 `Why does this signal sound distorted?`（它也是提交给诊断模型的问题，不翻译）；
  - 评测面板中的 `held-out Agent slots`、`behavioral-failure`、`outcome error`、`completed/meets_target` 等；
  - 模式名 `Unknown one-WAV signal` / `Declared single tone` / `Compare with clean reference`（T-CX328）；
  - `Optional upgrades:`、`reference WAV`、`nominal fundamental (Hz)`、`stimulus kind single tone`（T-CX328）。
- 服务端返回的文字（claim 内容、错误信息、guidance 摘要）原样显示，不在浏览器里翻译。
- 字段名和枚举值（如 `nominal_single_tone`）在技术细节里保持原样。

## 3. 约束

- 不改任何冻结测试（T276–T280、T-CX117–T-CX119、T-CX268、T-CX275、T-CX326–T-CX328），只在其上新增测试。
- 合同 §63 列出的每个视图仍然存在，只是默认折叠。
- 继续禁止 `innerHTML` 等写入方式、CDN、框架和浏览器端诊断计算。
- 产品默认 prompt、报告文件格式和 API 都不变。HTML/JSON 报告不翻译。

## 4. 测试（新增 ID，T-CX420 起）

| ID | 内容 |
|---|---|
| T-CX420 | 接诊面板在手动表单之前；手动表单在默认折叠的 `<details>` 里，原有元素 id 全部还在 |
| T-CX421 | 摘要卡只读取 snapshot 已有字段（outcome、confidence、mode、context_origin、claims）；技术面板为 `<details>`，id 不变；空面板在运行结束后隐藏 |
| T-CX422 | 宽屏两栏只用 CSS grid，含窄屏单栏的媒体查询；无框架、无 CDN |
| T-CX423 | `lang="zh-CN"`；冻结测试钉住的英文原文全部仍在页面或脚本里；默认问题未翻译 |
| T-CX424 | 浏览器证明（Playwright，桩 planner，不调用模型）：宽屏和手机宽度各截图一次，走完接诊 → 确认 → 诊断，无页面错误、无横向滚动 |

T-CX424 是手工验收记录（截图附在 PR 里），不进 CI，因为 CI 没有浏览器。

## 5. 不做

- 不翻译报告文件和 CLI。
- 不加暗色模式开关，也不改配色体系（只做现有 CSS 变量内的调整）。
- 不改波形预览的取点方式：现在整段一千点看起来像一条黑带。这需要改服务端预览，应单独设计。
- 不动回归工作台页面（`/regression`）。

## 6. 待操作员决定

1. “已验收评测”放页面底部并默认折叠，可以吗？推荐：可以。它是 V0.2 的历史数字，不是当前运行的结果，放在显眼处容易被误读为当前质量。
2. 回归工作台页面以后是否也要改中文？推荐：本次不做，另起。
