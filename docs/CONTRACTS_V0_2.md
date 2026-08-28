# Signal Diagnosis Agent — Frozen Contracts V0.2

**Document:** `CONTRACTS_V0_2.md`  
**Contract version:** `0.2`  
**Status:** Frozen for Phase 1–3
**Scope:** Phase 1 deterministic foundation, Phase 2 hybrid Agent runtime, and
Phase 3 rules/knowledge contracts
**Architecture:** `docs/ARCHITECTURE_V0_2.md`  

---

## 1. Contract Policy

This document defines the public Python surface for V0.2. Sections 2–31 are
frozen for Phase 1–2. Sections 32–40 were approved on 2026-08-28 and are frozen
for Phase 3.

After approval, implementation must not silently rename modules, classes,
functions, arguments, return types, statuses, or waveform conventions.

If a genuine correctness problem is found:

1. do not silently work around the contract;
2. record the issue in `docs/OPEN_QUESTIONS.md`;
3. propose the smallest correction and its test impact;
4. obtain explicit approval before changing the public surface.

Private helpers remain implementation details. Phase 4–5 interfaces remain
unfrozen. Phase 3 interfaces are frozen in §32–§40.

---

## 2. Runtime Baseline

V0.2 targets:

- Python 3.11 or newer;
- NumPy arrays for numerical signal data;
- Pydantic V2 models for validated structured contracts;
- `dataclass(frozen=True, slots=True)` for numerical result containers where
  Pydantic serialization is not required.

Provider-specific LLM and orchestration types must not appear in these public
contracts.

---

## 3. Required Package Layout

### 3.1 Phase 1–2 layout (frozen)

```text
src/signal_diag/
├── signal/
│   ├── __init__.py
│   ├── models.py
│   ├── exceptions.py
│   ├── factory.py
│   ├── repository.py
│   ├── segment.py
│   └── synthetic.py
├── dsp/
│   ├── __init__.py
│   ├── models.py
│   ├── preprocess.py
│   ├── clipping.py
│   ├── spectrum.py
│   ├── pitch.py
│   └── harmonics.py
├── tools/
│   ├── __init__.py
│   ├── contracts.py
│   ├── results.py
│   ├── evidence.py
│   ├── service.py
│   └── registry.py
└── agent/
    ├── __init__.py
    ├── models.py
    ├── planner.py
    ├── state.py
    ├── policies.py
    ├── diagnosis.py
    ├── runtime.py
    └── demo.py
```

`agent/` is part of the frozen Phase 2 contract. No `evaluation/` or `app/`
implementation is part of the Phase 1–2 contract.

### 3.2 Phase 3 additions (frozen)

```text
src/signal_diag/
├── rules/
│   ├── __init__.py
│   ├── models.py
│   ├── engine.py
│   └── profiles/
│       └── s1_distortion_v1.yaml
└── knowledge/
    ├── __init__.py
    ├── models.py
    ├── index.py
    └── corpus/
        └── *.md
```

`rules/` and `knowledge/` are created only in Phase 3. They must not import
`agent/`, LLM frameworks, or orchestration libraries.

---

## 4. Shared Signal Types

Location: `signal/models.py`

```python
from typing import Literal

SourceType = Literal[
    "wav",
    "pcm",
    "csv",
    "generated",
]

ChannelMode = Literal[
    "left",
    "right",
    "mixdown",
]

FaultLabel = Literal[
    "clipping",
    "harmonic_distortion",
    "noise",
]
```

### 4.1 `TimeRange`

```python
class TimeRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_s: float = Field(default=0.0, ge=0.0)
    end_s: float | None = Field(default=None, gt=0.0)
```

Semantic validation requires `end_s > start_s` when `end_s` is supplied. The
interval is left-closed and right-open: `[start_s, end_s)`.

### 4.2 `SignalMeta`

```python
class SignalMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_id: str = Field(min_length=1)
    source_type: SourceType
    filename: str | None = None
    sample_rate_hz: int = Field(gt=0)
    channels: int = Field(gt=0)
    num_samples: int = Field(gt=0)
    duration_s: float = Field(gt=0.0)
    original_dtype: str
    amplitude_unit: str = "FS"
```

`duration_s` equals `num_samples / sample_rate_hz` for the canonical record.
Direct `SignalMeta` construction rejects a duration inconsistent with those
fields beyond absolute tolerance `1e-12`.

### 4.3 `SignalRecord`

```python
@dataclass(frozen=True, slots=True)
class SignalRecord:
    meta: SignalMeta
    samples: np.ndarray
```

Canonical samples are contiguous `float32` with shape `(num_samples, channels)`.
Dataclass freezing alone does not make an ndarray immutable; repository behavior
in Section 8 provides the storage guarantee.

Direct `SignalRecord` construction validates dtype, rank, contiguity, finiteness,
and agreement with `meta.num_samples` and `meta.channels`. Non-canonical direct
construction raises `InvalidSignalError`. A factory-created record may remain
writable until inserted into a repository.

---

## 5. Signal Exceptions

Location: `signal/exceptions.py`

```python
class SignalError(Exception):
    """Base signal-domain exception."""

class SignalNotFoundError(SignalError):
    pass

class InvalidSignalError(SignalError):
    pass

class InvalidTimeRangeError(SignalError):
    pass

class UnsupportedChannelError(SignalError):
    pass
```

Scientifically inapplicable DSP results are represented in result models and
Tool status; they are not signal-domain exceptions in V0.2.

---

## 6. Signal Factory

Location: `signal/factory.py`

```python
def build_signal_record(
    samples: np.ndarray,
    *,
    sample_rate_hz: int,
    source_type: SourceType,
    filename: str | None = None,
    signal_id: str | None = None,
) -> SignalRecord:
    ...
```

Required behavior:

1. reject non-positive sample rates;
2. reject empty arrays, NaN, and infinity;
3. accept `(N,)` and `(N, C)` only;
4. convert `(N,)` to `(N, 1)`;
5. preserve `original_dtype` in metadata;
6. convert signed integer PCM by dividing by `2 ** (bits - 1)`;
7. cast floating input to `float32` without peak normalization;
8. return an owned, C-contiguous `float32` array;
9. compute all shape-derived metadata rather than trusting caller metadata;
10. generate an ID beginning with `sig_` when no ID is supplied.

Unsigned PCM conversion is outside Phase 1–2 scope and must raise
`InvalidSignalError` rather than guess an offset convention.

---

## 7. Repository Contract

Location: `signal/repository.py`

```python
class SignalRepository(ABC):
    @abstractmethod
    def put(self, record: SignalRecord) -> None: ...

    @abstractmethod
    def get(self, signal_id: str) -> SignalRecord: ...

    @abstractmethod
    def exists(self, signal_id: str) -> bool: ...

    @abstractmethod
    def remove(self, signal_id: str) -> None: ...

    @abstractmethod
    def list_meta(self) -> list[SignalMeta]: ...

class InMemorySignalRepository(SignalRepository):
    ...
```

Required behavior:

- `put()` copies waveform storage and metadata;
- `get()` returns an immutable snapshot that cannot mutate repository-owned
  storage even if the caller manipulates ndarray flags;
- every returned sample array has `writeable is False`;
- mutating the source record after `put()` does not affect the repository;
- `get()` and `remove()` raise `SignalNotFoundError` for missing IDs;
- `exists()` returns `False` for missing IDs;
- `list_meta()` returns metadata only and preserves insertion order;
- inserting an existing `signal_id` replaces the prior record atomically.

---

## 8. Segment and Channel Extraction

Location: `signal/segment.py`

```python
def extract_segment(
    record: SignalRecord,
    *,
    time_range: TimeRange | None = None,
    channel: ChannelMode = "mixdown",
) -> np.ndarray:
    ...
```

Required behavior:

- output is a writable one-dimensional `float32` copy;
- time indices use `round(time_s * sample_rate_hz)`;
- an omitted end means the record end;
- an end beyond duration is clamped to the record end;
- a start at or beyond duration is invalid;
- empty or reversed ranges raise `InvalidTimeRangeError`;
- mono returns channel 0 for `left` and `mixdown`;
- mono `right` raises `UnsupportedChannelError`;
- stereo `left` and `right` select channels 0 and 1;
- `mixdown` averages all available channels using floating arithmetic;
- `left` or `right` on records with more than two channels is unsupported;
- no returned array exposes repository backing storage.

---

## 9. Synthetic Ground Truth

Location: `signal/synthetic.py`

```python
GroundTruthValue = (
    str
    | int
    | float
    | bool
    | dict[str, float]
)

class SyntheticGroundTruth(BaseModel):
    model_config = ConfigDict(frozen=True)

    generator: str
    fault_labels: tuple[FaultLabel, ...] = ()
    parameters: dict[str, GroundTruthValue]

@dataclass(frozen=True, slots=True)
class SyntheticCase:
    record: SignalRecord
    ground_truth: SyntheticGroundTruth
```

Fault labels contain no duplicates and use stable order:
`clipping`, `harmonic_distortion`, then `noise` when applicable.

All generator parameter dictionaries contain `sample_rate_hz` and `duration_s`.
Additional required keys are:

| Generator | Required parameter keys |
|---|---|
| `sine` | `frequency_hz`, `amplitude`, `phase_rad`, `dc_offset` |
| `clipped_sine` | `frequency_hz`, `input_amplitude`, `clip_level` |
| `harmonic_sine` | `fundamental_hz`, `fundamental_amplitude`, `harmonic_ratios` |
| `combined_distortion` | `fundamental_hz`, `fundamental_amplitude`, `harmonic_ratios`, `clip_level` |
| `white_noise` | `rms`, `seed` |

`harmonic_ratios` is stored in ground truth with decimal order strings such as
`{"2": 0.1, "3": 0.05}` so the model remains JSON-serializable.

### 9.1 Clean sine

```python
def generate_sine(
    *,
    frequency_hz: float,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    amplitude: float = 0.5,
    phase_rad: float = 0.0,
    dc_offset: float = 0.0,
) -> SyntheticCase:
    ...
```

Uses `amplitude * sin(2πft + phase_rad) + dc_offset`. Ground truth generator is
`sine`, and `fault_labels` is empty.

### 9.2 Clipped sine

```python
def generate_clipped_sine(
    *,
    frequency_hz: float,
    clip_level: float,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    amplitude: float = 0.9,
) -> SyntheticCase:
    ...
```

Uses symmetric hard clipping and requires `0 < clip_level <= 1`. Ground truth
generator is `clipped_sine` with fault label `clipping`.

### 9.3 Harmonic-distortion sine

```python
def generate_harmonic_sine(
    *,
    fundamental_hz: float,
    harmonic_ratios: dict[int, float],
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    fundamental_amplitude: float = 0.5,
) -> SyntheticCase:
    ...
```

For harmonic order `k`, amplitude is `fundamental_amplitude *
harmonic_ratios[k]`. Orders must be integers of at least 2, ratios must be
non-negative, and at least one ratio must be positive. The generator performs no
normalization or clipping. Ground truth generator is `harmonic_sine` with fault
label `harmonic_distortion`.

### 9.4 Combined distortion

```python
def generate_combined_distortion(
    *,
    fundamental_hz: float,
    harmonic_ratios: dict[int, float],
    clip_level: float,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    fundamental_amplitude: float = 0.9,
) -> SyntheticCase:
    ...
```

Builds the harmonic waveform and then applies symmetric hard clipping. Ground
truth generator is `combined_distortion` with fault labels `clipping` and
`harmonic_distortion` in that order.

### 9.5 White noise

```python
def generate_white_noise(
    *,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    rms: float = 0.1,
    seed: int = 0,
) -> SyntheticCase:
    ...
```

Uses `np.random.default_rng(seed)`, requires positive RMS, and does not normalize
each generated realization to exact RMS. Ground truth generator is `white_noise`
with fault label `noise`.

All generators reject non-positive duration, sample rate, or required frequency.
The sample count is `round(duration_s * sample_rate_hz)` and must be positive.

---

## 10. DSP Result Models

Location: `dsp/models.py`

```python
@dataclass(frozen=True, slots=True)
class ClippingAnalysis:
    detected: bool
    clipping_ratio: float
    clipped_samples: int
    clipping_events: int
    longest_event_samples: int
    peak_abs: float
    full_scale_detected: bool
    flat_top_detected: bool

@dataclass(frozen=True, slots=True)
class SpectrumPeak:
    frequency_hz: float
    magnitude_db: float

@dataclass(frozen=True, slots=True)
class FFTAnalysis:
    frequencies_hz: np.ndarray
    magnitude_db: np.ndarray
    frequency_resolution_hz: float
    dominant_frequency_hz: float | None
    dominant_magnitude_db: float | None
    spectral_centroid_hz: float | None
    peaks: tuple[SpectrumPeak, ...]

@dataclass(frozen=True, slots=True)
class F0Estimate:
    f0_hz: float | None
    confidence: float
    voiced: bool
    method: str

@dataclass(frozen=True, slots=True)
class HarmonicComponent:
    order: int
    target_frequency_hz: float
    measured_frequency_hz: float
    relative_amplitude: float
    relative_magnitude_db: float

@dataclass(frozen=True, slots=True)
class HarmonicAnalysis:
    valid: bool
    invalid_reason: str | None
    fundamental_frequency_hz: float | None
    fundamental_amplitude: float | None
    thd_percent: float | None
    max_harmonic_order: int
    frequency_resolution_hz: float
    components: tuple[HarmonicComponent, ...]
```

For valid harmonic analysis:

```text
THD percent = 100 * sqrt(sum(A_k^2 for k=2..K)) / A_1
```

where `A_1` and `A_k` are deterministic spectral amplitude estimates. When a
stable supported fundamental cannot be established, `valid=False`, numeric
fundamental/THD fields are `None`, and `invalid_reason` is non-empty.

---

## 11. DSP Preprocessing

Location: `dsp/preprocess.py`

```python
def remove_dc(samples: np.ndarray) -> np.ndarray: ...
def rms(samples: np.ndarray) -> float: ...
def peak_abs(samples: np.ndarray) -> float: ...
```

Inputs must be finite, non-empty, and one-dimensional. Functions do not mutate
caller data.

---

## 12. Clipping Analysis

Location: `dsp/clipping.py`

```python
def analyze_clipping(
    samples: np.ndarray,
    *,
    full_scale_threshold: float = 0.99,
    min_consecutive_samples: int = 2,
    flat_top_tolerance: float = 1e-4,
    min_flat_top_samples: int = 3,
) -> ClippingAnalysis:
    ...
```

The function validates finite one-dimensional non-empty input and parameter
ranges. Detection combines full-scale saturation and sub-full-scale flat tops.
`clipped_samples` counts the union of samples belonging to detected full-scale
or flat-top events, so a sample is counted at most once.

---

## 13. Spectrum Analysis

Location: `dsp/spectrum.py`

```python
def analyze_fft(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    window: str = "hann",
    n_fft: int | None = None,
    remove_dc_component: bool = True,
    max_peaks: int = 10,
) -> FFTAnalysis:
    ...
```

Required behavior:

- validate one-dimensional finite input, positive sample rate, supported window,
  positive `n_fft`, and `max_peaks >= 1`;
- reject fewer than three samples;
- use the selected sample count when `n_fft` is omitted;
- require explicit `n_fft` to be at least the selected sample count and use
  zero-padding when it is larger; hidden truncation is not allowed;
- remove DC when requested;
- apply the requested window and real FFT;
- return relative magnitude with maximum finite magnitude equal to `0 dB`;
- report frequency resolution as `sample_rate_hz / n_fft`;
- exclude DC when choosing the dominant diagnostic frequency;
- report at most `max_peaks` local peaks ordered by descending magnitude;
- preserve full arrays only in the DSP result.

For zero-energy input, the result has no dominant frequency, no spectral
centroid, no peaks, and no NaN values. Relative-magnitude bins may use negative
infinity to represent absence of energy.

---

## 14. Fundamental Estimation

Location: `dsp/pitch.py`

```python
def estimate_f0_autocorrelation(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
    voicing_threshold: float = 0.3,
) -> F0Estimate:
    ...
```

The algorithm uses DC removal, windowing, FFT-based autocorrelation, normalized
lag confidence, restricted lag search, and optional parabolic refinement. It
must return unvoiced with `f0_hz=None` for negligible energy or unreliable
periodicity. Invalid bounds are rejected and never silently swapped.

---

## 15. Harmonic-Distortion Analysis

Location: `dsp/harmonics.py`

```python
def analyze_harmonic_distortion(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fundamental_hz: float | None = None,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
    max_harmonic_order: int = 5,
    window: str = "hann",
) -> HarmonicAnalysis:
    ...
```

Required behavior:

- validate input and bounds as in spectrum/fundamental analysis;
- require `max_harmonic_order >= 2`;
- use the provided positive fundamental or estimate one deterministically;
- return invalid when the fundamental is absent, unreliable, above Nyquist, or
  has negligible spectral amplitude;
- include only harmonic orders whose target frequency does not exceed Nyquist;
- calculate THD from orders 2 through the highest included order;
- return components ordered by harmonic order;
- never classify PASS/FAIL; it returns a metric only;
- never mutate input.

The exact bin-integration and interpolation method is an internal DSP choice but
must satisfy `TEST_PLAN_V0_2.md` tolerances.

---

## 16. Tool Input and Output Contracts

Location: `tools/contracts.py`

```python
ToolName = Literal[
    "detect_clipping",
    "analyze_spectrum",
    "estimate_fundamental",
    "analyze_harmonic_distortion",
]

class SignalSelection(BaseModel):
    model_config = ConfigDict(frozen=True)
    time_range: TimeRange | None = None
    channel: ChannelMode = "mixdown"

class ClippingInput(SignalSelection):
    full_scale_threshold: float = Field(default=0.99, gt=0.0)

class SpectrumInput(SignalSelection):
    window: str = "hann"
    n_fft: int | None = Field(default=None, ge=3)
    max_peaks: int = Field(default=10, ge=1, le=20)

class FundamentalInput(SignalSelection):
    fmin_hz: float = Field(default=50.0, gt=0.0)
    fmax_hz: float = Field(default=1000.0, gt=0.0)

class HarmonicDistortionInput(SignalSelection):
    fundamental_hz: float | None = Field(default=None, gt=0.0)
    fmin_hz: float = Field(default=50.0, gt=0.0)
    fmax_hz: float = Field(default=1000.0, gt=0.0)
    max_harmonic_order: int = Field(default=5, ge=2, le=10)
    window: str = "hann"
```

Both fundamental input models validate `fmax_hz > fmin_hz`.

```python
class ClippingOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["clipping"] = "clipping"
    detected: bool
    clipping_ratio: float
    clipped_samples: int
    clipping_events: int
    longest_event_samples: int
    peak_abs: float
    full_scale_detected: bool
    flat_top_detected: bool

class SpectrumPeakOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    frequency_hz: float
    relative_magnitude_db: float

class SpectrumOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["spectrum"] = "spectrum"
    frequency_resolution_hz: float
    dominant_frequency_hz: float | None
    spectral_centroid_hz: float | None
    spectral_peaks: tuple[SpectrumPeakOutput, ...]

class FundamentalOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["fundamental"] = "fundamental"
    f0_hz: float | None
    confidence: float
    voiced: bool
    method: str

class HarmonicComponentOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    order: int
    measured_frequency_hz: float
    relative_amplitude: float
    relative_magnitude_db: float

class HarmonicDistortionOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["harmonic_distortion"] = "harmonic_distortion"
    valid: bool
    invalid_reason: str | None
    fundamental_frequency_hz: float | None
    thd_percent: float | None
    components: tuple[HarmonicComponentOutput, ...]
```

Tool outputs contain no ndarray fields.

---

## 17. Evidence and Tool Results

Locations: `tools/evidence.py`, `tools/results.py`

```python
EvidenceValue = bool | int | float | str
EvidenceValidity = Literal["valid", "not_applicable"]
ToolStatus = Literal["success", "invalid", "error"]

class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(pattern=r"^ev_")
    source_tool: ToolName
    call_id: str = Field(pattern=r"^call_")
    metric: str = Field(min_length=1)
    value: EvidenceValue
    unit: str | None = None
    validity: EvidenceValidity = "valid"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    time_range: TimeRange | None = None
    channel: ChannelMode

T = TypeVar("T")

class ToolResult(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    call_id: str = Field(pattern=r"^call_")
    tool_name: ToolName
    status: ToolStatus
    result: T | None = None
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[str, ...] = ()
    error_message: str | None = None
```

Status invariants:

- `success`: result is present, error message is absent;
- `invalid`: a compact result may be present, warnings are non-empty, error
  message is absent;
- `error`: result is absent, evidence is empty, error message is non-empty;
- only deterministic Tool adapters create Evidence;
- invalid Evidence may describe why a metric is unavailable but may not contain
  a fabricated numeric metric.

---

## 18. Tool Service

Location: `tools/service.py`

```python
class SignalToolService:
    def __init__(self, repository: SignalRepository) -> None: ...

    def detect_clipping(
        self,
        signal_id: str,
        args: ClippingInput,
    ) -> ToolResult[ClippingOutput]: ...

    def analyze_spectrum(
        self,
        signal_id: str,
        args: SpectrumInput,
    ) -> ToolResult[SpectrumOutput]: ...

    def estimate_fundamental(
        self,
        signal_id: str,
        args: FundamentalInput,
    ) -> ToolResult[FundamentalOutput]: ...

    def analyze_harmonic_distortion(
        self,
        signal_id: str,
        args: HarmonicDistortionInput,
    ) -> ToolResult[HarmonicDistortionOutput]: ...
```

The service injects `signal_id`; it never appears in Agent-generated Tool input.
The service retrieves the record, extracts the selected working array, calls DSP,
maps compact output, and creates Evidence. Expected operational failures are
returned as `error`. Scientifically unreliable fundamental or harmonic metrics
are returned as `invalid`.

---

## 19. Tool Registry

Location: `tools/registry.py`

```python
class ToolDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: ToolName
    description: str
    useful_when: str
    input_schema: dict[str, object]

def get_tool_descriptors() -> tuple[ToolDescriptor, ...]:
    ...
```

The registry exposes all four Phase 1 tools without prescribing an order. Schema
data must be JSON-serializable and must not contain callable or provider objects.

---

## 20. Agent Exceptions

Location: `agent/models.py`

```python
class AgentError(Exception):
    """Base Agent runtime exception."""

class PlannerError(AgentError):
    pass

class PlannerOutputError(PlannerError):
    pass

class ScriptExhaustedError(PlannerError):
    pass

class DiagnosisValidationError(AgentError):
    pass
```

These exceptions are converted into explicit runtime result states at the
runtime boundary.

---

## 21. Agent Models

Location: `agent/models.py`

```python
TaskType = Literal[
    "distortion_analysis",
    "unsupported",
]

DiagnosisOutcome = Literal[
    "supported_fault",
    "no_supported_fault",
    "inconclusive",
]

ConfidenceLabel = Literal[
    "low",
    "medium",
    "high",
]

TerminationReason = Literal[
    "planner_finished",
    "unsupported_task",
    "max_tool_calls",
    "max_planner_retries",
    "no_progress",
    "runtime_error",
]
```

### 21.1 Task assessment

```python
class TaskAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_type: TaskType
    objective: str = Field(min_length=1)
    hypotheses: tuple[str, ...] = ()
```

### 21.2 Typed Tool invocations

```python
class DetectClippingCall(BaseModel):
    model_config = ConfigDict(frozen=True)
    tool_name: Literal["detect_clipping"] = "detect_clipping"
    args: ClippingInput

class AnalyzeSpectrumCall(BaseModel):
    model_config = ConfigDict(frozen=True)
    tool_name: Literal["analyze_spectrum"] = "analyze_spectrum"
    args: SpectrumInput

class EstimateFundamentalCall(BaseModel):
    model_config = ConfigDict(frozen=True)
    tool_name: Literal["estimate_fundamental"] = "estimate_fundamental"
    args: FundamentalInput

class AnalyzeHarmonicDistortionCall(BaseModel):
    model_config = ConfigDict(frozen=True)
    tool_name: Literal["analyze_harmonic_distortion"] = (
        "analyze_harmonic_distortion"
    )
    args: HarmonicDistortionInput

ToolInvocation = Annotated[
    DetectClippingCall
    | AnalyzeSpectrumCall
    | EstimateFundamentalCall
    | AnalyzeHarmonicDistortionCall,
    Field(discriminator="tool_name"),
]
```

### 21.3 Decisions

```python
class DiagnosisClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str = Field(pattern=r"^claim_")
    fault_type: Literal[
        "clipping",
        "harmonic_distortion",
        "no_supported_fault",
        "inconclusive",
    ]
    statement: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

class CallToolDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_type: Literal["call_tool"] = "call_tool"
    task_assessment: TaskAssessment | None = None
    call: ToolInvocation
    purpose: str = Field(min_length=1)
    expected_evidence: tuple[str, ...] = ()

class FinishDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_type: Literal["finish"] = "finish"
    task_assessment: TaskAssessment | None = None
    outcome: DiagnosisOutcome
    claims: tuple[DiagnosisClaim, ...]
    confidence_label: ConfidenceLabel
    limitations: tuple[str, ...] = ()

AgentDecision = Annotated[
    CallToolDecision | FinishDecision,
    Field(discriminator="decision_type"),
]
```

The first valid decision must include `task_assessment`. An unsupported task must
finish without Tool calls. A supported-fault or no-supported-fault finish must
contain at least one claim with at least one evidence reference. An inconclusive
finish may have no Evidence but must contain a limitation.

---

## 22. Observation and Planner Context

Location: `agent/models.py`

```python
ToolOutput = Annotated[
    ClippingOutput
    | SpectrumOutput
    | FundamentalOutput
    | HarmonicDistortionOutput,
    Field(discriminator="kind"),
]

class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: str = Field(pattern=r"^obs_")
    call_id: str = Field(pattern=r"^call_")
    tool_name: ToolName
    normalized_arguments: dict[str, object]
    purpose: str
    status: ToolStatus
    result: ToolOutput | None = None
    evidence_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error_message: str | None = None

class ToolHistoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    tool_name: ToolName
    normalized_arguments: dict[str, object]
    purpose: str
    status: ToolStatus

class PlannerContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(pattern=r"^run_")
    user_request: str = Field(min_length=1)
    signal_meta: SignalMeta
    task_assessment: TaskAssessment | None
    observations: tuple[Observation, ...]
    evidence: tuple[Evidence, ...]
    tool_history: tuple[ToolHistoryEntry, ...]
    available_tools: tuple[ToolDescriptor, ...]
    remaining_tool_calls: int = Field(ge=0)
    remaining_planner_retries: int = Field(ge=0)
    no_progress_count: int = Field(ge=0)
    warnings: tuple[str, ...] = ()
    recoverable_errors: tuple[str, ...] = ()
```

No field may contain an ndarray, waveform samples, or full FFT arrays.
`normalized_arguments` must contain only JSON-serializable scalar, list, and
mapping values produced from the validated Tool input model.

---

## 23. Planner Protocol and Implementations

Location: `agent/planner.py`

```python
class PlannerModel(Protocol):
    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        ...
```

### 23.1 `RealLLMPlanner`

```python
class RealLLMPlanner:
    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        ...
```

Its constructor and provider client are phase-local composition details and are
not frozen until a provider is selected. Required behavior is frozen:

- use a real LLM and structured output;
- return only validated `AgentDecision` objects;
- never calculate deterministic metrics;
- never receive raw waveform/full FFT data;
- raise `PlannerOutputError` for malformed model output after adapter parsing;
- never fall back to `ScriptedPlanner`.

### 23.2 `ScriptedPlanner`

```python
class ScriptedStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_observation_count: int = Field(ge=0)
    required_evidence_metrics: tuple[str, ...] = ()
    decision: AgentDecision

class ScriptedPlanner:
    def __init__(self, steps: Sequence[ScriptedStep]) -> None: ...

    async def decide(
        self,
        context: PlannerContext,
    ) -> AgentDecision:
        ...
```

It consumes one step per call, verifies context expectations, and raises
`ScriptExhaustedError` when no step remains. It drives real Tool/DSP execution
and does not fabricate numerical observations.

---

## 24. Runtime Policies

Location: `agent/policies.py`

```python
class AgentLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_tool_calls: int = Field(default=8, ge=1)
    max_planner_retries: int = Field(default=2, ge=0)
    max_no_progress: int = Field(default=2, ge=1)
```

Phase 3 adds `max_rule_evaluations` and `max_knowledge_retrievals` additively;
see §38.2. Phase 2 behavior uses only the three fields above.

Two Tool calls are equivalent when their tool name and canonical serialized
arguments are equal. Changing prose purpose alone does not make an equivalent
call useful. An equivalent call is rejected and increments no-progress count.

A first non-equivalent `invalid` observation counts as progress because it adds
scientific information. Repeating the same invalid or failed call does not.

---

## 25. Diagnosis and Run Result

Locations: `agent/diagnosis.py`, `agent/models.py`

```python
class StructuredDiagnosis(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    task_type: TaskType
    outcome: DiagnosisOutcome
    claims: tuple[DiagnosisClaim, ...]
    confidence_label: ConfidenceLabel
    limitations: tuple[str, ...]
    termination_reason: TerminationReason
    tool_call_count: int = Field(ge=0)

RunStatus = Literal["success", "inconclusive", "error"]

class AgentRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    status: RunStatus
    diagnosis: StructuredDiagnosis | None
    observations: tuple[Observation, ...]
    evidence: tuple[Evidence, ...]
    tool_history: tuple[ToolHistoryEntry, ...]
    termination_reason: TerminationReason
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
```

Diagnosis validation requires all cited Evidence to exist in the same run.
Numerical claims must cite deterministic Evidence. Unsupported references raise
`DiagnosisValidationError` and are handled by runtime retry/termination policy.

---

## 26. Runtime Contract

Location: `agent/runtime.py`

```python
class DistortionDiagnosisRuntime:
    def __init__(
        self,
        *,
        repository: SignalRepository,
        tool_service: SignalToolService,
        planner: PlannerModel,
        limits: AgentLimits = AgentLimits(),
    ) -> None:
        ...

    async def run(
        self,
        *,
        signal_id: str,
        user_request: str,
    ) -> AgentRunResult:
        ...
```

Runtime responsibilities:

1. load signal metadata;
2. construct compact Planner context;
3. invoke and validate planner decisions;
4. inject `signal_id` and execute the selected real Tool;
5. record observation, evidence, and history;
6. enforce call, retry, duplicate, and no-progress policies;
7. validate finish decisions and evidence references;
8. return an explicit terminal result.

The runtime must not choose a replacement Tool after a planner decision. It may
reject an invalid decision and retry the planner within policy. Real-model failure
never causes a scripted-planner fallback.

---

## 27. State Contract

Location: `agent/state.py`

```python
class DiagnosisState(TypedDict):
    run_id: str
    signal_id: str
    user_request: str
    signal_meta: SignalMeta
    task_assessment: TaskAssessment | None
    observations: list[Observation]
    evidence: list[Evidence]
    tool_history: list[ToolHistoryEntry]
    planner_attempt_count: int
    tool_call_count: int
    no_progress_count: int
    warnings: list[str]
    errors: list[str]
    termination_reason: TerminationReason | None
    diagnosis: StructuredDiagnosis | None
```

This mutable state is runtime-owned. The planner receives only immutable
`PlannerContext` snapshots.

---

## 28. Phase 2 S1 Semantics

The runtime must support legal dynamic paths for:

- clipping-only input: clipping evidence may be sufficient to stop;
- harmonic input: the planner may obtain fundamental/harmonic evidence after a
  negative or irrelevant first observation;
- combined input: full-credit evaluation requires both supported claims, without
  freezing their discovery order;
- clean input: a no-fault claim requires relevant negative evidence;
- noise/invalid input: no fabricated F0 or THD; an inconclusive finish is valid.

These are outcome constraints, not a fixed Tool pipeline.

---

## 29. Explicitly Unfrozen Phase 4–5 Interfaces

V0.2 does not yet freeze:

- evaluation dataset/report schemas;
- fixed-pipeline baseline contracts;
- WAV loader signature;
- HTTP API;
- UI contracts;
- HTML/PDF report schema;
- embedding or vector-database retrieval backends;
- concrete LLM provider constructor details beyond Phase 2 behavior requirements;
- orchestration framework integration.

Phase 3 rule and knowledge contracts are frozen in §32–§40. Phase 4–5
contracts are frozen immediately before their implementation phase.

---

## 30. V0.1 Compatibility Decisions

V0.2 intentionally supersedes these V0.1 public elements:

| V0.1 | V0.2 | Reason |
|---|---|---|
| `SyntheticGroundTruth.fault_type` | `fault_labels` | combined faults require multiple labels |
| `FFTInput` / `FFTOutput` | `SpectrumInput` / `SpectrumOutput` | Tool name describes diagnostic summary rather than implementation primitive |
| `F0Input` / `F0Output` | `FundamentalInput` / `FundamentalOutput` | S1 uses fundamental evidence beyond pitch terminology |
| `fft_analysis` | `analyze_spectrum` | consistent Tool naming |
| `estimate_f0` Tool method | `estimate_fundamental` | consistent evidence terminology |
| no harmonic Tool | `analyze_harmonic_distortion` | required for S1 |
| no Evidence on Tool result | deterministic `Evidence` tuple | diagnosis traceability |
| Agent postponed | Phase 2 hybrid runtime | required for complete S1 Demo |

No compatibility aliases are required because no V0.1 implementation has been
released. V0.1 documents remain historical records.

---

## 31. Frozen V0.2 Public Surface Summary

```text
signal.models
    SourceType, ChannelMode, FaultLabel
    TimeRange, SignalMeta, SignalRecord

signal.factory
    build_signal_record

signal.repository
    SignalRepository, InMemorySignalRepository

signal.segment
    extract_segment

signal.synthetic
    SyntheticGroundTruth, SyntheticCase
    generate_sine, generate_clipped_sine
    generate_harmonic_sine, generate_combined_distortion
    generate_white_noise

dsp.models
    ClippingAnalysis, SpectrumPeak, FFTAnalysis, F0Estimate
    HarmonicComponent, HarmonicAnalysis

dsp.preprocess
    remove_dc, rms, peak_abs

dsp.clipping
    analyze_clipping

dsp.spectrum
    analyze_fft

dsp.pitch
    estimate_f0_autocorrelation

dsp.harmonics
    analyze_harmonic_distortion

tools.contracts
    ToolName, SignalSelection
    ClippingInput, SpectrumInput, FundamentalInput
    HarmonicDistortionInput
    ClippingOutput, SpectrumPeakOutput, SpectrumOutput
    FundamentalOutput, HarmonicComponentOutput
    HarmonicDistortionOutput

tools.evidence
    Evidence, EvidenceValue, EvidenceValidity

tools.results
    ToolStatus, ToolResult

tools.service
    SignalToolService

tools.registry
    ToolDescriptor, get_tool_descriptors

agent.models
    task, decision, observation, context, diagnosis, and run-result models

agent.planner
    PlannerModel, RealLLMPlanner, ScriptedStep, ScriptedPlanner

agent.policies
    AgentLimits

agent.state
    DiagnosisState

agent.runtime
    DistortionDiagnosisRuntime
```

Any Phase 1–2 change to this surface after approval requires explicit contract
revision.

---

## 32. Phase 3 Contract Policy

Phase 3 separates three concerns that must not be conflated:

1. **Evidence** — deterministic numerical facts from DSP Tools;
2. **Rule judgment** — configured PASS/FAIL/NOT_APPLICABLE results over Evidence;
3. **Knowledge** — curated explanatory text retrieved for the planner and final
   diagnosis narrative.

Phase 3 adds `rules/` and `knowledge/` below `tools/` and extends Agent contracts
additively. Sections 2–31 remain frozen. Phase 3 must not change existing Phase
1–2 field names, statuses, or semantics.

Phase 3 Agent extensions are defined as new models and optional fields in §39.
OQ-001 approval authorizes their implementation in `agent/models.py`.

### 32.1 Deterministic ID policy

For identical business inputs (profile, Evidence, query text/tags, corpus
version), Phase 3 outputs must have identical business fields: judgments,
observed values, matched terms/tags, ordering, and cited references.

Trace identifiers (`evaluation_id`, `batch_id`, `retrieval_id`) may vary between
runs unless a test explicitly asserts stable IDs. When stability is required,
tests must pin the ID generator or compare normalized payloads excluding trace
IDs.

---

## 33. Rule Profile Models

Location: `rules/models.py`

```python
RuleComparator = Literal[
    "lt",
    "lte",
    "gt",
    "gte",
    "eq",
    "neq",
]

RuleJudgment = Literal[
    "pass",
    "fail",
    "not_applicable",
]

class RuleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(pattern=r"^rule_")
    metric: str = Field(min_length=1)
    source_tool: ToolName
    comparator: RuleComparator
    threshold: EvidenceValue
    unit: str | None = None
    description: str = Field(min_length=1)

class RuleProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str = Field(pattern=r"^profile_")
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    rules: tuple[RuleDefinition, ...]
```

Required semantics:

- `metric` names a deterministic Evidence metric produced by `source_tool`;
- `threshold` uses the same scalar type as the referenced Evidence value;
  compatibility is strict by scalar category (`bool`, `int`, `float`, `str`),
  and `bool` is never treated as an `int` despite Python subclass semantics;
- when `RuleDefinition.unit` is non-null, matching Evidence must have the exact
  same unit; a unit mismatch is not type-compatible. A null rule unit imposes no
  unit constraint;
- `comparator` expresses the **PASS condition**: when Evidence is valid and
  type-compatible, the expression `observed_value <comparator> threshold` (using
  the named comparator) evaluates to `true` → judgment `pass`, `false` →
  judgment `fail`. Examples: `clipping_ratio lte 0.01`, `flat_top_detected eq
  false`, `thd_percent lte 5.0`;
- `rules` must be non-empty and contain no duplicate `rule_id` values within a
  profile;
- profile `version` is opaque to callers but must change when any rule threshold
  or comparator changes;
- the first supported profile is `profile_s1_distortion` for S1 clipping and
  harmonic metrics;
- demonstration thresholds are not industry standards.

Profile files live under `rules/profiles/` as versioned YAML or JSON loaded into
`RuleProfile`. Loading is explicit dependency injection; the runtime must not
read fixed directories or globals implicitly.

```python
class RuleProfileLoader(Protocol):
    def load(self, profile_id: str) -> RuleProfile:
        ...
```

Callers inject a `RuleProfileLoader` (or equivalent callable) into
`DistortionDiagnosisRuntime`; see §38.1.

---

## 34. Rule Evaluation Result

Location: `rules/models.py`, `rules/engine.py`

```python
class RuleEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    evaluation_id: str = Field(pattern=r"^ruleval_")
    rule_id: str = Field(pattern=r"^rule_")
    judgment: RuleJudgment
    observed_value: EvidenceValue | None = None
    comparator: RuleComparator
    threshold: EvidenceValue
    profile_id: str = Field(pattern=r"^profile_")
    profile_version: str = Field(min_length=1)
    evidence_refs: tuple[str, ...]
    reason: str | None = None

class RuleEvaluationBatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str = Field(pattern=r"^rulebatch_")
    profile_id: str = Field(pattern=r"^profile_")
    profile_version: str = Field(min_length=1)
    evaluations: tuple[RuleEvaluation, ...]
```

```python
class RuleEngine:
    def evaluate_profile(
        self,
        profile: RuleProfile,
        evidence: Sequence[Evidence],
        *,
        evidence_filter: frozenset[str] | None = None,
    ) -> RuleEvaluationBatch:
        ...
```

Required behavior:

- evaluation is deterministic for identical profile and Evidence inputs;
- **one `RuleDefinition` × one matching Evidence → one `RuleEvaluation`**;
- when no Evidence matches a rule's `source_tool` and `metric`, emit one
  `not_applicable` evaluation for that rule with **empty** `evidence_refs` and a
  non-empty `reason`;
- when matching Evidence exists but has `validity="not_applicable"`, is
  type-incompatible with the rule threshold, or violates the rule's unit
  constraint, emit one `not_applicable` evaluation that **must** cite that
  Evidence in `evidence_refs`;
- when multiple Evidence records match the same rule (same `source_tool` and
  `metric`), emit **one evaluation per matching Evidence**;
- optional `evidence_filter` restricts which Evidence IDs are considered; rules
  with no matching Evidence after filtering follow the no-match rule above;
- `not_applicable` must never be reported as `pass`;
- the engine does not call DSP, Tools, or an LLM;
- PASS/FAIL applies the comparator-as-PASS-condition rule from §33 only when
  Evidence is valid and type-compatible;
- `evidence_refs` entries must reference existing Evidence IDs from the input
  sequence when non-empty.

Initial S1 rule bindings (subject to profile file values) cover at minimum:

| rule metric family | source tool | example metric names |
|---|---|---|
| clipping | `detect_clipping` | `clipping_ratio`, `clipping_detected`, `flat_top_detected` |
| harmonic distortion | `analyze_harmonic_distortion` | `thd_percent`, `valid` |

Exact thresholds and comparator choices belong in the versioned profile file.
OQ-003 approved `profile_s1_distortion` version `1.0.0-demo`; D015 records its
values and demonstration-only status.

---

## 35. Knowledge Corpus Models

Location: `knowledge/models.py`

```python
class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str = Field(pattern=r"^doc_")
    title: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    version: str = Field(min_length=1)

class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(pattern=r"^chunk_")
    document_id: str = Field(pattern=r"^doc_")
    title: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    heading_path: tuple[str, ...] = ()
```

Required semantics:

- corpus content is curated local Markdown under `knowledge/corpus/`;
- chunks are deterministic subdivisions of source documents;
- chunking rules are implementation details but must be stable for a fixed corpus
  version;
- corpus text does not create numerical Evidence and must not alter DSP metrics;
- initial corpus size is small and S1-focused (clipping, harmonic distortion,
  THD explanation, inconclusive handling).

---

## 36. Knowledge Retrieval Result

Location: `knowledge/models.py`, `knowledge/index.py`

```python
class KnowledgeMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str = Field(pattern=r"^doc_")
    chunk_id: str = Field(pattern=r"^chunk_")
    matched_terms: tuple[str, ...] = ()
    matched_tags: tuple[str, ...] = ()

class KnowledgeRetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    retrieval_id: str = Field(pattern=r"^know_")
    query_text: str = Field(default="")
    query_tags: tuple[str, ...] = ()
    matches: tuple[KnowledgeMatch, ...]
    chunks: tuple[KnowledgeChunk, ...]
```

```python
class KnowledgeIndex:
    def __init__(self, corpus_root: Path) -> None: ...

    def retrieve(
        self,
        *,
        query_text: str,
        tags: Sequence[str] = (),
        max_results: int = 5,
    ) -> KnowledgeRetrievalResult:
        ...
```

Required behavior per D011:

- retrieval is deterministic keyword and tag matching over the local corpus;
- `max_results` must be at least 1; zero or negative values raise `ValueError`;
- no network access, embeddings, or vector database in the initial implementation;
- identical query inputs return identical match ordering and business fields for
  a fixed corpus version (see §32.1 for trace ID policy);
- `matches` and `chunks` are **1:1**, in the same order, with no missing chunk
  references: each `KnowledgeMatch.chunk_id` resolves to the corresponding
  `KnowledgeChunk` at the same index in `chunks`;
- `chunks` contains compact excerpts only; no raw waveform or FFT data;
- when both `query_text` and `tags` are empty, `retrieve()` returns a
  `KnowledgeRetrievalResult` with `query_text=""`, empty `matches`, and empty
  `chunks` — not an error;
- non-empty `query_text` in planner decisions uses `Field(min_length=1)`; only
  the empty-query retrieval result allows `query_text=""`;
- missing knowledge does not change deterministic numerical conclusions;
- a later embedding backend may replace indexing internals if it preserves this
  public result contract.

Keyword normalization (frozen minimum):

- Unicode casefold on query terms and corpus tokens;
- split on punctuation and whitespace into tokens;
- deduplicate query tokens while preserving first-seen order;
- tag matching is exact string equality after stripping leading/trailing
  whitespace on both query tags and chunk/document tags.

Ranking is by descending count of matched query terms and tags, then stable
document/chunk ID order. Tie-breaking rules are fixed in implementation tests.

---

## 37. Phase 3 Package Boundaries

Allowed dependencies:

```text
rules  -> tools, signal
knowledge -> (stdlib only; no signal/tools/agent imports required)
agent  -> rules, knowledge, tools, signal   # Phase 3 runtime integration only
```

Forbidden dependencies:

- `rules/` must not import `agent/`, `evaluation/`, `app/`, or LLM clients;
- `knowledge/` must not import `agent/`, `rules/`, `dsp/`, `tools/`, LLM
  clients, or embedding/vector libraries in the initial implementation;
- `signal/`, `dsp/`, and `tools/` must not import `rules/` or `knowledge/`.

`rules/` and `knowledge/` expose compact structured results only. They never pass
corpus text or rule configuration into model prompts except through the
existing Agent context and diagnosis fields defined in §39.

---

## 38. Phase 3 Runtime Actions

Location: `agent/runtime.py` (extended), `rules/engine.py`, `knowledge/index.py`

### 38.1 Runtime dependency injection

Phase 3 extends `DistortionDiagnosisRuntime` additively. All rule and knowledge
boundaries are injected; the runtime must not read fixed profile directories,
corpus paths, or module-level singletons implicitly.

```python
class DistortionDiagnosisRuntime:
    def __init__(
        self,
        *,
        repository: SignalRepository,
        tool_service: SignalToolService,
        planner: PlannerModel,
        limits: AgentLimits = AgentLimits(),
        rule_engine: RuleEngine | None = None,
        rule_profile_loader: RuleProfileLoader | None = None,
        knowledge_index: KnowledgeIndex | None = None,
    ) -> None:
        ...
```

- `rule_engine` evaluates profiles against run Evidence;
- `rule_profile_loader.load(profile_id)` resolves versioned profiles;
- `knowledge_index` serves deterministic retrieval over the injected corpus.

Phase 2-only construction without the three Phase 3 dependencies remains valid.
If the planner requests a Phase 3 action while its required injected dependency
is absent, the runtime terminates explicitly with `runtime_error`; it must not
load a fixed directory, use a module-level singleton, or silently fall back.

### 38.2 AgentLimits extension

Phase 3 adds independent action budgets separate from Tool-call limits:

```python
class AgentLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_tool_calls: int = Field(default=8, ge=1)
    max_planner_retries: int = Field(default=2, ge=0)
    max_no_progress: int = Field(default=2, ge=1)
    max_rule_evaluations: int = Field(default=4, ge=0)
    max_knowledge_retrievals: int = Field(default=4, ge=0)
```

Existing Phase 2 defaults for the first three fields are unchanged. Rule and
knowledge actions do not consume `max_tool_calls`.

Phase 3 extends `TerminationReason` additively with:

```python
"max_rule_evaluations"
"max_knowledge_retrievals"
```

The corresponding runtime counter increments immediately before an injected
rule or knowledge dependency is executed, including an execution that returns
an error. A rejected equivalent action does not increment the action counter and
instead follows the existing no-progress policy.

### 38.3 Runtime actions

Phase 3 adds two deterministic runtime actions executed by
`DistortionDiagnosisRuntime` after planner validation:

1. **evaluate rules** — load the requested profile via `rule_profile_loader`,
   evaluate with `rule_engine` against current run Evidence, append
   `RuleEvaluationBatch` to state;
2. **retrieve knowledge** — query `knowledge_index`, append
   `KnowledgeRetrievalResult` to state.

Each action counts as progress when it adds a new batch or retrieval result not
equivalent to a prior action with the same profile/query inputs.

Equivalent rule evaluations and knowledge retrievals follow the same no-progress
semantics as equivalent Tool calls (§24).

---

## 39. Phase 3 Agent Contract Extensions

Location: `agent/models.py`, `agent/diagnosis.py`, `agent/state.py`

Phase 3 extends the frozen Phase 2 Agent contracts additively.

### 39.1 Additional planner decisions

```python
class EvaluateRulesDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_type: Literal["evaluate_rules"] = "evaluate_rules"
    task_assessment: TaskAssessment | None = None
    profile_id: str = Field(pattern=r"^profile_")
    evidence_refs: tuple[str, ...] = ()
    purpose: str = Field(min_length=1)

class RetrieveKnowledgeDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_type: Literal["retrieve_knowledge"] = "retrieve_knowledge"
    task_assessment: TaskAssessment | None = None
    query_text: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    purpose: str = Field(min_length=1)
```

Extended union:

```python
AgentDecision = Annotated[
    CallToolDecision
    | EvaluateRulesDecision
    | RetrieveKnowledgeDecision
    | FinishDecision,
    Field(discriminator="decision_type"),
]
```

### 39.2 Extended planner context and state

`DiagnosisState` (mutable, runtime-owned) gains:

```python
rule_evaluation_batches: list[RuleEvaluationBatch]
knowledge_retrievals: list[KnowledgeRetrievalResult]
rule_evaluation_count: int
knowledge_retrieval_count: int
```

`PlannerContext` and `AgentRunResult` (immutable snapshots) gain:

```python
rule_evaluation_batches: tuple[RuleEvaluationBatch, ...] = ()
knowledge_retrievals: tuple[KnowledgeRetrievalResult, ...] = ()
```

These fields contain only compact structured results from §34 and §36. Claims
cite individual `RuleEvaluation.evaluation_id` values found within batches via
`rule_refs`.

### 39.3 Extended diagnosis output

Diagnosis output must distinguish evidence, rule judgment, and explanation.

```python
class DiagnosisClaim(BaseModel):
    # existing Phase 2 fields unchanged
    rule_refs: tuple[str, ...] = ()       # RuleEvaluation.evaluation_id values
    knowledge_refs: tuple[str, ...] = ()    # KnowledgeRetrievalResult.retrieval_id values

class StructuredDiagnosis(BaseModel):
    # existing Phase 2 fields unchanged
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...] = ()
    knowledge_retrievals: tuple[KnowledgeRetrievalResult, ...] = ()
```

Validation extensions:

- every `rule_refs` entry must exist as an `evaluation_id` within
  `rule_evaluation_batches` for the same run;
- every `knowledge_refs` entry must exist in `knowledge_retrievals` for the same
  run;
- numerical claims still require deterministic Evidence; knowledge refs alone are
  insufficient;
- claims that assert a configured threshold outcome must cite the supporting
  `rule_refs`;
- `knowledge_refs` explain claims and limitations; they do not satisfy Evidence
  requirements.

`AgentRunResult` gains the same two optional batch/retrieval tuples for trace
completeness.

### 39.4 Scripted planner extension

`ScriptedStep` may return `EvaluateRulesDecision` and
`RetrieveKnowledgeDecision` in addition to existing decision types. Scripted
tests must drive real rule-engine and knowledge-index execution.

---

## 40. Phase 3 Public Surface Summary and Remaining Unfrozen Items

### 40.1 Frozen Phase 3 public surface

```text
rules.models
    RuleComparator, RuleJudgment
    RuleDefinition, RuleProfile, RuleProfileLoader
    RuleEvaluation, RuleEvaluationBatch

rules.engine
    RuleEngine

knowledge.models
    KnowledgeDocument, KnowledgeChunk
    KnowledgeMatch, KnowledgeRetrievalResult

knowledge.index
    KnowledgeIndex

agent.models (additive)
    EvaluateRulesDecision, RetrieveKnowledgeDecision
    extended AgentDecision, PlannerContext, DiagnosisClaim, StructuredDiagnosis
    extended TerminationReason for rule/knowledge budget exhaustion

agent.state (additive)
    rule_evaluation_batches, knowledge_retrievals
    rule_evaluation_count, knowledge_retrieval_count in DiagnosisState

agent.policies (additive)
    max_rule_evaluations, max_knowledge_retrievals in AgentLimits

agent.runtime (behavioral extension)
    optional injected RuleEngine, RuleProfileLoader, KnowledgeIndex
    execute evaluate_rules and retrieve_knowledge actions
```

### 40.2 Still unfrozen after Phase 3 approval

- YAML serialization details beyond the frozen RuleProfile fields;
- corpus document list and chunking parameters;
- embedding or vector retrieval backends;
- Phase 4 evaluation and fixed-pipeline contracts;
- Phase 5 presentation contracts.

Approval of §32–§40 authorizes Phase 3 implementation but does not freeze Phase
4–5 interfaces.
