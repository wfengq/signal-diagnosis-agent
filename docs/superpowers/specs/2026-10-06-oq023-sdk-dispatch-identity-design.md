# OQ-023 方案 A：SDK 观测标识改为 httpx2

日期：2026-10-06
状态：操作员 2026-10-06 批准（OQ-023 方案 A），授权实现。
上位依据：AGENTS.md（Scope gates）、`docs/OPEN_QUESTIONS.md` OQ-023、D038–D041、D046、`CONTRACTS_V0_3_CONTEXTUAL.md` §21。

## 1. 问题

锁定的 `openai==3.6.0` 通过自带的 `httpx2`（2.12.0）发请求。审计过的 SDK 观测档案却记录：

- `native_http_family="httpx"`；
- `native_http_version` 取自 `httpx.__version__`，值为 0.28.1；
- `native_dispatch_hook="httpx.AsyncClient.send"`。

版本审计也只钉住 `httpx`。所以 `httpx2` 升级不会被发现。

2026-10-06 已对关闭的本地端口实测，未调用模型：观测按实例包装客户端自己的传输层，能看到每次发送。错的只是标识和审计，计数没有问题。

## 2. 改动范围

### 2.1 产品代码

- **`agent/provider_telemetry.py`：**
  - `native_http_family="httpx2"`，版本取自 `httpx2.__version__`；
  - 分发钩子标签改为 `httpx2.AsyncClient.send`；
  - 新增 `_AUDITED_HTTPX2_VERSION = "2.12.0"`，不符时给出阻断原因 `httpx2_version_drift`；
  - 原有 `httpx`、`httpcore` 版本核对保留：SDK 仍然导入 `httpx`，保留不损失任何检查。
- **`evaluation/planner_ablation/v2/resource_capability.py`：** `_NATIVE_DISPATCH_HOOK` 同步改为新标签，否则它与观测档案对不上。

### 2.2 测试

起草时以为下列 dev_2 测试把旧标签写死成“已审阅身份”、需要改夹具：

- `tests/evaluation/planner_ablation/v2/test_codex_revise_gates.py`
- `tests/evaluation/planner_ablation/v2/test_codex_revise_round2.py`
- `tests/evaluation/planner_ablation/v2/test_resource_budget.py`
- `tests/evaluation/planner_ablation/v2/test_resource_candidate.py`
- `tests/evaluation/planner_ablation/v2/test_resource_telemetry.py`

实现时核实：这些夹具自成一体，不与已安装的 SDK 比对，改动后全部通过，无需修改。`tests/agent/test_provider_telemetry.py` 同样无需修改。实际只新增 T-CX425–T-CX427。

### 2.3 不改

- `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/` 下所有文件，包括 `OFFLINE_ACCEPTANCE.md`、`RESOURCE_BOUNDS.md` 中的旧标签：它们是历史记录。
- 冻结的 V0.2 合同 §§1–64、产品 prompt、诊断行为。
- `resource_capability.py` 中 D041 的 HTTP 发送系数身份字符串（`openai==3.6.0;httpx==0.28.1`）：它是 D041 的历史接受记录，属于已停止的 dev_2。

### 2.4 身份记录

`agent/` 有改动，产品树哈希会变。按惯例在 `code_identity_amendment.json` 末尾追加一行（`model_calls=0`），并在 `test_v03_prompt_v9_11.py` 里钉住上一行的哈希。

## 3. 合同与测试

- **合同：** 在 `CONTRACTS_V0_3_CONTEXTUAL.md` §21 之后追加 §21.x，写明观测档案的分发族、版本和钩子标签以实际分发的 HTTP 客户端为准，审计同时钉住 `httpx2`。
- **决策：** D048（OQ-023 方案 A）。
- **新测试：**

| ID | 内容 |
|---|---|
| T-CX425 | 审计档案的 `native_http_family` 等于 `type(AsyncOpenAI(...)._client)` 所在的顶层模块（`httpx2`），版本等于该模块的 `__version__` |
| T-CX426 | `httpx2` 版本与审阅值不符时，档案 `supported=False`，并给出 `httpx2_version_drift:…` |
| T-CX427 | 对关闭的本地端口发一次请求（不调用模型），附加观测后发出成对的 SdkAttempt 和 HttpSend 开始/结束事件 |

## 4. 风险

- dev_2 的历史 Markdown 仍写旧标签，读者可能混淆。缓解：D048 写明旧标签只属于历史记录。
- 以后升级 `openai` 时，`httpx2` 版本可能一起变。新的阻断原因正是为了让这种变化显式暴露。
