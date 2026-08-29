# Phase 3 Real-Model Behavior Report

**Report date:** 2026-08-29
**Scope:** Scenario S1 — Distortion Diagnosis, Phase 3 product-path observation
**Planner path:** `RealLLMPlanner` with injected `RuleEngine`, explicitly mapped
`YamlRuleProfileLoader`, and `KnowledgeIndex`
**Status:** **BLOCKED — `DEEPSEEK_API_KEY` missing** (not a scored pass or fail)

---

## 1. Acceptance boundary

This report is the Phase 3 product-path observation required by
`docs/superpowers/plans/2026-08-29-phase3-rules-knowledge.md` Task 9 and
`TEST_PLAN_V0_2.md` §17. It is **not** a CI gate and is **not** a substitute
for T001–T124.

- T093–T124 validate deterministic rules, knowledge retrieval, runtime
  injection, and scripted S1 paths.
- A real-model run would inspect selection, observation-driven
  rule/retrieval decisions, unnecessary actions, stopping, grounding, and
  limitations on the four Phase 2 S1 cases.
- Missing credentials must not be papered over with `ScriptedPlanner` or with
  fabricated model traces.

**This file records one honest attempt that did not invoke the live model.**
It does not score R001-style behavior and does not claim passing product-path
observations. Failures and blocks are recorded as-is; the run was not retried
until a favorable trace appeared (`TEST_PLAN_V0_2.md` §13 / §18).

## 2. Credential search and why the run did not occur

`scripts/run_phase3_real_model_eval.py` requires `DEEPSEEK_API_KEY`. When the
key is unset, the runner prints a clear error that it does not fall back to
`ScriptedPlanner` and exits non-zero.

On 2026-08-29 this session searched, without inventing a key:

| Source | Result |
|---|---|
| Process environment `DEEPSEEK_API_KEY` | unset |
| User environment `DEEPSEEK_API_KEY` | unset |
| Machine environment `DEEPSEEK_API_KEY` | unset |
| Worktree `.env` (`sdd-phase3-rules-knowledge`) | file absent |
| Original repo `.env` (`signal-diagnosis-agent`) | file absent |

**Missing variable:** `DEEPSEEK_API_KEY`

The runner was therefore not executed against a live model. No JSON traces
were written under `real_model_eval_output/phase3/`. `ScriptedPlanner` was
not used as a fallback.

## 3. Command actually run

Python: `C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

```powershell
python scripts/run_phase3_real_model_eval.py --output-dir real_model_eval_output/phase3
```

- **Exit code:** 1
- **stderr:** `RealLLMPlanner is not configured: set DEEPSEEK_API_KEY in the environment before running real-model evaluation. This command does not fall back to ScriptedPlanner.`
- **Traces:** none (`real_model_eval_output/phase3/` was not created)
- **Model id:** not observed (planner never constructed against a live call)

The product composition that would have been used, had credentials been
present:

- `RealLLMPlanner(provider="deepseek")` — never `ScriptedPlanner`
- `InMemorySignalRepository` and `SignalToolService`
- `RuleEngine()`
- `YamlRuleProfileLoader({"profile_s1_distortion": <shipped YAML path>})`
- `KnowledgeIndex(<shipped corpus root>)`

Traces would be checked for raw waveforms and full FFT arrays
(`frequencies_hz`, `magnitude_db`, `ndarray` payloads) before write.

`profile_s1_distortion` version `1.0.0-demo` thresholds are demonstration-only
and are not industry standards.

## 4. Four-case outcomes

The four Phase 2 S1 cases were **not executed**. Recorded as-is:

| Case | Deterministic input | Ground truth | Outcome |
|---|---|---|---|
| S1-CLIP-SUBFS | 200 Hz sine, amplitude 0.9, clipped at 0.5 | sub-full-scale flat-top clipping | **NOT RUN** — blocked before first case |
| S1-HARM | 200 Hz fundamental, amplitude 0.5, H2=0.10, H3=0.05 | harmonic distortion | **NOT RUN** — blocked before first case |
| S1-CLEAN | 200 Hz sine, amplitude 0.5 | no supported fault | **NOT RUN** — blocked before first case |
| S1-NOISE | white noise, RMS 0.1, seed 1234 | inconclusive/non-periodic input | **NOT RUN** — blocked before first case |

Tool counts, diagnosis, rule/knowledge refs, elapsed time, and provider usage
are unavailable because no case started.

## 5. Scoring

| Observation | Result |
|---|---|
| First-tool selection | not scored — BLOCKED (`DEEPSEEK_API_KEY`) |
| Observation-driven rule/retrieval decisions | not scored — BLOCKED (`DEEPSEEK_API_KEY`) |
| Unnecessary actions | not scored — BLOCKED (`DEEPSEEK_API_KEY`) |
| Stopping | not scored — BLOCKED (`DEEPSEEK_API_KEY`) |
| Grounding of evidence/rule/knowledge refs | not scored — BLOCKED (`DEEPSEEK_API_KEY`) |
| Limitations | not scored — BLOCKED (`DEEPSEEK_API_KEY`) |

Do not treat this table as a pass. Missing credentials and a **BLOCKED**
status are an honest record; they are not a fabricated pass. When credentials
are configured, run the command above **once**, retain the traces including
failures, and replace this report with an honest observation of that run.
Score first-tool selection, observation-driven rule/retrieval decisions,
unnecessary actions, stopping, grounding, and limitations honestly. Report
individual failures rather than retrying until a favorable example appears
(`TEST_PLAN_V0_2.md` §13). If a run performs poorly, retain the trace,
classify the failure, and report variation transparently (§18). Do not wait
for, loop for, or cherry-pick a favorable trace.

## 6. Deterministic gate (separate)

Missing real-model credentials do not block T001–T124. The deterministic
Phase 3 gate remains the pytest / Ruff / mypy / `git diff --check` result
recorded in the Task 9 implementer report.
