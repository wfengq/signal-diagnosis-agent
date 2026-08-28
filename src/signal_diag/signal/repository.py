"""Immutable repository implementations for canonical signal records."""

from abc import ABC, abstractmethod

import numpy as np

from .exceptions import SignalNotFoundError
from .models import SignalMeta, SignalRecord


class SignalRepository(ABC):
    """Storage boundary for canonical signal records."""

    @abstractmethod
    def put(self, record: SignalRecord) -> None:
        """Store a signal record under its signal ID."""

    @abstractmethod
    def get(self, signal_id: str) -> SignalRecord:
        """Return an immutable snapshot of the requested record."""

    @abstractmethod
    def exists(self, signal_id: str) -> bool:
        """Return whether a record exists for ``signal_id``."""

    @abstractmethod
    def remove(self, signal_id: str) -> None:
        """Remove a stored record."""

    @abstractmethod
    def list_meta(self) -> list[SignalMeta]:
        """Return stored metadata in insertion order."""


class InMemorySignalRepository(SignalRepository):
    """An insertion-ordered repository which owns its waveform storage."""

    def __init__(self) -> None:
        self._records: dict[str, SignalRecord] = {}

    def put(self, record: SignalRecord) -> None:
        """Copy a record into private immutable storage."""
        stored_samples = np.array(record.samples, dtype=np.float32, order="C", copy=True)
        stored_samples.flags.writeable = False
        stored_record = SignalRecord(
            meta=record.meta.model_copy(deep=True),
            samples=stored_samples,
        )
        self._records[stored_record.meta.signal_id] = stored_record

    def get(self, signal_id: str) -> SignalRecord:
        """Return an independent read-only snapshot of a stored record."""
        try:
            stored = self._records[signal_id]
        except KeyError as error:
            raise SignalNotFoundError(f"signal not found: {signal_id}") from error

        snapshot = np.array(stored.samples, dtype=np.float32, order="C", copy=True)
        snapshot.flags.writeable = False
        return SignalRecord(meta=stored.meta.model_copy(deep=True), samples=snapshot)

    def exists(self, signal_id: str) -> bool:
        """Return whether a record exists for ``signal_id``."""
        return signal_id in self._records

    def remove(self, signal_id: str) -> None:
        """Remove a record or raise the domain-specific missing-ID error."""
        if signal_id not in self._records:
            raise SignalNotFoundError(f"signal not found: {signal_id}")
        del self._records[signal_id]

    def list_meta(self) -> list[SignalMeta]:
        """Return detached metadata copies without exposing waveform arrays."""
        return [record.meta.model_copy(deep=True) for record in self._records.values()]
