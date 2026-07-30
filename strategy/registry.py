from typing import Dict, List, Optional
from strategy.models import StrategyDefinition, StrategyStatus
from strategy.exceptions import StrategyRegistryError


class StrategyRegistry:
    def __init__(self):
        self._strategies: Dict[str, StrategyDefinition] = {}
        self._status: Dict[str, StrategyStatus] = {}

    def register(self, definition: StrategyDefinition) -> None:
        if definition.strategy_id in self._strategies:
            raise StrategyRegistryError(f"Strategy {definition.strategy_id} already registered")
        self._strategies[definition.strategy_id] = definition
        self._status[definition.strategy_id] = StrategyStatus.REGISTERED

    def unregister(self, strategy_id: str) -> None:
        self._strategies.pop(strategy_id, None)
        self._status.pop(strategy_id, None)

    def get_definition(self, strategy_id: str) -> Optional[StrategyDefinition]:
        return self._strategies.get(strategy_id)

    def set_status(self, strategy_id: str, status: StrategyStatus) -> None:
        if strategy_id in self._status:
            self._status[strategy_id] = status

    def get_status(self, strategy_id: str) -> Optional[StrategyStatus]:
        return self._status.get(strategy_id)

    def list_strategies(self) -> List[str]:
        return list(self._strategies.keys())
