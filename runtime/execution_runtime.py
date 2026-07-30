"""ExecutionRuntime — receives ExecutionContract, sends to Broker. No decisions.
Runtime validates → converts → sends → logs → returns ExecutionResult.
No Knowledge, no Detector, no Decision Engine, no Setup Resolver.
"""
import logging
from typing import Any, Optional
from core.execution.execution_contract import ExecutionContract
from runtime.execution_result import ExecutionResult
from runtime.order_converter import OrderConverter
from runtime.runtime_logger import RuntimeLogger

log = logging.getLogger("ExecutionRuntime")

WAIT = "WAIT"
SKIP = "SKIP"


class ExecutionRuntime:
    """
    Generic executor. Accepts ExecutionContract from TIE.
    Sends OrderRequest to BrokerAdapter.
    No trading decisions made here.
    """

    def __init__(self, broker_adapter: Any, logger: Optional[RuntimeLogger] = None):
        self._broker = broker_adapter
        self._converter = OrderConverter()
        self._log = logger or RuntimeLogger()

    def execute(self, contract: ExecutionContract) -> ExecutionResult:
        """
        Main entry point.
        1. Validate contract has actionable direction.
        2. Convert to OrderRequest.
        3. Submit to broker.
        4. Return ExecutionResult.
        """
        self._log.log_contract_received(contract.contract_id, contract.symbol, contract.direction)

        # 1. Validate — skip non-actionable contracts
        if contract.action in (WAIT, SKIP) or not contract.direction:
            return ExecutionResult(
                success=False,
                contract_id=contract.contract_id,
                status="SKIPPED",
                error=f"Contract action={contract.action} — no order sent",
            )

        # 2. Convert contract → broker order
        order = self._converter.convert(contract)

        # 3. Send to broker adapter
        try:
            response = self._broker.submit_order(order)
        except Exception as e:
            self._log.log_error(contract.contract_id, str(e))
            return ExecutionResult(
                success=False,
                contract_id=contract.contract_id,
                status="ERROR",
                error=str(e),
            )

        # 4. Build result
        success = response.status == "FILLED"
        if success:
            self._log.log_order_filled(contract.contract_id,
                                       response.filled_price or 0.0,
                                       response.filled_volume or 0.0)
        else:
            self._log.log_order_rejected(contract.contract_id,
                                         response.error or response.status)

        return ExecutionResult(
            success=success,
            contract_id=contract.contract_id,
            order_id=response.order_id,
            status=response.status,
            filled_price=response.filled_price,
            filled_volume=response.filled_volume,
            error=response.error,
        )
