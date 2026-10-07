# D057 修订：测试向导提示词 1.1、拒绝记录与留出场景（设计，D059）

日期：2026-10-07
状态：已批准（操作员 2026-10-07，§9 四项均选 A；D059）。
上位依据：D057（第 4 阶段测试向导，§31）、D058（解释层拒绝记录的做法）、D052、AGENTS.md。
起因：真实模型验收 `docs/evaluations/v0_3/guide/live_1/`（wfengq/signal-diagnosis-agent#91）未达门槛。

## 1. 要解决什么

`live_1` 调用模型 40 次，结果如下：

| 指标 | 值 | 门槛 |
|---|---|---|
| 方案正确率 `plan_accuracy` | 0.775 | ≥ 0.9 |
| 参数正确率 `parameter_accuracy` | 0.65 | ≥ 0.9 |
| 数字被拒 `number_rejections` | 0 | = 0 |
| 多余提问 `unnecessary_question_cases` | 11 | 只报告 |
| 退回问卷 `fallback_reasons` | `illegal_output` ×9 | — |

逐条看过 `results.jsonl` 后，失败分三类：

1. **提示词没讲清楚的事实。** 这一类占多数（§2.1）。
2. **9 次输出不合法，但原因看不到**（§2.2）。
3. **1 次模型真的判断错了**（§2.3）。

本设计做四件事：
- 补上拒绝记录；
- 修改提示词；
- 先冻结一组新的留出场景，用来做公正的复测；
- 定下复测的验收方式。

方案目录、问卷、校验规则和门槛都不变。

## 2. 已确认的事实

### 2.1 提示词缺三条事实

- **扫频用的是工具自己生成的测试信号。** 提示词没说这一点，于是 g02、g03、g13、g15 里模型都问了“用哪个测试文件播放”。扫频方案根本不用 `test_file`。
- **采样率只对扫频方案有用。** 扫频要按这个采样率生成测试信号；其他方案分析的是现成录音，采样率直接从文件头读取。可是提示词把 `sample_rate_hz` 写成所有方案的参数，于是 g21、g27、g29、g30、g31、g33、g35 里模型都问了“这段录音的采样率是多少”。
- **接线方式怎么判断。** 提示词只列了三个取值，没说各自对应什么描述：
  - g06（“接在声卡上”）、g08（“record its output with my interface”）、g18（“USB 录音口”）里，模型都没填接线方式，而是去问用户；
  - g15（“USB 声卡带直录功能”）里，模型填了 `line_loopback`，还标成了默认值。这是错的。

### 2.2 9 次 `illegal_output` 看不到原因

出问题的案例是 g22–g26、g28、g34、g37、g38，全部属于录音类方案，而且用户都上传了文件。

输出结构不接受多余的键（`extra="forbid"`），所以可能是模型多写了一个键，也可能是某个值的类型不对。但评测只记录了检查名，没有保存模型原文，无法确认。这与 D058 之前解释层的情况相同。

### 2.3 1 次真实的判断错误

g31 里，模型把干声和压缩后的录音弄反了：参考录音应该是 `dry.wav`，模型却填了 `wet.wav`。

## 3. 改动一：拒绝记录（照 D058 的做法）

- `GuideService` 增加一个仅供程序内部使用的关键字参数 `rejection_sink`，以及 `with_rejection_sink(sink)`。每次模型输出被拒，它收到一条 `GuideRejection(check, detail, raw)`：
  - `check` 是 `illegal_output` 或 §31 校验的检查名；
  - `detail` 是具体原因，例如 pydantic 报错的第一行；
  - `raw` 是模型原文。
- API、CLI、网页和报告都不传这个参数，对外输出不变。
- `guide_eval` 在每一行结果里增加 `rejection_detail` 和 `rejected_draft`，在 `summary.json` 里增加 `rejection_details` 计数。
- 输出文件不留行尾空白。
- 每行结果和 `summary.json` 增加 `prompt_version`。`GuideResult` 已经通过 `guide.prompt_version` 带有版本号，不改。

## 4. 改动二：提示词 `v0.3-s1-guide-1.1`

在 1.0 的基础上只补规则，不改输出结构，不加方案。新增的要点是：

1. **扫频**
   - 测试信号由工具生成，用户只需要播放它并录回。
   - 选 `sweep_levels` 时，`test_file` 和 `reference_file` 填 null，不要问测试文件。
2. **采样率**
   - `sample_rate_hz` 只用于 `sweep_levels`，表示生成测试信号所用的采样率。
   - 其他方案填 null，也不要问；录音自己的采样率会从文件里读取。
3. **接线方式**（只用于 `sweep_levels`）
   - 设备输出用线接到声卡或录音接口再录回，选 `line_loopback`；
   - 用麦克风在空气中拾音，选 `acoustic_mic`；
   - 设备通过 USB 或数字接口直接录下自己的输出，选 `digital_capture`；
   - 描述里看不出来时填 null，并只就这一项提问。不要把接线方式当默认值填。
4. **录音类方案**
   - `test_file` 填用户上传的、要检查的那个文件；
   - `paired_reference` 的 `reference_file` 是正常、原始、处理前的那一段（好的设备、干声、修改前），`test_file` 是有问题、处理后的那一段。
5. **只问缺的东西**
   - `missing_fields` 只能列当前方案用得到的参数：
     - `sweep_levels` 用 `sample_rate_hz`、`level_labels`、`connection`；
     - `existing_recording` 用 `test_file`；
     - `paired_reference` 用 `test_file`、`reference_file`；
     - `nominal_tone` 用 `test_file`、`nominal_fundamental_hz`。
   - 能从描述或默认值得到的参数，不要再问。
6. **格式**
   - 只输出一个 JSON 对象，正好包含规定的五个键，`parameters` 里也只有规定的键；
   - 不要加任何解释文字。

**写法约束：** 这些规则按概念写，不照抄 40 个场景里的具体用语。按 §5，这组场景在改提示词时已经看过，不再作为验收依据。

## 5. 改动三：留出场景（先冻结，再改提示词）

40 个开发场景已经用来定位问题，提示词又是照着它们改的。如果 `live_2` 还只用这 40 个打分，结果会偏高。

因此新增 20 个**留出场景**。先由 Cursor 写入 `docs/evaluations/v0_3/guide/heldout/guide_cases_heldout.json`，单独开 PR 并合并，作为冻结版本；这个 PR 只改文档目录，不影响产品代码身份。之后实现时，再把它逐字节复制到 `evaluation/assets/guide_cases_heldout.json`，并用测试保证两份文件的 SHA-256 相同。格式与 `guide_cases.json` 相同（`guide_cases/1`）。

- **分布：** `sweep_levels` 8 个（线路 3、麦克风 2、数字 2、冲突 1），`existing_recording` 4 个，`paired_reference` 4 个，`nominal_tone` 4 个。
- **语言：** 约三分之一是英文。
- **完整度：** 每个方案至少有一个“信息完整”的场景，用来统计多余提问。
- **顺序：** 留出场景单独提交，并把它的 SHA-256 写进 D059。这个提交必须在提示词 1.1 的提交**之前**。之后不再修改。
- **撰写人：** 见 §9 第 1 项。

`guide_eval` 增加参数 `--cases dev|heldout`，默认 `dev`，保持现有行为。`summary.json` 标明用的是哪组场景。

## 6. 改动四（可选）：多余提问的处理

`missing_fields` 里出现当前方案用不到的参数时，有三种处理办法：

- **A：只报告，校验不拦。** `unnecessary_question_cases` 照常统计。
- **B：校验拒绝。** 新增检查 `irrelevant_field`，被拒就退回问卷。这样会拉低正确率，而用户本来只是多回答一个问题。
- **C：确定性地删掉。** 把无关字段和对应的问题删掉。但问题和字段之间没有可靠的一一对应关系，容易删错。

推荐 A：先靠提示词解决，并继续报告这个数字。

## 7. 验收

- `live_1` 原样保留，结论仍是“未达门槛”。
- 由 Cursor 在新代码上跑 `live_2`，两组场景各跑一次，共 60 次调用：
  - 留出组：`--cases heldout --out docs/evaluations/v0_3/guide/live_2_heldout`；
  - 开发组：`--cases dev --out docs/evaluations/v0_3/guide/live_2_dev`。
- **是否可以开启 `SIGNAL_DIAG_GUIDE_MODEL`，以留出组为准：** 方案正确率 ≥ 0.9，参数正确率 ≥ 0.9，数字被拒 = 0。门槛与 D057 相同，不变。
- 开发组只作参考，用来和 `live_1` 对比。
- 如果留出组仍未达门槛，就按 `rejection_detail` 判断下一步，需要另起设计。不在没有新留出组的情况下反复调提示词。

## 8. 合同与测试

- **合同：** §31 增加小节 §31.1，写明提示词 1.1 的规则、`rejection_sink`、新增字段、留出场景和 `--cases` 参数。不改 §31 已有正文的含义。
- **新测试编号 T-CX498–T-CX502：**
  - **T-CX498：** 提示词版本是 `v0.3-s1-guide-1.1`，并包含 §4 的每一条规则（扫频不要测试文件、采样率只用于扫频、三种接线方式、参考录音的定义、每个方案用到的参数）；适配器仍只发送描述文字、文件名和采样率。
  - **T-CX499：** 拒绝记录器能收到非法 JSON、多余的键、校验失败三种情况的检查名、原因和原文；正常草稿和问卷请求不产生记录；API 输出不变。
  - **T-CX500：** 留出场景共 20 个，分布符合 §5，每个预期方案都能通过校验；与开发场景没有重复文字；文件的 SHA-256 与 D059 记录一致。
  - **T-CX501：** `guide_eval --cases heldout` 离线运行不调用模型，结果全对；输出包含 `rejection_detail`、`rejected_draft`、`rejection_details`、`prompt_version` 和场景组名；没有行尾空白和密钥文字。
  - **T-CX502：** 只在 §6 选 B 或 C 时才有，测试对应的行为。
- 已有的 T-CX483–T-CX493 全部保持通过。只有写明提示词版本的那一处断言随版本更新，其余不改。
- 照规则在 `code_identity_amendment.json` 末尾追加身份行。

## 9. 操作员决定

1. **留出场景由谁写**
   - A（推荐）：由 Cursor 写。只给它 §5 的分布要求和方案目录，不给它 §4 的提示词改动，然后单独提交并冻结。之后我才写提示词。
   - B：由我写。先提交并冻结，再写提示词。这样较省事，但出题和改提示词是同一方，独立性弱一些。
   - C：由操作员写。
2. **多余提问的处理（§6）**
   - A（推荐）：只报告。
   - B：校验拒绝。
   - C：确定性地删掉。
3. **验收依据**
   - A（推荐）：以留出组为准，开发组只作参考。
   - B：两组都要达到门槛。
4. **拒绝记录**
   - A（推荐）：保存完整原文（`rejected_draft`），与 D058 相同。
   - B：只保存检查名和原因。

## 10. 不改变的东西

- 方案目录、问卷、确认流程、§31 的各项校验和数字规则不变。
- 门槛不变：方案正确率 0.9、参数正确率 0.9、数字被拒 0。
- 40 个开发场景和 `live_1` 不变。
- 引擎、扫频测试、解释层和各项规则不变。
- `SIGNAL_DIAG_GUIDE_MODEL` 在留出组通过之前不开启。
- 我不调用真实模型，`live_2` 由 Cursor 运行。
