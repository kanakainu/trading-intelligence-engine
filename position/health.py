"""Position health monitor — aggregates position manager status."""
from datetime import datetime, timezone
from typing import List
from position.models import PositionHealth


class PositionHealthMonitor:
    def __init__(self):
        self._active = 0
        self._closed = 0
        self._errors = 0
        self._last_sync: datetime = datetime.now(timezone.utc)
        self._sync_status = "OK"

    def record_open(self, count: int = 1) -> None:
        self._active += count

    def record_close(self, count: int = 1) -> None:
        self._active = max(0, self._active - count)
        self._closed += count

    def record_sync(self, ok: bool = True) -> None:
        self._last_sync = datetime.now(timezone.utc)
        self._sync_status = "OK" if ok else "ERROR"

    def record_error(self) -> None:
        self._errors += 1

    def get_report(self) -> PositionHealth:
        return PositionHealth(
            active_positions=self._active,
            closed_positions=self._closed,
            synchronization_status=self._sync_status,
            last_sync=self._last_sync,
            status="OPERATIONAL",
            errors=self._errors,
        )
