"""Layer-1 full-scale method characterization (evaluation-only; D043 / T-CX371)."""

from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.manifest import (
    build_manifest,
    manifest_sha256,
)
from signal_diag.evaluation.full_scale_characterization.models import ScaleLimitExceeded
from signal_diag.evaluation.full_scale_characterization.pcm import encode_pcm_wav
from signal_diag.evaluation.full_scale_characterization.synthesis import (
    clipped,
    harmonic_sine,
    sine,
)

__all__ = [
    "ROUND_1",
    "ScaleLimitExceeded",
    "build_manifest",
    "clipped",
    "encode_pcm_wav",
    "harmonic_sine",
    "manifest_sha256",
    "sine",
]
