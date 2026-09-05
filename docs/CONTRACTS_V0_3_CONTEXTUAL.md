# CONTRACTS_V0_3_CONTEXTUAL.md

**Status:** additive V0.3 contracts

**Extends:** `docs/CONTRACTS_V0_2.md` (does **not** edit or supersede frozen §§1–64)

**Design:** `docs/superpowers/specs/2026-09-04-v0-3-contextual-reference-diagnosis-design.md`

**Test IDs:** `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` (T-CX001–T-CX207)

## 1. Scope

This document freezes normative names, modes, DSP/tool/rule/runtime/app/evaluation
surfaces for Scenario S1 **contextual reference diagnosis**. Existing V0.2 public
interfaces, DTO meanings, `profile_s1_distortion` `1.0.0-demo` thresholds (1%
clipping / 5% THD), v8.1/v9.4 prompt identities, official bundles, Demo assets,
and tag `v0.2.0` remain immutable.

## 2. Diagnostic modes

```text
DiagnosticMode = "single_signal" | "nominal_single_tone" | "paired_reference"
```

Mode validation:

| Mode | Requires | Rejects |
|------|----------|---------|
| `single_signal` | test WAV only | reference WAV; nominal stimulus fields |
| `nominal_single_tone` | `stimulus_kind="single_tone"`; finite positive `nominal_fundamental_hz` | reference WAV |
| `paired_reference` | distinct `reference_signal_id` / reference WAV | missing reference |

`ContextAssertionSource = "user_supplied" | "evaluation_manifest"`.

## 3. StimulusContext

Immutable provenance object (not numerical Evidence):

- `mode: DiagnosticMode`
- `test_signal_id: str`
- `reference_signal_id: str | None`
- `nominal_fundamental_hz: float | None` (finite, `> 0` when required)
- `stimulus_kind: Literal["single_tone"] | None`
- `assertion_source: ContextAssertionSource`

Planner may read this for task framing; it must not cite it as Evidence.

`EffectiveCapabilities` records requested mode vs available comparison/clipping
paths after qualification.

## 4. Application service

Frozen V0.2 `DiagnosisApplicationService.submit_wav(...)` and
`POST /api/v1/runs/wav` remain unchanged and create an internal `single_signal`
context.

Additive operation:

```text
submit_contextual_wav(
  *,
  test_wav_bytes: bytes,
  test_filename: str,
  mode: DiagnosticMode,
  reference_wav_bytes: bytes | None = None,
  reference_filename: str | None = None,
  nominal_fundamental_hz: float | None = None,
  stimulus_kind: Literal["single_tone"] | None = None,
  user_request: str,
  channel_mode: ChannelMode = ...,
) -> ContextualRunSnapshot
```

API: `POST /api/v1/contextual-runs/wav`

Snapshot/report: `/api/v1/contextual-runs/{run_id}` (+ report subroute)

CLI: `signal-diag diagnose contextual TEST_PATH` with `--mode`, `--reference`,
`--nominal-fundamental-hz`, `--stimulus-kind`

Web UI: optional mode selector; default remains one-file flow.

Per-file WAV limits unchanged; multipart also enforces a bounded aggregate
request limit from two file limits + fixed form overhead.

## 5. Contextual DSP results (deterministic, NumPy only)

Qualification / comparison must not resample mismatched sample rates.

Core result types (exact field sets implemented in Tasks 3–4):

- `ReferenceQualificationResult` / Evidence: signal IDs, channel mode, sample-rate
  compatibility, duration compatibility, periodicity/voicing validity per signal,
  fundamentals + reliability, fundamental compatibility, reference clipping
  indicators, `comparison_valid`, machine-readable `invalid_reasons`.
- `HarmonicComparisonResult` / Evidence: normalized harmonic amplitudes (per
  signal fundamental), per-order growth, reference/test THD and delta, F0 delta,
  alignment/gain diagnostics, validity, limitations.
- `ClippingComparisonResult` / Evidence: reference vs test clipping ratio,
  full-scale runs, flat-top indicators (advisory; positive clipping still uses
  existing single-signal mechanism path).

Causal decisions use **normalized** harmonic growth, not sample subtraction.

## 6. Tool

Additive tool name (exact registration in Task 4):
`compare_with_reference` (or the plan’s final registered `ToolName` alias).

Returns compact Evidence only — no waveform/FFT arrays to the planner.

## 7. Rules

- Existing profile: `profile_s1_distortion` `1.0.0-demo` unchanged.
- Additive profile: `profile_s1_contextual_comparison` `1.0.0` with versioned
  growth / compatibility thresholds calibrated on development only and frozen
  before validation construction.

Rule families (IDs finalized in Task 5 YAML):

- reference qualification validity / compatibility
- harmonic growth FAIL for paired mode
- absolute harmonic/THD path for nominal mode (still citing same-run Evidence)
- no replacement of clipping-ratio or flat-top demo thresholds

## 8. Causal gates (runtime-enforced)

### Clipping (all modes)

Requires `clipping_mechanism=true` **and** substantial clipping rule FAIL
(`rule_clipping_ratio_acceptable` or `rule_flat_top_absent`). Independent of
harmonic/comparison validity.

### Harmonic — `paired_reference`

Requires valid qualification, compatible fundamentals, valid harmonic comparison
Evidence, versioned harmonic-growth rule FAIL, same-run refs. Absolute THD FAIL
or `even_order_present` alone is insufficient.

### Harmonic — `nominal_single_tone`

Requires declared single-tone context, measured F0 compatible with declaration,
valid harmonic Evidence + versioned absolute harmonic/THD FAIL, same-run refs,
and a mandatory limitation that the conclusion is conditional on the declaration.

### Harmonic — `single_signal`

Absolute THD FAIL / `even_order_present` may be descriptive only; they cannot
alone support causal `harmonic_distortion`. Clipping may still succeed on its
independent path; otherwise unresolved high harmonics → `inconclusive` requesting
reference or declared tone.

### Combined

Requires independently sufficient clipping **and** harmonic paths under the
active mode. No positive fault + sibling `no_supported_fault`.

## 9. Outcomes

- `supported_fault` iff ≥1 positive cause passes its complete mode gate
- `no_supported_fault` iff analyses are valid/complete and no supported FAIL
- `inconclusive` iff invalid context/comparison/identifiability gaps
- infrastructure/provider failure is never converted to a diagnosis; no
  `ScriptedPlanner` fallback

## 10. Planner identity

Product contextual path uses frozen prompt identity `v0.3-s1-planner-9.9`
with causal policy `v9_9_paired_reference_recovery`. Historical identities
remain immutable:

- `v0.3-s1-planner-9.9` / `v9_9_paired_reference_recovery`
- `v0.3-s1-planner-9.8` / `v9_8_claim_reference_recovery`
- `v0.3-s1-planner-9.7` / `v9_7_deterministic_rule_closure` (bytes and finish semantics frozen)
- `v0.3-s1-planner-9.6` / `v9_6_contextual` (bytes and finish semantics frozen)
- `v0.3-s1-planner-9.5` / `v9_5_contextual` (bytes and finish semantics frozen)
- `v0.3-s1-planner-9.4` and earlier

## 10.1 Causal policy versions

```text
CausalPolicyVersion =
  "v9_4_legacy"
  | "v9_5_contextual"
  | "v9_6_contextual"
  | "v9_7_deterministic_rule_closure"
  | "v9_8_claim_reference_recovery"
  | "v9_9_paired_reference_recovery"
```

| Policy | Finish gates | Mode-aware harmonic Tool routing | Rule evaluation |
|--------|--------------|----------------------------------|-----------------|
| `v9_4_legacy` | legacy | none | manual `evaluate_rules` |
| `v9_5_contextual` | frozen v9.5 contextual gates | none (historical) | manual `evaluate_rules` |
| `v9_6_contextual` | reuses v9.5 contextual finish gates | rejects `analyze_harmonic_distortion` in `paired_reference` / `nominal_single_tone` before execution | manual `evaluate_rules` |
| `v9_7_deterministic_rule_closure` | reuses v9.6 contextual finish gates | reuses v9.6 Tool-routing guard | automatic Tool-to-profile closure; planner `evaluate_rules` rejected |
| `v9_8_claim_reference_recovery` | inherits v9.7 requirements; accumulates ID-bearing nominal-harmonic recovery errors | inherits v9.7 | inherits v9.7 automatic closure + manual rejection |
| `v9_9_paired_reference_recovery` | inherits v9.8 requirements; also accumulates ID-bearing paired-harmonic recovery errors | inherits v9.8 | inherits v9.8 automatic closure + manual rejection |

Under `v9_6_contextual` only:

- rejected ordinary harmonic Tool calls consume one planner retry and zero Tool
  budget; no Tool Evidence is created;
- the recoverable error must name `analyze_contextual_distortion`;
- `single_signal` continues to allow `analyze_harmonic_distortion` (descriptive);
- clipping remains independently finishable in every mode.

v9.5 behavior is frozen and must not gain the new routing guard. Explicit tests
and dependency injection may still construct older policy identities.

## 10.2 `v9_7_deterministic_rule_closure`

Under `v9_7_deterministic_rule_closure` only:

### Tool → profile mapping

- `detect_clipping` in every diagnostic mode → `profile_s1_distortion`
- `analyze_harmonic_distortion` in `single_signal` → `profile_s1_distortion`
- `analyze_contextual_distortion` in `paired_reference` or
  `nominal_single_tone` → `profile_s1_contextual_comparison`
- `analyze_spectrum` and `estimate_fundamental` → no closure
- Observation with Tool status `error` → no closure
- Observation with Tool status `success` or `invalid` for a relevant Tool →
  exactly one automatic RuleEngine batch

### Automatic Evidence suffix

- Closure uses the triggering Observation's complete ordered `evidence_refs`
  as the Evidence filter; callers cannot supply an arbitrary subset.
- A relevant non-error Tool with an empty Evidence suffix is a runtime contract
  violation and terminates as `runtime_error`.
- Automatic closure consumes exactly one existing `max_rule_evaluations` slot
  after a successful/invalid relevant Tool; errored Tools do not consume a slot.

### Manual rule rejection

- Planner-created `evaluate_rules` is a recoverable behavioral error after the
  normal initial task-assessment requirement.
- Rejection consumes one planner retry and zero Tool/rule budget; creates no
  Evidence and no rule batch; is not infrastructure.
- Typed `EvaluateRulesDecision` remains for older policies and historical
  traces.

### Trace event order

For a relevant non-error Tool decision, chronologically:

1. existing `PlannerDecisionEvent` for the Tool call
2. one `ObservationEvent` with the exact Evidence suffix
3. one `RuleEvaluationEvent` for the automatic batch

Observation and rule events share the same `caused_by_decision_index` (the
Tool decision). Irrelevant or errored Tools keep the historical shape with no
automatic rule event.

### Legacy compatibility

- v9.4 / v9.5 / v9.6 prompts, policies, thresholds, and recorded runs remain
  immutable; no historical prompt constant may be edited.
- Existing recorded traces require no migration and must round-trip unchanged.
- Finish gates are not weakened; v9.7 reuses the v9.6 contextual finish
  validator.

### Authorization / conclusion gates

- `v9_7_harness_complete` is the strongest offline conclusion permitted by this
  remediation; it does not mean `development_confirmed`, validation passed, or
  performance improved.
- Real-model confirmation, validation access, and push/PR remain separately
  authorized.

## 10.3 `v9_8_claim_reference_recovery`

Under `v9_8_claim_reference_recovery` only:

- Inherit v9.7 Tool→profile mapping, automatic Evidence suffix, manual rule
  rejection, and chronological Observation→RuleEvaluation provenance.
- Finish requirement sets are not weakened relative to v9.7.
- For `supported_fault` + `harmonic_distortion` + `nominal_single_tone`, one
  finish must simultaneously cite:
  1. `rule_contextual_analysis_valid=pass`
  2. `rule_contextual_f0_compatible=pass`
  3. valid `test_series_kind=even_order_present` Evidence
  4. `rule_nominal_thd_acceptable=fail`
  5. the FAIL rule’s corresponding `test_thd_percent` Evidence
- When any of those citations are missing, the recoverable error lists **all**
  current deficits in one message, naming accurate same-run `evidence_id` /
  `evaluation_id` values when present, and requires repairing every listed
  deficit together on the next finish.
- Runtime must not insert claim `evidence_refs` or `rule_refs`; the Planner
  remains responsible for selecting and submitting citations.
- Frozen v9.7 prompt bytes, policy semantics, and recorded runs remain
  immutable.

### Authorization / conclusion gates (v9.8)

- `v9_8_harness_complete` is the strongest offline conclusion for this
  remediation; it does not mean `development_confirmed`, validation passed, or
  performance improved.
- A new real-model development confirmation requires separate written
  authorization and an append-only run directory.

## 10.4 `v9_9_paired_reference_recovery`

Under `v9_9_paired_reference_recovery` only:

- Inherit every v9.8 finish requirement, routing rule, automatic closure rule,
  and nominal recovery behavior without weakening it.
- For `supported_fault` + `harmonic_distortion` + `paired_reference`, one
  finish must simultaneously cite the existing five paired rule requirements:
  contextual analysis PASS, contextual F0 compatibility PASS, reference
  clipping-ratio PASS, reference flat-top PASS, and even-harmonic-growth FAIL.
- A rejected paired finish lists all current deficits in one message and names
  accurate same-run `evaluation_id` values when present.
- Paired recovery must not suggest or accept
  `rule_nominal_thd_acceptable` as a substitute for the paired growth rule.
- Runtime must not insert claim references. Combined outcomes still require an
  independently complete clipping claim and an independently complete paired
  harmonic claim.
- v9.8 prompt bytes, finish behavior, and recorded runs remain immutable.

### Authorization / conclusion gates (v9.9)

- `v9_9_harness_complete` is the strongest offline conclusion for this
  remediation; it does not mean `development_confirmed`, validation passed, or
  performance improved.
- A new real-model development confirmation requires separate written
  authorization and a new append-only run directory.

## 11. Evaluation

Separate contextual evaluation package under `evaluation/contextual/` with
manifests, runner, scorer, calibration, sealing, and CLI. Historical V0.2 /
v9.4 scoring identities and EV-C036 single-WAV draft are not rewritten.
Use `single_reviewer_provenance_audit`; agreement/kappa reported `not_evaluated`.

### 11.1 Truth-free fixed pipeline

The validation `fixed_pipeline` arm accepts only an immutable
`ContextualBaselineRequest` containing `case_id`, `signal_id`, and
`StimulusContext`. It must not receive or inspect role, expected outcome,
expected causes, confidence tier, transform provenance, or source labels.

It executes deterministic clipping analysis plus the mode-appropriate absolute
or contextual harmonic analysis, evaluates the unchanged frozen profiles, and
maps only same-run Evidence and rule evaluations to a grounded diagnosis. A
manifest `ContextualCase` passed at the execution boundary is rejected. Offline
test oracles are explicit injected test doubles and are not validation arms.

### 11.2 Contextual validation campaign runner

The validation runner consumes sealed, truth-free `execution_inputs.json` and
non-secret `runtime_identity.json`
containing only case ID, diagnostic mode, local test/reference WAV paths, and
the declared nominal stimulus fields required by that mode. It rejects any
historical seal, non-zero execution ledger, identity/checksum mismatch, missing
credential, unsafe path, duplicate slot, or existing output directory before
constructing the real executor. Preflight pins the canonical active-seal path,
the append-only supersession status and seal-index SHA, recomputes the live
prompt/profile/scoring/product-tree/harness identities, and rejects any
provider/model/base-URL/planner/prompt/policy mismatch before execution.

Execution order is frozen and arm-major: all 20 `contextual_agent` slots, then
all 20 truth-free `fixed_pipeline` slots, then all 20
`no_context_ablation` slots. Each slot has one attempt. Behavioral failure
occupies its frozen denominator and execution continues; infrastructure failure
stops the campaign immediately. The two Agent arms use `RealLLMPlanner`; no
ScriptedPlanner fallback is legal. WAV bytes remain local to the application
and deterministic baseline boundaries and are never serialized into campaign
artifacts or provider context.

The evaluation layer owns truth-free plans, fixed execution, persistence, and
scoring. The product-backed RealLLMPlanner adapter and guarded live-run CLI live
under `app/`, preserving the frozen dependency direction; evaluation never
imports application composition.

Campaign startup copies the non-secret seal identity into the new output.
Truth-bearing manifest fields are loaded for scoring only after all 60 slots
are terminal. The runner preserves attempts, trace, result, case summary,
execution ledger, run summary, metrics, audit, and status as append-only artifacts. Only the
`contextual_agent` arm determines target status; fixed pipeline and no-context
ablation remain required comparisons. Final-test access, validation-driven
tuning, and rewriting historical seals/runs are forbidden.

## 12. Authorization gates (product ops)

Separate explicit authorizations required for: public audio acquisition,
contextual development materialization, real-model confirmation, validation
construction/seal, validation model campaign, push/PR.
