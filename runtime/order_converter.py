"""OrderConverter — translate ExecutionContract to OrderRequest.
No trading logic. Pure schema translation.
"""
from adapters.broker.models import OrderRequest
from core.execution.execution_contract import ExecutionContract


class OrderConverter:
    """
    Converts TIE ExecutionContract → Broker OrderRequest.
    No BUY/SELL decisions. No SL/TP recalculation. Pure conversion.
    """

    def convert(self, contract: ExecutionContract) -> OrderRequest:
        meta = contract.metadata or {}
        volume = meta.get("volume", 0.01)
        return OrderRequest(
            symbol=contract.symbol,
            side=contract.direction,  # BUY | SELL — already decided by TIE
            volume=float(volume),
            order_type=meta.get("order_type", "market"),
            stop_loss=contract.sl,
            take_profit=contract.tp,
            comment=f"TIE:{contract.contract_id}",
            metadata={
                "contract_id": contract.contract_id,
                "setup": contract.setup,
                "confidence": contract.confidence,
                "entry_pattern": contract.entry_pattern,
                "methodology": contract.methodology,
                "trace_id": contract.trace_id,
                "partial_tp_pct": meta.get("partial_tp_pct"),
                "be_trigger_atr": meta.get("be_trigger_atr"),
                "trail_trigger_atr": meta.get("trail_trigger_atr"),
                "trail_offset_atr": meta.get("trail_offset_atr"),
            },
        )
