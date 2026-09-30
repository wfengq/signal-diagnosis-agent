# Single-file context guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** complete — merged via PR #10 (guidance) / #11 (RealLLM evidence);
Web UI held-bytes upgrade closed in PR #12; post-merge hygiene PR #13.

**Goal:** When a contextual `single_signal` run ends `inconclusive` for missing attribution context, attach a deterministic `context_guidance` block and accept `mode=single_signal` on contextual WAV submit (D037 / approved design).

**Architecture:** Pure app-layer additive DTO + pure function deriving guidance from mode + `AgentRunResult`; extend multipart/service mode union; keep V0.2 endpoints and agent/DSP/rules untouched.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing FastAPI contextual routes.

## Global Constraints

- Frozen `CONTRACTS_V0_2.md` §§1–64 and V0.2 `AppRunSnapshot` / `/api/v1/runs/*` / `diagnose wav` remain byte-stable.
- No DSP, rule-threshold, planner-prompt, or causal-gate changes.
- No RealLLM re-runs; ScriptedPlanner tests only.
- Guidance text must not soft-diagnose (“可能是谐波失真”).
- Nominal Hz must never be auto-filled from measured F0.
- Presets stay unknown-signal (D037 §2).
- Do not cite HEAD quality numbers (D037 §3).

## File map

| File | Responsibility |
|------|----------------|
| `src/signal_diag/app/context_guidance.py` | Pure builder: reason codes + templates |
| `src/signal_diag/app/contextual_models.py` | Additive `ContextGuidance` on snapshot/report |
| `src/signal_diag/app/multipart.py` | Allow `mode=single_signal` |
| `src/signal_diag/app/service.py` | Accept single_signal submit; attach guidance on complete |
| `src/signal_diag/app/api.py` / `cli.py` | Pass through if needed |
| `src/signal_diag/app/static/app.js` (+ html if needed) | Default unknown WAV → contextual single_signal; show guidance |
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` | §17 freeze |
| `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | T-CX264–T-CX268 |
| `docs/superpowers/specs/2026-09-29-single-file-context-guidance-design.md` | Mark approved |
| `tests/app/test_context_guidance.py` | Unit tests for builder |
| `tests/app/test_contextual_service.py` | single_signal submit + guidance on snapshot |

---

### Task 1: Guidance builder + unit tests (T-CX264/265)

**Files:**
- Create: `src/signal_diag/app/context_guidance.py`
- Create: `tests/app/test_context_guidance.py`
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` (register T-CX264–T-CX265)

**Interfaces:**
- Produces: `ContextGuidanceReasonCode`, `ContextGuidance` model, `build_context_guidance(*, mode, result: AgentRunResult | None) -> ContextGuidance | None`

- [x] **Step 1: Write failing tests**

```python
# tests/app/test_context_guidance.py
from signal_diag.app.context_guidance import build_context_guidance
# Construct minimal AgentRunResult with outcome inconclusive + harmonic Evidence
# assert guidance is not None, reason_codes contain harmonic_attribution_requires_context
# assert "可能是" not in guidance.summary and "likely" not in guidance.summary.lower()
# For supported_fault clipping result → guidance is None
# For no_supported_fault → None
# For mode paired_reference inconclusive → None
```

- [x] **Step 2: Run** `pytest tests/app/test_context_guidance.py -q` → expect FAIL (import/missing)

- [x] **Step 3: Implement** `context_guidance.py` with frozen Pydantic models and templates keyed by reason codes; detect harmonic attribution gap via diagnosis outcome + claim/evidence heuristics documented in §17 (prefer: outcome `inconclusive` + any valid Evidence metric in `{"thd_percent","even_order_present","fundamental_relative_energy"}` OR empty claims with successful harmonic tool observation — keep rule simple and tested).

- [x] **Step 4: pytest green**

- [x] **Step 5: Commit** `test+feat: deterministic context_guidance builder (T-CX264/265)`

---

### Task 2: Snapshot DTO + single_signal contextual submit (T-CX266/267)

**Files:**
- Modify: `src/signal_diag/app/contextual_models.py`
- Modify: `src/signal_diag/app/multipart.py` (`_CONTEXTUAL_MODES`)
- Modify: `src/signal_diag/app/service.py` (`_queued_capabilities`, `submit_contextual_wav` mode union + validation branch + attach guidance on completed snapshot)
- Modify: `tests/app/test_contextual_service.py` / `tests/app/test_contextual_models.py`
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §17
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` T-CX266–T-CX267

**Interfaces:**
- Consumes: `build_context_guidance`
- Produces: `ContextualAppRunSnapshot.context_guidance: ContextGuidance | None = None`; multipart accepts `single_signal`

- [x] **Step 1: Failing tests** — submit_contextual_wav mode=single_signal with wav bytes succeeds; completed inconclusive run exposes context_guidance; paired submit unchanged.

- [x] **Step 2: pytest fail**

- [x] **Step 3: Implement** mode=`single_signal` validation (reject reference; reject nominal fields); `_queued_capabilities("single_signal")` → clipping + absolute_harmonic_description only; on `mark_completed` path set `context_guidance=build_context_guidance(...)`.

- [x] **Step 4: green + commit** `feat: contextual single_signal submit and guidance field`

---

### Task 3: API/CLI/UI wiring (T-CX268)

**Files:**
- Modify: `src/signal_diag/app/api.py` if mode typing is narrowed
- Modify: `src/signal_diag/app/cli.py` if contextual diagnose rejects single_signal
- Modify: `src/signal_diag/app/static/app.js` (+ `index.html` if needed) — default unknown WAV uses contextual endpoint with mode single_signal; render guidance + upgrade hints
- Test: extend existing app UI/API tests if present; else ScriptedPlanner service-level coverage already in Task 2; add lightweight JS-free API test for multipart mode=single_signal

- [x] **Step 1–4:** TDD where Python tests exist; manual static change for JS with verify skill optional
- [x] **Step 5: Commit** `feat: wire single_signal guidance through API/UI`

---

### Task 4: Design status + docs closeout + verify

**Files:**
- Modify: design spec status → approved
- Modify: `AGENTS.md` / README only if needed (already D037)

- [x] Run: `pytest tests/app/test_context_guidance.py tests/app/test_contextual_service.py tests/app/test_contextual_models.py -q`
- [x] Run: `ruff check --no-cache src/signal_diag/app tests/app` and `mypy --no-incremental src/signal_diag/app`
- [x] Push PR #10; mark ready when green
- [x] Commit: `docs: mark context-guidance design approved; register T-CX264–268`

## Spec coverage check

| Spec § | Task |
|--------|------|
| 5.1 emission conditions | Task 1 |
| 5.2 reason codes | Task 1 |
| 5.3 payload | Task 1–2 |
| 5.4 single_signal submit + UI | Task 2–3 |
| 5.5 layers unchanged | Global constraints |
| 5.6 contracts/tests | Task 2 + 4 |
| 5.7 verification | Task 4 |
