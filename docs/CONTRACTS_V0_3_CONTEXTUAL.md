# CONTRACTS_V0_3_CONTEXTUAL.md

**Status:** additive V0.3 contracts  
**Extends:** `docs/CONTRACTS_V0_2.md` (does **not** edit or supersede frozen §§1–64)  
**Design:** `docs/superpowers/specs/2026-09-04-v0-3-contextual-reference-diagnosis-design.md`  
**Test IDs:** `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` (T-CX001–T-CX145)

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

Product contextual path uses frozen prompt identity `v0.3-s1-planner-9.5`
(bytes frozen in Task 7). v9.4 and earlier remain immutable historical identities.

## 11. Evaluation

Separate contextual evaluation package under `evaluation/contextual/` with
manifests, runner, scorer, calibration, sealing, and CLI. Historical V0.2 /
v9.4 scoring identities and EV-C036 single-WAV draft are not rewritten.
Use `single_reviewer_provenance_audit`; agreement/kappa reported `not_evaluated`.

## 12. Authorization gates (product ops)

Separate explicit authorizations required for: public audio acquisition,
contextual development materialization, real-model confirmation, validation
construction/seal, validation model campaign, push/PR.
