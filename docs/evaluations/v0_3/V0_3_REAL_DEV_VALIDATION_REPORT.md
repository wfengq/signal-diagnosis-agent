# V0.3 Real Dev Validation Report

**Date:** 2026-09-02
**Phase:** V0.3 Real Dev Validation (authorized; dev only)
**Code SHA (agent run):** `0261499fdc92ba7db1df202a558400a8d4063658`
**Commit (artifacts):** `be94682`
**Planner:** `v0.3-s1-planner-9.0`
**Prompt SHA-256:** `bbc6ec4c8f2b7fbe27872188c7f8bb1a64241d48dd87d02841736641f3d1c59a`

Artifacts:

- Dev manifest: `docs/evaluations/v0_3/dev/study_v0_3_dev_1/dev_manifest.json`
- Source catalog: `docs/evaluations/v0_3/dev/protocol/source_catalog.json`
- Reference qualification: `docs/evaluations/v0_3/dev/study_v0_3_dev_1/reference_qualification.json`
- A/B DSP metrics: `docs/evaluations/v0_3/dev/study_v0_3_dev_1/ab_dsp_metrics.json`
- Real-model run: `docs/evaluations/v0_3/dev/study_v0_3_dev_1/agent_v9_0_dev_run_1/run_summary.json`

---

## 1. Dev dataset composition

| case_id | category | origin | notes |
|---------|----------|--------|-------|
| a1f3c9e2b804d716 | single_tone_periodic | repo-synthesized 440 Hz sine | PCM24 mono 48 kHz, 1 s |
| b2e4d0f3c915e827 | injected_harmonic | transform on sine master | second_harmonic α=0.5, post_gain=0.8 |
| c3f5e1a4d026f938 | clipping | transform on sine master | hard_clip tail_proportion=0.03 |
| d4a6f2b5e1370a49 | combined | transform on sine master | clip + H2 combined |
| e5b7a3c6f2481b5a | multi_tone | repo-synthesized 200+400 Hz | |
| f6c8b4d7a3592c6b | speech | ESC-10 crying_baby (187207) | human vocal proxy |
| 07d9c5e8b46a3d7c | musical_instrument | ESC-10 clock_tick (21934) | quasi-musical periodic real recording |
| 18ea06f9c57b4e8d | environmental_non_periodic | ESC-10 helicopter (172649) | |
| 29fb17a0d68c5f9e | low_snr_periodic | repo-synthesized 440 Hz + noise | SNR 5 dB |
| 3a0c28b1e79d60af | controlled_distorted_periodic | repo-synthesized 700 Hz sine | subharmonic-lock probe |
| 4b1d39c2f8ae71b0 | environmental_non_periodic | ESC-10 rain (21189) | |
| 5c2e4ad309bf82c1 | environmental_non_periodic | ESC-10 sea_waves (39901) | |

**Total:** 12 cases covering all 10 design categories (some categories have multiple cases).

**V0.2 overlap check:** no `source_recording_key` overlaps SMARD / Pyramic / V0.2 ESC / NSynth catalog entries. ESC-10 files use distinct `src_file` IDs (172649, 187207, 21189, 21934, 39901).

---

## 2. Source/license status

| source_id | license | attribution |
|-----------|---------|-------------|
| v03_repo_synthesized | repository-generated | deterministic local synthesis; full SHA-256 in manifest |
| esc10_* (5 entries) | CC-BY-4.0 (ESC-10 subset) | Piczak ESC-50/ESC-10; upstream WAV SHA-256 recorded in `build_meta.upstream_sha256` |

All analysis WAVs are mono PCM24 with per-file SHA-256 in `dev_manifest.json`. Qualification used **reference analyzer 1.1.0 only**; production `analyze_harmonic_distortion` was not used for source labeling.

---

## 3. Reference validator version

| Identity | Version | Entry point | Use |
|----------|---------|-------------|-----|
| V0.2 historical | **1.0.0** | `analyze_reference()` | EV-T027 preservation; sealed V0.2 bundles unchanged |
| V0.3 independent | **1.1.0** | `analyze_reference_v03()` | dev split qualification; manifest field `reference_analyzer_version` |

Implementation path: `reference_harmonics.py` (numpy-only, EV-C032). V0.2 historical identity **1.0.0** is preserved in API and tests.

---

## 4. A/B DSP metrics on real WAV

Production path metrics recorded in `ab_dsp_metrics.json`.

**Periodic / transform masters (valid harmonic analysis):**

| case | FRE | f0_reliability | valid | THD % | octave_ambiguity |
|------|-----|----------------|-------|-------|------------------|
| single_tone | 0.667 | reliable | true | ~0 | false |
| injected_h2 | 0.656 | reliable | true | 12.5 | false |
| clipping | 0.667 | reliable | true | ~0 | false |
| combined | 0.628 | reliable | true | 25.0 | false |
| multi_tone | 0.333 | reliable | true | ~100 | false |

**Real recordings / stress cases:**

| case | FRE | f0_reliability | valid | notes |
|------|-----|----------------|-------|-------|
| speech | 0.0035 | unreliable | false | mis-lock F0 ≈ 706 Hz |
| clock_tick | 6.6e-06 | unreliable | false | |
| helicopter | 1.4e-06 | unreliable | false | |
| low_snr | 1.5e-05 | unreliable | false | mis-lock F0 ≈ 88 Hz |
| 700 Hz probe | ~0 | unreliable | false | octave_ambiguity **true**, F0 ≈ 350 Hz |
| rain / sea_waves | null | null | false | unvoiced |

---

## 5. FRE distribution

Observed bands on real dev WAV:

- **Pure / low-distortion periodic:** FRE ≈ **0.63–0.67**
- **Multi-tone (200+400):** FRE ≈ **0.33**
- **Unreliable / non-periodic:** FRE < **4×10⁻³** or null (unvoiced)
- **Subharmonic-lock probe (700 Hz):** FRE ≈ **1.5×10⁻²⁰**

Consistent with Phase 1.5 synthesized calibration; finite-window pure sines cluster near 0.67, not 1.0.

---

## 6. Octave ambiguity results

Only **`3a0c28b1e79d60af` (700 Hz controlled distorted periodic)** set `octave_ambiguity_detected=true` with F0 lock at **350 Hz**.

Pure sines, multi-tone, and ESC real recordings: **no false octave flags** on this dev split.

---

## 7. Validity-gate false-invalid / missed-unreliable analysis

**Engineering default:** `min_fundamental_relative_energy = 0.15`

| Metric | @ 0.15 | Interpretation |
|--------|--------|----------------|
| missed-unreliable | **0** | All FRE-unreliable voiced cases correctly invalidated |
| false-invalid (strict counter) | 2 (`4b1d`, `5c2e`) | **Artifact:** unvoiced environmental cases (FRE=null, f0_reliability=null) — should not count as periodic false-invalid |
| threshold scan (FRE not null) | 0 false-invalid / 0 missed-unreliable | for thresholds 0.05–0.25 |

**Conclusion:** 0.15 remains appropriate on this dev split. No parameter change authorized.

---

## 12. Parameter changes and justification

| Parameter | Old | New | Decision |
|-----------|-----|-----|----------|
| `min_fundamental_relative_energy` | 0.15 | **0.15 (unchanged)** | Zero missed-unreliable; periodic cluster well above 0.15; unreliable regime < 10⁻⁵ |
| `octave_ambiguity_tolerance` | 0.95 | **0.95 (unchanged)** | Single expected flag on 700 Hz probe; no pure-sine false flags |

No tuning used V0.2 sealed final set.

---

## 8. Real-model v9.0 behavior

**Run:** 12 cases, ~2.1 min, DeepSeek via `RealLLMPlanner` (v9.0).

| Outcome | Count | Cases |
|---------|-------|-------|
| no_supported_fault | 2 | single_tone, **clipping** |
| supported_fault | 3 | injected_h2, combined, low_snr |
| inconclusive | 1 | multi_tone |
| planner error (no finish) | 6 | speech, clock_tick, helicopter, 700 Hz probe, rain, sea_waves |

### Checklist vs authorization

1. **THD FAIL ≠ automatic harmonic_distortion:** **PASS on multi_tone** — inconclusive with limitation citing THD FAIL without causal mechanism. **Mixed on injected_h2** — supported_fault with explicit order-2 evidence (acceptable for ground-truth injected case).
2. **valid=true + insufficient attribution → inconclusive:** **PASS** (multi_tone).
3. **Over-conservative supported_fault:** No spurious harmonic_distortion on clean single_tone. **Concern:** clipping case returned no_supported_fault (see §10).
4. **evidence_refs / rule_refs / limitations:** Present and populated on successful finishes; inconclusive case includes required limitation text per §9.
5. **Unnecessary tool actions:** All successful runs used exactly `[detect_clipping, analyze_harmonic_distortion]` — no extra tools.
6. **A/B reliability evidence interpretation:** When harmonic `valid=false`, model often attempted `retrieve_knowledge` with **invalid JSON schema** (`query_text` missing) → runtime error after 3 retries. Reliability gating works in DSP; **prompt/runtime path for invalid harmonic is not production-ready**.

---

## 9. Inconclusive behavior

**Positive example (e5b7a3c6f2481b5a, multi_tone):**

- Outcome: `inconclusive`
- Claim: THD rule FAIL + valid harmonic measurement + no clipping mechanism
- Limitation: *"THD rule FAIL establishes elevated harmonic content… not causal harmonic_distortion without additional distortion-mechanism Evidence."*
- Matches v9.0 §9 representative path.

**Gap:** Cases with `harmonic.valid=false` did not reach a clean inconclusive finish; planner schema errors blocked completion.

---

## 10. Harmonic TP / FP / FN analysis

Ground truth from dev construction (transform / synthesis labels):

| Label | Case | Agent outcome | Verdict |
|-------|------|---------------|---------|
| TP harmonic | b2e4d0f3 (injected) | supported_fault + harmonic_distortion | TP |
| TP harmonic + clip | d4a6f2b5 (combined) | supported_fault both | TP |
| TN harmonic | a1f3c9e2 (single_tone) | no_supported_fault | TN |
| TN harmonic (conservative) | e5b7a3c6 (multi_tone) | inconclusive (no harmonic_distortion claim) | TN / intended conservatism |
| FN clip | c3f5e1a4 (clipping) | no_supported_fault | **FN** — clip transform may be below demo 1% threshold on this master |
| N/A | invalid-harmonic cases (6) | planner error | unscored |

No clear **FP harmonic_distortion** on clean single-tone.

---

## 11. Prompt iteration history

| Iteration | Prompt SHA | Code SHA | Change | Result |
|-----------|------------|----------|--------|--------|
| 1 (initial) | `bbc6ec4…` | `0261499…` | none (baseline v9.0) | 6/12 planner errors on invalid harmonic; 1 inconclusive success; clipping FN |

**No prompt wording changes** in this validation pass (per authorization: record before iterate).

---

## 13. Remaining root causes

1. **Invalid-harmonic finish path:** Real model emits malformed `retrieve_knowledge` decisions when harmonic analysis is invalid/unvoiced → 50% case error rate on heterogeneous real recordings.
2. **Dev clipping master:** `c3f5e1a4` clipping transform did not produce agent-detectable clipping at demo thresholds (DSP clipping_ratio may be ≤ 1%).
3. **low_snr clipping FP:** Agent claimed clipping on noise-heavy sine (`29fb17a0`) — likely full-scale/noise artifact; needs review.
4. **ESC-10 speech proxy:** crying_baby is vocal but not structured speech; dedicated speech corpus deferred.
5. **Architecture test T285:** `test_t285_phase5_cumulative_contract_is_registered` still fails on **Phase 1–4.3.1 frozen path drift** from `evaluation/external/*` (branch-level, pre-existing). **`git diff --check` trailing whitespace: PASS** after hygiene commit.

---

## 14. Whether A/B/C are ready to freeze for val

| Workstream | Ready for val freeze? | Rationale |
|------------|----------------------|-----------|
| **A** (F0 reliability / octave) | **Conditional yes** | 700 Hz probe behaves as designed; no pure-sine false octave flags on real dev |
| **B** (validity gate / FRE) | **Conditional yes** | 0.15 validated; zero missed-unreliable on FRE-bearing cases |
| **C** (prompt v9.0) | **No** | 50% error rate on invalid-harmonic real recordings; needs prompt iteration + re-run before val |

---

## 15. Exact blockers before val split

1. **Prompt iteration (C):** Add explicit v9.0 guidance for `harmonic.valid=false` / unvoiced — finish inconclusive without mandatory knowledge retrieval; ensure `retrieve_knowledge.query_text` is emitted when knowledge is chosen.
2. **Re-run real-model dev campaign** after prompt SHA update with logged run summary.
3. **Expand dev split** toward Workstream D val-ready counts (currently 12 dev cases; no val/test materialization).
4. **Optional B refinement:** Document unvoiced exclusion in false-invalid metrics; confirm clipping transform parameters produce demo-threshold clipping for ground-truth clip cases.
5. **Repository gate:** Resolve or exempt T285 frozen-path assertion for authorized `evaluation/external` V0.3 surface (branch hygiene, not product regression).
6. **Explicit user authorization** for val split freeze (currently **prohibited**).

---

## Step 0 baseline verification

| Check | Status |
|-------|--------|
| Markdown trailing whitespace (`git diff --check`) | **PASS** |
| Preservation EV-T001 | **PASS** |
| mypy `src/` | **PASS** |
| Full pytest | **1160 passed, 1 failed** (T285 frozen-path drift on `evaluation/external/*`) |
| ruff | Pre-existing warnings in uncommitted scratch paths; committed `src/` clean via mypy gate |

---

**STOP:** Dev validation complete. Val split not built. Test split not touched. No push. No PR.
