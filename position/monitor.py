"""Position monitor — watch for changes and publish events."""
from typing import Callable, Optional
from position.models import Position
from position.events import PositionEvent, PositionEventType


class PositionMonitor:
    """Monitors position changes and publishes events."""

    def __init__(self, publish_fn: Optional[Callable[[PositionEvent], None]] = None):
        self._publish = publish_fn or (lambda e: None)

    def on_opened(self, pos: Position) -> None:
        self._publish(PositionEvent(
            event_type=PositionEventType.POSITION_OPENED,
            position_id=pos.position_id,
            payload={"symbol": pos.symbol, "side": pos.side, "volume": pos.volume},
        ))

    def on_updated(self, pos: Position, changes: dict) -> None:
        self._publish(PositionEvent(
            event_type=PositionEventType.POSITION_UPDATED,
            position_id=pos.position_id,
            payload={"changes": changes},
        ))

    def on_closed(self, pos: Position) -> None:
        self._publish(PositionEvent(
            event_type=PositionEventType.POSITION_CLOSED,
            position_id=pos.position_id,
            payload={"realized_pnl": pos.realized_pnl},
        ))

    def on_synced(self, count: int) -> None:
        self._publish(PositionEvent(
            event_type=PositionEventType.POSITION_SYNCED,
            payload={"changes": count},
        ))

    def on_error(self, pos_id: str, error: str) -> None:
        self._publish(PositionEvent(
            event_type=PositionEventType.POSITION_ERROR,
            position_id=pos_id,
            payload={"error": error},
        ))
