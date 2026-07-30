"""HCK Memory Adapter — translates generic MemoryAdapter calls into HCK API.
Isolates Runtime from HCK internals (CRE, Episodic, Semantic, etc).
Runtime only sees MemoryAdapterBase. CRE remains HCK responsibility.
"""
from typing import List, Optional
from adapters.base import BaseAdapter
from adapters.lifecycle import AdapterState
from adapters.memory.base import MemoryAdapterBase
from adapters.memory.models import MemoryRecord, MemoryQuery, MemoryResult, MemoryHealthReport
from adapters.memory.exceptions import (
    MemoryConnectionError, MemoryUnavailableError,
    MemoryQueryError, MemoryWriteError
)


class HCKMemoryAdapter(MemoryAdapterBase):
    @property
    def name(self) -> str: return "hck"

    def __init__(self, hck_client=None):
        super().__init__()
        self._client = hck_client

    def initialize(self):
        if not self._client:
            raise MemoryConnectionError("HCK client not provided")
        self._set_state(AdapterState.INITIALIZED)

    def connect(self):    self._set_state(AdapterState.CONNECTED)
    def disconnect(self): self._set_state(AdapterState.DISCONNECTED)
    def health_check(self): return {"name": self.name, "status": self._state.value}

    def _require(self):
        if not self._client:
            raise MemoryConnectionError("HCK client not connected")

    # All CRUD delegate to HCK — placeholder until Phase 4.5 wiring
    def store(self, record: MemoryRecord) -> MemoryRecord:
        self._require()
        # TODO: self._client.store(record) — HCK API call
        record.record_id = record.record_id or "hck_auto"
        return record

    def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        self._require()
        return None  # TODO: self._client.retrieve(record_id)

    def search(self, query: MemoryQuery) -> MemoryResult:
        self._require()
        return MemoryResult()  # TODO: self._client.search(query)

    def update(self, record: MemoryRecord) -> MemoryRecord:
        self._require()
        return record  # TODO: self._client.update(record)

    def delete(self, record_id: str) -> bool:
        self._require()
        return True  # TODO: self._client.delete(record_id)

    def compact(self) -> None:
        """Delegate to HCK internal compaction / CRE."""
        pass

    def cleanup(self, before_age_seconds: int = 86400) -> int:
        """Delegate to HCK internal cleanup / CRE."""
        return 0

    def health_report(self) -> MemoryHealthReport:
        return MemoryHealthReport(
            provider="hck",
            connected=self._state.value == "CONNECTED",
            available=self._state.value in ("CONNECTED","INITIALIZED"),
        )
