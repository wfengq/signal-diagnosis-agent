# V0.2 External WAV Validity Study Design

**Date:** 2026-09-01

**Status:** Written specification approved by the user in chat on 2026-09-01.
This document authorizes creation of a detailed implementation plan only; it
does not authorize data download, product-code changes, dependency installation,
real-model execution, commit, push, or merge.

**Implementation baseline:** `605c8a8` on the accepted V0.2 history. Release tag
`v0.2.0` remains on `ff16e2a` and must not move.

**Design branch:** `codex/v0.2-real-world-validation`

## 1. Objective

This study adds a small, credible, reproducible external-validity layer to the
accepted V0.2 Scenario S1 system. It asks:

> When V0.2 receives real capture-chain audio, controlled distortions applied to
> real-recording masters, and public out-of-domain audio, does it still diagnose
> clipping, harmonic distortion, no supported fault, or inconclusive outcomes
> reliably, conservatively, and with traceable same-run support?

The study is an additive V0.2 evaluation. It does not broaden the diagnosis
domain, redefine the product, or revise any historical acceptance fact.

The study must keep six concepts distinct:

1. a real LLM call;
2. the real WAV product entry point;
3. a project-generated WAV;
4. a WAV recorded through a real loudspeaker, room, and microphone chain;
5. controlled semi-real distortion applied to a real-recording master;
6. third-party public audio.

None of the first three alone is evidence of real-world audio validity.

## 2. Accepted baseline and preservation boundary

The study starts from a completed V0.2 with:

- deterministic T001-T285 acceptance and 1006 passing tests;
- public `RealLLMPlanner` using `v0.2-s1-planner-8.1`;
- DeepSeek `deepseek-v4-flash` as the accepted product-model identity;
- synthetic dataset `s1-distortion-synthetic` `1.2.0`;
- Phase 4.3.1 scoring identity `signal_diag.scoring` `2.0.0`;
- immutable development and official Phase 4.3.1 bundles;
- a bounded integer-PCM WAV loader and shared CLI/API/Web application service;
- two retained Phase 5 real-model Demo runs whose WAV content came from the
  project generator rather than an external recording device.

The following are immutable inputs, not study outputs:

- `docs/evaluations/phase4_3_1/development/`;
- `docs/evaluations/phase4_3_1/official/`;
- `docs/demo/phase5/v0_2_acceptance/`;
- every v4-v8.1 prompt byte and prompt hash;
- every historical scoring identity and bundle checksum;
- `profile_s1_distortion` `1.0.0-demo`, including its 1% clipping and 5% THD
  demonstration settings;
- tag `v0.2.0` and all Git history.

The study may refer to these assets but may not overwrite, rewrite, relabel,
rerun, or repackage them.

## 3. Selected study shape

The selected design uses three complementary data layers:

- **A — public real-capture group:** existing online recordings made through
  documented loudspeaker, room, and microphone chains;
- **B — controlled semi-real paired group:** clean real-capture masters from A's
  source domain with reproducible digital clipping, second-harmonic, and
  combined transforms;
- **C — public out-of-domain stress group:** licensed environmental, musical,
  speech, noise, or device audio used primarily to evaluate conservatism.

The quantitative positive-class evidence comes primarily from B. A tests real
input and capture-chain robustness without pretending that its recordings have
precise THD causality. C tests abstention, limitation disclosure, grounding, and
unnecessary actions without translating third-party semantic labels into S1
fault labels.

The study contains 52 unique analysis WAVs:

```text
                         development   validation   final_external_test   total
A public real capture          3            3                6              12
B paired semi-real             8            4               16              28
C public stress                3            3                6              12
Total                         14           10               28              52
```

The planned truth/outcome composition is explicit rather than inferred from
source names:

```text
planned class                         whole study   final_external_test
no_supported_fault                          11                6
clipping only                                7                4
harmonic_distortion only                     7                4
combined clipping + harmonic                 7                4
reference-supported inconclusive            12                6
weak/unknown, correctness-unscored            8                4
total                                        52               28
```

The three positive rows have expected outcome `supported_fault`; their causal
sets are respectively `{clipping}`, `{harmonic_distortion}`, and
`{clipping, harmonic_distortion}`. The table is a pre-seal target. A case that
cannot support its planned confidence is retained under the downgrade and
failure rules rather than relabeled to preserve the target count.

### 3.1 Considered alternatives

**Self-recorded phone or microphone data** would provide direct control over
distance, gain, and environment, but was rejected because the available setup
is one computer and the user prefers not to record audio.

**A public-dataset-only classification benchmark** was rejected because no
identified public dataset supplies causal S1 clipping and independent harmonic
ground truth. Machine `normal/abnormal`, environmental class, instrument
`distortion`, and perceived-quality labels are not interchangeable with S1
causes.

**A large multi-corpus benchmark** using full MUSAN, FSD50K, MIMII, or similar
corpora was rejected because it adds tens of gigabytes, complex per-asset
licensing, and labels unrelated to the narrow S1 question.

**SMARD-centered real capture plus small licensed stress sources** was selected.
SMARD supplies actual loudspeaker-room-microphone recordings and loopback
references, while smaller excerpts from ESC-10/ESC-50, NSynth, and Pyramic add
domain diversity.

Across the complete study, public source selection targets at least two
documented acoustic environments (for example, a listening room and an
anechoic capture), while preserving source/configuration isolation. This is
environment coverage, not a claim that the same signal was recorded under
controlled matched environments.

## 4. Scope

### 4.1 In scope

- online, documented real-capture WAV sources;
- source, license, citation, asset-ID, and checksum provenance;
- bounded selection and deterministic derivation of supported mono PCM WAVs;
- real-capture clean, harmonic-signal, stepped-sine, noise, speech, and musical
  material where the source permits it;
- controlled paired clipping, second-harmonic, and combined transforms;
- four-level label confidence;
- source/configuration/master-level development, validation, and final split;
- a single-reviewer delayed blinded re-review protocol;
- deterministic dataset, transformation, scoring, and report verification;
- one separately authorized real-model final campaign;
- the accepted fixed pipeline as a comparison path;
- honest preservation of completed/below-target results and unscored slots.

### 4.2 Non-goals

- new fault families, frequency drift, jumps, modulation, codec defects, or
  general audio-quality diagnosis;
- changing DSP algorithms, Tool contracts, Runtime behavior, prompt text,
  rule thresholds, or V0.2 public application interfaces merely to improve the
  study result;
- mapping machine, environmental, instrument, or subjective-quality labels to
  S1 causal truth;
- industrial validation, production readiness, hardware qualification,
  standards compliance, or an SLA;
- claiming that online recordings reproduce a user-controlled phone test;
- distinguishing playback-side overload from microphone/ADC overload when the
  public source does not provide that ground truth;
- redistributing third-party files without clear permission;
- tuning on `final_external_test`;
- falling back to `ScriptedPlanner` after a provider or behavior failure;
- replacing Phase 4.3.1 as the official V0.2 benchmark.

## 5. Public source policy

Every selected source must have an official project page, original paper,
institutional repository, or authoritative code/data repository. A convenience
mirror alone is insufficient.

### 5.1 SMARD — primary A/B source

Official source:
`https://www.es.aau.dk/research/audio-analysis-lab/smard`

SMARD contains approximately 18 GB of 48 kHz, 24-bit recordings made in a
documented 60 m2 listening room with multiple loudspeakers and microphone
arrays. It includes single stepped sinusoidal tones, harmonic signals, sweeps,
noise, speech, vocals, and music. For each configuration, microphone recordings
and a loudspeaker loopback were stored.

The official page permits downloading the whole database or a subset, describes
research use, and requests citation of the IWAENC 2014 paper. It does not present
an equally explicit standardized data license such as CC BY on the inspected
page. Therefore:

- SMARD may be used as an online research source after a terms snapshot is
  retained;
- original SMARD WAVs are not committed or redistributed by default;
- the repository stores source URL, citation, source asset/configuration IDs,
  download timestamp, original digest, selection rule, and derivation digest;
- if later license review does not permit the intended use, SMARD is excluded
  before final sealing and replaced under a new approved design revision, not
  silently swapped;
- a source becoming unavailable after sealing does not authorize result or
  checksum rewriting.

### 5.2 Pyramic — licensed real-recording stress source

Official source: `https://github.com/fakufaku/pyramic-dataset`

Pyramic supplies real loudspeaker recordings captured through a 48-channel MEMS
array in an anechoic chamber. The data license is CC BY 4.0 and the source
publishes checksums. Available material includes linear and exponential sweeps,
noise, silence, and speech. It is appropriate for real-capture stress and
inconclusive cases, not for stable-tone positive truth.

Because current V0.2 accepts at most stereo WAV, any Pyramic use must preserve
the original digest and apply a predeclared single-channel extraction. The
derived mono WAV is a study asset, not an unmodified source recording.

### 5.3 ESC-10/ESC-50 — environmental stress source

Official source: `https://github.com/karolpiczak/ESC-50`

ESC-50 contains 2,000 five-second, 44.1 kHz mono WAVs derived from Freesound
field recordings. Full ESC-50 uses CC BY-NC; the ESC-10 subset uses CC BY.
Fragments from one original `src_file` remain one split unit.

Environmental class labels describe sound events. They do not label clipping,
independent harmonic distortion, or no-supported-fault truth.

### 5.4 NSynth — sustained-note stress source

Official source: `https://magenta.withgoogle.com/datasets/nsynth`

NSynth contains four-second, 16 kHz, 16-bit PCM musical notes and uses CC BY
4.0. Its `distortion` quality means a crunchy waveshaped timbre with many
harmonics and sometimes noise. That quality is not an S1 causal label. An
instrument, rather than an individual note, is the minimum split unit.

### 5.5 Rejected primary sources

- MUSAN is clearly licensed CC BY 4.0 but its single official archive is about
  11 GB and its speech/music/noise labels add no S1 positive truth.
- FSD50K is about 24.7 GB, carries per-clip metadata and licensing obligations,
  and provides sound-event rather than S1-cause labels.
- MIMII is about 100 GB, uses eight-channel machine recordings, and its
  normal/abnormal causes do not map to S1.
- MIMII DUE is about 9.4 GB and focuses on anomalous machine sounds under domain
  shift, not clipping or harmonic causality.

## 6. Study asset and provenance model

Every study input requires a provenance record with at least:

- opaque `case_id` that reveals no source or truth to the Planner;
- `split`: `development`, `validation`, or `final_external_test`;
- `source_group`: A, B, or C;
- official source name, version/record ID, URL, citation, and access timestamp;
- source license or terms classification and redistribution decision;
- upstream asset ID and upstream source-recording/group ID;
- original filename stored evaluator-side only;
- original file SHA-256 and byte count;
- source sample rate, bit depth, channel count, frames, and duration;
- derivation tool identity, parameters, channel selection, crop interval, and
  derived SHA-256;
- capture configuration identifiers available from the source;
- `parent_master_id` for every B asset;
- transformation identity and parameters for B assets;
- label confidence, eligible metric families, evidence references, review
  rounds, and adjudication result;
- attribution and repository redistribution permission.

Public analysis filenames are truth-free:

```text
extwav_<split>_<opaque_case_id>.wav
```

No filename, Signal ID, default question, Planner context, or report-visible
source label may reveal group, transform, expected fault, or expected outcome
before the Agent finishes.

## 7. WAV derivation boundary

The analysis WAV must satisfy the frozen V0.2 loader:

- little-endian RIFF/WAVE;
- integer PCM or supported extensible PCM;
- mono preferred, stereo allowed only when the channel policy is frozen;
- 8/16/24/32 bit;
- 8 kHz-192 kHz;
- no more than 20 MiB, 2,000,000 frames, or 30 seconds.

The preferred study representation is mono, 48 kHz, 24-bit PCM for SMARD
derivatives and mono 16-bit or 24-bit PCM for other compatible sources. A
source-native supported file remains source-native where practical.

Permitted derivations are:

- deterministic selection of one documented source channel;
- deterministic crop to a predeclared stable interval;
- lossless integer-PCM recontainerization when needed;
- one documented sample-rate conversion only if the original is unsupported;
- B-group transforms described in Section 9.

Prohibited derivations are:

- per-signal peak normalization;
- loudness normalization;
- automatic denoising, declipping, EQ, compression, or enhancement;
- selecting a channel or interval after seeing Agent output;
- overwriting the upstream asset;
- describing a derived mono/cropped/converted file as the untouched original.

Both original and derived digests remain in provenance even when the original
audio cannot be redistributed.

`Independent reference analysis` in this study means a versioned,
evaluator-side deterministic measurement that cannot read Planner messages,
Agent traces, predictions, or final scores. It receives only the analysis WAV
and sealed provenance, and reports applicability, flat-top/clipped proportion,
F0 validity, order amplitudes, and THD needed to check the intended study
label. It is independent of Agent behavior; it is not a claim of independent
hardware calibration, a second DSP laboratory, or a second human reviewer.
Its implementation identity and test vectors must freeze before final sealing.

## 8. A — public real-capture group

A contains 12 actual capture-chain examples:

```text
development:       3
validation:        3
final_external_test: 6
```

The primary candidates are SMARD stepped single-tone, harmonic-signal, and
quiet/noise recordings selected across different loudspeaker, microphone,
position, and configuration groups. Pyramic may supply a bounded number of
licensed stress examples but does not replace SMARD's stable-tone role.

A is designed to test:

- WAV ingestion and bounded derivation;
- real device/room coloration;
- F0 and harmonic applicability;
- conservative handling of ambiguous real distortion;
- same-run grounding and limitation disclosure.

Planned confidence distribution:

```text
reference_supported: 8
weak_observation:     4
```

The final A split contains four reference-supported and two weak-observation
cases. A sample can be reference-supported only when source metadata, loopback
or input identity, and independent reference analysis agree on the eligible
outcome. A visible flat top without capture-side causality remains
weak-observation.

Across A, the planned reference-supported outcomes are four
`no_supported_fault` and four `inconclusive`; the other four cases are
weak-observation stress cases. The final A split contributes two of each.

Selection targets at least four mutually isolated capture-configuration
families overall and at least three in final. Where SMARD metadata permits,
the whole group also covers at least two loudspeakers, two microphone/position
settings, two documented distance settings, and two documented playback-level
settings. Stable periodic material spans at least three F0 bands:
100-300 Hz, 400-1,000 Hz, and 1.2-3 kHz; final spans at least two bands.
Unavailable distance, device, or level fields are recorded as unavailable and
are never inferred from filenames or waveform amplitude.

A does not provide `strong_ground_truth` and does not claim controlled playback
or recording gain. Consequently, public A data cannot fulfill the originally
considered clean/playback-overload/record-gain causal matrix; it replaces that
matrix with documented public capture-configuration coverage and records the
missing overload-mechanism truth as a study limitation.

## 9. B — controlled semi-real paired group

B uses seven real-capture masters chosen from mutually isolated source
configuration groups:

```text
development:       2 masters x 4 variants =  8 WAVs
validation:        1 master  x 4 variants =  4 WAVs
final_external_test: 4 masters x 4 variants = 16 WAVs
total:             7 masters x 4 variants = 28 WAVs
```

Each master produces exactly:

1. a canonical clean/base variant;
2. a controlled-clipping variant;
3. a controlled-second-harmonic variant;
4. a combined second-harmonic-then-clipping variant.

The original source asset remains unchanged. All four variants inherit one
`parent_master_id`, one split, and one source configuration group.

### 9.1 Master eligibility

A B master must:

- originate from a real microphone recording rather than a project generator;
- contain a stable periodic interval accepted by the independent reference
  analysis;
- have no detected flat top or full-scale pile-up in the selected interval;
- have a stable reference F0;
- have reportable harmonic bins;
- not already meet the independent positive clipping condition;
- not already meet the independent positive harmonic-distortion condition;
- not contain an order-2 component that makes the injected independent cause
  unidentifiable;
- pass the frozen WAV and provenance checks.

The seven masters span the same three F0 bands used by A where source material
permits, with all three represented overall and at least two represented in
final. No master or capture-configuration family crosses a split.

Failure before split sealing rejects the entire four-variant family. After
`final_external_test` sealing, a failed master remains a documented failed or
unscoreable family and is not replaced.

### 9.2 Common base

All variants are derived from the same canonical base samples. A globally fixed
attenuation may be selected on development/validation to guarantee headroom,
but it must be identical for every master and every variant. The source is not
normalized per file.

The original source samples, the fixed attenuation, and the canonical base
digest are recorded.

### 9.3 Controlled clipping

Clipping uses symmetric hard clipping:

```text
y[n] = min(max(x[n], -T), T)
```

Development evaluates predeclared clipping-severity candidates corresponding
to target absolute-sample tail proportions of 3%, 5%, and 10%. Validation
selects one global severity by a rule fixed before validation: choose the
lowest candidate that produces an independently verified flat top and exceeds
the demo profile's 1% clipping setting on every eligible validation master.

For a candidate proportion `q`, `T` is calculated deterministically from the
canonical base's `abs(x)` distribution using a frozen quantile method. That
per-master threshold is a consequence of the globally selected `q`, not an
outcome-tuned per-file severity. Quantile method, tie handling, and integer-PCM
rounding are part of the transformation identity.

The selected rule, not a per-final-file choice, is frozen for final. Threshold
`T`, achieved clipped-sample proportion, and output digest are recorded for
each file.

### 9.4 Controlled second harmonic

The second-harmonic transform is an even-order memoryless nonlinearity applied
to the canonical base:

```text
y_pre[n] = x[n] + alpha * (x[n]^2 - mean(x^2))
```

A globally fixed post-gain may be used solely to keep every candidate inside
integer-PCM full scale. It must be chosen on development/validation, applied to
all harmonic and combined assets, and recorded. It is not selected separately
for final files.

Development evaluates `alpha` in the fixed candidate set `{0.10, 0.15, 0.20}`.
Validation selects the smallest global candidate that, on every eligible
validation master:

- produces a reportable order-2 component;
- exceeds the demonstration 5% THD setting under the independent reference
  analysis;
- does not produce clipping;
- leaves F0 valid.

If no candidate satisfies the rule, the study stops at validation and the
transform design must be revised under a new written approval. It does not
inspect final masters to choose `alpha`.

### 9.5 Combined transform

Combined assets apply the frozen second-harmonic transform first and the frozen
clipping transform second. Both causal interventions and their achieved
reference measurements are retained. Reversing the order creates a different
study identity and is not an allowed rerun.

### 9.6 B label confidence

The 21 degraded assets are `strong_ground_truth` only when the frozen transform
log, input/output digests, and independent reference checks all validate. The
seven canonical clean assets are `reference_supported` when the master
eligibility checks pass.

If a degraded asset's achieved signature does not support its intended causal
label, it becomes unscoreable; its intended transform is still disclosed. It
is not relabeled based on the Agent response.

## 10. C — public out-of-domain stress group

C contains 12 public stress examples:

```text
development:       3
validation:        3
final_external_test: 6
```

The preferred total composition is:

- six ESC-10/ESC-50 environmental recordings;
- three NSynth acoustic sustained-note recordings;
- three Pyramic real-capture sweep, noise, or speech recordings.

The source-recording/instrument unit remains inside one split.

Planned confidence distribution:

```text
reference_supported inconclusive: 8
unknown:                          4
```

The final C split contains four reference-supported inconclusive cases and two
unknown cases. A C asset receives reference-supported inconclusive status only
when its source semantics and independent review establish that stable periodic
S1 measurement is not applicable. A naturally harmonic sustained instrument,
engine, bell, or other ambiguous source remains unknown.

C is used for:

- inconclusive appropriateness;
- positive causal-claim rate on unknown inputs;
- limitation presence;
- evidence grounding;
- unsupported same-run claim detection;
- unnecessary Tool actions;
- qualitative failure analysis.

Unknown cases never enter outcome accuracy, causal exact-set accuracy, or
macro-F1. Their positive-claim rate is not called a false-positive rate.

## 11. Label-confidence and metric-eligibility policy

Every case has exactly one confidence:

- `strong_ground_truth` — deterministic intervention, complete transform
  provenance, and independent reference confirmation;
- `reference_supported` — source/control metadata plus independent measurement
  or review support, without complete causal control;
- `weak_observation` — a plausible observation without enough causal support;
- `unknown` — no reliable S1 truth.

Only strong-ground-truth and reference-supported cases may enter:

- outcome accuracy;
- causal exact-set accuracy;
- causal macro-F1;
- positive-class recall or precision;
- an assertion that a final outcome is correct or incorrect.

All cases may enter structural measures that do not require causal truth,
including report creation, reference integrity, same-run evidence grounding,
Tool/action counts, termination, and provider/runtime completion.

The planned whole-study confidence distribution is:

```text
strong_ground_truth: 21
reference_supported: 23
weak_observation:     4
unknown:              4
```

The planned final distribution is:

```text
strong_ground_truth: 12
reference_supported: 12
weak_observation:      2
unknown:               2
```

Thus the final campaign has exactly 28 Agent slots and 24 outcome-scoreable
slots when sealing succeeds.

## 12. Single-reviewer delayed blinded re-review

The study has one human reviewer. It must not claim double annotation,
inter-rater reliability, or independent human adjudication.

The protocol is named `single-reviewer delayed blinded re-review`:

1. Round 1 records source/provenance review, independent measurements,
   confidence, eligible outcome, causal set, and reason codes before any Agent
   result is available.
2. A blind package is generated with new random review aliases. It excludes
   source names, original filenames, transform names/parameters, split, prior
   labels, and all Agent output.
3. The reviewer waits at least 14 complete days after Round 1.
4. Round 2 presents cases in a newly randomized order with only the analysis
   audio, allowed neutral metadata, frozen reference summaries, and the common
   labeling form.
5. Round 2 records outcome, causal set, confidence, applicability, and reason
   codes without displaying Round 1.
6. The review report calculates raw outcome agreement, confidence agreement,
   causal-set agreement on eligible cases, unweighted Cohen's kappa for outcome,
   and quadratic-weighted Cohen's kappa for the ordered confidence levels where
   each statistic is mathematically defined.
7. Disagreement never upgrades confidence. Transform-proven B labels may remain
   strong only when deterministic provenance and independent reference checks
   pass; all other unresolved disagreement is downgraded to weak or unknown.
8. Final review outputs and the scoreability mask are frozen before any final
   Agent call.

The annotation-stability target is:

- raw outcome agreement at least 85%;
- outcome Cohen's kappa at least 0.70 where defined;
- quadratic-weighted confidence kappa at least 0.70 where defined.

Failure does not erase the dataset. It blocks `meets_target`, is reported as an
annotation limitation, and removes unresolved cases from correctness metrics.

## 13. Split and leakage policy

Files are never randomly split in isolation. The grouping hierarchy is:

```text
official source
  -> upstream source recording or instrument
    -> capture configuration / device / position / environment
      -> clean master and all derivatives
        -> individual analysis WAV
```

Minimum split units are:

- SMARD: capture configuration including loudspeaker, microphone/array,
  position, and available session identity;
- Pyramic: upstream sample, speaker, and angle/configuration family;
- ESC-50: `src_file`;
- NSynth: `instrument`;
- B: `parent_master_id` and all four variants.

Development permits observation and correction of study tooling and protocol.
Validation selects the frozen transform configuration, reference parameters,
question, scoring identity, target bands, and report schema. Final contains only
unseen groups and is inaccessible to tuning.

Before final access, preflight must prove:

- no group key occurs in more than one split;
- no original digest or derived digest occurs in more than one split;
- no parent/child lineage crosses a split;
- no source truth appears in Planner-visible values;
- development and validation identities are complete;
- final destination is absent and write-once;
- the scoreability mask and labels are sealed;
- prompt, model, rule profile, scoring, and dataset identities match the frozen
  campaign.

## 14. Agent and fixed-pipeline execution

The Agent and fixed pipeline receive identical final WAV content and the same
versioned V0.2 DSP Tools and rule profile.

The product Agent identity remains:

```text
planner:       public RealLLMPlanner
provider:      deepseek
model:         deepseek-v4-flash
prompt:        v0.2-s1-planner-8.1
rule profile:  profile_s1_distortion 1.0.0-demo
```

The neutral default request is frozen before validation results are scored and
contains no source or label hint. The selected candidate is:

```text
Why does this signal sound distorted? Check only the supported S1 causes and
state clearly when the evidence is insufficient or the analysis is not
applicable.
```

Any wording change after validation requires a new campaign identity. Runtime
does not force a Tool order or action.

The fixed pipeline is the accepted non-Agent comparison using the same DSP
Tools and rule engine. It is not changed to target external cases.

Final execution schedules:

- one Agent slot for each of 28 final cases;
- one fixed-pipeline slot for each of the same 28 cases;
- no stochastic repetition in the first external study;
- max concurrency one for real-model calls;
- an attempted provider call is a consumed slot;
- no rerun after timeout, provider error, wrong outcome, or poor score;
- no ScriptedPlanner fallback.

If credentials are missing, final remains pending. If the configured provider
or frozen model is unavailable during an authorized campaign, affected attempts
remain failed/unscored and the campaign does not silently substitute a model.

## 15. New identities and historical isolation

The additive study identities are:

```text
dataset:              s1-distortion-external-wav 1.0.0
study:                v0.2-external-wav-validity-1
development bundle:   study_v0_2_external_wav_dev_1
validation bundle:    study_v0_2_external_wav_validation_1
final bundle:         study_v0_2_external_wav_final_1
external scoring:     signal_diag.external_scoring 1.0.0
```

The word `official` is deliberately absent. `signal_diag.external_scoring`
does not replace or modify Phase 4.3.1 `signal_diag.scoring` `2.0.0`.

External bundle paths must be additive and must not be nested inside a
historical Phase 4 or Phase 5 accepted bundle. All outputs are write-once.

Before and after any later implementation, a preservation audit compares the
tracked bytes or normalized checksum policy for every protected historical
asset. Drift is a hard failure, not an update opportunity.

## 16. Metrics

Every metric reports numerator, denominator, excluded cases, confidence layer,
source group, and execution path.

### 16.1 Correctness metrics

On the 24 planned scoreable final slots:

- outcome accuracy;
- causal exact-set accuracy;
- causal macro-F1 over `clipping` and `harmonic_distortion`;
- per-cause precision and recall;
- inconclusive appropriateness on the six planned reference-supported
  inconclusive cases;
- scoreable-slot coverage.

Empty causal sets for clean/inconclusive outcomes participate in exact-set
accuracy where their labels are reference-supported. Macro-F1 is calculated
only for the two positive S1 fault types.

### 16.2 Grounding and behavior metrics

Across every eligible run and, where defined, every final run:

- evidence-grounding rate;
- unsupported-claim rate;
- first-Tool selection rate where acceptable first Tools can be labeled without
  hidden evaluator assumptions;
- observation-driven replan rate;
- unnecessary Tool action rate;
- timely stopping rate;
- applicable-rule usage rate;
- required-knowledge usage rate;
- unnecessary-knowledge retrieval rate;
- limitation-presence rate;
- positive causal-claim rate on weak/unknown cases;
- Tool actions, planner calls, completion reason, latency, tokens, and observed
  cost when available.

An unknown case's positive causal-claim rate is a conservatism observation, not
a false-positive rate.

### 16.3 Stratification and clustering

Metrics are reported by:

- A/B/C source group;
- strong/reference/weak/unknown confidence;
- public source;
- capture configuration family;
- parent master;
- clean, clipping, harmonic, combined, and inconclusive target;
- Agent versus fixed pipeline.

The four B variants from one master are correlated. Reports show raw WAV-slot
metrics and master-cluster summaries. Confidence intervals or bootstrap
estimates, if included, resample parent masters rather than pretending that all
variants are independent captures.

No statistical-significance or population-generalization claim is made from
four final B masters.

## 17. Acceptance states and targets

Three states remain separate.

### 17.1 Harness completed

```text
external_validation_harness_completed
```

Requires:

- all 52 planned manifest entries or explicit pre-seal exclusions accounted
  for;
- source, license/terms, attribution, lineage, and checksum validation;
- deterministic derivation and transformation reproduction;
- split/group leakage checks;
- blind-review package and agreement calculation;
- deterministic scoring/report verification;
- protected V0.2 assets unchanged;
- no real-model dependency.

### 17.2 Experiment completed

```text
external_validation_completed
```

Requires:

- one sealed final manifest with 28 cases;
- 28 Agent-slot attempt records and 28 fixed-pipeline records;
- all successful, failed, and unscored cases retained;
- complete identities, reports, and checksums;
- no final tuning, replacement, selective rerun, or fallback.

Completion does not imply target achievement.

### 17.3 Meets target

```text
external_validation_meets_target
```

Requires all hard integrity gates plus:

- exactly 24 scoreable final outcome slots after the pre-run seal;
- outcome accuracy at least 0.80;
- causal exact-set accuracy at least 0.75;
- causal macro-F1 at least 0.75;
- evidence grounding exactly 1.0;
- unsupported claim rate exactly 0.0;
- unnecessary Tool action rate no greater than 0.20;
- at least five of six reference-supported inconclusive cases handled
  appropriately;
- raw delayed-review outcome agreement at least 85%;
- outcome Cohen's kappa at least 0.70 where defined;
- quadratic-weighted confidence kappa at least 0.70 where defined;
- every final slot represented by an immutable attempt record;
- no ScriptedPlanner fallback or historical drift.

These are study demonstration targets, not standards, SLAs, or product pass
criteria.

A completed campaign that misses any applicable target is retained as:

```text
external_validation_completed/below_target
```

It is not rewritten, relabeled, or rerun to cross the threshold.

## 18. Failure and correction policy

Before final sealing, development or validation may reveal:

- inaccessible or ambiguously licensed assets;
- unsupported containers or channel layouts;
- master ineligibility;
- transform signatures that do not meet the independent reference rule;
- leakage or duplicate source groups;
- unstable single-reviewer labels;
- scoring or report harness defects.

Corrections are allowed only on development/validation, must retain failed
evidence where material, and must produce a new configuration fingerprint.
They may not change V0.2 prompt, thresholds, rules, or historical assets.

After final sealing:

- input, labels, confidence, scoreability, transforms, and targets are immutable;
- a data or scoring defect invalidates the campaign identity;
- the invalid bundle is retained;
- a corrected campaign requires a new written design amendment, new identities,
  and explicit authorization;
- model behavior failure remains a result, not a reason to alter the data;
- provider failure never authorizes ScriptedPlanner or model substitution.

## 19. Security, privacy, and repository policy

- No user recording is required.
- Public source audio is screened for personal data and license restrictions.
- Human speech is used only from an authoritative dataset whose consent/use
  terms cover research redistribution or reference.
- Source filenames, uploader names, paths, and metadata are sanitized from
  Planner context and public reports unless attribution requires them.
- Credentials, authorization headers, provider bodies, and local user paths
  never enter manifests or bundles.
- SMARD original audio is not committed by default.
- Third-party audio is committed only when its license clearly permits the
  intended redistribution; otherwise the repository keeps provenance and
  deterministic reconstruction instructions.
- Download caches, raw archives, and temporary conversions stay outside tracked
  artifact paths.
- No downloader runs automatically from ordinary tests or package import.

## 20. Phased execution plan and stop gates

### Phase A — protocol and manifest freeze

**Objective:** freeze study authority, source policy, schemas, identities,
metrics, and preservation checks.

**Scope:** design, contract/test additions, provenance templates, label manual,
source-license review, and deterministic test IDs.

**Non-goals:** downloads, transforms, product runs, model calls, or final data
access.

**Dependencies:** approval of this written design and a later implementation
plan.

**Artifacts:** approved spec, implementation plan, proposed contract additions,
test matrix, and source decision record.

**Stop gate:** no implementation until spec and plan are separately approved.

### Phase B — small pilot

**Objective:** prove that a small SMARD subset can be acquired, attributed,
decoded, derived, transformed, and independently checked on one computer.

**Scope:** temporary development-only assets, one or two master families, WAV
preflight, transform candidates, and review-form rehearsal.

**Non-goals:** formal metrics, final cases, product behavior claims, or real
model calls.

**Dependencies:** explicit download and implementation authorization, disk and
network budget, and source terms snapshot.

**Artifacts:** pilot provenance, checksums, reference summaries, and protocol
corrections.

**Stop gate:** source use, single-channel/crop derivation, and all transforms
must reproduce from recorded parameters.

### Phase C — development and validation

**Objective:** build the 14-case development and 10-case validation splits and
freeze every configurable study choice.

**Scope:** deterministic dataset/transform/scoring/report harness, fixed-pipeline
runs, reference analysis, label Round 1, and validation selection rules.

**Non-goals:** final access, final model calls, or V0.2 behavior changes.

**Dependencies:** Phase B pass and TDD-authorized implementation plan.

**Artifacts:** write-once development/validation bundles, chosen global clipping
severity, alpha/post-gain identity, scoring identity, targets, and neutral
request.

**Stop gate:** validation identities and harness pass without prompt, rule, or
threshold drift.

### Phase D — freeze final_external_test

**Objective:** create and seal 28 unseen final cases.

**Scope:** source-group-isolated selection, provenance, derivation, Round 1 and
delayed Round 2 review, label resolution, scoreability mask, checksums, and
preflight.

**Non-goals:** Agent execution or result-driven replacement.

**Dependencies:** at least 14 days for delayed review and a passing validation
gate.

**Artifacts:** sealed final manifest, 24 scoreable labels, four weak/unknown
cases, review-agreement report, and final fingerprint.

**Stop gate:** final data remains unopened by the Agent until every identity and
integrity check passes.

### Phase E — one-time real-model run

**Objective:** execute the sealed 28-slot Agent campaign and identical
fixed-pipeline comparison exactly once.

**Scope:** public RealLLMPlanner, frozen provider/model/prompt/profile, one slot
per case, chronological traces, scoring, and immutable bundle writing.

**Non-goals:** retries for quality, model substitution, prompt tuning, final
relabeling, or ScriptedPlanner fallback.

**Dependencies:** explicit real-model authorization, credentials, provider
availability, and Phase D preflight.

**Artifacts:** `study_v0_2_external_wav_final_1` with all attempts, metrics,
reports, failures, and checksums.

**Stop gate:** campaign completion is recorded independently from target status.

### Phase F — case report and resume material

**Objective:** present the external evidence without overstating scope.

**Scope:** stratified Agent/baseline comparison, clustered master analysis,
success/failure cases, source/license data card, README/case-study additions,
and result-dependent resume wording.

**Non-goals:** calling the study official, industrial, production, or a new
diagnosis domain.

**Dependencies:** immutable Phase E bundle.

**Artifacts:** external-validity report, evidence map, honest limitations, and
resume text tied to actual numerators and denominators.

**Stop gate:** every public statement must trace to a frozen artifact and retain
below-target findings.

## 21. Reporting and resume boundary

Before the study, the project may say it has:

- a real-LLM behavior evaluation on a versioned synthetic held-out dataset;
- a real WAV product entry point;
- a generator-encoded WAV Demo;
- no completed real-recording external-validity benchmark.

After a completed study, it may say:

> Designed and executed a small external-validity study using public real
> loudspeaker-room-microphone recordings, controlled paired distortions on
> real-recording masters, and licensed out-of-domain audio, with source-level
> isolation, delayed blinded re-review, and immutable failure retention.

Only if targets pass may it add the actual frozen outcome, grounding, and
conservatism metrics.

It must never claim:

- industrial validation or production readiness;
- industry-standard clipping or THD limits;
- self-recorded phone/device coverage;
- precise real-chain THD causality for A;
- that public machine/environment/instrument labels are S1 causal truth;
- that a 28-case study establishes population-wide accuracy.

## 22. Resolved decisions and open questions

The following design decisions are resolved:

- one-computer execution;
- no user recording requirement;
- online public real-capture data preferred over self-recording;
- SMARD-centered A/B design, subject to the terms gate;
- one human reviewer using delayed blinded self-re-review rather than a claimed
  second reviewer;
- 14 complete days between review rounds;
- additive external study, never a replacement official benchmark.

The following require user decision before their named phase, not before review
of this specification:

1. **Download/cache budget before Phase B.** Recommended default: no more than
   5 GiB of selected subsets and temporary cache on the one computer; never
   fetch the complete 18 GiB SMARD archive merely for convenience.
2. **SMARD terms disposition before Phase B.** After retaining the official
   terms snapshot, confirm non-redistributed research use or exclude SMARD and
   approve a design revision. This document does not provide legal advice.
3. **Stress-source license policy before Phase C.** Recommended default: use
   CC BY material such as ESC-10, NSynth, and Pyramic; use CC BY-NC ESC-50 only
   if its non-commercial restriction is explicitly accepted and reported.
4. **Exact public source records before Phase D.** Approve the frozen list of
   source IDs/configurations after development/validation eligibility checks,
   without exposing final audio to the Agent.
5. **Provider budget and run window before Phase E.** Authorize the 28 consumed
   real-model slots, credential use, and one-time run window separately.
6. **Repository audio policy before Phase F.** Recommended default: commit only
   manifests, checksums, derivation instructions, and clearly redistributable
   derived assets; keep SMARD originals and ambiguous-license audio untracked.

## 23. Authorization gates

Approval of this written design authorizes only transition to a detailed
implementation plan.

It does not by itself authorize:

- data download;
- dependency installation;
- source, test, or product-code changes;
- dataset materialization;
- opening or running final cases;
- real-model calls;
- commit, push, merge, tag changes, or historical cleanup.

Later implementation must occur only on
`codex/v0.2-real-world-validation`, begin with new written contract/test IDs,
use test-driven development for behavior, and request separate authorization
for downloads and for the one-time real-model campaign.
