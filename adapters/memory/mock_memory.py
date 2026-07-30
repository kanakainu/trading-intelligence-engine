"""Mock memory provider — in-memory store for testing. No external dependency."""
import time, uuid
from datetime import datetime, timezone
from typing import List, Optional
from adapters.base import BaseAdapter
from adapters.lifecycle import AdapterState
from adapters.memory.base import MemoryAdapterBase
from adapters.memory.models import MemoryRecord, MemoryQuery, MemoryResult, MemoryHealthReport


class MockMemoryAdapter(MemoryAdapterBase):
    @property
    def name(self) -> str: return "mock"

    def __init__(self):
        super().__init__()
        self._store: dict = {}

    def initialize(self): self._set_state(AdapterState.INITIALIZED)
    def connect(self):    self._set_state(AdapterState.CONNECTED)
    def disconnect(self): self._set_state(AdapterState.DISCONNECTED)
    def health_check(self): return {"name": self.name, "status": self._state.value}

    def store(self, record: MemoryRecord) -> MemoryRecord:
        rid = record.record_id or str(uuid.uuid4())[:12]
        record.record_id = rid
        record.created_at = datetime.now(timezone.utc)
        record.version = 1
        self._store[rid] = record
        return record

    def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        return self._store.get(record_id)

    def search(self, query: MemoryQuery) -> MemoryResult:
        results = list(self._store.values())
        if query.category:
            results = [r for r in results if r.category == query.category]
        if query.tags:
            results = [r for r in results if any(t in r.tags for t in query.tags)]
        if query.keywords:
            kw = [k.lower() for k in query.keywords]
            results = [r for r in results
                       if any(k in str(r.value).lower() or k in str(r.key).lower() for k in kw)]
        if query.since:
            results = [r for r in results if r.created_at >= query.since]
        total = len(results)
        results = results[query.offset:query.offset + query.limit]
        return MemoryResult(records=results, total=total)

    def update(self, record: MemoryRecord) -> MemoryRecord:
        if record.record_id not in self._store:
            raise KeyError(f"Record not found: {record.record_id}")
        record.updated_at = datetime.now(timezone.utc)
        record.version += 1
        self._store[record.record_id] = record
        return record

    def delete(self, record_id: str) -> bool:
        return self._store.pop(record_id, None) is not None

    def compact(self) -> None: pass

    def cleanup(self, before_age_seconds: int = 86400) -> int:
        cutoff = time.time() - before_age_seconds
        to_del = [k for k, v in self._store.items() if v.created_at.timestamp() < cutoff]
        for k in to_del: del self._store[k]
        return len(to_del)

    def health_report(self) -> MemoryHealthReport:
        return MemoryHealthReport(
            provider="mock", connected=self._state.value == "CONNECTED",
            available=self._state.value in ("CONNECTED","INITIALIZED"),
            latency_ms=0.1, records_count=len(self._store))
