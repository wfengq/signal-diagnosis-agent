# Phase 1 Implementation Readiness Report

**Date:** 2026-09-02
**Scope:** V0.3 Workstreams A/B/C — verification + TDD scaffolding only (no production behavior changes)
**Artifacts:**
- Experiments: `docs/evaluations/v0_3/prerequisites/phase1_experiment_results.json`
- Scratch runner: `private/scratch/v03_phase1_prerequisites.py`
- Tests: `tests/dsp/test_v03_workstream_a_f0_reliability.py`, `tests/dsp/test_v03_workstream_b_harmonic_validity_gate.py`, `tests/agent/test_v03_workstream_c_prompt_policy.py`
- Helpers: `tests/dsp/v03_prerequisite_helpers.py`

---

## 1. AGENTS.md scope findings

| Finding | Detail |
|---------|--------|
| V0.2 frozen | Product behavior, public interfaces, prompt v8.1 SHA-256, scoring 2.0.0, sealed artifacts must not change without explicit V0.3 authorization. |
| V0.3 gate | Amendment requires **new design + contract IDs (EV-C026–036) + test IDs + explicit implementation authorization** (AGENTS.md scope gates). |
| Phase 1 allowed | Read-only investigation, scratch experiments, **contract tests that fail until implementation** — consistent with user instruction and TDD workflow. |
| Phase 1 forbidden (observed) | No edits to `src/signal_diag/dsp/pitch.py`, `harmonics.py`, `prompts.py`, sealed V0.2 bundles, or protected assets. |
| Interface note | Adding fields to `F0Estimate` / `HarmonicAnalysis` **may** be permissible if function signatures stay frozen — requires explicit contract amendment approval before implementation (EV-C026–029). |

---

## 2. `fundamental_relative_energy` — implementation feasibility

**Verdict: FEASIBLE** using the existing Hann-windowed RFFT inside `analyze_harmonic_distortion`.

Reference implementation (tests + Phase 1 scratch) matches design EV-C026:

```text
numerator   = |X[k_f0]|²
denominator = Σ_{k=1}^{N/2} |X[k]|²
FRE         = numerator / denominator  ∈ [0, 1]
```

**Phase 1 empirical calibration (N=48000, 1 s, Hann, SR=48 kHz):**

| Scenario | Estimated F0 | FRE | Notes |
|----------|-------------|-----|-------|
| Pure sine 200/400/440 Hz | correct | **≈ 0.667** | Not ≈1.0 — finite-window spectral leakage spreads energy across bins |
| Two-tone 200+400 Hz | 200 Hz | **≈ 0.333** | Energy shared across partials |
| 700 Hz sine (subharmonic lock) | **350 Hz** | **≈ 1.5×10⁻²⁰** | Matches master_final_02 failure mechanism |
| Sine 440 + noise SNR 0 dB | wrong (88 Hz) | **≈ 2.2×10⁻⁵** | Unreliable regime + absurd THD |
| Theoretical equal-noise floor | — | **2/N ≈ 4.2×10⁻⁵** | Design lower bound reference |

**Important:** Design text “pure sinusoid → FRE approaching 1.0” is **optimistic** for the specified FFT definition on finite frames. Implementation docs should state expected **pure-sine band ≈ 0.60–0.70** under current window/definition, not 1.0.

---

## 3. `min_fundamental_relative_energy` — candidate range (NOT final default)

**Do not commit a production default yet.** Phase 1 synthesized evidence suggests:

| Bound | Value | Basis |
|-------|-------|-------|
| Theoretical floor | **≈ 4×10⁻⁵** | `2/N` equal per-bin noise (design reference) |
| Observed unreliable | **< 10⁻⁴** | 700 Hz→350 Hz lock; SNR 0 dB mis-lock |
| Reliable pure sines | **≈ 0.60–0.67** | All tested pure tones |
| Ambiguous multi-partial | **≈ 0.33** | Two-tone 200+400 |

**Candidate implementation band for dev-split tuning:** **`[0.01, 0.10]`**

- Safely above unreliable synthesized regimes (~10⁻⁴–10⁻⁵)
- Safely below pure-sine cluster (~0.66)
- **Dev split must confirm** gate does not false-trigger on V0.2 synthetic benchmark (T-B-005) or clip/harmonic fixtures

**Not derived from V0.2 failure case observations** (350 Hz / 905.7 Hz).

---

## 4. `octave_ambiguity_tolerance` — candidate range (NOT final default)

**Verdict: algorithm specification incomplete — blocker for Workstream A implementation.**

Phase 1 finding: naïve comparison of `|acf(lag_f0)|` vs `|acf(lag_2f0)|` yields **~1.0 on every pure sine** (values ≈ +1 vs −1), which would false-flag all monophonic tones.

**Required refinement (before coding):**

- Detect **local maxima** in normalized ACF over `[fmin, fmax]` lag range
- Compare **primary peak** vs **secondary peak** height (not fixed 2× lag of selected F0 only)
- Exclude cases where secondary peak is a negative trough

**Candidate tolerance band for synthesized ambiguous cases:** **`0.90 – 0.98`** (ratio secondary/primary local maxima) — must be validated on:

- Pure sines → **no flag** (T-A-005)
- 700 Hz subharmonic-lock sine → **flag set**, F0 unchanged (T-A-002)
- Two-tone 200+400 → TBD in dev experiments

---

## 5. Reference validator independence (EV-C032)

**Verdict: NOT SATISFIED today.**

`src/signal_diag/evaluation/external/reference.py` directly imports production:

- `signal_diag.dsp.harmonics.analyze_harmonic_distortion`
- `signal_diag.dsp.pitch.estimate_f0_autocorrelation`
- `signal_diag.dsp.clipping.analyze_clipping`

Workstream D requires a **reference-only harmonic validator** (may share numpy/scipy primitives, must not call production `harmonics.py` or tool adapters).

**Required before V0.3 dataset qualification:** refactor `reference.py` or add `reference_harmonics.py` with duplicated/independent FFT-threshold logic used only for study gates.

---

## 6. V0.3 prompt version naming

Existing convention in `prompts.py`:

```text
v0.2-s1-planner-4 … v0.2-s1-planner-8.1
```

**Recommended V0.3 identifier:** **`v0.3-s1-planner-9.0`**

- Major prefix bump (`v0.3`) matches V0.3 study scope
- Increment planner generation (`9.0`) after frozen `8.1`
- Export as `_S1_PROMPT_V9_0` / `_S1_SYSTEM_PROMPT_V9_0` mirroring existing pattern
- **Do not alter** `_S1_PROMPT_V8_1` bytes or SHA-256 (`f2f0a81c…`) in protected assets

---

## 7. T-A / T-B / T-C test scaffolding added

| Suite | File | IDs |
|-------|------|-----|
| Workstream A | `tests/dsp/test_v03_workstream_a_f0_reliability.py` | T-A-001 … T-A-005 |
| Workstream B | `tests/dsp/test_v03_workstream_b_harmonic_validity_gate.py` | T-B-001 … T-B-008 |
| Workstream C | `tests/agent/test_v03_workstream_c_prompt_policy.py` | T-C-001 … T-C-006 |

All tests use **synthesized fixtures** only (no sealed V0.2 WAV paths).

---

## 8. Expected FAIL vs PASS today (2026-09-02 run)

**15 failed, 4 passed** — expected for Phase 1 scaffolding.

| Test | Expected now | Why |
|------|--------------|-----|
| T-A-001 … T-A-005 | **FAIL** | `F0Estimate` lacks `f0_reliability`, `octave_ambiguity_detected` |
| T-B-001, T-B-004 | **FAIL** | No validity gate; 700 Hz lock returns `valid=true` + huge THD |
| T-B-002, T-B-003, T-B-005 | **PASS** | Current behavior already valid for high-THD synthetic + injected harmonic + V0.2 fixtures |
| T-B-006, T-B-008 | **FAIL** | `HarmonicAnalysis` lacks `fundamental_relative_energy` |
| T-B-007 | **PASS** | Reference helper only (no production field) |
| T-C-001 … T-C-003 | **FAIL** | ScriptedPlanner scenarios not authored (explicit `pytest.fail` stubs) |
| T-C-004 … T-C-006 | **FAIL** | `v0.3-s1-planner-9.0` prompt not yet defined |

---

## 9. Blockers resolved vs remaining

| Blocker (design §Ready for Cursor) | Status |
|-------------------------------------|--------|
| FRE formula feasibility | **Resolved** — implementable at zero extra FFT cost |
| Subharmonic mechanism on synthesized signals | **Resolved** — 700 Hz sine locks 350 Hz, FRE≈0, THD explodes |
| Reference validator independence | **NOT resolved** — requires refactor |
| `min_fundamental_relative_energy` default | **Partially resolved** — candidate band `[0.01, 0.10]`, needs dev tuning |
| `octave_ambiguity_tolerance` | **NOT resolved** — needs local-max ACF algorithm spec |
| V0.3 prompt naming | **Resolved** — recommend `v0.3-s1-planner-9.0` |
| EV-C036 acceptance targets | **Deferred** (per user) — before test split unseal only |

---

## 10. Authorization for production implementation?

**NO — not yet.**

Authorized now:
- Phase 1 artifacts in this report
- TDD tests (expected red)
- Further synthesized/dev experiments

Requires explicit next authorization:
1. Finalize **octave ambiguity algorithm** (Workstream A)
2. Lock **`min_fundamental_relative_energy`** on V0.3 dev split with logged justification
3. Implement **independent reference validator** (EV-C032)
4. Approve **dataclass extensions** / contract publication (EV-C026–031)
5. Then implement Workstreams A → B → C in order with TDD green

---

## 11. Recommended next steps

1. **Approve/refine** octave-ambiguity detection spec (local ACF maxima; avoid pure-sine false positives).
2. **Authorize** reference validator split (`reference_harmonics.py` or equivalent) — no production coupling.
3. **Run V0.3 dev split experiments** to pick `min_fundamental_relative_energy` inside `[0.01, 0.10]` with T-B-005 regression guard.
4. **Authorize production implementation** Workstream A only → green T-A-* → then B → green T-B-*.
5. **Separately authorize** Workstream C prompt `v0.3-s1-planner-9.0` authoring + ScriptedPlanner scenarios (T-C-*).
6. **Do not** re-score or tune on sealed V0.2 final set; plan held-out V0.3 test split per Workstream D.

---

## Cross-reference: prior V0.2 investigation

Findings from `docs/evaluations/v0_2_external_wav/investigation_report_2026-09-02.md` remain valid:

- 905.7 Hz on SMARD sinus_tones 01/03/04 is **likely correct**, not an fmax artifact
- master_final_02 harmonic failure matches **350 Hz lock / 699 Hz spectral energy** pattern reproduced at **700 Hz synthetic**
- Transform 1.1.0 ↔ detector **consistent on pure sines**; gap is reliability gating, not formula typo
