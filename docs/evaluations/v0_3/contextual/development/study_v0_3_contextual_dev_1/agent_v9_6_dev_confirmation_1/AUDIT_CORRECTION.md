# v9.6 development confirmation — AUDIT CORRECTION

**Label:** v9.6 remediation development confirmation（审计修正，不是 Task 13 修复）
**target_status:** `below_target`（不变）
**scoring identity:** `signal_diag.contextual_scoring@1.0.0-dev.1`
**范围:** 仅修正审计/评分解释；未改产品代码、未重跑模型、未访问 validation。

## 不变文件（未修改）

- `attempts.json` / `trace.json` / `result.json` / `case_summary.json`（各 case）
- `preflight.json`
- `development_seal/`

## 既有审计产物 SHA-256（修正前，保留原文）

| 文件 | SHA-256 |
|---|---|
| `run_summary.json` | `3742f664ee7487d5ea320826bdec0596bb324a1340ca0644b6af88aeea62d3a0` |
| `audit_report.json` | `cef68d2845f9d062b73fbfd512ff6a9ab309704e9222d5a3f420a05e9c2be883` |
| `STATUS.md` | `fa2caf401804f5e4373cb7a4b58ee991d797d79b4973acefe2cb66b737a77a58` |

新增文件：`corrected_scoring.json`、`AUDIT_CORRECTION.md`（本文件）。

## 原审计错误

原 `audit_report.json` 把行为 `error` / 无 diagnosis 当成可评分的 `ok` 预测：

1. 对 expected causal 为空的 case，空预测被计为 **causal correct**（例如 clean / natural_even → 把 causal 虚增到 **12/17**）。
2. 无 diagnosis 仍计 `evidence_refs_complete=true` → **evidence grounding 虚增到 17/17**。
3. outcome 分子碰巧仍是 7，但因果与 grounding 口径错误。

## 修正方法（failure-as-incorrect）

对冻结 scorer `score_contextual_run`：

- **有 diagnosis**（runtime `success` / `inconclusive` 且 `outcome` 非空）：`ArmResult(status="ok", …)`。
- **行为失败 / 无 diagnosis**：走 scorer 的 `status != "ok"` 路径，使 outcome / causal / grounding **分子不加分**，仍占 scoreable 分母 17。

说明：`ArmResult` 字面量只能是 `ok | infrastructure_failure`；此处使用 non-ok 路径仅为适配冻结 scorer 的 failure-as-incorrect 语义，**不是**把这些槽位改判为基础设施故障。原始 `case_summary.json` 仍记录 `infrastructure_failure=false`。

## 修正后主指标（冻结）

| 指标 | 修正后 | 原审计 |
|---|---|---|
| outcome accuracy | **7/17 ≈ 0.412** | 7/17 |
| causal exact-set | **7/17 ≈ 0.412** | 12/17（错误） |
| evidence grounding | **7/17 ≈ 0.412** | 17/17（错误） |
| planner completion | **10/20 = 0.50** | 未单列 |
| unsupported claim rate | **0/17** | 0/17 |
| inconclusive appropriateness | **6/6** | 6/6 |
| natural_even harmonic FP | **0** | 0 |

门禁：`scoreable_outcome_accuracy_ge_0_80` / `scoreable_causal_exact_ge_0_75` / `evidence_grounding_100` / `planner_completion_ge_0_95` 均为 false。planner completion **10/20 = 0.50**，未达到 ≥0.95 门禁 → **`below_target`**。

## Descriptive full-population metrics

行为失败视为空因果预测（全 scoreable 人群）：

- **harmonic recall = 0/5**
- **clipping recall = 4/6**

这两项仅作描述性全人群指标，不替代下方原生 scorer 输出。

## 冻结 scorer 对行为失败跳过后的原生输出

将 10 个行为失败映射到 non-ok 后，scorer 在 precision/recall 循环里 `continue`（跳过更新）：

- `harmonic_precision` / `harmonic_recall` → **`not_evaluated`**（5 个 harmonic/combined 正类均失败被跳过）
- `clipping_precision` → **4/4**
- `clipping_recall` → **4/4**（2 个 combined 中的 clipping 漏检被跳过，故不等于 descriptive 4/6）

完整原生 aggregate 见 `corrected_scoring.json` → `frozen_scorer_native_output_behavioral_failures_skipped`。

## 根因证据（来自未改动的 traces / results）

1. **evaluate_rules：36 次全部为 `profile_s1_distortion`；`profile_s1_contextual_comparison` = 0。**
2. **5 个 harmonic/combined 正类**均有同次 contextual Evidence：`context_valid=true`，且 `even_harmonic_growth_percent > 5`：

| case_id | role | growth_percent | context_valid |
|---|---|---:|---|
| `a4a0853be9983f8c` | harmonic | 7.23 | true |
| `2be730b9113701de` | harmonic | 9.91 | true |
| `35967af7b71c5b75` | harmonic | 10.34 | true |
| `6fb80bbda391c26c` | combined | 8.81 | true |
| `aa9b4a91b0253c33` | combined | 6.41 | true |

解读：contextual 工具已给出可支持 even-growth 的 Evidence，但 planner 从未对 `profile_s1_contextual_comparison` 做 `evaluate_rules`，随后 finish 被拒 / 重试耗尽 → 行为失败。这是确认失败的核心行为根因，不是基础设施错误。

## 协议声明

- 未修改 prompt / profile / data / 标签 / scoring identity。
- 未访问 validation / final test。
- 未改动 v9.5 Task 13 目录。
- 未 commit、未 push；停止等待审阅。
