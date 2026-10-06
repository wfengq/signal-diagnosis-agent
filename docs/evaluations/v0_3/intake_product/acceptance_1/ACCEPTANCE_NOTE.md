# D047 接诊产品流程小样本验收：说明

本目录是 2026-10-06 的一次真实模型运行（PR #72，检出点 `a474761`，开发集 T1 的 6 例，`intake diagnose --yes`）。目录内文件保持原样；本说明只补充解读，不改任何记录。

## 结论

流程验收通过：6 例 CLI 退出码均为 0；每份报告 `context_origin=intake_confirmed`、`assertion_source=user_supplied`；输出中没有凭据；产品默认 prompt 仍为 `v0.3-s1-planner-9.11`。这不是质量评测：诊断结论不计分，不与 H1 比较，不替代 V0.2 的 79/80。

## `http_calls: 0` 不是真实调用次数

`summary.json` 中每例 `http_calls` 为 0，`http_calls_total` 为 0。这是交接脚本的缺陷，不是运行没有调用模型：

- 脚本在 `httpx.AsyncClient.send` 上计数并执行上限。锁定的 `openai==3.6.0` 通过自带的 `httpx2.AsyncClient` 发送请求，该钩子一次也没有被调用（本地对关闭端口复现，计数为 0）。
- 因此本次“每例 15 次、全程 90 次”的上限没有被脚本执行。
- 由报告推算的实际调用：每例 trace 有 3 次 planner 决策（2 次工具调用、1 次结束），加 1 次接诊，约每例 4 次，6 例约 24 次。trace 是否记录失败重试未核实；运行时结构上限为每例约 14 次（1 次接诊 + 最多 8 次工具调用、1 次结束、2 次重试、2 次无进展），即全程不超过 84 次，低于授权的 90 次。
- `agent_increment` 研究（含 H1）的计数在 SDK 的 `chat.completions.create` 处，不受影响。

## 与研究确认模式不一致的两例

| 用例 | 文字 | 本次提交 | 研究第 5 轮确认 | 说明 |
|---|---|---|---|---|
| dev-t1-00 | 1000 Hz 正弦，听着干净。 | `nominal_single_tone` | `single_signal` | 草稿给出 1000 Hz、单音，且未列缺失字段，`--yes` 按 §25.4 接受。清单真值是单文件；这正是 H1 报告记过的开发集干净对照标签与文字矛盾。 |
| dev-t1-10 | 哎这个听着破，频率好像写了 440 Hz。 | `single_signal` | `nominal_single_tone` | 模型把 `stimulus_kind` 列为缺失，`--yes` 不接受，按 §25.1 降级并在 stderr 写明原因。研究中由模拟用户补上该字段。 |

两例都是 §25 规定的行为，不是缺陷。

## 以后的交接脚本

真实模型运行的调用计数与上限放在 SDK 边界（`client.chat.completions.create`，发送前预留），不要放在 HTTP 库的 `send` 上：SDK 可能使用自带或改名的 HTTP 客户端。
