# Workstream C Implementation Report

**Date:** 2026-09-02  
**Prompt:** `v0.3-s1-planner-9.0`  
**Status:** Complete — stopped before real-model tuning

---

## 1. 修改了哪些文件

| File | Change |
|------|--------|
| `src/signal_diag/agent/prompts_v03.py` | **New** — v9.0 prompt built from frozen v8.1 text |
| `src/signal_diag/agent/planner.py` | Product `RealLLMPlanner` → v9.0; added `_Phase4V8_1RealLLMPlanner` pin |
| `src/signal_diag/app/composition.py` | Certified default prompt → v9.0 |
| `src/signal_diag/evaluation/runner.py` | v8.1 campaigns use `_Phase4V8_1RealLLMPlanner` |
| `tests/agent/test_v03_workstream_c_prompt_policy.py` | T-C-001..006 runtime + prompt tests |
| `tests/agent/test_phase4_3_1_prompt_v8_1.py` | v8.1 frozen via pinned planner; product → v9 |
| `tests/agent/test_phase4_3_1_v8_1_runtime.py` | v8.1 runtime uses pinned planner |
| `tests/agent/test_real_llm_planner.py` | Product prompt version → v9.0 |
| `tests/evaluation/test_phase4_3_1_v8_1_runner.py` | v8.1 builder uses pinned planner |
| `tests/app/test_service.py` | Default product identity → v9.0 |
| `tests/test_architecture_boundaries.py` | v8.1 builder expects pinned planner class |

**Preserved unchanged:** `src/signal_diag/agent/prompts.py` (v8.1 bytes + SHA-256)

---

## 2. v9.0 prompt 核心行为变化

1. **§3 语义澄清（EV-C030 部分）**  
   `rule_thd_acceptable` FAIL 仅表示谐波含量相对阈值升高；**本身不足以**建立 causal `harmonic_distortion`。

2. **禁止 LLM 主观 heuristic**  
   不得仅凭 THD 幅度或相对谐波模式猜测“自然 vs 注入”谐波。

3. **§9 新 inconclusive 路径（EV-C030）**  
   当 `valid=true` + THD FAIL + 无 clipping/其他失真机制 Evidence → **inconclusive 为合法 finish**；需 same-run `evidence_refs`、`rule_refs`、非空 `limitations`。

4. **§10** 原 output contract 顺延编号；无 numeric threshold 硬编码（EV-C031）。

---

## 3. T-C-001 ~ T-C-006 结果

| Test | Result |
|------|--------|
| T-C-001 inconclusive accepted (valid THD FAIL, no clipping) | **PASS** |
| T-C-002 refs + limitations required | **PASS** |
| T-C-003 combined supported_fault not regressed | **PASS** |
| T-C-004 no numeric thresholds in prompt | **PASS** |
| T-C-005 v8.1 SHA frozen + v9.0 present | **PASS** |
| T-C-006 §3 THD FAIL ≠ causal harmonic | **PASS** |

---

## 4. v8.1 regression 结果

| Suite | Result |
|-------|--------|
| `test_phase4_3_1_prompt_v8_1.py` | **PASS** (v8.1 bytes/SHA via `_S1_PROMPT_V8_1`; pinned planner) |
| `test_phase4_3_1_v8_1_runtime.py` | **PASS** |
| `test_phase4_3_1_v8_1_runner.py` | **PASS** |
| Full agent suite | **169/169 PASS** |

---

## 5. full pytest / ruff / mypy 结果

| Gate | Result |
|------|--------|
| **T-C + agent** | 169 passed |
| **Full pytest** | **1153 passed, 7 failed** |
| **mypy** | Success (80 source files) |
| **ruff** | Clean on Workstream C touched files after `--fix` |

**7 failures:** all `test_architecture_boundaries.py` `git diff --check` against historical phase baselines — trailing whitespace in pre-existing branch docs (`EXTERNAL_VALIDATION_*`, amendment specs). **Not introduced by Workstream C.**

---

## 6. preservation audit 结果

| Check | Result |
|-------|--------|
| `test_ev_t001_protected_v02_assets_match_frozen_hashes` | **PASS** |
| v8.1 prompt SHA-256 (`f2f0a81c…`) | **Unchanged** (T-C-005) |
| `prompts.py` file hash in `protected_assets.sha256` | **Unchanged** (v9 in separate `prompts_v03.py`) |

---

## 7. 是否存在行为回归

| Area | Assessment |
|------|------------|
| v8.1 sealed campaigns | **No regression** — pinned `_Phase4V8_1RealLLMPlanner` |
| Combined clipping+harmonic | **No regression** (T-C-003) |
| Product default path | **Intentional change** — now v9.0 conservative policy |
| Scoring thresholds | **Unchanged** |
| FinishDecision / schema | **Unchanged** |

---

## 8. 是否具备进入 V0.3 real dev validation 的条件

**Yes — with noted prerequisites:**

- Workstreams A/B/C implementation complete and GREEN on contract tests
- Product planner on v9.0; v8.1 preserved for historical benchmarks
- Real-model dev validation **not run** (per authorization)

**Still required before test-split unseal:**

- EV-C036 acceptance targets pre-registration
- Real WAV V0.3 dev split acquisition
- Real-model prompt behavior validation (separate authorization)

---

## 9. Remaining blockers

| Blocker | Status |
|---------|--------|
| Real-model v9.0 dev validation | Not started (explicitly out of scope) |
| EV-C036 pre-registration | Deferred until test split unseal |
| Architecture `git diff --check` on branch | 7 pre-existing doc whitespace failures |
| V0.3 study manifest / real WAV dev split | Not yet acquired |

**Stopped per authorization. No push. No PR.**
