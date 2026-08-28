# Task 1 Report — Project Skeleton, Signal Models, and Factory

## Status

Implemented Task 1 only. No DSP, tools, agent, or Phase 2+ modules were
created.

## Implementation

- Added setuptools/pytest project metadata and a `src` package layout.
- Added frozen Pydantic `TimeRange` and `SignalMeta` models, including interval
  and duration semantic validators.
- Added `SignalRecord` validation for canonical `float32`, `(N, C)`, C-contiguous,
  finite arrays that agree with metadata.
- Added all frozen signal-domain exceptions and signal package exports.
- Added `build_signal_record`, which rejects invalid/non-finite/unsigned input,
  converts signed PCM at full scale, preserves floating amplitudes without peak
  normalization, owns contiguous data, derives metadata, and generates `sig_`
  IDs.
- Added T001–T006 acceptance tests.

## TDD evidence

RED command:

```powershell
python -m pytest tests/signal/test_factory.py -v
```

Actual output before implementation: collection failed with
`ModuleNotFoundError: No module named 'signal_diag'`; `0 items / 1 error`.
This was the expected missing-package failure.

GREEN command:

```powershell
python -m pytest tests/signal/test_factory.py -v
```

Actual output: `12 passed in 0.40s` (the parametrized T004 has seven cases).

## Verification

```powershell
python -m pytest -q
```

Actual output: `12 passed in 0.31s`.

```powershell
python -m ruff check .
```

Actual output: `All checks passed!`.

```powershell
python -m mypy src
```

Actual output: `No module named mypy`; the configured optional development
dependency is absent in this offline local environment, so mypy was not run.

## Modified files

- `pyproject.toml`
- `src/signal_diag/__init__.py`
- `src/signal_diag/signal/__init__.py`
- `src/signal_diag/signal/exceptions.py`
- `src/signal_diag/signal/factory.py`
- `src/signal_diag/signal/models.py`
- `tests/__init__.py`
- `tests/signal/__init__.py`
- `tests/signal/test_factory.py`

## Self-review

- Verified all public names required by Contracts Sections 4–6 are present.
- Verified signed integer conversion uses `2 ** (bits - 1)` and has no peak
  normalization.
- Verified the factory derives all shape metadata and validates direct-record
  canonical invariants.
- Reviewed staged diff with `git diff --cached --check`; it reported no whitespace
  errors. Generated `__pycache__` files were removed before staging.
- Scope contains only Task 1 package, configuration, and tests.

## Warnings, unsupported cases, and contract concerns

- The local interpreter is Python 3.8.17 although V0.2 requires Python 3.11+.
  `SignalRecord` therefore uses `slots=True` on Python 3.10+ (including the
  supported target) and a compatibility fallback only to enable local tests.
- Type annotations use `Optional[...]` rather than `| None` for the same local
  interpreter compatibility; public names and runtime semantics are unchanged.
- Unsigned PCM remains explicitly unsupported as required by the frozen contract.
- No implementation or contract concern beyond the local Python-version mismatch.
