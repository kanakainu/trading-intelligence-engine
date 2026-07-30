"""RuntimeLogger — structured execution event log. No trading logic."""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

log = logging.getLogger("ExecutionRuntime")


class RuntimeLogger:
    def __init__(self):
        self._events = []

    def log_contract_received(self, contract_id: str, symbol: str, direction: str) -> None:
        self._record("CONTRACT_RECEIVED", contract_id,
                     {"symbol": symbol, "direction": direction})

    def log_order_sent(self, contract_id: str, order_id: str) -> None:
        self._record("ORDER_SENT", contract_id, {"order_id": order_id})

    def log_order_filled(self, contract_id: str, price: float, volume: float) -> None:
        self._record("ORDER_FILLED", contract_id, {"price": price, "volume": volume})

    def log_order_rejected(self, contract_id: str, reason: str) -> None:
        self._record("ORDER_REJECTED", contract_id, {"reason": reason})

    def log_error(self, contract_id: str, error: str) -> None:
        self._record("EXECUTION_ERROR", contract_id, {"error": error})

    def get_events(self, contract_id: Optional[str] = None):
        if contract_id:
            return [e for e in self._events if e["contract_id"] == contract_id]
        return list(self._events)

    def _record(self, event_type: str, contract_id: str, payload: Dict[str, Any]) -> None:
        entry = {"event": event_type, "contract_id": contract_id,
                 "ts": datetime.now(timezone.utc).isoformat(), **payload}
        self._events.append(entry)
        log.info(f"[{event_type}] {contract_id} {payload}")
