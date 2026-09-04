"""Deterministic DSP result models and preprocessing."""

from .clipping import analyze_clipping
from .contextual import (
    CONTEXTUAL_DSP_VERSION,
    ContextualAnalysisConfig,
    ContextualDistortionAnalysis,
    HarmonicGrowthComponent,
    analyze_contextual_distortion,
)
from .harmonics import analyze_harmonic_distortion
from .models import (
    ClippingAnalysis,
    F0Estimate,
    FFTAnalysis,
    HarmonicAnalysis,
    HarmonicComponent,
    SpectrumPeak,
)
from .pitch import estimate_f0_autocorrelation
from .preprocess import peak_abs, remove_dc, rms
from .spectrum import analyze_fft

__all__ = [
    "CONTEXTUAL_DSP_VERSION",
    "ClippingAnalysis",
    "ContextualAnalysisConfig",
    "ContextualDistortionAnalysis",
    "F0Estimate",
    "FFTAnalysis",
    "HarmonicAnalysis",
    "HarmonicComponent",
    "HarmonicGrowthComponent",
    "SpectrumPeak",
    "analyze_clipping",
    "analyze_contextual_distortion",
    "analyze_fft",
    "analyze_harmonic_distortion",
    "estimate_f0_autocorrelation",
    "peak_abs",
    "remove_dc",
    "rms",
]
