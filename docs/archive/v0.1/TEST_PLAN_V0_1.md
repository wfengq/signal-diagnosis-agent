# Signal Diagnosis Agent — Phase 1 Test Plan V0.1

**Document:** `TEST_PLAN_V0_1.md`  
**Version:** `0.1`  
**Scope:** deterministic Signal → DSP → Tool foundation

---

# 1. Purpose

This document defines the executable acceptance criteria for Phase 1.

Phase 1 is not complete because:

```text
the code imports successfully
```

or because:

```text
a demo prints plausible-looking values
```

It is complete only when deterministic tests verify the approved contracts.

The core execution chain under test is:

```text
Synthetic Signal
        ↓
SignalRecord
        ↓
Repository
        ↓
Segment Extraction
        ↓
DSP
        ↓
Tool Service
```

LLM and Agent behavior are explicitly outside Phase 1 testing.

---

# 2. Test Philosophy

Tests should verify:

- mathematical behavior;
- public contracts;
- shape/dtype invariants;
- non-mutation guarantees;
- reliable invalid-result behavior;
- deterministic synthetic data;
- Tool/DSP separation.

Tests should not merely duplicate internal implementation details.

Prefer:

```text
input → expected externally observable result
```

over:

```text
assert private variable equals implementation-specific intermediate value
```

---

# 3. Required Tooling

Use:

```text
pytest
numpy
scipy
```

Optional:

```text
pytest-cov
ruff
mypy
```

The project should not require an LLM API key to execute Phase 1 tests.

---

# 4. Determinism Rules

All random data must use explicit seeds.

Required pattern:

```python
rng = np.random.default_rng(seed)
```

Tests must not depend on:

- wall-clock time;
- random global state;
- network access;
- external APIs;
- machine-specific audio hardware.

A test should produce the same logical result on repeated execution.

---

# 5. Shared Numerical Tolerances

Recommended shared constants:

```python
FREQ_ABS_TOL_HZ = 1.0

FLOAT_ABS_TOL = 1e-6

RMS_REL_TOL = 0.03
```

Tests may use tighter tolerances where mathematically justified.

Tests must not weaken tolerances simply to hide an implementation defect.

If an algorithm legitimately requires a larger tolerance, document the numerical reason.

---

# 6. Test Layout

Required structure:

```text
tests/
├── conftest.py
│
├── signal/
│   ├── test_factory.py
│   ├── test_repository.py
│   ├── test_segment.py
│   └── test_synthetic.py
│
├── dsp/
│   ├── test_clipping.py
│   ├── test_spectrum.py
│   └── test_pitch.py
│
└── tools/
    └── test_signal_tools.py
```

---

# 7. Shared Fixtures

Recommended `tests/conftest.py` fixtures:

```python
@pytest.fixture
def sine_200hz():
    return generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=0.5,
    )
```

```python
@pytest.fixture
def clipped_200hz():
    return generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=0.9,
        clip_level=0.5,
    )
```

```python
@pytest.fixture
def white_noise():
    return generate_white_noise(
        sample_rate_hz=48_000,
        duration_s=2.0,
        rms=0.1,
        seed=1234,
    )
```

```python
@pytest.fixture
def repository():
    return InMemorySignalRepository()
```

Fixtures may be implemented differently while preserving deterministic behavior.

---

# 8. Required Phase 1 Test Matrix

| ID | Area | Test | Required result |
|---|---|---|---|
| T01 | Factory | Mono canonical shape | `(N,) → (N,1)` and `float32` |
| T02 | Factory | No peak normalization | float peak remains unchanged |
| T03 | Factory | int16 full-scale conversion | expected FS mapping |
| T04 | Repository | Put/Get integrity | samples and metadata preserved |
| T05 | Repository | Immutability | stored signal independent and non-writeable |
| T06 | Repository | Missing ID | raises `SignalNotFoundError` |
| T07 | Segment | Time-range extraction | correct sample interval |
| T08 | Synthetic | 200 Hz sine | metadata and ground truth correct |
| T09 | Synthetic | Clipped sine | signal limited by clip level |
| T10 | Clipping | Clean sine | no false clipping |
| T11 | Clipping | Near full-scale clipping | saturation detected |
| T12 | Clipping | Sub-full-scale flat-top clipping | clipping still detected |
| T13 | FFT | 200 Hz sine | dominant frequency ≈ 200 Hz |
| T14 | FFT | DC-offset sine | DC removal preserves ≈ 200 Hz dominant |
| T15 | F0 | 200 Hz sine | F0 ≈ 200 Hz and voiced |
| T16 | F0 | Silence | no numeric F0 and unvoiced |
| T17 | F0 | Seeded white noise | unreliable/unvoiced |
| T18 | F0 | Invalid frequency bounds | explicit validation failure |

---

# 9. T01 — Canonical Mono Shape

File:

```text
tests/signal/test_factory.py
```

Input:

```python
samples = np.array(
    [0.0, 0.1, -0.2],
    dtype=np.float64,
)
```

Action:

```python
record = build_signal_record(
    samples,
    sample_rate_hz=48_000,
    source_type="generated",
)
```

Required assertions:

```python
assert record.samples.shape == (3, 1)
assert record.samples.dtype == np.float32

assert record.meta.channels == 1
assert record.meta.num_samples == 3
```

Purpose:

- freezes `(N,C)` repository representation;
- prevents accidental `(N,)` mono storage.

---

# 10. T02 — No Peak Normalization

Input:

```python
samples = np.array(
    [0.0, 0.25, -0.5],
    dtype=np.float64,
)
```

Action:

```python
record = build_signal_record(...)
```

Required:

```python
assert np.max(
    np.abs(record.samples)
) == pytest.approx(
    0.5,
    abs=FLOAT_ABS_TOL,
)
```

Explicitly forbidden behavior:

```text
peak becomes 1.0
```

Purpose:

preserves amplitude information needed for:

- clipping;
- RMS;
- future amplitude diagnostics.

---

# 11. T03 — int16 Full-Scale Conversion

Input:

```python
samples = np.array(
    [-32768, 0, 32767],
    dtype=np.int16,
)
```

Expected approximate output:

```text
-1.0
0.0
32767 / 32768
```

Assertions:

```python
x = record.samples[:, 0]

assert x[0] == pytest.approx(
    -1.0,
    abs=1e-6,
)

assert x[1] == pytest.approx(
    0.0,
    abs=1e-6,
)

assert x[2] == pytest.approx(
    32767 / 32768,
    abs=1e-6,
)
```

Also:

```python
assert record.meta.original_dtype == "int16"
```

---

# 12. T04 — Repository Put/Get Integrity

File:

```text
tests/signal/test_repository.py
```

Arrange:

```python
case = generate_sine(
    frequency_hz=200,
)
```

Action:

```python
repo.put(case.record)

stored = repo.get(
    case.record.meta.signal_id
)
```

Required:

```python
assert stored.meta == case.record.meta

np.testing.assert_array_equal(
    stored.samples,
    case.record.samples,
)
```

Also:

```python
assert repo.exists(
    case.record.meta.signal_id
)
```

---

# 13. T05 — Repository Immutability

This test has two parts.

## Part A — Repository owns a copy

Create a writable source array.

Insert the resulting record.

Mutate the caller-controlled source where possible.

Stored data must not change.

## Part B — Stored array is readonly

Required:

```python
stored = repo.get(signal_id)

assert stored.samples.flags.writeable is False
```

Attempted direct mutation should fail:

```python
with pytest.raises(ValueError):
    stored.samples[0, 0] = 123.0
```

Purpose:

prevents one DSP analysis from modifying another analysis's source data.

---

# 14. T06 — Missing Signal ID

Required:

```python
with pytest.raises(
    SignalNotFoundError
):
    repo.get(
        "does_not_exist"
    )
```

Also:

```python
assert repo.exists(
    "does_not_exist"
) is False
```

---

# 15. T07 — Time-Range Extraction

File:

```text
tests/signal/test_segment.py
```

Generate:

```python
case = generate_sine(
    frequency_hz=200,
    sample_rate_hz=48_000,
    duration_s=3.0,
)
```

Select:

```text
1.0 s → 2.0 s
```

Expected number of samples:

```text
48,000
```

Required:

```python
segment = extract_segment(
    case.record,
    time_range=TimeRange(
        start_s=1.0,
        end_s=2.0,
    ),
)

assert segment.ndim == 1
assert len(segment) == 48_000
```

Additional recommended assertion:

the segment should numerically match the corresponding reference slice.

Invalid empty range should raise:

```text
InvalidTimeRangeError
```

This may be implemented as an additional test.

---

# 16. T08 — Synthetic 200 Hz Sine

File:

```text
tests/signal/test_synthetic.py
```

Generate:

```python
case = generate_sine(
    frequency_hz=200.0,
    sample_rate_hz=48_000,
    duration_s=2.0,
    amplitude=0.5,
)
```

Required metadata:

```python
assert (
    case.record.meta.sample_rate_hz
    == 48_000
)

assert (
    case.record.meta.num_samples
    == 96_000
)

assert case.record.meta.channels == 1
```

Ground truth:

```python
assert (
    case.ground_truth.generator
    == "sine"
)

assert (
    case.ground_truth.fault_type
    is None
)

assert (
    case.ground_truth.parameters[
        "frequency_hz"
    ]
    == pytest.approx(200.0)
)
```

Approximate amplitude:

```python
assert np.max(
    np.abs(case.record.samples)
) == pytest.approx(
    0.5,
    abs=1e-3,
)
```

---

# 17. T09 — Synthetic Clipped Sine

Generate:

```python
case = generate_clipped_sine(
    frequency_hz=200,
    amplitude=0.9,
    clip_level=0.5,
)
```

Required:

```python
peak = np.max(
    np.abs(case.record.samples)
)

assert peak <= 0.5 + 1e-6

assert peak == pytest.approx(
    0.5,
    abs=1e-4,
)
```

Ground truth:

```python
assert (
    case.ground_truth.fault_type
    == "clipping"
)

assert (
    case.ground_truth.parameters[
        "clip_level"
    ]
    == pytest.approx(0.5)
)
```

---

# 18. Recommended Synthetic Noise Reproducibility Test

Although not numbered in the original core matrix, this test is strongly recommended.

Generate twice:

```python
a = generate_white_noise(
    seed=1234,
)

b = generate_white_noise(
    seed=1234,
)
```

Required:

```python
np.testing.assert_array_equal(
    a.record.samples,
    b.record.samples,
)
```

Different seed:

```python
c = generate_white_noise(
    seed=1235,
)
```

Required:

```python
assert not np.array_equal(
    a.record.samples,
    c.record.samples,
)
```

Approximate RMS:

```python
measured = np.sqrt(
    np.mean(
        a.record.samples[:, 0] ** 2
    )
)

assert measured == pytest.approx(
    0.1,
    rel=0.03,
)
```

---

# 19. T10 — Clean Sine Must Not Trigger Clipping

File:

```text
tests/dsp/test_clipping.py
```

Generate:

```python
case = generate_sine(
    frequency_hz=200,
    amplitude=0.5,
)
```

Extract mono waveform.

Run:

```python
result = analyze_clipping(
    samples
)
```

Required:

```python
assert result.detected is False

assert (
    result.full_scale_detected
    is False
)

assert (
    result.flat_top_detected
    is False
)
```

Clipping ratio should be zero or extremely close to zero.

Purpose:

avoids a detector that treats normal smooth peaks as clipping.

---

# 20. T11 — Near Full-Scale Clipping

Construct a signal that contains repeated samples at or above the configured full-scale threshold.

This can use a clipped synthetic signal with a high clip level, for example:

```python
case = generate_clipped_sine(
    frequency_hz=200,
    amplitude=1.2,
    clip_level=1.0,
)
```

or another deterministic equivalent.

Required:

```python
assert result.detected is True

assert (
    result.full_scale_detected
    is True
)

assert result.clipped_samples > 0
assert result.clipping_events > 0
```

The exact event count is not frozen because implementation details may merge adjacent plateaus differently.

---

# 21. T12 — Sub-Full-Scale Flat-Top Clipping

This is a critical acceptance test.

Generate:

```python
case = generate_clipped_sine(
    frequency_hz=200,
    amplitude=0.9,
    clip_level=0.5,
)
```

Because:

```text
peak = 0.5
```

the signal does not approach:

```text
0.99 FS
```

Therefore a full-scale-only detector would fail.

Required:

```python
assert result.detected is True

assert (
    result.flat_top_detected
    is True
)
```

Recommended:

```python
assert (
    result.full_scale_detected
    is False
)
```

This test prevents regression to a trivial threshold-only clipping detector.

---

# 22. T13 — FFT Dominant Frequency on 200 Hz Sine

File:

```text
tests/dsp/test_spectrum.py
```

Generate:

```python
case = generate_sine(
    frequency_hz=200.0,
    sample_rate_hz=48_000,
    duration_s=2.0,
)
```

Run:

```python
result = analyze_fft(
    samples,
    48_000,
)
```

Required:

```python
assert (
    result.dominant_frequency_hz
    == pytest.approx(
        200.0,
        abs=FREQ_ABS_TOL_HZ,
    )
)
```

Required frequency resolution:

for `n_fft = N = 96000`:

```text
48000 / 96000 = 0.5 Hz
```

So:

```python
assert (
    result.frequency_resolution_hz
    == pytest.approx(
        0.5,
        abs=1e-9,
    )
)
```

Required:

```python
assert len(result.peaks) > 0
```

The strongest reported peak should be close to 200 Hz.

---

# 23. T14 — FFT With DC Offset

Generate:

```python
case = generate_sine(
    frequency_hz=200.0,
    amplitude=0.3,
    dc_offset=0.4,
)
```

Run:

```python
result = analyze_fft(
    samples,
    sample_rate_hz,
    remove_dc_component=True,
)
```

Required:

```python
assert (
    result.dominant_frequency_hz
    == pytest.approx(
        200.0,
        abs=FREQ_ABS_TOL_HZ,
    )
)
```

Purpose:

confirms that a large DC component does not incorrectly become the dominant diagnostic frequency when DC removal is enabled.

---

# 24. FFT Relative Magnitude Sanity Test

Recommended additional test:

```python
assert np.max(
    result.magnitude_db
) == pytest.approx(
    0.0,
    abs=1e-6,
)
```

Purpose:

freezes the Phase 1 relative magnitude convention.

This is not an absolute dB calibration test.

---

# 25. T15 — F0 on 200 Hz Sine

File:

```text
tests/dsp/test_pitch.py
```

Generate:

```python
case = generate_sine(
    frequency_hz=200,
    sample_rate_hz=48_000,
    duration_s=2.0,
)
```

Run:

```python
estimate = (
    estimate_f0_autocorrelation(
        samples,
        48_000,
        fmin_hz=100,
        fmax_hz=400,
    )
)
```

Required:

```python
assert estimate.voiced is True

assert estimate.f0_hz is not None

assert estimate.f0_hz == pytest.approx(
    200.0,
    abs=FREQ_ABS_TOL_HZ,
)

assert estimate.confidence >= 0.3

assert (
    estimate.method
    == "autocorrelation"
)
```

The confidence threshold may be exposed as a parameter.

---

# 26. T16 — F0 on Silence

Input:

```python
samples = np.zeros(
    48_000,
    dtype=np.float32,
)
```

Required:

```python
estimate = (
    estimate_f0_autocorrelation(
        samples,
        48_000,
    )
)

assert estimate.voiced is False
assert estimate.f0_hz is None
```

Required:

```python
assert estimate.confidence >= 0.0
```

The algorithm must not divide by zero, emit NaN or fabricate a pitch.

---

# 27. T17 — F0 on Seeded White Noise

Generate:

```python
case = generate_white_noise(
    sample_rate_hz=48_000,
    duration_s=2.0,
    rms=0.1,
    seed=1234,
)
```

Run:

```python
estimate = (
    estimate_f0_autocorrelation(
        samples,
        48_000,
        fmin_hz=50,
        fmax_hz=1000,
    )
)
```

Required expected behavior:

```python
assert estimate.voiced is False
assert estimate.f0_hz is None
```

Important:

If the initial autocorrelation implementation occasionally produces a false voiced result for this fixed deterministic noise case, fix the algorithm or confidence logic.

Do not weaken this test by simply increasing the accepted F0 error.

The scientific requirement is:

> Random broadband noise must not be confidently reported as a stable F0 for this deterministic acceptance fixture.

---

# 28. T18 — Invalid F0 Bounds

Examples:

```text
fmin_hz = 400
fmax_hz = 100
```

or:

```text
fmin_hz == fmax_hz
```

Required:

explicit validation failure.

Acceptable mechanisms:

- `ValueError`;
- a project-specific invalid-argument exception;
- Pydantic validation when validating Tool input.

The DSP API itself must not silently swap the bounds.

Example:

```python
with pytest.raises(ValueError):
    estimate_f0_autocorrelation(
        samples,
        48_000,
        fmin_hz=400,
        fmax_hz=100,
    )
```

---

# 29. Tool Service Tests

File:

```text
tests/tools/test_signal_tools.py
```

The Tool Service tests verify adaptation behavior, not the entire DSP mathematics again.

---

# 30. Tool Clipping Integration Test

Arrange:

```python
repo = InMemorySignalRepository()

case = generate_clipped_sine(
    frequency_hz=200,
    amplitude=0.9,
    clip_level=0.5,
)

repo.put(case.record)

service = SignalToolService(repo)
```

Call:

```python
result = service.detect_clipping(
    case.record.meta.signal_id,
    ClippingInput(),
)
```

Required:

```python
assert result.status == "success"

assert result.result is not None

assert result.result.detected is True

assert (
    result.result.flat_top_detected
    is True
)
```

The Tool output must not contain raw waveform arrays.

---

# 31. Tool FFT Integration Test

Call:

```python
result = service.fft_analysis(
    case.record.meta.signal_id,
    FFTInput(),
)
```

Required:

```python
assert result.status == "success"

assert (
    result.result.dominant_frequency_hz
    == pytest.approx(
        200,
        abs=1.0,
    )
)
```

Required Tool-level contract:

```python
assert not hasattr(
    result.result,
    "frequencies_hz",
)

assert not hasattr(
    result.result,
    "magnitude_db",
)
```

because large FFT arrays belong to the DSP layer, not Agent Tool output.

---

# 32. Tool F0 Success Test

For a deterministic sine:

```python
result = service.estimate_f0(
    signal_id,
    F0Input(
        fmin_hz=100,
        fmax_hz=400,
    ),
)
```

Required:

```python
assert result.status == "success"

assert result.result.voiced is True

assert result.result.f0_hz == pytest.approx(
    200,
    abs=1.0,
)
```

---

# 33. Tool F0 Invalid Test

For deterministic seeded white noise:

```python
result = service.estimate_f0(
    signal_id,
    F0Input(),
)
```

Required:

```python
assert result.status == "invalid"

assert result.result is not None

assert result.result.voiced is False

assert result.result.f0_hz is None

assert len(result.warnings) >= 1
```

Purpose:

tests the distinction between:

```text
invalid scientific result
```

and:

```text
software execution error
```

---

# 34. Segment + Tool Integration

Recommended:

Create a signal containing different behavior in two time regions.

Example:

```text
0–1 s:
200 Hz sine

1–2 s:
400 Hz sine
```

Call FFT with:

```text
0–1 s
```

and then:

```text
1–2 s
```

Expected dominant frequencies:

```text
≈200 Hz
≈400 Hz
```

This test validates that Tool-level `TimeRange` is actually respected.

It may be added after the minimum T01–T18 set.

---

# 35. Channel Test

Recommended stereo test.

Construct:

```text
left:
200 Hz sine

right:
400 Hz sine
```

Expected:

```text
channel="left"
→ ≈200 Hz

channel="right"
→ ≈400 Hz
```

This is recommended but not mandatory for the initial 18-test acceptance gate.

---

# 36. Mutation Safety Test for DSP

Recommended test:

```python
before = samples.copy()

analyze_fft(samples, fs)

np.testing.assert_array_equal(
    samples,
    before,
)
```

Repeat for:

```text
analyze_clipping
estimate_f0_autocorrelation
```

DSP public functions must not alter the input waveform.

---

# 37. Invalid Input Tests

Recommended coverage:

## Empty signal

```text
[]
```

Expected:

explicit failure.

## NaN

Expected:

explicit failure or rejection at factory boundary.

## Inf

Expected:

explicit failure or rejection at factory boundary.

## Invalid sample rate

```text
0
-48000
```

Expected:

explicit failure.

These are important but may be added after the primary T01–T18 suite.

---

# 38. Test Execution Workflow

For each implementation unit:

```text
1. write/confirm the focused test;
2. run it;
3. confirm the expected failure if implementing new behavior;
4. implement the smallest correct solution;
5. run the focused test;
6. refactor if needed;
7. run the complete Phase 1 suite.
```

Example:

```bash
pytest tests/dsp/test_clipping.py -q
```

Then:

```bash
pytest -q
```

---

# 39. Completion Rules

A coding Agent must not report Phase 1 as complete unless:

```text
all required T01–T18 behaviors pass
```

and Tool integration tests for the implemented Tools pass.

Not allowed:

```text
xfail on a required test
```

Not allowed:

```text
skip because implementation is difficult
```

Not allowed:

```text
loosening assertions solely to produce green tests
```

Not allowed:

```text
replacing a failed scientific requirement with a mocked value
```

---

# 40. Failure Handling Policy

When a test fails:

1. determine whether the implementation is wrong;
2. determine whether the contract and test disagree;
3. if the test correctly represents the frozen contract, fix implementation;
4. if a genuine contract defect is discovered, stop and report the issue;
5. do not silently redefine accepted behavior.

---

# 41. Phase 1 Acceptance Command

Minimum final verification:

```bash
pytest -q
```

If linting is configured:

```bash
ruff check .
```

If static typing is configured:

```bash
mypy src
```

The exact tooling may evolve, but `pytest` is mandatory.

---

# 42. Required Final Development Report

After a Phase 1 coding task, the coding Agent should report:

```text
Files changed:
...

Tests added:
...

Focused tests run:
...

Full suite:
...

Result:
PASS / FAIL

Warnings:
...

Contract concerns:
...
```

It must not state:

```text
Everything is complete.
```

if required tests are failing.

---

# 43. Phase 1 Acceptance Summary

Minimum required behavioral gate:

```text
Signal representation
    ✔ canonical float32
    ✔ shape (N,C)
    ✔ no peak normalization

Repository
    ✔ copy ownership
    ✔ immutable storage
    ✔ missing-ID behavior

Segmentation
    ✔ deterministic time extraction

Synthetic
    ✔ sine
    ✔ clipped sine
    ✔ seeded white noise

Clipping
    ✔ clean sine not flagged
    ✔ full-scale clipping detected
    ✔ sub-full-scale flat-top detected

FFT
    ✔ 200 Hz recovery
    ✔ DC robustness

F0
    ✔ 200 Hz recovery
    ✔ silence rejected
    ✔ deterministic noise rejected
    ✔ invalid range rejected

Tools
    ✔ compact typed output
    ✔ no waveform leakage
    ✔ correct success/invalid semantics
```

When these conditions are satisfied, the repository has a reliable deterministic base suitable for the next DSP expansion phase.