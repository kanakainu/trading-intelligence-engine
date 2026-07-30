"""Adapter health monitor — collect health from all registered adapters."""
from typing import Any, Dict, List
from adapters.registry import AdapterRegistry


def collect(registry: AdapterRegistry) -> List[Dict[str, Any]]:
    results = []
    for name in registry.discover():
        adapter = registry.load(name)
        if adapter:
            try:
                adapter.initialize()
                results.append(adapter.health_check())
            except Exception as e:
                results.append({"name": name, "status": "ERROR", "error": str(e)})
    return results
