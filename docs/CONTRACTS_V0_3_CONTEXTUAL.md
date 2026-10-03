# CONTRACTS_V0_3_CONTEXTUAL.md

**Status:** additive V0.3 contracts

**Extends:** `docs/CONTRACTS_V0_2.md` (does **not** edit or supersede frozen §§1–64)

**Design:** `docs/superpowers/specs/2026-09-04-v0-3-contextual-reference-diagnosis-design.md`

**D037 product framing (shipped):** §17–§18;
`docs/superpowers/specs/2026-09-29-single-file-context-guidance-design.md`;
`docs/superpowers/specs/2026-09-30-d037-upgrade-loop-ui-design.md` (PR #10–#13).

**D038 planner-ablation study shape (definitions):** §19;
`docs/superpowers/specs/2026-09-30-s1-planner-ablation-utility-study-design.md`;
`docs/superpowers/plans/2026-09-30-s1-planner-ablation-utility-study.md`.
Harness, Scripted dry-run, protocol seal, and RealLLM remain separately gated.

**D038 protocol revision (dev_2 definitions):** §20;
`docs/superpowers/specs/2026-10-01-s1-planner-ablation-protocol-revision-design.md`;
`docs/superpowers/plans/2026-10-01-s1-planner-ablation-protocol-revision.md`.
Approved design values await a concrete seal; formal seal, RealLLM, and
product changes remain separately gated.

**D038 token/transport telemetry (definitions):** §21;
`docs/superpowers/specs/2026-10-01-s1-planner-ablation-token-transport-telemetry-design.md`;
`docs/superpowers/plans/2026-10-01-s1-planner-ablation-token-transport-telemetry.md`.
Observation defaults off; formal seal, RealLLM, concrete numeric budgets, and
provider-binding acceptance remain separately gated.

**Test IDs:** `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` (T-CX001–T-CX323)

**Live product identity (HEAD):** prompt `v0.3-s1-planner-9.11` with causal
policy `v9_11_mode_aware_no_fault_recovery` (§15). Historical identities
through v9.10 remain immutable. Default user path is single-file with optional
reference/nominal upgrades (D037).

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

Registered additive tool name (exact): `analyze_contextual_distortion`.

`get_tool_descriptors()` / planner context advertising always includes this
fifth tool alongside the four frozen V0.2 S1 tools (`detect_clipping`,
`analyze_harmonic_distortion`, `analyze_spectrum`, `estimate_fundamental`).
`CONTRACTS_V0_2.md` §§16/23 remain frozen historical inventory for the V0.2
slice. Mode-filtered descriptor lists (hide contextual tool on
`single_signal`) are **not** authorized here; that would be a separate B-class
design (see resolved OQ-016 hygiene disposition).

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

**Current HEAD / product contextual path** uses prompt identity
`v0.3-s1-planner-9.11` with causal policy `v9_11_mode_aware_no_fault_recovery`
(§15; T-CX250–T-CX255).

Earlier frozen product identity for the v9.9 slice was
`v0.3-s1-planner-9.9` / `v9_9_paired_reference_recovery`. Historical identities
remain immutable:

- `v0.3-s1-planner-9.11` / `v9_11_mode_aware_no_fault_recovery` (current)
- `v0.3-s1-planner-9.10` / `v9_10_contextual_clipping_recovery`
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
  | "v9_10_contextual_clipping_recovery"
  | "v9_11_mode_aware_no_fault_recovery"
```

| Policy | Finish gates | Mode-aware harmonic Tool routing | Rule evaluation |
|--------|--------------|----------------------------------|-----------------|
| `v9_4_legacy` | legacy | none | manual `evaluate_rules` |
| `v9_5_contextual` | frozen v9.5 contextual gates | none (historical) | manual `evaluate_rules` |
| `v9_6_contextual` | reuses v9.5 contextual finish gates | rejects `analyze_harmonic_distortion` in `paired_reference` / `nominal_single_tone` before execution | manual `evaluate_rules` |
| `v9_7_deterministic_rule_closure` | reuses v9.6 contextual finish gates | reuses v9.6 Tool-routing guard | automatic Tool-to-profile closure; planner `evaluate_rules` rejected |
| `v9_8_claim_reference_recovery` | inherits v9.7 requirements; accumulates ID-bearing nominal-harmonic recovery errors | inherits v9.7 | inherits v9.7 automatic closure + manual rejection |
| `v9_9_paired_reference_recovery` | inherits v9.8 requirements; also accumulates ID-bearing paired-harmonic recovery errors | inherits v9.8 | inherits v9.8 automatic closure + manual rejection |
| `v9_10_contextual_clipping_recovery` | inherits v9.9; contextual clipping recovery amendments | inherits v9.9 | inherits v9.9 |
| `v9_11_mode_aware_no_fault_recovery` | inherits v9.10 except mode-aware `no_supported_fault` validation (§15) | inherits v9.10 | inherits v9.10 |

Under `v9_6_contextual` only:

- rejected ordinary harmonic Tool calls consume one planner retry and zero Tool
  budget; no Tool Evidence is created;
- the recoverable error must name `analyze_contextual_distortion`;
- `single_signal` continues to allow `analyze_harmonic_distortion` (descriptive);
- clipping remains independently finishable in every mode.

v9.5 behavior is frozen and must not gain the new routing guard. Explicit tests
and dependency injection may still construct older policy identities.

## 10.2 `v9_7_deterministic_rule_closure`

For product policies `v9_7_deterministic_rule_closure` and later, automatic
Tool-to-profile rule closure **supersedes** planner-owned
`EvaluateRulesDecision` for the live HEAD path (D033). Frozen
`CONTRACTS_V0_2.md` §38.3 / D021 remain the V0.2 historical requirement.

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

## 10.5 `v9_10_contextual_clipping_recovery`

Under `v9_10_contextual_clipping_recovery` only:

### Contextual test-side clipping Evidence

- `ContextualDistortionAnalysis` and `ContextualDistortionResult` add the
  Boolean field `test_clipping_mechanism`.
- Its value comes only from the existing deterministic clipping analysis of
  the test waveform, including when the contextual comparison itself is
  invalid.
- `analyze_contextual_distortion` emits exactly one compact, valid
  `test_clipping_mechanism` Evidence item. No waveform, sample array, or full
  FFT payload crosses the Tool boundary.

### Additive contextual profile identity

- The existing `profile_s1_contextual_comparison` version `1.0.0` file and
  bytes remain unchanged.
- The additive profile `profile_s1_contextual_comparison_v9_10` version
  `1.0.0` inherits the original six rule semantics unchanged and adds exactly:
  1. `rule_test_clipping_ratio_acceptable`:
     `test_clipping_ratio <= 0.01`
  2. `rule_test_flat_top_absent`:
     `test_flat_top_detected == false`
- The 1% clipping-ratio and Boolean flat-top limits remain demonstration
  thresholds, not industry standards or SLAs.
- v9.7 through v9.9 continue to map contextual observations to the original
  profile. Only v9.10 maps paired or nominal contextual observations to the
  additive profile, in the existing single automatic rule batch and from the
  triggering Observation's exact complete Evidence suffix.

### Coherent clipping family semantics

A v9.10 clipping claim must satisfy one complete coherent clipping family:

- legacy family: valid `clipping_mechanism=true` Evidence plus FAIL of either
  `rule_clipping_ratio_acceptable` or `rule_flat_top_absent`;
- contextual test family: valid `test_clipping_mechanism=true` Evidence plus
  FAIL of either `rule_test_clipping_ratio_acceptable` or
  `rule_test_flat_top_absent`.

Evidence and rule evaluations from different families cannot be mixed to
satisfy the gate. Mechanism Evidence alone is insufficient. Older policies
retain their exact historical behavior.

For `no_supported_fault` in paired-reference or nominal-single-tone mode,
v9.10 may use a complete contextual test-side clean family: valid
`test_clipping_mechanism=false` Evidence plus PASS of both new test-side
clipping rules. Every existing mode-specific harmonic and contextual
requirement remains mandatory.

### Single-signal supported-subset recovery

Only when a v9.10 `supported_fault` finish in `single_signal` mode contains an
independently complete coherent clipping claim, an unsupported sibling
`harmonic_distortion` claim, and no other invalid positive claim, the
recoverable error states that the clipping claim is independently supported
and instructs the next finish to preserve that clipping claim and its same-run
references while removing the unsupported harmonic sibling.

This supported-subset recovery is validation guidance only. Runtime does not
accept, insert, delete, rewrite, or replace any claim or reference. Incomplete
clipping receives the ordinary clipping validation error. Paired-reference
and nominal-single-tone recovery retain their v9.9 and v9.8 behavior, and a
complete combined harmonic gate continues to require both claims.

### Authorization / conclusion gates (v9.10)

- Historical v9.9 prompt/profile identities, development and validation
  artifacts, both validation ledgers, the diagnostic reconstruction, and
  `validation_seal_v3` remain immutable.
- The original v9.9 validation campaign remains `infrastructure_stopped` at
  47/60. Its 13-slot continuation is diagnostic-only and cannot complete or
  replace it.
- `validation_seal_v3` cannot support v9.10 performance claims because the
  product/profile identity changes.
- `v9_10_harness_complete` is the strongest implementation conclusion. It
  does not mean `development_confirmed`, validation completion, performance
  improvement, or final-test access.
- Any v9.10 real-model development confirmation, later validation,
  preregistration/seal, push, or PR requires separate explicit authorization
  and append-only artifacts where applicable.

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

### Claim-population scoring correction

Evidence grounding uses every claim in every completed diagnosis as its
denominator. Unsupported-claim rate uses only predicted positive clipping or
harmonic-distortion claims as its denominator. Each claim is grounded only when
its required Evidence and rule references resolve within the same run. A slot
without a completed diagnosis contributes no claim to either population. A
zero positive-claim denominator is `not_evaluated` and blocks `meets_target`.

## 12. Authorization gates (product ops)

Separate explicit authorizations required for: public audio acquisition,
contextual development materialization, real-model confirmation, validation
construction/seal, validation model campaign, push/PR.

## 13. v9.10 freeze and seal lifecycle

The v9.10 implementation may bridge the frozen development dataset only with
an append-only, behavior-bearing identity amendment backed by unchanged
deterministic qualification and calibration results. Such a bridge does not
constitute development confirmation.

The v9.9 `validation_seal_v3` remains immutable historical evidence of an
infrastructure-stopped 47/60-slot campaign. Its separate 13-slot diagnostic
continuation cannot repair or complete the original one-shot campaign. No
v9.10 run may reuse or amend that seal; no validation seal is active until a
successful v9.10 development confirmation and separate construction approval.

## 14. Evaluation failure observability (T-CX245–T-CX249)

The contextual real-model adapter may retain one restricted failure fingerprint
when an application run fails before a diagnosis result is produced. The
fingerprint contains only a bounded exception type, a coarse category, and an
optional HTTP status code. It must not contain exception text, module names,
request or response bodies, raw WAV data, labels, expected outcomes, or
credentials. Provider transport failures are categorized separately from
ordinary evaluator/internal failures. This diagnostic field does not alter
application-facing error messages, retry behavior, scoring, or historical run
artifacts.

Later evaluation-harness fixes must preserve earlier identity amendments and
append a new bridge to the current implementation SHA. Compatibility support
for lightweight test services must not disable restricted failure capture on
the real product service.

## 15. v9.11 mode-aware no-fault recovery (T-CX250–T-CX255)

Policy `v9_11_mode_aware_no_fault_recovery` inherits v9.10 except for
`no_supported_fault` validation. Single-signal no-fault uses the legacy
clipping clean family; paired-reference and nominal-single-tone no-fault use
the contextual test clean family. Existing mode-specific harmonic/contextual
PASS requirements remain mandatory.

A rejected no-fault finish reports every missing requirement together and
includes each available matching same-run Evidence or rule-evaluation ID.
Runtime validates the planner decision without adding, removing, or rewriting
claims or references. v9.10 behavior and recorded runs remain immutable.

## 16. Single-signal flat-top clipping finish predicate (OQ-014 Option C)

DSP `clipping_mechanism` remains the strict causal label from
`detect_clipping` (unchanged). For `single_signal` `supported_fault` clipping
under v9.10/v9.11 coherent-family validation and under legacy
`_validate_clipping_supported`, a claim is valid when either:

- valid `clipping_mechanism=true` Evidence plus FAIL of
  `rule_clipping_ratio_acceptable` or `rule_flat_top_absent`; or
- valid `flat_top_detected=true` Evidence plus FAIL of the same substantial
  legacy clipping rules when `clipping_mechanism` is false.

`paired_reference` and `nominal_single_tone` clipping claims still require the
contextual test family (`test_clipping_mechanism=true` plus test-side rule
FAILs). Legacy and contextual families cannot be mixed.

## 17. Single-file context guidance (D037)

Additive report field on `ContextualAppRunSnapshot` /
`ContextualDiagnosisReport` only (frozen V0.2 `AppRunSnapshot` /
`DiagnosisReport` and `/api/v1/runs/*` remain unchanged):

```text
ContextGuidanceReasonCode =
  "harmonic_attribution_requires_context"
  | "insufficient_evidence_for_supported_fault"

context_guidance: ContextGuidance | None
  reason_codes: non-empty unique ordered tuple[ContextGuidanceReasonCode, ...]
  unlockable_modes: ("paired_reference", "nominal_single_tone")  # subset
  required_inputs:
    paired_reference: ("reference_wav",)
    nominal_single_tone: ("nominal_fundamental_hz", "stimulus_kind=single_tone")
  summary: str  # fixed templates; UTF-8; no LLM; no soft diagnosis
```

Emission (deterministic; no planner text):

1. `stimulus_context.mode == "single_signal"`;
2. terminal diagnosis outcome is `inconclusive`;
3. otherwise omit (`None`) for `supported_fault`, `no_supported_fault`,
   failed/infrastructure terminals, and non-`single_signal` modes.

Reason selection:

- If same-run valid Evidence includes a harmonic measurement metric in
  `{thd_percent, even_order_present, fundamental_relative_energy,
  even_harmonic_growth, odd_harmonic_growth, test_thd_percent}` →
  `harmonic_attribution_requires_context`;
- else → `insufficient_evidence_for_supported_fault`.

Observed facts (D039; additive on `ContextGuidance`; reason selection above
unchanged):

```text
ObservedFact =
  evidence_id, source_tool, call_id, metric, value, unit, validity,
  time_range, channel
  # validity must be "valid"; value/unit/metric/scope match same-run Evidence

ContextGuidance.observed_facts: tuple[ObservedFact, ...]  # may be ()

Display whitelist (first phase; independent of reason metric set):
  metric=thd_percent
  source_tool=analyze_harmonic_distortion
  type=strict finite float  # reject int/bool/str; no float() coercion
  unit=%

Selection: filter whitelist; dedupe by (metric, channel, time_range) keeping
lexicographically smallest evidence_id; order whitelist then evidence_id.
Empty tuple allowed. Reason selection unchanged when facts empty.

Compatibility:
  missing observed_facts on decode → ()
  extra="forbid" consumers must be updated in-repo; out-of-repo old binaries
  not guaranteed
```

`submit_contextual_wav` / `POST /api/v1/contextual-runs/wav` /
`signal-diag diagnose contextual --mode single_signal` accept
`mode=single_signal` with test WAV only (reject reference and nominal
stimulus fields). Queued capabilities for `single_signal` expose clipping and
absolute harmonic description only.

Web UI default “Unknown one-WAV signal” submits through the contextual
endpoint as `mode=single_signal`. Legacy `POST /api/v1/runs/wav` remains for
compatibility and does not gain `context_guidance`. Nominal Hz must never be
auto-filled from measured F0.

## 18. Demo preset WAV materialization and held-bytes upgrade (D037 UI)

Additive read-only route (no planner credentials):

```text
GET /api/v1/presets/{preset_id}/wav → 200 audio/wav
```

- Body is mono 48 kHz **32-bit integer PCM** WAV for a Demo catalog ID.
- Bytes are deterministic for a given ID.
- Unknown ID → `unknown_preset` (same code family as existing preset errors).
- Response must not place a Demo preset ID in `Content-Disposition` filename.
- Frozen `POST /api/v1/runs/synthetic` remains for V0.2 compatibility; the Web UI
  product path must not use it for diagnosis after this section.

Web UI held-bytes upgrade (client state; not a new server DTO):

1. After a contextual submit (upload or preset-materialized WAV), the UI retains
   the exact test WAV bytes used for that submit.
2. Preset-materialized submits use multipart filename `input.wav` so no Demo
   preset ID enters `PlannerContext.signal_meta.filename`.
3. When `context_guidance` is present, the UI may re-submit the held test bytes
   as `paired_reference` (user-supplied reference WAV) or `nominal_single_tone`
   (user-typed `nominal_fundamental_hz` + `stimulus_kind=single_tone`).
4. Measured F0 must never write into the nominal Hz control.
5. The UI must not auto-attach `clean_periodic` (or any other Demo preset) as a
   reference; only an explicit user file selection is allowed.

## 19. Planner-ablation utility study (D038)

Additive evaluation-study contract for development study
`study_s1_planner_ablation_dev_1`. This section freezes study identity and
acceptance obligations. It does **not** authorize harness code, Scripted
dry-run execution, protocol seal generation, RealLLM campaign execution, or
product planner replacement.

```text
study_id: study_s1_planner_ablation_dev_1
evidence_root: docs/evaluations/v0_3/planner_ablation/
scored_arms: product_agent | fixed_pipeline
harness_only_arm: scripted_agent   # optional; never scored vs product_agent
modes_first_freeze: single_signal | paired_reference
```

### 19.1 Product-slot entry (D037 path)

Study `product_agent` slots for `single_signal` and `paired_reference` must use:

1. `DiagnosisApplicationService.submit_contextual_wav` with the full keyword
   surface required by the live service (`test_filename`, `mode`,
   `reference_data`, `reference_filename`, `nominal_fundamental_hz`,
   `stimulus_kind`, `user_request`, and optional `channel`);
2. `DiagnosisApplicationService.wait_for_contextual_terminal` for the resulting
   run id.

Legacy `submit_wav` / `wait_for_terminal` are forbidden for study product slots.
`single_signal` must reject reference and nominal stimulus fields per §17.

### 19.2 Matching matrix

Before attributable planner conclusions, both scored arms must satisfy the same
mode-specific claim-gate matrix for the frozen modes:

| Mode | Clipping support | Harmonic support | `no_supported_fault` | Valid `inconclusive` |
|------|------------------|------------------|----------------------|----------------------|
| `single_signal` | §16 Option C: either (a) valid `clipping_mechanism=true` Evidence plus substantial legacy FAIL, or (b) valid `flat_top_detected=true` Evidence plus the same substantial legacy FAIL when `clipping_mechanism` is false. `clipping_mechanism=true` alone is not enough. | Absolute/harmonic description only; no unsupported harmonic `supported_fault` | Legacy clipping clean family plus single-signal no-fault rules as on the product path | Correct when evidence is insufficient; may carry deterministic `context_guidance` per §17 |
| `paired_reference` | Contextual test family only (`test_clipping_mechanism` plus test-side FAILs); no family mixing | Mode-specific contextual harmonic gate | Contextual test clean family | Correct when context is invalid or insufficient per the sealed oracle |

Positive and negative cases, valid Evidence, mode-specific rule families, and
same-run references are mandatory. Historical
`ContextualFixedPipelineBaseline` and the sealed v9.11 campaign path remain
immutable reuse candidates. The study fixed-pipeline arm must live in an
additive study module; copy-forward alone does not prove gate equivalence.

### 19.3 Deterministic report parity

Both scored arms must expose equivalent deterministic report fields for:

- `context_guidance` emission when §17 rules apply;
- omission when those rules do not apply;
- reason codes and required-input names.

`context_guidance` is never planner skill. Offline labels
`context_obtainable`, `context_valid`, and `context_sufficient` must not appear
in execution-arm inputs. A baseline run must not be relabeled `product_agent`
to reuse product report helpers.

### 19.4 Package boundary

`evaluation/planner_ablation` consumes an injected executor protocol and
study-owned result fields. It must not import app composition, service, or
report modules. Real application-service composition for product slots belongs
in an app-level study adapter.

### 19.5 Scoring identity and decision language

The study uses an independent seal and scorer identity and explicit denominator
derivation. Reject foreign study identities and wrong derivation. Do not reject
a result only because a rate numerically equals a historical 17/6-style figure.

Recorded conclusions after a sealed band are exactly one of:

```text
planner_advantage
fixed_pipeline_dominance
insufficient_evidence
```

Equal 100% completion does not block `fixed_pipeline_dominance` when quality,
safety, usefulness, and completion are non-inferior and a sealed
cost/experience metric improves materially, with no unacceptable regression on
other constrained metrics. Safety failure, missing evaluable population,
incomplete protocol, failed matching prerequisites, or an unmatched comparison
must not yield `planner_advantage` or `fixed_pipeline_dominance`. Failure to
demonstrate a difference is not evidence of equivalence.

Harness-only / Scripted dry-run artifacts carry a distinct execution identity
and must be rejected by the scored-input validator even if an arm label is
rewritten to `product_agent`.

### 19.6 Authorization remainder

Wave 1 definitions in this section do not authorize implementation. Later
grants are required for harness and Scripted dry-run tests (T-CX276–T-CX288
behavior), protocol seal (including N, uncertainty, mode-level non-inferiority,
resource bounds, and population identity), RealLLM campaign execution, and any
product behavior change.

## 20. Planner-ablation protocol revision (dev_2)

Additive study contract for follow-up development study
`study_s1_planner_ablation_dev_2`. This section registers observable protocol
behavior for identity, timing, populations, decision bands, provenance, failure
accounting, and staged authority. Numerical and schedule values below are
**approved design choices awaiting a concrete seal**, not already sealed
protocol values. This section does **not** authorize a formal protocol seal,
RealLLM campaign execution, product planner/gate changes, or rewriting of
§19 / `study_s1_planner_ablation_dev_1` evidence.

```text
study_id: study_s1_planner_ablation_dev_2
scorer: signal_diag.planner_ablation_scoring version 2.0.0-dev.1
evidence_root: docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/
scored_arms: product_agent | fixed_pipeline
modes: single_signal | paired_reference
timing_contract: encoded_bytes_to_terminal_v1
```

The old study `study_s1_planner_ablation_dev_1`, its identity validator, seal,
campaign artifacts, and machine enum remain immutable evidence. Formal
dominance was not accepted for that study. A later implementation must add
explicit version dispatch or a separate v2 model/scorer while preserving the
dev_1 reproducer and foreign-identity rejection. Proposed design values must
not be interpreted as already-sealed protocol bindings.

### 20.1 Request identity, aliases, and schedule

A request identity is derived from mode, test-byte hash, reference-byte hash
when present, nominal context when present, channel/segment representation
policy, and normalized user request. Scenario IDs, role names, filenames, and
hidden truth labels do not distinguish otherwise identical analysis requests.
Execution filenames are constant `input.wav` and `reference.wav`.

Equal request identities must carry equal oracle outcome and exact causal-fault
sets. Duplicate identical single-mode requests share one execution and one
scored unit via an explicit alias; the proposed schedule therefore has nine
unique single requests and ten paired requests (19 keys per arm per
repetition). Scenario-oriented tables may show aliases but must not double-count
the shared result in primary metrics.

Three repetitions of each unique request on each arm yield 114 scheduled
executions, including 57 product executions. Repetitions are fixed in advance
and include unsuccessful runs. Canonical request-key order is frozen; for key
index `i` and repetition `r`, execute product then fixed when `(i + r)` is
even, fixed then product otherwise, with repetition as the outer loop. Seal of
the complete expanded slot list is a later grant; dynamic reorder after error
is forbidden.

### 20.2 Mode-specific oracles and fixed populations

Oracles are mode-specific. A bad paired reference withheld in single mode must
not alter that single request's oracle. Labels require recorded rationales from
source transformations, stimulus context, deterministic measurement validity,
and versioned gates. Neither product output nor the study baseline diagnosis
may serve as oracle. Prior-output exposure motivating the redesign must stay
disclosed. Independent offline label review must check all rows before any
seal; disagreement revises the unsealed proposal and must not relax DSP
thresholds or finish gates. Demonstration thresholds (1% clipping, 5% THD)
remain demonstration values, not industry standards.

Upgrade population U, conditional population C, and guidance-eligible
population G are registered before execution from construction labels, not from
guidance emission, initial diagnosis, completion, or final success. Proposed
sizes subject to offline review are `|U|=7`, `|C|=6`, and `|G|=4`. No execution
arm receives these labels. Zero conditional population is not evaluable and
never 100% success. Missing guidance remains in the guidance denominator.

### 20.3 Common request timing

The primary timing endpoint is request latency from encoded WAV bytes in memory
to a terminal study result with deterministic guidance materialized. Named
events are `request_start` and `terminal_result_ready` under timing contract
`encoded_bytes_to_terminal_v1`.

Before either arm's timer: validate frozen manifest and input hashes, read
encoded WAV files into memory, and prepare a fresh empty execution container.
Imports and immutable profile/corpus loading may occur here. Container
preparation must not decode this slot's WAV, analyze its signal, call the
provider, construct a diagnosis, or populate a result cache.

Inside the timer both arms must perform WAV decoding and identical
channel/segment selection; analysis-record creation, repository insertion, and
context construction; diagnosis execution with pinned profiles and finish
gates; required deterministic postprocessing and context guidance; and
construction of the complete study terminal result. Stop only when that result
or a classified terminal failure exists. Serialize artifacts, calculate
metrics, and write checksums after stopping. Container teardown is outside
request latency and recorded separately. No overlapping requests or warm-up
provider calls are permitted.

The fixed adapter must receive encoded bytes, not pre-decoded signal IDs, and
must include both test/reference decoding in paired mode plus guidance
construction before its terminal marker. The product adapter keeps the complete
contextual submission and contextual waiter, including D037's single-file path.
Residual product application work (for example preview/event projection) must
be recorded explicitly; it must not be removed by post-hoc time subtraction or
by silently changing the product path. The outer common interval is
authoritative; partial phase timings are diagnostic only. Every report must
qualify that this is a request-level system comparison, not pure planner-only
attribution.

A proposed common outer slot deadline is 120 seconds. Offline tests must prove
injected decode/execution/guidance delays are included and serialization delays
after terminal readiness are excluded. Absent/out-of-order timing markers, wrong
timing-contract version, or pre-decoded fixed inputs must reject
`matched_comparison`; that flag is derived, never a constant true.

### 20.4 Matching, report parity, and provenance

Both scored arms remain subject to the §19.2 mode-specific claim-gate matrix
and §19.3 deterministic report-parity obligations, including D037 guidance
fields. Product slots continue to use complete `submit_contextual_wav` /
`wait_for_contextual_terminal` (§19.1). Matching proofs and gate identity
(including `v9_11_mode_aware_no_fault_recovery` and §16 Option C) remain
prerequisites for attributable comparison.

Execution provenance records the actual concrete planner/provider mode from
session construction and execution, never from an input arm label. Scripted,
fake-client `RealLLMPlanner`, synthetic fixtures, and any offline session carry
immutable `harness_only` provenance. Relabeled offline artifacts must be
rejected for scored product ingestion. Exact approved product type/prompt and
verified online execution context are required for future scored ingestion; a
class-name string alone is insufficient.

### 20.5 Metrics and decision bands

Per mode and repetition, report:

- primary quality as exact outcome-plus-causal-set accuracy over every unique
  scheduled request; missing diagnosis scores zero; outcome-only accuracy is
  secondary;
- useful-terminal rate: completed and oracle-compatible supported fault or
  justified `no_supported_fault`, with semantic claim/rule support; incorrect
  confident output is not useful;
- completion including a valid inconclusive diagnosis;
- unsupported positive claims and grounding with explicit counts and
  zero-denominator states;
- shared-boundary latency mean, median, nearest-rank p95, and maximum,
  including behavioral failure time;
- actual tool/rule/planner/repair/transport/token telemetry;
- upgrade and guidance metrics from the fixed U/C/G populations.

Per-arm denominators are 9 single and 10 paired per repetition, or 27 and 30
across repetitions. Total execution count 114 is never a per-arm denominator.
Related scenarios and repetitions do not create independent samples. No
p-values or generalization intervals are claimed for this known development
calibration set.

Claim safety requires valid same-run references and evidence/rule support for
the declared fault under that mode. Reference existence alone is not semantic
safety. Each arm/mode/round must have an evaluable positive-claim population;
zero claims or missing claim data block a positive study conclusion.

Proposed accepted decision conditions (engineering bands awaiting seal, not
statistical non-inferiority claims):

1. All identity, timing, oracle, report-parity, and matching prerequisites
   pass; the entire planned campaign completes; both arms pass safety.
   Otherwise the accepted conclusion is `insufficient_evidence` with explicit
   reason codes.
2. `fixed_pipeline_dominance` requires zero accepted quality, usefulness,
   completion, upgrade, or guidance regression in every mode/round (non-
   inferiority margin exactly zero — not a tiny epsilon). It also requires at
   least 20% mean latency reduction and 100 ms absolute mean saving in each
   mode/round, with no regression in fixed p95 or mean tool-action count.
3. `planner_advantage` uses quality as the sole primary superiority endpoint:
   at least one additional correctly diagnosed unique request in the same mode
   in each round, with no quality regression in the other mode and no
   usefulness/completion/upgrade/guidance regression. Utility-only improvement
   is secondary evidence.
4. Other complete comparisons yield `insufficient_evidence`. Equal performance
   alone does not establish equivalence outside the frozen development band.

The scorer must independently derive matched status and constrained regressions
from verified records; callers cannot assert them with default booleans.
Machine metrics, prerequisite results, and accepted review status remain
distinct fields. No enum authorizes product replacement.

### 20.6 Failure accounting and resource bounds

Each scheduled slot has one campaign attempt. Product-internal repair and
provider-transport retries retain their pinned product configuration; changing
those limits is not a campaign-level retry policy. Infrastructure failures —
including provider authentication/transport exhaustion, persistence failure, or
deadline expiry without a valid terminal result — stop the campaign. Preserve
started and unstarted schedule slots; no accepted conclusion is available from
a truncated campaign. Product behavioral failures already represented by the
runtime, including exhausted diagnosis/repair budgets, continue and remain
failures in their denominators. Classification must use typed causes.

Before seal, record exact product runtime limits, request timeout, provider
retry policy, model/prompt/settings, and token limits supported by that
provider path. Before a RealLLM grant, present a numerical worst-case
request/token budget derived from those limits and the 57 scheduled product
executions. Unknown limits, unavailable retry telemetry, or an unbounded
request configuration block execution.

### 20.7 Package boundary, sealing, and staged authority

Keep `evaluation` independent of `app`. App-owned study adapters map byte
requests through the product service or fixed pipeline to study-owned fields.
Evaluation owns schedules, oracle/eligibility labels, verified population
identities, pure metrics, and decision logic. Do not add a fixed product route,
change product composition, or change the historical contextual baseline.

A later sealed manifest must bind the unique-request schedule, aliases,
scenario/source/master relations, every mode oracle and offline label-review
record, U/C/G membership, timing/lifecycle/order/repetitions/limits/decision
bands, original WAV and canonical request hashes, immutable implementation
commit and product/prompt/profile/corpus/study-code hashes, dependency/runtime
versions, and operator authorization references. Preflight recomputes
file/input/code hashes. Generation refuses any existing destination, including
an empty directory. Verification is read-only. No tool may regenerate `dev_1`
as a migration step.

Staged authority remains:

1. definitions and study-only offline implementation under their grants;
2. separate seal grant on a concrete candidate manifest, label review,
   schedule, numeric bands, and budgets;
3. separate RealLLM grant with exact sealed identity and numerical
   request/token budget;
4. any product planner change requires a separate product design, contracts,
   tests, and operator implementation authorization.

Offline acceptance must neither score historical RealLLM outputs under the
revised oracle as new study evidence nor call a provider to test connectivity.

## 21. Planner-ablation token and transport telemetry

Additive study contract for `study_s1_planner_ablation_dev_2` resource
observation and source-aware bound admission. This section closes the §20.6 /
T-CX299 gap that conditional ceilings alone cannot prove actual calls, retries,
or tokens. It does **not** change product request semantics, §19 / §20 meanings,
frozen V0.2 §§1–64, DSP thresholds, or the product planner default. It does
**not** authorize a formal protocol seal, RealLLM campaign, provider
connectivity probe, explicit product request caps, concrete numeric budget
acceptance, provider-model mapping acceptance, commit, push, or merge.

```text
study_id: study_s1_planner_ablation_dev_2
resource_policy: planner_ablation_resource_v1
telemetry_schema: planner_ablation_telemetry_v1
timing_contract: encoded_bytes_to_terminal_v1
```

Numerical ceilings remain unaccepted until a later bound proof and operator
decision. Knowing a ceiling does not prove observation. Ceiling-only estimates
do not satisfy T-CX299's requirement for **actual** resource telemetry. A
successful mock run does not prove live model identity or authorize a campaign.

### 21.1 Event units

Observation counts these units separately and never equates them:

```text
study slot
  planner turn: one entry to RealLLMPlanner.decide
    logical completion call: one SDK chat.completions.create invocation
      SDK attempt: one iteration of the SDK request/retry loop
        HTTP send attempt: one underlying HTTP request dispatch
```

A turn may fail before a logical completion call. SDK retries do not create new
planner turns. Runtime repair consumes the runtime parse/reject budget and
creates a subsequent turn; it is counted separately from SDK retries. Redirects
and audited authentication/lower-transport resends may create extra HTTP send
attempts without another SDK attempt. Connection-establishment events that do
not replay an HTTP request must not be labeled as additional completions.
Factory construction probes and wrapper/factory bookkeeping are not planner
turns.

Two token quantities remain distinct:

1. `reported_usage` — sum of valid provider-reported usage on received
   completion responses, including responses whose content later fails planner
   parsing;
2. `potential_token_exposure` — conservative per-send ceiling reservation for
   attempts whose usage is unavailable; not an observed token count or invoice.

An HTTP send attempt proves local dispatch only, not provider receipt,
execution, or billing.

### 21.2 Unknown and partial usage

Missing usage is unknown, never fabricated zero. No response means usage is
unknown unless a validated trace proves the call was never dispatched. A
missing usage object on a completion is unknown. HTTP error responses without
usage do not automatically prove zero token use.

A complete usage object requires nonnegative integer prompt, completion, and
total tokens with total equal to prompt plus completion. Reject booleans,
malformed fields, and inconsistent totals. Cache-hit/cache-miss and reasoning
details are subdivisions; do not add them again to totals. When subdivisions
are present, validate their arithmetic; contradictory details invalidate the
observation instead of discarding them to preserve a passing total.

`input_tokens`, `output_tokens`, and `total_tokens` are exact campaign sums only
when every potentially token-consuming attempt has complete usage or a reviewed
zero-use proof. Otherwise keep the aggregate unknown and report the known
subtotal and unobserved exposure bound separately. Known usage must never be
reported as the entire campaign's actual usage while another attempt remains
unknown.

### 21.3 Source-aware default admission

Add resource policy `planner_ablation_resource_v1` to the unsealed dev_2
candidate. Bound facts carry an origin among `request_override`,
`sdk_default_audit`, `provider_spec`, `control_flow_proof`, and `unknown`. Each
accepted fact binds the code/path and environment that make it true. A number
without that proof is unknown for admission.

Audited SDK or provider defaults may supply effective bounds under this policy
after review. They must **never** set existing product flags
`max_tokens_explicit`, `request_timeout_explicit`, or
`transport_retry_override_explicit` to true, and must not auto-clear legacy
explicit-flag gates. Legacy configs that still require those explicit flags
retain their fail-closed semantics on the old `inspect_limits` path. Unknown,
unproved, unsupported-scope, or legacy facts remain blocked.

Independent factors may be multiplied into campaign ceilings only when nesting
and units are proved. Planner-turn, SDK-attempt, HTTP-send, and token ceilings
remain named units. An HTTP-send ceiling additionally requires an admitted
send/redirect/auth/lower-transport factor. Token ceilings require admitted
per-send input/output or all-outcome bounds. Unknown factors fail closed.
Finiteness alone is not operator acceptance of exposure.

### 21.4 Default-off agent and wrapper observation

Observation is private, opt-in, and disabled by default on the canonical
`RealLLMPlanner`. Public constructors, builders, decision types, run-result
fields, report JSON, prompt/settings, runtime budgets, fresh-client
construction, and native timeout/retry/redirect/authentication/proxy/TLS/
lifetime behavior remain unchanged when observation is off.

The agent owns stdlib-only observation protocols and immutable events. They
must not import the study, `evaluation`, or `app`. SDK-dependent observation
stays at the existing agent provider boundary. Evaluation consumes serialized
facts; it must not construct a service, import app composition, or call the
SDK for this feature. App owns per-slot collection and checked conversion to
study-owned ledgers.

Later implementation under a separate grant may add only these exact T285
additive paths for this feature:

```text
src/signal_diag/agent/telemetry.py
src/signal_diag/agent/provider_telemetry.py
src/signal_diag/evaluation/recording.py
```

Existing planner/runtime paths remain additive-authorized but still require
this feature's implementation grant. Whole `agent/` or `evaluation/` directory
authorization is forbidden. `RecordingPlanner` must forward the private
observer binding to the inner planner without importing evaluation into agent,
without counting wrapper or factory probes as planner turns, and without
runtime inspecting the wrapper by class name.

Callback errors and full buffers latch observation invalidity and must not
alter planner/runtime control flow, diagnosis results, guidance, or exception
behavior. No subclass, alternate planner, injected fake completion client,
global patch, new request header, retry wrapper, or prompt rewrite is admitted
as scored product observation. Construction probes produce no planner-turn or
provider-call events.

### 21.5 Resource failures versus behavioral and infrastructure failures

A typed resource failure — telemetry invalidity, usage absence without a
zero-use proof, undrained late callbacks, model metadata outside the accepted
policy, or a bound violation — preserves the product terminal outcome and stops
before starting another slot. It blocks an accepted positive study conclusion,
including when the failure is on the last slot. It is **not** automatically a
planner behavioral failure and must not remove a slot from the frozen
denominators.

Product behavioral failures already represented by the runtime, including
exhausted diagnosis/repair budgets, continue under §20.6 rules and remain in
their denominators. Infrastructure failures — including provider authentication/
transport exhaustion, persistence failure, or deadline expiry without a valid
terminal result — keep their existing stop classification.

Cancellation of the waiter alone is not worker completion. Record late events
until actual drain; if drain fails, retain pending/unknown exposure, stop, and
do not retry or overlap slots. Observation must not introduce new product
retries or alter diagnosis to repair study bookkeeping. Observation overhead on
the product arm remains inside `encoded_bytes_to_terminal_v1`; it is not
subtracted away. Terminal readiness remains the authoritative shared timer;
observation drain is accounted separately and must not fake a closed ledger.

### 21.6 Provider identity and model mapping

Record requested model name and provider-declared served route separately.
Returned model/fingerprint metadata, when available, is checked against the
accepted policy. Accepting that live identity, including stated fingerprint or
alias-echo limitations, is an explicit operator decision and a seal blocker
when unaccepted (`unaccepted_provider_model_mapping`). Detectable response
drift outside the accepted policy stops execution; it does not regenerate a
seal or change the product model string under this section.

Exact installed SDK and native transport dependency/source identity must bind
actual observation behavior. Lockfile-only labels, cross-environment
substitutions, and changed-dependency identities fail. Offline
`MockTransport`, injected `_client` fakes, Scripted planners, and synthetic
fixtures remain `harness_only` even when class-name strings look correct.
Caller booleans cannot elevate them.

### 21.7 Proof, capability, and candidate validation

Before seal, offline capability evidence must demonstrate that the selected
observation profile can capture turns, repairs, SDK attempts, HTTP sends, and
usage under controlled success/failure cases, bound to exact code/dependency
hashes. A caller cannot assert retry telemetry availability without that
binding. No live calibration request is authorized by this section.

Production candidate validation recomputes resource bindings from admitted
facts and rejects inconsistent values, missing proof, environment drift,
fixture-only complete-budget helpers, and label-review mismatch. The resource
extension binds resource-policy and telemetry-schema versions, observation
profile and capability evidence, exact implementation/dependency identities,
endpoint/authentication mode with credentials removed, requested and declared
model identities, finite named ceilings with units, timeout/drain policy, and
the accepted independent label-review record. Synthetic complete budget objects
remain fixture-only.

### 21.8 Evidence scope and staged authority

Within this definitions scope, the only new permitted unsealed evidence
document name under
`docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/` is
`RESOURCE_BOUNDS.md`. Existing permitted unsealed names remain. The
`protocol_seal/` prohibition for `study_s1_planner_ablation_dev_2` is retained.
Historical digests, `dev_1` seal/reproducer assets, and accepted evaluation
bundles remain immutable. Actual architecture allowlist edits occur only under
a later offline implementation grant.

Staged authority remains separate from these definitions:

1. definitions registration in this section and T-CX303–318;
2. offline observation and source-aware validation under an explicit
   implementation grant that names private agent observation and
   `RecordingPlanner` forwarding;
3. independent review of implementation evidence and remaining blockers;
4. separate grants for commit/push, concrete candidate acceptance, formal
   seal, and RealLLM.

Any product request-cap or planner change requires a separate product design,
contracts, tests, and operator authorization. Registering these definitions
does not clear `unaccepted_provider_model_mapping`,
`unbound_sdk_transport_identity`, `unproved_http_send_bound`, unknown token
bounds, `unavailable_retry_telemetry`, `unbound_label_review`, or
`unverified_resource_candidate`. If finite token/transport proof cannot
preserve approved product request semantics, execution stays blocked; do not
silently introduce product caps to make gates green. Offline acceptance must
neither fabricate bound closure nor call a provider to test connectivity.
