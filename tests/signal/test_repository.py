"""Acceptance tests for the immutable in-memory signal repository."""

import numpy as np
import pytest

from signal_diag.signal import (
    InMemorySignalRepository,
    SignalMeta,
    SignalNotFoundError,
    SignalRecord,
    build_signal_record,
)


@pytest.fixture
def repository() -> InMemorySignalRepository:
    return InMemorySignalRepository()


@pytest.fixture
def sine_record() -> SignalRecord:
    return build_signal_record(
        np.array([0.0, 0.25, -0.5, 0.125], dtype=np.float32),
        sample_rate_hz=48_000,
        source_type="generated",
        signal_id="sig_sine",
    )


def test_t007_put_get_preserves_samples_and_immutable_metadata(
    repository: InMemorySignalRepository, sine_record: SignalRecord
) -> None:
    repository.put(sine_record)

    retrieved = repository.get("sig_sine")

    np.testing.assert_array_equal(retrieved.samples, sine_record.samples)
    assert retrieved.meta == sine_record.meta
    assert retrieved.meta.model_config["frozen"] is True


def test_t008_put_owns_source_samples_and_metadata(
    repository: InMemorySignalRepository, sine_record: SignalRecord
) -> None:
    repository.put(sine_record)
    sine_record.samples[0, 0] = 0.75

    first_snapshot = repository.get("sig_sine")
    second_snapshot = repository.get("sig_sine")

    assert first_snapshot.samples[0, 0] == 0.0
    assert first_snapshot.meta == sine_record.meta
    assert second_snapshot.meta == sine_record.meta
    assert first_snapshot.meta is not sine_record.meta
    assert second_snapshot.meta is not sine_record.meta
    assert first_snapshot.meta is not second_snapshot.meta


def test_t009_get_snapshot_cannot_mutate_repository_storage(
    repository: InMemorySignalRepository, sine_record: SignalRecord
) -> None:
    repository.put(sine_record)
    first = repository.get("sig_sine")
    assert first.samples.flags.writeable is False
    with pytest.raises(ValueError):
        first.samples[0, 0] = 123.0

    try:
        first.samples.flags.writeable = True
        first.samples[0, 0] = 123.0
    except ValueError:
        pass

    second = repository.get("sig_sine")
    assert second.samples[0, 0] == sine_record.samples[0, 0]
    assert second.samples.flags.c_contiguous
    assert second.samples.dtype == np.float32
    assert not np.shares_memory(first.samples, second.samples)


def test_t010_missing_id_has_exact_repository_semantics(
    repository: InMemorySignalRepository,
) -> None:
    assert repository.exists("sig_missing") is False
    with pytest.raises(SignalNotFoundError):
        repository.get("sig_missing")
    with pytest.raises(SignalNotFoundError):
        repository.remove("sig_missing")


def test_t011_replacement_preserves_order_and_list_meta_has_no_arrays(
    repository: InMemorySignalRepository,
) -> None:
    first_a = build_signal_record(
        np.array([0.0, 0.25], dtype=np.float32),
        sample_rate_hz=48_000,
        source_type="generated",
        signal_id="sig_a",
    )
    record_b = build_signal_record(
        np.array([0.0, -0.25], dtype=np.float32),
        sample_rate_hz=48_000,
        source_type="generated",
        signal_id="sig_b",
    )
    replacement_a = build_signal_record(
        np.array([0.5, -0.5], dtype=np.float32),
        sample_rate_hz=48_000,
        source_type="generated",
        signal_id="sig_a",
    )
    repository.put(first_a)
    repository.put(record_b)
    repository.put(replacement_a)

    metadata = repository.list_meta()
    metadata_again = repository.list_meta()

    assert [item.signal_id for item in metadata] == ["sig_a", "sig_b"]
    assert all(isinstance(item, SignalMeta) for item in metadata)
    assert all(not hasattr(item, "samples") for item in metadata)
    assert metadata[0] == metadata_again[0]
    assert metadata[1] == metadata_again[1]
    assert metadata[0] is not metadata_again[0]
    assert metadata[1] is not metadata_again[1]
    assert metadata[0] is not repository.get("sig_a").meta
    assert metadata[1] is not repository.get("sig_b").meta
    np.testing.assert_array_equal(repository.get("sig_a").samples, replacement_a.samples)
    repository.remove("sig_a")
    assert repository.exists("sig_a") is False
    assert repository.get("sig_b").meta.signal_id == "sig_b"
