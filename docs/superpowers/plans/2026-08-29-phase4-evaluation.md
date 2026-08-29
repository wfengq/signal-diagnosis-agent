# Phase 4 Versioned Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, versioned Scenario S1 evaluation harness, an honest fixed-pipeline baseline, and a provider-neutral real-model benchmark runner without changing Phase 1–3 behavior.

**Architecture:** Add an isolated `signal_diag.evaluation` package whose dependencies point only toward the accepted Phase 1–3 layers. A typed 24-case manifest feeds the existing synthetic generators, repository, DSP Tools, rules, knowledge, and Agent runtime; immutable traces then feed pure scorers and append-only report writers. Real-model execution uses the existing `RealLLMPlanner` product path through an external recording wrapper, while required CI uses injected scripted planners and provider stubs.

**Tech Stack:** Python 3.11+, NumPy, Pydantic V2, PyYAML safe loading, pytest/pytest-asyncio, Ruff, mypy, standard-library `csv`, `hashlib`, `importlib.resources`, `json`, and `pathlib`.

**Spec:** `docs/superpowers/specs/2026-08-29-phase4-evaluation-design.md`

## Global Constraints

- `docs/CONTRACTS_V0_2.md` §§41–§49 and `docs/TEST_PLAN_V0_2.md` §22 are frozen.
- Do not modify any Phase 1–3 public model, function, constructor, package boundary, or runtime behavior.
- Dependency direction is `signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app`; no Phase 1–3 module imports `evaluation`.
- `RealLLMPlanner` is the product path. `ScriptedPlanner` and provider fakes are deterministic test doubles only; never fall back from a failed real planner to a scripted planner.
- Never serialize raw waveforms, full FFT arrays, credentials, or raw provider responses into planner records, traces, or official bundles.
- Numerical signal metrics come only from existing DSP/Tools. Pass/fail thresholds come only from `profile_s1_distortion` `1.0.0-demo`.
- The 1% clipping-ratio and 5% THD values are demonstration limits, not industry standards or SLAs.
- Required pytest must not call a real LLM. Missing real-model credentials may leave `benchmark_status="pending"` but must not block deterministic harness acceptance.
- The official real benchmark pins provider `deepseek`, model `deepseek-v4-flash`, prompt `v0.2-s1-planner-4`, five held-out repetitions, two infrastructure retries, and concurrency one.
- Use TDD for each task: focused RED, minimal GREEN, cumulative full pytest, then a local commit. Do not push or merge.
- Stop on a genuine frozen-contract conflict; record it in `docs/OPEN_QUESTIONS.md` instead of silently changing the interface.
- Phase 5, WAV, API/UI, HTML/PDF, new DSP algorithms, new fault classes, vector retrieval, and model training are out of scope.

## File Structure

```text
src/signal_diag/evaluation/
├── __init__.py          # frozen public exports only
├── __main__.py          # four operational subcommands, no plaintext key argument
├── models.py            # all immutable Phase 4 public Pydantic models
├── dataset.py           # safe manifest loading, signal materialization, validation
├── recording.py         # transparent planner recording and strict trace assembly
├── baseline.py          # two-Tool deterministic comparison path
├── scoring.py           # pure per-run and aggregate scoring
├── runner.py            # deterministic harness and provider-neutral slot scheduler
├── reporting.py         # append-only six-file bundle writer
└── manifests/
    └── s1_distortion_v1.yaml

tests/evaluation/
├── __init__.py
├── conftest.py          # clocks, IDs, dependency builders, compact trace fixtures
├── test_models.py       # T125–T132
├── test_dataset.py      # T133–T140
├── test_recording.py    # T141–T148
├── test_baseline.py     # T149–T154
├── test_scoring.py      # T155–T166
├── test_acceptance.py   # T167–T172
├── test_reporting.py    # T173–T174 and report safety in T181
└── test_runner.py       # T175–T181
```

Modify `pyproject.toml` only to package `evaluation/manifests/*.yaml`. Modify `tests/test_architecture_boundaries.py` only to add T182. Update `AGENTS.md` and `docs/README.md` only after the deterministic gate is actually green.

---

### Task 1: Public Evaluation Models and Cross-Field Validation

**Files:**
- Create: `src/signal_diag/evaluation/__init__.py`
- Create: `src/signal_diag/evaluation/models.py`
- Create: `tests/evaluation/__init__.py`
- Create: `tests/evaluation/conftest.py`
- Create: `tests/evaluation/test_models.py`

**Test IDs:** T125–T132

**Interfaces:**
- Consumes: `ToolName`, `EvidenceValidity`, `DiagnosisOutcome`, `DiagnosisClaim`, `AgentDecision`, `PlannerContext`, `Observation`, `AgentRunResult`, `TerminationReason`, `RunStatus`, `ConfidenceLabel`, `ToolHistoryEntry`, `RuleEvaluationBatch`, and `KnowledgeRetrievalResult` from accepted Phase 1–3 modules.
- Produces: every public alias and model listed in `CONTRACTS_V0_2.md` §§42, 44, 46, and 47, exported verbatim from `evaluation.models` and later from `evaluation.__init__`.

- [ ] **Step 1: Create model-contract tests that fail because the package is absent**

  Add tests named `test_t125_manifest_identity_and_immutability`, `test_t126_signal_spec_discriminator`, `test_t127_signal_parameter_validation`, `test_t128_harmonic_ratio_validation`, `test_t129_evidence_condition_strictness`, `test_t130_sufficient_set_references`, `test_t131_case_consistency`, and `test_t132_manifest_identity_and_references`.

  Use the discriminated union directly so unknown generators fail at validation:

  ```python
  SIGNAL_SPEC_ADAPTER = TypeAdapter(SyntheticSignalSpec)

  def test_t126_signal_spec_discriminator() -> None:
      parsed = SIGNAL_SPEC_ADAPTER.validate_python(
          {"generator": "sine", "frequency_hz": 200.0}
      )
      assert isinstance(parsed, SineSignalSpec)
      with pytest.raises(ValidationError):
          SIGNAL_SPEC_ADAPTER.validate_python(
              {"generator": "square", "frequency_hz": 200.0}
          )
  ```

  For T129, assert `expected_value=True` does not compare equal by scalar category to `1`; for T130–T132, construct one valid case and mutate exactly one duplicate/reference/category field per parametrized row.

- [ ] **Step 2: Run the model RED suite**

  Run:

  ```powershell
  python -m pytest tests/evaluation/test_models.py -q
  ```

  Expected: collection fails with `ModuleNotFoundError: signal_diag.evaluation`.

- [ ] **Step 3: Implement aliases, typed signal specs, and leaf models exactly as frozen**

  Define the aliases and model fields exactly as §§42, 44, 46, and 47. Use strict scalar types and finite-number validation:

  ```python
  EvidenceScalar = StrictStr | StrictInt | StrictFloat | StrictBool

  class HarmonicRatioSpec(BaseModel):
      model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
      order: int = Field(ge=2)
      ratio: float = Field(ge=0.0)

  SyntheticSignalSpec = Annotated[
      SineSignalSpec
      | ClippedSineSignalSpec
      | HarmonicSineSignalSpec
      | CombinedDistortionSignalSpec
      | WhiteNoiseSignalSpec,
      Field(discriminator="generator"),
  ]
  ```

  Implement `ProviderUsage`, planner/event/attempt/baseline/trace models, rate/run/aggregate/target/report models, and the two run-artifact variants in this same task so later tasks never create shadow data structures.

- [ ] **Step 4: Implement explicit cross-field validators**

  Add reusable duplicate checks and `model_validator(mode="after")` methods. The `EvaluationCase` validator must enforce the frozen mapping:

  ```python
  _CATEGORY_RULES = {
      "clean": ("sine", (), ("no_supported_fault",), "not_needed"),
      "clipping": ("clipped_sine", ("clipping",), ("supported_fault",), "optional"),
      "harmonic": (
          "harmonic_sine",
          ("harmonic_distortion",),
          ("supported_fault",),
          "optional",
      ),
      "combined": (
          "combined_distortion",
          ("clipping", "harmonic_distortion"),
          ("supported_fault",),
          "optional",
      ),
      "invalid_noise": ("white_noise", (), ("inconclusive",), "required"),
  }
  ```

  Also enforce canonical causal-fault ordering, non-empty/unique harmonic ratios, non-empty/unique sufficient-set tuples, knowledge-tag policy, combined-only identifiability, UTC-aware timestamps, attempt time order, decision/error status consistency, provider-token sum consistency, and `RateMetric.value == numerator / denominator` with zero denominator mapped to `0.0`.

- [ ] **Step 5: Run T125–T132 GREEN and type-check the new module**

  Run:

  ```powershell
  python -m pytest tests/evaluation/test_models.py -q
  python -m ruff check src/signal_diag/evaluation/models.py tests/evaluation/test_models.py
  python -m mypy src/signal_diag/evaluation/models.py
  ```

  Expected: eight test groups pass; Ruff and mypy pass.

- [ ] **Step 6: Run the cumulative suite and commit**

  Run `python -m pytest -q`, then commit:

  ```powershell
  git add src/signal_diag/evaluation/__init__.py src/signal_diag/evaluation/models.py tests/evaluation
  git commit -m "feat(evaluation): add frozen Phase 4 models"
  ```

---

### Task 2: Canonical Manifest, Signal Materialization, and Dataset Gate

**Files:**
- Create: `src/signal_diag/evaluation/dataset.py`
- Create: `src/signal_diag/evaluation/manifests/s1_distortion_v1.yaml`
- Create: `tests/evaluation/test_dataset.py`
- Modify: `pyproject.toml`
- Modify: `src/signal_diag/evaluation/__init__.py`

**Test IDs:** T133–T140

**Interfaces:**
- Consumes: all Task 1 manifest models; existing five synthetic generators; `build_signal_record`, `SignalRepository`, `SignalToolService`, `RuleEngine`, and `RuleProfileLoader`.
- Produces: `load_dataset_manifest(path: Path) -> DatasetManifest`, the exact
  five-argument `validate_dataset(manifest, repository, tool_service,
  rule_engine, profile_loader) -> DatasetValidationReport`, and private
  `_materialize_case(case, repository) -> SignalRecord`.

- [ ] **Step 1: Add failing loader, allocation, packaging, and reconstruction tests**

  Test the exact allocation `(8 development, 16 held_out)` and category counts `(2,2,2,1,1)` / `(3,4,4,3,2)`. Reconstruct each case twice and assert stable metadata plus `np.array_equal` samples. Build a wheel without network and inspect it as a ZIP:

  ```python
  subprocess.run(
      [
          sys.executable,
          "-m",
          "pip",
          "wheel",
          ".",
          "--no-deps",
          "--no-build-isolation",
          "--wheel-dir",
          str(tmp_path),
      ],
      check=True,
  )
  wheel = next(tmp_path.glob("signal_diagnosis_agent-*.whl"))
  with ZipFile(wheel) as archive:
      assert "signal_diag/evaluation/manifests/s1_distortion_v1.yaml" in archive.namelist()
  ```

- [ ] **Step 2: Add failing real-DSP validation and rejection tests**

  Parametrize independent corruptions for allocation, observable condition, profile identity, seeded reconstruction, and combined identifiability. Assert each yields `valid is False`, a stable issue code, and prevents the runner fixture from starting. Assert white-noise harmonic Evidence has `validity="not_applicable"` and no `thd_percent` Evidence.

- [ ] **Step 3: Run the dataset RED suite**

  Run `python -m pytest tests/evaluation/test_dataset.py -q`.

  Expected: imports or canonical-manifest lookup fail.

- [ ] **Step 4: Write the exact 24-case manifest**

  Use the exact case matrix below. Every row explicitly serializes
  `sample_rate_hz: 48000` and `duration_s: 2.0`. Sine rows additionally use
  `phase_rad: 0.0` and `dc_offset: 0.0`; noise rows use `rms: 0.1`.

  | Case ID | Split/category | Exact generator parameters | Boundary/severity tag |
  |---|---|---|---|
  | `case_dev_clean_01` | development/clean | sine 200 Hz, amplitude 0.50 | nominal |
  | `case_dev_clean_02` | development/clean | sine 400 Hz, amplitude 0.70 | high-amplitude-clean |
  | `case_dev_clipping_01` | development/clipping | clipped sine 200 Hz, amplitude 0.90, clip 0.65 | strong |
  | `case_dev_clipping_boundary` | development/clipping | clipped sine 80 Hz, amplitude 0.90, clip 0.89999 | clipping-at-0.01 |
  | `case_dev_harmonic_boundary` | development/harmonic | harmonic sine 200 Hz, amplitude 0.50, ratios `{2: 0.04999999}` | thd-at-5 |
  | `case_dev_harmonic_01` | development/harmonic | harmonic sine 250 Hz, amplitude 0.50, ratios `{2: 0.08}` | above-thd |
  | `case_dev_combined_01` | development/combined | combined 200 Hz, amplitude 0.90, ratios `{2: 0.20}`, clip 0.75; signature order 2, separation 0.04 | strong |
  | `case_dev_invalid_noise_01` | development/invalid_noise | white noise seed 11 | invalid-harmonic |
  | `case_held_clean_01` | held_out/clean | sine 220 Hz, amplitude 0.35 | low-amplitude-clean |
  | `case_held_clean_02` | held_out/clean | sine 300 Hz, amplitude 0.50 | nominal |
  | `case_held_clean_03` | held_out/clean | sine 500 Hz, amplitude 0.70 | high-amplitude-clean |
  | `case_held_clipping_01` | held_out/clipping | clipped sine 65 Hz, amplitude 0.90, clip 0.89999 | clipping-below-0.01 |
  | `case_held_clipping_02` | held_out/clipping | clipped sine 80 Hz, amplitude 0.90, clip 0.899999 | clipping-at-0.01 |
  | `case_held_clipping_03` | held_out/clipping | clipped sine 70 Hz, amplitude 0.90, clip 0.89999 | clipping-above-0.01 |
  | `case_held_clipping_04` | held_out/clipping | clipped sine 300 Hz, amplitude 0.90, clip 0.70 | strong |
  | `case_held_harmonic_01` | held_out/harmonic | harmonic sine 300 Hz, amplitude 0.50, ratios `{2: 0.04}` | thd-below-5 |
  | `case_held_harmonic_02` | held_out/harmonic | harmonic sine 400 Hz, amplitude 0.50, ratios `{2: 0.04999999}` | thd-at-5 |
  | `case_held_harmonic_03` | held_out/harmonic | harmonic sine 500 Hz, amplitude 0.50, ratios `{2: 0.08}` | thd-above-5 |
  | `case_held_harmonic_04` | held_out/harmonic | harmonic sine 250 Hz, amplitude 0.50, ratios `{2: 0.08, 3: 0.04}` | multi-harmonic |
  | `case_held_combined_01` | held_out/combined | combined 250 Hz, amplitude 0.90, ratios `{3: 0.18}`, clip 0.72; signature order 3, separation 0.04 | strong |
  | `case_held_combined_02` | held_out/combined | combined 300 Hz, amplitude 0.90, ratios `{2: 0.12, 3: 0.08}`, clip 0.70; signature order 3, separation 0.03 | mixed |
  | `case_held_combined_03` | held_out/combined | combined 400 Hz, amplitude 0.90, ratios `{2: 0.15}`, clip 0.78; signature order 2, separation 0.04 | moderate |
  | `case_held_invalid_noise_01` | held_out/invalid_noise | white noise seed 29 | invalid-harmonic |
  | `case_held_invalid_noise_02` | held_out/invalid_noise | white noise seed 47 | invalid-harmonic |

  These parameters were calibrated against the accepted DSP at baseline
  `3eaf662`: the three held-out boundary clipping ratios are `0.009375`,
  `0.010000`, and `0.010416666666666666`; pure second-harmonic ratios 0.04,
  0.04999999, and 0.08 yield THD approximately 4%, 4.9999993522848%, and 8%.
  The exact `0.05` injection measures slightly above 5.0% and would fail the
  strict rule condition `lte 5.0`; `0.04999999` keeps THD inside the stacked
  `gte 4.999` / `lte 5.001` window **and** `lte 5.0`. Comparators stay strict;
  do not add implicit tolerance to the rule engine. The calibration values
  are test expectations, not extra product thresholds.

  `case_held_clean_01` is 220 Hz at amplitude 0.35, not 100 Hz. A 100 Hz sine
  at the same amplitude false-triggers the existing DSP 1e-4 flat-top detector
  near peaks (`clipping_detected` / `flat_top_detected` become true while
  `clipping_ratio` stays 0.0). That 100 Hz flat-top false positive is a known
  limitation of the accepted DSP / dataset calibration, not a frozen-contract
  defect. At 220 Hz / 0.35 the measured clipping metrics are
  `clipping_ratio = 0.0`, `clipping_detected = false`, `flat_top_detected = false`.

  Express the two numerical boundary windows as pairs of manifest conditions:
  clipping-at-boundary is `gte 0.0095` plus `lte 0.0105`; THD-at-boundary is
  `gte 4.999` plus `lte 5.001` with unit `%`, stacked with the harmonic-template
  rule condition `lte 5.0`. These are explicit dataset-QA tolerances, never
  extra rule thresholds or planner-visible product limits.

  Apply these exact condition templates, using case-prefixed IDs so all refs are
  globally readable:

  - Clean: clipping detected `eq false`, clipping ratio `lte 0.01`, flat top
    `eq false`, harmonic valid `eq true`, and THD `lte 5.0` `%`; one sufficient
    set contains all five refs and supports `no_supported_fault`.
  - Clipping: clipping detected `eq true`; clipping ratio uses `lte 0.01` only
    for the below/at rows and `gt 0.01` for above/strong rows; flat top `eq
    true`. One sufficient set contains those three refs and supports clipping.
  - Harmonic: clipping detected `eq false`, harmonic valid `eq true`, and THD
    uses `lte 5.0` for below/at rows or `gt 5.0` for above rows. At-boundary
    rows also stack the QA window `gte 4.999` plus `lte 5.001`. The causal claim
    remains harmonic even when the profile judgment passes. One sufficient set
    contains valid plus THD and supports harmonic distortion; a second contains
    clipping-absent plus valid plus THD so order-distinct routes are legal.
  - Combined: clipping detected `eq true`, clipping ratio `gt 0.01`, harmonic
    valid `eq true`, THD `gt 5.0` `%`, and the declared harmonic signature
    `gte` its injected ratio times `0.25`. The sufficient set contains clipping,
    valid, THD, and signature refs and supports both fault claims.
  - Invalid/noise: harmonic `valid` has validity `not_applicable`, comparator
    `eq`, expected value `false`, and supports `inconclusive`; its one sufficient
    set supports inconclusive and requires a limitation.

  Acceptable first tools are both `detect_clipping` and
  `analyze_harmonic_distortion` for clean/harmonic/combined, only
  `detect_clipping` for clipping, and only `analyze_harmonic_distortion` for
  invalid/noise. Knowledge policy/tags are exactly: clean `not_needed`/empty;
  clipping `optional`/`("clipping",)`; harmonic `optional`/
  `("harmonic-distortion",)`; combined `optional`/both tags; invalid/noise
  `required`/`("inconclusive",)`. Do not insert generated expected floating
  values into the manifest beyond the explicit boundary and signature values
  above.

- [ ] **Step 5: Implement safe loading and stable materialization**

  Parse using `yaml.safe_load`, then `DatasetManifest.model_validate`. Dispatch only on the typed signal spec. Preserve samples while assigning the stable ID:

  ```python
  def _stable_signal_id(case_id: str) -> str:
      return f"sig_eval_{case_id.removeprefix('case_')}"

  generated = generate_sine(
      frequency_hz=spec.frequency_hz,
      sample_rate_hz=spec.sample_rate_hz,
      duration_s=spec.duration_s,
      amplitude=spec.amplitude,
      phase_rad=spec.phase_rad,
      dc_offset=spec.dc_offset,
  )
  record = build_signal_record(
      generated.record.samples,
      sample_rate_hz=generated.record.meta.sample_rate_hz,
      source_type="synthetic",
      signal_id=_stable_signal_id(case.case_id),
  )
  repository.put(record)
  ```

  Implement equivalent explicit calls for the other four spec variants. Never normalize, round, or expose generation truth to planner context.

- [ ] **Step 6: Implement condition matching and complete validation**

  For every case, execute only the real Tools referenced by its observable conditions, index Evidence by `(source_tool, metric)`, and require strict type, validity, unit, and comparator matches. Load the frozen profile and verify both identity fields. Reconstruct twice and compare stable metadata/samples. For combined cases, generate the matched clipping-only control, run harmonic analysis, read the declared signature metric from each result, and require absolute separation at least the manifest value. Return all issues in manifest order; `valid` is exactly `not issues`.

- [ ] **Step 7: Package the manifest and run T133–T140 GREEN**

  Add:

  ```toml
  "signal_diag.evaluation" = ["manifests/*.yaml"]
  ```

  under `[tool.setuptools.package-data]`, export loader/validator, then run:

  ```powershell
  python -m pytest tests/evaluation/test_dataset.py -q
  python -m pytest tests/evaluation/test_models.py tests/evaluation/test_dataset.py -q
  ```

- [ ] **Step 8: Run the cumulative suite and commit**

  Commit only after `python -m pytest -q` passes:

  ```powershell
  git add pyproject.toml src/signal_diag/evaluation tests/evaluation/test_dataset.py
  git commit -m "feat(evaluation): add validated S1 dataset manifest"
  ```

---

### Task 3: Transparent RecordingPlanner

**Files:**
- Create: `src/signal_diag/evaluation/recording.py`
- Create: `tests/evaluation/test_recording.py`
- Modify: `src/signal_diag/evaluation/__init__.py`

**Test IDs:** T141–T142

**Interfaces:**
- Consumes: existing `PlannerModel.decide(context)`, `AgentDecision`, `PlannerOutputError`, and frozen Task 1 record models.
- Produces: `RecordingPlanner(planner)` and immutable `records` snapshots.

- [ ] **Step 1: Write failing delegation and failure-record tests**

  Use a delegate that asserts object identity (`context is received_context`), returns one known decision, then separate delegates that raise `PlannerOutputError` and `RuntimeError`. Assert the wrapper returns the exact decision object, records zero-based indices, and re-raises the exact exception object.

- [ ] **Step 2: Run the RecordingPlanner RED tests**

  Run `python -m pytest tests/evaluation/test_recording.py -k 't141 or t142' -q`.

  Expected: `RecordingPlanner` is missing.

- [ ] **Step 3: Implement transparent recording with injectable measurement hooks**

  Keep public construction exactly one-argument. Private defaults use `perf_counter`; usage extraction returns `None` unless a delegate exposes validated usage through a private adapter protocol.

  ```python
  async def decide(self, context: PlannerContext) -> AgentDecision:
      index = len(self._records)
      started = self._clock()
      try:
          candidate = await self._planner.decide(context)
      except BaseException as error:
          self._append_error(index, context, error, started)
          raise
      try:
          decision = _AGENT_DECISION_ADAPTER.validate_python(candidate)
      except ValidationError as error:
          output_error = PlannerOutputError(
              f"planner returned invalid AgentDecision: {error}"
          )
          self._append_error(index, context, output_error, started)
          raise output_error from error
      self._records.append(
          PlannerDecisionRecord(
              record_id=f"decision_{index:06d}",
              decision_index=index,
              context=context,
              status="decision",
              decision=decision,
              latency_ms=max(0.0, (self._clock() - started) * 1000.0),
              provider_usage=self._read_usage(),
          )
      )
      return decision
  ```

  Convert a Pydantic validation failure for a returned candidate into
  `PlannerOutputError` before recording/re-raising so the unchanged Runtime uses
  its existing retry policy. Classify planner-output failures as
  `planner_output_error`, known planner failures as `planner_error`,
  provider-adapter failures as `provider_error`, and remaining raised
  exceptions as `planner_error`. Sanitize messages without including response
  bodies or credentials. `_read_usage` may inspect only a private capture proxy
  already held by `RealLLMPlanner._client`; it must return `None` for ordinary
  planners and must never expose the provider response.

- [ ] **Step 4: Run GREEN, cumulative tests, and commit**

  Run focused tests, `python -m pytest -q`, Ruff, and mypy. Commit:

  ```powershell
  git add src/signal_diag/evaluation/recording.py src/signal_diag/evaluation/__init__.py tests/evaluation/test_recording.py
  git commit -m "feat(evaluation): record planner decisions transparently"
  ```

---

### Task 4: Strict Chronological Trace Assembly

**Files:**
- Modify: `src/signal_diag/evaluation/recording.py`
- Modify: `tests/evaluation/test_recording.py`

**Test IDs:** T143–T148

**Interfaces:**
- Consumes: Task 3 records plus `AgentRunResult | BaselineRunResult`.
- Produces: `assemble_evaluation_trace(case, records, result, config, *, run_slot, execution_path) -> EvaluationTrace`.

- [ ] **Step 1: Add failing success-path tests for all four decision kinds**

  Construct contexts where exactly one artifact delta follows each successful decision: Tool -> Observation/Evidence, rules -> one batch, knowledge -> one retrieval, finish -> no new runtime artifact. Assert contiguous event indices and causing-decision indices.

- [ ] **Step 2: Add failing ambiguity and safety tests**

  Parametrize missing/duplicate/reordered Observation, Evidence-ref mismatch, two rule batches after one decision, unresolved final claim refs, waveform/FFT-like arrays, secret keys, and raw response bodies. Every ambiguous case must raise `ValueError` rather than use grouped history.

- [ ] **Step 3: Run T143–T148 RED**

  Run `python -m pytest tests/evaluation/test_recording.py -k 't14[3-8]' -q`.

- [ ] **Step 4: Implement delta-based assembly**

  Compare record `i` context to record `i+1` context, or to the final result for the last successful action. Require tuple-prefix identity and extract only the suffix:

  ```python
  def _strict_suffix(before: tuple[T, ...], after: tuple[T, ...], label: str) -> tuple[T, ...]:
      if len(after) < len(before) or after[: len(before)] != before:
          raise ValueError(f"{label} is not an append-only delta")
      return after[len(before) :]
  ```

  A successful `CallToolDecision` requires one Observation whose Tool and normalized arguments match the decision and whose referenced Evidence equals the extracted Evidence suffix. `EvaluateRulesDecision` and `RetrieveKnowledgeDecision` each require exactly one corresponding suffix item. Error records produce only planner-call events. Baseline traces contain observation/rule events in result order and no planner events; their required `caused_by_decision_index` values use fixed-pipeline action ordinals `0` for clipping, `1` for harmonic analysis, and `2` for rule evaluation. These ordinals correlate artifacts without fabricating planner calls.

- [ ] **Step 5: Validate final references and forbidden payloads**

  Build same-trace sets of Evidence IDs, rule evaluation IDs, and knowledge retrieval IDs. Reject every missing claim reference. Recursively inspect serialized planner records/events for `samples`, `waveform`, full spectral arrays, credential-like keys, and raw provider-response fields; compact Tool result fields and spectral-peak summaries remain allowed.

- [ ] **Step 6: Run GREEN, cumulative tests, and commit**

  Run `python -m pytest tests/evaluation/test_recording.py -q`, then full pytest, Ruff, mypy, and commit:

  ```powershell
  git add src/signal_diag/evaluation/recording.py tests/evaluation/test_recording.py
  git commit -m "feat(evaluation): assemble strict chronological traces"
  ```

---

### Task 5: Honest Fixed-Pipeline Baseline

**Files:**
- Create: `src/signal_diag/evaluation/baseline.py`
- Create: `tests/evaluation/test_baseline.py`
- Modify: `src/signal_diag/evaluation/__init__.py`

**Test IDs:** T149–T154

**Interfaces:**
- Consumes: injected repository, `SignalToolService`, `RuleEngine`, `RuleProfileLoader`, `ClippingInput()`, and `HarmonicDistortionInput()`.
- Produces: `FixedPipelineBaseline.run(*, signal_id: str, user_request: str) ->
  BaselineRunResult` with exactly two Tool calls and one profile batch.

- [ ] **Step 1: Write failing order, dependency, and no-privilege tests**

  Spy on the injected Tool service and assert exact calls:

  ```python
  assert calls == [
      ("detect_clipping", signal_id, ClippingInput()),
      ("analyze_harmonic_distortion", signal_id, HarmonicDistortionInput()),
  ]
  ```

  Use spies that fail if FFT/F0/knowledge/manifest truth or matched-control data is accessed.

- [ ] **Step 2: Write failing six-row mapping and reproducibility tests**

  Cover the exact §45 table. Assert baseline-specific completion reasons, empty knowledge refs, limitations on invalid harmonic Evidence, same-run evidence/rule refs, and stable business fields across repeated fresh-dependency runs.

- [ ] **Step 3: Run T149–T154 RED**

  Run `python -m pytest tests/evaluation/test_baseline.py -q`.

- [ ] **Step 4: Implement the two-Tool run and rule mapping**

  Convert each `ToolResult` into the existing `Observation`, `Evidence`, and `ToolHistoryEntry` shapes without inventing values. Evaluate the full official profile over the accumulated Evidence. Derive indicators by rule IDs and judgments:

  ```python
  clipping = any(
      item.rule_id in {
          "rule_clipping_detected_absent",
          "rule_clipping_ratio_acceptable",
          "rule_flat_top_absent",
      }
      and item.judgment == "fail"
      for item in batch.evaluations
  )
  harmonic_valid = any(
      item.rule_id == "rule_harmonic_analysis_valid" and item.judgment == "pass"
      for item in batch.evaluations
  )
  harmonic = harmonic_valid and any(
      item.rule_id == "rule_thd_acceptable" and item.judgment == "fail"
      for item in batch.evaluations
  )
  ```

  Generate deterministic baseline/run/claim IDs from canonical input IDs and referenced artifacts, not random UUIDs. Cite only Evidence and evaluations used by each claim.

- [ ] **Step 5: Run GREEN, cumulative tests, and commit**

  Run focused tests, full pytest, Ruff, mypy, then commit:

  ```powershell
  git add src/signal_diag/evaluation/baseline.py src/signal_diag/evaluation/__init__.py tests/evaluation/test_baseline.py
  git commit -m "feat(evaluation): add honest fixed-pipeline baseline"
  ```

---

### Task 6: Pure Per-Run Scoring

**Files:**
- Create: `src/signal_diag/evaluation/scoring.py`
- Create: `tests/evaluation/test_scoring.py`
- Modify: `src/signal_diag/evaluation/__init__.py`

**Test IDs:** T155, T157–T165

**Interfaces:**
- Consumes: one `EvaluationCase` and one assembled `EvaluationTrace`.
- Produces: `score_evaluation_trace(case, trace) -> RunScore` and private pure helpers for condition matching and viability.

- [ ] **Step 1: Add failing diagnosis, outcome, grounding, and unsupported-claim tests**

  Cover clean, single-fault, combined, and inconclusive traces. Deduplicate predicted labels for exact-set scoring but count duplicate unsupported fault claims in the unsupported numerator. For grounding, require all refs to resolve and at least one matching condition whose `supports_claims` includes the exact claim type.

- [ ] **Step 2: Add failing behavior-path tests**

  Create compact traces for acceptable alternative first Tools, sufficient-set advancement, invalid/error recovery, premature/redundant rule use, a Tool call after sufficiency, required/optional/not-needed knowledge, irrelevant tags, and uncited retrievals. Assert exact counters and stable failure codes rather than a single opaque boolean.

- [ ] **Step 3: Run T155 and T157–T165 RED**

  Run:

  ```powershell
  python -m pytest tests/evaluation/test_scoring.py -k "not macro_f1 and not aggregate" -q
  ```

- [ ] **Step 4: Implement claim and grounding extraction**

  Extract the final diagnosis from either result type; absent diagnosis yields no predicted faults and `predicted_outcome=None`. Match Evidence conditions using the same strict comparator function as dataset validation. Never infer semantic support from metric names.

- [ ] **Step 5: Implement path viability and action scoring**

  Track which condition refs are satisfied after each event. A sufficient set remains viable until a required condition is contradicted by observed valid Evidence. A Tool advances a viable set only if its new Evidence satisfies a previously unsatisfied condition. After each Observation/rule/knowledge delta, classify the next decision with a stable reason code. Set timely stop false only for DSP Tool decisions after the earliest satisfied sufficient set; required rules/knowledge remain legal.

- [ ] **Step 6: Implement knowledge and efficiency counters**

  Normalize tags using the existing knowledge normalization semantics. A required-policy run has one opportunity and succeeds once if any non-duplicate retrieval is relevant. Score each retrieval independently for unnecessary use and citation utilization. Preserve unknown usage and latency as `None`.

- [ ] **Step 7: Run per-run GREEN, cumulative tests, and commit**

  Run focused tests, full pytest, Ruff, mypy, then commit:

  ```powershell
  git add src/signal_diag/evaluation/scoring.py src/signal_diag/evaluation/__init__.py tests/evaluation/test_scoring.py
  git commit -m "feat(evaluation): score diagnosis traces deterministically"
  ```

---

### Task 7: Aggregate Metrics, Fingerprint, and Target Status

**Files:**
- Modify: `src/signal_diag/evaluation/scoring.py`
- Modify: `tests/evaluation/test_scoring.py`

**Test IDs:** T156, T166, fingerprint portion of T175

**Interfaces:**
- Consumes: manifest, traces, scores, attempts, config, targets, and harness status.
- Produces: the exact frozen `aggregate_benchmark(manifest, traces, scores,
  attempts, config, targets, *, harness_status) -> BenchmarkReport`.

- [ ] **Step 1: Add failing macro-F1 and aggregation tests**

  Assert per-label `TP`, `FP`, and `FN` over exactly `clipping` and `harmonic_distortion`, label F1 `2TP / (2TP + FP + FN)`, zero label denominator -> `0.0`, and arithmetic mean of the two label F1 values. Test nearest-rank p50/p95 using sorted samples and `ceil(p*n)`.

- [ ] **Step 2: Add failing identity, zero-denominator, and target-status tests**

  Reject duplicate `(execution_path, case_id, run_slot)`, trace/score mismatches, and foreign dataset/config records. Assert target metrics use held-out Agent runs only; baseline metrics are separate; zero denominators are non-applicable; pending/incomplete always maps to `not_evaluated`; completed below threshold maps to `below_target` without raising.

- [ ] **Step 3: Add failing canonical fingerprint tests**

  Assert changing any behavioral field changes the SHA-256, while changing only `benchmark_id` or `started_at_utc` does not. Serialize with sorted keys and compact separators:

  ```python
  payload = config.model_dump(mode="json", exclude={"benchmark_id", "started_at_utc"})
  encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
  expected = hashlib.sha256(encoded).hexdigest()
  ```

- [ ] **Step 4: Run aggregate RED tests**

  Run `python -m pytest tests/evaluation/test_scoring.py -k 'macro_f1 or aggregate or fingerprint' -q`.

- [ ] **Step 5: Implement aggregation from raw counters**

  Construct every `RateMetric` through one helper that computes its value. Sum observed provider usage only for covered runs; return all usage totals `None` at zero coverage. Average planner calls only for Agent traces. Build warnings for non-applicable target metrics rather than treating them as successes.

- [ ] **Step 6: Run GREEN, cumulative tests, and commit**

  Run focused tests, full pytest, Ruff, mypy, then commit:

  ```powershell
  git add src/signal_diag/evaluation/scoring.py tests/evaluation/test_scoring.py
  git commit -m "feat(evaluation): aggregate metrics and target status"
  ```

---

### Task 8: Deterministic Full-Manifest Harness

**Files:**
- Create: `src/signal_diag/evaluation/runner.py`
- Create: `tests/evaluation/test_acceptance.py`
- Modify: `tests/evaluation/conftest.py`

**Test IDs:** T167–T172

**Interfaces:**
- Consumes: validated manifest, existing `DistortionDiagnosisRuntime`, `ScriptedPlanner`, real DSP/Tools/rules/knowledge, recording/trace/scoring/baseline modules.
- Produces: private `_run_deterministic_harness(manifest: DatasetManifest,
  scripted_steps: Mapping[str, tuple[ScriptedStep, ...]], config:
  BenchmarkConfig) -> tuple[EvaluationTrace, ...]` and reusable dependency
  factories; these remain private because §49 exposes no runner function.

- [ ] **Step 1: Write a failing 24-case scripted acceptance test**

  Build scripts from each case's declared legal alternatives, not from a universal Tool sequence. At least one clipping case starts with clipping, one harmonic case starts with harmonic analysis, and two equivalent cases reach the same expected outcome through distinct sufficient sets. The test must use real generated signals, Tool service, RuleEngine, profile loader, KnowledgeIndex, and runtime.

- [ ] **Step 2: Add failing same-run, repeatability, and baseline-comparison tests**

  Assert every Evidence/rule/knowledge ref resolves in the same trace. Run twice with injected clock/ID values and compare normalized JSON after excluding measured latency. Run the baseline once for all 24 cases and assert side-by-side aggregates without an Agent-beats-baseline assertion.

- [ ] **Step 3: Run T167–T172 RED**

  Run `python -m pytest tests/evaluation/test_acceptance.py -q`.

- [ ] **Step 4: Implement deterministic dependency and script builders**

  Materialize each case into a fresh repository. Build `SignalToolService`, `RuleEngine`, `YamlRuleProfileLoader`, and `KnowledgeIndex` from package resources. Create `RecordingPlanner(ScriptedPlanner(scripted_steps[case.case_id]))`, inject it into the unchanged runtime, assemble the trace, and score it. Scripts may select any manifest-declared sufficient route; they must request rules and required knowledge only when justified by current context.

- [ ] **Step 5: Implement normalized deterministic comparison**

  In the repeatability test, monkeypatch the existing runtime module's `uuid4`
  symbol with the same deterministic sequence for each run and inject the same
  evaluation clock; this adds no Phase 2 constructor parameter. Normalize only
  clock-derived latency/timestamps and benchmark ID. Do not normalize run IDs,
  diagnosis, actions, Evidence, rules, knowledge, scores, or completion reasons.

- [ ] **Step 6: Run GREEN, cumulative tests, and commit**

  Run focused tests and the full quality suite, then commit:

  ```powershell
  git add src/signal_diag/evaluation/runner.py tests/evaluation/conftest.py tests/evaluation/test_acceptance.py
  git commit -m "feat(evaluation): run deterministic S1 evaluation harness"
  ```

---

### Task 9: Append-Only Evaluation Report Bundle

**Files:**
- Create: `src/signal_diag/evaluation/reporting.py`
- Create: `tests/evaluation/test_reporting.py`
- Modify: `src/signal_diag/evaluation/__init__.py`

**Test IDs:** T173–T174 and report/artifact portion of T181

**Interfaces:**
- Consumes: one validated `BenchmarkReport` and a parent output directory.
- Produces: `write_benchmark_bundle(report: BenchmarkReport, output_dir: Path)
  -> tuple[Path, ...]` with exactly six files.

- [ ] **Step 1: Add failing exact-file and representation-agreement tests**

  Assert exact filenames, frozen CSV header order, one JSONL artifact per scored/unscored slot, required Markdown sections, retained failures/variation, UTF-8/LF/final newline, finite JSON numbers, and agreement on run counts/statuses/aggregates.

- [ ] **Step 2: Add failing immutability, checksum, and redaction tests**

  Assert an existing benchmark directory raises `FileExistsError`; checksums cover the other five files and exclude themselves; no secret fixture, raw response, waveform, NumPy type name, or platform path separator appears.

- [ ] **Step 3: Run T173–T174 RED**

  Run `python -m pytest tests/evaluation/test_reporting.py -q`.

- [ ] **Step 4: Implement canonical serializers and atomic directory creation**

  Create `<output_dir>/<benchmark_id>` with `exist_ok=False`. Use one canonical JSON helper:

  ```python
  def _json_line(value: object) -> str:
      return json.dumps(
          value,
          ensure_ascii=False,
          allow_nan=False,
          sort_keys=True,
          separators=(",", ":"),
      ) + "\n"
  ```

  Render CSV with `lineterminator="\n"` and the exact §48 header. Encode tuple failure codes with `;`. Build run artifacts by matching attempts on execution path/case/slot. Write the five data files, calculate their hashes in filename order, then write `checksums.sha256` last.

- [ ] **Step 5: Run GREEN, cumulative tests, and commit**

  Run focused tests, full pytest, Ruff, mypy, and commit:

  ```powershell
  git add src/signal_diag/evaluation/reporting.py src/signal_diag/evaluation/__init__.py tests/evaluation/test_reporting.py
  git commit -m "feat(evaluation): write immutable benchmark bundles"
  ```

---

### Task 10: Provider-Neutral Official Runner and Operational CLI

**Files:**
- Modify: `src/signal_diag/evaluation/runner.py`
- Create: `src/signal_diag/evaluation/__main__.py`
- Create: `tests/evaluation/test_runner.py`

**Test IDs:** T175–T181

**Interfaces:**
- Consumes: frozen DeepSeek planner configuration, validated dataset/profile, runner dependencies, scorer, aggregator, and writer.
- Produces: private slot/preflight protocols plus the four §49 CLI subcommands. No provider SDK type becomes public.

- [ ] **Step 1: Add failing official-configuration and schedule tests**

  Assert provider/model/prompt/version/hash/model parameters are fully recorded. Assert schedule order is five rounds of the 16 held-out cases (`slot 1` for every case before `slot 2`) and one manifest-order baseline run per case. Assert `max_concurrency == 1`.

- [ ] **Step 2: Add failing retry and status tests with an injected provider fake**

  Parametrize timeout, 429, 5xx, provider-other, authentication, missing credentials/dependency, invalid configuration, invalid model output, planner retry exhaustion, no-progress, and Tool/rule/knowledge budgets. Only the first three infrastructure classes receive at most two retries. Every attempt remains ordered; behavioral outcomes retain their original slot.

- [ ] **Step 3: Add failing append-only and credential-safety CLI tests**

  Once a held-out behavior result exists, rerunning the same benchmark ID must fail. A preflight failure before results produces pending; the same failure after results produces incomplete. Inspect `--help` and report models to assert no API-key argument/field exists.

- [ ] **Step 4: Run T175–T181 RED**

  Run `python -m pytest tests/evaluation/test_runner.py -q`.

- [ ] **Step 5: Implement private preflight and round-robin scheduling**

  Define private protocols for planner construction and transport classification so tests inject fakes. Preflight must validate credentials/dependency/provider/model/prompt SHA/dataset/profile before scheduling. Use the exact schedule:

  ```python
  slots = tuple(
      (case.case_id, run_slot)
      for run_slot in range(1, config.repetitions + 1)
      for case in manifest.cases
      if case.split == "held_out"
  )
  ```

  Retry the same slot only for `timeout`, `rate_limited`, or `provider_5xx`, with total attempts equal to one plus `max_infrastructure_retries`. Never replace a behavior result.

  Compute the official prompt hash from the exact existing
  `signal_diag.agent.planner._SYSTEM_PROMPT` bytes and verify
  `PROMPT_VERSION == "v0.2-s1-planner-4"`; do not duplicate or rewrite the
  prompt. Construct `RealLLMPlanner(provider="deepseek", client=capture_client)`
  with a private client proxy that records response usage before returning the
  unchanged response to the planner. `RecordingPlanner` reads only the proxy's
  validated `ProviderUsage`; when the provider omits usage it records `None`.

- [ ] **Step 6: Implement the four CLI subcommands without exposing secrets**

  `validate-dataset` loads and validates the canonical manifest. `run-deterministic` executes the scripted harness and baseline. `run-real` reads credentials only through the existing environment/provider boundary and writes a new official bundle. `render-report` validates an existing report JSON input and writes only to a new benchmark directory. Use subparsers with explicit path/config arguments and no `--api-key` option.

- [ ] **Step 7: Run GREEN, CLI smoke tests, cumulative tests, and commit**

  Run:

  ```powershell
  python -m pytest tests/evaluation/test_runner.py -q
  python -m signal_diag.evaluation --help
  python -m signal_diag.evaluation validate-dataset --help
  python -m pytest -q
  python -m ruff check .
  python -m mypy src
  ```

  Commit:

  ```powershell
  git add src/signal_diag/evaluation/runner.py src/signal_diag/evaluation/__main__.py tests/evaluation/test_runner.py
  git commit -m "feat(evaluation): add controlled real-model benchmark runner"
  ```

---

### Task 11: Architecture Gate, Documentation, and Full Phase 4 Verification

**Files:**
- Modify: `tests/test_architecture_boundaries.py`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/plans/2026-08-29-phase4-evaluation.md` only to check completed boxes during execution

**Test IDs:** T182–T183 and cumulative T001–T183

**Interfaces:**
- Consumes: all Phase 4 modules and tests.
- Produces: deterministic `harness_accepted` evidence; does not claim `benchmark_completed` unless the separate 80-slot real run and immutable bundle actually exist.

- [x] **Step 1: Add the failing Phase 4 dependency-boundary test**

  Parse imports under `src/signal_diag`. Assert `evaluation` may import Phase 1–3, while `signal`, `dsp`, `tools`, `rules`, `knowledge`, and `agent` never import `signal_diag.evaluation`. Assert `app` remains absent. Remove the former Phase 4 skip; T182 must be a hard gate once the package exists.

- [x] **Step 2: Run T182 RED, then make only boundary-compliant corrections**

  Run `python -m pytest tests/test_architecture_boundaries.py -q`. If it fails, move evaluation-only helpers inward; do not change a frozen Phase 1–3 import to accommodate evaluation.

- [x] **Step 3: Run every focused Phase 4 file with no skips or xfails**

  Run:

  ```powershell
  python -m pytest tests/evaluation tests/test_architecture_boundaries.py -q -rxXs
  ```

  Expected: T125–T182 pass; no required skip/xfail is reported.

- [x] **Step 4: Run the complete deterministic quality gate**

  Run exactly:

  ```powershell
  python -m pytest -q -rxXs
  python -m ruff check .
  python -m mypy src
  git diff --check
  ```

  Expected: T001–T183 pass, zero required skip/xfail, Ruff clean, mypy clean, and no whitespace errors.

- [x] **Step 5: Update documentation with honest dual acceptance status**

  Set Phase 4 deterministic status to `harness_accepted` only after Step 4 passes. Keep real status `benchmark_pending` if credentials/service were unavailable, `incomplete` if infrastructure/evaluator attempts exhausted, or `completed` only with 80 scoreable held-out slots and the six-file bundle. Keep Phase 5 gated unless both harness and benchmark are complete. Record actual commit IDs and exact command outputs; do not convert a target miss into a failure or hide it.

- [x] **Step 6: Commit the final deterministic gate**

  ```powershell
  git add tests/test_architecture_boundaries.py AGENTS.md docs/README.md docs/superpowers/plans/2026-08-29-phase4-evaluation.md
  git commit -m "test(evaluation): enforce Phase 4 acceptance gate"
  ```

- [ ] **Step 7: Request independent code review before any merge**

  Use `superpowers:requesting-code-review` against the full Phase 4 branch. Require explicit review of frozen-interface conformance, trace chronology, no truth leakage, baseline honesty, score formulas, retry/status semantics, report immutability, and Phase 1–3 regression. Apply accepted feedback through `superpowers:receiving-code-review`, rerun Step 4, and commit fixes separately.

## T125–T183 Mapping

| Test range | Implementation task | Primary test file |
|---|---|---|
| T125–T132 | Task 1 models and manifest invariants | `tests/evaluation/test_models.py` |
| T133–T140 | Task 2 packaged dataset and validation | `tests/evaluation/test_dataset.py` |
| T141–T142 | Task 3 transparent planner recording | `tests/evaluation/test_recording.py` |
| T143–T148 | Task 4 chronological trace assembly | `tests/evaluation/test_recording.py` |
| T149–T154 | Task 5 fixed-pipeline baseline | `tests/evaluation/test_baseline.py` |
| T155, T157–T165 | Task 6 per-run scoring | `tests/evaluation/test_scoring.py` |
| T156, T166 | Task 7 aggregate scoring and targets | `tests/evaluation/test_scoring.py` |
| T167–T172 | Task 8 deterministic full-manifest acceptance | `tests/evaluation/test_acceptance.py` |
| T173–T174 | Task 9 report bundle | `tests/evaluation/test_reporting.py` |
| T175–T181 | Tasks 7, 9, and 10 configuration/runner/safety | `tests/evaluation/test_runner.py`, `test_reporting.py`, `test_scoring.py` |
| T182 | Task 11 architecture boundary | `tests/test_architecture_boundaries.py` |
| T183 | Task 11 cumulative gate | full test suite and quality commands |

Explicit coverage inventory:

```text
Task 1: T125 T126 T127 T128 T129 T130 T131 T132
Task 2: T133 T134 T135 T136 T137 T138 T139 T140
Task 3: T141 T142
Task 4: T143 T144 T145 T146 T147 T148
Task 5: T149 T150 T151 T152 T153 T154
Task 6: T155 T157 T158 T159 T160 T161 T162 T163 T164 T165
Task 7: T156 T166 T175
Task 8: T167 T168 T169 T170 T171 T172
Task 9: T173 T174 T181
Task 10: T175 T176 T177 T178 T179 T180 T181
Task 11: T182 T183
```

T175 and T181 intentionally span more than one task: their configuration and
artifact-safety assertions are verified at both the pure-model/report boundary
and the operational runner boundary.

## Expected Local Commit Sequence

```text
feat(evaluation): add frozen Phase 4 models
feat(evaluation): add validated S1 dataset manifest
feat(evaluation): record planner decisions transparently
feat(evaluation): assemble strict chronological traces
feat(evaluation): add honest fixed-pipeline baseline
feat(evaluation): score diagnosis traces deterministically
feat(evaluation): aggregate metrics and target status
feat(evaluation): run deterministic S1 evaluation harness
feat(evaluation): write immutable benchmark bundles
feat(evaluation): add controlled real-model benchmark runner
test(evaluation): enforce Phase 4 acceptance gate
```

Do not squash these commits during implementation. Do not push or merge until independent review and user acceptance.
