"""Compatibility boundary — wraps Phase 3 ExecutionContract for Phase 4+ adapters."""
from typing import Any, Dict, Optional
from core.compat.version import TIE_VERSION, PHASE4_VERSION, SUPPORTED_ADAPTER_TARGETS
from core.compat.adapter_interface import AdapterInterface, NullAdapter
from core.compat.migration_guard import MigrationGuard
from core.execution.contract_serializer import to_dict


class CompatBoundary:
    """
    Sits between Phase 3 output and Phase 4 broker adapters.
    Phase 3 modules never import from here.
    """

    def __init__(self, adapter: Optional[AdapterInterface] = None):
        self._adapter = adapter or NullAdapter()
        MigrationGuard.register(PHASE4_VERSION, self.__class__.__name__)

    @staticmethod
    def version_info() -> Dict[str, str]:
        return {"tie_version": TIE_VERSION, "phase4_version": PHASE4_VERSION}

    def validate_target(self, target: str) -> bool:
        return target in SUPPORTED_ADAPTER_TARGETS

    def forward(self, contract: Any) -> Dict[str, Any]:
        """Convert ExecutionContract → dict, pass to adapter."""
        payload = to_dict(contract) if hasattr(contract, "contract_id") else contract
        return self._adapter.send(payload)

    def dry_run(self, contract: Any) -> Dict[str, Any]:
        """Always uses NullAdapter regardless of configured adapter."""
        payload = to_dict(contract) if hasattr(contract, "contract_id") else contract
        return NullAdapter().send(payload)
