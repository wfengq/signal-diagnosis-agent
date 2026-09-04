# V0.3 Contextual Reference Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable three-mode Scenario S1 product path that uses a declared single-tone stimulus or a clean/reference WAV to improve harmonic-distortion attribution without weakening clipping behavior or rewriting V0.2 evidence.

**Architecture:** Preserve the existing one-WAV runtime and DTO meanings, then add typed stimulus context, deterministic contextual DSP, one contextual Tool, versioned rules, v9.5 runtime gates, and separate contextual app/evaluation surfaces. Paired decisions use normalized harmonic growth relative to the reference; nominal decisions are conditional on the declared tone; unknown single-WAV inputs remain conservative.

**Tech Stack:** Python 3.11/3.12, NumPy, Pydantic v2, PyYAML, pytest, Ruff, mypy, FastAPI, native HTML/CSS/JavaScript, existing OpenAI-compatible `RealLLMPlanner` boundary.

**Spec:** `docs/superpowers/specs/2026-09-04-v0-3-contextual-reference-diagnosis-design.md`

## Global Constraints

- Work on `codex/v0.2-real-world-validation`; do not create a replacement branch during execution.
- Use TDD for every behavior change: failing focused test, minimal implementation, focused green run, then commit.
- Preserve Phase 4.3.1 official bundles, V0.2 external bundles, the accepted Demo, v8.1/v9.4 prompt and scoring identities, `profile_s1_distortion` `1.0.0-demo`, and tag `v0.2.0` byte-for-byte.
- Do not change the existing 1% clipping or 5% THD demonstration thresholds.
- Do not send waveform arrays or full FFT arrays to the planner.
- Do not add SciPy or another dependency; bounded alignment uses NumPy only.
- Do not silently resample mismatched WAVs or fall back to `ScriptedPlanner`.
- Use `single_reviewer_provenance_audit`; do not require a second reviewer or a
  delayed blind-review waiting period. Report agreement/kappa as
  `not_evaluated`.
- Do not download public audio, access validation audio, run a real model, commit run artifacts, or push without the specific gate in this plan being authorized.
- Existing untracked `docs/evaluations/v0_2_external_wav/investigation_report_2026-09-02.md` and `docs/evaluations/v0_3/validation/` are user-owned and excluded from implementation commits unless a later task explicitly adopts a new versioned file.
- Every commit stages only the files listed by its task.

## File Structure

New focused modules:

- `src/signal_diag/signal/context.py`: mode and stimulus-provenance models.
- `src/signal_diag/dsp/contextual.py`: pure NumPy qualification, alignment diagnostics, normalized harmonic comparison, and contextual result dataclasses.
- `src/signal_diag/tools/contextual.py`: contextual Tool input/output models and Evidence adapter.
- `src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml`: additive contextual rules.
- `src/signal_diag/app/contextual_models.py`: new contextual submission/snapshot/report DTOs.
- `src/signal_diag/app/contextual_runs.py`: contextual store/executor without changing the frozen V0.2 store model.
- `src/signal_diag/app/contextual_reporting.py`: contextual trace/report assembly and rendering.
- `src/signal_diag/evaluation/contextual/`: contextual manifests, runner, scorer, calibration, sealing, and CLI.

Existing registration/composition points receive small additive changes only:

- `src/signal_diag/tools/contracts.py`, `registry.py`, `service.py`, and exports.
- `src/signal_diag/agent/models.py`, `state.py`, `runtime.py`, `diagnosis.py`, `prompts_v03.py`, `planner.py`, and exports.
- `src/signal_diag/app/service.py`, `composition.py`, `api.py`, `cli.py`, static UI assets, and exports.
- `pyproject.toml` package-data entries only if the new profile is not already covered by the existing wildcard.

---

### Task 1: Freeze V0.3 contextual contracts and test identities

**Files:**
- Create: `docs/CONTRACTS_V0_3_CONTEXTUAL.md`
- Create: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`
- Create: `tests/evaluation/external/test_v03_contextual_preservation.py`

**Interfaces:**
- Consumes: approved design at `docs/superpowers/specs/2026-09-04-v0-3-contextual-reference-diagnosis-design.md`.
- Produces: normative names and T-CX001–T-CX145 test registry used by Tasks 2–12.

- [ ] **Step 1: Write preservation tests T-CX001–T-CX003**

Pin SHA-256 values for the protected V0.2/v9.4 prompt assets, profile file, Demo acceptance manifest, and selected Phase 4.3.1 bundle manifests using the repository's existing preservation helper pattern. Assert that `v0.2.0` still resolves and that its object ID is unchanged.

```python
from hashlib import sha256
from pathlib import Path
import subprocess

from signal_diag.agent.prompts import _S1_PROMPT_V8_1
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_4

ROOT = Path(__file__).resolve().parents[3]
S1_PROFILE = ROOT / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
DEMO_README = ROOT / "docs/demo/phase5/v0_2_acceptance/README.md"
OFFICIAL_MANIFEST = ROOT / "docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/benchmark_manifest.json"

def sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()

def test_t_cx001_frozen_prompt_and_profile_bytes_are_preserved() -> None:
    assert sha256(_S1_PROMPT_V8_1.system_prompt.encode()).hexdigest() == (
        "f2f0a81cc8f36f0301ee67c43e692886e86f9aa9136adeea4d592707133423ca"
    )
    assert sha256(_S1_PROMPT_V9_4.system_prompt.encode()).hexdigest() == (
        "a29c9cda17bd4bf1d922880610609e32f0670b3eecb984a1e3afa16671e806af"
    )
    assert sha256_path(S1_PROFILE) == (
        "1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1"
    )
    assert sha256_path(DEMO_README) == (
        "5771cc72f21123148a1eb16a719189564bd6370f3fffc4bad285aab79da17c55"
    )
    assert sha256_path(OFFICIAL_MANIFEST) == (
        "392a0ccc24ebce3c245a2c5b1a0d859f8a35aa2001ca4245e165a66f983df950"
    )

def test_t_cx003_v0_2_tag_is_unchanged() -> None:
    resolved = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "rev-parse",
            "v0.2.0^{commit}",
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    assert resolved == "ff16e2a59a2c96b89bcb2b28906ede199eb104dc"
```

- [ ] **Step 2: Run the new preservation test and confirm the fixture list is complete**

Run: `python -m pytest tests/evaluation/external/test_v03_contextual_preservation.py -v`

Expected: PASS against the current baseline before any product change.

- [ ] **Step 3: Write the additive contract document**

Copy the approved field names, method signatures, mode validation, DSP result fields, rule IDs, causal gates, endpoint paths, error behavior, and authorization gates into `docs/CONTRACTS_V0_3_CONTEXTUAL.md`. State explicitly that this document extends but does not edit `docs/CONTRACTS_V0_2.md`.

- [ ] **Step 4: Register exact test IDs**

In `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`, allocate:

```text
T-CX001..010  preservation and context contracts
T-CX011..030  deterministic contextual DSP
T-CX031..045  Tool outputs and Evidence
T-CX046..055  contextual rules
T-CX056..075  runtime causal policy
T-CX076..085  v9.5 prompt and composition
T-CX086..105  application service/store/report
T-CX106..120  API/CLI/Web UI
T-CX121..140  evaluation, scoring, calibration, sealing
T-CX141..145  cumulative, packaging, and preservation gates
```

- [ ] **Step 5: Check documentation and commit**

Run: `git diff --check`

Expected: no whitespace errors.

Commit only these three files:

```bash
git add docs/CONTRACTS_V0_3_CONTEXTUAL.md docs/TEST_PLAN_V0_3_CONTEXTUAL.md tests/evaluation/external/test_v03_contextual_preservation.py
git commit -m "docs: freeze V0.3 contextual contracts"
```

### Task 2: Add immutable stimulus-context models

**Files:**
- Create: `src/signal_diag/signal/context.py`
- Modify: `src/signal_diag/signal/__init__.py`
- Create: `tests/signal/test_context.py`

**Interfaces:**
- Consumes: existing signal IDs and `ChannelMode`.
- Produces: `DiagnosticMode`, `ContextAssertionSource`, `StimulusContext`, and `EffectiveCapabilities`.

- [ ] **Step 1: Write failing model tests T-CX004–T-CX010**

Cover all valid modes, forbidden field combinations, finite positive nominal frequency, paired reference requirements, and frozen-model mutation rejection.

```python
def test_t_cx006_nominal_tone_requires_frequency() -> None:
    with pytest.raises(ValidationError):
        StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            assertion_source="user_supplied",
            stimulus_kind="single_tone",
        )

def test_t_cx007_paired_reference_requires_distinct_reference() -> None:
    with pytest.raises(ValidationError):
        StimulusContext(
            mode="paired_reference",
            test_signal_id="sig_same",
            reference_signal_id="sig_same",
            assertion_source="user_supplied",
        )
```

- [ ] **Step 2: Run the model tests and confirm RED**

Run: `python -m pytest tests/signal/test_context.py -v`

Expected: collection failure because `signal_diag.signal.context` does not exist.

- [ ] **Step 3: Implement the exact immutable models**

```python
DiagnosticMode = Literal["single_signal", "nominal_single_tone", "paired_reference"]
ContextAssertionSource = Literal["user_supplied", "evaluation_manifest"]

class StimulusContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    mode: DiagnosticMode
    test_signal_id: str = Field(min_length=1)
    reference_signal_id: str | None = None
    nominal_fundamental_hz: float | None = Field(default=None, gt=0.0)
    stimulus_kind: Literal["single_tone"] | None = None
    assertion_source: ContextAssertionSource

class EffectiveCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    clipping: bool = True
    absolute_harmonic_description: bool = True
    nominal_harmonic_attribution: bool = False
    paired_harmonic_attribution: bool = False
```

Use one `model_validator` to enforce the mode matrix from the contract.

- [ ] **Step 4: Export and run focused tests**

Run: `python -m pytest tests/signal/test_context.py tests/signal/test_repository.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signal_diag/signal/context.py src/signal_diag/signal/__init__.py tests/signal/test_context.py
git commit -m "feat: add contextual stimulus contracts"
```

### Task 3: Implement deterministic contextual DSP

**Files:**
- Create: `src/signal_diag/dsp/contextual.py`
- Modify: `src/signal_diag/dsp/__init__.py`
- Create: `tests/dsp/test_contextual.py`

**Interfaces:**
- Consumes: one-dimensional finite arrays, sample rates, mode, optional nominal F0/reference samples.
- Produces: `analyze_contextual_distortion(...) -> ContextualDistortionAnalysis`.

- [ ] **Step 1: Write RED tests T-CX011–T-CX030**

Use seeded synthetic arrays to cover gain invariance, bounded time shift,
H2/H3 injection, natural-even no-growth control, clipping in test/reference,
sample-rate mismatch, F0 mismatch, unvoiced input, too-short input, and
determinism.

```python
def test_t_cx014_even_harmonic_growth_is_gain_invariant() -> None:
    result = analyze_contextual_distortion(
        test * 0.4,
        48_000,
        mode="paired_reference",
        reference_samples=reference * 0.8,
        reference_sample_rate_hz=48_000,
    )
    assert result.valid
    assert result.even_harmonic_growth_percent == pytest.approx(expected, abs=0.05)

def test_t_cx016_natural_even_reference_has_no_new_growth() -> None:
    result = analyze_contextual_distortion(
        delayed_copy,
        48_000,
        mode="paired_reference",
        reference_samples=natural_even,
        reference_sample_rate_hz=48_000,
    )
    assert result.valid
    assert result.even_harmonic_growth_percent < 0.1
```

- [ ] **Step 2: Run the DSP file and confirm RED**

Run: `python -m pytest tests/dsp/test_contextual.py -v`

Expected: import failure for the new function.

- [ ] **Step 3: Implement result dataclasses and configuration**

```python
CONTEXTUAL_DSP_VERSION = "1.0.0"

@dataclass(frozen=True, slots=True)
class ContextualAnalysisConfig:
    max_lag_s: float = 0.25
    min_alignment_correlation: float = 0.50
    max_f0_relative_delta: float = 0.02
    max_harmonic_order: int = 5
    full_scale_threshold: float = 0.99

@dataclass(frozen=True, slots=True)
class HarmonicGrowthComponent:
    order: int
    reference_relative_amplitude: float
    test_relative_amplitude: float
    positive_growth: float

@dataclass(frozen=True, slots=True)
class ContextualDistortionAnalysis:
    algorithm_version: Literal["1.0.0"]
    mode: Literal["nominal_single_tone", "paired_reference"]
    valid: bool
    invalid_reason: str | None
    test_f0_hz: float | None
    comparison_f0_hz: float | None
    f0_relative_delta: float | None
    alignment_lag_samples: int | None
    alignment_correlation: float | None
    gain_ratio: float | None
    reference_thd_percent: float | None
    test_thd_percent: float | None
    thd_delta_percent: float | None
    even_harmonic_growth_percent: float | None
    test_series_kind: str | None
    components: tuple[HarmonicGrowthComponent, ...]
    reference_clipping_ratio: float | None
    reference_flat_top_detected: bool | None
    test_clipping_ratio: float
    test_flat_top_detected: bool
```

- [ ] **Step 4: Implement pure analysis**

Use existing `analyze_harmonic_distortion` and `analyze_clipping`. Implement
bounded normalized cross-correlation with NumPy FFT, take the best lag only
inside `±round(max_lag_s * sample_rate_hz)`, and estimate gain by least squares
after excluding samples whose absolute amplitude is at least 0.99. Compute:

```python
growth = np.maximum(test_relative - reference_relative, 0.0)
even_growth_percent = 100.0 * float(
    np.sqrt(np.sum(np.square(growth[even_order_mask])))
)
f0_relative_delta = abs(test_f0 - comparison_f0) / comparison_f0
```

The function returns invalid results, not exceptions, for unvoiced/F0/alignment
qualification failures. Programmer errors and malformed numeric parameters
raise `ValueError`.

- [ ] **Step 5: Run focused and existing DSP regression tests**

Run: `python -m pytest tests/dsp/test_contextual.py tests/dsp/test_harmonics.py tests/dsp/test_clipping.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/signal_diag/dsp/contextual.py src/signal_diag/dsp/__init__.py tests/dsp/test_contextual.py
git commit -m "feat: add deterministic contextual DSP"
```

### Task 4: Add the contextual Tool and compact Evidence

**Files:**
- Create: `src/signal_diag/tools/contextual.py`
- Modify: `src/signal_diag/tools/contracts.py`
- Modify: `src/signal_diag/tools/service.py`
- Modify: `src/signal_diag/tools/registry.py`
- Modify: `src/signal_diag/tools/__init__.py`
- Modify: `src/signal_diag/agent/models.py`
- Create: `tests/tools/test_contextual.py`
- Modify: `tests/tools/test_contracts.py`

**Interfaces:**
- Consumes: `StimulusContext`, repository records, and `ContextualDistortionInput`.
- Produces: Tool name `analyze_contextual_distortion`, `ContextualDistortionOutput`, and compact same-run Evidence.

- [ ] **Step 1: Write RED contract and Tool tests T-CX031–T-CX045**

Assert strict schemas, no signal IDs in planner-supplied arguments, correct
reference loading, no waveform arrays in JSON, invalid-result Evidence, and
deterministic IDs.

```python
def test_t_cx034_contextual_tool_args_cannot_choose_signal_ids() -> None:
    schema = ContextualDistortionInput.model_json_schema()
    assert "signal_id" not in schema["properties"]
    assert "reference_signal_id" not in schema["properties"]

def test_t_cx040_output_json_contains_no_raw_arrays(result: ToolResult[object]) -> None:
    payload = result.model_dump_json()
    assert "samples" not in payload
    assert "fft" not in payload.lower()
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m pytest tests/tools/test_contextual.py tests/tools/test_contracts.py -v`

Expected: new imports or literal values fail.

- [ ] **Step 3: Implement contextual contracts**

```python
class ContextualDistortionInput(SignalSelection):
    max_harmonic_order: int = Field(default=5, ge=2, le=10)
    window: Literal["hann", "boxcar"] = "hann"

class HarmonicGrowthComponentOutput(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    order: int = Field(ge=2)
    reference_relative_amplitude: float = Field(ge=0.0)
    test_relative_amplitude: float = Field(ge=0.0)
    positive_growth: float = Field(ge=0.0)

class ContextualDistortionOutput(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    kind: Literal["contextual_distortion"] = "contextual_distortion"
    algorithm_version: Literal["1.0.0"] = "1.0.0"
    mode: Literal["nominal_single_tone", "paired_reference"]
    valid: bool
    invalid_reason: str | None
    test_f0_hz: float | None
    comparison_f0_hz: float | None
    f0_relative_delta: float | None
    alignment_lag_samples: int | None
    alignment_correlation: float | None
    gain_ratio: float | None
    reference_thd_percent: float | None
    test_thd_percent: float | None
    thd_delta_percent: float | None
    even_harmonic_growth_percent: float | None
    test_series_kind: str | None
    components: tuple[HarmonicGrowthComponentOutput, ...]
    reference_clipping_ratio: float | None
    reference_flat_top_detected: bool | None
    test_clipping_ratio: float
    test_flat_top_detected: bool
```

Extend `ToolName`, `ToolOutput`, `ToolInvocation`, and the registry with one new
discriminated member. Add `AnalyzeContextualDistortionCall` whose arguments
contain selection only.

- [ ] **Step 4: Adapt DSP output to Evidence**

`SignalToolService.analyze_contextual_distortion(context, args)` resolves IDs
from the trusted context. Emit scalar Evidence for `context_valid`, mode,
algorithm version, test/comparison F0, `f0_relative_delta`, THD values, THD delta,
`even_harmonic_growth_percent`, `test_series_kind`, alignment diagnostics, and
reference/test clipping metrics. Invalid numeric metrics use
`validity="not_applicable"`; `context_valid=false` remains a valid boolean fact.

- [ ] **Step 5: Run focused Tool and schema tests**

Run: `python -m pytest tests/tools/test_contextual.py tests/tools/test_contracts.py tests/tools/test_service.py -v`

Expected: PASS and unchanged existing Tool behavior.

- [ ] **Step 6: Commit**

```bash
git add src/signal_diag/tools/contextual.py src/signal_diag/tools/contracts.py src/signal_diag/tools/service.py src/signal_diag/tools/registry.py src/signal_diag/tools/__init__.py src/signal_diag/agent/models.py tests/tools/test_contextual.py tests/tools/test_contracts.py
git commit -m "feat: expose contextual comparison evidence"
```

### Task 5: Add contextual rules without changing V0.2 thresholds

**Files:**
- Create: `src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml`
- Modify: `src/signal_diag/app/composition.py`
- Modify: `tests/rules/test_models.py`
- Modify: `tests/rules/test_engine.py`
- Create: `tests/rules/test_contextual_profile.py`

**Interfaces:**
- Consumes: contextual Evidence from Task 4.
- Produces: development candidate profile `profile_s1_contextual_comparison`
  version `1.0.0-dev.1` and rule IDs used by runtime gates. Task 11 freezes
  version `1.0.0` before any real-model run.

- [ ] **Step 1: Write RED tests T-CX046–T-CX055**

Assert that the existing YAML checksum and values remain unchanged, the new
profile loads independently, invalid Evidence yields `not_applicable`, and each
new metric binds to `analyze_contextual_distortion`.

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/rules/test_contextual_profile.py -v`

Expected: profile path not found.

- [ ] **Step 3: Add the profile with development-stage values**

```yaml
profile_id: profile_s1_contextual_comparison
version: 1.0.0-dev.1
description: Contextual S1 comparison limits; demonstration targets, not an industry standard.
rules:
  - rule_id: rule_contextual_analysis_valid
    metric: context_valid
    source_tool: analyze_contextual_distortion
    comparator: eq
    threshold: true
    unit: null
    description: Contextual analysis must be valid.
  - rule_id: rule_contextual_f0_compatible
    metric: f0_relative_delta
    source_tool: analyze_contextual_distortion
    comparator: lte
    threshold: 0.02
    unit: null
    description: Measured and comparison fundamentals differ by at most two percent.
  - rule_id: rule_reference_clipping_ratio_acceptable
    metric: reference_clipping_ratio
    source_tool: analyze_contextual_distortion
    comparator: lte
    threshold: 0.01
    unit: null
    description: Reference clipping ratio is at most the unchanged demo threshold.
  - rule_id: rule_reference_flat_top_absent
    metric: reference_flat_top_detected
    source_tool: analyze_contextual_distortion
    comparator: eq
    threshold: false
    unit: null
    description: Reference has no reliable flat top.
  - rule_id: rule_even_harmonic_growth_acceptable
    metric: even_harmonic_growth_percent
    source_tool: analyze_contextual_distortion
    comparator: lte
    threshold: 1.0
    unit: "%"
    description: Development candidate; frozen by Task 11 before validation.
  - rule_id: rule_nominal_thd_acceptable
    metric: test_thd_percent
    source_tool: analyze_contextual_distortion
    comparator: lte
    threshold: 5.0
    unit: "%"
    description: Reuses, but does not modify, the five-percent demo threshold.
```

The 1.0% growth value is an explicit development candidate, not a validation
target or industry threshold. Task 11 selects the final value once using the
preregistered development-only rule and then changes the profile version to
`1.0.0`.

- [ ] **Step 4: Register both profile paths in product composition**

Keep `_PROFILE_ID = "profile_s1_distortion"`; add
`_CONTEXTUAL_PROFILE_ID = "profile_s1_contextual_comparison"` and pass both
paths to `YamlRuleProfileLoader`.

- [ ] **Step 5: Run rule regressions and commit**

Run: `python -m pytest tests/rules -v`

Expected: PASS.

```bash
git add src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml src/signal_diag/app/composition.py tests/rules/test_models.py tests/rules/test_engine.py tests/rules/test_contextual_profile.py
git commit -m "feat: add contextual distortion rules"
```

### Task 6: Extend the runtime with mode-aware causal gates

**Files:**
- Modify: `src/signal_diag/agent/state.py`
- Modify: `src/signal_diag/agent/models.py`
- Modify: `src/signal_diag/agent/runtime.py`
- Modify: `src/signal_diag/agent/diagnosis.py`
- Create: `tests/agent/test_v03_contextual_runtime.py`

**Interfaces:**
- Consumes: `StimulusContext`, contextual Tool decisions, contextual rules.
- Produces: optional `stimulus_context` input on `DistortionDiagnosisRuntime.run`, explicit `CausalPolicyVersion`, and enforced mode-specific finish semantics.

- [ ] **Step 1: Write RED runtime tests T-CX056–T-CX075**

Cover legal Tool/mode combinations, trusted signal IDs, invalid comparison,
paired harmonic success, paired absolute-THD rejection, nominal conditional
success, nominal mismatch rejection, single-WAV harmonic rejection, independent
clipping success, combined independence, mode-specific `no_supported_fault`,
grounded inconclusive results, and same-run refs.

```python
def test_t_cx064_single_signal_rejects_causal_harmonic_claim() -> None:
    with pytest.raises(DiagnosisValidationError, match="contextual support"):
        validate_finish_decision(
            harmonic_finish,
            stimulus_context=single_context,
            known_evidence_ids=known,
            evidence=evidence,
            rule_evaluations=rules,
        )

def test_t_cx067_paired_claim_requires_growth_rule_fail() -> None:
    with pytest.raises(DiagnosisValidationError, match="harmonic growth"):
        validate_finish_decision(
            harmonic_finish,
            stimulus_context=paired_context,
            known_evidence_ids=known,
            evidence=evidence_without_growth_fail,
            rule_evaluations=rules,
        )
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m pytest tests/agent/test_v03_contextual_runtime.py -v`

Expected: missing keyword/model/tool handling failures.

- [ ] **Step 3: Add context to state and planner context**

Add the policy identity and change the runtime entry additively:

```python
CausalPolicyVersion = Literal["v9_4_legacy", "v9_5_contextual"]

def __init__(
    self,
    *,
    repository: SignalRepository,
    tool_service: SignalToolService,
    planner: PlannerModel,
    limits: AgentLimits = _DEFAULT_LIMITS,
    rule_engine: RuleEngine | None = None,
    rule_profile_loader: RuleProfileLoader | None = None,
    knowledge_index: KnowledgeIndex | None = None,
    causal_policy_version: CausalPolicyVersion = "v9_4_legacy",
) -> None:
    self._repository = repository
    self._tool_service = tool_service
    self._planner = planner
    self._limits = limits
    self._rule_engine = rule_engine
    self._rule_profile_loader = rule_profile_loader
    self._knowledge_index = knowledge_index
    self._causal_policy_version = causal_policy_version
    self._observation_sequence = 0

async def run(
    self,
    *,
    signal_id: str,
    user_request: str,
    stimulus_context: StimulusContext | None = None,
) -> AgentRunResult:
```

When `stimulus_context is None`, construct `single_signal` using `signal_id`.
Reject a context whose `test_signal_id` differs from `signal_id`. Load reference
metadata only for `paired_reference`; return `runtime_error` if the trusted
reference ID does not exist. Add context and optional reference metadata to
`PlannerContext` and `DiagnosisState`.

- [ ] **Step 4: Execute the new Tool only through trusted context**

Handle `AnalyzeContextualDistortionCall` in `_execute_tool`; planner arguments
cannot override test/reference IDs. Reject the call in `single_signal` mode.

- [ ] **Step 5: Implement deterministic finish gates**

In `validate_finish_decision`, retain the clipping gate unchanged. Replace the
v9.4 harmonic branch only for the active v9.5 contextual runtime policy:

Define local validation helpers over the already constructed
`evidence_by_id` and `evaluations_by_id` maps. `require_metric` accepts only a
valid cited Evidence item with the exact metric/value. `require_rule_pass` and
`require_rule_fail` accept only a cited evaluation with the exact rule ID and
judgment. Each helper raises `DiagnosisValidationError` naming the missing gate;
it never searches an uncited same-run item.

```python
if context.mode == "paired_reference":
    require_rule_pass(claim, "rule_contextual_analysis_valid")
    require_rule_pass(claim, "rule_contextual_f0_compatible")
    require_rule_pass(claim, "rule_reference_clipping_ratio_acceptable")
    require_rule_pass(claim, "rule_reference_flat_top_absent")
    require_rule_fail(claim, "rule_even_harmonic_growth_acceptable")
elif context.mode == "nominal_single_tone":
    require_rule_pass(claim, "rule_contextual_analysis_valid")
    require_rule_pass(claim, "rule_contextual_f0_compatible")
    require_metric(claim, "test_series_kind", "even_order_present")
    require_rule_fail(claim, "rule_nominal_thd_acceptable")
else:
    reject_causal_harmonic_claim()
```

Keep a compatibility policy entry point for preserved historical v9.4 tests;
do not reinterpret recorded v9.4 results. The default runtime policy remains
`v9_4_legacy` so historical builders and tests are stable. Only callers that
explicitly select `v9_5_contextual` receive the new mode-aware finish gate.

For `v9_5_contextual`, also enforce negative and unresolved outcomes:

```python
if decision.outcome == "no_supported_fault":
    require_metric(claim, "clipping_mechanism", False)
    require_rule_pass(claim, "rule_clipping_ratio_acceptable")
    require_rule_pass(claim, "rule_flat_top_absent")
    if context.mode == "paired_reference":
        require_rule_pass(claim, "rule_contextual_analysis_valid")
        require_rule_pass(claim, "rule_contextual_f0_compatible")
        require_rule_pass(claim, "rule_reference_clipping_ratio_acceptable")
        require_rule_pass(claim, "rule_reference_flat_top_absent")
        require_rule_pass(claim, "rule_even_harmonic_growth_acceptable")
    elif context.mode == "nominal_single_tone":
        require_rule_pass(claim, "rule_contextual_analysis_valid")
        require_rule_pass(claim, "rule_contextual_f0_compatible")
        require_rule_pass(claim, "rule_nominal_thd_acceptable")
    else:
        require_rule_pass(claim, "rule_harmonic_analysis_valid")
        require_rule_pass(claim, "rule_thd_acceptable")

if decision.outcome == "inconclusive":
    require_nonempty_limitations(decision)
    require_at_least_one_same_run_evidence_or_rule_ref(decision)
```

`clipping_mechanism=true` with no substantial clipping rule failure remains
inconclusive, matching the preserved low-SNR adjudication; it cannot become a
negative no-fault proof.

- [ ] **Step 6: Run runtime and preservation regressions**

Run: `python -m pytest tests/agent/test_v03_contextual_runtime.py tests/agent/test_v03_workstream_c_prompt_policy.py tests/evaluation/external/test_v03_contextual_preservation.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/signal_diag/agent/state.py src/signal_diag/agent/models.py src/signal_diag/agent/runtime.py src/signal_diag/agent/diagnosis.py tests/agent/test_v03_contextual_runtime.py
git commit -m "feat: enforce contextual causal gates"
```

### Task 7: Freeze and wire the v9.5 planner identity

**Files:**
- Modify: `src/signal_diag/agent/prompts_v03.py`
- Modify: `src/signal_diag/agent/planner.py`
- Modify: `src/signal_diag/app/composition.py`
- Modify: `src/signal_diag/app/service.py`
- Create: `tests/agent/test_v03_prompt_v9_5.py`
- Modify: `tests/app/test_service.py`

**Interfaces:**
- Consumes: contextual planner schema and runtime gates.
- Produces: `PROMPT_VERSION = "v0.3-s1-planner-9.5"` and a frozen SHA test.

- [ ] **Step 1: Write RED prompt tests T-CX076–T-CX085**

Assert the exact version, frozen SHA fixture, mode semantics, no numeric
thresholds in prompt prose, no hidden provenance, no ScriptedPlanner fallback,
and preservation of the v9.4 prompt SHA.

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/agent/test_v03_prompt_v9_5.py -v`

Expected: v9.5 identity not found.

- [ ] **Step 3: Add a complete v9.5 prompt spec**

Build v9.5 independently from shared stable fragments plus a complete
contextual-policy fragment. It must instruct:

```text
paired_reference -> use analyze_contextual_distortion; harmonic causality needs valid comparison and harmonic-growth FAIL
nominal_single_tone -> conclusion is conditional on the declaration; F0 must match and THD/even-order gates must pass
single_signal -> high THD/even-order structure is descriptive only; causal harmonic claim is unavailable
clipping -> remains independent and needs mechanism plus substantial clipping FAIL
invalid context -> do not silently downgrade mode; state the limitation
```

- [ ] **Step 4: Freeze SHA and composition identity**

Compute SHA from exact UTF-8 prompt bytes, place it in the test, set
the public product prompt to v9.5, and keep v9.4 constants and tests intact.
Because v9.5 is not the accepted Phase 4 default, retain
`_CERTIFIED_PROMPT_VERSION = "v0.3-s1-planner-9.4"` so the frozen
`phase4_certified_default` field is correctly `False` for v9.5.

Add this defaulted dependency field so existing test builders remain legacy:

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
    causal_policy_version: CausalPolicyVersion = "v9_4_legacy"
```

`build_product_service()` sets it to `"v9_5_contextual"`; every service-created
runtime passes that exact value. Historical evaluation builders that omit the
field continue to use `v9_4_legacy`.

- [ ] **Step 5: Run prompt, planner, runtime, and composition tests**

Run: `python -m pytest tests/agent/test_v03_prompt_v9_5.py tests/agent/test_real_llm_planner.py tests/agent/test_v03_contextual_runtime.py tests/app/test_service.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/signal_diag/agent/prompts_v03.py src/signal_diag/agent/planner.py src/signal_diag/app/composition.py src/signal_diag/app/service.py tests/agent/test_v03_prompt_v9_5.py tests/app/test_service.py
git commit -m "feat: wire V0.3 planner v9.5"
```

### Task 8: Add contextual application service, storage, and reports

**Files:**
- Create: `src/signal_diag/app/contextual_models.py`
- Create: `src/signal_diag/app/contextual_runs.py`
- Create: `src/signal_diag/app/contextual_reporting.py`
- Modify: `src/signal_diag/app/service.py`
- Modify: `src/signal_diag/app/__init__.py`
- Create: `tests/app/test_contextual_models.py`
- Create: `tests/app/test_contextual_runs.py`
- Create: `tests/app/test_contextual_service.py`
- Create: `tests/app/test_contextual_reporting.py`

**Interfaces:**
- Consumes: two bounded WAV inputs, context models, v9.5 runtime.
- Produces: contextual submission/snapshot/report DTOs and `submit_contextual_wav(...)`.

- [ ] **Step 1: Write RED tests T-CX086–T-CX105**

Cover lifecycle invariants, mode validation, separate previews/source summaries,
two-signal cleanup on rollback/eviction/close, provider failure, invalid
reference with continuing clipping capability, and report context disclosure.

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/app/test_contextual_models.py tests/app/test_contextual_runs.py tests/app/test_contextual_service.py tests/app/test_contextual_reporting.py -v`

Expected: contextual app modules do not exist.

- [ ] **Step 3: Implement distinct immutable DTOs**

```python
class ContextualRunSubmission(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_id: str = Field(pattern=r"^run_[0-9a-f]{32}$")
    status: Literal["queued"] = "queued"

class ContextualAppRunSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    run_id: str
    status: AppRunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    user_request: str
    analyzed_channel: ChannelMode
    test_source: SourceSummary
    reference_source: SourceSummary | None
    stimulus_context: StimulusContext
    effective_capabilities: EffectiveCapabilities
    test_preview: WaveformPreview
    planner_identity: PlannerIdentity
    trace_events: tuple[TraceEventView, ...] = ()
    result: AgentRunResult | None = None
    application_error: AppErrorDetail | None = None
```

Implement matching `ContextualDiagnosisReport` schema version `1.0.0`.

- [ ] **Step 4: Implement isolated contextual store/executor**

Mirror the proven lifecycle behavior from `runs.py` using contextual DTOs. Keep
queue limit 4, running limit 1, terminal retention 20, deep-copy boundaries,
and cleanup callbacks. Define `ContextualRunExecutionResult` with
`result`, `trace_events`, and final `effective_capabilities`; completion updates
the queued snapshot with all three. Do not generalize the frozen V0.2 store
during this task.

- [ ] **Step 5: Implement `submit_contextual_wav`**

```python
async def submit_contextual_wav(
    self,
    test_data: bytes,
    *,
    test_filename: str | None,
    mode: Literal["nominal_single_tone", "paired_reference"],
    reference_data: bytes | None,
    reference_filename: str | None,
    nominal_fundamental_hz: float | None,
    stimulus_kind: Literal["single_tone"] | None,
    user_request: str,
    channel: ChannelMode = "mixdown",
) -> ContextualRunSubmission:
```

Load each WAV through `load_wav_bytes`, build separate source and analysis
records, construct trusted context from generated analysis IDs, and submit to
the contextual executor. On any exception, remove every record inserted by the
attempt. Add:

```python
def get_contextual_run(self, run_id: str) -> ContextualAppRunSnapshot:
    return self._contextual_store.get(run_id)

async def wait_for_contextual_terminal(
    self,
    run_id: str,
    *,
    timeout_s: float | None = None,
) -> ContextualAppRunSnapshot:
    waiter = self._contextual_store.wait_for_terminal(run_id)
    if timeout_s is None:
        return await waiter
    return await asyncio.wait_for(waiter, timeout=timeout_s)
```

`aclose()` closes both executors. Queued capabilities reflect what the mode
requests; terminal capabilities are recomputed from `context_valid` Evidence so
an invalid reference never appears as effective paired attribution.

- [ ] **Step 6: Implement report projection**

Render measured Evidence, declared context, effective capabilities, comparison
limitations, and both sources. Refuse report construction when any cited
Evidence/rule/knowledge ID fails same-run resolution.

- [ ] **Step 7: Run app regressions and commit**

Run: `python -m pytest tests/app/test_contextual_*.py tests/app/test_service.py tests/app/test_runs.py tests/app/test_reporting.py -v`

Expected: PASS.

```bash
git add src/signal_diag/app/contextual_models.py src/signal_diag/app/contextual_runs.py src/signal_diag/app/contextual_reporting.py src/signal_diag/app/service.py src/signal_diag/app/__init__.py tests/app/test_contextual_models.py tests/app/test_contextual_runs.py tests/app/test_contextual_service.py tests/app/test_contextual_reporting.py
git commit -m "feat: add contextual application workflow"
```

### Task 9: Expose contextual API, CLI, and Web UI

**Files:**
- Modify: `src/signal_diag/app/multipart.py`
- Modify: `src/signal_diag/app/api.py`
- Modify: `src/signal_diag/app/cli.py`
- Modify: `src/signal_diag/app/static/index.html`
- Modify: `src/signal_diag/app/static/app.js`
- Modify: `src/signal_diag/app/static/styles.css`
- Modify: `tests/app/test_api.py`
- Modify: `tests/app/test_cli.py`
- Modify: `tests/app/test_ui.py`
- Modify: `tests/app/test_packaging.py`

**Interfaces:**
- Consumes: Task 8 service and DTOs.
- Produces: contextual routes, CLI source form, and optional UI mode fields.

- [ ] **Step 1: Write RED adapter tests T-CX106–T-CX120**

Test the exact API paths, two per-file 20 MiB limits, bounded aggregate body,
duplicate/missing fields, CLI mode matrix, original `diagnose wav` behavior,
UI accessibility labels, conditional field visibility, sanitized errors, and
absence of browser-side diagnosis calculations.

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/app/test_api.py tests/app/test_cli.py tests/app/test_ui.py tests/app/test_packaging.py -v`

Expected: contextual route/arguments/controls are missing.

- [ ] **Step 3: Implement bounded multipart parsing and routes**

Add `parse_contextual_wav_upload(...)` with fields `test_file`, optional
`reference_file`, `mode`, optional nominal frequency/stimulus kind,
`user_request`, and `channel`. Expose:

```text
POST /api/v1/contextual-runs/wav
GET  /api/v1/contextual-runs/{run_id}
GET  /api/v1/contextual-runs/{run_id}/report.json
GET  /api/v1/contextual-runs/{run_id}/report.html
```

- [ ] **Step 4: Implement the CLI source form**

Add:

```text
signal-diag diagnose contextual TEST_PATH \
  --mode paired_reference \
  --reference REFERENCE_PATH

signal-diag diagnose contextual TEST_PATH \
  --mode nominal_single_tone \
  --stimulus-kind single_tone \
  --nominal-fundamental-hz 440
```

Reuse `_read_wav_path`, service waiting, and report renderers. Reject invalid
mode/flag combinations before submission.

- [ ] **Step 5: Implement progressive UI fields**

Default to unknown one-WAV mode. Reveal nominal frequency only for declared
single tone and reveal reference upload for paired mode. Display declaration,
comparison qualification, and limitation sections separately from Evidence.

- [ ] **Step 6: Run adapter tests and commit**

Run: `python -m pytest tests/app -v`

Expected: PASS.

```bash
git add src/signal_diag/app/multipart.py src/signal_diag/app/api.py src/signal_diag/app/cli.py src/signal_diag/app/static/index.html src/signal_diag/app/static/app.js src/signal_diag/app/static/styles.css tests/app/test_api.py tests/app/test_cli.py tests/app/test_ui.py tests/app/test_packaging.py
git commit -m "feat: expose contextual diagnosis in app adapters"
```

### Task 10: Build an isolated contextual evaluation harness

**Files:**
- Create: `src/signal_diag/evaluation/contextual/__init__.py`
- Create: `src/signal_diag/evaluation/contextual/models.py`
- Create: `src/signal_diag/evaluation/contextual/manifest.py`
- Create: `src/signal_diag/evaluation/contextual/runner.py`
- Create: `src/signal_diag/evaluation/contextual/scoring.py`
- Create: `src/signal_diag/evaluation/contextual/calibration.py`
- Create: `src/signal_diag/evaluation/contextual/sealing.py`
- Create: `src/signal_diag/evaluation/contextual/__main__.py`
- Create: `tests/evaluation/contextual/` matching the modules above

**Interfaces:**
- Consumes: contextual runtime/service, existing external provenance and transform records where their public contracts apply.
- Produces: contextual manifests, three-arm one-shot execution, fixed metrics, calibration records, and append-only seals.

- [ ] **Step 1: Write RED tests T-CX121–T-CX140**

Cover exact 20-case role counts, 17 scoreable cases, mode distribution, source
and master leakage, SHA checks, fixed denominators, three arms, single execution,
failure-as-incorrect scoring, natural-even FP, harmonic/clipping precision and
recall, 5/6 inconclusive appropriateness, unnecessary tools, ablation delta,
and bundle verification.

```python
def test_t_cx124_validation_distribution_is_exact(manifest: ContextualManifest) -> None:
    assert len(manifest.cases) == 20
    assert sum(case.scoreable for case in manifest.cases) == 17
    assert Counter(case.mode for case in manifest.cases) == {
        "paired_reference": 10,
        "nominal_single_tone": 4,
        "single_signal": 6,
    }

def test_t_cx132_ablation_uses_same_test_sha(manifest: ContextualManifest) -> None:
    for slot in manifest.paired_harmonic_slots:
        assert slot.contextual.test_wav_sha256 == slot.ablation.test_wav_sha256
```

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/evaluation/contextual -v`

Expected: package import failure.

- [ ] **Step 3: Implement strict models and manifest validation**

Use frozen Pydantic models with `extra="forbid"`. Each case stores case ID,
mode, role, expected outcome/causal set, confidence tier, source/license fields,
test/reference SHA, parent master, recording key, transform identity, and the
three planned arm slots. Reject any exact identity or lineage leakage across
development and validation.

- [ ] **Step 4: Implement runner and scoring**

The contextual Agent arm determines target status. The fixed pipeline applies
the same deterministic gates without planner decisions. The no-context arm
uses v9.5 `single_signal` on the identical test SHA. Infrastructure failures
occupy their frozen denominators as incorrect. Empty required refs fail
grounding. A zero prediction denominator returns `not_evaluated`, never zero.

- [ ] **Step 5: Implement development-only calibration**

Evaluate candidate even-growth thresholds `(0.5, 1.0, 2.0, 3.0, 5.0)` percent.
Select the largest candidate with 100% specificity on development no-growth
controls and at least 90% sensitivity on development harmonic-bearing
positives. If none qualifies, emit `calibration_status="blocked"` and stop.
Persist all candidates, confusion counts, selected value, source manifest SHA,
and code SHA.

- [ ] **Step 6: Implement seal and verify**

The seal covers manifest, WAV checksums, source decisions, product code SHA,
prompt SHA, both profile SHAs, scoring identity, slot plan, and execution
counters. Verification rejects missing, changed, or duplicate artifacts and
does not read planner credentials.

- [ ] **Step 7: Run contextual evaluation tests**

Run: `python -m pytest tests/evaluation/contextual -v`

Expected: PASS.

- [ ] **Step 8: Run the preliminary offline cumulative gate**

Run:

```text
python -m pytest -v
python -m ruff check .
python -m mypy src
python -m pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py -v
git diff --check 605c8a8
```

Expected: all PASS. This establishes pre-data implementation readiness, not
formal code acceptance or experimental success.

- [ ] **Step 9: Commit**

```bash
git add src/signal_diag/evaluation/contextual/__init__.py src/signal_diag/evaluation/contextual/models.py src/signal_diag/evaluation/contextual/manifest.py src/signal_diag/evaluation/contextual/runner.py src/signal_diag/evaluation/contextual/scoring.py src/signal_diag/evaluation/contextual/calibration.py src/signal_diag/evaluation/contextual/sealing.py src/signal_diag/evaluation/contextual/__main__.py tests/evaluation/contextual/test_models.py tests/evaluation/contextual/test_manifest.py tests/evaluation/contextual/test_runner.py tests/evaluation/contextual/test_scoring.py tests/evaluation/contextual/test_calibration.py tests/evaluation/contextual/test_sealing.py tests/evaluation/contextual/test_cli.py
git commit -m "feat: add contextual evaluation harness"
```

### Task 11: Construct contextual development data and freeze parameters

**Authorization gate:** Stop before this task until the user authorizes public-source download and development data construction. This authorization does not permit a real-model run.

**Files:**
- Create: `docs/evaluations/v0_3/contextual/protocol/source_catalog.json`
- Create: `docs/evaluations/v0_3/contextual/protocol/source_decision_record.md`
- Create: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/`
- Modify once: `src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml` to freeze version `1.0.0` and the selected value
- Create: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/calibration_report.json`

**Interfaces:**
- Consumes: licensed public sources and Task 10 calibration.
- Produces: exactly 20 development cases, qualification report, selected profile SHA, and no model outputs.

- [ ] **Step 1: Review candidate sources without downloading**

Record official source page, original paper/repository, license text, download
size, format, label meaning, and S1 role. Reject any source whose redistribution
or provenance is unclear. Record whether speech or environmental recordings
carry identifiable personal information; exclude material that cannot be
lawfully redistributed or safely represented by metadata/checksums. Do not map
third-party machine-fault labels to S1.

- [ ] **Step 2: Obtain explicit download authorization, then cache privately**

Download only approved files to `private/contextual_wav/`. Record URL, retrieval
time, bytes, and SHA-256. Do not commit provider credentials, cookies, or full
archives.

- [ ] **Step 3: Materialize exactly 20 development cases**

Use at least four masters and the exact validation-shaped distribution: ten
paired cases (clean 1, clipping 2, harmonic 2, combined 2, natural-even control
2, invalid comparison 1), four nominal cases (clean 1, clipping 1, harmonic 1,
frequency mismatch 1), and six single cases (clean 1, clipping 1, controlled
inconclusive 1, public domain-out inconclusive 3). A parent master contributes
at most two positive cases. Store clean and degraded pair links, transform
parameters, filenames, WAV properties, checksums, confidence tiers, and
source/license references. Keep all derivatives of one master inside
development.

- [ ] **Step 4: Run deterministic qualification and calibration once**

Run the contextual harness `qualify-development` then `calibrate`. If calibration
is blocked, retain the report and stop; do not widen candidates or relabel cases
without a written amendment.

- [ ] **Step 5: Freeze profile and rerun deterministic qualification**

Update only the new contextual profile from `1.0.0-dev.1` to `1.0.0`, write the
selected threshold even when it remains 1.0%, record old/new SHA and selection
evidence, then rerun qualification. Require all 20 slots to be materialized and
every positive to pass its intended deterministic causal gate.

- [ ] **Step 6: Run focused and full static checks, then commit only approved data/provenance**

Run: `python -m pytest tests/evaluation/contextual tests/rules/test_contextual_profile.py -v`

Expected: PASS.

Commit the catalog, decision record, development manifests/derived WAVs,
qualification/calibration reports, and optional contextual profile change.
Do not commit the private cache.

### Task 12: Run cumulative product and packaging acceptance

**Files:**
- Create: `docs/evaluations/v0_3/contextual/CONTEXTUAL_CODE_ACCEPTANCE_REPORT.md`

**Interfaces:**
- Consumes: Tasks 1–11.
- Produces: code/harness acceptance decision; no experimental target claim.

- [ ] **Step 1: Run focused contextual suite**

Run: `python -m pytest tests/signal/test_context.py tests/dsp/test_contextual.py tests/tools/test_contextual.py tests/rules/test_contextual_profile.py tests/agent/test_v03_contextual_runtime.py tests/agent/test_v03_prompt_v9_5.py tests/app/test_contextual_*.py tests/evaluation/contextual -v`

Expected: all PASS, zero skip/xfail.

- [ ] **Step 2: Run cumulative quality gates T-CX141–T-CX145**

```text
python -m pytest -v
python -m ruff check .
python -m mypy src
python -m pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py -v
git diff --check 605c8a8
```

Expected: all PASS; no protected asset drift.

- [ ] **Step 3: Run packaging gates**

Build the wheel, inspect it for the new YAML/static assets and absence of raw
private audio, then run clean-environment smoke tests under locally available
CPython 3.11 and 3.12. Missing one interpreter is a release-gate failure, not a
silent skip.

- [ ] **Step 4: Write the code-acceptance report**

Record exact commands, versions, pass counts, commit SHA, prompt/profile SHAs,
preservation SHAs, and any warnings. State `harness_complete` separately from
experimental success.

- [ ] **Step 5: Commit**

```bash
git add docs/evaluations/v0_3/contextual/CONTEXTUAL_CODE_ACCEPTANCE_REPORT.md
git commit -m "docs: record contextual code acceptance"
```

### Task 13: Run one-shot real-model development confirmation

**Authorization gate:** Stop until the user separately authorizes exactly 20 development cases with `RealLLMPlanner`. This authorization does not permit validation access.

**Files:**
- Create: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/agent_v9_5_dev_run/`

**Interfaces:**
- Consumes: frozen code, prompt, profiles, manifest, and development seal.
- Produces: 20 unique real-model attempts and an audited development result.

- [ ] **Step 1: Preflight without invoking the model**

Verify code/prompt/profile/manifest SHAs, credentials presence without printing
them, 20 unique decision indices, zero prior v9.5 output slots, and no validation
paths in the resolved manifest.

- [ ] **Step 2: Execute each development slot exactly once**

Use `RealLLMPlanner`; set `scripted_planner_fallback=false`; write attempts,
trace, result, and case summary atomically per slot. Stop on infrastructure
failure according to the frozen runner policy; do not retry a behavioral
failure.

- [ ] **Step 3: Audit and score**

Recompute outcomes, causal sets, grounding, unsupported claims, tool use, mode
gates, and denominators from raw traces. Check 20 unique cases and no duplicate
decision indices.

- [ ] **Step 4: Preserve the result and stop at the gate**

If development targets fail, record `below_target` and stop. If they pass,
record `development_confirmed`; this still does not authorize validation.

- [ ] **Step 5: Commit only after explicit artifact-commit authorization**

Stage only `agent_v9_5_dev_run/`; scan for credentials and raw provider payloads
before committing.

### Task 14: Preregister, construct, seal, and run contextual validation

**Authorization gates:** Validation protocol review, public-source download, validation construction, validation seal, and real-model execution are separate approvals. Never combine them into one inferred authorization.

**Files:**
- Create: `docs/evaluations/v0_3/contextual/validation/EV_CX_VALIDATION_PROTOCOL_PREREGISTRATION.md`
- Create: `docs/evaluations/v0_3/contextual/validation/acceptance_targets.json`
- Create: `docs/evaluations/v0_3/contextual/validation/slot_plan.json`
- Create after construction authorization: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/`

**Interfaces:**
- Consumes: development-confirmed frozen identities.
- Produces: reviewed protocol, 20 disjoint cases, append-only seal, contextual/fixed/ablation results, and `meets_target` or `below_target`.

- [ ] **Step 1: Write and review the new preregistration**

Freeze the exact 10/4/6 mode distribution, five/4/3/2/6 outcome roles, 17
scoreable cases, all numerator/denominator formulas, role hard gates, three-arm
execution order, infrastructure treatment, and anti-tuning stop rules. Preserve
the current single-WAV EV-C036 draft rather than rewriting it into this study.
Record review mode `single_reviewer_provenance_audit` and agreement/kappa as
`not_evaluated`; add no artificial waiting gate.

- [ ] **Step 2: After construction authorization, materialize disjoint assets**

Require no match with development or V0.2 sealed final on WAV SHA, parent
master, source recording key, session/environment family, or transform lineage.
Run deterministic qualification; stop on any role/count/ground-truth failure.

- [ ] **Step 3: Seal before any model access**

Seal the manifest, all WAVs, source/license records, code/prompt/profile/scoring
identities, arm plan, and empty execution ledger. Verify the seal independently.

- [ ] **Step 4: After real-model authorization, run all preregistered arms once**

Execute contextual Agent, fixed pipeline, and v9.5 no-context ablation without
changing code, prompt, profiles, labels, or order between arms. Retain every
attempt and infrastructure failure.

- [ ] **Step 5: Verify and classify target status**

Recompute metrics from traces and apply every aggregate and role hard gate.
Write `meets_target` only if all required gates pass; otherwise write
`below_target`. Never rerun slots to improve the result.

### Task 15: Publish an honest case study and resume-safe evidence summary

**Authorization gate:** Documentation may be updated only after the validation bundle verifies and the user authorizes presentation work.

**Files:**
- Modify: `docs/PROJECT_CASE_STUDY.md`
- Create: `docs/evaluations/v0_3/contextual/CONTEXTUAL_VALIDATION_REPORT.md`
- Create: `docs/evaluations/v0_3/contextual/RESUME_EVIDENCE.md`

**Interfaces:**
- Consumes: verified frozen bundle only.
- Produces: reproducible report and claims whose numbers match bundle denominators.

- [ ] **Step 1: Generate the report from frozen metrics**

Include dataset composition, mode/source/confidence stratification, Agent versus
fixed pipeline, contextual versus no-context ablation, grounding, unsupported
claims, unnecessary tools, limitations, and all failed cases.

- [ ] **Step 2: Write status-dependent resume language**

For `meets_target`, state that a small preregistered external/contextual study
met its frozen demonstration targets. For `below_target`, state that the system
implemented and evaluated paired-reference diagnosis and report the actual
result without implying target attainment.

- [ ] **Step 3: Run integrity checks**

Verify every displayed numerator/denominator against bundle JSON, scan for
claims of industrial validation/production readiness, and run preservation plus
`git diff --check`.

- [ ] **Step 4: Commit and stop before push**

Commit only the report/case-study/resume files. Push requires separate explicit
authorization.

## Execution checkpoints

The default execution may proceed through Tasks 1–10 and their preliminary
offline cumulative gate without network or model calls. Task 11 requires
public-source download and development-construction authorization; Task 12 is
the formal post-data code/package acceptance. Task 13 requires real-model
development authorization. Task 14 has separate protocol, construction, seal,
and real-model validation approvals. Task 15 requires presentation-update
authorization. At every checkpoint, report current commit SHAs, test evidence,
untracked files, and whether protected assets remain unchanged.
