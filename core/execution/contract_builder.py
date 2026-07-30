"""ContractBuilder — TradeDecision → ExecutionContract. No broker/MT5/lot/margin."""
from typing import Any, Dict, Optional
from core.execution.execution_contract import ExecutionContract
from core.decision.trade_decision import TradeDecision


class ContractBuilder:
    def build(
        self,
        decision: TradeDecision,
        symbol: str = "",
        methodology: str = "",
        entry_pattern: str = "",
    ) -> ExecutionContract:
        return ExecutionContract(
            action=decision.action,
            symbol=symbol,
            methodology=methodology,
            setup=decision.setup_name,
            entry_pattern=entry_pattern,
            confidence=decision.confidence,
            direction=decision.action,
            reason=decision.reason,
            trace_id=decision.setup_id,
            metadata={
                "setup_id": decision.setup_id,
                "ranking": decision.ranking[:3],
            },
        )
