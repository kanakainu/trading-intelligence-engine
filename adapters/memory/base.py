"""Abstract Memory Adapter interface — provider-agnostic.
The runtime depends only on this. HCK, CRE, etc are isolated behind it.
"""
from abc import abstractmethod
from typing import List, Optional
from adapters.base import BaseAdapter
from adapters.memory.models import MemoryRecord, MemoryQuery, MemoryResult, MemoryHealthReport


class MemoryAdapterBase(BaseAdapter):
    @abstractmethod
    def store(self, record: MemoryRecord) -> MemoryRecord: ...

    @abstractmethod
    def retrieve(self, record_id: str) -> Optional[MemoryRecord]: ...

    @abstractmethod
    def search(self, query: MemoryQuery) -> MemoryResult: ...

    @abstractmethod
    def update(self, record: MemoryRecord) -> MemoryRecord: ...

    @abstractmethod
    def delete(self, record_id: str) -> bool: ...

    @abstractmethod
    def compact(self) -> None: ...

    @abstractmethod
    def cleanup(self, before_age_seconds: int = 86400) -> int: ...

    @abstractmethod
    def health_report(self) -> MemoryHealthReport: ...

    def store_many(self, records: List[MemoryRecord]) -> List[MemoryRecord]:
        return [self.store(r) for r in records]