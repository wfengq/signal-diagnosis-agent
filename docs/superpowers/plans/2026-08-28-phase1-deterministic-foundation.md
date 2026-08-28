# Phase 1 Deterministic Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (only when the user explicitly
> authorizes subagents) or `superpowers:executing-plans` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete deterministic Signal → DSP → Tool → Evidence
foundation required by Scenario S1 and pass required tests T001–T063.

**Architecture:** Implement a layered Python package in dependency order:
`signal` owns canonical data and synthetic cases, `dsp` owns numerical
algorithms, and `tools` owns compact Agent-facing adapters and deterministic
Evidence. Phase 1 creates no Agent, LLM, rules, RAG, API, UI, or WAV loader.

**Tech Stack:** Python 3.11+, NumPy, Pydantic V2, pytest, setuptools src layout;
Ruff and mypy are development checks when configured.

**Spec:** `docs/ARCHITECTURE_V0_2.md`, `docs/CONTRACTS_V0_2.md`, and
`docs/TEST_PLAN_V0_2.md`.

## Global Constraints

- Preserve dependency direction `signal → dsp → tools`; lower layers never
  import higher layers.
- Repository waveforms are C-contiguous `float32` with shape `(N, C)`.
- Integer signed PCM is converted to floating full scale; floating input is not
  peak-normalized.
- Repository-owned waveform data is immutable and isolated from caller arrays.
- DSP functions receive finite one-dimensional arrays and never mutate input.
- Numerical metrics come only from deterministic DSP code.
- Tool inputs do not contain `signal_id`; runtime/service composition injects it.
- Tool outputs contain no waveform or full FFT arrays.
- Required random data uses explicit seeds.
- Required T001–T063 tests may not be skipped or xfailed.
- Follow RED → verify failure → GREEN → focused test → accumulated suite for
  every task.
- Do not create Agent, LangGraph, LLM, rules, RAG, API, UI, WAV, persistence,
  Docker, or deployment modules in Phase 1.
- Do not commit or push unless the user explicitly requests it. This plan uses a
  review gate instead of an automatic commit step.

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | package metadata, runtime/dev dependencies, pytest config |
| `src/signal_diag/signal/models.py` | signal aliases, `TimeRange`, metadata, canonical record |
| `src/signal_diag/signal/exceptions.py` | signal-domain exceptions |
| `src/signal_diag/signal/factory.py` | validation, PCM conversion, canonical record construction |
| `src/signal_diag/signal/repository.py` | abstract repository and immutable in-memory storage |
| `src/signal_diag/signal/segment.py` | time/channel selection into writable 1-D arrays |
| `src/signal_diag/signal/synthetic.py` | deterministic S1 generators and ground truth |
| `src/signal_diag/dsp/models.py` | frozen deterministic DSP result containers |
| `src/signal_diag/dsp/preprocess.py` | common input validation, DC, RMS, peak helpers |
| `src/signal_diag/dsp/clipping.py` | full-scale and flat-top clipping analysis |
| `src/signal_diag/dsp/spectrum.py` | real FFT and compact peak discovery |
| `src/signal_diag/dsp/pitch.py` | autocorrelation fundamental baseline |
| `src/signal_diag/dsp/harmonics.py` | harmonic association and THD metric |
| `src/signal_diag/tools/contracts.py` | compact validated Tool input/output models |
| `src/signal_diag/tools/evidence.py` | deterministic scalar Evidence model |
| `src/signal_diag/tools/results.py` | generic Tool result and status invariants |
| `src/signal_diag/tools/registry.py` | four unordered Tool descriptors |
| `src/signal_diag/tools/service.py` | repository/segment/DSP adapters and Evidence creation |
| `tests/conftest.py` | canonical deterministic fixtures |
| `tests/signal/*.py` | T001–T024 |
| `tests/dsp/*.py` | T025–T052 |
| `tests/tools/*.py` | T053–T063 |

## Task-to-Test Map

| Task | Required IDs |
|---|---|
| 1. Project skeleton, signal models, factory | T001–T006 |
| 2. Immutable repository | T007–T011 |
| 3. Segment and channels | T012–T016 |
| 4. Basic synthetic generators | T017–T020 |
| 5. Harmonic and combined generators | T021–T024 |
| 6. DSP models and preprocessing | T025–T027 |
| 7. Clipping DSP | T028–T032 |
| 8. Spectrum DSP | T033–T038 |
| 9. Fundamental DSP | T039–T043 |
| 10. Harmonic-distortion DSP | T044–T052 |
| 11. Tool contracts, results, Evidence, registry | T062–T063 plus contract support |
| 12. Tool Service integration | T053–T061 |
| 13. Phase 1 architecture and full verification | accumulated T001–T063 |

---

### Task 1: Project Skeleton, Signal Models, and Factory

**Files:**

- Create: `pyproject.toml`
- Create: `src/signal_diag/__init__.py`
- Create: `src/signal_diag/signal/__init__.py`
- Create: `src/signal_diag/signal/models.py`
- Create: `src/signal_diag/signal/exceptions.py`
- Create: `src/signal_diag/signal/factory.py`
- Create: `tests/__init__.py`
- Create: `tests/signal/__init__.py`
- Create: `tests/signal/test_factory.py`

**Interfaces:**

- Produces: `SourceType`, `ChannelMode`, `FaultLabel`, `TimeRange`, `SignalMeta`,
  `SignalRecord`, `InvalidSignalError`, and `build_signal_record` exactly as
  frozen in Contracts Sections 4–6.
- Consumed by: every later task.

**Owned tests:** T001, T002, T003, T004, T005, T006.

- [ ] **Step 1: Add packaging metadata and write failing T001–T006 tests**

Use this minimal project configuration:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "signal-diagnosis-agent"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = [
  "numpy>=1.26",
  "pydantic>=2.7,<3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "ruff>=0.8",
  "mypy>=1.10",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

Create tests with these exact public behaviors:

```python
def test_t001_mono_is_canonical_float32():
    record = build_signal_record(
        np.array([0.0, 0.1, -0.2], dtype=np.float64),
        sample_rate_hz=48_000,
        source_type="generated",
    )
    assert record.samples.shape == (3, 1)
    assert record.samples.dtype == np.float32
    assert record.samples.flags.c_contiguous


def test_t002_float_input_is_not_peak_normalized():
    record = build_signal_record(
        np.array([0.0, 0.25, -0.5], dtype=np.float64),
        sample_rate_hz=48_000,
        source_type="generated",
    )
    assert np.max(np.abs(record.samples)) == pytest.approx(0.5, abs=1e-6)


def test_t003_int16_uses_signed_full_scale():
    record = build_signal_record(
        np.array([-32768, 0, 32767], dtype=np.int16),
        sample_rate_hz=48_000,
        source_type="generated",
    )
    np.testing.assert_allclose(
        record.samples[:, 0],
        [-1.0, 0.0, 32767 / 32768],
        atol=1e-6,
    )
    assert record.meta.original_dtype == "int16"
```

Add parametrized T004 cases for empty, NaN, Inf, rank 0/rank 3, and sample rates
`0` and `-1`. Add T005 with `np.uint8` expecting `InvalidSignalError`. Add T006
assertions for `sig_` prefix, duration, channels, samples, inconsistent direct
`SignalMeta`, and a direct `SignalRecord` whose shape disagrees with metadata.

- [ ] **Step 2: Run T001–T006 and verify RED**

Run:

```powershell
python -m pytest tests/signal/test_factory.py -v
```

Expected: collection/import failure because the package and public models are
not implemented. After adding empty package files, expected failures must be due
to missing models/behavior rather than test syntax.

- [ ] **Step 3: Implement the minimal canonical models and factory**

Implement Pydantic semantic validation and dataclass validation exactly once.
The conversion core should follow:

```python
def _to_float32(samples: np.ndarray) -> np.ndarray:
    if np.issubdtype(samples.dtype, np.unsignedinteger):
        raise InvalidSignalError("unsigned PCM is not supported in V0.2")
    if np.issubdtype(samples.dtype, np.signedinteger):
        bits = np.iinfo(samples.dtype).bits
        scaled = samples.astype(np.float64) / float(2 ** (bits - 1))
        return scaled.astype(np.float32)
    if np.issubdtype(samples.dtype, np.floating):
        return samples.astype(np.float32, copy=True)
    raise InvalidSignalError(f"unsupported dtype: {samples.dtype}")
```

Cast the integer branch to `float32` after division, reshape mono with
`values[:, None]`, call `np.ascontiguousarray`, derive metadata, and return the
validated record. Do not call any normalization function.

Use an absolute `1e-12` duration consistency check in `SignalMeta`, and validate
canonical dtype/rank/shape/contiguity/finiteness in `SignalRecord.__post_init__`.

- [ ] **Step 4: Run focused GREEN tests**

Run:

```powershell
python -m pytest tests/signal/test_factory.py -v
```

Expected: T001–T006 pass.

- [ ] **Step 5: Run accumulated suite and review scope**

Run:

```powershell
python -m pytest -q
```

Confirm no Agent/DSP/Tool modules were created. Do not commit without explicit
user authorization.

---

### Task 2: Immutable In-Memory Repository

**Files:**

- Create: `src/signal_diag/signal/repository.py`
- Create: `tests/signal/test_repository.py`
- Modify: `src/signal_diag/signal/__init__.py`

**Interfaces:**

- Consumes: `SignalMeta`, `SignalRecord`, `SignalNotFoundError`.
- Produces: `SignalRepository` and `InMemorySignalRepository` from Contracts
  Section 7.

**Owned tests:** T007, T008, T009, T010, T011.

- [ ] **Step 1: Write failing T007–T011 tests**

Include these strong immutability assertions:

```python
def test_t009_get_snapshot_cannot_mutate_repository_storage(repository, sine_case):
    repository.put(sine_case.record)
    first = repository.get(sine_case.record.meta.signal_id)
    assert first.samples.flags.writeable is False
    with pytest.raises(ValueError):
        first.samples[0, 0] = 123.0

    try:
        first.samples.flags.writeable = True
        first.samples[0, 0] = 123.0
    except ValueError:
        pass

    second = repository.get(sine_case.record.meta.signal_id)
    assert second.samples[0, 0] == sine_case.record.samples[0, 0]
```

T007 asserts array/meta equality. T008 mutates the source record after `put`.
T010 covers `get`, `remove`, and `exists`. T011 inserts A, B, then replacement A,
checks list order `[A, B]`, checks replacement content, removes A, and checks B
remains.

- [ ] **Step 2: Run T007–T011 and verify RED**

```powershell
python -m pytest tests/signal/test_repository.py -v
```

Expected: import failure for `signal.repository`.

- [ ] **Step 3: Implement repository copy ownership**

Store a private owned array and immutable metadata. On every `get`, create an
independent array snapshot and then mark it read-only:

```python
snapshot = np.array(stored.samples, dtype=np.float32, order="C", copy=True)
snapshot.flags.writeable = False
return SignalRecord(meta=stored.meta.model_copy(deep=True), samples=snapshot)
```

Use an insertion-ordered dict. Replacing an existing key must not move it.
`list_meta()` returns deep model copies and no arrays.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/signal/test_repository.py -v
```

- [ ] **Step 5: Run accumulated suite and review**

```powershell
python -m pytest tests/signal -q
```

Expected: T001–T011 pass.

---

### Task 3: Time Segment and Channel Selection

**Files:**

- Create: `src/signal_diag/signal/segment.py`
- Create: `tests/signal/test_segment.py`
- Modify: `src/signal_diag/signal/__init__.py`

**Interfaces:**

- Consumes: `SignalRecord`, `TimeRange`, `ChannelMode`.
- Produces: `extract_segment -> np.ndarray` from Contracts Section 8.

**Owned tests:** T012, T013, T014, T015, T016.

- [ ] **Step 1: Write failing T012–T016 tests**

Use a 3-second 48 kHz reference for T012 and verify exact slice equality. Build
a manual stereo record with 200 Hz left and 400 Hz right for T016:

```python
left = np.sin(2 * np.pi * 200 * t)
right = np.sin(2 * np.pi * 400 * t)
record = build_signal_record(
    np.column_stack([left, right]),
    sample_rate_hz=48_000,
    source_type="generated",
)
np.testing.assert_allclose(
    extract_segment(record, channel="mixdown"),
    ((left + right) / 2).astype(np.float32),
    atol=1e-6,
)
```

Assert every returned array is 1-D, writable, and independent from record
storage. Cover end clamping and all invalid ranges.

- [ ] **Step 2: Run T012–T016 and verify RED**

```powershell
python -m pytest tests/signal/test_segment.py -v
```

- [ ] **Step 3: Implement exact index/channel semantics**

Compute:

```python
start = round(start_s * sample_rate_hz)
end = num_samples if end_s is None else min(
    round(end_s * sample_rate_hz),
    num_samples,
)
```

Validate `0 <= start < end <= num_samples`. Select mono/stereo according to the
contract, calculate mixdown with
`np.mean(selected_channels, axis=1, dtype=np.float64)`, then
return `np.array(selected, dtype=np.float32, order="C", copy=True)`.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/signal/test_segment.py -v
```

- [ ] **Step 5: Run accumulated suite**

```powershell
python -m pytest tests/signal -q
```

Expected: T001–T016 pass.

---

### Task 4: Clean, Clipped, and Noise Synthetic Generators

**Files:**

- Create: `src/signal_diag/signal/synthetic.py`
- Create: `tests/conftest.py`
- Create: `tests/signal/test_synthetic.py`
- Modify: `src/signal_diag/signal/__init__.py`

**Interfaces:**

- Consumes: `build_signal_record`, `FaultLabel`.
- Produces: `SyntheticGroundTruth`, `SyntheticCase`, `generate_sine`,
  `generate_clipped_sine`, and `generate_white_noise`.

**Owned tests:** T017, T018, T019, T020.

- [ ] **Step 1: Write failing T017–T020 tests and canonical fixtures**

Create fixtures matching Test Plan Section 5. Assert required parameter keys,
empty/expected fault labels, amplitude, length, equal-seed identity, different
seed inequality, noise mean within `0.01`, and RMS within 3%.

Representative assertion:

```python
def test_t018_clipped_sine_has_exact_limit(clipped_case):
    peak = np.max(np.abs(clipped_case.record.samples))
    assert peak == pytest.approx(0.5, abs=1e-4)
    assert clipped_case.ground_truth.generator == "clipped_sine"
    assert clipped_case.ground_truth.fault_labels == ("clipping",)
```

- [ ] **Step 2: Run T017–T020 and verify RED**

```powershell
python -m pytest tests/signal/test_synthetic.py -v
```

- [ ] **Step 3: Implement deterministic basic generators**

Use:

```python
n = round(duration_s * sample_rate_hz)
t = np.arange(n, dtype=np.float64) / sample_rate_hz
clean = amplitude * np.sin(2 * np.pi * frequency_hz * t + phase_rad) + dc_offset
clipped = np.clip(clean, -clip_level, clip_level)
noise = np.random.default_rng(seed).normal(0.0, rms, size=n)
```

Pass arrays through `build_signal_record`. Do not normalize noise to exact RMS or
normalize any generated signal.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/signal/test_synthetic.py -k "t017 or t018 or t019 or t020" -v
```

- [ ] **Step 5: Run accumulated suite**

```powershell
python -m pytest tests/signal -q
```

---

### Task 5: Harmonic and Combined Synthetic Generators

**Files:**

- Modify: `src/signal_diag/signal/synthetic.py`
- Modify: `tests/signal/test_synthetic.py`
- Modify: `tests/conftest.py`

**Interfaces:**

- Produces: `generate_harmonic_sine` and `generate_combined_distortion` exactly
  as Contracts Section 9.
- Consumed by: harmonic DSP and S1 acceptance.

**Owned tests:** T021, T022, T023, T024.

- [ ] **Step 1: Write failing T021–T024 tests**

For T021, use FFT projection or correlation against exact sine bases to verify
ratios without depending on the future spectrum module:

```python
def measured_amplitude(x: np.ndarray, frequency: float, fs: int) -> float:
    t = np.arange(len(x), dtype=np.float64) / fs
    basis = np.sin(2 * np.pi * frequency * t)
    return float(2 * np.dot(x.astype(np.float64), basis) / len(x))

assert measured_amplitude(x, 400.0, 48_000) / measured_amplitude(
    x, 200.0, 48_000
) == pytest.approx(0.10, abs=1e-4)
```

T022 checks string-keyed ground-truth ratios. T023 checks both labels and exact
clip peak. T024 parametrizes invalid order 1, negative ratio, empty/all-zero
ratios, invalid clip level, and invalid common parameters.

- [ ] **Step 2: Run T021–T024 and verify RED**

```powershell
python -m pytest tests/signal/test_synthetic.py -k "t021 or t022 or t023 or t024" -v
```

- [ ] **Step 3: Implement harmonic construction once and reuse it**

Use a private validated helper:

```python
x = fundamental_amplitude * np.sin(2 * np.pi * fundamental_hz * t)
for order, ratio in sorted(harmonic_ratios.items()):
    x = x + fundamental_amplitude * ratio * np.sin(
        2 * np.pi * order * fundamental_hz * t
    )
```

`generate_harmonic_sine` stores this directly. Combined generation clips the
same waveform afterward. Serialize ratio keys with `str(order)`.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/signal/test_synthetic.py -v
```

- [ ] **Step 5: Checkpoint A verification**

```powershell
python -m pytest tests/signal -q
python -m pytest -q
```

Expected: T001–T024 pass.

---

### Task 6: DSP Result Models and Preprocessing

**Files:**

- Create: `src/signal_diag/dsp/__init__.py`
- Create: `src/signal_diag/dsp/models.py`
- Create: `src/signal_diag/dsp/preprocess.py`
- Create: `tests/dsp/__init__.py`
- Create: `tests/dsp/test_preprocess.py`

**Interfaces:**

- Consumes: one-dimensional NumPy arrays only.
- Produces: all result dataclasses in Contracts Section 10 and `remove_dc`,
  `rms`, `peak_abs`.

**Owned tests:** T025, T026, T027.

- [ ] **Step 1: Write failing T025–T027 tests**

```python
def test_t025_remove_dc_does_not_mutate():
    x = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    before = x.copy()
    y = remove_dc(x)
    assert np.mean(y) == pytest.approx(0.0, abs=1e-7)
    np.testing.assert_array_equal(x, before)


def test_t026_rms_and_peak_known_values():
    x = np.array([3.0, 4.0], dtype=np.float32)
    assert rms(x) == pytest.approx(np.sqrt(12.5))
    assert peak_abs(x) == pytest.approx(4.0)
```

Parametrize T027 over empty, NaN, Inf, and `(N,1)` arrays for all helpers.

- [ ] **Step 2: Run T025–T027 and verify RED**

```powershell
python -m pytest tests/dsp/test_preprocess.py -v
```

- [ ] **Step 3: Implement one shared private validator and frozen result models**

```python
def _validated_1d(samples: np.ndarray) -> np.ndarray:
    values = np.asarray(samples)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("samples must be finite, non-empty, and one-dimensional")
    return values.astype(np.float64, copy=False)
```

Each helper derives a value or new array from this view and never writes to it.
Define every dataclass field exactly as Contracts Section 10.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/dsp/test_preprocess.py -v
```

- [ ] **Step 5: Run accumulated suite**

```powershell
python -m pytest tests/signal tests/dsp -q
```

---

### Task 7: Clipping DSP

**Files:**

- Create: `src/signal_diag/dsp/clipping.py`
- Create: `tests/dsp/test_clipping.py`
- Modify: `src/signal_diag/dsp/__init__.py`

**Interfaces:**

- Consumes: finite 1-D arrays.
- Produces: `analyze_clipping -> ClippingAnalysis`.

**Owned tests:** T028, T029, T030, T031, T032.

- [ ] **Step 1: Write failing T028–T032 tests**

Use canonical clean, full-scale, and sub-full-scale cases. For T031 construct an
explicit plateau that meets both masks and assert the union count does not exceed
the plateau sample count. For T032 preserve a byte-for-byte input copy.

```python
def test_t030_sub_full_scale_flat_top_is_detected(clipped_case):
    x = extract_segment(clipped_case.record)
    result = analyze_clipping(x)
    assert result.detected
    assert result.flat_top_detected
    assert not result.full_scale_detected
```

- [ ] **Step 2: Run T028–T032 and verify RED**

```powershell
python -m pytest tests/dsp/test_clipping.py -v
```

- [ ] **Step 3: Implement run detection and union accounting**

Build:

```python
full_scale_mask = np.abs(x) >= full_scale_threshold
flat_diff = np.abs(np.diff(x)) <= flat_top_tolerance
```

Convert flat differences into sample runs, require `min_flat_top_samples`, and
require the plateau to be a local high-amplitude extremum rather than any
constant low-level region. Merge qualifying full-scale and flat-top sample masks
with logical OR. Derive event runs from the union mask and calculate every result
field from that union.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/dsp/test_clipping.py -v
```

- [ ] **Step 5: Run accumulated suite**

```powershell
python -m pytest tests/signal tests/dsp -q
```

---

### Task 8: Spectrum DSP

**Files:**

- Create: `src/signal_diag/dsp/spectrum.py`
- Create: `tests/dsp/test_spectrum.py`
- Modify: `src/signal_diag/dsp/__init__.py`

**Interfaces:**

- Produces: `analyze_fft -> FFTAnalysis`.
- Consumed by: harmonics and Tool service.

**Owned tests:** T033, T034, T035, T036, T037, T038.

- [ ] **Step 1: Write failing T033–T038 tests**

Use `n_fft=131_072` for T036 and assert `len(frequencies) == n_fft // 2 + 1`.
For silence assert `dominant_frequency_hz is None`, centroid is `None`, peaks are
empty, and magnitude contains no NaN. Include truncating `n_fft=N-1` in T038.

- [ ] **Step 2: Run T033–T038 and verify RED**

```powershell
python -m pytest tests/dsp/test_spectrum.py -v
```

- [ ] **Step 3: Implement windowed real FFT and deterministic peaks**

Core calculation:

```python
working = remove_dc(x) if remove_dc_component else x.astype(np.float64, copy=True)
window_values = np.hanning(len(working)) if window == "hann" else np.ones(len(working))
spectrum = np.fft.rfft(working * window_values, n=resolved_n_fft)
linear = np.abs(spectrum)
frequencies = np.fft.rfftfreq(resolved_n_fft, d=1.0 / sample_rate_hz)
```

When maximum linear magnitude is zero, emit `-np.inf` bins and no dominant/peak/
centroid. Otherwise calculate `20*log10(linear/max_linear)` using a positive
floor only to avoid log warnings. Exclude bin 0 from dominant selection. Find
local maxima by neighbor comparison and sort by magnitude descending, then
frequency ascending for deterministic ties.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/dsp/test_spectrum.py -v
```

- [ ] **Step 5: Run accumulated suite**

```powershell
python -m pytest tests/signal tests/dsp -q
```

---

### Task 9: Autocorrelation Fundamental DSP

**Files:**

- Create: `src/signal_diag/dsp/pitch.py`
- Create: `tests/dsp/test_pitch.py`
- Modify: `src/signal_diag/dsp/__init__.py`

**Interfaces:**

- Produces: `estimate_f0_autocorrelation -> F0Estimate`.
- Consumed by: harmonic analysis and Tool service.

**Owned tests:** T039, T040, T041, T042, T043.

- [ ] **Step 1: Write failing T039–T043 tests**

Use the canonical sine, silence, and noise fixtures. Assert no NaN and preserve
input. Parametrize invalid rates and frequency bounds.

```python
def test_t039_sine_fundamental_is_200_hz(sine_case):
    estimate = estimate_f0_autocorrelation(
        extract_segment(sine_case.record),
        48_000,
        fmin_hz=100.0,
        fmax_hz=400.0,
    )
    assert estimate.voiced
    assert estimate.f0_hz == pytest.approx(200.0, abs=1.0)
    assert estimate.method == "autocorrelation"
```

- [ ] **Step 2: Run T039–T043 and verify RED**

```powershell
python -m pytest tests/dsp/test_pitch.py -v
```

- [ ] **Step 3: Implement the specified autocorrelation baseline**

Use DC removal, negligible-RMS rejection, Hann window, zero-padded FFT-based
autocorrelation, zero-lag normalization, and lag bounds:

```python
min_lag = max(1, int(np.floor(sample_rate_hz / fmax_hz)))
max_lag = min(len(x) - 1, int(np.ceil(sample_rate_hz / fmin_hz)))
n_fft = 1 << (2 * len(windowed) - 1).bit_length()
power = np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2
acf = np.fft.irfft(power, n=n_fft)[: len(windowed)]
acf = acf / acf[0]
```

Choose the strongest restricted candidate, optionally parabolically refine its
lag, use candidate normalized correlation as confidence, and return unvoiced
below threshold.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/dsp/test_pitch.py -v
```

- [ ] **Step 5: Run accumulated suite**

```powershell
python -m pytest tests/signal tests/dsp -q
```

---

### Task 10: Harmonic Association and THD DSP

**Files:**

- Create: `src/signal_diag/dsp/harmonics.py`
- Create: `tests/dsp/test_harmonics.py`
- Modify: `src/signal_diag/dsp/__init__.py`

**Interfaces:**

- Consumes: `estimate_f0_autocorrelation` and deterministic spectral helpers.
- Produces: `analyze_harmonic_distortion -> HarmonicAnalysis`.

**Owned tests:** T044, T045, T046, T047, T048, T049, T050, T051, T052.

- [ ] **Step 1: Write failing T044–T052 tests**

Use the canonical `11.180339%` fixture for T044. Assert component order/frequency,
supplied and estimated fundamentals, silence/noise invalidity, Nyquist truncation,
mutation safety, and absence of PASS/FAIL fields.

```python
def test_t044_known_harmonic_ratios_produce_expected_thd(harmonic_case):
    result = analyze_harmonic_distortion(
        extract_segment(harmonic_case.record),
        48_000,
        fundamental_hz=200.0,
        max_harmonic_order=5,
    )
    assert result.valid
    assert result.thd_percent == pytest.approx(11.180339, abs=0.5)
```

- [ ] **Step 2: Run T044–T052 and verify RED**

```powershell
python -m pytest tests/dsp/test_harmonics.py -v
```

- [ ] **Step 3: Implement deterministic harmonic measurement**

Resolve or estimate the fundamental. Compute a Hann-windowed real spectrum and
convert peak magnitudes to amplitudes with the same window correction for every
order so ratios remain comparable. For each target `k*f0` at or below Nyquist,
search the nearest bin and its immediate neighbors, choose the largest magnitude,
and calculate:

```python
relative_amplitude = harmonic_amplitude / fundamental_amplitude
relative_magnitude_db = 20.0 * np.log10(max(relative_amplitude, tiny))
thd_percent = 100.0 * np.sqrt(sum(a * a for a in harmonic_amplitudes)) / fundamental_amplitude
```

Return `valid=False` with all numeric fundamental/THD fields `None` when energy,
fundamental confidence, frequency support, or fundamental amplitude is
insufficient. Do not return diagnostic labels or thresholds.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/dsp/test_harmonics.py -v
```

- [ ] **Step 5: Checkpoint B verification**

```powershell
python -m pytest tests/dsp -q
python -m pytest tests/signal tests/dsp -q
python -m pytest -q
```

Expected: T001–T052 pass.

---

### Task 11: Tool Contracts, Result Invariants, Evidence, and Registry

**Files:**

- Create: `src/signal_diag/tools/__init__.py`
- Create: `src/signal_diag/tools/contracts.py`
- Create: `src/signal_diag/tools/evidence.py`
- Create: `src/signal_diag/tools/results.py`
- Create: `src/signal_diag/tools/registry.py`
- Create: `tests/tools/__init__.py`
- Create: `tests/tools/test_contracts.py`
- Create: `tests/tools/test_evidence.py`

**Interfaces:**

- Consumes: Signal selection types and compact scalar DSP meanings.
- Produces: every model in Contracts Sections 16–17 and
  `get_tool_descriptors()`.

**Owned tests:** T062, T063.

- [ ] **Step 1: Write failing T062–T063 contract tests**

Parametrize invalid ToolResult combinations:

```python
VALID_OUTPUT = ClippingOutput(
    detected=False,
    clipping_ratio=0.0,
    clipped_samples=0,
    clipping_events=0,
    longest_event_samples=0,
    peak_abs=0.5,
    full_scale_detected=False,
    flat_top_detected=False,
)

VALID_EVIDENCE = Evidence(
    evidence_id="ev_detected",
    source_tool="detect_clipping",
    call_id="call_example",
    metric="clipping_detected",
    value=False,
    channel="mixdown",
)

@pytest.mark.parametrize(
    "status,result,evidence_items,warnings,error_message",
    [
        ("success", None, (), (), None),
        ("invalid", None, (), (), None),
        ("error", VALID_OUTPUT, (), (), "failed"),
        ("error", None, (VALID_EVIDENCE,), (), "failed"),
        ("success", VALID_OUTPUT, (), (), "unexpected"),
    ],
)
def test_t062_tool_result_rejects_invalid_status_combinations(
    status,
    result,
    evidence_items,
    warnings,
    error_message,
):
    with pytest.raises(ValidationError):
        ToolResult[ClippingOutput](
            call_id="call_example",
            tool_name="detect_clipping",
            status=status,
            result=result,
            evidence=evidence_items,
            warnings=warnings,
            error_message=error_message,
        )
```

Also prove the three legal combinations:

```python
@pytest.mark.parametrize(
    "status,result,evidence_items,warnings,error_message",
    [
        ("success", VALID_OUTPUT, (VALID_EVIDENCE,), (), None),
        ("invalid", VALID_OUTPUT, (), ("metric not applicable",), None),
        ("error", None, (), (), "signal not found"),
    ],
)
def test_t062_tool_result_accepts_valid_status_combinations(
    status,
    result,
    evidence_items,
    warnings,
    error_message,
):
    parsed = ToolResult[ClippingOutput](
        call_id="call_example",
        tool_name="detect_clipping",
        status=status,
        result=result,
        evidence=evidence_items,
        warnings=warnings,
        error_message=error_message,
    )
    assert parsed.status == status
```

T063 compares the exact Tool-name set and calls
`json.dumps(descriptor.input_schema)`.

- [ ] **Step 2: Run T062–T063 and verify RED**

```powershell
python -m pytest tests/tools/test_contracts.py tests/tools/test_evidence.py -v
```

- [ ] **Step 3: Implement exact Pydantic contracts and validators**

Copy field names and constraints from Contracts Sections 16–19. Add
`model_validator(mode="after")` to `FundamentalInput`,
`HarmonicDistortionInput`, and `ToolResult`. Generate registry schemas with
`InputModel.model_json_schema()`; descriptors are an unordered tuple and contain
no runtime callable.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/tools/test_contracts.py tests/tools/test_evidence.py -v
```

- [ ] **Step 5: Run accumulated suite**

```powershell
python -m pytest tests/signal tests/dsp tests/tools -q
```

---

### Task 12: Signal Tool Service and Deterministic Evidence

**Files:**

- Create: `src/signal_diag/tools/service.py`
- Create: `tests/tools/test_service.py`
- Modify: `src/signal_diag/tools/__init__.py`

**Interfaces:**

- Consumes: repository, `extract_segment`, all four DSP functions, Tool models.
- Produces: `SignalToolService` methods from Contracts Section 18.

**Owned tests:** T053, T054, T055, T056, T057, T058, T059, T060, T061.

- [ ] **Step 1: Write failing T053–T061 integration tests**

Use real repository, segments, and DSP. Representative checks:

```python
def test_t057_harmonic_tool_returns_thd_evidence(repository, harmonic_case):
    repository.put(harmonic_case.record)
    service = SignalToolService(repository)
    result = service.analyze_harmonic_distortion(
        harmonic_case.record.meta.signal_id,
        HarmonicDistortionInput(fundamental_hz=200.0),
    )
    assert result.status == "success"
    assert result.result is not None
    assert result.result.thd_percent == pytest.approx(11.180339, abs=0.5)
    assert any(item.metric == "thd_percent" for item in result.evidence)
```

For T054 serialize the result and recursively reject ndarray values and keys that
contain full frequency/magnitude arrays. T059 calls all four methods with a
missing ID. T060 uses a two-region or stereo signal. T061 validates Evidence IDs,
call linkage, metrics, selection provenance, and uniqueness.

- [ ] **Step 2: Run T053–T061 and verify RED**

```powershell
python -m pytest tests/tools/test_service.py -v
```

- [ ] **Step 3: Implement one shared service execution boundary**

Use private helpers only to remove repetition:

```python
def _load_selected(
    repository: SignalRepository,
    signal_id: str,
    selection: SignalSelection,
) -> tuple[SignalRecord, np.ndarray]:
    record = repository.get(signal_id)
    samples = extract_segment(
        record,
        time_range=selection.time_range,
        channel=selection.channel,
    )
    return record, samples
```

Each public method creates one `call_` ID, catches expected operational
exceptions into `error`, maps scientific invalidity to `invalid`, and creates
only scalar/categorical Evidence with `ev_` IDs. Clipping emits evidence for
detection flags, ratio, events, and peak. Spectrum emits dominant frequency,
resolution, and centroid when present. Fundamental emits voiced/confidence and
F0 only when voiced. Harmonic emits validity/fundamental/THD and compact component
metrics only when valid.

- [ ] **Step 4: Run focused GREEN tests**

```powershell
python -m pytest tests/tools/test_service.py -v
```

- [ ] **Step 5: Checkpoint C verification**

```powershell
python -m pytest tests/tools -q
python -m pytest tests/signal tests/dsp tests/tools -q
python -m pytest -q
```

Expected: T001–T063 pass.

---

### Task 13: Phase 1 Contract, Boundary, and Full Verification

**Files:**

- Create: `tests/test_architecture_boundaries.py`
- Modify only if verification exposes a defect: the smallest affected Phase 1
  source/test file.

**Interfaces:**

- Consumes: all Phase 1 modules.
- Produces: verified Phase 1 delivery with no new public API.

- [ ] **Step 1: Add architecture-boundary tests without inventing new behavior**

Inspect source imports with `ast` and assert:

```python
FORBIDDEN = {
    "signal": {"signal_diag.dsp", "signal_diag.tools", "signal_diag.agent"},
    "dsp": {"signal_diag.tools", "signal_diag.agent"},
    "tools": {"signal_diag.agent"},
}
```

Walk `src/signal_diag/<layer>/*.py`, parse `Import` and `ImportFrom`, and fail when
an imported module begins with a forbidden prefix. Also assert no `agent`,
`rules`, `knowledge`, `evaluation`, or `app` package exists yet.

- [ ] **Step 2: Run the boundary test and verify its value**

```powershell
python -m pytest tests/test_architecture_boundaries.py -v
```

Expected on correct Phase 1 structure: PASS. To prove the test is capable of
failing, temporarily add a forbidden import to an in-memory source string tested
by the boundary helper; do not modify production source for this proof.

- [ ] **Step 3: Run complete required verification**

```powershell
python -m pytest -q
```

Expected: T001–T063 and architecture-boundary tests pass with zero failures,
skips, or xfails.

- [ ] **Step 4: Run configured quality checks**

```powershell
ruff check .
mypy src
```

If mypy requires NumPy/Pydantic plugin configuration, add only documented
project-local configuration; do not weaken type checks with broad ignores.

- [ ] **Step 5: Perform contract coverage review**

Review `docs/CONTRACTS_V0_2.md` Sections 3–19 and
`docs/TEST_PLAN_V0_2.md` T001–T063 line by line. Record in the development report:

```text
Files changed:
Tests added by ID:
Focused RED commands and expected failures:
Focused GREEN commands and results:
Full suite command and result:
Ruff result:
Mypy result:
Warnings:
Unsupported cases:
Contract concerns:
```

Do not describe Phase 1 as complete if any required check is failing. Do not
commit or push without explicit user authorization.

---

## Plan Self-Review Checklist

- [ ] Tasks 1–12 map every required ID T001–T063 exactly once as the owning task.
- [ ] Task 13 verifies dependency boundaries and the complete accumulated suite.
- [ ] Later tasks consume only interfaces defined by earlier tasks.
- [ ] Public names match `CONTRACTS_V0_2.md`.
- [ ] No task creates Phase 2 Agent or Phase 3–5 modules.
- [ ] No production code is scheduled before its failing behavioral test.
- [ ] No random test omits an explicit seed.
- [ ] No Tool output or Agent-facing contract contains waveform/full FFT arrays.
- [ ] No automatic commit or push step is present.

## Execution Handoff

After user review, execute this plan either:

1. **Inline execution:** use `superpowers:executing-plans` in this session with
   checkpoint reviews; or
2. **Subagent-driven execution:** only after the user explicitly authorizes
   subagents, use `superpowers:subagent-driven-development` with a fresh
   implementer and review gate per task.

The current workspace is not a Git repository, so worktree and branch-finishing
flows do not apply unless repository initialization is separately authorized.
