# Signal Diagnosis Agent — Frozen Contracts V0.1

**Document:** `CONTRACTS_V0_1.md`  
**Contract version:** `0.1`  
**Status:** Frozen for Phase 1

---

# 1. Contract Policy

This document defines the approved Phase 1 public interfaces.

Coding agents must not silently:

- rename modules;
- rename public classes;
- rename public functions;
- change argument meaning;
- change return types;
- change waveform shape conventions;
- add hidden normalization;
- collapse DSP and Tool layers.

If an implementation discovers a concrete contradiction or correctness problem in this document:

1. do not silently change the contract;
2. document the issue;
3. propose a minimal correction;
4. obtain explicit approval before changing a public interface.

Internal private helpers may evolve freely as long as public behavior remains unchanged.

---

# 2. Package Layout

Required Phase 1 structure:

```text
src/
└── signal_diag/
    ├── signal/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── exceptions.py
    │   ├── factory.py
    │   ├── repository.py
    │   ├── segment.py
    │   └── synthetic.py
    │
    ├── dsp/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── preprocess.py
    │   ├── clipping.py
    │   ├── spectrum.py
    │   └── pitch.py
    │
    └── tools/
        ├── __init__.py
        ├── contracts.py
        ├── results.py
        ├── service.py
        ├── registry.py
        └── evidence.py
```

The following may be added later but are not required in Phase 1:

```text
dsp/statistics.py
dsp/distortion.py
dsp/harmonics.py
dsp/snr.py
dsp/drift.py
agent/
rules/
report/
evaluation/
```

---

# 3. Signal Type Aliases

Location:

```text
signal/models.py
```

Required:

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
```

---

# 4. `TimeRange`

```python
from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    start_s: float = Field(
        default=0.0,
        ge=0.0,
    )

    end_s: float | None = Field(
        default=None,
        gt=0.0,
    )
```

Semantic convention:

```text
[start_s, end_s)
```

The interval is left-closed and right-open.

Additional semantic validation may reject:

```text
end_s <= start_s
```

either during model validation or segment extraction.

---

# 5. `SignalMeta`

```python
from pydantic import BaseModel, Field


class SignalMeta(BaseModel):
    signal_id: str

    source_type: SourceType
    filename: str | None = None

    sample_rate_hz: int = Field(gt=0)

    channels: int = Field(gt=0)
    num_samples: int = Field(gt=0)

    duration_s: float = Field(gt=0)

    original_dtype: str

    amplitude_unit: str = "FS"
```

Required interpretation:

```text
duration_s =
num_samples / sample_rate_hz
```

for the canonical stored signal.

---

# 6. `SignalRecord`

```python
from dataclasses import dataclass

import numpy as np


@dataclass(
    frozen=True,
    slots=True,
)
class SignalRecord:
    meta: SignalMeta
    samples: np.ndarray
```

Canonical sample contract:

```text
dtype:
float32

shape:
(num_samples, channels)
```

Mono example:

```text
(96000, 1)
```

Stereo example:

```text
(96000, 2)
```

The repository must not store mono data as `(N,)`.

---

# 7. Signal Exceptions

Location:

```text
signal/exceptions.py
```

Required hierarchy:

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


class DSPNotApplicableError(SignalError):
    """
    Algorithm executed normally, but the requested
    metric is not applicable to the current signal.
    """
```

`DSPNotApplicableError` is not equivalent to an internal program error.

---

# 8. Signal Factory

Location:

```text
signal/factory.py
```

Public function:

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
2. reject empty signals;
3. reject NaN/Inf;
4. preserve the original dtype in metadata;
5. convert integer PCM to float32 full-scale values;
6. cast floating-point input to float32;
7. do not peak-normalize floating-point input;
8. convert `(N,)` input to `(N,1)`;
9. accept `(N,C)` input;
10. reject other dimensions;
11. generate a signal ID when none is supplied;
12. return contiguous float32 storage.

Suggested ID form:

```text
sig_<random-or-unique-token>
```

The exact token generation is internal behavior.

---

# 9. Full-Scale Conversion

Private helper may be implemented as:

```python
def _to_full_scale_float32(
    samples: np.ndarray,
) -> np.ndarray:
    ...
```

Required behavior for signed integer types:

```text
float_value ≈ integer_value / full_scale
```

For `int16`:

```text
-32768 → -1.0
32767  → approximately 0.9999695
```

Floating-point arrays must not be peak normalized.

Input:

```text
[0.0, 0.25, -0.5]
```

must remain approximately:

```text
[0.0, 0.25, -0.5]
```

---

# 10. Repository Interface

Location:

```text
signal/repository.py
```

Required abstract interface:

```python
from abc import ABC, abstractmethod


class SignalRepository(ABC):

    @abstractmethod
    def put(
        self,
        record: SignalRecord,
    ) -> None:
        ...

    @abstractmethod
    def get(
        self,
        signal_id: str,
    ) -> SignalRecord:
        ...

    @abstractmethod
    def exists(
        self,
        signal_id: str,
    ) -> bool:
        ...

    @abstractmethod
    def remove(
        self,
        signal_id: str,
    ) -> None:
        ...

    @abstractmethod
    def list_meta(
        self,
    ) -> list[SignalMeta]:
        ...
```

Phase 1 implementation:

```python
class InMemorySignalRepository(
    SignalRepository
):
    ...
```

Required repository behavior:

- repository owns a copy of inserted waveform data;
- mutation of the caller's original array after `put()` must not affect stored data;
- stored waveform must be non-writeable;
- missing IDs raise `SignalNotFoundError`;
- `exists()` does not raise for missing IDs;
- `list_meta()` does not expose waveform arrays.

---

# 11. Segment Extraction

Location:

```text
signal/segment.py
```

Public function:

```python
def extract_segment(
    record: SignalRecord,
    *,
    time_range: TimeRange | None = None,
    channel: ChannelMode = "mixdown",
) -> np.ndarray:
    ...
```

Required output:

```text
one-dimensional numeric array
shape = (selected_num_samples,)
```

Required behavior:

## Mono

Any valid default selection returns:

```text
record.samples[:, 0]
```

## Stereo `left`

Returns channel 0.

## Stereo `right`

Returns channel 1.

## `mixdown`

Returns channel mean.

For stereo:

```text
mixdown[n] =
(left[n] + right[n]) / 2
```

Required time conversion:

```text
sample_index ≈ round(time_seconds * sample_rate)
```

Invalid or empty ranges must raise:

```text
InvalidTimeRangeError
```

The function must return a writable working array/copy and must not expose mutable repository backing storage.

---

# 12. Synthetic Ground Truth

Location:

```text
signal/synthetic.py
```

Required:

```python
from pydantic import BaseModel


class SyntheticGroundTruth(BaseModel):
    generator: str

    fault_type: str | None = None

    parameters: dict[
        str,
        float | int | str,
    ]
```

Required wrapper:

```python
from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class SyntheticCase:
    record: SignalRecord
    ground_truth: SyntheticGroundTruth
```

---

# 13. `generate_sine`

Required signature:

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

Required mathematical form:

```text
x(t) =
amplitude *
sin(
    2π * frequency_hz * t
    + phase_rad
)
+ dc_offset
```

Ground truth must include at least:

```text
frequency_hz
amplitude
dc_offset
```

`fault_type`:

```text
None
```

---

# 14. `generate_clipped_sine`

Required signature:

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

Required clipping model:

```text
clean =
amplitude * sin(2πft)

clipped =
clip(
    clean,
    -clip_level,
    +clip_level
)
```

Required constraint:

```text
0 < clip_level <= 1
```

Ground truth:

```text
generator:
clipped_sine

fault_type:
clipping
```

Required parameters:

```text
frequency_hz
input_amplitude
clip_level
```

---

# 15. `generate_white_noise`

Required signature:

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

Required random API:

```python
np.random.default_rng(seed)
```

Required behavior:

- approximately zero mean;
- approximately requested RMS for sufficiently long signals;
- deterministic for equal seeds;
- different seeds should normally produce different samples.

Ground truth:

```text
generator:
white_noise
```

`fault_type` may be:

```text
noise
```

Required parameters:

```text
rms
seed
```

---

# 16. DSP Result Models

Location:

```text
dsp/models.py
```

## 16.1 Clipping

```python
@dataclass(
    frozen=True,
    slots=True,
)
class ClippingAnalysis:
    detected: bool

    clipping_ratio: float
    clipped_samples: int

    clipping_events: int
    longest_event_samples: int

    peak_abs: float

    full_scale_detected: bool
    flat_top_detected: bool
```

---

## 16.2 Spectrum peak

```python
@dataclass(
    frozen=True,
    slots=True,
)
class SpectrumPeak:
    frequency_hz: float
    magnitude_db: float
```

`magnitude_db` means relative magnitude in Phase 1.

---

## 16.3 FFT

```python
@dataclass(
    frozen=True,
    slots=True,
)
class FFTAnalysis:
    frequencies_hz: np.ndarray
    magnitude_db: np.ndarray

    frequency_resolution_hz: float

    dominant_frequency_hz: float | None
    dominant_magnitude_db: float | None

    spectral_centroid_hz: float | None

    peaks: tuple[
        SpectrumPeak,
        ...,
    ]
```

---

## 16.4 F0

```python
@dataclass(
    frozen=True,
    slots=True,
)
class F0Estimate:
    f0_hz: float | None

    confidence: float

    voiced: bool

    method: str
```

Phase 1 method name:

```text
autocorrelation
```

---

# 17. DSP Preprocessing Helpers

Location:

```text
dsp/preprocess.py
```

Required signatures:

```python
def remove_dc(
    samples: np.ndarray,
) -> np.ndarray:
    ...
```

```python
def rms(
    samples: np.ndarray,
) -> float:
    ...
```

```python
def peak_abs(
    samples: np.ndarray,
) -> float:
    ...
```

These functions must not mutate the caller's signal.

---

# 18. Clipping Analysis

Location:

```text
dsp/clipping.py
```

Required public signature:

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

Input contract:

```text
one-dimensional numeric array
```

Required validation:

- non-empty;
- one-dimensional;
- finite values.

Required detection components:

```text
full-scale saturation
flat-top saturation
```

The implementation may use private run-detection helpers.

Example private helper:

```python
def _find_runs(
    mask: np.ndarray,
) -> list[
    tuple[int, int]
]:
    ...
```

A clean sine with amplitude significantly below full scale must not normally be flagged.

A clipped sine at:

```text
clip_level = 0.5
```

must be detectable through the flat-top mechanism even though it never approaches `0.99 FS`.

---

# 19. FFT Analysis

Location:

```text
dsp/spectrum.py
```

Required signature:

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

1. require one-dimensional samples;
2. require a positive sample rate;
3. reject signals that are too short;
4. optionally remove DC;
5. apply requested window;
6. use real FFT;
7. produce frequency bins;
8. produce relative magnitude dB;
9. identify dominant non-DC frequency;
10. compute frequency resolution;
11. compute spectral centroid where meaningful;
12. identify up to `max_peaks` strong local peaks.

Phase 1 magnitude convention:

```text
max magnitude = 0 dB
```

Tool-facing code must call it relative magnitude.

---

# 20. F0 Estimation

Location:

```text
dsp/pitch.py
```

Required signature:

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

Required input validation:

```text
sample_rate_hz > 0
fmin_hz > 0
fmax_hz > fmin_hz
```

Required algorithmic stages:

```text
1. convert to float
2. remove DC
3. reject negligible energy
4. apply window
5. FFT-based autocorrelation
6. normalize by zero-lag autocorrelation
7. restrict lag search range
8. find strongest candidate
9. estimate confidence
10. optionally refine lag by local parabolic interpolation
11. compare against voicing threshold
```

Unreliable signal:

```python
F0Estimate(
    f0_hz=None,
    voiced=False,
    ...
)
```

is valid behavior.

The implementation must not always return a numeric F0.

---

# 21. Tool Input Contracts

Location:

```text
tools/contracts.py
```

The Agent-facing Tool arguments must **not** contain `signal_id`.

`signal_id` is runtime context and is injected by application/Agent runtime.

---

# 22. `ClippingInput`

```python
class ClippingInput(BaseModel):
    time_range: TimeRange | None = None

    channel: ChannelMode = "mixdown"

    full_scale_threshold: float = Field(
        default=0.99,
        gt=0.0,
    )
```

Additional internal clipping parameters may use implementation defaults during Phase 1.

---

# 23. `ClippingOutput`

```python
class ClippingOutput(BaseModel):
    detected: bool

    clipping_ratio: float

    clipped_samples: int
    clipping_events: int

    longest_event_samples: int

    peak_abs: float

    full_scale_detected: bool
    flat_top_detected: bool
```

---

# 24. `FFTInput`

```python
class FFTInput(BaseModel):
    time_range: TimeRange | None = None

    channel: ChannelMode = "mixdown"

    window: str = "hann"

    n_fft: int | None = None

    max_peaks: int = Field(
        default=10,
        ge=1,
        le=20,
    )
```

---

# 25. `SpectrumPeakOutput`

```python
class SpectrumPeakOutput(BaseModel):
    frequency_hz: float

    relative_magnitude_db: float
```

---

# 26. `FFTOutput`

```python
class FFTOutput(BaseModel):
    frequency_resolution_hz: float

    dominant_frequency_hz: float | None

    spectral_centroid_hz: float | None

    spectral_peaks: list[
        SpectrumPeakOutput
    ]
```

Full FFT arrays must not appear here.

---

# 27. `F0Input`

```python
class F0Input(BaseModel):
    time_range: TimeRange | None = None

    channel: ChannelMode = "mixdown"

    fmin_hz: float = Field(
        default=50.0,
        gt=0.0,
    )

    fmax_hz: float = Field(
        default=1000.0,
        gt=0.0,
    )
```

The implementation must validate:

```text
fmax_hz > fmin_hz
```

---

# 28. `F0Output`

```python
class F0Output(BaseModel):
    f0_hz: float | None

    confidence: float

    voiced: bool

    method: str
```

---

# 29. Standard Tool Result

Location:

```text
tools/results.py
```

Required generic contract:

```python
from typing import (
    Generic,
    Literal,
    TypeVar,
)

from pydantic import (
    BaseModel,
    Field,
)


T = TypeVar("T")


class ToolResult(
    BaseModel,
    Generic[T],
):
    call_id: str

    tool_name: str

    status: Literal[
        "success",
        "invalid",
        "error",
    ]

    result: T | None = None

    warnings: list[str] = Field(
        default_factory=list
    )

    error_message: str | None = None
```

Required semantic rules:

```text
success:
meaningful numeric result

invalid:
software worked, metric not reliable/applicable

error:
execution failed
```

---

# 30. Tool Service

Location:

```text
tools/service.py
```

Required class:

```python
class SignalToolService:

    def __init__(
        self,
        repository: SignalRepository,
    ) -> None:
        ...
```

Required Phase 1 public methods:

```python
def detect_clipping(
    self,
    signal_id: str,
    args: ClippingInput,
) -> ToolResult[ClippingOutput]:
    ...
```

```python
def fft_analysis(
    self,
    signal_id: str,
    args: FFTInput,
) -> ToolResult[FFTOutput]:
    ...
```

```python
def estimate_f0(
    self,
    signal_id: str,
    args: F0Input,
) -> ToolResult[F0Output]:
    ...
```

The service:

1. retrieves the record;
2. extracts the selected segment/channel;
3. calls deterministic DSP;
4. maps DSP results to compact Tool outputs.

---

# 31. F0 Tool Status Mapping

For F0:

```text
voiced = True
→ success
```

```text
voiced = False
→ invalid
```

An invalid F0 should normally include a warning such as:

```text
No reliable periodic component detected.
```

It should not return a fabricated frequency.

---

# 32. Tool Registry

Location:

```text
tools/registry.py
```

Phase 1 may define metadata for:

```text
detect_clipping
fft_analysis
estimate_f0
```

Suggested conceptual structure:

```python
TOOL_METADATA = {
    "detect_clipping": {
        "description": "...",
    },

    "fft_analysis": {
        "description": "...",
    },

    "estimate_f0": {
        "description": "...",
    },
}
```

The exact registry implementation is not strongly frozen in Phase 1 because the Agent runtime does not yet exist.

The public Tool Service methods are the authoritative interface.

---

# 33. Evidence Layer

Location reserved:

```text
tools/evidence.py
```

Phase 1 may contain basic adapters or remain minimal.

Future evidence records should look conceptually like:

```python
class Evidence(BaseModel):
    evidence_id: str

    source_tool: str

    metric: str

    value: (
        float
        | int
        | bool
        | str
    )

    unit: str | None = None

    interpretation_hint: str | None = None

    confidence: float | None = None
```

Evidence IDs are primarily required by the later Agent layer and are not mandatory for Phase 1 DSP acceptance.

---

# 34. Future Contracts — Reserved but Not Implemented

The following Tool names are reserved for later phases:

```text
get_signal_info
signal_statistics
calculate_snr
calculate_thd
harmonic_analysis
detect_frequency_drift
```

The current Phase 1 implementation must not create speculative versions of these simply to fill out the registry.

---

# 35. Future Agent State — Informational Only

Not Phase 1 implementation.

Expected later state concept:

```python
class DiagnosisState(TypedDict):
    signal_id: str
    user_query: str

    signal_meta: dict

    objective: str | None
    task_type: str | None
    hypotheses: list[str]

    next_action: dict | None

    pending_tool_call: dict | None
    last_tool_result: dict | None

    tool_history: list[dict]
    evidence: list[dict]
    rule_results: list[dict]

    tool_call_count: int
    max_tool_calls: int

    retry_count: int
    max_retries: int

    no_progress_count: int
    max_no_progress: int

    errors: list[str]

    termination_reason: str | None

    diagnosis: dict | None
    report: dict | None

    finished: bool
```

This section is informational and must not trigger Agent implementation during Phase 1.

---

# 36. Contract Summary

Frozen Phase 1 public surface:

```text
signal.models
    TimeRange
    SignalMeta
    SignalRecord
    SourceType
    ChannelMode

signal.factory
    build_signal_record

signal.repository
    SignalRepository
    InMemorySignalRepository

signal.segment
    extract_segment

signal.synthetic
    SyntheticGroundTruth
    SyntheticCase
    generate_sine
    generate_clipped_sine
    generate_white_noise

dsp.models
    ClippingAnalysis
    SpectrumPeak
    FFTAnalysis
    F0Estimate

dsp.preprocess
    remove_dc
    rms
    peak_abs

dsp.clipping
    analyze_clipping

dsp.spectrum
    analyze_fft

dsp.pitch
    estimate_f0_autocorrelation

tools.contracts
    ClippingInput
    ClippingOutput
    FFTInput
    SpectrumPeakOutput
    FFTOutput
    F0Input
    F0Output

tools.results
    ToolResult

tools.service
    SignalToolService
        detect_clipping
        fft_analysis
        estimate_f0
```

Any change to this public surface during Phase 1 requires explicit approval.