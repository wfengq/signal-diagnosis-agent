# Phase 2 R001–R006 Real-Model Acceptance Report

**Report date:** 2026-08-29
**Scope:** Scenario S1 — Distortion Diagnosis, Phase 2 product-path behavior
**Planner path:** `RealLLMPlanner` with DeepSeek
**Model:** `deepseek-v4-flash`
**Prompt version:** `v0.2-s1-planner-3`
**Status:** Accepted as a Phase 2 product-behavior checkpoint, with the limitations in §8

---

## 1. Acceptance boundary

This report closes the Phase 2 R001–R006 review required by
`TEST_PLAN_V0_2.md` §13. It evaluates the real-model product path separately
from deterministic CI acceptance.

- T064–T092 validate the planner boundary, runtime state machine, Tool
  execution, propagation, error policies, and reproducible S1 paths with
  `ScriptedPlanner`.
- R001–R006 inspect one retained real-model run for each initial S1 case.
- R001–R006 are behavioral observations, not deterministic CI gates and not a
  claim that future model calls will behave identically.

No model call was made while preparing this report. The report scores the four
retained traces produced on 2026-08-28 by `scripts/run_real_model_eval.py`.

## 2. Inputs and provenance

All acceptance inputs are deterministic synthetic signals with known ground
truth. Every case uses a 48 kHz sample rate, a two-second duration, and the user
request `Why does this signal sound distorted?`.

| Case | Deterministic input | Ground truth |
|---|---|---|
| S1-CLIP-SUBFS | 200 Hz sine, amplitude 0.9, clipped at 0.5 | sub-full-scale flat-top clipping |
| S1-HARM | 200 Hz fundamental, amplitude 0.5, H2=0.10, H3=0.05 | harmonic distortion |
| S1-CLEAN | 200 Hz sine, amplitude 0.5 | no supported fault |
| S1-NOISE | white noise, RMS 0.1, seed 1234 | inconclusive/non-periodic input |

The local JSON traces are intentionally ignored by Git until Phase 4 freezes a
versioned evaluation-artifact schema. This report is the reviewable, versioned
result. Trace SHA-256 values used for this review are:

| Trace | SHA-256 |
|---|---|
| `s1-clip-subfs.json` | `2CF47043F0758376E50EBA2BB593BFB72F1475AAEAFBF5A32D74F524EE3D7114` |
| `s1-harm.json` | `0C9BBCE4EFC474238EBDA6027B85F77BC9F0952AE3269F9748D21508ABBAC7E8` |
| `s1-clean.json` | `149E72C71392DAEF8F54992517540A63C4C8A1BD138F4B45ED6AEE5E2182EAEA` |
| `s1-noise.json` | `41AB456C81B98AF884F09310CFE9C0F5259943C0AA85E88DF4EFA11671B4ED02` |

The runner rejects full FFT arrays and NumPy array payloads before writing a
trace. The retained files contain structured observations only.

## 3. Deterministic Phase 2 gate

The real-model observations rely on a separately accepted deterministic
runtime. Fresh verification for this report produced:

| Gate | Command | Result |
|---|---|---|
| Phase 2 Agent suite | `python -m pytest tests/agent -q -p no:cacheprovider` | 55 passed |
| Accumulated suite | `python -m pytest -q -p no:cacheprovider` | 195 passed, 4 Phase 3 package-absence skips |
| Lint | `python -m ruff check --no-cache src tests` | passed |
| Type check | `python -m mypy --no-incremental src` | passed, 29 source files |

The four skips are Phase 3 architecture migration checks that become hard gates
when the `rules/` and `knowledge/` packages are created. They do not weaken the
accepted T001–T092 result.

## 4. Per-case trace review

| Case | Tool sequence | Key observation and replan | Stop/outcome | Review |
|---|---|---|---|---|
| S1-CLIP-SUBFS | `detect_clipping` | Positive clipping evidence: ratio 0.625 and flat top detected | stopped after 1 Tool; clipping | appropriate |
| S1-HARM | `detect_clipping` → `analyze_harmonic_distortion` | Negative clipping evidence led to harmonic analysis; valid THD 11.18%, H2≈0.10, H3≈0.05 | stopped after 2 Tools; harmonic distortion | appropriate |
| S1-CLEAN | `detect_clipping` → `analyze_harmonic_distortion` | Negative clipping evidence led to harmonic analysis; valid THD ≈3.27e-7% | stopped after 2 Tools; no supported fault | appropriate |
| S1-NOISE | `detect_clipping` → `analyze_harmonic_distortion` | Negative clipping evidence led to harmonic analysis; fundamental was invalid, so THD was not applicable | stopped after 2 Tools; inconclusive | appropriate |

No case called the full set of clipping, spectrum, fundamental, and harmonic
Tools. The model stopped after sufficient evidence for the supported diagnosis
space instead of executing a fixed pipeline.

## 5. R001–R006 scoring

| ID | Result | Evidence-based assessment |
|---|---|---|
| R001 — first-Tool selection | pass | `detect_clipping` was the first Tool in all four runs. It is relevant to every initial S1 distortion state and immediately resolved S1-CLIP-SUBFS. This sample does not demonstrate first-Tool diversity. |
| R002 — observation-driven replanning | pass | Positive clipping evidence caused immediate finish; negative clipping evidence caused a justified harmonic call; invalid harmonic evidence caused an inconclusive finish rather than a fabricated metric. |
| R003 — unnecessary calls | pass, 0 observed | Every Tool call added evidence needed to distinguish clipping, harmonic distortion, no supported fault, or inconclusive. There were no separate spectrum/F0 calls after the harmonic Tool had already supplied sufficient fundamental/THD evidence. |
| R004 — stopping timing | pass | All four runs ended with `planner_finished`; no run stopped before its supported outcome was grounded, and no run continued after sufficient evidence was available. |
| R005 — final diagnosis quality | pass with minor narrative concern | Ground-truth outcome matched in 4/4 cases. All 14 claim evidence references resolved within the same run; there were no unsupported numerical claims. S1-CLEAN used two separate no-fault claims, which is valid but mildly repetitive. S1-NOISE correctly exposed limitations and made no fault claim. |
| R006 — execution characteristics | partial data | 7 Tool calls total; 28.216 s total latency; 7.054 s mean latency. Model and prompt version were recorded. Exact planner/model-call counts, token usage, and cost were not captured. |

## 6. R006 measurements

| Case | Tool calls | Latency (s) | Termination | Errors | Warnings |
|---|---:|---:|---|---:|---:|
| S1-CLIP-SUBFS | 1 | 6.506 | `planner_finished` | 0 | 0 |
| S1-HARM | 2 | 8.365 | `planner_finished` | 0 | 0 |
| S1-CLEAN | 2 | 7.295 | `planner_finished` | 0 | 0 |
| S1-NOISE | 2 | 6.050 | `planner_finished` | 0 | 1 expected invalid-fundamental warning |

The current trace format does not expose exact planner calls. A successful run
requires at least one decision per Tool plus a final finish decision, but this
report does not present that lower bound as the measured model-call count because
provider/parser retry calls are not recorded. Token and cost fields are likewise
reported as unavailable rather than estimated.

## 7. Acceptance decision

Phase 2 satisfies its two distinct validation layers:

1. deterministic system acceptance is reproducible through T064–T092 and the
   injected `ScriptedPlanner`;
2. the product path demonstrably used `RealLLMPlanner` and, across the four
   retained S1 traces, selected Tools, replanned from observations, stopped
   selectively, and returned evidence-grounded outcomes.

Therefore Phase 2 is accepted for the narrow synthetic S1 MVP and Phase 3 may
build on its runtime contracts. This decision does not claim production-grade
model reliability or complete evaluation coverage.

## 8. Retained limitations and Phase 4 follow-up

- Each real-model case has one retained run, so stochastic variation and
  confidence intervals are unknown.
- All four runs chose clipping first; the traces prove selective continuation
  and stopping, but not diversity of initial Tool choice.
- Exact planner/provider call counts, retry counts, token usage, and estimated
  cost are missing from the current artifact schema.
- S1-CLEAN contains two correct but somewhat repetitive no-fault claims.
- The dataset covers four initial cases only. Combined distortion,
  boundary-severity cases, repeated runs, held-out cases, and Agent-versus-fixed-
  pipeline comparison belong to Phase 4.
- These traces use synthetic inputs. WAV ingestion and presentation adapters
  remain Phase 5 work.

Phase 4 should version the trace/report schema, capture provider usage and retry
telemetry, run repeated trials, retain failures without cherry-picking, and
compare the Agent with a fixed pipeline using identical signals, DSP Tools, and
rules.
