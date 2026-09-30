"""Public Demo synthetic catalog isolated from evaluation manifests."""

from __future__ import annotations

from collections.abc import Callable

from signal_diag.app.errors import UnknownPresetError
from signal_diag.app.models import AppErrorDetail, DemoPresetDescriptor, DemoPresetId
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.signal.models import SignalRecord
from signal_diag.signal.synthetic import (
    SyntheticCase,
    generate_clipped_sine,
    generate_combined_distortion,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)

_PRESET_BUILDERS: dict[DemoPresetId, Callable[[], SyntheticCase]] = {
    "clean_periodic": lambda: generate_sine(
        frequency_hz=220.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=0.35,
    ),
    "clipping": lambda: generate_clipped_sine(
        frequency_hz=220.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=1.2,
        clip_level=0.65,
    ),
    "harmonic_distortion": lambda: generate_harmonic_sine(
        fundamental_hz=220.0,
        harmonic_ratios={2: 0.12, 3: 0.04},
        sample_rate_hz=48_000,
        duration_s=1.0,
        fundamental_amplitude=0.5,
    ),
    "combined_distortion": lambda: generate_combined_distortion(
        fundamental_hz=220.0,
        harmonic_ratios={2: 0.12, 3: 0.04},
        clip_level=0.55,
        sample_rate_hz=48_000,
        duration_s=1.0,
        fundamental_amplitude=0.9,
    ),
    "noise_inconclusive": lambda: generate_white_noise(
        sample_rate_hz=48_000,
        duration_s=1.0,
        rms=0.1,
        seed=5001,
    ),
}

_PRESET_DESCRIPTORS: tuple[DemoPresetDescriptor, ...] = (
    DemoPresetDescriptor(
        preset_id="clean_periodic",
        label="Clean periodic",
        description="Clean 220 Hz sine without injected faults.",
        sample_rate_hz=48_000,
        duration_s=1.0,
        channels=1,
    ),
    DemoPresetDescriptor(
        preset_id="clipping",
        label="Clipping",
        description="Sine with symmetric hard clipping.",
        sample_rate_hz=48_000,
        duration_s=1.0,
        channels=1,
    ),
    DemoPresetDescriptor(
        preset_id="harmonic_distortion",
        label="Harmonic distortion",
        description="Sine with added second and third harmonics.",
        sample_rate_hz=48_000,
        duration_s=1.0,
        channels=1,
    ),
    DemoPresetDescriptor(
        preset_id="combined_distortion",
        label="Combined distortion",
        description="Harmonic distortion followed by hard clipping.",
        sample_rate_hz=48_000,
        duration_s=1.0,
        channels=1,
    ),
    DemoPresetDescriptor(
        preset_id="noise_inconclusive",
        label="Inconclusive noise",
        description="Seeded white-noise waveform for an inconclusive Demo.",
        sample_rate_hz=48_000,
        duration_s=1.0,
        channels=1,
    ),
)


def list_demo_presets() -> tuple[DemoPresetDescriptor, ...]:
    return _PRESET_DESCRIPTORS


def build_demo_preset(preset_id: DemoPresetId) -> SignalRecord:
    builder = _PRESET_BUILDERS.get(preset_id)
    if builder is None:
        raise UnknownPresetError(
            AppErrorDetail(
                code="unknown_preset",
                message=f"Unknown demo preset: {preset_id}",
            )
        )
    return builder().record


def render_demo_preset_wav(preset_id: DemoPresetId) -> bytes:
    """Materialize a Demo catalog ID as deterministic mono 32-bit PCM WAV bytes."""
    record = build_demo_preset(preset_id)
    return encode_pcm32_wav(
        record.samples,
        sample_rate_hz=record.meta.sample_rate_hz,
    )
