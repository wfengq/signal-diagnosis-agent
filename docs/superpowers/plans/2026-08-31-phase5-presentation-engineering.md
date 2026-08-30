# Phase 5 Presentation Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task-by-task.
> Every implementation task also uses `superpowers:test-driven-development`;
> every review response uses `superpowers:receiving-code-review`; every
> completion claim uses `superpowers:verification-before-completion`. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the accepted S1 distortion-diagnosis vertical slice as a
local Web/API/CLI product that accepts deterministic presets and bounded PCM
WAV, runs the real product Agent dynamically, exposes its actual strict trace,
and exports canonical JSON/self-contained HTML evidence reports.

**Architecture:** Add strict WAV ingestion to `signal`, an additive generic
Agent-event bridge to `evaluation`, and one thin `app` layer containing frozen
DTOs, bounded in-process execution, the shared application service, reports,
FastAPI, argparse, and a native no-build Web UI. All adapters converge on
`DiagnosisApplicationService`; the existing Runtime remains the only Agent
controller and public `RealLLMPlanner` remains the product planner.

**Tech Stack:** Python 3.11/3.12, NumPy, Pydantic v2, PyYAML, FastAPI,
Uvicorn, python-multipart low-level streaming callbacks, native HTML/CSS/JS,
argparse, pytest/pytest-asyncio/httpx, Ruff, mypy, setuptools/build, and the
existing DeepSeek OpenAI-compatible planner client.

**Spec:**
`docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md`

**Implementation baseline:** `07619fb` on
`phase5-presentation-engineering`. This commit freezes OQ-010, Contracts
§§55–§64, Test Plan §28 T224–T285, and D026–D030.

**Execution start:** Cursor starts from the committed plan HEAD on
`phase5-presentation-engineering`. Task 1 is complete. Nothing in this plan
authorizes Task 2 until the user separately chooses an execution workflow.

## Global Constraints

- Read `AGENTS.md` and every required document it lists before Task 2.
- Preserve the pre-existing untracked `build/` directory without staging,
  deleting, moving, or using it for Phase 5 artifacts.
- Preserve Phase 1–4.3.1 public behavior, prompt bytes, datasets, scoring,
  targets, reports, and committed evaluation-bundle checksums.
- Do not change `PlannerModel`, `PlannerContext`, `AgentDecision`,
  `AgentRunResult`, `DistortionDiagnosisRuntime`, Rule/Knowledge contracts, DSP
  algorithms, Tool semantics, or `profile_s1_distortion 1.0.0-demo`.
- `RealLLMPlanner` is the product path. Scripted/fake planners are explicit
  deterministic test injection only and are never a product fallback.
- Never send raw waveform, full FFT, preset identity/truth, evaluation truth,
  expected Tool/outcome, or target bands to PlannerContext.
- Numeric diagnosis values come only from deterministic DSP. Thresholds come
  only from the frozen profile. The 1% clipping and 5% THD settings are Demo
  configuration, not standards or SLAs.
- Application `run_[0-9a-f]{32}` IDs and the frozen Runtime's nested Agent run
  ID are distinct correlation scopes. Do not change Runtime to accept an app
  ID; validate same-run Evidence/Rule/Knowledge references inside the nested
  `AgentRunResult`.
- Web multipart parsing must consume `Request.stream()` through bounded
  python-multipart callbacks. Do not use `UploadFile`, `request.form()`, or any
  path that may spool uploaded bytes to disk.
- API/UI/CLI/report code must not calculate DSP values, select Tools, evaluate
  rules, retrieve Knowledge, or synthesize diagnoses.
- No Node build, frontend framework, CDN, database, Redis, Celery, Docker,
  authentication, cancellation, SSE/WebSocket, PDF, vector database, LangGraph,
  or multi-Agent product architecture.
- Required CI is deterministic and secret-free. Do not call DeepSeek from
  pytest or CI.
- Do not run P5-R001–P5-R003 until T001–T285 and all deterministic gates are
  committed and independently green.
- Do not push, merge, delete the worktree, or clean `build/` without separate
  authorization.

Use this interpreter for local commands:

```powershell
$Phase5Python = 'C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

## File and Responsibility Map

```text
src/signal_diag/signal/wav.py
    strict RIFF/WAVE parsing, limits, PCM conversion, WAV exceptions

src/signal_diag/evaluation/recording.py
    public assemble_agent_events extraction; legacy trace delegation

src/signal_diag/evaluation/assets/
    immutable accepted Phase 4.3.1 summary JSON only

src/signal_diag/app/models.py
    exact frozen Phase 5 DTOs and model invariants
src/signal_diag/app/errors.py
    typed application exceptions and safe AppErrorDetail conversion
src/signal_diag/app/presets.py
    five public deterministic Demo signals; no evaluation imports
src/signal_diag/app/preview.py
    deterministic visualization-only min/max envelope
src/signal_diag/app/runs.py
    atomic InMemoryRunStore and one-worker bounded FIFO executor
src/signal_diag/app/service.py
    DiagnosisApplicationService and shared source-to-Runtime use case
src/signal_diag/app/composition.py
    product/test dependency assembly; RealLLMPlanner product factory
src/signal_diag/app/reporting.py
    trace projection, report validation, JSON/HTML, evaluation-summary load
src/signal_diag/app/multipart.py
    bounded in-memory streaming multipart decoder; never UploadFile
src/signal_diag/app/api.py
    FastAPI adapter, error mapping, lifecycle, static files
src/signal_diag/app/cli.py
    argparse adapter and console entry
src/signal_diag/app/static/
    index.html, styles.css, app.js; native same-origin UI

scripts/build_phase5_evaluation_summary.py
    deterministic one-way generator from immutable official bundle
scripts/create_phase5_demo_wav.py
    deterministic supported 16-bit PCM Demo input
scripts/verify_phase5_wheel.py
    cross-platform isolated sdist/wheel build, install, asset, and smoke gate
scripts/smoke_installed_phase5.py
    installed-wheel smoke without provider access

tests/signal/test_wav.py
tests/app/test_models.py
tests/app/test_presets_preview.py
tests/app/test_runs.py
tests/app/test_service.py
tests/app/test_reporting.py
tests/app/test_api.py
tests/app/test_cli.py
tests/app/test_ui.py
tests/app/test_packaging.py
    T224–T282 focused coverage

tests/evaluation/test_recording.py
tests/test_architecture_boundaries.py
    T253–T255 and T283/T285 compatibility/boundary gates
```

## Required Per-Task Review Protocol

For Tasks 2–12 and every corrective change in Tasks 13–15, Cursor uses this
serial sequence:

1. A fresh Implementer agent performs RED → GREEN TDD and leaves changes
   uncommitted.
2. A separate agent reviews specification compliance against §§55–§64, the
   assigned T224–T285 IDs, D026–D030, the frozen design, and this Task.
3. The Implementer fixes every Critical or Important spec finding; a separate
   agent re-reviews each fix to closure.
4. A separate agent performs code-quality review.
5. The Implementer fixes every Critical or Important quality finding; a
   separate agent re-reviews each fix to closure.
6. The main Cursor controller independently inspects the diff and reruns focused
   plus cumulative verification.
7. Only the main Cursor controller creates the local Task commit.

Do not let agents modify the same worktree concurrently. Do not start the next
Task before the current Task is committed. Review prose is not evidence; Git
state and independently rerun commands determine status.

---

### Task 1: Freeze Phase 5 design and acceptance contracts — complete

**Files:**

- Created:
  `docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md`
- Modified: `AGENTS.md`, `docs/README.md`, `docs/CONTRACTS_V0_2.md`,
  `docs/TEST_PLAN_V0_2.md`, `docs/DECISIONS.md`,
  `docs/OPEN_QUESTIONS.md`

**Produces:** Frozen §§55–§64, T224–T285, D026–D030, resolved OQ-010, and
this plan's authority boundary.

Completed by Codex in local commits:

```text
cab18b9  docs: draft phase 5 presentation engineering contracts
07619fb  docs: freeze phase 5 presentation contracts
```

Cursor must not redo, amend, squash, or reinterpret Task 1.

---

### Task 2: Expose strict generic Agent event assembly

**Files:**

- Modify: `src/signal_diag/evaluation/recording.py`
- Modify: `src/signal_diag/evaluation/__init__.py`
- Modify: `tests/evaluation/test_recording.py`

**Interfaces:**

- Consumes: `PlannerDecisionRecord`, `AgentRunResult`, existing private
  `_assemble_agent_events`, `_validate_result_artifacts`,
  `_validate_claim_refs`, and `_reject_forbidden_payloads`.
- Produces:
  `assemble_agent_events(records: tuple[PlannerDecisionRecord, ...], result: AgentRunResult) -> tuple[EvaluationEvent, ...]`.
- `assemble_evaluation_trace` must delegate to the new function for Agent
  traces and remain byte-equivalent for every historical evaluation artifact.

- [ ] **Step 1: Re-establish recording baseline**

  ```powershell
  & $Phase5Python -m pytest tests/evaluation/test_recording.py tests/evaluation/test_reporting.py -q
  ```

  Expected: green before edits.

- [ ] **Step 2: Write T253–T255 RED tests**

  Extend `tests/evaluation/test_recording.py` so its existing
  `_full_agent_chain()` fixture proves the public helper and legacy delegation:

  ```python
  from signal_diag.evaluation import assemble_agent_events


  def test_t253_public_agent_event_assembly() -> None:
      records, result = _full_agent_chain()
      events = assemble_agent_events(records, result)
      assert isinstance(events, tuple)
      assert [event.event_index for event in events] == list(range(len(events)))
      assert [event.event_type for event in events] == [
          "planner_call",
          "observation",
          "planner_call",
          "rule_evaluation",
          "planner_call",
          "knowledge_retrieval",
          "planner_call",
      ]


  def test_t255_evaluation_trace_delegates_without_drift() -> None:
      records, result = _full_agent_chain()
      events = assemble_agent_events(records, result)
      trace = assemble_evaluation_trace(
          make_evaluation_case(),
          records,
          result,
          _benchmark_config(),
          run_slot=1,
          execution_path="agent",
      )
      assert trace.events == events
  ```

  Reuse existing invalid-history parameterizations for T254 and call the new
  helper directly. Require empty-delta decisions and planner errors to remain,
  while non-append-only suffixes, grouped histories, unknown references, and
  forbidden payloads raise `ValueError`.

- [ ] **Step 3: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/evaluation/test_recording.py -q
  ```

  Expected: import failure because `assemble_agent_events` is absent.

- [ ] **Step 4: Implement the public extraction**

  Add this exact public boundary and replace the Agent branch's private call:

  ```python
  def assemble_agent_events(
      records: tuple[PlannerDecisionRecord, ...],
      result: AgentRunResult,
  ) -> tuple[EvaluationEvent, ...]:
      _validate_path("agent", result, records)
      events = _assemble_agent_events(records, result)
      _validate_result_artifacts(result, events)
      _validate_claim_refs(records, result, events)
      _reject_forbidden_payloads(records, events)
      return tuple(events)
  ```

  In `assemble_evaluation_trace`, use `events = list(assemble_agent_events(records, result))`
  for the Agent branch. Move the existing artifact/ref/payload validation into
  the fixed-pipeline branch so the Agent path is validated exactly once by the
  helper; keep fixed-pipeline results byte-equivalent. Re-export the helper from
  `signal_diag.evaluation`.

- [ ] **Step 5: Run GREEN and historical regression**

  ```powershell
  & $Phase5Python -m pytest tests/evaluation/test_recording.py tests/evaluation/test_reporting.py tests/evaluation/test_scoring.py -q
  ```

- [ ] **Step 6: Apply the review protocol and commit**

  Spec review checks T253–T255 and byte-equivalent Phase 4 traces. Quality
  review rejects duplicated validation or relaxed payload checks. Then:

  ```powershell
  git add src/signal_diag/evaluation/recording.py src/signal_diag/evaluation/__init__.py tests/evaluation/test_recording.py
  git commit -m "feat(evaluation): expose strict Agent event assembly"
  ```

---

### Task 3: Implement strict bounded PCM WAV ingestion

**Files:**

- Create: `src/signal_diag/signal/wav.py`
- Modify: `src/signal_diag/signal/__init__.py`
- Create: `tests/signal/test_wav.py`

**Interfaces:**

- Produces exact §56 exports: `WavLoadLimits`, `WavSourceInfo`, `LoadedWav`,
  `load_wav_bytes`, `WavDecodeError`, `UnsupportedWavError`,
  `InvalidWavError`, and `SignalLimitExceededError`.
- Uses `build_signal_record(..., source_type="wav")` only after every RIFF,
  encoding, byte, frame, duration, and rate check succeeds.

- [ ] **Step 1: Write a deterministic WAV fixture builder**

  In `tests/signal/test_wav.py`, create bytes without external files:

  ```python
  import struct


  def _riff_wave(*, fmt_payload: bytes, data: bytes, extra: tuple[bytes, ...] = ()) -> bytes:
      chunks = [b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload]
      chunks.extend(extra)
      chunks.append(b"data" + struct.pack("<I", len(data)) + data)
      body = b"WAVE" + b"".join(
          chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
      )
      return b"RIFF" + struct.pack("<I", len(body)) + body


  def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
      block_align = channels * bits // 8
      return struct.pack(
          "<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits
      )
  ```

  Add a second helper for format tag `0xFFFE`, 22-byte extension, matching valid
  bits, and the PCM subtype GUID bytes.

- [ ] **Step 2: Write T224–T233 RED tests**

  Parameterize mono/stereo and 8/16/24/32-bit extrema. Assert exact float32
  values:

  ```python
  np.testing.assert_array_equal(
      loaded.record.samples[:, 0],
      np.asarray([-1.0, 0.0, 32767 / 32768], dtype=np.float32),
  )
  assert loaded.record.samples.dtype == np.float32
  assert loaded.record.samples.flags.c_contiguous
  assert loaded.record.meta.source_type == "wav"
  assert re.fullmatch(r"sig_[0-9a-f]{32}", loaded.record.meta.signal_id)
  ```

  Cover exact 20 MiB eligibility and next-byte rejection, 8,000/192,000 Hz
  inclusivity, 2,000,000 frames, 30 seconds, odd pad bytes, unknown chunks,
  24-bit sign extension, basename/255-code-point handling, and no temp-file
  calls. Reject duplicate/missing `fmt `/`data`, RIFX/RF64/float/compressed,
  valid-bit mismatch, truncation, partial frame, bad RIFF size, byte rate,
  block alignment, channels, rate, duration, and frame count with the exact
  exception class.

- [ ] **Step 3: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/signal/test_wav.py -q
  ```

  Expected: module import failure.

- [ ] **Step 4: Implement bounded RIFF traversal**

  Use `memoryview` and checked integer offsets; do not call `wave.open` because
  extensible PCM and strict duplicate/trailing validation must be explicit:

  ```python
  def _read_chunk_header(view: memoryview, offset: int) -> tuple[bytes, int, int]:
      if offset + 8 > len(view):
          raise InvalidWavError("truncated RIFF chunk header")
      chunk_id = bytes(view[offset : offset + 4])
      size = int.from_bytes(view[offset + 4 : offset + 8], "little")
      data_start = offset + 8
      data_end = data_start + size
      if data_end > len(view):
          raise InvalidWavError("declared RIFF chunk exceeds input")
      return chunk_id, data_start, data_end
  ```

  Require RIFF declared size `len(data) - 8`, exactly one `fmt ` and `data`,
  legal pad handling, and no allocation from declared sizes before bounds pass.

- [ ] **Step 5: Implement exact PCM decoding and model validation**

  Decode 24-bit samples by assembling unsigned bytes and sign extending before
  division:

  ```python
  raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
  value = (
      raw[:, 0].astype(np.int32)
      | (raw[:, 1].astype(np.int32) << 8)
      | (raw[:, 2].astype(np.int32) << 16)
  )
  value = np.where(value & 0x800000, value - 0x1000000, value)
  samples = (value.astype(np.float64) / 2**23).astype(np.float32)
  ```

  Decode other depths with explicit little-endian dtypes, reshape by channels,
  and call `build_signal_record` only after all limits pass. Strip directory
  components from both slash styles, truncate display metadata to 255 Unicode
  code points, and never open/write a file.

- [ ] **Step 6: Run GREEN and Signal regressions**

  ```powershell
  & $Phase5Python -m pytest tests/signal/test_wav.py tests/signal -q
  ```

- [ ] **Step 7: Apply the review protocol and commit**

  Spec review maps every T224–T233 row. Quality review checks integer overflow,
  allocation order, 24-bit math, no normalization, and no filesystem write.
  Then:

  ```powershell
  git add src/signal_diag/signal/wav.py src/signal_diag/signal/__init__.py tests/signal/test_wav.py
  git commit -m "feat(signal): add strict bounded PCM WAV loading"
  ```

---

### Task 4: Add frozen application DTOs and typed errors

**Files:**

- Create: `src/signal_diag/app/__init__.py`
- Create: `src/signal_diag/app/models.py`
- Create: `src/signal_diag/app/errors.py`
- Create: `tests/app/__init__.py`
- Create: `tests/app/test_models.py`

**Interfaces:**

- Produces the exact Pydantic models in §§57–§58 and §61:
  `DemoPresetDescriptor`, `WaveformPoint`, `WaveformPreview`, `AppErrorDetail`,
  `AppErrorEnvelope`, `SourceSummary`, `PlannerIdentity`, `TraceEventView`,
  `RunSubmission`, `AppRunSnapshot`, `DiagnosisReport`, and
  `AcceptedEvaluationSummary`.
- Produces private typed `ApplicationError` subclasses that carry a frozen
  `AppErrorDetail`; HTTP mapping remains Task 9's responsibility.

- [ ] **Step 1: Write T239–T240 RED model tests**

  Create factories with a fixed UTC time and require exact discriminators,
  immutability, finite numbers, and state invariants:

  ```python
  NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
  RUN_ID = "run_0123456789abcdef0123456789abcdef"


  def test_t239_source_discriminator_and_run_id() -> None:
      wav = SourceSummary(
          source_kind="wav",
          display_name="input.wav",
          sample_rate_hz=48_000,
          channels=2,
          num_frames=48_000,
          duration_s=1.0,
          bits_per_sample=16,
      )
      assert wav.preset_id is None
      with pytest.raises(ValidationError):
          SourceSummary.model_validate(
              {**wav.model_dump(), "preset_id": "clipping"}
          )
      with pytest.raises(ValidationError):
          RunSubmission(run_id="run_clipping", status="queued")
  ```

  Construct queued, running, completed, and failed snapshots. Reject every
  illegal timestamp/result/error/trace combination, non-UTC time, NaN/inf,
  WAV-with-preset, synthetic-with-bits, wrong checksum keys, wrong frozen
  counts, and mutation.

- [ ] **Step 2: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_models.py -q
  ```

  Expected: `signal_diag.app` import failure.

- [ ] **Step 3: Implement strict common validators**

  Use one private UTC helper and model validators; do not loosen frozen fields:

  ```python
  _RUN_ID_PATTERN = r"^run_[0-9a-f]{32}$"


  def _require_utc(value: datetime, field_name: str) -> None:
      if value.tzinfo is None or value.utcoffset() != timedelta(0):
          raise ValueError(f"{field_name} must be timezone-aware UTC")


  class SourceSummary(BaseModel):
      model_config = ConfigDict(frozen=True, allow_inf_nan=False)

      source_kind: Literal["wav", "synthetic"]
      display_name: str = Field(min_length=1, max_length=255)
      sample_rate_hz: int = Field(gt=0)
      channels: Literal[1, 2]
      num_frames: int = Field(gt=0)
      duration_s: float = Field(gt=0.0)
      bits_per_sample: Literal[8, 16, 24, 32] | None = None
      preset_id: DemoPresetId | None = None

      @model_validator(mode="after")
      def validate_source(self) -> "SourceSummary":
          if self.source_kind == "wav":
              if self.bits_per_sample is None or self.preset_id is not None:
                  raise ValueError("wav source requires bits and forbids preset")
          elif self.preset_id is None or self.bits_per_sample is not None:
              raise ValueError("synthetic source requires preset and forbids bits")
          return self
  ```

- [ ] **Step 4: Implement lifecycle validation**

  Define every field exactly as §58 and validate status-specific state:

  ```python
  @model_validator(mode="after")
  def validate_lifecycle(self) -> "AppRunSnapshot":
      _require_utc(self.created_at, "created_at")
      if self.started_at is not None:
          _require_utc(self.started_at, "started_at")
      if self.finished_at is not None:
          _require_utc(self.finished_at, "finished_at")
      if self.status == "queued":
          valid = self.started_at is None and self.finished_at is None
      elif self.status == "running":
          valid = self.started_at is not None and self.finished_at is None
      elif self.status == "completed":
          valid = (
              self.started_at is not None
              and self.finished_at is not None
              and self.result is not None
              and self.application_error is None
          )
      else:
          valid = (
              self.started_at is not None
              and self.finished_at is not None
              and self.result is None
              and self.application_error is not None
          )
      if not valid:
          raise ValueError("snapshot fields do not match lifecycle status")
      if self.status not in ("completed", "failed") and self.trace_events:
          raise ValueError("non-terminal snapshots forbid trace events")
      if self.status == "failed" and self.trace_events:
          raise ValueError("application-failed snapshots forbid trace events")
      return self
  ```

  Enforce monotonic `created_at <= started_at <= finished_at` when fields exist.

- [ ] **Step 5: Implement report and evaluation-summary validators**

  Use the exact §61 fields. Require exact checksum keys and lowercase digests:

  ```python
  _SUMMARY_FILES = frozenset(
      {
          "benchmark_manifest.json",
          "case_summary.csv",
          "metrics.json",
          "report.md",
          "runs.jsonl",
      }
  )


  @field_validator("source_checksums_sha256")
  @classmethod
  def validate_checksums(cls, value: dict[str, str]) -> dict[str, str]:
      if set(value) != _SUMMARY_FILES:
          raise ValueError("evaluation summary checksum keys are not canonical")
      if any(re.fullmatch(r"[0-9a-f]{64}", digest) is None for digest in value.values()):
          raise ValueError("evaluation summary checksums must be lowercase SHA-256")
      return dict(sorted(value.items()))
  ```

  `DiagnosisReport.status` is always `completed`; `generated_at` is UTC.

- [ ] **Step 6: Add safe typed application errors**

  Keep exception messages sanitized at construction:

  ```python
  class ApplicationError(Exception):
      def __init__(self, detail: AppErrorDetail) -> None:
          super().__init__(detail.message)
          self.detail = detail


  class AppCapacityError(ApplicationError):
      pass


  class PlannerNotConfiguredError(ApplicationError):
      pass


  class TraceIntegrityError(ApplicationError):
      pass


  class PayloadTooLargeError(ApplicationError):
      pass
  ```

  Add the private typed subclasses `InvalidRequestError`,
  `UnknownPresetError`, `RunNotFoundError`, `RunNotTerminalError`, and
  `ReportUnavailableError`. Together with the four classes above, each class
  must construct exactly one frozen `AppErrorCode`; do not add a second
  payload-too-large exception or an HTTP-aware exception hierarchy.

- [ ] **Step 7: Run GREEN**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_models.py -q
  & $Phase5Python -m mypy --no-incremental src/signal_diag/app
  ```

- [ ] **Step 8: Apply the review protocol and commit**

  Spec review compares every DTO field with §§57–§58/§61. Quality review checks
  validators are centralized, frozen, finite, and free of HTTP imports. Then:

  ```powershell
  git add src/signal_diag/app tests/app
  git commit -m "feat(app): add frozen Phase 5 application models"
  ```

---

### Task 5: Add isolated Demo presets and deterministic preview

**Files:**

- Create: `src/signal_diag/app/presets.py`
- Create: `src/signal_diag/app/preview.py`
- Modify: `src/signal_diag/app/__init__.py`
- Create: `tests/app/test_presets_preview.py`

**Interfaces:**

- Produces `list_demo_presets()`, `build_demo_preset(preset_id)`, and
  `build_waveform_preview(samples, sample_rate_hz, max_points=1000)`.
- Consumes only accepted `signal.synthetic` generators; it never imports
  `signal_diag.evaluation`.

- [ ] **Step 1: Write T234–T238 RED tests**

  Assert exact order and IDs, byte-identical repeated samples but distinct
  opaque Signal IDs, the noise seed, no evaluation imports, extrema-preserving
  preview, and invalid `max_points`:

  ```python
  def test_t234_catalog_is_exact() -> None:
      assert [item.preset_id for item in list_demo_presets()] == [
          "clean_periodic",
          "clipping",
          "harmonic_distortion",
          "combined_distortion",
          "noise_inconclusive",
      ]


  def test_t236_materialization_is_deterministic_but_ids_are_fresh() -> None:
      first = build_demo_preset("noise_inconclusive")
      second = build_demo_preset("noise_inconclusive")
      assert first.samples.tobytes() == second.samples.tobytes()
      assert first.meta.signal_id != second.meta.signal_id
      assert "noise" not in first.meta.signal_id
  ```

  Monkeypatch Tool service entry points and prove preview calls none. Inspect
  `_build_user_message` payload in Task 8 tests to prove no preset metadata
  reaches PlannerContext.

- [ ] **Step 2: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_presets_preview.py -q
  ```

- [ ] **Step 3: Implement the exact public preset catalog**

  Lock private generator parameters in one mapping:

  ```python
  _PRESET_BUILDERS: dict[DemoPresetId, Callable[[], SyntheticCase]] = {
      "clean_periodic": lambda: generate_sine(
          frequency_hz=220.0, sample_rate_hz=48_000,
          duration_s=1.0, amplitude=0.35,
      ),
      "clipping": lambda: generate_clipped_sine(
          frequency_hz=220.0, sample_rate_hz=48_000,
          duration_s=1.0, amplitude=1.2, clip_level=0.65,
      ),
      "harmonic_distortion": lambda: generate_harmonic_sine(
          fundamental_hz=220.0, harmonic_ratios={2: 0.12, 3: 0.04},
          sample_rate_hz=48_000, duration_s=1.0,
          fundamental_amplitude=0.5,
      ),
      "combined_distortion": lambda: generate_combined_distortion(
          fundamental_hz=220.0, harmonic_ratios={2: 0.12, 3: 0.04},
          clip_level=0.55, sample_rate_hz=48_000,
          duration_s=1.0, fundamental_amplitude=0.9,
      ),
      "noise_inconclusive": lambda: generate_white_noise(
          sample_rate_hz=48_000, duration_s=1.0, rms=0.1, seed=5001,
      ),
  }
  ```

  Return only `case.record`; never return or persist generator ground truth.

- [ ] **Step 4: Implement min/max envelope preview**

  Preserve original index order even when max precedes min in a bucket:

  ```python
  def _bucket_indices(values: np.ndarray) -> tuple[int, ...]:
      minimum = int(np.argmin(values))
      maximum = int(np.argmax(values))
      return (minimum,) if minimum == maximum else tuple(sorted((minimum, maximum)))
  ```

  Use `np.linspace(0, len(samples), bucket_count + 1, dtype=np.int64)` for
  integer edges, emit absolute sample indices, and create `WaveformPoint` with
  `time_s=index/sample_rate_hz`. Reject non-1D, empty, non-finite, invalid rate,
  and `max_points` outside 2–1,000.

- [ ] **Step 5: Run GREEN and architecture-focused checks**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_presets_preview.py tests/signal/test_synthetic.py -q
  & $Phase5Python -m ruff check --no-cache src/signal_diag/app tests/app
  ```

- [ ] **Step 6: Apply the review protocol and commit**

  Spec review checks T234–T238 and evaluation isolation. Quality review checks
  deterministic parameters, no truth leakage, extrema ordering, and the
  1,000-point bound. Then:

  ```powershell
  git add src/signal_diag/app tests/app/test_presets_preview.py
  git commit -m "feat(app): add public Demo presets and bounded preview"
  ```

---

### Task 6: Implement atomic RunStore and one-worker FIFO executor

**Files:**

- Create: `src/signal_diag/app/runs.py`
- Create: `tests/app/test_runs.py`

**Interfaces:**

- Produces private `InMemoryRunStore`, `RunWorkItem`, and
  `BoundedRunExecutor` used by Task 8.
- Store defaults: one running, four queued, twenty terminal; only
  queued→running→completed/failed; FIFO; terminal eviction calls injected
  Signal cleanup for that run only.

- [ ] **Step 1: Write T241–T245 RED concurrency tests**

  Use `asyncio.Event` barriers, not sleeps:

  ```python
  @pytest.mark.asyncio
  async def test_t241_one_active_and_fifo_four_queued() -> None:
      entered = asyncio.Event()
      release = asyncio.Event()
      order: list[str] = []

      async def first() -> RunExecutionResult:
          order.append("first")
          entered.set()
          await release.wait()
          return _successful_execution("run_" + "1" * 32)

      await executor.submit(_work("run_" + "1" * 32, first))
      await entered.wait()
      for digit in "2345":
          await executor.submit(_work("run_" + digit * 32, _instant_success))
      with pytest.raises(AppCapacityError):
          await executor.submit(_work("run_" + "6" * 32, _instant_success))
      release.set()
      await executor.wait_idle()
      assert order[0] == "first"
  ```

  Cover monotonic transitions, concurrent polling immutability, exact oldest
  terminal eviction, cleanup ownership, no active/queued eviction, lookup,
  independent stores, empty restart, idempotent close, queued failure on close,
  active completion awaited, and admission rejection after close.

- [ ] **Step 2: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_runs.py -q
  ```

- [ ] **Step 3: Implement immutable store updates**

  Keep mutable synchronization private and return model copies:

  ```python
  @dataclass(frozen=True, slots=True)
  class RunExecutionResult:
      result: AgentRunResult
      trace_events: tuple[TraceEventView, ...]


  @dataclass(frozen=True, slots=True)
  class RunWorkItem:
      run_id: str
      execute: Callable[[], Awaitable[RunExecutionResult]]


  class InMemoryRunStore:
      def __init__(self, *, terminal_limit: int = 20,
                   cleanup: Callable[[tuple[str, ...]], None]) -> None:
          self._snapshots: dict[str, AppRunSnapshot] = {}
          self._owned_signal_ids: dict[str, tuple[str, ...]] = {}
          self._terminal_order: deque[str] = deque()
          self._condition = asyncio.Condition()
  ```

  Test helpers construct work explicitly:

  ```python
  def _work(
      run_id: str,
      execute: Callable[[], Awaitable[RunExecutionResult]],
  ) -> RunWorkItem:
      return RunWorkItem(run_id=run_id, execute=execute)


  async def _instant_success() -> RunExecutionResult:
      return _successful_execution("run_" + "f" * 32)
  ```

  Every transition builds a validated `AppRunSnapshot`; never mutate nested
  state in place. `get()` returns `model_copy(deep=True)`.

- [ ] **Step 4: Implement bounded executor lifecycle**

  Use one `asyncio.Queue[RunWorkItem]` with `maxsize=4`, one worker task, and a
  sentinel owned only by `aclose`. Start the worker lazily on the first async
  `submit`, so `build_product_service()` and `create_app()` remain legal outside
  a running event loop. Reserve the store before enqueue; roll back reservation
  if enqueue fails. Worker order is:

  ```python
  await store.mark_running(item.run_id, started_at=clock())
  try:
      completed = await item.execute()
  except Exception as error:
      await store.mark_failed(
          item.run_id,
          finished_at=clock(),
          error=sanitize_application_error(error),
      )
  else:
      await store.mark_completed(
          item.run_id,
          finished_at=clock(),
          result=completed.result,
          trace_events=completed.trace_events,
      )
  ```

  Do not catch `BaseException`. On close, stop admission, drain queued work into
  sanitized failed snapshots, let the active coroutine finish, join the worker,
  and make repeated close a no-op.

  Define the exception conversion in `errors.py`: return `error.detail` for an
  `ApplicationError`; otherwise return `AppErrorDetail(code="internal_error",
  message="diagnosis execution failed")`. Never serialize `str(error)` for an
  unexpected exception.

- [ ] **Step 5: Run GREEN and race repetition**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_runs.py -q
  1..10 | ForEach-Object {
    & $Phase5Python -m pytest tests/app/test_runs.py -q
    if ($LASTEXITCODE -ne 0) { throw "run-store repetition failed" }
  }
  ```

- [ ] **Step 6: Apply the review protocol and commit**

  Spec review checks T241–T245. Quality review checks atomic capacity,
  condition notification, cleanup isolation, no sleep-based tests, exception
  sanitization, and idempotent shutdown. Then:

  ```powershell
  git add src/signal_diag/app/runs.py tests/app/test_runs.py
  git commit -m "feat(app): add bounded local diagnosis execution"
  ```

---

### Task 7: Build strict reports and immutable evaluation presentation data

**Files:**

- Create: `src/signal_diag/app/reporting.py`
- Create: `src/signal_diag/evaluation/assets/__init__.py`
- Create: `src/signal_diag/evaluation/assets/phase4_3_1_official_summary.json`
- Create: `scripts/build_phase5_evaluation_summary.py`
- Create: `tests/app/test_reporting.py`
- Modify: `src/signal_diag/app/__init__.py`

**Interfaces:**

- Produces `project_agent_events`, `build_diagnosis_report`,
  `render_report_json`, `render_report_html`, and
  `load_accepted_evaluation_summary`.
- Consumes Task 2 `assemble_agent_events` output and Task 4 frozen models.
- Evaluation assets contain data only; `signal_diag.evaluation` never imports
  `signal_diag.app`.

- [ ] **Step 1: Write T256–T263 and T279 RED tests**

  Build a completed `AppRunSnapshot` from the existing full Agent chain. Prove
  event projection is compact, every claim ref resolves, JSON is stable, HTML
  escapes all external text, and changing preview cannot change the nested
  Agent result:

  ```python
  def test_t259_json_is_canonical_and_round_trips() -> None:
      report = _report()
      first = render_report_json(report)
      second = render_report_json(report)
      assert first == second
      assert first.endswith("\n")
      assert DiagnosisReport.model_validate_json(first) == report


  def test_t260_html_escapes_external_text() -> None:
      report = _report(filename='<img src=x onerror="alert(1)">')
      html = render_report_html(report)
      assert "<img" not in html
      assert "&lt;img" in html
      assert "<script" not in html.casefold()
      assert "http://" not in html and "https://" not in html
  ```

  Parameterize unknown Evidence, Rule, and Knowledge refs. Scan JSON/HTML for
  API-key patterns, authorization, traceback, ndarray/full waveform/full FFT,
  and raw provider keys. Validate the packaged summary against the five hashes
  in the accepted official `checksums.sha256`, exact identities, 80 slots,
  2 behavioral-failure slots, 1 outcome error, and wheel-independent resource
  loading.

- [ ] **Step 2: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_reporting.py -q
  ```

- [ ] **Step 3: Implement compact trace projection**

  Match event discriminators and preserve order; do not serialize full context:

  ```python
  def project_agent_events(
      events: tuple[EvaluationEvent, ...],
  ) -> tuple[TraceEventView, ...]:
      projected: list[TraceEventView] = []
      for event in events:
          if isinstance(event, PlannerDecisionEvent):
              record = event.record
              action = (
                  record.decision.decision_type
                  if record.decision is not None
                  else record.status
              )
              refs: tuple[str, ...] = ()
              kind = "planner"
              purpose = getattr(record.decision, "purpose", None)
              status = record.status
              usage = record.provider_usage
              latency = record.latency_ms
          elif isinstance(event, ObservationEvent):
              action = event.observation.tool_name
              refs = event.observation.evidence_refs
              kind, purpose, status, usage, latency = (
                  "observation", event.observation.purpose,
                  event.observation.status, None, None,
              )
          elif isinstance(event, RuleEvaluationEvent):
              action = event.batch.profile_id
              refs = tuple(item.evaluation_id for item in event.batch.evaluations)
              kind, purpose, status, usage, latency = (
                  "rule", None, "completed", None, None,
              )
          else:
              action = "retrieve_knowledge"
              refs = (event.retrieval.retrieval_id,)
              kind, purpose, status, usage, latency = (
                  "knowledge", None, "completed", None, None,
              )
          projected.append(TraceEventView(
              event_index=event.event_index, kind=kind, action_name=action,
              status=status, purpose=purpose, reference_ids=refs,
              latency_ms=latency, provider_usage=usage,
          ))
      return tuple(projected)
  ```

  Use explicit branches for all four event classes so mypy can prove the
  attributes; the compact assignment above is the required field mapping.

- [ ] **Step 4: Implement report integrity and canonical rendering**

  Before constructing `DiagnosisReport`, collect exact same-result IDs:

  ```python
  evidence_ids = {item.evidence_id for item in result.evidence}
  rule_ids = {
      item.evaluation_id
      for batch in result.rule_evaluation_batches
      for item in batch.evaluations
  }
  knowledge_ids = {
      item.retrieval_id for item in result.knowledge_retrievals
  }
  for claim in result.diagnosis.claims if result.diagnosis else ():
      if not set(claim.evidence_refs) <= evidence_ids:
          raise TraceIntegrityError(_trace_error("unknown Evidence reference"))
      if not set(claim.rule_refs) <= rule_ids:
          raise TraceIntegrityError(_trace_error("unknown Rule reference"))
      if not set(claim.knowledge_refs) <= knowledge_ids:
          raise TraceIntegrityError(_trace_error("unknown Knowledge reference"))
  ```

  `_trace_error(message)` returns
  `AppErrorDetail(code="trace_integrity_error", message=message)` and never
  includes a payload value or stack trace.

  Serialize with `json.dumps(..., ensure_ascii=False, allow_nan=False,
  sort_keys=True, separators=(",", ":")) + "\n"`. Render HTML through
  `html.escape` from only `DiagnosisReport.model_dump(mode="json")`, embed CSS,
  add stable `id` anchors, and include no script/CDN.

- [ ] **Step 5: Generate and validate the accepted evaluation summary**

  The script reads only the canonical bundle, parses manifest/metrics/report,
  hashes the five data files, counts Agent failures from `runs.jsonl`, validates
  `AcceptedEvaluationSummary`, and writes sorted UTF-8 JSON. Its fixed source is:

  ```python
  SOURCE = Path(
      "docs/evaluations/phase4_3_1/official/"
      "bench_official_s1_v12_planner8_1_gate5"
  )
  DESTINATION = Path(
      "src/signal_diag/evaluation/assets/phase4_3_1_official_summary.json"
  )
  ```

  Run once, then make the test rebuild in a temporary directory and compare
  exact bytes with the committed asset:

  ```powershell
  & $Phase5Python scripts/build_phase5_evaluation_summary.py
  & $Phase5Python -m pytest tests/app/test_reporting.py -q
  ```

- [ ] **Step 6: Run historical evaluation regressions**

  ```powershell
  & $Phase5Python -m pytest tests/evaluation/test_recording.py tests/evaluation/test_reporting.py tests/evaluation/test_acceptance.py tests/app/test_reporting.py -q
  ```

- [ ] **Step 7: Apply the review protocol and commit**

  Spec review checks T256–T263/T279 and exact disclosed failures. Quality review
  checks escaping, stable bytes, package ownership, no rescore, and no
  evaluation→app import. Then:

  ```powershell
  git add src/signal_diag/app src/signal_diag/evaluation/assets scripts/build_phase5_evaluation_summary.py tests/app/test_reporting.py
  git commit -m "feat(app): add traceable reports and evaluation summary"
  ```

---

### Task 8: Implement the shared application service and product composition

**Files:**

- Create: `src/signal_diag/app/service.py`
- Create: `src/signal_diag/app/composition.py`
- Modify: `src/signal_diag/app/__init__.py`
- Create: `tests/app/test_service.py`

**Interfaces:**

- Produces exact §59 `PlannerFactory`, `DiagnosisApplicationService`, and
  `build_product_service`.
- Consumes Tasks 2–7 and accepted Signal/DSP/Tools/Rules/Knowledge/Runtime.
- Every execution creates fresh `RealLLMPlanner` or injected planner,
  `RecordingPlanner`, and `DistortionDiagnosisRuntime`.

- [ ] **Step 1: Write T246–T252 RED tests**

  Use explicit fake planner factories with real Runtime lower layers. Cover WAV
  and all presets, left/right/mixdown samples, mono-right rejection, 2,000-char
  request, no truth/raw data leakage, fresh per-run objects, missing credentials
  before repository insertion/reservation, reference resolution, and no
  ScriptedPlanner product fallback.

  Capture outbound PlannerContext with a fake transport through
  `RealLLMPlanner` and require:

  ```python
  serialized = _build_user_message(received_context, prompt_version=PROMPT_VERSION)
  forbidden = (
      "preset_id", "combined_distortion", "fault_labels", "ground_truth",
      "acceptable_first_tools", "target_status", "samples", "waveform",
  )
  assert all(item not in serialized for item in forbidden)
  ```

  For representative WAV clipping and synthetic noise, require same-run
  Evidence/rule/knowledge references and terminal application snapshots.

- [ ] **Step 2: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_service.py -q
  ```

- [ ] **Step 3: Define private composition dependencies**

  Keep HTTP and environment logic out of the service:

  ```python
  @dataclass(frozen=True, slots=True)
  class ApplicationDependencies:
      repository: SignalRepository
      planner_factory: PlannerFactory
      planner_identity: PlannerIdentity
      planner_configured: bool
      rule_engine: RuleEngine
      rule_profile_loader: RuleProfileLoader
      knowledge_index: KnowledgeIndex
  ```

  `DiagnosisApplicationService` receives this bundle plus clock/store/executor.
  Tests construct it explicitly; product construction lives only in
  `composition.py`.

- [ ] **Step 4: Implement one transactional source-registration path**

  Both public submissions produce a `(SignalRecord, SourceSummary)` pair and
  call one private registration method. The critical ordering is:

  ```python
  if not self._dependencies.planner_configured:
      raise PlannerNotConfiguredError(_planner_not_configured_detail())
  question = _normalize_question(user_request)
  source_record, source_summary = source_builder()
  selected = extract_segment(source_record, channel=channel)
  analysis_record = build_signal_record(
      selected,
      sample_rate_hz=source_record.meta.sample_rate_hz,
      source_type=source_record.meta.source_type,
      filename=source_record.meta.filename,
  )
  preview = build_waveform_preview(
      selected, sample_rate_hz=analysis_record.meta.sample_rate_hz
  )
  ```

  Insert source and analysis records immediately before atomic reservation. If
  reservation/enqueue fails, remove both IDs. Never persist synthetic ground
  truth. The factual suffix is exactly `Analyzed channel: {channel}.`.

- [ ] **Step 5: Implement fresh Runtime execution**

  The queued closure creates all run-scoped objects and strict trace:

  ```python
  async def execute() -> RunExecutionResult:
      inner = self._dependencies.planner_factory()
      recorder = RecordingPlanner(inner)
      runtime = DistortionDiagnosisRuntime(
          repository=self._dependencies.repository,
          tool_service=SignalToolService(self._dependencies.repository),
          planner=recorder,
          rule_engine=self._dependencies.rule_engine,
          rule_profile_loader=self._dependencies.rule_profile_loader,
          knowledge_index=self._dependencies.knowledge_index,
      )
      result = await runtime.run(
          signal_id=analysis_record.meta.signal_id,
          user_request=f"{question}\nAnalyzed channel: {channel}.",
      )
      events = assemble_agent_events(recorder.records, result)
      return RunExecutionResult(
          result=result,
          trace_events=project_agent_events(events),
      )
  ```

  Do not compare the app run ID with `result.run_id`; validate refs within the
  nested Agent result.

- [ ] **Step 6: Implement product composition without eager Web imports**

  Resolve environment from the provided mapping only. Default identity is
  DeepSeek / `deepseek-v4-flash` / `v0.2-s1-planner-8.1`. The factory is:

  ```python
  def planner_factory() -> PlannerModel:
      return RealLLMPlanner(
          provider="deepseek",
          api_key=api_key,
          base_url=base_url,
          model=model,
      )
  ```

  Build repository, RuleEngine, YAML loader for the packaged
  `profiles/s1_distortion_v1.yaml`, and KnowledgeIndex for packaged corpus.
  Record `phase4_certified_default` only when actual model and prompt equal the
  accepted defaults. Missing key sets `planner_configured=False`; no scripted
  object is constructed.

- [ ] **Step 7: Run GREEN and complete S1 service paths**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_service.py tests/agent/test_phase3_s1_acceptance.py -q
  & $Phase5Python -m mypy --no-incremental src/signal_diag/app
  ```

- [ ] **Step 8: Apply the review protocol and commit**

  Spec review maps T246–T252. Quality review checks transaction cleanup,
  per-run object isolation, environment handling, app/Agent ID separation, and
  no controller-forced action. Then:

  ```powershell
  git add src/signal_diag/app tests/app/test_service.py
  git commit -m "feat(app): add shared diagnosis application service"
  ```

---

### Task 9: Add bounded FastAPI and polling endpoints

**Files:**

- Create: `src/signal_diag/app/multipart.py`
- Create: `src/signal_diag/app/api.py`
- Create: `tests/app/test_api.py`
- Modify: `pyproject.toml`

**Interfaces:**

- Produces exact §62 routes and `create_app(service=None) -> FastAPI`.
- Adds optional `app` dependencies: FastAPI, Uvicorn, python-multipart; adds
  httpx to `dev`. Core imports remain usable without them.
- Multipart file bytes stay in a bounded `bytearray` and never use UploadFile,
  `request.form()`, a spool, or a temporary file.

- [ ] **Step 1: Add optional test/runtime dependencies**

  Modify only dependency metadata:

  ```toml
  app = [
    "fastapi>=0.115,<1",
    "uvicorn>=0.30,<1",
    "python-multipart>=0.0.9,<1",
  ]
  dev = [
    "build>=1.2",
    "httpx>=0.27,<1",
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
    "mypy>=1.10",
    "types-PyYAML>=6.0.12",
  ]
  ```

  Install the project extras into the approved Phase 5 execution environment
  only after the user permits dependency installation:

  ```powershell
  & $Phase5Python -m pip install -e '.[app,llm,dev]'
  ```

- [ ] **Step 2: Write T264–T270 RED API tests**

  Use `httpx.AsyncClient` with `ASGITransport`. Test health/presets/evaluation
  without credentials, 202 submission, monotonic polling, both reports,
  normalized errors/status/content types, CORS absence, CSP, safe download
  names, simultaneous GET immutability, capacity, and shutdown.

  Patch `tempfile.SpooledTemporaryFile`, `tempfile.NamedTemporaryFile`, and
  `builtins.open` to fail during upload. Send a body whose file portion crosses
  20 MiB by one byte in chunks and require 413 before service invocation.

- [ ] **Step 3: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_api.py -q
  ```

- [ ] **Step 4: Implement bounded streaming multipart callbacks**

  Parse `Content-Type` boundary, feed each `Request.stream()` chunk to
  `multipart.MultipartParser`, and enforce the total request/file bound in
  `on_part_data` before extending the file buffer:

  ```python
  def on_part_data(data: bytes, start: int, end: int) -> None:
      piece = data[start:end]
      if state.is_file and len(state.file_bytes) + len(piece) > max_file_bytes:
          raise PayloadTooLargeError(_payload_too_large_detail())
      target = state.file_bytes if state.is_file else state.field_bytes
      target.extend(piece)
  ```

  `_payload_too_large_detail()` returns the fixed safe detail
  `AppErrorDetail(code="payload_too_large", message="WAV upload exceeds 20 MiB")`.

  Accept exactly one `file`, one `user_request`, and one `channel`; reject
  duplicates, unknown fields, missing disposition/boundary, invalid UTF-8, and
  malformed termination. Bound non-file field bytes to 8 KiB each and total
  request bytes to `max_file_bytes + 64 KiB`.

- [ ] **Step 5: Implement FastAPI routes and common error mapping**

  Use a lifespan that owns/closes the default service. Exception handlers return
  `AppErrorEnvelope.model_dump(mode="json")`. Required mapping is:

  ```python
  _STATUS_BY_CODE = {
      "invalid_request": 422,
      "invalid_wav": 422,
      "signal_limit_exceeded": 422,
      "unknown_preset": 422,
      "payload_too_large": 413,
      "unsupported_wav": 415,
      "run_not_found": 404,
      "run_not_terminal": 409,
      "report_unavailable": 409,
      "capacity_exceeded": 429,
      "planner_not_configured": 503,
      "trace_integrity_error": 500,
      "internal_error": 500,
  }
  ```

  Provider/runtime errors after 202 remain in terminal snapshots. Never map
  them retroactively to the submission response.

- [ ] **Step 6: Add report responses and security headers**

  Use opaque run ID filenames only:

  ```python
  headers = {
      "Content-Disposition": f'attachment; filename="{run_id}.report.json"',
      "Content-Security-Policy": "default-src 'self'; object-src 'none'; base-uri 'none'",
  }
  ```

  Do not install CORS middleware. Keep FastAPI imports confined to `api.py` and
  `multipart.py`.

- [ ] **Step 7: Run GREEN**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_api.py tests/app/test_service.py -q
  & $Phase5Python -m ruff check --no-cache src/signal_diag/app tests/app
  ```

- [ ] **Step 8: Apply the review protocol and commit**

  Spec review maps T264–T270 except root/static details completed in Task 11.
  Quality review checks no spool path, bounded callbacks, lifespan, safe
  errors, no secret/base-URL response, and optional imports. Then:

  ```powershell
  git add pyproject.toml src/signal_diag/app tests/app/test_api.py
  git commit -m "feat(app): add bounded FastAPI diagnosis API"
  ```

---

### Task 10: Add the direct-service argparse CLI

**Files:**

- Create: `src/signal_diag/app/cli.py`
- Create: `tests/app/test_cli.py`

**Interfaces:**

- Produces `signal-diag serve`, `presets`, `diagnose wav`, and
  `diagnose synthetic` grammar from §63.
- Calls the shared service directly; only `serve` imports Uvicorn/FastAPI.

- [ ] **Step 1: Write T271–T275 RED tests**

  Invoke `main()` with a captured stdout/stderr and injected service factory.
  Require exact defaults, options, exit codes, JSON/HTML identity, bounded WAV
  read, no HTTP client, no scripted-planner switch, and `127.0.0.1` serve
  default:

  ```python
  def test_t271_parser_defaults() -> None:
      args = build_parser().parse_args(["diagnose", "synthetic", "clipping"])
      assert args.question == "Why does this signal sound distorted?"
      assert args.channel == "mixdown"
      assert args.output == "text"
      assert args.html_output is None
  ```

  Map valid supported/no-fault/inconclusive to 0, Agent/application failure to
  1, and usage/input/configuration errors to 2. A completed Agent result with
  nested `status="error"` exits 1 while retaining honest output.

- [ ] **Step 2: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_cli.py -q
  ```

- [ ] **Step 3: Implement parser and bounded local file read**

  Build subparsers exactly once. Read at most limit+1 bytes:

  ```python
  def _read_wav_path(path: Path, max_bytes: int) -> bytes:
      with path.open("rb") as stream:
          data = stream.read(max_bytes + 1)
      if len(data) > max_bytes:
          raise ApplicationError(AppErrorDetail(
              code="payload_too_large",
              message=f"WAV exceeds {max_bytes} bytes",
          ))
      return data
  ```

  Do not use `Path.read_bytes()` because it is not bounded.

- [ ] **Step 4: Implement async diagnose dispatch through the service**

  One coroutine submits, waits, and builds the report:

  ```python
  submission = await (
      service.submit_wav(
          wav_bytes, filename=path.name,
          user_request=args.question, channel=args.channel,
      )
      if args.source_kind == "wav"
      else service.submit_synthetic(
          args.preset_id,
          user_request=args.question, channel=args.channel,
      )
  )
  snapshot = await service.wait_for_terminal(submission.run_id)
  if snapshot.status == "completed":
      report = build_diagnosis_report(
          snapshot, generated_at=datetime.now(UTC)
      )
  ```

  Text output prints outcome, confidence, termination, claims, and references.
  JSON uses `render_report_json`; `--html-output` writes
  `render_report_html(report)` as UTF-8 only to the explicit user path. Always
  `await service.aclose()` in `finally`.

- [ ] **Step 5: Implement serve lazily**

  Print the local/no-auth warning and call:

  ```python
  uvicorn.run(
      create_app(),
      host=args.host,
      port=args.port,
      log_level="info",
  )
  ```

  Default host is `127.0.0.1`; explicit host/port remain user-controlled.

- [ ] **Step 6: Run GREEN**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_cli.py tests/app/test_service.py -q
  ```

- [ ] **Step 7: Apply the review protocol and commit**

  Spec review maps T271–T275. Quality review checks direct service use, bounded
  file reads, exit semantics, lazy optional imports, safe stdout/stderr, and
  service close. Then:

  ```powershell
  git add src/signal_diag/app/cli.py tests/app/test_cli.py
  git commit -m "feat(app): add direct-service diagnosis CLI"
  ```

---

### Task 11: Add the packaged native Web UI

**Files:**

- Create: `src/signal_diag/app/static/index.html`
- Create: `src/signal_diag/app/static/styles.css`
- Create: `src/signal_diag/app/static/app.js`
- Modify: `src/signal_diag/app/api.py`
- Create: `tests/app/test_ui.py`
- Modify: `tests/app/test_api.py`

**Interfaces:**

- Completes root/static T264 and T276–T280.
- Uses only same-origin `/api/v1` calls and safe DOM creation; no client-side
  diagnostic logic.

- [ ] **Step 1: Write T276–T280 RED static/security tests**

  Require packaged filenames, root content, no CDN/framework/analytics/credential
  field/`innerHTML`/`insertAdjacentHTML`/`document.write`, and all required UI
  sections. Assert API integration renders external strings through
  `textContent` and `createTextNode` only.

  ```python
  def test_t278_external_text_never_uses_html_sinks() -> None:
      script = _static_text("app.js")
      forbidden = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write")
      assert all(token not in script for token in forbidden)
      assert "textContent" in script
  ```

  Validate the Evaluation copy contains `completed/meets_target`, `80`, `2/80`,
  `1/80`, and demonstration-target wording after loading the actual summary.

- [ ] **Step 2: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_ui.py tests/app/test_api.py -q
  ```

- [ ] **Step 3: Build semantic no-build HTML and accessible controls**

  Include exact stable section IDs:

  ```html
  <main>
    <section id="input-panel" aria-labelledby="input-heading"></section>
    <section id="lifecycle-panel" aria-live="polite"></section>
    <section id="diagnosis-panel"></section>
    <section id="waveform-panel"></section>
    <section id="trace-panel"></section>
    <section id="evidence-panel"></section>
    <section id="rules-panel"></section>
    <section id="knowledge-panel"></section>
    <section id="evaluation-panel"></section>
  </main>
  ```

  Add WAV/preset mode, question, legal channel, submit, report downloads, local
  no-auth warning, and demonstration-threshold labels. Use no inline event
  handlers.

- [ ] **Step 4: Implement safe polling and rendering**

  Use one element helper and actual lifecycle only:

  ```javascript
  function appendText(parent, tagName, value, className = "") {
    const element = document.createElement(tagName);
    element.textContent = String(value ?? "");
    if (className) element.className = className;
    parent.appendChild(element);
    return element;
  }

  async function pollRun(runId) {
    for (;;) {
      const snapshot = await apiJson(`/api/v1/runs/${encodeURIComponent(runId)}`);
      renderLifecycle(snapshot.status);
      if (snapshot.status === "completed" || snapshot.status === "failed") {
        renderTerminal(snapshot);
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
  }
  ```

  While queued/running, show only those words and elapsed neutral status; never
  name a Tool. Draw preview with SVG elements created through `createElementNS`
  from server-provided points; do not derive diagnostic values in JavaScript.

- [ ] **Step 5: Serve package resources safely**

  Resolve static assets with `importlib.resources.files("signal_diag.app.static")`
  and a fixed filename allowlist. Root returns `index.html`; `/static/styles.css`
  and `/static/app.js` return exact media types and CSP. Reject every path
  containing separators or dot segments.

- [ ] **Step 6: Run GREEN**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_ui.py tests/app/test_api.py -q
  ```

- [ ] **Step 7: Apply the review protocol and commit**

  Spec review maps T276–T280 and verifies complete fields. Quality review checks
  safe DOM, keyboard labels, polling termination, no fake progress, no
  diagnostic JS, responsive CSS, and asset traversal. Then:

  ```powershell
  git add src/signal_diag/app/static src/signal_diag/app/api.py tests/app/test_ui.py tests/app/test_api.py
  git commit -m "feat(app): add native distortion diagnosis Web UI"
  ```

---

### Task 12: Complete packaging, architecture guards, CI, and product docs

**Files:**

- Modify: `pyproject.toml`
- Create: `scripts/smoke_installed_phase5.py`
- Create: `scripts/create_phase5_demo_wav.py`
- Create: `scripts/verify_phase5_wheel.py`
- Create: `tests/app/test_packaging.py`
- Modify: `tests/test_architecture_boundaries.py`
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`

**Interfaces:**

- Completes T281–T284 and prepares T285.
- Wheel includes profiles, corpus, evaluation manifests/summary, and Web static
  assets. Core install does not require FastAPI.

- [ ] **Step 1: Write T281–T283 RED package and boundary tests**

  Parse `pyproject.toml` and require exact console/extra/package-data entries:

  ```toml
  [project.scripts]
  signal-diag = "signal_diag.app.cli:main"

  [tool.setuptools.package-data]
  "signal_diag.app" = ["static/*.html", "static/*.css", "static/*.js"]
  "signal_diag.evaluation" = ["manifests/*.yaml", "assets/*.json"]
  "signal_diag.knowledge" = ["corpus/*.md"]
  "signal_diag.rules" = ["profiles/*.yaml"]
  ```

  Extend AST guards so Signal/DSP/Tools/Rules/Knowledge/Agent never import app;
  `signal.wav` imports no app/evaluation/Agent/LLM/FastAPI; evaluation assets
  import no app; API/CLI/static contain no DSP/rule/diagnosis implementation.

- [ ] **Step 2: Write installed-wheel RED smoke**

  `scripts/smoke_installed_phase5.py` must run outside the source tree and:

  ```python
  from signal_diag.app import build_product_service, list_demo_presets
  from signal_diag.app.reporting import load_accepted_evaluation_summary
  from signal_diag.signal import load_wav_bytes

  assert len(list_demo_presets()) == 5
  assert load_accepted_evaluation_summary().agent_slot_count == 80
  service = build_product_service(environ={})
  assert service.list_presets()
  ```

  The smoke exits without submitting a model run and closes the service.

  Add a deterministic WAV generator that writes a one-second 48 kHz mono
  16-bit PCM clipping preset without normalization:

  ```python
  def build_demo_wav_bytes() -> bytes:
      case = generate_clipped_sine(
          frequency_hz=220.0, sample_rate_hz=48_000,
          duration_s=1.0, amplitude=1.2, clip_level=0.65,
      )
      pcm = np.rint(
          np.clip(case.record.samples[:, 0], -1.0, 32767 / 32768) * 32768
      ).astype("<i2")
      output = io.BytesIO()
      with wave.open(output, "wb") as stream:
          stream.setnchannels(1)
          stream.setsampwidth(2)
          stream.setframerate(48_000)
          stream.writeframes(pcm.tobytes())
      return output.getvalue()
  ```

  The script writes only to its explicit CLI output path. A packaging test
  loads the bytes through `load_wav_bytes` and verifies the exact sample count,
  rate, depth, and deterministic SHA-256.

- [ ] **Step 3: Run RED**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_packaging.py tests/test_architecture_boundaries.py -q
  ```

- [ ] **Step 4: Finalize metadata and build clean distribution artifacts**

  Keep `llm` as the existing OpenAI-client extra, add `app`, retain `dev`, add
  the console entry, and package all assets. Implement
  `scripts/verify_phase5_wheel.py` with only the standard library plus the
  configured Python executable. It must:

  1. resolve the repository root and create one fresh system-Temp root;
  2. copy the source tree while excluding `.git`, `build`, `.pytest_cache`,
     `__pycache__`, `.mypy_cache`, `.ruff_cache`, virtual environments, and
     bytecode;
  3. build both sdist and wheel inside the copied tree;
  4. create a fresh venv, install the wheel path with its `[app,llm]` extras,
     and run `smoke_installed_phase5.py` with the working directory outside
     both source trees;
  5. inspect the wheel ZIP for every static, profile, corpus, manifest, and
     accepted-evaluation-summary asset;
  6. emit artifact names and lowercase SHA-256 hashes; and
  7. delete only resolved child paths beneath its own Temp root in a `finally`
     block.

  It must never read, write, delete, or use the repository's pre-existing
  `build/`. Run the same cross-platform gate locally and in CI:

  ```powershell
  & $Phase5Python scripts/verify_phase5_wheel.py
  ```

- [ ] **Step 5: Add secret-free Python 3.11/3.12 CI**

  The workflow checks out, sets up matrix Python, installs
  `.[app,llm,dev]`, and runs:

  ```yaml
  - run: python -m pytest -q -rxXs -p no:cacheprovider
  - run: python -m ruff check --no-cache src tests scripts
  - run: python -m mypy --no-incremental src
  - run: python scripts/verify_phase5_wheel.py
  ```

  No provider secret, real-model command, skip allowance, Docker service, or
  network model call appears.

- [ ] **Step 6: Write truthful root documentation**

  `README.md` must contain: S1 scope; architecture; Python 3.11/3.12 install;
  `.[app,llm]`; local `DEEPSEEK_API_KEY`; `signal-diag serve`; CLI examples;
  supported WAV table/limits; actual dynamic trace; JSON/HTML; accepted Phase
  4.3.1 metrics and 2/80 plus 1/80 disclosure; deterministic versus real Demo
  gates; no-auth localhost warning; Demo thresholds disclaimer; limitations;
  and resume bullets that do not claim production/chip validation.

  Before Task 14, document the future artifact directory as plain text rather
  than broken Markdown links. Add clickable screenshot/report links only after
  those files legally exist; do not fabricate files.

- [ ] **Step 7: Run GREEN, wheel smoke, and architecture**

  ```powershell
  & $Phase5Python -m pytest tests/app/test_packaging.py tests/test_architecture_boundaries.py -q
  & $Phase5Python -m ruff check --no-cache src tests scripts
  & $Phase5Python -m mypy --no-incremental src
  ```

  Then execute `& $Phase5Python scripts/verify_phase5_wheel.py` and retain its
  artifact-name/hash output as evidence.

- [ ] **Step 8: Apply the review protocol and commit**

  Spec review maps T281–T284. Quality review inspects wheel contents, fresh
  install, CI secret absence, dependency direction, and every README claim.
  Then:

  ```powershell
  git add pyproject.toml scripts/smoke_installed_phase5.py scripts/verify_phase5_wheel.py scripts/create_phase5_demo_wav.py tests/app/test_packaging.py tests/test_architecture_boundaries.py .github/workflows/ci.yml README.md docs/README.md AGENTS.md
  git commit -m "build: package and verify Phase 5 application"
  ```

---

### Task 13: Enforce T285 and obtain deterministic presentation acceptance

**Files:**

- Modify: `tests/test_architecture_boundaries.py`
- Modify after local evidence: `AGENTS.md`, `docs/README.md`, and this plan
- Do not modify product behavior, frozen contracts, or historical assets

**Interfaces:**

- Consumes Tasks 2–12 and all T001–T284.
- Produces either `presentation_harness_accepted` after both CI matrix jobs pass,
  or the exact honest pending state that blocks Task 14.

- [ ] **Step 1: Write the T285 cumulative guard**

  Add one test that names every Phase 5 checkpoint file and freezes forbidden
  historical paths/hashes. It must prove no required test marker is skip/xfail,
  no RealLLMPlanner network path is called from required tests, and the committed
  workflow has Python `3.11` and `3.12`.

  ```python
  def test_t285_phase5_cumulative_contract_is_registered() -> None:
      test_plan = (REPO_ROOT / "docs" / "TEST_PLAN_V0_2.md").read_text("utf-8")
      for number in range(224, 286):
          assert f"| T{number} |" in test_plan
      assert "presentation_harness_accepted" in test_plan
      assert "real_demo_completed" in test_plan
  ```

- [ ] **Step 2: Run focused architecture and Phase 5 suites**

  ```powershell
  & $Phase5Python -m pytest tests/signal/test_wav.py tests/app tests/evaluation/test_recording.py tests/test_architecture_boundaries.py -q -rxXs -p no:cacheprovider
  ```

  Expected: zero failed, skipped, or xfailed tests.

- [ ] **Step 3: Run the complete local deterministic gate**

  ```powershell
  $Phase5Temp = Join-Path $env:TEMP ('signal-diag-phase5-pytest-' + [guid]::NewGuid().ToString('N'))
  & $Phase5Python -m pytest -q -rxXs -p no:cacheprovider --basetemp $Phase5Temp
  & $Phase5Python -m ruff check --no-cache src tests scripts
  & $Phase5Python -m mypy --no-incremental src
  git diff --check 36ae7c9..HEAD
  ```

  Delete only `$Phase5Temp` after resolving and verifying it is under the
  system Temp directory. Required result: T001–T285, zero skip/xfail, Ruff,
  mypy, architecture, and diff-check green.

- [ ] **Step 4: Repeat build and clean-install smoke from Task 12**

  Run `& $Phase5Python scripts/verify_phase5_wheel.py`. Require a fresh
  system-Temp source copy and venv, both sdist and wheel, installation from the
  built wheel rather than the checkout, a working directory outside the
  repository, the installed smoke, complete package-data inspection, and
  reported artifact hashes.

- [ ] **Step 5: Record local readiness without inventing CI success**

  If local gates pass, update status to exactly:

  ```text
  Phase 5 deterministic implementation locally green; Python 3.11/3.12 hosted
  CI pending; presentation_harness_accepted not yet granted; real Demo gated.
  ```

  Apply the review protocol and commit only status/test changes:

  ```powershell
  git add tests/test_architecture_boundaries.py AGENTS.md docs/README.md docs/superpowers/plans/2026-08-31-phase5-presentation-engineering.md
  git commit -m "test(app): enforce Phase 5 deterministic gate"
  ```

- [ ] **Step 6: Stop for explicit push/CI authorization**

  This plan does not authorize push. Return the local evidence to the user.
  Only after the user separately authorizes a push/PR or another accepted hosted
  CI trigger may both Python jobs run. Inspect their complete logs; do not rerun
  a failed job without diagnosing and fixing the deterministic cause through
  the review protocol.

- [ ] **Step 7: Record deterministic acceptance only after hosted CI passes**

  When both Python 3.11/3.12 jobs, wheel smoke, and all local gates are current
  and green, record `presentation_harness_accepted` in AGENTS/README/this plan
  and commit locally. If CI is unavailable or fails, retain the pending state
  and do not start Task 14.

---

### Task 14: Run exactly two real-model product Demo paths

**Files:**

- Create after deterministic acceptance:
  `docs/demo/phase5/v0_2_acceptance/input_clipping_16bit.wav`
- Create after actual runs:
  `docs/demo/phase5/v0_2_acceptance/synthetic_report.json`
- Create after actual runs:
  `docs/demo/phase5/v0_2_acceptance/synthetic_report.html`
- Create after actual runs:
  `docs/demo/phase5/v0_2_acceptance/wav_report.json`
- Create after actual runs:
  `docs/demo/phase5/v0_2_acceptance/wav_report.html`
- Create after actual UI display:
  `docs/demo/phase5/v0_2_acceptance/ui_completed.png`
- Create: `docs/demo/phase5/v0_2_acceptance/README.md`
- Modify: `README.md`, `AGENTS.md`, `docs/README.md`, and this plan

**Interfaces:**

- Consumes `presentation_harness_accepted`, public `RealLLMPlanner`, public
  preset `clipping`, supported deterministic WAV bytes, same application
  service, API/UI/CLI, and valid JSON/HTML renderers.
- Produces P5-R001–P5-R003 evidence and either `real_demo_completed` or an honest
  pending/failed state. It never changes prompt, model, Runtime, dataset,
  targets, or product code after seeing results.

- [ ] **Step 1: Prove legal preconditions and credentials**

  Require clean committed deterministic tree, accepted hosted CI, no existing
  artifact directory, and locally configured `DEEPSEEK_API_KEY` without
  printing its value:

  ```powershell
  if (-not $env:DEEPSEEK_API_KEY) { Write-Output 'real_demo_pending'; exit 2 }
  if (Test-Path 'docs/demo/phase5/v0_2_acceptance') {
    throw 'Phase 5 real Demo artifact directory already exists'
  }
  ```

  Missing credentials are not a deterministic failure; stop with
  `real_demo_pending`. A pre-existing artifact directory blocks execution so
  no previous result can be overwritten or mistaken for this two-run gate.

- [ ] **Step 2: Generate and validate the public WAV input**

  ```powershell
  New-Item -ItemType Directory -Path 'docs/demo/phase5/v0_2_acceptance'
  & $Phase5Python scripts/create_phase5_demo_wav.py --output 'docs/demo/phase5/v0_2_acceptance/input_clipping_16bit.wav'
  & $Phase5Python -c "from pathlib import Path; from signal_diag.signal import load_wav_bytes; x=load_wav_bytes(Path('docs/demo/phase5/v0_2_acceptance/input_clipping_16bit.wav').read_bytes(), filename='input_clipping_16bit.wav'); print(x.source_info.model_dump_json())"
  ```

  The printed metadata must be 48,000 Hz, mono, 16-bit, 48,000 frames, one
  second. Do not print waveform samples.

- [ ] **Step 3: Use the Web UI for P5-R001 and P5-R003**

  Start `signal-diag serve` on localhost. In the primary Web UI select the
  public `clipping` preset and default question, submit once, wait for actual
  completion, inspect actual trace/evidence/rules/knowledge and the honest
  Evaluation panel, then download JSON and HTML to the exact synthetic report
  paths. Capture a sanitized screenshot to `ui_completed.png` using the
  available in-app browser screenshot tool or the user's visible browser;
  ensure no credential, local username path, provider raw body, or unsanitized
  error appears. If screenshot capture is unavailable, record
  `real_demo_pending` and stop instead of fabricating the artifact.

  This one real run satisfies P5-R001 and the completed-run portion of P5-R003.
  Do not submit the preset a second time to improve its diagnosis.

- [ ] **Step 4: Use the CLI once for P5-R002**

  ```powershell
  $WavJsonTemp = Join-Path $env:TEMP ('phase5-wav-report-' + [guid]::NewGuid().ToString('N') + '.json')
  & $Phase5Python -m signal_diag.app.cli diagnose wav 'docs/demo/phase5/v0_2_acceptance/input_clipping_16bit.wav' --question 'Why does this signal sound distorted?' --channel mixdown --output json --html-output 'docs/demo/phase5/v0_2_acceptance/wav_report.html' | Set-Content -Encoding utf8NoBOM $WavJsonTemp
  if ($LASTEXITCODE -ne 0) { throw 'WAV product Demo failed' }
  Move-Item -LiteralPath $WavJsonTemp -Destination 'docs/demo/phase5/v0_2_acceptance/wav_report.json'
  ```

  This is the second and final required real-model run. Do not rerun it to
  change the outcome.

- [ ] **Step 5: Validate and sanitize both artifact sets**

  Parse both JSON files as `DiagnosisReport`, require strict trace events and
  resolvable same-run refs, confirm HTML is self-contained/escaped, and scan all
  created text/binary metadata for secrets, authorization, raw provider body,
  stack trace, full waveform, and full FFT markers. Record provider/model/prompt,
  result status/outcome, limitations, and any errors honestly in the artifact
  README.

- [ ] **Step 6: Apply independent product-Demo review and commit**

  Spec review verifies exactly two real product runs and P5-R001–P5-R003.
  Quality review validates sanitization, report parity, screenshot truth, no
  fallback, and no post-result code/prompt changes. Then:

  ```powershell
  git add docs/demo/phase5/v0_2_acceptance README.md AGENTS.md docs/README.md docs/superpowers/plans/2026-08-31-phase5-presentation-engineering.md
  git commit -m "docs: record Phase 5 real product Demo"
  ```

  If either run fails, retain the honest sanitized failure artifacts where a
  valid report exists, record `real_demo_pending`, and stop before Task 15
  acceptance. Never replace it with ScriptedPlanner.

---

### Task 15: Record terminal V0.2 status and prepare independent handoff

**Files:**

- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: this plan
- Do not change frozen contracts unless a genuine contradiction is first
  recorded in `docs/OPEN_QUESTIONS.md` and explicitly approved

**Interfaces:**

- Consumes only current deterministic/CI evidence and the two actual product
  Demo runs.
- Produces an honest terminal status and independent-verification handoff; no
  automatic push, merge, worktree deletion, or `build/` cleanup.

- [ ] **Step 1: Record exactly one terminal state**

  If and only if both gates passed, record:

  ```text
  presentation_harness_accepted
  real_demo_completed
  Phase 5 accepted; V0.2 complete resume-grade demonstrable vertical slice
  ```

  Otherwise record the exact pending/failed gate and do not claim Phase 5 or
  V0.2 completion.

- [ ] **Step 2: Run fresh final verification**

  ```powershell
  $Phase5FinalTemp = Join-Path $env:TEMP ('signal-diag-phase5-final-' + [guid]::NewGuid().ToString('N'))
  & $Phase5Python -m pytest -q -rxXs -p no:cacheprovider --basetemp $Phase5FinalTemp
  & $Phase5Python -m ruff check --no-cache src tests scripts
  & $Phase5Python -m mypy --no-incremental src
  git diff --check 36ae7c9..HEAD
  git status --short --branch
  ```

  Repeat the fresh wheel install smoke and verify hosted CI logs still point to
  the same commit. Worktree status may contain only the pre-existing untracked
  `build/` before the final status-doc commit.

- [ ] **Step 3: Map T224–T285 and P5-R001–P5-R003 to evidence**

  Include the matrix below, every task commit SHA, focused RED/GREEN commands,
  cumulative outputs, CI URLs/status, wheel name/hash, Demo artifact hashes,
  warnings, unsupported cases, and contract concerns in the handoff.

- [ ] **Step 4: Apply final independent reviews and commit status docs**

  Review the entire `07619fb..HEAD` diff against §§55–§64 and the frozen spec.
  Close every Critical/Important issue before commit:

  ```powershell
  git add AGENTS.md README.md docs/README.md docs/superpowers/plans/2026-08-31-phase5-presentation-engineering.md
  git commit -m "docs: record Phase 5 terminal acceptance"
  ```

- [ ] **Step 5: Deliver handoff without integration**

  Report branch, HEAD, commits, status, full verification, T/P5 mapping,
  artifact paths/checksums, warnings, and remaining limits. Do not push, merge,
  delete the worktree, or touch `build/` unless the user separately authorizes
  that integration action.

---

## Acceptance-ID to Task Mapping

| IDs | Task | Primary evidence |
|---|---:|---|
| T224–T233 | 3 | `tests/signal/test_wav.py` |
| T234–T238 | 5 | `tests/app/test_presets_preview.py` |
| T239–T240 | 4 | `tests/app/test_models.py` |
| T241–T245 | 6 | `tests/app/test_runs.py` |
| T246–T252 | 8 | `tests/app/test_service.py` |
| T253–T255 | 2 | `tests/evaluation/test_recording.py` |
| T256–T263 | 7 | `tests/app/test_reporting.py` |
| T264–T270 | 9 and 11 | `tests/app/test_api.py`, `tests/app/test_ui.py` |
| T271–T275 | 10 | `tests/app/test_cli.py` |
| T276–T280 | 11 and 7 | `tests/app/test_ui.py`, `tests/app/test_reporting.py` |
| T281–T284 | 12 | `tests/app/test_packaging.py`, `tests/test_architecture_boundaries.py`, CI |
| T285 | 13 | full deterministic/static/build/install/CI gate |
| P5-R001 | 14 | one Web-UI public synthetic RealLLMPlanner report set |
| P5-R002 | 14 | one CLI supported-WAV RealLLMPlanner report set |
| P5-R003 | 14 | actual completed UI, evaluation panel, sanitized screenshot |

### Detailed deterministic checklist

| ID | Task | Focus |
|---|---:|---|
| T224 | 3 | standard integer PCM containers |
| T225 | 3 | extensible PCM and unsupported encodings |
| T226 | 3 | exact full-scale conversion and 24-bit sign extension |
| T227 | 3 | canonical immutable SignalRecord |
| T228 | 3 | bounded RIFF traversal and pad bytes |
| T229 | 3 | structural corruption rejection |
| T230 | 3 | unsupported channel/encoding rejection |
| T231 | 3 | exact upload-byte boundary |
| T232 | 3 | sample-rate/frame/duration limits |
| T233 | 3 | safe filename and no-temp-file hygiene |
| T234 | 5 | exact five-preset catalog |
| T235 | 5 and 8 | evaluation/truth isolation from PlannerContext |
| T236 | 5 | deterministic samples with fresh opaque IDs |
| T237 | 5 and 8 | canonical shared registration |
| T238 | 5 | extrema-preserving bounded preview |
| T239 | 4 | frozen DTO validation |
| T240 | 4 | lifecycle invariants |
| T241 | 6 | one-active/four-queued FIFO scheduling |
| T242 | 6 | latest-twenty terminal retention |
| T243 | 6 | active safety and owned-Signal cleanup |
| T244 | 6 | capacity, lookup, and illegal-state errors |
| T245 | 6 | in-memory scope and idempotent shutdown |
| T246 | 8 | WAV service submission path |
| T247 | 8 | synthetic service submission path |
| T248 | 8 | channel realization |
| T249 | 8 | request integrity and forbidden Planner payloads |
| T250 | 8 | fresh per-run Planner/Runtime isolation |
| T251 | 8 | RealLLMPlanner product boundary and missing credentials |
| T252 | 8 | complete deterministic S1 service path |
| T253 | 2 | public generic Agent-event assembly |
| T254 | 2 | strict order, suffix, ref, and payload errors |
| T255 | 2 | Phase 4 trace/fingerprint/bundle compatibility |
| T256 | 7 | compact trace projection |
| T257 | 7 | completed-report construction |
| T258 | 7 | same-result Evidence/Rule/Knowledge integrity |
| T259 | 7 | canonical deterministic JSON |
| T260 | 7 | escaped self-contained HTML |
| T261 | 7 | forbidden secret/raw-array/provider data |
| T262 | 7 | actual identity and Demo-threshold labels |
| T263 | 7 | preview/report diagnostic separation |
| T264 | 9 and 11 | credential-free read-only endpoints and root UI |
| T265 | 9 | bounded WAV multipart endpoint |
| T266 | 9 | synthetic endpoint and validation envelope |
| T267 | 9 | monotonic polling lifecycle |
| T268 | 9 | JSON/HTML report endpoints and states |
| T269 | 9 and 11 | HTTP/CSP/CORS/static security defaults |
| T270 | 8 and 9 | missing credentials and post-202 failure truth |
| T271 | 10 | exact argparse grammar |
| T272 | 10 | bounded direct-service WAV command |
| T273 | 10 | direct-service preset command without truth leakage |
| T274 | 10 | text/JSON/HTML parity and exit codes |
| T275 | 10 | localhost serve defaults and no fake switch |
| T276 | 11 and 12 | packaged native no-build UI |
| T277 | 11 | complete Web interaction |
| T278 | 11 | text-safe DOM and no fake progress |
| T279 | 7 and 11 | immutable accepted-evaluation snapshot integrity |
| T280 | 7 and 11 | honest Evaluation panel disclosure |
| T281 | 12 | extras, console entry, and package data |
| T282 | 12 | sdist/wheel clean-install smoke |
| T283 | 12 | architecture dependency boundary |
| T284 | 12 | secret-free Python 3.11/3.12 CI |
| T285 | 13 | cumulative deterministic/static/build/install/CI gate |

## Execution Stop

This plan is a design asset. Its creation does not authorize Task 2, dependency
installation, code/test modification, model execution, push, merge, worktree
deletion, or `build/` cleanup. Cursor may begin only after the user explicitly
chooses an execution workflow and scope.
