"""Adapter interface placeholder — all Phase 4+ adapters implement this."""
from abc import ABC, abstractmethod
from typing import Any, Dict


class AdapterInterface(ABC):
    """Base adapter. Concrete implementations live in adapters/ (Phase 4.2+)."""

    @property
    @abstractmethod
    def target(self) -> str:
        """Adapter target id, e.g. 'mt5', 'rest_api'."""

    @abstractmethod
    def send(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """Send ExecutionContract payload. Returns broker response dict."""


class NullAdapter(AdapterInterface):
    """No-op adapter for testing / dry-run."""

    @property
    def target(self) -> str:
        return "null"

    def send(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "noop", "contract_id": contract.get("contract_id")}
