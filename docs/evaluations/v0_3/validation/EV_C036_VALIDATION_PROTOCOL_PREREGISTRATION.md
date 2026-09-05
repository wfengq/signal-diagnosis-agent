# V0.3 Validation Protocol & EV-C036 Pre-registration

**Status:** PRE-REGISTERED — v9.9 identity amendment approved and frozen
**Study ID:** `v0.3-real-validation-1`
**Protocol version:** `1.2.0-prereg`
**Document revised:** 2026-09-05
**Re-review acknowledgment:** approved 2026-09-05
**This phase does not run models, open validation/test WAV payloads, or change product code.**

## 0. Frozen product baseline (inputs)

| Item | Frozen value |
|------|----------------|
| Code commit (semantic freeze) | `15c047ced6cbd46a4b4757abdfdacd11e0a12ea1` |
| Dev evidence commit | `a45177574ad09d41b4c26c8bdf93e85ca6a7eed8` |
| Prompt version | `v0.3-s1-planner-9.9` |
| Prompt SHA-256 | `27a9315ad85a035c9cc9cbfe5f15ea26c49383d7fb23207989315ae0adb78dc9` |
| Causal policy | `v9_9_paired_reference_recovery` |
| Implementation SHA-256 | `5bc2a3375d5fb5be5c7c77cb0ddba140c240635d549662c9d3221e64acb81ae2` |
| Dev manifest SHA-256 | `cca0ee24d8574435761d2d057fd4341c5e015ee7d5337826f796ea832cf047dd` |
| Dev confirmation | 20/20 planner completion; 17/17 outcome, causal exact-set, and grounding; independently audited under `agent_v9_9_dev_confirmation_1/` |
| Rule profiles | `profile_s1_distortion` `1.0.0-demo` SHA `1e02d0da…f5ed1`; `profile_s1_contextual_comparison` `1.0.0` SHA `c79865ca…d9eb58` (unchanged; not industry SLAs) |
| Scoring identity | `signal_diag.contextual_scoring@1.0.0-dev.1` |

Any later materialization or Agent run must record these SHAs. Drift without a new written amendment voids the pre-registration.

Protocol `1.2.0-prereg` changes only the frozen product/development identity and
expands the development isolation forbid-list. It does not change the 20-slot
design, confidence assignments, scoring denominators, acceptance thresholds,
role hard gates, or one-shot policy defined in `1.1.0-prereg`.

---

## 1. Validation sample size and outcome distribution

### 1.1 Size

| Split | Case count | Scoreable (`strong_ground_truth` ∪ `reference_supported`) | Unscored (`weak_observation` ∪ `unknown`) |
|-------|------------:|----------------------------------------------------------:|------------------------------------------:|
| validation | **20** | **17** | **3** |

Rationale: larger than V0.2 external validation (10) to cover V0.3 causal gates and natural even-order false-positive controls; smaller than a final test so one-shot cost stays bounded. Final test size is **not** fixed here and remains gated (§8).

### 1.2 Expected-outcome / role distribution (all 20)

| Role ID | Expected outcome | Causal exact-set (when scoreable) | Count | Notes |
|---------|------------------|-----------------------------------|------:|-------|
| `clean` | `no_supported_fault` | `{}` | **3** | No controlled distortion |
| `clipping_pos` | `supported_fault` | `{clipping}` | **3** | New clipping positives |
| `harmonic_pos` | `supported_fault` | `{harmonic_distortion}` | **3** | New controlled even-order injection positives |
| `combined_pos` | `supported_fault` | `{clipping, harmonic_distortion}` | **2** | New combined positives |
| `natural_even_neg` | `inconclusive` | must **not** claim `harmonic_distortion` | **2** | Natural even-order; **no** controlled distortion; both `reference_supported` |
| `natural_rich` | `inconclusive` | n/a | **3** | multi-tone / square / harmonic-rich natural |
| `low_snr` | `inconclusive` | n/a | **2** | Low-SNR periodic / unreliable lock |
| `ood` | `inconclusive` | n/a | **2** | Speech / environmental / other OOD |

**Totals:** clean 3 + clipping 3 + harmonic 3 + combined 2 + inconclusive-family 9 = **20**.

### 1.3 Confidence tier assignment (fixed counts — no silent downgrade)

| Confidence | Count | Binding assignment |
|------------|------:|--------------------|
| `strong_ground_truth` | **8** | All `clipping_pos` (3) + `harmonic_pos` (3) + `combined_pos` (2) |
| `reference_supported` | **9** | All 3 `clean` + **exactly 6** scoreable inconclusive (must include both `natural_even_neg`) |
| `weak_observation` | **2** | From remaining inconclusive-family slots |
| `unknown` | **1** | Remaining hard OOD |

Scoreable = 8 + 9 = **17**. Unscored = 2 + 1 = **3**.

**Fixed denominators (construction hard stops):**

| Fixed quantity | Value | Rule |
|----------------|------:|------|
| Scoreable inconclusive (`reference_supported` ∧ expected `inconclusive`) | **exactly 6** | Not “≥6”. If construction cannot place all six, **stop and amend** — never silently downgrade confidence |
| `natural_even_neg` confidence | both **must** be `reference_supported` | No weak/unknown substitution |

If any planned confidence cannot be honestly adjudicated, construction **halts** and requires a written protocol amendment. Silent confidence downgrade is forbidden.

### 1.4 Source composition (frozen)

| Rule | Requirement |
|------|-------------|
| Public real recordings | **≥10 / 20** cases derived from license-clear public **real** recordings (not pure repo synthesis-only) |
| Strong-positive masters | The **8** `strong_ground_truth` positives must come from **≥4** independent **real recording** parent masters |
| Per-master positive cap | A single `parent_master_id` may contribute **at most 2** scoreable positives |
| Reference/unscored diversity | The union of `reference_supported` + unscored cases must cover **≥3** independent `source` / `source_recording` families |

Consequence of the per-master cap with 8 strong positives: at least four distinct real parent masters; typical pattern is four masters × two positives each (transforms applied only to those independent masters — see §2).

---

## 2. Split isolation (strengthened)

### 2.1 Forbidden reuse

Validation **must not**:

1. Reuse any of the **34 development case_ids** listed in `val_slot_plan.json` (14 legacy V0.3 dev plus 20 contextual dev)
2. Reuse any development `wav_sha256` from `dev_manifest.json`
3. Reuse V0.2 sealed `final_external_test` case_ids, asset SHA sets, or sealed study payloads
4. Clone a development WAV and re-hash under a new id

### 2.2 Cross-split identity ban (any one match forbids)

A validation case is **forbidden** if it shares **any** of the following with a development case, a V0.2 sealed final case, or another split’s reserved identity:

| Identity axis | Rule |
|---------------|------|
| `parent_master_id` | Same value ⇒ same lineage group; **no cross-split use** |
| `source_recording_key` | Same value ⇒ same lineage group; **no cross-split use** |
| Capture / session lineage | Same capture session, take, or recorded session id ⇒ same lineage group; **no cross-split use** |

**Crops:** different time crops / channel extracts / fades of the **same** recording remain the **same lineage group**. They do **not** create a new independent master.

**Transforms do not create independence:** applying a different transform recipe, alpha, clip level, or seed to a shared master / recording / session **does not** authorize reuse across splits. Transform recipes may be applied **only** to **new, independent** parent masters that are themselves split-isolated.

### 2.3 Transform policy

1. Controlled clipping / H2 / combined transforms run only on validation-owned independent parent masters
2. Parameters are recorded in `build_meta`
3. Byte-identical reuse of rematerialized development assets (`c3`, `d4a6`, `b2`, …) is forbidden
4. “Same master, different transform” is **not** a valid isolation argument

### 2.4 Allowed similarity (non-identity)

Same public **corpus family** (e.g. ESC-class, instrument corpora) may appear if `parent_master_id`, `source_recording_key`, and capture/session lineage are all disjoint from development and from V0.2 sealed final.

---

## 3. Required content classes (construction mandates)

| Mandate | Minimum | Construction note |
|---------|--------:|-------------------|
| New harmonic positive | 3 | Controlled injection on independent val masters; `strong_ground_truth` |
| New clipping positive | 3 | Substantial clipping Evidence path; independent val masters |
| New combined positive | 2 | Clip + H2 on independent val masters |
| Natural even-order negative | 2 | Both `reference_supported`; no controlled distortion; harmonic FP probe |
| multi-tone / square / harmonic-rich | 3 | Expected `inconclusive` |
| Low-SNR | 2 | Expected `inconclusive` |
| OOD | 2 | Expected `inconclusive` |
| Public real recordings | ≥10/20 | License-clear; documented |
| Distinct real masters for strong positives | ≥4 | With ≤2 scoreable positives per master |

Slot plan: `docs/evaluations/v0_3/validation/val_slot_plan.json`

---

## 4. Scoring qualification tiers

| Confidence | Scoring eligibility | Truth exposure | Typical use |
|------------|---------------------|----------------|-------------|
| `strong_ground_truth` | **Scoreable** | Full expected outcome + causal set | Controlled transforms with provenance on real masters |
| `reference_supported` | **Scoreable** | Full expected outcome + causal set | Clean; scoreable inconclusive incl. both natural-even negatives |
| `weak_observation` | **Unscored** for correctness | Must **not** expose scoring truth to the planner | Ambiguous natural / borderline SNR |
| `unknown` | **Unscored** for correctness | Must **not** expose scoring truth | Hard OOD |

### 4.1 Fixed scoreable denominators

Only `strong_ground_truth` and `reference_supported` are scoreable. Denominators for outcome / exact-set / macro-F1 are **fixed at construction seal** to **17** and do **not** shrink when a scoreable case hits infrastructure failure (§5.10).

### 4.2 Unscored policy

`weak_observation` / `unknown` still count in planner/infrastructure success over all 20 cases. Positive causal claims on unscored cases are diagnostic only (`positive_causal_claims_on_unscored`), not an EV-C036 hard gate unless amended.

### 4.3 Natural even-order negatives

- Both slots **must** be `reference_supported` (fixed)
- May exhibit DSP `series_kind=even_order_present`
- Expected outcome **must** be `inconclusive`
- Any `harmonic_distortion` claim is a hard-gate failure for the role

---

## 5. EV-C036 metrics — definitions (numerator / denominator)

Machine-readable targets: `ev_c036_acceptance_targets.json`.
Aggregates below are for the **Agent** campaign unless noted. Fixed-pipeline uses the same formulas for comparison (§6).

### 5.1 Planner / infrastructure success

- **Numerator:** cases finished without planner-output, provider, authentication, harness infrastructure error, or ScriptedPlanner fallback
- **Denominator:** **20** (all validation cases)
- Operator / threshold: ≥ **0.95**

### 5.2 Outcome accuracy

- **Numerator:** scoreable cases with predicted outcome == expected outcome **and** a successful finished diagnosis
- **Denominator:** **17** (fixed)
- Scoreable infrastructure / planner failures count as **incorrect** (remain in the denominator)
- Operator / threshold: ≥ **0.80**

### 5.3 Causal exact-set accuracy

- **Numerator:** scoreable cases whose predicted positive causal set equals the expected set **and** finished successfully
- **Denominator:** **17** (fixed); infrastructure failures count as **incorrect**
- Positive faults ∈ `{clipping, harmonic_distortion}` only
- Operator / threshold: ≥ **0.75**

### 5.4 Causal macro-F1

- Unweighted mean of per-label F1 for `{clipping, harmonic_distortion}` on the fixed scoreable population (failures contribute as non-matches / empty prediction as defined by the scorer)
- Operator / threshold: ≥ **0.75**

### 5.5 Evidence grounding

- **Numerator:** claims that satisfy grounding
- **Denominator:** all claims on finished Agent diagnoses in the campaign
- A claim that the contract requires to cite Evidence / rules **fails grounding if `evidence_refs` is empty** (or required `rule_refs` is empty when the contract demands them). Empty refs are never an automatic pass
- Same-run ID resolution is still required for every cited ref
- Operator / threshold: = **1.00**

### 5.6 Unsupported claim rate

- **Numerator:** positive fault claims that violate causal Evidence gates or lack same-run grounding
- **Denominator:** all predicted positive fault claims (`clipping` + `harmonic_distortion`)
- If **denominator = 0**, status is **`not_evaluated`** — this metric **must not** auto-pass
- When evaluated, operator / threshold: = **0.00**

### 5.7 Inconclusive appropriateness (fixed 6)

- Population: the **exactly 6** scoreable `reference_supported` cases with expected `inconclusive`
- **Numerator:** those with predicted `inconclusive` and **no** positive causal fault
- **Denominator:** **6** (fixed)
- Operator / threshold: ≥ **5/6** (numerator ≥ 5)

### 5.8 Unnecessary tool rate

- **Numerator:** unnecessary tool actions under the frozen path scorer
- **Denominator:** all tool actions in the Agent campaign
- Operator / threshold: ≤ **0.20**

### 5.9 Role hard gates (all must pass)

| Role | Gate | Fixed den | Pass rule |
|------|------|----------:|-----------|
| `clean` | outcome correct | 3 | ≥ **2/3** |
| `clipping_pos` | causal exact-set | 3 | ≥ **2/3** |
| `harmonic_pos` | causal exact-set | 3 | ≥ **2/3** |
| `combined_pos` | causal exact-set | 2 | = **2/2** |
| `natural_even_neg` | appropriate inconclusive + zero `harmonic_distortion` claims | 2 | = **2/2** inconclusive and **0** harmonic claims |
| scoreable inconclusive | inconclusive appropriateness | 6 | ≥ **5/6** |

Infrastructure failure on a role member counts against that role’s numerator (treated as incorrect / not appropriate).

### 5.10 Aggregate threshold summary

| Metric | Operator | Threshold |
|--------|----------|-----------|
| planner_infrastructure_success | ≥ | 0.95 |
| outcome_accuracy | ≥ | 0.80 |
| causal_exact_set_accuracy | ≥ | 0.75 |
| causal_macro_f1 | ≥ | 0.75 |
| evidence_grounding | = | 1.00 |
| unsupported_claim_rate | = | 0.00 when evaluated; else `not_evaluated` blocks pass |
| inconclusive_appropriateness | ≥ | 5/6 |
| unnecessary_tool_rate | ≤ | 0.20 |
| all §5.9 role hard gates | — | must all pass |

`meets_target` requires every aggregate gate in this table **and** every role hard gate. A `not_evaluated` unsupported_claim_rate **blocks** `meets_target`.

---

## 6. Agent vs fixed pipeline

| Path | Role |
|------|------|
| `fixed_pipeline` | Honest deterministic baseline; run **once** on the sealed validation manifest; no LLM |
| `agent` (`RealLLMPlanner`, prompt v9.9) | Product path under EV-C036; run **once** after baseline |

Rules:

1. Both paths use the **same** sealed manifest, rule profile, causal gates, and identity SHAs
2. **Between** the fixed-pipeline baseline run and the Agent run, it is forbidden to modify any product code, prompt, thresholds, DSP, rules, data bytes, labels, expected outcomes, confidence, or case/run identity
3. EV-C036 **pass/fail** is decided on the **Agent** aggregates + role hard gates
4. Fixed-pipeline metrics are mandatory comparison artifacts, not a substitute for Agent acceptance
5. Agent must not silently fall back to ScriptedPlanner

---

## 7. One-shot run, failure retention, anti-tuning stop rules

1. **One-shot:** exactly one Agent campaign and one fixed-pipeline campaign on the sealed validation set
2. **No slot retries:** failed or wrong cases retained; no selective re-runs
3. **Preserve all artifacts:** attempts, traces, results, summaries; code / prompt / manifest / model / timestamps
4. **No validation-driven tuning:** results must not edit prompt, thresholds, profile, DSP, labels, or expected outcomes
5. **Construction confidence failure:** stop and amend; never silent downgrade
6. **If below_target / not_evaluated blocking:** failure report; stop; no final test
7. **Infrastructure abort** before completion: retain partial artifacts; no ScriptedPlanner completion; new campaign requires explicit re-authorization

---

## 8. Gate to final test

Final test is **forbidden** until all hold:

1. Validation manifest sealed under this protocol (counts, isolation, source composition, fixed confidences)
2. Fixed-pipeline baseline archived
3. Agent one-shot completed with full artifacts
4. No product/data/label/identity edits between baseline and Agent (§6.2)
5. EV-C036 Agent status = `meets_target` (§5.10)
6. All role hard gates passed
7. Preservation / architecture / `git diff --check` green on the evaluation commit
8. **Explicit user authorization** naming final-test scope

---

## 9. Semantic constraints (mandatory language)

1. `series_kind=even_order_present` is **operational spectral structure only**, never injection provenance
2. Validation **must** include natural even-order negative controls
3. Causal `harmonic_distortion` requires `even_order_present` Evidence plus frozen THD FAIL path
4. Causal `clipping` requires `clipping_mechanism=true` plus substantial clipping rule FAIL
5. Demo 1% clipping / 5% THD thresholds are demonstration profile values, not industry SLAs

---

## 10. Out of scope for this pre-registration package

- Materializing WAVs or downloading corpora
- Opening validation/test audio bytes
- Changing product code, prompt, thresholds, or dev labels
- Running RealLLMPlanner or fixed pipeline on validation
- Commit / push / PR

---

## 11. Review checklist (human)

See `VALIDATION_CONSTRUCTION_CHECKLIST.md`.

**STOP after re-review.** Next step only with explicit authorization: catalog construction & seal (still no model runs), or further amendments.
