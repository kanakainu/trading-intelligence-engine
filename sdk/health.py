from typing import Dict, Any


class SDKHealth:
    def __init__(self):
        self._check_fns = {}

    def register_check(self, name: str, fn) -> None:
        self._check_fns[name] = fn

    def check(self) -> Dict[str, Any]:
        results = {}
        overall = True
        for name, fn in self._check_fns.items():
            try:
                res = fn()
                ok = res.get("healthy", True)
                results[name] = {"healthy": ok, "detail": res.get("detail", "")}
                if not ok:
                    overall = False
            except Exception as e:
                results[name] = {"healthy": False, "detail": str(e)}
                overall = False

        return {
            "overall_healthy": overall,
            "runtime_status": "OPERATIONAL" if overall else "DEGRADED",
            "checks": results,
        }
