"""Position tracker — in-memory store for active/closed/historical positions."""
from typing import Dict, List, Optional
from position.models import Position, PositionStatus


class PositionTracker:
    """Provider-independent tracker. Maintains complete position state."""

    def __init__(self):
        self._positions: Dict[str, Position] = {}  # position_id -> Position
        self._closed: Dict[str, Position] = {}
        self._history: Dict[str, Position] = {}

    def add(self, pos: Position) -> None:
        self._positions[pos.position_id] = pos

    def get(self, position_id: str) -> Optional[Position]:
        return self._positions.get(position_id) or self._closed.get(position_id) or self._history.get(position_id)

    def update(self, pos: Position) -> None:
        if pos.position_id in self._closed:
            self._closed[pos.position_id] = pos
        else:
            self._positions[pos.position_id] = pos

    def remove(self, position_id: str) -> Optional[Position]:
        pos = self._positions.pop(position_id, None)
        if pos:
            self._closed[position_id] = pos
            self._prune_history()
        return pos

    def list_active(self) -> List[Position]:
        return [p for p in self._positions.values() if p.status in {
            PositionStatus.OPEN, PositionStatus.SUBMITTED,
            PositionStatus.MODIFIED, PositionStatus.PARTIALLY_CLOSED,
            PositionStatus.CLOSING
        }]

    def list_closed(self) -> List[Position]:
        return [p for p in self._closed.values()]

    def list_by_symbol(self, symbol: str) -> List[Position]:
        return [p for p in self._positions.values() if p.symbol == symbol]

    def list_history(self, limit: int = 100) -> List[Position]:
        all_pos = list(self._positions.values()) + list(self._closed.values())
        return sorted(all_pos, key=lambda p: p.opened_at or p.created_at, reverse=True)[:limit]

    def count_active(self) -> int: return len(self.list_active())
    def count_closed(self) -> int: return len(self._closed)

    def _prune_history(self, max_size: int = 1000) -> None:
        if len(self._closed) > max_size:
            excess = len(self._closed) - max_size
            for _ in range(excess):
                k = next(iter(self._closed))
                self._history[k] = self._closed.pop(k)
