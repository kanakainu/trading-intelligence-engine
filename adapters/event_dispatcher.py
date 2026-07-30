"""EventDispatcher — publishes TIE events to HCK."""
from typing import Any, Dict
from adapters.hck_bridge import HCKBridge


class EventDispatcher:
    def __init__(self, bridge: HCKBridge):
        self._bridge = bridge

    def dispatch(self, event_type: str, payload: Dict[str, Any]) -> bool:
        return self._bridge.publish_event(event_type, payload)
