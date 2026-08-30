# Phase 5 Presentation Engineering Design

**Date:** 2026-08-31

**Status:** Interactive design approved on 2026-08-31. This written
specification, draft Contracts §§55–§64, draft Test Plan §28 T224–T285, and
D026–D030 are submitted for final written review. They do not authorize source
or test implementation until the user explicitly freezes the written assets
and separately authorizes an implementation plan.

**Implementation baseline:** `36ae7c9` on the accepted Phase 4.3.1 history.

**Design branch:** `phase5-presentation-engineering`

## 1. Objective

Phase 5 packages the accepted S1 distortion-diagnosis system as a local,
resume-grade application without duplicating diagnosis logic. A user can select
a deterministic synthetic signal or upload a supported PCM WAV, ask why it
sounds distorted, run the real product Agent, inspect its actual dynamic trace,
and export traceable JSON and self-contained HTML reports.

The Phase 5 product is a presentation layer over the accepted vertical slice:

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

The application does not broaden the V0.2 diagnosis space. Supported outcomes
remain clipping, harmonic distortion, basic frequency/fundamental evidence
when needed, no supported fault, and inconclusive. D016's longer-term audio,
sensor, and sampled-waveform platform vision remains unchanged.

## 2. Accepted baseline and authority

Phase 5 starts only from the merged Phase 4.3.1 terminal baseline `36ae7c9`.
That baseline contains:

- deterministic T001–T223 with the last accepted run at 825 passed;
- public `RealLLMPlanner` using prompt `v0.2-s1-planner-8.1`;
- the accepted DeepSeek `deepseek-v4-flash` product identity;
- Phase 4.3.1 development and official results that are both
  `completed/meets_target`;
- the immutable 80-slot official bundle, including two slots with behavioral
  failure codes and one wrong outcome disclosed honestly;
- the frozen DSP, Tool, Evidence, Rule, Knowledge, Runtime, and evaluation
  contracts.

Phase 5 may add presentation interfaces and narrowly expose existing generic
trace assembly. It may not change prompt bytes, evaluation targets, dataset
truth, numerical behavior, rule thresholds, Runtime decision policy, or any
historical bundle.

## 3. Selected product shape

The Web UI is the primary live Demo. A versioned HTTP API is the shared Web
backend, and a CLI is the development and automation entry point.

The selected technology is:

- FastAPI for HTTP and OpenAPI;
- server-owned static assets with native HTML, CSS, and JavaScript;
- browser `fetch` calls to same-origin APIs;
- no Node.js build chain and no frontend framework;
- `argparse` for CLI commands;
- an in-process bounded background queue with status polling;
- JSON as the canonical report and self-contained HTML as its human-readable
  rendering.

### 3.1 Considered alternatives

**FastAPI plus React/Vite** was rejected for V0.2 because it adds a second
dependency, build, and testing system without improving the diagnostic
contract.

**FastAPI-centric business logic with a CLI HTTP client** was rejected because
it makes local CLI use require a server and couples application behavior to
HTTP lifecycle.

**Separate CLI and API Runtime composition** was rejected because it duplicates
input validation, dependency assembly, execution, and reporting.

**Synchronous HTTP diagnosis** was rejected because real multi-call LLM runs
can exceed a comfortable request wait and provide poor status visibility.

**SSE or WebSocket streaming** was deferred. It would require event publication,
disconnect, and replay semantics that the accepted Runtime does not need.

## 4. Scope

### 4.1 In scope

- uncompressed integer PCM WAV ingestion;
- five public deterministic synthetic Demo presets;
- whole-file mono, left, right, or mixdown analysis as applicable;
- one shared `DiagnosisApplicationService`;
- bounded, in-memory background execution and status polling;
- real Planner decision recording and strict chronological event presentation;
- compact deterministic waveform preview;
- observation, Evidence, Rule, Knowledge, limitation, warning, and error views;
- canonical structured JSON and self-contained HTML reports;
- a packaged, checksum-linked Phase 4.3.1 evaluation summary;
- FastAPI, CLI, Web UI, packaging, README, screenshots, Demo artifacts, and CI;
- deterministic application acceptance plus a separate real-model product
  smoke protocol.

### 4.2 Non-goals

- new faults, DSP algorithms, Tool calls, thresholds, or prompt calibration;
- rerunning or replacing any Phase 4 development or official campaign;
- PCM or CSV file input outside WAV containers;
- batch diagnosis, file management, or persistent run history;
- time-range editing, live audio, or audio streaming;
- SSE, WebSocket, cancellation, pause, resume, or cross-process recovery;
- authentication, authorization, multi-tenancy, payment, or public deployment;
- database, Redis, Celery, Docker, Kubernetes, or microservices;
- React, Vue, a Node build, or a charting dependency;
- full waveform or full FFT download;
- PDF as a Phase 5 acceptance requirement;
- a ScriptedPlanner product command or automatic fake fallback;
- LangGraph, multi-Agent architecture, embeddings, or vector search.

## 5. Component boundaries

Phase 5 adds the following modules:

```text
signal_diag.signal.wav
  WAV parsing, validation, and full-scale PCM conversion

signal_diag.app
  models.py       frozen application DTOs and errors
  presets.py      public synthetic Demo catalog
  preview.py      deterministic visualization-only downsampling
  runs.py         bounded RunStore and background executor
  service.py      DiagnosisApplicationService
  composition.py  product and test dependency assembly
  reporting.py    canonical JSON and self-contained HTML rendering
  api.py          FastAPI adapter
  cli.py          argparse adapter and console entry point
  static/         index.html, styles.css, app.js

signal_diag.evaluation.assets
  packaged accepted-evaluation summary snapshot
```

The adapters converge on one application service:

```text
CLI -----------------------+
                            |
HTTP API -------------------+--> DiagnosisApplicationService
  ^                                     |
  |                                     +--> SignalRepository
Web UI                                   +--> Runtime factory
                                        +--> RunStore / executor
                                        +--> trace projection
                                        +--> report renderer
```

`signal/` remains independent of `app/`. `app/` may depend on every accepted
lower layer, including the generic recording primitives in `evaluation/`.
No lower layer imports `signal_diag.app`.

## 6. WAV ingestion contract

### 6.1 Supported formats

The loader accepts little-endian `RIFF/WAVE` containing uncompressed integer
PCM in either of these forms:

- format tag `WAVE_FORMAT_PCM`;
- `WAVE_FORMAT_EXTENSIBLE` whose subtype is PCM and whose valid bit count
  equals the container bit count.

Supported bit depths are 8, 16, 24, and 32. Supported channel counts are one
and two. Unknown well-formed RIFF chunks and legal pad bytes may be skipped.

The loader rejects RIFX, RF64, IEEE-float WAV, compressed formats, more than two
channels, missing or duplicate `fmt`/`data` chunks, truncated chunks,
inconsistent block alignment or byte rate, and trailing or declared sizes that
cannot be reconciled safely.

### 6.2 Full-scale conversion

Conversion is deterministic and does not peak-normalize:

```text
8-bit unsigned:   (sample - 128) / 128
16-bit signed:    sample / 32768
24-bit signed:    sample / 8388608
32-bit signed:    sample / 2147483648
```

Twenty-four-bit input is sign-extended correctly before scaling. Output is a
C-contiguous `float32` array shaped `(num_samples, channels)`. The resulting
`SignalRecord` is immutable after insertion into the accepted repository. The
source summary retains filename, encoded bit depth, channel count, sample rate,
frame count, duration, and source kind without changing frozen `SignalMeta`.

### 6.3 Resource limits

All limits must pass simultaneously:

```text
maximum uploaded bytes:  20 MiB (20 * 1024 * 1024)
maximum sample frames:   2,000,000
maximum duration:        30 seconds
sample-rate range:       8,000 through 192,000 Hz inclusive
```

The API reads uploads through a bounded reader and stops once the byte limit is
exceeded. It never silently truncates, resamples, normalizes, or repairs input.
These are local Demo resource limits, not signal-quality standards.

Filenames are display metadata only. Only a basename of at most 255 Unicode
code points is retained; it never participates in filesystem path construction.
Uploaded bytes are not written to a temporary file.

## 7. Synthetic presets and waveform preview

The product catalog contains five versioned public presets:

```text
clean_periodic
clipping
harmonic_distortion
combined_distortion
noise_inconclusive
```

Each preset uses existing `signal.synthetic` generators with fixed public
parameters and explicit seed where randomness exists. The catalog is separate
from every evaluation manifest and may not import or materialize held-out
cases. Product signal IDs are opaque and cannot encode the preset or expected
fault. Preset labels and generator truth never enter PlannerContext.

The preview is visualization only. It operates on the selected analysis
channel and returns at most 1,000 `(time_s, amplitude)` points. Its configurable
point bound is limited to 2–1,000. For longer signals it uses deterministic
min/max bucket envelopes so isolated peaks are not hidden by stride sampling.
It does not create Evidence, affect Agent state, or trigger a DSP Tool. The API
and reports never expose the complete waveform.

## 8. Application models and run lifecycle

Phase 5 defines frozen Pydantic application models for:

- source and analyzed-signal summaries;
- preset descriptors;
- waveform-preview points;
- run submission acknowledgement;
- lifecycle snapshots;
- compact presentation trace events;
- diagnosis reports;
- evaluation summary;
- structured application errors.

The lifecycle is:

```text
queued -> running -> completed
                  \-> failed
```

`completed` means a valid `AgentRunResult` exists. The nested Agent result may
still have `status="error"`; the UI and report must show that truthfully.
`failed` is reserved for application/infrastructure failure before a valid
Runtime result can be stored. Inconclusive is a diagnosis outcome, not an
application failure.

The default local store permits one active run, at most four queued runs, and
retains the latest twenty terminal runs. A new submission evicts the oldest
terminal run when necessary. Queued or running records are never evicted. When
no safe capacity exists, submission returns `capacity_exceeded`. Eviction also
removes source and derived waveform records that are owned only by that run.

State transitions are atomic and monotonic. Run IDs use `run_` plus 32 lowercase
UUID4 hexadecimal characters; Run and Signal IDs are random and semantically
opaque. WAV source summaries require encoded bit depth and forbid preset ID;
synthetic summaries require preset ID and forbid encoded bit depth. DTO floats
reject NaN and infinity. Process restart clears all runs and uploaded signals.
Phase 5 provides no persistence or recovery claim.

Service shutdown is explicit and idempotent: stop admitting work, fail queued
runs with a sanitized application error, and await the one active run. This is
process lifecycle handling, not a user-facing cancellation feature.

## 9. Application service and composition

`DiagnosisApplicationService` is the only product use-case boundary. Its
operations submit WAV or synthetic work, list presets, read run state, and
render reports. CLI and API call the same service; the Web UI calls the API.

Submission performs these steps:

1. validate the question and source;
2. decode or generate the canonical source record;
3. apply the requested `left`, `right`, or `mixdown` selection with the accepted
   `extract_segment()` behavior;
4. create a run-owned mono analysis record with an opaque ID;
5. calculate the bounded visualization preview;
6. reserve a queued run atomically;
7. execute it through a newly composed Planner and Runtime.

The question is trimmed, must remain non-empty, and is limited to 2,000
characters. The service may add a factual analyzed-channel instruction. It may
not add a fault label, preset label, expected Tool, expected outcome, scoring
target, or generator truth.

Every run creates fresh `RealLLMPlanner`, `RecordingPlanner`, and
`DistortionDiagnosisRuntime` instances. It reuses the accepted repository,
RuleEngine, explicit `profile_s1_distortion` mapping, KnowledgeIndex corpus,
and Tool service through injected composition. This prevents Runtime counters
or planner records from crossing run boundaries.

The product composition defaults to DeepSeek, `deepseek-v4-flash`, and the
public v8.1 `RealLLMPlanner`. It uses `DEEPSEEK_API_KEY` and the existing
optional `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` overrides. Actual provider,
model, and prompt version are recorded. A non-default model is labeled as not
the model certified by the Phase 4.3.1 official benchmark.

The server can start without credentials so health and static documentation
remain available. A diagnosis submission then fails before run reservation
with `planner_not_configured`. There is no ScriptedPlanner fallback. Tests
inject a planner/runtime factory explicitly.

## 10. Product trace bridge

The product must display real decision order, not a reconstructed fixed
pipeline and not fake progress labels.

Phase 5 adds one backward-compatible public function in
`signal_diag.evaluation.recording`:

```python
def assemble_agent_events(
    records: tuple[PlannerDecisionRecord, ...],
    result: AgentRunResult,
) -> tuple[EvaluationEvent, ...]:
    ...
```

It exposes the existing strict Agent-event assembly without requiring an
`EvaluationCase`, causal truth, scoring configuration, or run slot.
`assemble_evaluation_trace()` delegates to it for Agent traces. All Phase 4
trace ordering, suffix validation, reference validation, forbidden-payload
checks, and historical outputs remain unchanged.

The application projects these generic events into compact presentation events
and links each action to the resulting observation, Evidence, Rule batch, or
Knowledge retrieval. It does not expose repeated full PlannerContext snapshots
in report JSON. Per-decision latency and observed provider usage may be shown;
missing usage is not estimated.

During queued/running state the UI shows only actual lifecycle status. The
complete verified timeline appears after Runtime completion. Phase 5 does not
claim live event streaming.

## 11. Reports and evaluation summary

### 11.1 Canonical report

One frozen `DiagnosisReport` is the source of truth for both formats. It
contains:

- schema version, report time, run identity, and lifecycle status;
- source summary, selected channel, and analysis metadata;
- provider, model, and prompt identity;
- structured diagnosis and termination reason;
- compact chronological trace events;
- observations, Evidence, Rule evaluations, and Knowledge citations;
- limitations, warnings, sanitized errors, and observed usage;
- the bounded waveform preview.

JSON is a direct serialization of that validated model. HTML is rendered only
from the model, with embedded CSS and no CDN or executable report script. With
an injected clock, rendering the same report model is deterministic.

Every claim reference must resolve within the same report. Missing Evidence,
Rule, or Knowledge references cause `trace_integrity_error`; the renderer never
drops or invents a reference. All external text is HTML-escaped. Reports
exclude credentials, authorization headers, stack traces, raw provider
responses, full waveform arrays, and full FFT arrays.

The preview is labeled `visualization only`. Rule output is labeled with
`profile_s1_distortion 1.0.0-demo`, and the 1% clipping and 5% THD limits are
described only as demonstration configuration, never an industry standard or
SLA. PDF remains deferred.

### 11.2 Evaluation summary

`evaluation/` owns a compact, versioned, packageable snapshot derived from:

```text
docs/evaluations/phase4_3_1/official/
  bench_official_s1_v12_planner8_1_gate5/
```

The snapshot records source bundle checksums, configuration identity, target
bands, actual aggregate metrics, Agent/fixed-pipeline comparison, slot counts,
and disclosed failures. A deterministic test compares it with the committed
official bundle so a hand-edited or stale summary cannot pass.

The frozen `AcceptedEvaluationSummary` carries the exact five checksums listed
by `checksums.sha256`, canonical bundle-relative path, benchmark/dataset/
provider/model/prompt/profile/scoring identities, `TargetBands`, Agent and
fixed-pipeline `AggregateMetrics`, 80 Agent slots, two behavioral-failure
slots, one outcome-error slot, and the demonstration-target disclaimer.

The Web Evaluation panel must state that development and official were both
`completed/meets_target`, that official used 80 held-out Agent slots, and that
two of 80 slots had behavioral failure codes while one of 80 had the sole
wrong outcome. It must call targets demonstration targets rather than standards
or SLAs. The UI does not rescore traces or hide failures.

## 12. HTTP API

The versioned same-origin API is:

```text
GET  /api/v1/health
GET  /api/v1/presets
GET  /api/v1/evaluation-summary

POST /api/v1/runs/wav
POST /api/v1/runs/synthetic

GET  /api/v1/runs/{run_id}
GET  /api/v1/runs/{run_id}/report.json
GET  /api/v1/runs/{run_id}/report.html

GET  /
```

WAV submission is multipart and synthetic submission is JSON. A valid
submission returns HTTP 202 with a run ID and queued snapshot. Status polling
returns lifecycle state and includes the final result only at a terminal state.
Reports return conflict until a completed Runtime result exists. Downloads use
safe `Content-Disposition` filenames derived from the opaque run ID.

FastAPI's OpenAPI document remains available. CORS is disabled by default.
The server binds `127.0.0.1` by default. README warns that the V0.2 service has
no authentication and must not be exposed directly to an untrusted network.

## 13. CLI and Web UI

The console script is `signal-diag` and uses `argparse`:

```text
signal-diag serve
signal-diag presets
signal-diag diagnose wav <path>
signal-diag diagnose synthetic <preset_id>
```

Diagnosis supports `--question`, `--channel`, `--output text|json`, and
`--html-output`. It uses the same application service, waits for its run to
finish, and never reassembles Runtime dependencies independently.

CLI exit codes are:

```text
0  valid terminal diagnosis, including no-supported-fault or inconclusive
1  Agent/runtime or application execution failure
2  usage, source-input, or product-configuration error
```

The Web UI has input, lifecycle, diagnosis, export, and Evaluation sections.
It shows outcome, confidence, termination, claims, waveform preview, actual
trace, observations, Evidence, Rule results, Knowledge citations, limitations,
warnings, errors, and report links. It uses safe DOM APIs such as
`textContent` for external text and never inserts LLM or uploaded content as
HTML.

## 14. Error and security contract

Application errors share this envelope:

```json
{
  "error": {
    "code": "unsupported_wav",
    "message": "human-readable message",
    "details": {}
  }
}
```

Frozen codes are:

```text
invalid_request
payload_too_large
unsupported_wav
invalid_wav
signal_limit_exceeded
unknown_preset
run_not_found
run_not_terminal
report_unavailable
capacity_exceeded
planner_not_configured
provider_error
runtime_error
trace_integrity_error
internal_error
```

HTTP mapping uses 400/422 for invalid requests, 413 for upload bytes, 415 for
unsupported WAV encoding, 404 for unknown resources, 409 for non-terminal,
non-reportable, or conflicting state, 429 for capacity, 503 for missing product
configuration, and 500 for integrity or unexpected endpoint failure. Provider
or Runtime failures after an accepted 202 submission are represented honestly
in the polled terminal snapshot rather than rewritten as a synchronous HTTP
failure. Exact validation details are safe and structured; responses never
include secrets or stack traces.

The application retains the Phase 4 sanitizer for planner/provider messages.
The API never returns API keys, authorization values, raw provider bodies, full
waveforms, or full FFT arrays. Static responses use a same-origin Content
Security Policy. Default CORS is off. Opaque IDs reveal no preset or case truth.

## 15. Packaging, documentation, and CI

FastAPI, an ASGI server, multipart support, and the OpenAI-compatible client are
installed through explicit optional groups. The core DSP package remains
installable without Web dependencies. `signal-diag` and all static/report
assets are included in the wheel.

The repository adds a secret-free CI workflow for Python 3.11 and 3.12. CI
runs the full deterministic suite, Ruff, mypy, architecture checks, wheel
build, clean wheel-install smoke, and diff validation. CI never calls a real
LLM and never requires `DEEPSEEK_API_KEY`.

The root README must include scope, architecture, install/configuration,
one-command local startup, CLI examples, UI screenshots, report examples,
Phase 4.3.1 evaluation results, limitations, truthful resume bullets, and a
clear distinction between synthetic Demo data and real production or chip-test
data.

One documented sequence starts the product:

```text
install app + llm extras
set DEEPSEEK_API_KEY locally
signal-diag serve
open the localhost URL
```

No credential, generated local run store, or unsanitized provider artifact is
committed.

## 16. Acceptance

### 16.1 Deterministic presentation harness

Draft T224–T285 in Test Plan §28 cover WAV, presets, preview, application
models, RunStore, service, composition, trace bridge, reports, API, CLI, UI,
evaluation summary, packaging, architecture, CI, and the cumulative gate.

Acceptance requires:

- T001–T285 pass with zero required skip or xfail;
- Ruff, mypy, architecture, and `git diff --check` pass;
- wheel build and clean-install smoke pass;
- Python 3.11 and 3.12 CI pass;
- all Phase 1–4.3.1 semantics and immutable assets remain unchanged;
- deterministic API integration uses ScriptedPlanner injection with real DSP,
  Tools, RuleEngine, KnowledgeIndex, Runtime, service, and report rendering;
- no deterministic test accesses a real provider.

The state is named `presentation_harness_accepted` only after all of those
checks are current and green.

### 16.2 Real-model product Demo

After deterministic acceptance, one public synthetic preset and one public
Demo signal encoded as supported PCM WAV each run once through the public
`RealLLMPlanner` and the same application service. Each run must produce an
actual planner trace and valid JSON/HTML report with same-run reference
integrity and forbidden-payload checks.

This is an integration demonstration, not a replacement stochastic benchmark.
The result is retained honestly whether the two individual diagnoses are right
or wrong. Phase 4.3.1 remains the behavior-quality evidence. No failed Demo may
fall back to ScriptedPlanner.

Sanitized Demo reports and UI screenshots are committed under a versioned Demo
directory. Missing credentials leave `real_demo_pending`; they do not fail
deterministic CI, but Phase 5 cannot be called fully accepted.

Phase 5 is accepted only when both states are true:

```text
presentation_harness_accepted
real_demo_completed
```

Only then may V0.2 be described as a complete resume-grade demonstrable
product.

## 17. Proposed implementation order

After written-spec approval and a separate detailed plan:

1. freeze documentation and acceptance IDs;
2. expose the generic Agent event bridge;
3. implement WAV ingestion;
4. implement presets and preview;
5. implement app models, RunStore, and executor;
6. implement service and composition;
7. implement reports and evaluation summary;
8. implement FastAPI;
9. implement CLI;
10. implement Web UI;
11. implement packaging, CI, README, and screenshots;
12. pass the deterministic cumulative gate;
13. run the two real-model Demo cases;
14. perform independent final acceptance.

Each code task uses TDD, focused RED/GREEN evidence, cumulative tests, separate
spec-compliance and code-quality reviews, and a local task commit. No task may
push, merge, delete worktrees, modify historical evaluation assets, or touch
the pre-existing untracked `build/` directory without separate authorization.

## 18. Documentation and authorization gates

This file records the approved interactive design. The next gates are:

1. user reviews and explicitly freezes this written specification,
   Contracts §§55–§64, Test Plan §28 T224–T285, and D026–D030;
2. use the Superpowers writing-plans workflow to create a task-level
   implementation plan;
3. user reviews the plan and explicitly chooses an implementation workflow;
4. only then may Phase 5 source or test implementation begin.

Until all four gates pass, no Phase 5 implementation, model run, push, merge,
worktree deletion, or `build/` cleanup is authorized.
