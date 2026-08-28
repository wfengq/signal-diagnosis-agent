"""Deterministic DSP result models and preprocessing."""

from .clipping import analyze_clipping
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
    "ClippingAnalysis",
    "F0Estimate",
    "FFTAnalysis",
    "HarmonicAnalysis",
    "HarmonicComponent",
    "SpectrumPeak",
    "analyze_clipping",
    "analyze_fft",
    "estimate_f0_autocorrelation",
    "peak_abs",
    "remove_dc",
    "rms",
]
