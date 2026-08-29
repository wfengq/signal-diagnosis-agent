# Phase 3 Real-Model Behavior Report

**Report date:** 2026-08-29
**Scope:** Scenario S1 — Distortion Diagnosis, Phase 3 product-path observation
**Planner path:** `RealLLMPlanner` with injected `RuleEngine`, explicitly mapped
`YamlRuleProfileLoader`, and `KnowledgeIndex`
**Status:** **NOT RUN — credentials unavailable**

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

**This file records that the real model was not invoked.** It does not score
R001-style behavior and does not claim passing product-path observations.

## 2. Why the run did not occur

`scripts/run_phase3_real_model_eval.py` requires `DEEPSEEK_API_KEY`. When the
key is unset, the runner prints a clear error that it does not fall back to
`ScriptedPlanner` and exits non-zero.

On 2026-08-29 the Task 9 implementer environment did not have
`DEEPSEEK_API_KEY`. The runner was therefore not executed against a live
model. No JSON traces were written under `real_model_eval_output/phase3/`.

## 3. What would have been run

The runner reuses the four Phase 2 S1 signal definitions:

| Case | Deterministic input | Ground truth |
|---|---|---|
| S1-CLIP-SUBFS | 200 Hz sine, amplitude 0.9, clipped at 0.5 | sub-full-scale flat-top clipping |
| S1-HARM | 200 Hz fundamental, amplitude 0.5, H2=0.10, H3=0.05 | harmonic distortion |
| S1-CLEAN | 200 Hz sine, amplitude 0.5 | no supported fault |
| S1-NOISE | white noise, RMS 0.1, seed 1234 | inconclusive/non-periodic input |

Command (not executed in this environment):

```powershell
python scripts/run_phase3_real_model_eval.py --output-dir real_model_eval_output/phase3
```

The product composition is:

- `RealLLMPlanner(provider="deepseek")` — never `ScriptedPlanner`
- `InMemorySignalRepository` and `SignalToolService`
- `RuleEngine()`
- `YamlRuleProfileLoader({"profile_s1_distortion": <shipped YAML path>})`
- `KnowledgeIndex(<shipped corpus root>)`

Traces would be checked for raw waveforms and full FFT arrays
(`frequencies_hz`, `magnitude_db`, `ndarray` payloads) before write.

`profile_s1_distortion` version `1.0.0-demo` thresholds are demonstration-only
and are not industry standards.

## 4. Scoring

| Observation | Result |
|---|---|
| First-tool selection | not scored — NOT RUN |
| Observation-driven rule/retrieval decisions | not scored — NOT RUN |
| Unnecessary actions | not scored — NOT RUN |
| Stopping | not scored — NOT RUN |
| Grounding of evidence/rule/knowledge refs | not scored — NOT RUN |
| Limitations | not scored — NOT RUN |

Do not treat this table as a pass. Missing credentials and a **NOT RUN**
status are an honest record; they are not a fabricated pass. When credentials
are configured, run the command above once, retain the traces including
failures, and replace this report with an honest observation of that run.
Score first-tool selection, observation-driven rule/retrieval decisions,
unnecessary actions, stopping, grounding, and limitations honestly. Report
individual failures rather than retrying until a favorable example appears
(`TEST_PLAN_V0_2.md` §13). If a run performs poorly, retain the trace,
classify the failure, and report variation transparently (§18). Do not wait
for, loop for, or cherry-pick a favorable trace.

## 5. Deterministic gate (separate)

Missing real-model credentials do not block T001–T124. The deterministic
Phase 3 gate remains the pytest / Ruff / mypy / `git diff --check` result
recorded in the Task 9 implementer report.
