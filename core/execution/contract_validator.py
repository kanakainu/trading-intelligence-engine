"""ContractValidator — validate ExecutionContract fields before passing to adapter."""
from typing import List, Tuple
from core.execution.execution_contract import ExecutionContract

VALID_ACTIONS = {"BUY","SELL","WAIT","SKIP"}


class ContractValidator:
    def validate(self, contract: ExecutionContract) -> Tuple[bool, List[str]]:
        errors = []
        if not contract.contract_id:    errors.append("missing:contract_id")
        if not contract.action:         errors.append("missing:action")
        if contract.action not in VALID_ACTIONS:
            errors.append(f"invalid_action:{contract.action}")
        if not (0.0 <= contract.confidence <= 1.0):
            errors.append(f"invalid_confidence:{contract.confidence}")
        return len(errors) == 0, errors
