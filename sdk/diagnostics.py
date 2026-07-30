from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class SDKDiagnostics:
    def __init__(self):
        self._reports = {}

    def register_component(self, name: str, check_fn) -> None:
        self._reports[name] = check_fn

    def run_diagnostics(self) -> Dict[str, Any]:
        ts = datetime.now(timezone.utc)
        results = {}
        overall_status = "HEALTHY"

        for name, fn in self._reports.items():
            try:
                result = fn()
                results[name] = {
                    "status": result.get("status", "UNKNOWN"),
                    "details": result,
                }
                if result.get("status") == "FAILING":
                    overall_status = "DEGRADED"
            except Exception as e:
                results[name] = {"status": "FAILING", "details": {"error": str(e)}}
                overall_status = "DEGRADED"

        return {
            "timestamp": ts.isoformat(),
            "overall_status": overall_status,
            "components": results,
        }
