# Single-file inconclusive → context guidance

**Status:** implemented and merged (PR #10; RealLLM single_signal evidence PR
#11; operator `通过` 2026-09-29). Web UI held-bytes upgrade loop follows in
`2026-09-30-d037-upgrade-loop-ui-design.md` (PR #12).

**Date:** 2026-09-29

**Product decisions:** D037 (single-file default; presets option A; no HEAD
quality claims)

**Plan:** `docs/superpowers/plans/2026-09-29-single-file-context-guidance.md`

**Related:** D016 (long-term vision); D032–D036; CONTRACTS_V0_3_CONTEXTUAL.md
modes; `src/signal_diag/app/contextual_*`; `src/signal_diag/agent/diagnosis.py`
single_signal harmonic rejection

## 1. Decision summary

Accept D037 framing: **single-file is the default experience**; paired
reference and declared single-tone stimulus are optional upgrades.

When a completed single-file run ends `inconclusive` because harmonic (or
similar) attribution lacks context—not because measurements failed—emit a
**deterministic** `context_guidance` block that states what evidence is
missing and which upgrade unlocks which judgment. The UI may offer a one-click
path to re-run the **same test WAV** under `paired_reference` or
`nominal_single_tone` (user must supply reference bytes or declare frequency).

This does **not** change DSP, rule thresholds, planner prompts, or causal
finish gates. It does **not** invent a soft diagnosis (“probably harmonic”).
It does **not** authorize new RealLLM held-out runs (D037 §3).

## 2. Problem

Under HEAD `v9_11_mode_aware_no_fault_recovery` / single_signal:

- Clipping can finish via mechanism or OQ-014 Option C flat-top path (D036).
- Harmonic `supported_fault` is rejected without reference/nominal context.
- Valid analyses with no supported FAIL → `no_supported_fault`.
- Otherwise harmonic-rich one-file cases often → `inconclusive`.

Built-in preset `harmonic_distortion` is a concrete example: measurements show
elevated THD, but single-file gates correctly refuse harmonic attribution, so
the terminal outcome is `inconclusive` with no productized next step.

Users who only have one file are the default audience (D037). They need an
honest bridge to the optional context modes—not a Demo that pretends presets
carry known stimulus (rejected option B).

## 3. Goals and non-goals

### Goals

1. After eligible single-file `inconclusive`, surface deterministic guidance:
   reason code, unlockable modes, required user inputs.
2. Keep frozen V0.2 DTOs (`AppRunSnapshot`, `DiagnosisReport`, `/api/v1/runs/*`,
   `diagnose wav`) byte-stable.
3. Prefer converging the **Web UI default** onto the contextual run flow so
   `single_signal` / `paired_reference` / `nominal_single_tone` share one report
   shape (`ContextualAppRunSnapshot` + additive guidance).
4. Presets remain unknown-signal semantics; guidance explains inconclusive.

### Non-goals

- Softening single_signal harmonic finish gates.
- Injecting generator-known stimulus into presets.
- Citing HEAD quality numbers or re-running official held-out.
- Mode-filtered tool descriptors (former OQ-016 B-class).
- Second diagnosis domain (noise, sensors, …) — still D016 backlog.
- LangGraph, vector DB, auth, public deploy.

## 4. Approaches considered

| Option | Idea | Trade-off | Verdict |
|--------|------|-----------|---------|
| **A** | Deterministic `context_guidance` on contextual/`single_signal` reports; UI upgrade CTA | App/contract additive only; no new model runs for acceptance | **Recommended** |
| B | Presets carry known stimulus so harmonic Demo is positive | Makes Demo stronger than real one-file users; rejected by D037 §2 | Rejected |
| C | Only rewrite LLM prose / prompt to “suggest context” | Non-deterministic; pollutes planner identity; weaker tests | Rejected |

## 5. Design (Option A)

### 5.1 When guidance appears

Emit `context_guidance` only when **all** hold:

- `stimulus_context.mode == "single_signal"`;
- terminal diagnosis outcome is `inconclusive`;
- same-run analyses are complete enough that the block is about **missing
  attribution context**, not transport/planner failure;
- at least one deterministic reason code applies (see §5.2).

Do **not** emit guidance for `supported_fault`, `no_supported_fault`, or
infrastructure/`application_error` terminals.

### 5.2 Reason codes (normative names)

Exact enum to freeze in CONTRACTS_V0_3 (additive):

```text
ContextGuidanceReasonCode =
  "harmonic_attribution_requires_context"
  | "insufficient_evidence_for_supported_fault"
```

Mapping rules (deterministic; no LLM):

- If harmonic-oriented rule FAIL Evidence exists (or THD/even-order Evidence is
  valid and elevated under profile rules) **and** single_signal harmonic finish
  would reject attribution → include
  `harmonic_attribution_requires_context`.
- Else if outcome is `inconclusive` under the gates above →
  `insufficient_evidence_for_supported_fault`.

Wording constraint: user-visible text must say evidence is **insufficient to
attribute**, never “likely harmonic distortion.”

### 5.3 Guidance payload

Additive fields on contextual report / snapshot (names illustrative; freeze in
contract):

```text
context_guidance:
  reason_codes: list[ContextGuidanceReasonCode]  # non-empty, ordered, unique
  unlockable_modes: ("paired_reference", "nominal_single_tone")  # subset
  required_inputs:
    paired_reference: ("reference_wav",)
    nominal_single_tone: ("nominal_fundamental_hz", "stimulus_kind=single_tone")
  summary: str  # fixed templates keyed by reason_codes; UTF-8; no LLM
```

`unlockable_modes` lists only modes that would unlock a judgment class
implied by the reason codes (both modes for harmonic attribution).

### 5.4 Application / UI behavior

1. **Contextual submission** already rejects or omits `single_signal` in some
   multipart paths—extend additive contextual WAV submit to accept
   `mode=single_signal` with test WAV only (no reference).
2. **Web UI default** “Unknown one-WAV signal” submits through the contextual
   flow as `single_signal`, not only the legacy V0.2 run endpoint.
3. **Legacy V0.2 endpoints** remain for compatibility and frozen contracts; they
   do not gain `context_guidance`.
4. **Upgrade CTA:** from a completed guided run, UI offers:
   - attach reference → re-submit `paired_reference` with same test bytes;
   - declare `nominal_fundamental_hz` (user-typed; **must not** auto-fill from
     measured F0) → re-submit `nominal_single_tone`.
5. **Presets:** still generate unknown waveforms; after inconclusive, show
   guidance. One-click upgrade applies only when the UI still holds WAV bytes
   (uploads). Preset-only sessions show guidance text without claiming a stored
   reference.

### 5.5 Layers unchanged

`signal/`, `dsp/`, `tools/`, `rules/` thresholds, `agent/` planner prompts,
runtime causal gates, evaluation sealed bundles, and tag `v0.2.0` preservation
tests: **unchanged**.

### 5.6 Contracts and tests

- Amend `docs/CONTRACTS_V0_3_CONTEXTUAL.md` with a new section (e.g. §17)
  freezing reason codes, emission rules, and DTO fields.
- Add T-CX IDs in `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` for: emission on
  harmonic-rich inconclusive; absence on clipping `supported_fault`; absence
  on `no_supported_fault`; template wording constraints; multipart
  `single_signal` accept; UI/API upgrade payload shape (ScriptedPlanner).
- Record D037 in `docs/DECISIONS.md` (done with this design package).

### 5.7 Verification gates

- Deterministic pytest + architecture + ruff + mypy; no required RealLLM run.
- Optional Demo with RealLLM is a **separate** authorization after merge.

## 6. Risks

| Risk | Mitigation |
|------|------------|
| Guidance read as soft diagnosis | Fixed templates; tests forbid causal soft language |
| Nominal frequency prefilled from F0 | Forbidden; user must type declaration |
| Dual report shapes confuse API users | Document: guidance only on contextual shape; V0.2 shape frozen |
| Scope creep into new domains | Explicit non-goals; D016 backlog only |

## 7. Implementation authorization gate

Operator approved 2026-09-29 (`通过`). Implementation proceeds per
`docs/superpowers/plans/2026-09-29-single-file-context-guidance.md`.
