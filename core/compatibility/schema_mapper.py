"""Schema mapper — safe translation Phase 3 ↔ Phase 4. Read-only, reversible."""
from typing import Any, Dict


def contract_to_dict(contract: Any) -> Dict[str, Any]:
    """ExecutionContract → plain dict (Phase 3 → generic payload)."""
    from core.execution.contract_serializer import to_dict
    return to_dict(contract)


def dict_to_contract_stub(d: Dict[str, Any]) -> Dict[str, Any]:
    """Generic payload → Phase 4 runtime stub dict (reverse mapping)."""
    return {
        "contract_id":  d.get("contract_id",""),
        "action":       d.get("action","WAIT"),
        "symbol":       d.get("symbol",""),
        "confidence":   d.get("confidence", 0.0),
        "methodology":  d.get("methodology",""),
        "setup":        d.get("setup",""),
        "timestamp":    d.get("timestamp",""),
        "_source":      "phase3",
    }
