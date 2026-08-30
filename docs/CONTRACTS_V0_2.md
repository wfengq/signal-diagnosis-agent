# Signal Diagnosis Agent — Frozen Contracts V0.2

**Document:** `CONTRACTS_V0_2.md`  
**Contract version:** `0.2`  
**Status:** Frozen for Phase 1–4; Phase 4 accepted at `b68ec5e`; Phase 4.1
§50 deterministic implementation complete with v5 development below target;
additive v6 correction §51 frozen and implementation-authorized
**Scope:** Phase 1 deterministic foundation, Phase 2 hybrid Agent runtime, and
Phase 3 rules/knowledge contracts; frozen Phase 4 evaluation contracts;
additive Phase 4.1 behavior gate
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

Private helpers remain implementation details. Phase 3 interfaces are frozen in
§32–§40. The written-spec-approved Phase 4 contracts are frozen in §41–§49.
Phase 4 is accepted at `b68ec5e`. Additive Phase 4.1 behavior contracts are
frozen in §50. The v5 development result is immutable
`completed/below_target`. The additive v6 correction is frozen in §51 and its
Task 2–8 implementation is authorized; real-model execution remains subject to
the §51 development-before-held-out gates.

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

## 29. Explicitly Unfrozen Later Interfaces

V0.2 does not yet freeze:

- WAV loader signature;
- HTTP API;
- UI contracts;
- HTML/PDF report schema;
- embedding or vector-database retrieval backends;
- concrete LLM provider constructor details beyond Phase 2 behavior requirements;
- orchestration framework integration.

Phase 3 rule and knowledge contracts are frozen in §32–§40. The Phase 4
evaluation contracts are frozen in §41–§49. Phase 5 contracts remain gated and
will be frozen immediately before implementation.

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

### 40.2 Items not frozen by Phase 3 approval

- YAML serialization details beyond the frozen RuleProfile fields;
- corpus document list and chunking parameters;
- embedding or vector retrieval backends;
- Phase 5 presentation contracts.

Approval of §32–§40 authorizes Phase 3 implementation. Phase 4 is governed by
the written-spec-approved and frozen §41–§49. Phase 5 interfaces remain gated.

---

## 41. Phase 4 Contract Status and Package Boundary

Sections 41–49 are the frozen Phase 4 evaluation contracts. The user approved
them section-by-section and approved the written specification at
`docs/superpowers/specs/2026-08-29-phase4-evaluation-design.md` on 2026-08-29.
They become implementation authority once the task-level implementation-plan
and explicit execution-choice gates pass.

Phase 4 adds:

```text
src/signal_diag/evaluation/
├── __init__.py
├── __main__.py
├── models.py
├── dataset.py
├── recording.py
├── baseline.py
├── scoring.py
├── runner.py
├── reporting.py
└── manifests/
    └── s1_distortion_v1.yaml
```

The manifest is shipped as package data. Tests must verify it remains available
from an installed wheel, not only from a source checkout.

The frozen dependency direction is:

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

`evaluation/` may import the existing layers it evaluates. No Phase 1–3
package may import `evaluation/`. Phase 4 does not change any public Phase 1–3
model, function, constructor, or runtime behavior.

All Phase 4 public Pydantic models use `ConfigDict(frozen=True)`. Tuples are
used in immutable snapshots and reports. Provider-specific SDK types do not
appear in public models.

---

## 42. Dataset Manifest Models

### 42.1 Common aliases

```python
EvaluationSplit = Literal["development", "held_out"]
EvaluationCategory = Literal[
    "clean",
    "clipping",
    "harmonic",
    "combined",
    "invalid_noise",
]
CausalFault = Literal["clipping", "harmonic_distortion"]
DiagnosisClaimType = Literal[
    "clipping",
    "harmonic_distortion",
    "no_supported_fault",
    "inconclusive",
]
KnowledgePolicy = Literal["required", "optional", "not_needed"]
EvidenceComparator = Literal["eq", "neq", "lt", "lte", "gt", "gte"]
EvidenceScalar = StrictStr | StrictInt | StrictFloat | StrictBool
```

Boolean, integer, and float values remain strict distinct scalar types when
conditions are evaluated. A range is represented by two conditions rather
than a special hidden comparator.

Causal-fault tuples contain no duplicates and use canonical order
`clipping`, then `harmonic_distortion`. F1/exact-set extraction deduplicates
labels across claims; unsupported-claim rates still count individual predicted
fault claims so duplication cannot improve that metric.

### 42.2 Typed synthetic specifications

```python
class HarmonicRatioSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    order: int = Field(ge=2)
    ratio: float = Field(ge=0.0)


class SineSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["sine"] = "sine"
    frequency_hz: float = Field(gt=0.0)
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    amplitude: float = Field(default=0.5, gt=0.0, le=1.0)
    phase_rad: float = 0.0
    dc_offset: float = 0.0


class ClippedSineSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["clipped_sine"] = "clipped_sine"
    frequency_hz: float = Field(gt=0.0)
    clip_level: float = Field(gt=0.0, le=1.0)
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    amplitude: float = Field(default=0.9, gt=0.0, le=1.0)


class HarmonicSineSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["harmonic_sine"] = "harmonic_sine"
    fundamental_hz: float = Field(gt=0.0)
    harmonic_ratios: tuple[HarmonicRatioSpec, ...]
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    fundamental_amplitude: float = Field(default=0.5, gt=0.0, le=1.0)


class CombinedDistortionSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["combined_distortion"] = "combined_distortion"
    fundamental_hz: float = Field(gt=0.0)
    harmonic_ratios: tuple[HarmonicRatioSpec, ...]
    clip_level: float = Field(gt=0.0, le=1.0)
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    fundamental_amplitude: float = Field(default=0.9, gt=0.0, le=1.0)


class WhiteNoiseSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["white_noise"] = "white_noise"
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    rms: float = Field(default=0.1, gt=0.0)
    seed: int = 0


SyntheticSignalSpec = Annotated[
    SineSignalSpec
    | ClippedSineSignalSpec
    | HarmonicSineSignalSpec
    | CombinedDistortionSignalSpec
    | WhiteNoiseSignalSpec,
    Field(discriminator="generator"),
]
```

Harmonic specifications must contain at least one positive ratio and no
duplicate order. Canonical manifests serialize all resolved generator fields,
including defaulted values. The adapter calls only the existing Phase 1
generators.

Existing generators intentionally allocate a fresh Signal ID. The evaluation
adapter therefore rewraps the returned immutable samples through the existing
`build_signal_record` factory with stable ID
`sig_eval_<case-id-without-case_>`. It changes no sample value and performs no
normalization. Dataset reconstruction compares this stable materialized record
and ground truth, not the generator's transient UUID.

### 42.3 Evidence and sufficiency expectations

```python
class EvidenceCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    condition_id: str = Field(pattern=r"^cond_")
    tool_name: ToolName
    metric: str = Field(min_length=1)
    validity: EvidenceValidity
    comparator: EvidenceComparator
    expected_value: EvidenceScalar
    unit: str | None = None
    supports_claims: tuple[DiagnosisClaimType, ...] = ()


class SufficientEvidenceSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_set_id: str = Field(pattern=r"^evset_")
    condition_refs: tuple[str, ...]
    supported_claims: tuple[DiagnosisClaimType, ...]
    acceptable_outcomes: tuple[DiagnosisOutcome, ...]
```

All three tuples in `SufficientEvidenceSet` must be non-empty. Condition
references resolve within the same case. Duplicate condition IDs, set IDs,
references, claim types, and outcomes are invalid.

An Evidence item matches a condition only when Tool, metric, validity, strict
scalar type, unit, and comparator all match. `supports_claims` defines semantic
grounding for fault, no-fault, and inconclusive claims; it is not inferred from
a metric name.

### 42.4 Combined identifiability

```python
class CombinedIdentifiabilitySpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    signature_metric: str = Field(pattern=r"^harmonic_order_[2-9][0-9]*_relative_amplitude$")
    minimum_absolute_separation: float = Field(gt=0.0)
```

For a combined generator, the validator creates a matched clipping-only control
with the same fundamental, amplitude, sampling, duration, and clipping fields
and no injected harmonic ratios. The absolute difference in
`signature_metric` must be at least `minimum_absolute_separation`.

This field is dataset quality metadata only. It is absent from planner context,
baseline input, and scoring thresholds. Combined cases require it; other
categories reject it.

### 42.5 Case and manifest

```python
class EvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^case_")
    split: EvaluationSplit
    category: EvaluationCategory
    user_request: str = Field(min_length=1)
    signal: SyntheticSignalSpec
    causal_faults: tuple[CausalFault, ...] = ()
    observable_conditions: tuple[EvidenceCondition, ...]
    acceptable_first_tools: tuple[ToolName, ...]
    sufficient_evidence_sets: tuple[SufficientEvidenceSet, ...]
    knowledge_policy: KnowledgePolicy
    knowledge_tags: tuple[str, ...] = ()
    acceptable_outcomes: tuple[DiagnosisOutcome, ...]
    requires_limitation: bool = False
    tags: tuple[str, ...] = ()
    identifiability: CombinedIdentifiabilitySpec | None = None


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    rule_profile_id: str = Field(pattern=r"^profile_")
    rule_profile_version: str = Field(min_length=1)
    cases: tuple[EvaluationCase, ...]
```

The official `s1-distortion-synthetic` `1.0.0` manifest contains exactly the
24-case allocation approved in the Phase 4 design. IDs are unique and
references resolve. Category, causal faults, signal generator, knowledge
policy, and acceptable outcomes must be mutually consistent.

| Split | Clean | Clipping | Harmonic | Combined | Invalid/noise | Total |
|---|---:|---:|---:|---:|---:|---:|
| Development | 2 | 2 | 2 | 1 | 1 | 8 |
| Held-out | 3 | 4 | 4 | 3 | 2 | 16 |

The official category mapping is:

| Category | Generator | `causal_faults` | Acceptable outcome | Knowledge |
|---|---|---|---|---|
| `clean` | `sine` | empty | `no_supported_fault` | `not_needed` |
| `clipping` | `clipped_sine` | clipping | `supported_fault` | `optional` |
| `harmonic` | `harmonic_sine` | harmonic distortion | `supported_fault` | `optional` |
| `combined` | `combined_distortion` | clipping + harmonic distortion | `supported_fault` | `optional` |
| `invalid_noise` | `white_noise` | empty | `inconclusive` | `required` |

Invalid/noise cases require a non-empty limitation. Combined cases require
`CombinedIdentifiabilitySpec`; all other categories reject it.

`knowledge_tags` is empty when policy is `not_needed` and non-empty when policy
is `required`. For `optional`, it declares the topics under which a retrieval is
relevant. Relevance is established deterministically by normalized overlap with
the retrieval's query tags, matched tags, or returned chunk tags.

All boundary and comparison tolerances are explicit manifest conditions. The
loader, validator, and scorer have no hidden numeric tolerance.

---

## 43. Dataset Loading and Validation

```python
def load_dataset_manifest(path: Path) -> DatasetManifest:
    ...


class DatasetValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    case_id: str | None = None
    message: str = Field(min_length=1)


class DatasetValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_id: str
    dataset_version: str
    valid: bool
    checked_case_ids: tuple[str, ...]
    issues: tuple[DatasetValidationIssue, ...] = ()


def validate_dataset(
    manifest: DatasetManifest,
    repository: SignalRepository,
    tool_service: SignalToolService,
    rule_engine: RuleEngine,
    profile_loader: RuleProfileLoader,
) -> DatasetValidationReport:
    ...
```

The canonical manifest is UTF-8 YAML at
`src/signal_diag/evaluation/manifests/s1_distortion_v1.yaml` and is parsed with
safe loading. `load_dataset_manifest` raises file/parse/Pydantic errors rather
than returning a partial model. `validate_dataset` stores generated records in
the injected repository and runs the existing synthetic generators,
real DSP Tools, observable-condition checks, rule-profile identity/version
checks, seed reconstruction checks, official split/category coverage, and
combined-case identifiability.

`valid` is true exactly when `issues` is empty. A non-valid report prevents any
deterministic or real-model benchmark from starting.

---

## 44. Planner Recording and Evaluation Trace

### 44.1 Usage and decision records

```python
class ProviderUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)


PlannerCallStatus = Literal[
    "decision",
    "planner_output_error",
    "planner_error",
    "provider_error",
]


class PlannerDecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: str = Field(pattern=r"^decision_")
    decision_index: int = Field(ge=0)
    context: PlannerContext
    status: PlannerCallStatus
    decision: AgentDecision | None = None
    error_type: str | None = None
    error_message: str | None = None
    latency_ms: float | None = Field(default=None, ge=0.0)
    provider_usage: ProviderUsage | None = None
```

Unknown provider usage stays `None`. `total_tokens`, when present with both
parts, must equal their sum. `status="decision"` requires a decision and no
error fields. Every error status requires no decision plus non-empty error type
and message.

```python
class RecordingPlanner:
    def __init__(self, planner: PlannerModel) -> None:
        ...

    async def decide(self, context: PlannerContext) -> AgentDecision:
        ...

    @property
    def records(self) -> tuple[PlannerDecisionRecord, ...]:
        ...
```

The wrapper passes the same immutable context to the delegate and returns its
decision unchanged after validation. It records every delegate call, including
invalid-output and raised-error attempts, then re-raises the original exception
unchanged. It never substitutes another planner, retries independently, or
mutates runtime state.

### 44.2 Chronological events

```python
class PlannerDecisionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["planner_call"] = "planner_call"
    event_index: int = Field(ge=0)
    record: PlannerDecisionRecord


class ObservationEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["observation"] = "observation"
    event_index: int = Field(ge=0)
    caused_by_decision_index: int = Field(ge=0)
    observation: Observation
    evidence: tuple[Evidence, ...]


class RuleEvaluationEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["rule_evaluation"] = "rule_evaluation"
    event_index: int = Field(ge=0)
    caused_by_decision_index: int = Field(ge=0)
    batch: RuleEvaluationBatch


class KnowledgeRetrievalEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["knowledge_retrieval"] = "knowledge_retrieval"
    event_index: int = Field(ge=0)
    caused_by_decision_index: int = Field(ge=0)
    retrieval: KnowledgeRetrievalResult


EvaluationEvent = Annotated[
    PlannerDecisionEvent
    | ObservationEvent
    | RuleEvaluationEvent
    | KnowledgeRetrievalEvent,
    Field(discriminator="event_type"),
]
```

Event indices are contiguous from zero. A resulting artifact appears after its
successful causing decision and before the next planner call. Error call events
produce no runtime artifact. Evidence attached to an Observation event exactly
matches the Observation's `evidence_refs`.

### 44.3 Configuration, attempts, and trace

```python
ExecutionPath = Literal["agent", "fixed_pipeline"]
ConfigScalar = str | int | float | bool | None
ConfigObject = dict[str, ConfigScalar | dict[str, ConfigScalar]]
ConfigValue = ConfigScalar | tuple[ConfigScalar, ...] | ConfigObject
BaselineCompletionReason = Literal[
    "baseline_completed",
    "insufficient_evidence",
    "runtime_error",
]
AttemptStatus = Literal[
    "behavior_result",
    "infrastructure_error",
    "configuration_error",
    "evaluator_error",
]
AttemptErrorCode = Literal[
    "timeout",
    "rate_limited",
    "provider_5xx",
    "provider_other",
    "authentication",
    "missing_credentials",
    "missing_dependency",
    "invalid_configuration",
    "trace_assembly",
    "scoring",
    "reporting",
]


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    benchmark_id: str = Field(pattern=r"^bench_")
    dataset_id: str
    dataset_version: str
    rule_profile_id: str = Field(pattern=r"^profile_")
    rule_profile_version: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    prompt_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_parameters: dict[str, ConfigValue] = Field(
        default_factory=dict
    )
    sdk_versions: dict[str, str] = Field(default_factory=dict)
    repetitions: int = Field(default=1, ge=1)
    max_infrastructure_retries: int = Field(default=2, ge=0)
    max_concurrency: int = Field(default=1, ge=1)
    started_at_utc: datetime


class AttemptRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_path: ExecutionPath
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    attempt_index: int = Field(ge=1)
    status: AttemptStatus
    error_code: AttemptErrorCode | None = None
    error_message: str | None = None
    started_at_utc: datetime
    finished_at_utc: datetime


class BaselineDiagnosis(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(pattern=r"^baseline_")
    task_type: Literal["distortion_analysis"] = "distortion_analysis"
    outcome: DiagnosisOutcome
    claims: tuple[DiagnosisClaim, ...]
    confidence_label: ConfidenceLabel
    limitations: tuple[str, ...] = ()
    tool_call_count: int = Field(ge=0)
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...]


class BaselineRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    result_type: Literal["fixed_pipeline"] = "fixed_pipeline"
    run_id: str = Field(pattern=r"^baseline_")
    status: RunStatus
    diagnosis: BaselineDiagnosis | None
    observations: tuple[Observation, ...]
    evidence: tuple[Evidence, ...]
    tool_history: tuple[ToolHistoryEntry, ...]
    completion_reason: BaselineCompletionReason
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...]


class EvaluationTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    trace_id: str = Field(pattern=r"^trace_")
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    execution_path: ExecutionPath
    config: BenchmarkConfig
    events: tuple[EvaluationEvent, ...]
    result: AgentRunResult | BaselineRunResult
    provider_usage: ProviderUsage | None = None
```

```python
def assemble_evaluation_trace(
    case: EvaluationCase,
    records: tuple[PlannerDecisionRecord, ...],
    result: AgentRunResult | BaselineRunResult,
    config: BenchmarkConfig,
    *,
    run_slot: int,
    execution_path: ExecutionPath,
) -> EvaluationTrace:
    ...
```

Assembly rejects missing, duplicated, reordered, or ambiguous artifacts. It
never guesses chronology. The fixed baseline produces the same Observation,
Evidence, rule, and result event forms but no planner-decision events.

Waveform arrays, full FFT arrays, secrets, and raw provider responses are
forbidden in `PlannerDecisionRecord`, `EvaluationEvent`, and `EvaluationTrace`.

All recorded datetimes must be timezone-aware UTC. Attempt completion cannot
precede its start. Real-model configuration requires provider, model, prompt
version, and prompt hash; deterministic and baseline configurations leave those
fields `None`.

---

## 45. Fixed-Pipeline Baseline

```python
class FixedPipelineBaseline:
    def __init__(
        self,
        *,
        repository: SignalRepository,
        tool_service: SignalToolService,
        rule_engine: RuleEngine,
        profile_loader: RuleProfileLoader,
    ) -> None:
        ...

    async def run(
        self,
        *,
        signal_id: str,
        user_request: str,
    ) -> BaselineRunResult:
        ...
```

It always calls `detect_clipping` with `ClippingInput()` and then
`analyze_harmonic_distortion` with `HarmonicDistortionInput()`, evaluates
`profile_s1_distortion`, and applies the §6 mapping in the approved Phase 4
design. It uses no planner, manifest truth, matched control, knowledge index,
FFT, or F0. It creates no numerical values outside real Tool Evidence and no
threshold outside the loaded profile.

The exact mapping is:

| Clipping indicator | Harmonic indicator | Harmonic validity | Result |
|---|---|---|---|
| true | true | valid | clipping + harmonic claims |
| true | false | valid | clipping claim |
| false | true | valid | harmonic claim |
| false | false | valid | no-supported-fault claim |
| true | not available | invalid | clipping claim plus harmonic limitation |
| false/not available | not available | invalid | inconclusive plus limitation |

The clipping indicator is true when any applicable clipping-profile rule fails.
The harmonic indicator is true only when harmonic-validity passes and the THD
rule fails.

The result must satisfy the same same-run Evidence and rule-reference
validation as an Agent result. Separate baseline models avoid falsely assigning
`planner_finished` to a path with no planner. Its deterministic nature does not
permit it to run more than once per case in the official comparison.

Every baseline claim has empty `knowledge_refs`. Any non-empty knowledge ref or
knowledge action is a contract error, not an ignorable extra.

---

## 46. Per-Run and Aggregate Scoring

```python
class RateMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float = Field(ge=0.0, le=1.0)


class RunScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    trace_id: str = Field(pattern=r"^trace_")
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    execution_path: ExecutionPath
    expected_faults: tuple[CausalFault, ...]
    predicted_faults: tuple[CausalFault, ...]
    acceptable_outcomes: tuple[DiagnosisOutcome, ...]
    predicted_outcome: DiagnosisOutcome | None
    causal_exact_set_correct: bool
    outcome_correct: bool
    grounded_claims: int = Field(ge=0)
    scored_claims: int = Field(ge=0)
    unsupported_fault_claims: int = Field(ge=0)
    predicted_fault_claims: int = Field(ge=0)
    first_tool_correct: bool | None = None
    appropriate_replans: int = Field(ge=0)
    replan_opportunities: int = Field(ge=0)
    unnecessary_tool_actions: int = Field(ge=0)
    tool_actions: int = Field(ge=0)
    timely_stop: bool | None = None
    correct_rule_actions: int = Field(ge=0)
    rule_action_opportunities: int = Field(ge=0)
    required_knowledge_actions: int = Field(ge=0)
    required_knowledge_opportunities: int = Field(ge=0)
    unnecessary_knowledge_actions: int = Field(ge=0)
    knowledge_actions: int = Field(ge=0)
    cited_knowledge_actions: int = Field(ge=0)
    planner_calls: int = Field(ge=0)
    end_to_end_latency_ms: float | None = Field(default=None, ge=0.0)
    provider_usage: ProviderUsage | None = None
    completion_reason: TerminationReason | BaselineCompletionReason
    failure_codes: tuple[str, ...] = ()


class AggregateMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_count: int = Field(ge=0)
    causal_exact_set_accuracy: RateMetric
    causal_macro_f1: float = Field(ge=0.0, le=1.0)
    outcome_accuracy: RateMetric
    evidence_grounding_rate: RateMetric
    unsupported_claim_rate: RateMetric
    first_tool_selection_rate: RateMetric
    observation_driven_replan_rate: RateMetric
    unnecessary_tool_action_rate: RateMetric
    timely_stopping_rate: RateMetric
    applicable_rule_usage_rate: RateMetric
    required_knowledge_usage_rate: RateMetric
    unnecessary_knowledge_retrieval_rate: RateMetric
    knowledge_citation_utilization_rate: RateMetric
    average_tool_actions: float = Field(ge=0.0)
    average_planner_calls: float | None = Field(default=None, ge=0.0)
    latency_ms_mean: float | None = Field(default=None, ge=0.0)
    latency_ms_p50: float | None = Field(default=None, ge=0.0)
    latency_ms_p95: float | None = Field(default=None, ge=0.0)
    provider_usage_coverage_rate: RateMetric
    observed_input_tokens: int | None = Field(default=None, ge=0)
    observed_output_tokens: int | None = Field(default=None, ge=0)
    observed_total_tokens: int | None = Field(default=None, ge=0)
    observed_cost_usd: float | None = Field(default=None, ge=0.0)
```

A zero-denominator `RateMetric` has value `0.0`; the zero denominator remains
visible so consumers cannot confuse not-applicable with observed success.
Planner-specific metrics for the fixed baseline use denominator zero.

For a non-zero denominator, `RateMetric.value` is exactly
`numerator / denominator`; numerators and all per-run success counts cannot
exceed their denominators. Aggregators compute these values rather than accept
caller-supplied inconsistent rates.

`causal_macro_f1` is multilabel macro-F1 over exactly `clipping` and
`harmonic_distortion`. Clean and inconclusive are assessed by outcome and exact
set accuracy.

```python
def score_evaluation_trace(
    case: EvaluationCase,
    trace: EvaluationTrace,
) -> RunScore:
    ...
```

The scorer implements the approved metric semantics. In particular, a claim is
grounded only when all refs resolve and at least one cited Evidence matches a
  condition whose `supports_claims` includes that claim type. A structurally
valid but semantically unrelated citation is not grounded.

Observation-driven replanning is an observable proxy: after a context delta,
the next action must advance a still-viable sufficient Evidence set, validly
apply rule/knowledge policy, finish when sufficient, or handle an invalid/error
state according to the existing runtime policy. The scorer never attempts to
infer hidden model reasoning.

For Agent traces, no executed DSP Tool makes `first_tool_correct=False`;
`None` is reserved for the fixed baseline's non-applicable planner metric.
Timely stopping counts only DSP Tool actions after sufficiency; required rule or
knowledge actions after sufficiency are not penalized.

A required-knowledge case contributes one opportunity per run and at most one
success when at least one non-duplicate retrieval is relevant under the case's
`knowledge_tags`. Every retrieval is independently eligible for unnecessary
and citation-utilization counts. Optional retrieval is neither rewarded nor
penalized solely for occurring, but it must be relevant and cited to avoid
those penalties.

Latency uses the scoreable behavior attempt's UTC start/finish timestamps.
Provider-token/cost totals cover only runs with actual provider usage and are
paired with `provider_usage_coverage_rate`; when coverage is zero all observed
usage totals are `None`. Missing usage is never estimated.

Latency p50/p95 use the deterministic nearest-rank method on sorted observed
latencies: one-based rank `ceil(p * n)`. No interpolation library default is
allowed to change report values.

---

## 47. Targets and Benchmark Report

```python
class TargetBands(BaseModel):
    model_config = ConfigDict(frozen=True)

    causal_macro_f1_min: float = 0.80
    first_tool_selection_min: float = 0.80
    observation_driven_replan_min: float = 0.80
    evidence_grounding_min: float = 1.00
    unsupported_claim_rate_max: float = 0.05
    unnecessary_tool_action_rate_max: float = 0.20
    timely_stopping_min: float = 0.80
    applicable_rule_usage_min: float = 0.80
    required_knowledge_usage_min: float = 0.80
    knowledge_citation_utilization_min: float = 1.00
    unnecessary_knowledge_retrieval_rate_max: float = 0.20


BenchmarkStatus = Literal["pending", "incomplete", "completed"]
TargetStatus = Literal["not_evaluated", "meets_target", "below_target"]
HarnessStatus = Literal["pending", "accepted"]


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: BenchmarkConfig
    config_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest: DatasetManifest
    harness_status: HarnessStatus
    benchmark_status: BenchmarkStatus
    target_status: TargetStatus
    targets: TargetBands
    agent_metrics: AggregateMetrics | None
    baseline_metrics: AggregateMetrics | None
    scores: tuple[RunScore, ...]
    traces: tuple[EvaluationTrace, ...]
    attempts: tuple[AttemptRecord, ...]
    warnings: tuple[str, ...] = ()


class ScoredRunArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_type: Literal["scored_run"] = "scored_run"
    trace: EvaluationTrace
    score: RunScore
    attempts: tuple[AttemptRecord, ...]


class UnscoredSlotArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_type: Literal["unscored_slot"] = "unscored_slot"
    execution_path: ExecutionPath
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    attempts: tuple[AttemptRecord, ...]


RunArtifact = Annotated[
    ScoredRunArtifact | UnscoredSlotArtifact,
    Field(discriminator="record_type"),
]
```

```python
def aggregate_benchmark(
    manifest: DatasetManifest,
    traces: tuple[EvaluationTrace, ...],
    scores: tuple[RunScore, ...],
    attempts: tuple[AttemptRecord, ...],
    config: BenchmarkConfig,
    targets: TargetBands,
    *,
    harness_status: HarnessStatus,
) -> BenchmarkReport:
    ...
```

The aggregator rejects duplicate `(execution_path, case_id, run_slot)` keys,
trace/score mismatches, and records referencing another dataset/configuration.
Official target metrics use held-out Agent traces only. Baseline held-out
metrics are reported alongside them; development results are retained outside
the target calculation. The aggregator never requires the Agent to beat the
baseline.

`config_fingerprint_sha256` hashes the canonical behavioral configuration:
dataset/profile identity, provider/model, prompt version/hash, model parameters,
SDK versions, repetitions, and retry policy. It excludes `benchmark_id` and
`started_at_utc`, so an honest later rerun has a new ID but the same fingerprint
when behavioral configuration is unchanged.

Target bands are V0.2 demonstration goals only. `below_target` is a valid
completed real-model result and never fails required CI.

Target comparison uses held-out Agent metrics with non-zero denominators. A
zero-denominator metric is explicitly not-applicable and does not independently
change target status. `benchmark_status` other than `completed` always yields
`target_status="not_evaluated"`.

---

## 48. Official Execution and Reporting Protocol

The official product configuration uses the provider-neutral
`BenchmarkConfig` and pins provider `deepseek`, model
`deepseek-v4-flash`, prompt version `v0.2-s1-planner-4` and its SHA-256, and five
repetitions for each held-out case. The 16 held-out cases therefore define 80
fixed Agent run slots. The deterministic baseline runs once per case.

Official execution is sequential (`max_concurrency=1`) in five rounds. Each
round visits held-out cases in manifest order, giving every case run slot 1
before any case receives slot 2. The baseline visits all cases once in manifest
order. Scheduling fields are part of the configuration fingerprint.

The official `model_parameters` includes the actual product-path values for
temperature `0.0`, JSON-object response format, and disabled DeepSeek thinking
mode. `ConfigValue` deliberately supports scalar/tuple values and at most two
nested object levels, which covers the frozen provider request without an
unbounded recursive schema. Omitting a parameter changes the configuration
fingerprint.

Development cases may be used for prompt tuning. After held-out results are
observed for a benchmark ID, that benchmark is append-only. A later run uses a
new benchmark ID.

Held-out cases are versioned and visible for reproducibility; they are not a
secret competition set. `held_out` means they are excluded from prompt/model
policy tuning for the official benchmark and their observed failures cannot be
used to overwrite that benchmark.

Only transport timeout, 429, and provider 5xx errors are retryable
infrastructure errors, up to `max_infrastructure_retries`. Authentication and
configuration failures are not retried. Invalid planner output and every
Runtime termination are behavioral outcomes and keep their original run slot.

Missing credentials/service access leaves `benchmark_status="pending"`.
Exhausted infrastructure retries or evaluator failures leave it `incomplete`.
All 80 scoreable terminal behavior slots produce `completed`, independently of
target status.

The runner performs credential, dependency, provider/model, prompt-hash, and
dataset/profile preflight before scheduling a held-out slot. A preflight failure
is `pending`. If execution has already produced any held-out behavior result,
an equivalent later configuration/provider failure makes that benchmark
`incomplete` rather than erasing earlier runs.

```python
def write_benchmark_bundle(
    report: BenchmarkReport,
    output_dir: Path,
) -> tuple[Path, ...]:
    ...
```

The writer creates exactly:

```text
benchmark_manifest.json
runs.jsonl
metrics.json
case_summary.csv
report.md
checksums.sha256
```

under `docs/evaluations/phase4/<benchmark_id>/`. An existing destination is an
error. JSON and JSONL use stable key ordering; CSV has a frozen header; Markdown
contains all failures and run variation. The representations must agree on run
counts and aggregates. Raw provider responses remain in a gitignored local
directory and are never committed.

All bundle files use UTF-8, LF line endings, and a final newline. JSON numbers
must be finite; canonical JSON/JSONL uses sorted keys and no platform-specific
path separators.

The representation schemas are:

- `benchmark_manifest.json`: `config`, `config_fingerprint_sha256`, and the
  complete `DatasetManifest`;
- `runs.jsonl`: one `ScoredRunArtifact` per trace/score pair plus one
  `UnscoredSlotArtifact` for every scheduled slot without a scoreable trace;
- `metrics.json`: harness/benchmark/target statuses, `TargetBands`, Agent and
  baseline aggregates, and warnings;
- `case_summary.csv`: one row per scored run using the exact header below;
- `report.md`: required sections Configuration, Dataset, Acceptance Status,
  Agent Metrics, Baseline Metrics, Per-Case Variation, Failures, and
  Limitations;
- `checksums.sha256`: SHA-256 entries for the other five files, excluding
  itself.

```text
execution_path,case_id,split,category,run_slot,causal_exact_set_correct,
outcome_correct,evidence_grounding_rate,unsupported_claim_rate,
first_tool_correct,observation_driven_replan_rate,
unnecessary_tool_action_rate,timely_stop,applicable_rule_usage_rate,
required_knowledge_usage_rate,unnecessary_knowledge_retrieval_rate,
knowledge_citation_utilization_rate,tool_actions,planner_calls,
end_to_end_latency_ms,input_tokens,output_tokens,total_tokens,cost_usd,
completion_reason,failure_codes
```

The displayed line wrapping above is editorial; the actual CSV header is one
line with those fields in that order. Tuple failure codes use a stable
semicolon-separated encoding.

---

## 49. Phase 4 Public Surface and Gate

### 49.1 Public exports

```text
evaluation.models
    EvaluationSplit, EvaluationCategory, CausalFault, DiagnosisClaimType
    KnowledgePolicy, EvidenceComparator
    HarmonicRatioSpec and five typed SyntheticSignalSpec variants
    SyntheticSignalSpec
    EvidenceCondition, SufficientEvidenceSet
    CombinedIdentifiabilitySpec, EvaluationCase, DatasetManifest
    DatasetValidationIssue, DatasetValidationReport
    ProviderUsage, PlannerCallStatus, PlannerDecisionRecord
    PlannerDecisionEvent, ObservationEvent
    RuleEvaluationEvent, KnowledgeRetrievalEvent, EvaluationEvent
    ExecutionPath, ConfigScalar, ConfigObject, ConfigValue
    BaselineCompletionReason
    AttemptStatus, AttemptErrorCode
    BenchmarkConfig, AttemptRecord, EvaluationTrace
    BaselineDiagnosis, BaselineRunResult
    RateMetric, RunScore, AggregateMetrics, TargetBands, BenchmarkReport
    ScoredRunArtifact, UnscoredSlotArtifact, RunArtifact

evaluation.dataset
    load_dataset_manifest, validate_dataset

evaluation.recording
    RecordingPlanner, assemble_evaluation_trace

evaluation.baseline
    FixedPipelineBaseline

evaluation.scoring
    score_evaluation_trace, aggregate_benchmark

evaluation.reporting
    write_benchmark_bundle
```

The operational entry point is:

```text
python -m signal_diag.evaluation validate-dataset
python -m signal_diag.evaluation run-deterministic
python -m signal_diag.evaluation run-real
python -m signal_diag.evaluation render-report
```

Real-model credentials are read only from the environment or the existing
provider configuration boundary. There is no plaintext credential CLI
argument.

### 49.2 Acceptance gate

Deterministic `harness_accepted` requires T001–T183, zero required skip/xfail,
Ruff, mypy, `git diff --check`, and the Phase 4 architecture boundary to pass.

Full Phase 4 acceptance additionally requires `benchmark_completed` with an
immutable official report bundle. A below-target result is honest completion;
`pending` or `incomplete` is not. Phase 5 remains gated until full Phase 4
acceptance.

The written-spec review gate passed on 2026-08-29. Implementation planning is
authorized; code changes remain gated on the completed task-level plan and an
explicit execution choice.

---

## 50. Phase 4.1 Additive Behavior Gate

Phase 4.1 is an additive behavior-calibration gate. It does not reopen
§§41–§49 or T125–T183. The written design at
`docs/superpowers/specs/2026-08-30-phase4-1-agent-behavior-improvement-design.md`
was approved on 2026-08-30. D021 records the process rules.

The following statements are normative:

```text
Phase 4.1 preserves the v4/v1.0.0 official campaign and adds a v5/v1.1.0 campaign.
v5 changes planner instruction only; public Planner, Runtime, evaluation, scoring,
and report interfaces remain unchanged.
Causal distortion presence and configured rule acceptance are independent facts.
Rule PASS never erases supported causal Evidence.
Knowledge is selectively required by observable invalid/not-applicable state,
never by planner-visible evaluation labels.
Development uses 8 cases x 5 slots; official held-out uses 16 x 5 slots.
Phase 4.1 acceptance requires completed/meets_target and T001–T195 green.
```

The first official v1.0.0 DeepSeek benchmark at `b68ec5e` remains the immutable
diagnostic baseline. Its status is `completed/below_target`: the evaluation
harness completed honestly, and the result is not a product-quality behavior
pass.

Phase 4.1 deterministic implementation is complete at `cadc15d`; T184–T195
green (499 passed, ruff/mypy/`git diff --check b68ec5e..HEAD` clean).
Real-model gates are not done: 40-slot development then, only if
`meets_target`, one-shot 80-slot official held-out. Phase 4.1 is not accepted.
Phase 5 remains gated until Phase 4.1 reaches `completed/meets_target` with
T001–T195 green.

---

## 51. Phase 4.1 Additive Prompt v6 Correction Gate

The immutable v5 development campaign at `f9392c2` completed honestly with
`target_status=below_target`. Its bundle remains at
`docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/`.
Observed failures are concentrated in mutually inconsistent v4 examples and
the policy appendix used to construct v5. Section 51 authorizes one additive
prompt-only correction without reopening §50, §§41–§49, or any Phase 1–4
public interface. The written design at
`docs/superpowers/specs/2026-08-30-phase4-1-prompt-v6-correction-design.md`
was approved on 2026-08-30. D022 records the compatibility and evaluation
decision.

The following statements are normative:

```text
v4 and v5 prompt bytes, SHA-256 identities, planner builders, campaign routes,
configuration fingerprints, and committed report bundles remain reproducible.

The additive product prompt version is v0.2-s1-planner-6. Its system prompt is
one coherent immutable prompt, not v4 plus an appendix and not v5 plus an
appendix. Its exact UTF-8 bytes determine the SHA-256 identity frozen by T196
before any real-model v6 campaign runs.

RealLLMPlanner remains the product path and selects v6 after implementation.
Private legacy planners may select exact v4 or v5 identities only to reproduce
their historical campaigns. ScriptedPlanner and fake transports remain test
doubles and are never silent product fallbacks.

The runtime does not force DSP, rule, or knowledge actions. Numerical values
remain DSP-produced; configured thresholds remain profile-produced. Raw
waveforms, full FFT arrays, generator truth, expected faults, dataset policy,
and scoring targets never enter PlannerContext or outbound LLM messages.

The v6 prompt keeps every viable clipping or harmonic hypothesis open until it
is supported, ruled out, or explicitly unobservable. It does not prescribe a
fixed Tool sequence.

Observed causal distortion and configured rule acceptance are independent
facts. Rule PASS never erases supported harmonic or clipping Evidence.

no_supported_fault is a final empty-cause-set conclusion. It is not emitted as
an additional cause beside a supported fault and does not replace an observed
distortion merely because a configured rule passes.

An inconclusive diagnosis contains a traceable claim. The claim cites same-run
Evidence, cites an applicable same-run rule evaluation or states why no rule is
applicable, cites same-run knowledge when retrieval was used, and includes a
non-empty limitation.

Existing phase4.1-development and phase4.1-official campaign choices remain
bound to v5. New phase4.1-v6-development and phase4.1-v6-official choices bind
v6 without changing public evaluation or report models.

The v6 development benchmark ID is bench_phase4_1_dev_v6_gate2. It uses only
the existing v1.1.0 development split: 8 cases x 5 slots. A result other than
completed/meets_target is retained honestly and stops v6 before held-out.

The v6 official benchmark ID is bench_official_s1_v11_planner6_gate2. It may
run exactly once only after the development gate is completed/meets_target,
using the byte-identical approved candidate and the sealed v1.1.0 held-out
split: 16 cases x 5 slots. Existing target bands are unchanged.

Phase 4.1 acceptance requires the v6 official gate to be
completed/meets_target, all 80 Agent slots scoreable, the append-only six-file
bundle valid, and T001–T200 plus Ruff, mypy, architecture, and diff-check green.
Phase 5 remains gated until independent Phase 4.1 acceptance.
```

If v6 development gate2 is below target, incomplete, or pending, the result is
preserved and no v1.1.0 held-out case is run or inspected. A further prompt
version, PlannerContext change, model change, runtime change, target change, or
new dataset campaign requires a separate written design decision. If the
one-shot official gate2 is below target, its result is preserved, Phase 4.1
remains unaccepted, and the same held-out set is not used for tuning or rerun.
