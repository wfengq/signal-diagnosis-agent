"""T-CX349, T-CX351: full-scale facts beside measurement bundles."""

from __future__ import annotations

import pytest

from signal_diag.signal import InMemorySignalRepository, TimeRange
from signal_diag.tools.regression_full_scale import (
    full_scale_facts_digest,
    measure_full_scale_facts,
    verify_full_scale_facts,
)
from signal_diag.tools.regression_measurement import (
    MeasurementSelection,
    measure_output,
    verify_measurement_bundle_digest,
)
from tests.rules.full_scale_fixtures import (
    measured,
    redigest,
    sine,
    wav16,
    wav16_stereo,
)


def test_t_cx349_facts_follow_bundle_range_and_channel() -> None:
    bundle, repo, bits = measured(
        wav16(sine(amplitude=0.9905)),
        time_range=TimeRange(start_s=0.5, end_s=1.5),
    )
    facts = measure_full_scale_facts(repository=repo, bundle=bundle, pcm_bit_depth=bits)
    ident = bundle.identity
    assert facts is not None
    assert facts.analyzed_samples == ident.resolved_end_sample - ident.resolved_start_sample == 48_000
    assert facts.state == "yes" and facts.counted_samples == 1000 and facts.pcm_bit_depth == 16
    assert (facts.side, facts.run_id, facts.wav_sha256, facts.bundle_digest) == (
        ident.side,
        ident.run_id,
        ident.wav_sha256,
        bundle.digest,
    )
    assert facts.full_scale_threshold == 0.99 and facts.min_consecutive_samples == 2
    assert facts.facts_version == "v0.3-full-scale-facts-1"
    assert facts.digest == full_scale_facts_digest(facts)


def test_t_cx349_facts_use_the_selected_channel() -> None:
    stereo = wav16_stereo(sine(amplitude=0.5), sine(amplitude=0.9905))
    left, repo_l, bits = measured(stereo, channel="left")
    right, repo_r, _ = measured(stereo, channel="right")
    assert measure_full_scale_facts(repository=repo_l, bundle=left, pcm_bit_depth=bits).state == "no"
    assert measure_full_scale_facts(repository=repo_r, bundle=right, pcm_bit_depth=bits).state == "yes"


def test_t_cx351_bundle_digest_unchanged_by_facts() -> None:
    bundle, repo, bits = measured(wav16(sine(amplitude=0.5)))
    before = bundle.digest
    measure_full_scale_facts(repository=repo, bundle=bundle, pcm_bit_depth=bits)
    verify_measurement_bundle_digest(bundle)
    assert bundle.digest == before and "full_scale_facts" not in bundle.model_dump()


def test_facts_absent_when_clipping_tool_failed() -> None:
    bundle, _repo, bits = measured(wav16(sine(amplitude=0.5)))
    empty = InMemorySignalRepository()
    snap = bundle.identity.tool_parameter_snapshot
    failed = measure_output(
        repository=empty,
        identity=bundle.identity,
        selection=MeasurementSelection(clipping=snap.clipping, harmonic=snap.harmonic),
    )
    assert failed.clipping.status != "success"
    assert measure_full_scale_facts(repository=empty, bundle=failed, pcm_bit_depth=bits) is None


def test_verify_rejects_tampered_or_inconsistent_facts() -> None:
    bundle, repo, bits = measured(wav16(sine(amplitude=0.9905)))
    facts = measure_full_scale_facts(repository=repo, bundle=bundle, pcm_bit_depth=bits)
    assert facts is not None
    verify_full_scale_facts(facts, bundle)
    for update in (
        {"state": "no"},
        {"peak_abs": 0.5},
        {"analyzed_samples": 1},
        {"bundle_digest": "0" * 64},
        {"full_scale_threshold": 0.9},
        {"counted_samples": 0},
    ):
        with pytest.raises(ValueError):
            verify_full_scale_facts(redigest(facts.model_copy(update=update)), bundle)
    with pytest.raises(ValueError):
        verify_full_scale_facts(
            facts.model_copy(update={"counted_samples": facts.counted_samples + 1}),
            bundle,
        )
