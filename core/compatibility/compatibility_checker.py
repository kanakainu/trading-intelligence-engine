"""Compatibility checker — health report for Phase 3 → Phase 4 migration."""
from typing import Any, Dict
from core.compatibility.version_manager import CURRENT_VERSION, TARGET_VERSION, compatible
from core.compatibility.migration_guard import check_contract, migration_ready


def check(contract_dict: Dict[str, Any] = None) -> Dict[str, Any]:
    report = {
        "phase3_status":   "compatible",
        "current_version": CURRENT_VERSION,
        "target_version":  TARGET_VERSION,
        "version_compat":  compatible(CURRENT_VERSION, TARGET_VERSION),
        "migration_ready": False,
        "warnings":        [],
        "errors":          [],
    }
    if not compatible(CURRENT_VERSION, TARGET_VERSION):
        report["warnings"].append(f"major version gap {CURRENT_VERSION} → {TARGET_VERSION}")

    if contract_dict:
        ok, errors = check_contract(contract_dict)
        _, warnings = migration_ready(contract_dict)
        report["migration_ready"] = ok
        report["errors"].extend(errors)
        report["warnings"].extend(warnings)
        if errors:
            report["phase3_status"] = "invalid_contract"
        else:
            report["phase3_status"] = "compatible"
    else:
        report["migration_ready"] = True

    return report
