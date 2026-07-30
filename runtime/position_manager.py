"""PositionManager — entry point for runtime position management.
Receives Execution Contracts. Does not read Knowledge Pack, Facts, or Detectors.
"""
from typing import Any, Callable, Dict, List, Optional
from runtime.position_state import PositionState
from runtime.position_monitor import PositionMonitor
from runtime.contract_executor import ContractExecutor, ExecutionResult


class PositionManager:
    """
    Runtime position manager. Contract-driven only.
    No Brain, no Knowledge, no Detector, no Rule Engine.
    """

    def __init__(self, on_action: Optional[Callable] = None):
        self._positions: Dict[str, PositionState] = {}
        self._contracts: Dict[str, Any] = {}
        self._monitor = PositionMonitor(on_result=on_action)
        self._action_log: List[dict] = []

    def register_position(self, pos: PositionState, contract: Any) -> None:
        """Register a new position with its Execution Contract."""
        self._positions[pos.position_id] = pos
        self._contracts[pos.position_id] = contract

    def remove_position(self, position_id: str) -> None:
        self._positions.pop(position_id, None)
        self._contracts.pop(position_id, None)

    def tick(self, market_update: Dict[str, Any]) -> List[ExecutionResult]:
        """Process one market tick. Returns list of ExecutionResults."""
        return self._monitor.tick(
            positions=list(self._positions.values()),
            contracts=self._contracts,
            market_update=market_update,
        )

    def list_positions(self) -> List[PositionState]:
        return list(self._positions.values())

    def get_position(self, position_id: str) -> Optional[PositionState]:
        return self._positions.get(position_id)

    @property
    def count(self) -> int:
        return len(self._positions)
