"""Migration guard — validates Phase 3 contract integrity + migration readiness."""
from typing import Any, Dict, List, Tuple

REQUIRED_FIELDS = ["contract_id","action","symbol","confidence","timestamp"]
VALID_ACTIONS   = {"BUY","SELL","WAIT","SKIP"}


def check_contract(d: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    for f in REQUIRED_FIELDS:
        if f not in d:
            errors.append(f"missing:{f}")
    if "action" in d and d["action"] not in VALID_ACTIONS:
        errors.append(f"invalid_action:{d['action']}")
    if "confidence" in d:
        try:
            c = float(d["confidence"])
            if not (0.0 <= c <= 1.0):
                errors.append(f"confidence_oob:{c}")
        except (TypeError, ValueError):
            errors.append("confidence_not_float")
    return len(errors) == 0, errors


def backward_compatible(d: Dict[str, Any]) -> bool:
    ok, _ = check_contract(d)
    return ok


def migration_ready(d: Dict[str, Any]) -> Tuple[bool, List[str]]:
    ok, errors = check_contract(d)
    warnings = []
    if not d.get("methodology"):
        warnings.append("methodology empty — Phase 4 adapter may need it")
    if not d.get("setup"):
        warnings.append("setup empty — routing hint missing")
    return ok, warnings
