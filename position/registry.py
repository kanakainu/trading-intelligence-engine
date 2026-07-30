"""Position registry — pluggable monitors, lifecycle handlers, sync handlers."""
from typing import Any, Callable, Dict, List, Optional


class PositionRegistry:
    def __init__(self):
        self._monitors: Dict[str, Callable] = {}
        self._lifecycle_handlers: Dict[str, Callable] = {}
        self._sync_handlers: Dict[str, Callable] = {}

    def register_monitor(self, name: str, monitor: Callable) -> None:
        self._monitors[name] = monitor

    def register_lifecycle_handler(self, name: str, handler: Callable) -> None:
        self._lifecycle_handlers[name] = handler

    def register_sync_handler(self, name: str, handler: Callable) -> None:
        self._sync_handlers[name] = handler

    def get_monitor(self, name: str) -> Optional[Callable]: return self._monitors.get(name)
    def get_lifecycle_handler(self, name: str) -> Optional[Callable]: return self._lifecycle_handlers.get(name)
    def get_sync_handler(self, name: str) -> Optional[Callable]: return self._sync_handlers.get(name)
    def list_monitors(self) -> List[str]: return list(self._monitors.keys())
    def list_lifecycle_handlers(self) -> List[str]: return list(self._lifecycle_handlers.keys())
    def list_sync_handlers(self) -> List[str]: return list(self._sync_handlers.keys())
