"""Canonical deterministic fixtures from TEST_PLAN_V0_2.md Section 5."""

import pytest

from signal_diag.signal import (
    InMemorySignalRepository,
    SyntheticCase,
    generate_clipped_sine,
    generate_sine,
    generate_white_noise,
)


@pytest.fixture
def repository() -> InMemorySignalRepository:
    return InMemorySignalRepository()


@pytest.fixture
def sine_case() -> SyntheticCase:
    return generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=0.5,
    )


@pytest.fixture
def clipped_case() -> SyntheticCase:
    return generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=0.9,
        clip_level=0.5,
    )


@pytest.fixture
def full_scale_clipped_case() -> SyntheticCase:
    return generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=1.2,
        clip_level=1.0,
    )


@pytest.fixture
def noise_case() -> SyntheticCase:
    return generate_white_noise(
        sample_rate_hz=48_000,
        duration_s=2.0,
        rms=0.1,
        seed=1234,
    )
