# V0.3 Contextual Reference Diagnosis Design

**Status:** user-approved design

**Date:** 2026-09-04

**Scope:** additive Scenario S1 product capability and its validation

**Branch:** `codex/v0.2-real-world-validation`

## 1. Decision summary

V0.3 will add explicit, product-observable stimulus context so the system can
distinguish newly introduced harmonic distortion from harmonic content that was
already present in the source. The product will support three modes:

1. `single_signal`: the existing one-WAV workflow, retained as a conservative
   compatibility path;
2. `nominal_single_tone`: one WAV plus a user declaration that the intended
   stimulus is a single tone with a supplied nominal fundamental frequency;
3. `paired_reference`: a test WAV plus a clean/reference WAV, the primary new
   capability.

The change addresses an identifiability limitation rather than attempting to
hide it with prompt wording. In a single unknown WAV, `THD FAIL` and
`series_kind=even_order_present` can be produced by either causal distortion or
natural source harmonics. A matched reference or explicit stimulus contract
adds information that is not present in the waveform alone.

This is a V0.3 behavior and interface addition. It does not amend the accepted
V0.2 result, rewrite V0.2 evidence, or turn the V0.2 external study into a new
official benchmark.

## 2. Context and motivation

The accepted V0.2 external WAV campaign completed honestly as `below_target`.
Its strongest weakness was harmonic attribution, not basic WAV ingestion or
clipping detection. Subsequent V0.3 remediation produced a preserved v9.4
development confirmation with 14/14 correct cases, but the current operational
harmonic gate still has a real-world ambiguity:

- `even_order_present` is spectral structure, not injection provenance;
- a natural voice, instrument, square-like signal, or other harmonic-rich
  source can satisfy an absolute THD rule without a new distortion mechanism;
- a model cannot reliably infer the missing source history from one unknown WAV.

The design therefore changes what the product can observe. It does not lower
the evaluation target, relabel failures merely to increase accuracy, or give
the LLM access to hidden dataset provenance.

## 3. Goals

The implementation must:

- improve causal harmonic diagnosis when a reference or declared single-tone
  stimulus is available;
- reduce natural-harmonic false positives on unknown single-WAV inputs;
- preserve independent clipping diagnosis;
- make the selected mode and the available/missing context explicit in every
  run and report;
- keep all numerical analysis and causal gates deterministic and versioned;
- keep raw waveforms and full FFT arrays out of planner context;
- preserve same-run Evidence and rule-reference integrity;
- support an auditable comparison against the same test WAV without reference
  context;
- retain all unsuccessful or below-target evidence.

## 4. Non-goals

This increment will not:

- alter Scenario S1 or add frequency drift, jumps, or modulation diagnosis;
- identify which physical device in a playback/recording chain caused a
  distortion;
- infer a clean source from a third-party fault label;
- introduce automatic resampling in the first contextual release;
- perform sample-level waveform subtraction as a causal test;
- modify the V0.2 1% clipping or 5% THD demonstration thresholds;
- rewrite v8.1, v9.4, historical scoring identities, accepted Demo assets,
  official bundles, or the `v0.2.0` tag;
- silently fall back to `ScriptedPlanner`;
- claim industrial validation, production readiness, or an industry-standard
  threshold;
- guarantee that a future validation run meets its target.

## 5. Considered approaches

### 5.1 Prompt-only semantic tightening

A prompt could be instructed to call all harmonic-rich unknown inputs
`inconclusive`. This would reduce some false positives, but it would not add
information and would reduce recall on genuine harmonic distortion. It also
would not solve the paired-source use case. This approach is rejected as the
primary solution.

### 5.2 Nominal stimulus metadata only

A declared single-tone frequency is inexpensive and useful for controlled
tests, but it depends on the user's declaration and cannot show whether the
actual source or playback path was already harmonic-rich. This approach is
retained as a weaker mode, not the main evidence path.

### 5.3 Additive paired-reference analysis with conservative fallbacks

A reference allows deterministic comparison of normalized harmonic profiles
and clipping indicators. It directly addresses the missing-observation problem
and can distinguish stable natural harmonics from newly introduced components.
This is the selected primary approach. The existing single-WAV entry remains
available and becomes conservative where causal identifiability is absent.

## 6. Architectural boundaries

The existing dependency direction remains:

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

The change is additive inside those boundaries:

- `signal` continues to own WAV decoding, immutable records, repositories, and
  bounded channel selection;
- `dsp` gains deterministic reference qualification and comparison algorithms;
- `tools` adapts comparison results into compact Evidence;
- `rules` owns versioned contextual sufficiency thresholds and judgments;
- `agent` receives context summaries, Evidence, and rule evaluations only;
- `evaluation` gains contextual manifests, paired execution, ablation, scoring,
  and append-only bundles;
- `app` exposes an additive contextual submission flow through the same shared
  application service used by CLI, API, and Web UI.

Lower layers remain independent of Agent and LLM frameworks. No UI, CLI, or API
adapter may reimplement comparison or diagnosis logic.

## 7. Application interface strategy

The frozen V0.2 `DiagnosisApplicationService.submit_wav(...)` signature and the
existing `/api/v1/runs/wav` endpoint remain unchanged.

V0.3 adds a separate service operation named
`submit_contextual_wav(...)`. Its request contains:

- test WAV bytes and filename;
- `mode`;
- optional reference WAV bytes and filename;
- optional `nominal_fundamental_hz`;
- optional `stimulus_kind`, restricted initially to `single_tone`;
- the existing user request and channel selection.

Mode validation is strict:

- `single_signal` rejects a reference WAV and nominal stimulus fields;
- `nominal_single_tone` requires `stimulus_kind=single_tone` and a finite,
  positive nominal frequency, and rejects a reference WAV;
- `paired_reference` requires a reference WAV and may also carry a nominal
  single-tone frequency when known.

The API receives `POST /api/v1/contextual-runs/wav`, with matching contextual
snapshot and report routes under `/api/v1/contextual-runs/{run_id}`. The CLI receives
`signal-diag diagnose contextual TEST_PATH` with mode-specific `--reference`,
`--nominal-fundamental-hz`, and `--stimulus-kind` options rather than changing
the meaning of `diagnose wav`. The Web UI adds an optional mode selector and
reference/stimulus fields while retaining the original one-file flow as the
default. Existing `submit_wav(...)` creates an internal `single_signal` context;
the new public operation accepts `nominal_single_tone` and `paired_reference`.

V0.3 uses distinct contextual submission, snapshot, and report models that
compose existing result structures and add the context/comparison sections. It
does not mutate frozen V0.2 DTO meanings. Every stored contextual run records
both `requested_mode` and `effective_capabilities`. Each uploaded WAV remains
subject to the existing per-file limit, and the contextual multipart parser
also applies a bounded aggregate request limit derived from the two file limits
and fixed form overhead.

## 8. Context and Evidence contracts

### 8.1 `StimulusContext`

`StimulusContext` records provenance, not a measured signal fact. It contains:

- mode;
- test signal ID;
- optional reference signal ID;
- optional nominal fundamental frequency;
- optional stimulus kind;
- source of each contextual assertion (`user_supplied` or
  `evaluation_manifest` for harness runs).

The planner may use this object to understand the task, but it cannot cite the
object as numerical Evidence.

### 8.2 `ReferenceQualificationEvidence`

The qualification tool produces one same-run Evidence set containing at least:

- test and reference signal IDs;
- selected channel mode;
- sample-rate compatibility;
- usable-duration compatibility;
- periodicity/voicing validity for each signal;
- detected fundamental and reliability for each signal;
- fundamental compatibility;
- reference clipping indicators;
- comparison validity and machine-readable invalid reasons.

A harmonic-rich reference is not invalid merely because its absolute THD is
high. Qualification determines whether it is stable and comparable, not whether
it resembles a pure sinusoid. A reference with substantial clipping is invalid
for paired harmonic comparison because it cannot serve as the clean comparison
state; that invalidity does not suppress independent clipping analysis on the
test WAV.

### 8.3 `HarmonicComparisonEvidence`

For a valid pair, deterministic DSP produces:

- normalized harmonic amplitudes for supported orders in both signals;
- per-order harmonic growth;
- reference THD, test THD, and THD change;
- the fundamental-frequency difference;
- alignment quality and gain-normalization diagnostics;
- a validity value and limitations.

Each harmonic magnitude is normalized to that signal's supported fundamental.
The causal decision uses normalized spectral changes, not raw amplitude changes
or sample subtraction. Bounded time and gain alignment are qualification and
audit diagnostics; they are not allowed to manufacture a harmonic delta.

### 8.4 `ClippingComparisonEvidence`

The comparison exposes reference and test clipping ratios, full-scale runs, and
flat-top indicators. Existing single-signal clipping Evidence remains the
authoritative positive mechanism path. Comparison information explains whether
clipping is new relative to the reference but cannot erase independently valid
test clipping Evidence.

All Evidence IDs, observation IDs, signal IDs, rule IDs, and claim references
must resolve within the same run.

## 9. DSP behavior

The first contextual implementation follows this deterministic sequence:

1. decode test and reference independently with existing WAV limits;
2. apply the same requested channel policy to both inputs;
3. reject comparison when sample rates differ; do not resample;
4. choose bounded, deterministic analysis windows using the existing signal
   segmentation conventions;
5. estimate and validate a supported fundamental independently for each input;
6. require compatible fundamentals for paired harmonic comparison;
7. perform bounded time alignment and robust gain alignment for diagnostics,
   excluding samples already identified as near-clipped from gain estimation;
8. compute each signal's normalized harmonic profile and compare like orders;
9. compute clipping metrics independently on each signal;
10. emit typed results without modifying either immutable waveform.

All tolerances, supported harmonic orders, alignment bounds, and comparison
thresholds live in versioned deterministic configuration. They may be calibrated
only on development data and must be frozen before validation construction.

## 10. Causal rule semantics

The existing `profile_s1_distortion` `1.0.0-demo` rules retain their current 1%
clipping and 5% THD demonstration thresholds. Contextual comparison rules live
under the additive `profile_s1_contextual_comparison` `1.0.0` identity. Its
exact numerical parameters are development-calibrated and byte-frozen before
validation construction; they do not replace the existing profile.

### 10.1 Clipping

An affirmative `clipping` claim still requires both:

- same-run `clipping_mechanism=true`; and
- a same-run substantial clipping rule failure: clipping-ratio failure or
  reliable flat-top failure.

Invalid harmonic analysis or invalid reference comparison does not negate this
independent path. Sparse full-scale samples without a substantial rule failure
remain insufficient.

### 10.2 Harmonic distortion in `paired_reference`

An affirmative `harmonic_distortion` claim requires all of:

- valid reference qualification;
- compatible supported fundamentals;
- valid HarmonicComparisonEvidence;
- a versioned harmonic-growth rule failure;
- same-run Evidence and rule references.

Absolute `THD FAIL` or `even_order_present` alone is insufficient. The supported
statement is limited to additional harmonic distortion relative to the supplied
reference. It does not localize a faulty device.

### 10.3 Harmonic distortion in `nominal_single_tone`

An affirmative claim requires:

- a valid declared single-tone context;
- a measured fundamental compatible with the declared frequency;
- valid harmonic Evidence with a versioned absolute harmonic/THD failure;
- same-run Evidence and rule references.

The mandatory limitation states that the conclusion is conditional on the
declared stimulus. The system may say that unexpected harmonic content is
present in the captured chain; it may not identify which device caused it.

### 10.4 Harmonic distortion in `single_signal`

For an unknown one-WAV input, absolute `THD FAIL` and
`even_order_present` may be reported descriptively but cannot, by themselves,
support causal `harmonic_distortion`. If clipping has its independent sufficient
path, clipping may still be claimed. Otherwise unresolved high harmonic content
produces `inconclusive` with a request for a clean reference or declared
single-tone stimulus.

### 10.5 Combined diagnosis

`combined` is not a separate shortcut. It requires independently sufficient
clipping and harmonic-distortion paths under the active mode.

## 11. Outcome behavior

The runtime applies these outcome rules:

- `supported_fault` only when at least one positive cause satisfies its complete
  mode-specific deterministic gate;
- `no_supported_fault` when the relevant analyses are valid and sufficiently
  complete and no supported contextual or clipping rule fails;
- `inconclusive` when the input, declaration, reference, fundamental, or
  comparison is invalid or when observed harmonic content lacks causal
  identifiability;
- runtime/infrastructure failure remains an error and is never converted to a
  diagnostic outcome.

A qualified harmonic-rich reference with no material harmonic growth can
support `no_supported_fault` relative to that reference, while the report still
describes the existing harmonic structure. The same test WAV without reference
context may correctly be `inconclusive`.

No result may combine a positive fault claim with a sibling
`no_supported_fault` claim.

## 12. Error handling and degraded capability

Malformed, oversized, or unsupported WAV data fails through the existing
sanitized application-error boundary.

If the test WAV is valid but the reference or nominal context is unusable:

- the requested mode remains recorded;
- comparison Evidence is emitted as invalid with explicit reasons;
- the run is not silently relabeled as `single_signal`;
- independent test-only clipping analysis may continue;
- harmonic causality remains unavailable;
- the final report states the missing capability and corrective action.

If the provider is unavailable or credentials are absent, the run records the
infrastructure/configuration failure. It never invokes `ScriptedPlanner` as a
fallback.

## 13. Planner and runtime changes

The contextual product path receives the new
`v0.3-s1-planner-9.5` identity after code and semantics are implemented and its
exact bytes are frozen. v9.4 and all earlier prompt bytes and recorded runs
remain immutable.

The prompt explains the three modes and the available tools, but deterministic
runtime validation enforces the causal gates. A planner cannot turn user
metadata into numerical Evidence, cite invalid comparison Evidence as positive,
or use an absolute THD failure to bypass the paired harmonic-growth rule.

The runtime includes contextual mode, comparison Evidence, and comparison rule
evaluations in the chronological trace and report. Tool calls that cannot
advance a viable hypothesis are scored as unnecessary under a new scoring
identity; historical scoring identities remain unchanged.

## 14. Product presentation

The Web UI defaults to the existing single-WAV experience. A user may select:

- unknown signal;
- declared single tone, which reveals the nominal-frequency input;
- compare with clean reference, which reveals a second WAV input and optional
  nominal frequency.

The report visibly distinguishes:

- measured facts;
- user-declared context;
- reference-comparison conclusions;
- causal limitations.

The CLI and API expose the same behavior through the shared application service.
No adapter performs DSP or rule evaluation.

## 15. Development and validation data

The preserved 14-case v9.4 development run remains historical regression
evidence. It is not overwritten or presented as proof of the new contextual
capability.

A separate contextual development set contains exactly 20 cases and at least
four independent public-source recording masters. It covers:

- paired clean/control;
- paired clipping;
- paired harmonic injection;
- paired combined distortion;
- paired natural-even/harmonic-rich negative controls;
- nominal single-tone clean, distorted, and declaration-mismatch cases;
- unknown single-WAV natural-rich, low-SNR, and invalid cases.

Positive cases primarily use licensed public real recordings as clean masters
with controlled, recorded transformations. Original public audio supplies
domain-out negative and conservative-behavior cases. Every case records source,
license, checksum, parent master, transform parameters, mode, and confidence
tier. No personal recording is required.

Development/validation separation is by parent master, source recording key,
recording session or environment family, and transform lineage. Different crops
or transformations from one master remain in the same split.

A new contextual validation contains exactly 20 cases from disjoint
masters/families:

- ten `paired_reference` cases: clean 1, clipping 2, harmonic 2, combined 2,
  natural-even/no-growth control 2, and invalid comparison 1;
- four `nominal_single_tone` cases: clean 1, clipping 1, harmonic 1, and declared
  frequency mismatch 1;
- six `single_signal` cases: clean 1, clipping 1, controlled inconclusive 1,
  and public domain-out inconclusive 3.

The resulting outcome roles are five no-supported-fault controls, four
clipping-only positives, three harmonic-only positives, two combined positives,
and six inconclusive cases. The nine positive cases are
`strong_ground_truth`; five controls and three controlled inconclusive cases are
`reference_supported`; the three domain-out inconclusive cases are unscored
`weak_observation` or `unknown`. Thus outcome, causal exact-set, and macro-F1
use a fixed scoreable denominator of 17. Inconclusive appropriateness is a
separate conservatism metric over all six frozen inconclusive roles. These
counts and their case identities are frozen before any validation model run.

The current single-WAV EV-C036 preregistration draft must not be executed as if
it validated the new contextual architecture. It remains historical design
evidence; a distinct contextual protocol identity supersedes it prospectively
without rewriting any completed run.

## 16. Comparative evaluation

The contextual validation preregisters three evaluations:

1. the contextual Agent arm, which determines target pass/fail;
2. a fixed deterministic contextual pipeline on the same cases;
3. a no-context ablation using the same v9.5 product identity in
   `single_signal` mode on the same test WAVs, executed once under the same seal
   and without tuning between arms.

The ablation demonstrates whether improvement comes from observable reference
information rather than changed labels. Its outputs do not replace the primary
arm and are retained even when unfavorable.

No validation output may be used to change prompt, thresholds, rules, labels,
or implementation. Any later remediation creates a new version and a new,
disjoint evaluation protocol.

## 17. Acceptance criteria

### 17.1 Harness and code acceptance

The implementation is code-complete only when:

- focused deterministic and integration tests pass;
- the full required pytest suite has zero required skips or xfails;
- Ruff and `mypy src` pass;
- architecture and preservation tests pass;
- `git diff --check` passes against the applicable baseline;
- V0.2 interfaces and protected asset checks show no drift;
- comparison outputs are deterministic for fixed inputs;
- CLI, API, and Web UI use the same service/runtime path.

### 17.2 Development confirmation

Before validation construction:

- every positive claim satisfies the new causal gates;
- evidence grounding is 100%;
- unsupported claim rate is zero;
- paired natural-even controls produce zero harmonic-distortion false positives;
- single-WAV ambiguity produces conservative outcomes without suppressing
  independently supported clipping;
- a separately authorized real-model development run meets the frozen
  development targets without rerunning failed slots.

### 17.3 Contextual validation target

The prospective one-shot validation target is:

- planner/infrastructure correctness at least 95%;
- scoreable outcome accuracy at least 80%;
- causal exact-set accuracy at least 75%;
- causal macro-F1 at least 75%;
- harmonic-distortion precision and recall each at least 80% on the frozen
  scoreable population, with paired and nominal modes also reported separately;
- evidence grounding exactly 100%;
- unsupported claim rate exactly zero;
- natural-even harmonic false positives exactly zero;
- appropriate inconclusive outcomes at least 5/6 on the preregistered
  inconclusive denominator;
- unnecessary tool rate at most 20%;
- clipping precision and recall each at least 80% on the frozen clipping-bearing
  label population;
- on the four paired harmonic-bearing slots, the contextual arm must produce at
  least three more correct causal sets than the no-context ablation.

The contextual protocol defines every numerator, denominator, infrastructure
failure treatment, and role hard gate before execution.

Passing static checks means the harness is complete, not that the experiment
has succeeded. A completed run that misses any required target is sealed and
reported as `below_target`.

## 18. Testing strategy

### 18.1 Deterministic unit tests

Required fixtures include:

- identical harmonic profiles under gain and bounded time shifts;
- known second- and third-harmonic growth;
- harmonic-rich reference with no new test harmonics;
- new test clipping with clean reference;
- clipping present in both inputs;
- incompatible sample rates;
- incompatible or unreliable fundamentals;
- clipped, unvoiced, low-SNR, and too-short references;
- invalid nominal frequencies and declaration mismatches.

### 18.2 Tool, rule, and runtime tests

Tests prove typed Evidence construction, same-run reference resolution, invalid
Evidence behavior, mode-specific causal gates, combined independence, and the
absence of positive-fault/`no_supported_fault` mixtures.

### 18.3 Product integration tests

Tests cover service submission, bounded dual upload, API multipart handling,
CLI argument validation, Web UI field visibility, report serialization, run
cleanup of both signal records, and complete compatibility with the existing
single-WAV flow.

### 18.4 Evaluation integrity tests

Tests cover split leakage, manifest/checksum integrity, fixed denominators,
single execution per slot and arm, frozen identities, append-only bundles,
failure retention, and Agent-versus-pipeline comparison.

## 19. Implementation phases and stop gates

### Phase 1: contract and test identity

Add the V0.3 contextual contracts, design-derived test IDs, and preservation
guards. Stop if the additive surface cannot coexist with frozen V0.2 contracts.

### Phase 2: deterministic DSP and Evidence

Implement reference qualification, normalized harmonic comparison, clipping
comparison, adapters, and focused tests. Stop if gain/time changes create false
harmonic growth or natural-even controls cannot be distinguished.

### Phase 3: rules and runtime gates

Add the contextual rule profile, mode-specific causal gates, trace support, and
fixed-pipeline behavior. Stop if the runtime depends on prompt compliance for
claim validity.

### Phase 4: application surfaces

Add the service, API, CLI, Web UI, and report flow while preserving existing
entry points. Stop if an adapter duplicates analysis logic or dual-input cleanup
is not reliable.

### Phase 5: contextual development

Build the licensed-source catalog and development cases, run deterministic
qualification, calibrate only on development, and freeze the profile and prompt
identities. Stop if source licensing, master isolation, or positive truth cannot
be established.

### Phase 6: real-model development confirmation

After separate authorization, run each frozen development slot once with
`RealLLMPlanner`. Preserve all outcomes and stop on the preregistered gate.

### Phase 7: contextual validation construction and seal

Create the distinct protocol, disjoint catalog, fixed denominators, arm plan,
and checksummed seal. No model runs occur in this phase.

### Phase 8: one-shot validation

After separate authorization, execute the contextual Agent, fixed pipeline, and
no-context ablation exactly as preregistered. Do not tune or rerun failed slots.

### Phase 9: reporting

Publish the verified bundle, case-study amendment, failure analysis, and
resume-safe wording. State `meets_target` or `below_target` from frozen metrics.

## 20. Preservation and authorization gates

Every implementation plan and review must explicitly protect:

- Phase 4.3.1 official development and official bundles;
- all V0.2 external study bundles, including below-target evidence;
- the V0.2 accepted Demo;
- v8.1, v9.4, and earlier prompt/scoring identities;
- `profile_s1_distortion` `1.0.0-demo` thresholds;
- the `v0.2.0` tag and Git history.

Writing this design authorizes no product modification, data download, dataset
construction, validation access, real-model run, push, or rewrite of historical
assets. Those actions require the implementation plan and the applicable
explicit execution checkpoint.
