"""Plugin Registry — register and lookup Rule Plugins."""
from typing import Dict, List, Optional, Type
from core.rules.plugins.plugin_interface import RulePluginInterface


class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, RulePluginInterface] = {}

    def register(self, name: str, plugin: RulePluginInterface) -> None:
        self._plugins[name] = plugin

    def get(self, name: str) -> Optional[RulePluginInterface]:
        return self._plugins.get(name)

    def list_enabled(self) -> List[str]:
        return [n for n, p in self._plugins.items() if p.enabled()]

    def list_all(self) -> List[str]:
        return list(self._plugins.keys())
