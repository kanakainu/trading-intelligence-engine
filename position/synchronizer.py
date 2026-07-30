"""Position synchronizer — sync local state with Broker Adapter.
Does NOT communicate directly with brokers — uses BrokerAdapter interface.
"""
from datetime import datetime, timezone
from position.models import Position, PositionStatus
from position.tracker import PositionTracker
from position.health import PositionHealthMonitor


class PositionSynchronizer:
    def __init__(self, tracker: PositionTracker, health_monitor: PositionHealthMonitor):
        self._tracker = tracker
        self._health = health_monitor

    def synchronize(self, broker_positions: list) -> int:
        """
        Compare broker positions with local tracker.
        Returns count of changes detected.
        Returns: number of sync changes.
        """
        changes = 0
        broker_ids = set()

        for bp in broker_positions:
            pid = bp.get("position_id", "")
            broker_ids.add(pid)
            local = self._tracker.get(pid)

            if not local:
                # New position from broker
                pos = Position(
                    position_id=pid,
                    order_id=bp.get("order_id", ""),
                    symbol=bp.get("symbol", ""),
                    side=bp.get("side", ""),
                    volume=bp.get("volume", 0.0),
                    entry_price=bp.get("entry_price", 0),
                    current_price=bp.get("current_price", 0),
                    stop_loss=bp.get("stop_loss"),
                    take_profit=bp.get("take_profit"),
                    unrealized_pnl=bp.get("unrealized_pnl", 0.0),
                    status=PositionStatus.OPEN,
                    opened_at=datetime.now(timezone.utc),
                )
                self._tracker.add(pos)
                changes += 1
            else:
                # Update existing position
                local.current_price = bp.get("current_price", local.current_price)
                local.unrealized_pnl = bp.get("unrealized_pnl", local.unrealized_pnl)
                local.updated_at = datetime.now(timezone.utc)
                self._tracker.update(local)
                changes += 1

        # Detect closed positions (in local but not in broker)
        for local in self._tracker.list_active():
            if local.position_id not in broker_ids and local.status != PositionStatus.CLOSED:
                local.status = PositionStatus.CLOSED
                local.closed_at = datetime.now(timezone.utc)
                self._tracker.remove(local.position_id)
                changes += 1

        self._health.record_sync(ok=True)
        return changes
