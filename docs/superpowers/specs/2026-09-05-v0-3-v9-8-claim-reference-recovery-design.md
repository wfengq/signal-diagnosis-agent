# V0.3 v9.8 Claim-Reference Recovery Design

**Status:** approved for implementation
**Date:** 2026-09-05
**Branch:** `codex/v0.2-real-world-validation`
**Baseline HEAD:** `da3d4eca3be83a57381936b2121d27d42353fda8`

## 1. Problem

The append-only v9.7 RealLLMPlanner development confirmation
(`agent_v9_7_dev_confirmation_1`) completed 19/20 planner diagnoses and scored
16/17 outcome / causal / grounding under failure-as-incorrect scoring. The sole
behavioral failure was case `35967af7b71c5b75` (role `harmonic`, mode
`nominal_single_tone`).

Post-mortem of that case shows:

- Tool path used `detect_clipping` + `analyze_contextual_distortion` (correct).
- Automatic rule closure produced both `profile_s1_distortion` and
  `profile_s1_contextual_comparison` batches (correct).
- Same-run Evidence already contained `test_series_kind=even_order_present` and
  `test_thd_percent` with `rule_nominal_thd_acceptable=fail`.
- Finish retries alternately omitted either the series Evidence citation or the
  nominal THD FAIL rule citation, exhausting planner retries
  (`max_planner_retries`) with messages such as `missing nominal THD FAIL` /
  `missing test_series_kind=even_order_present`.

Root cause is **claim-reference recovery under multi-requirement finish gates**,
not DSP, Tools, profiles, thresholds, data, labels, or scoring.

## 2. Goals

1. Freeze product identity `v0.3-s1-planner-9.8` with policy
   `v9_8_claim_reference_recovery`.
2. Fully inherit v9.7 Tool routing, automatic rule closure, finish gate
   *requirements*, and manual `evaluate_rules` rejection.
3. For **nominal** `harmonic_distortion` positive claims, require **one finish**
   that simultaneously retains:
   - contextual analysis PASS (`rule_contextual_analysis_valid`)
   - F0 compatibility PASS (`rule_contextual_f0_compatible`)
   - `test_series_kind=even_order_present` Evidence
   - `rule_nominal_thd_acceptable=FAIL`
   - the FAIL rule’s corresponding `test_thd_percent` Evidence
4. When finish is rejected, emit a single recoverable error that lists **all**
   current deficits with accurate same-run `evidence_id` / `ruleval_*` IDs and
   instructs the planner to fix them together.
5. Runtime must **not** auto-insert claim refs; the Planner still selects and
   submits citations.

## 3. Non-goals

- No DSP / Tool schema / profile YAML / threshold / WAV / label / scoring
  changes.
- No retry-budget changes.
- No edits to frozen v9.7 (or earlier) prompt bytes or historical run trees.
- No validation/ access; no real-model run in this harness phase.
- No `ScriptedPlanner` product fallback.

## 4. Policy inheritance

```text
CausalPolicyVersion += "v9_8_claim_reference_recovery"
```

| Behavior | v9.7 | v9.8 |
|----------|------|------|
| Mode-aware harmonic Tool routing | yes | inherit |
| Automatic Tool→profile closure | yes | inherit |
| Manual `evaluate_rules` rejection | yes | inherit |
| Finish requirement set (nominal harmonic) | PASS/PASS/series/THD FAIL | same + explicit `test_thd_percent` citation |
| Finish rejection messaging | first deficit only, no IDs | accumulate all deficits with IDs |
| Auto-add claim refs | never | never |

v9.7 recorded runs and prompt SHA remain immutable preservation targets.

## 5. Finish-validator change (v9.8 only)

Under `v9_8_claim_reference_recovery`, for
`supported_fault` + `harmonic_distortion` + `nominal_single_tone`:

1. Evaluate the five citation requirements against the claim’s cited refs.
2. For each missing requirement, look up matching **same-run** Evidence /
   RuleEvaluation IDs (from the full run inventories, not invented IDs).
3. If any deficits exist, raise one `DiagnosisValidationError` whose message:
   - states that the nominal harmonic claim is incomplete;
   - lists every deficit with concrete `evidence_id` / `evaluation_id` values
     when present in the run;
   - requires citing **all** listed IDs together on the next finish;
   - never mutates the claim.

Paired / clipping / no-fault / inconclusive gates remain the inherited v9.7
semantics unless a deficit collector is reused for consistent multi-error
reporting without changing required citations.

## 6. Prompt change

Build `_S1_PROMPT_V9_8` from frozen v9.7 bytes via `_replace_once` only (do not
edit the v9.7 constant). Add explicit nominal-harmonic finish recovery guidance:

- After automatic contextual rule batches exist, a nominal harmonic
  `supported_fault` finish must cite the complete set in one decision.
- On recoverable finish errors listing multiple IDs, repair every listed ID
  together; do not alternate single-field fixes.
- Retain “Never fall back to ScriptedPlanner.” and no positive manual
  `evaluate_rules` instructions.

## 7. Product wiring

- `PROMPT_VERSION` / `RealLLMPlanner._prompt_spec` → v9.8
- `composition.py` `causal_policy_version` → `v9_8_claim_reference_recovery`
- `rule_closure.required_rule_profile` and runtime routing/rejection accept
  both v9.7 and v9.8 policy literals

## 8. Tests (T-CX186–T-CX190)

| ID | Intent |
|----|--------|
| T-CX186 | v9.7 prompt SHA + registry uniqueness for T-CX186–190 |
| T-CX187 | Nominal harmonic finish requires all five citations together |
| T-CX188 | Rejection message includes same-run evidence_id/ruleval IDs for all deficits |
| T-CX189 | v9.8 prompt freezes recovery wording; v9.7 bytes unchanged |
| T-CX190 | Composition wires v9.8; inherits v9.7 routing/closure/manual-rule rejection |

## 9. Acceptance

Harness-only conclusion permitted:

```text
v9_8_harness_complete
```

Not permitted without a new real-model authorization:

- `development_confirmed`
- performance improvement claims
- validation access

## 10. Protected assets

Preserve V0.2 official/Demo, v8.1/v9.4–v9.7 identities and run directories,
both profile SHA-256 values, scoring identity, and untracked user paths:

- `docs/evaluations/v0_2_external_wav/investigation_report_2026-09-02.md`
- `docs/evaluations/v0_3/validation/`
