"""Base adapter interface — every adapter implements this."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict
from adapters.lifecycle import AdapterState


class BaseAdapter(ABC):
    def __init__(self):
        self._state = AdapterState.CREATED

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]: ...

    def get_status(self) -> AdapterState:
        return self._state

    def _set_state(self, s: AdapterState) -> None:
        self._state = s

    def _health(self, latency: float = 0.0, error=None) -> Dict[str, Any]:
        return {
            "name":       self.name,
            "status":     self._state.value,
            "latency":    latency,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "error":      error,
        }
