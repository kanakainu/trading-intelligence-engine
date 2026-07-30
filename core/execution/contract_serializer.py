"""ContractSerializer — ExecutionContract → JSON / dict. Adapter-agnostic."""
import json
from typing import Any, Dict
from core.execution.execution_contract import ExecutionContract


def to_dict(contract: ExecutionContract) -> Dict[str, Any]:
    return {
        "contract_id":   contract.contract_id,
        "action":        contract.action,
        "symbol":        contract.symbol,
        "methodology":   contract.methodology,
        "setup":         contract.setup,
        "entry_pattern": contract.entry_pattern,
        "confidence":    contract.confidence,
        "direction":     contract.direction,
        "entry":         contract.entry,
        "sl":            contract.sl,
        "tp":            contract.tp,
        "reason":        contract.reason,
        "trace_id":      contract.trace_id,
        "timestamp":     contract.timestamp.isoformat(),
        "metadata":      contract.metadata,
    }


def to_json(contract: ExecutionContract, indent: int = 2) -> str:
    return json.dumps(to_dict(contract), indent=indent, ensure_ascii=False)
