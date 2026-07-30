"""Plugin Loader — instantiate plugins sorted by priority."""
from typing import Any, Dict, List
from core.rules.plugins.plugin_registry import PluginRegistry
from core.rules.plugins.plugin_interface import RuleResult


class PluginLoader:
    def __init__(self, registry: PluginRegistry):
        self._registry = registry

    def run_all(self, context: Dict[str, Any], facts: Dict[str, Any],
                setup_result: Any = None, decision: Any = None) -> List[RuleResult]:
        results = []
        names = sorted(
            self._registry.list_enabled(),
            key=lambda n: self._registry.get(n).priority()
        )
        for name in names:
            plugin = self._registry.get(name)
            result = plugin.evaluate(context, facts, setup_result, decision)
            results.append(result)
            if result.status == "REJECT":
                break  # short-circuit on first rejection
        return results
