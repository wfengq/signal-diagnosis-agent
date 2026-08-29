# Phase 3 Real-Model Behavior Report

**Report date:** 2026-08-29
**Scope:** Scenario S1 — Distortion Diagnosis, Phase 3 product-path observation
**Planner path:** `RealLLMPlanner` with injected `RuleEngine`, explicitly mapped
`YamlRuleProfileLoader`, and `KnowledgeIndex`
**Status:** **RAN** — one honest DeepSeek run (not retried)

---

## 1. Acceptance boundary

This report is the Phase 3 product-path observation required by
`docs/superpowers/plans/2026-08-29-phase3-rules-knowledge.md` Task 9 and
`TEST_PLAN_V0_2.md` §17. It is **not** a CI gate and is **not** a substitute
for T001–T124.

- T093–T124 validate deterministic rules, knowledge retrieval, runtime
  injection, and scripted S1 paths.
- This real-model run inspects selection, observation-driven rule/retrieval
  decisions, unnecessary actions, stopping, grounding, and limitations on the
  four Phase 2 S1 cases.
- `ScriptedPlanner` was not used. Failures are recorded as-is; the run was not
  retried until a favorable trace appeared (`TEST_PLAN_V0_2.md` §13 / §18).

## 2. Credentials and composition

`scripts/run_phase3_real_model_eval.py` requires `DEEPSEEK_API_KEY`. The Windows
**User** environment variable was confirmed non-empty (boolean check only). A
new PowerShell process loaded that User variable and ran the runner. The key
value is not recorded here.

Python: `C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

```powershell
python scripts/run_phase3_real_model_eval.py --output-dir real_model_eval_output/phase3
```

- **Exit code:** 0
- **Traces:** `real_model_eval_output/phase3/` (`index.json` plus four case JSON
  files). That directory is gitignored and is not committed.
- **Model id:** `deepseek-v4-flash`
- **Prompt version:** `v0.2-s1-planner-4`
- **Protocol:** `phase3-real-model`

Product composition actually used:

- `RealLLMPlanner(provider="deepseek")` — never `ScriptedPlanner`
- `InMemorySignalRepository` and `SignalToolService`
- `RuleEngine()`
- `YamlRuleProfileLoader({"profile_s1_distortion": <shipped YAML path>})`
- `KnowledgeIndex(<shipped corpus root>)`

Traces were checked for raw waveforms and full FFT arrays
(`frequencies_hz`, `magnitude_db`, `ndarray` payloads) before write. No API key
strings appear in the JSON traces.

`profile_s1_distortion` version `1.0.0-demo` thresholds are demonstration-only
and are not industry standards.

## 3. Four-case outcomes

| Case | Deterministic input | Ground truth | Run status | Diagnosis outcome | Tools | Rules | Knowledge | Elapsed (s) |
|---|---|---|---|---|---|---|---|---|
| S1-CLIP-SUBFS | 200 Hz sine, amplitude 0.9, clipped at 0.5 | sub-full-scale flat-top clipping | `success` / `planner_finished` | `supported_fault` | `detect_clipping`, `analyze_harmonic_distortion` | 0 | 0 | 8.424 |
| S1-HARM | 200 Hz fundamental, amplitude 0.5, H2=0.10, H3=0.05 | harmonic distortion | `success` / `planner_finished` | `supported_fault` | `detect_clipping`, `analyze_harmonic_distortion` | 0 | 0 | 4.366 |
| S1-CLEAN | 200 Hz sine, amplitude 0.5 | no supported fault | `success` / `planner_finished` | `no_supported_fault` | `detect_clipping`, `analyze_harmonic_distortion` | 0 | 0 | 4.981 |
| S1-NOISE | white noise, RMS 0.1, seed 1234 | inconclusive/non-periodic input | `inconclusive` / `planner_finished` | `inconclusive` | `detect_clipping`, `analyze_harmonic_distortion` | 0 | 0 | 3.712 |

### S1-CLIP-SUBFS

- First tool: `detect_clipping`. Second: `analyze_harmonic_distortion`.
- Claim 1: `clipping` — clipping ratio 0.625, flat-top present; cites clipping
  Evidence IDs. Matches ground truth.
- Claim 2: `harmonic_distortion` — THD 20.37% and third harmonic; cites harmonic
  Evidence IDs. Extra relative to the clipping-only ground truth (clipping can
  produce harmonics).
- `rule_refs` and `knowledge_refs` empty. Confidence `high`. Limitations empty.

### S1-HARM

- Same two-tool sequence. One claim: `harmonic_distortion` (THD 11.18%, 2nd and
  3rd harmonics) with harmonic Evidence IDs. Matches ground truth.
- `rule_refs` and `knowledge_refs` empty. Confidence `high`. Limitations empty.

### S1-CLEAN

- Same two-tool sequence. One claim: `no_supported_fault` with clipping and
  harmonic Evidence IDs. Matches ground truth.
- `rule_refs` and `knowledge_refs` empty. Confidence `high`. Limitations empty.

### S1-NOISE

- Same two-tool sequence. Zero claims. Outcome `inconclusive`. Matches ground
  truth.
- Limitations recorded: invalid F0 so harmonic metrics not applicable; clipping
  absent but harmonic distortion could not be assessed.
- Confidence `low`. No Evidence/rule/knowledge refs on claims (no claims).

`provider_usage` was `null` on all four summaries.

## 4. Scoring

| Observation | Result |
|---|---|
| First-tool selection | All four started with `detect_clipping`, then `analyze_harmonic_distortion`. Reasonable S1 opening. |
| Observation-driven rule/retrieval decisions | **Failed.** Rule-evaluation count 0 and knowledge-retrieval count 0 on every case, despite injected `RuleEngine` / `KnowledgeIndex`. The live planner never emitted `evaluate_rules` or `retrieve_knowledge`. |
| Unnecessary actions | Compact two-tool path; no looping. CLIP's extra `harmonic_distortion` claim is an overclaim versus clipping-only ground truth. |
| Stopping | All four stopped via `planner_finished` after two tools. No budget exhaustion. |
| Grounding of evidence/rule/knowledge refs | **Partial.** Fault cases cite same-run Evidence IDs. No claim cites a rule-evaluation ID or knowledge chunk. Phase 3 distinction between evidence, rule judgment, and explanation was unused. |
| Limitations | **Mixed.** NOISE stated F0/harmonic non-applicability. CLIP/HARM/CLEAN reported empty limitations (CLIP did not note that clipping can induce harmonics). |

Do not treat this table as a Phase 3 product-path pass. Diagnosis outcomes on
the four S1 labels were directionally correct, but the model did not use the
Phase 3 rule or knowledge actions. That gap is retained as the honest result of
this single run (`TEST_PLAN_V0_2.md` §13 / §18).

## 5. Deterministic gate (separate)

This real-model observation does not replace T001–T124. The deterministic
Phase 3 gate remains the pytest / Ruff / mypy / `git diff --check` result
recorded in the Task 9 implementer report.
