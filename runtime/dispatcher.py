"""In-process event dispatcher — pub/sub for runtime events."""
import threading
from typing import Callable, Dict, List, Optional
from runtime.events import RuntimeEvent, EventType


class Dispatcher:
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: EventType, handler: Callable[[RuntimeEvent], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        with self._lock:
            subs = self._subscribers.get(event_type, [])
            if handler in subs:
                subs.remove(handler)

    def publish(self, event: RuntimeEvent) -> None:
        with self._lock:
            handlers = self._subscribers.get(event.event_type, [])
        for h in handlers:
            try:
                h(event)
            except Exception:
                pass  # swallow handler errors to avoid cascade

    def clear(self) -> None:
        with self._lock:
            self._subscribers.clear()
