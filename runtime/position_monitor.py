"""PositionMonitor — watches live positions each tick and emits ExecutionResults."""
from typing import Any, Callable, Dict, List, Optional
from runtime.position_state import PositionState
from runtime.contract_executor import ContractExecutor, ExecutionResult


class PositionMonitor:
    """
    Monitors live positions. No broker access. No trading decisions.
    Delegates evaluation to ContractExecutor.
    Emits results via on_result callback.
    """

    def __init__(self, on_result: Optional[Callable] = None):
        self._executor = ContractExecutor()
        self._on_result = on_result or (lambda pos, result: None)

    def tick(self, positions: List[PositionState],
             contracts: Dict[str, Any],
             market_update: Dict[str, float]) -> List[ExecutionResult]:
        """
        Called each market tick.
        positions: list of live PositionState
        contracts: dict mapping position_id -> ExecutionContract
        market_update: dict mapping symbol -> current price + atr + candles
        Returns list of ExecutionResults.
        """
        results = []
        for pos in positions:
            # Update current price from market
            symbol_data = market_update.get(pos.symbol, {})
            if isinstance(symbol_data, dict):
                pos.current_price = symbol_data.get("price", pos.current_price)
                atr = symbol_data.get("atr", 0.0)
                candles = symbol_data.get("candles", None)
            else:
                atr = 0.0
                candles = None

            contract = contracts.get(pos.position_id)
            if not contract:
                continue

            result = self._executor.evaluate(pos, contract, atr, candles, m5_candles=candles.get("M5") if isinstance(candles, dict) else None)
            if result.action != "none":
                self._on_result(pos, result)
            results.append(result)
        return results
