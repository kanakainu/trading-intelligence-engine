"""Position Manager — tracks/manages complete position lifecycle.
Does NOT generate trade decisions. Does NOT evaluate risk.
Only manages existing positions.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from position.models import Position, PositionStatus, PositionAuditEntry, PositionHealth
from position.lifecycle import validate_transition
from position.tracker import PositionTracker
from position.synchronizer import PositionSynchronizer
from position.monitor import PositionMonitor
from position.audit import PositionAuditTrail
from position.health import PositionHealthMonitor
from position.registry import PositionRegistry
from position.config import PositionConfig
from position.exceptions import (
    PositionNotFoundError, PositionSynchronizationError,
    InvalidPositionStateError, PositionLifecycleError,
)


class PositionManager:
    """Central position manager. All position operations go through this."""

    def __init__(self, config: Optional[PositionConfig] = None):
        self._config = config or PositionConfig.default()
        self._tracker = PositionTracker()
        self._audit = PositionAuditTrail()
        self._health = PositionHealthMonitor()
        self._registry = PositionRegistry()
        self._publish_fn: Any = None
        self._monitor = PositionMonitor(publish_fn=self._publish_event)
        self._synchronizer = PositionSynchronizer(self._tracker, self._health)
        self._status = "CREATED"

    def initialize(self) -> None:
        self._status = "INITIALIZED"

    def start(self) -> None:
        self._status = "RUNNING"

    def stop(self) -> None:
        self._status = "STOPPED"

    def set_publish_fn(self, fn: Any) -> None:
        """Set event publishing function."""
        self._publish_fn = fn
        self._monitor = PositionMonitor(publish_fn=self._publish_event)

    def _publish_event(self, event) -> None:
        if self._publish_fn:
            self._publish_fn(event)

    # ── Position API ──────────────────────────────────────────────────────
    def open_position(self, symbol: str, side: str, volume: float,
                      entry_price: Decimal, stop_loss: Optional[Decimal] = None,
                      take_profit: Optional[Decimal] = None,
                      order_id: str = "", **metadata) -> Position:
        pos = Position(
            position_id=str(uuid.uuid4())[:12],
            order_id=order_id,
            symbol=symbol,
            side=side,
            volume=volume,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=PositionStatus.OPEN,
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            metadata=metadata,
        )
        self._tracker.add(pos)
        self._audit.record(PositionAuditEntry(
            position_id=pos.position_id,
            current_status=PositionStatus.OPEN.value,
            source="open_position",
            notes=f"{side} {volume} {symbol} @ {entry_price}",
        ))
        self._health.record_open()
        self._monitor.on_opened(pos)
        return pos

    def update_position(self, position_id: str, **changes) -> Position:
        pos = self._tracker.get(position_id)
        if not pos:
            raise PositionNotFoundError(f"Position not found: {position_id}")
        validate_transition(pos.status, PositionStatus.MODIFIED)

        old_status = pos.status
        applied = {}
        for key, val in changes.items():
            if hasattr(pos, key):
                setattr(pos, key, val)
                applied[key] = val
        
        # Update MFE/MAE
        pnl = float(pos.unrealized_pnl)
        pos.max_favorable_excursion = max(pos.max_favorable_excursion, pnl)
        pos.max_adverse_excursion = min(pos.max_adverse_excursion, pnl)

        pos.status = PositionStatus.MODIFIED if pos.status == PositionStatus.OPEN else pos.status
        pos.updated_at = datetime.now(timezone.utc)
        self._tracker.update(pos)

        self._audit.record(PositionAuditEntry(
            position_id=position_id,
            previous_status=old_status.value,
            current_status=pos.status.value,
            source="update_position",
            notes=f"Updated: {applied}",
        ))
        self._monitor.on_updated(pos, applied)
        return pos

    def close_position(self, position_id: str, realized_pnl: float = 0.0) -> Position:
        pos = self._tracker.get(position_id)
        if not pos:
            raise PositionNotFoundError(f"Position not found: {position_id}")
        validate_transition(pos.status, PositionStatus.CLOSED)

        old_status = pos.status
        pos.status = PositionStatus.CLOSED
        pos.realized_pnl = realized_pnl
        pos.closed_at = datetime.now(timezone.utc)
        pos.updated_at = datetime.now(timezone.utc)
        self._tracker.remove(position_id)

        self._audit.record(PositionAuditEntry(
            position_id=position_id,
            previous_status=old_status.value,
            current_status=PositionStatus.CLOSED.value,
            source="close_position",
            notes=f"Realized PnL: {realized_pnl}",
        ))
        self._health.record_close()
        self._monitor.on_closed(pos)
        return pos

    def get_position(self, position_id: str) -> Optional[Position]:
        return self._tracker.get(position_id)

    def list_positions(self, active_only: bool = True) -> List[Position]:
        return self._tracker.list_active() if active_only else self._tracker.list_history()

    def synchronize(self, broker_positions: list) -> int:
        return self._synchronizer.synchronize(broker_positions)

    def refresh(self) -> None:
        """Refresh internal state consistency."""
        pass

    def health_check(self) -> PositionHealth:
        return self._health.get_report()

    @property
    def tracker(self) -> PositionTracker: return self._tracker
    @property
    def audit(self) -> PositionAuditTrail: return self._audit
    @property
    def registry(self) -> PositionRegistry: return self._registry
    @property
    def config(self) -> PositionConfig: return self._config
