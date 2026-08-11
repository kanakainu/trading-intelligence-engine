"""PositionMonitor — watches live positions each tick and emits ExecutionResults."""
from typing import Any, Callable, Dict, List, Optional
from runtime.position_state import PositionState
from runtime.contract_executor import ContractExecutor, ExecutionResult
import logging

log = logging.getLogger("PositionMonitor")


class PositionMonitor:
    """
    Monitors live positions. Delegates evaluation to ContractExecutor.
    Executes modify/close via broker when ContractExecutor decides.
    """

    def __init__(self, on_result: Optional[Callable] = None, broker: Any = None):
        self._executor = ContractExecutor()
        self._on_result = on_result or (lambda pos, result: None)
        self._broker = broker

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
                self._exec_followup(pos, result)
            results.append(result)
        return results

    def _exec_followup(self, pos: PositionState, result: ExecutionResult):
        """Push trailing SL / partial close to broker."""
        if self._broker is None:
            return
        try:
            if result.action == "modify":
                new_sl = getattr(result, "new_sl", None)
                new_tp = getattr(result, "new_tp", None)
                if new_sl is not None or new_tp is not None:
                    # Gateway /trade/modify REQUIRES both sl AND tp
                    _sl = new_sl if new_sl is not None else pos.stop_loss
                    _tp = new_tp if new_tp is not None else pos.take_profit
                    if not _sl or not _tp:
                        log.warning(f"Modify {pos.position_id} skipped: SL={_sl} TP={_tp} — missing value")
                        return
                    resp = self._broker.modify_order(str(pos.position_id), stop_loss=_sl, take_profit=_tp)
                    log.info(f"Modify {pos.position_id}: SL={_sl} TP={_tp} -> {getattr(resp,'status','?')}")
            elif result.action == "close":
                resp = self._broker.close_position(str(pos.position_id))
                log.info(f"Close {pos.position_id} -> {getattr(resp,'status','?')}")
        except Exception as e:
            log.error(f"Exec follow-up {pos.position_id}: {e}")
