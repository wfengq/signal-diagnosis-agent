"""T-CX378 / A.16: tables are sharded by side, family and analysis-range length."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.manifest import (
    estimate_shard_sizes_bytes,
)
from signal_diag.evaluation.full_scale_characterization.store import (
    SHARD_MAX_BYTES,
    CharacterizationStore,
    decode_range_key,
    encode_range_key,
    shard_path,
)


def test_t_cx378_range_key_round_trips_every_round_1_length() -> None:
    lengths = set(ROUND_1.calibration_range_lengths_s) | set(ROUND_1.validation_range_lengths_s)
    keys = {encode_range_key(length) for length in lengths}
    assert len(keys) == len(lengths)
    for length in lengths:
        key = encode_range_key(length)
        assert "." not in key
        assert decode_range_key(key) == length
    assert encode_range_key(2.0) == "L2000000us"
    assert encode_range_key(0.005) == "L5000us"
    with pytest.raises(ValueError):
        encode_range_key(1e-7)
    with pytest.raises(ValueError):
        decode_range_key("L0.1us")


def test_t_cx378_store_accepts_only_the_a16_layout(tmp_path: Path) -> None:
    store = CharacterizationStore(tmp_path)
    good = shard_path("calibration", "measurements", "M3", 0.1)
    assert good == "calibration_measurements/M3/L100000us.jsonl.gz"
    store.write_jsonl_gz(good, [{"a": 1}])
    store.write_jsonl_gz(shard_path("calibration", "pairs", "M3", 0.1), [{"a": 1}])
    for bad in (
        "calibration_measurements/M3.jsonl.gz",
        "calibration_pairs/M3.jsonl.gz",
        "calibration_measurements/M3/L0.1.jsonl.gz",
        "calibration_measurements/M3/L100000us/x.jsonl.gz",
        "calibration_measurements/../M3/L100000us.jsonl.gz",
        "calibration_measurements/M3/../L100000us.jsonl.gz",
        "other_measurements/M3/L100000us.jsonl.gz",
    ):
        with pytest.raises(ValueError):
            store.write_jsonl_gz(bad, [{"a": 1}])
    assert store.list_dir("calibration_measurements") == [good]
    store.verify_sha256sums()


def test_t_cx378_directory_digest_covers_nested_shards(tmp_path: Path) -> None:
    store = CharacterizationStore(tmp_path)
    store.write_jsonl_gz(shard_path("calibration", "measurements", "M3", 0.1), [{"a": 1}])
    before = store.directory_sha256("calibration_measurements")
    store.write_jsonl_gz(shard_path("calibration", "measurements", "M3", 0.005), [{"a": 1}])
    assert store.directory_sha256("calibration_measurements") != before


def test_t_cx378_round_1_shards_fit_the_size_limit(round_1_manifest) -> None:
    shards = estimate_shard_sizes_bytes(round_1_manifest.planned_pair_counts)
    lengths = {
        "calibration": ROUND_1.calibration_range_lengths_s,
        "validation": ROUND_1.validation_range_lengths_s,
    }
    for side, families in round_1_manifest.planned_pair_counts.by_side_family.items():
        for family in families:
            for length in lengths[side]:
                assert f"{side}/{family}/{encode_range_key(length)}" in shards
    assert max(shards.values()) < SHARD_MAX_BYTES
    assert sum(shards.values()) == 2 * 170 * sum(round_1_manifest.planned_pair_counts.by_side.values())
