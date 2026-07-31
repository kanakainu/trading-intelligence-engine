"""Trade Lifecycle Engine — State machine for position management.

Merges PositionMonitor + ContractExecutor.
NO strategy code. Pure lifecycle.
"""
from typing import Dict, List, Optional, Any
from core.lifecycle.lifecycle_models import (
    LifecycleState, PositionSnapshot, LifecycleEvent
)


class TradeLifecycle:
    """
    State machine for position lifecycle.
    
    States: PENDING → OPEN → PARTIAL/BREAKEVEN/TRAILING → CLOSED → REFLECTION
    
    NO strategy logic.
    """
    
    def __init__(self):
        self._positions: Dict[str, PositionSnapshot] = {}
        self._events: List[LifecycleEvent] = []
    
    def create_position(self, position_id: str, **kwargs) -> PositionSnapshot:
        """Create new position in PENDING state."""
        snapshot = PositionSnapshot(
            position_id=position_id,
            state=LifecycleState.PENDING,
            **kwargs
        )
        self._positions[position_id] = snapshot
        return snapshot
    
    def update_state(
        self,
        position_id: str,
        new_state: LifecycleState,
        trigger: str,
        **kwargs
    ) -> PositionSnapshot:
        """Transition position to new state."""
        pos = self._positions.get(position_id)
        if not pos:
            raise ValueError(f"Position {position_id} not found")
        
        # Create event
        event = LifecycleEvent(
            event_id=f"ev_{position_id}_{len(self._events)}",
            position_id=position_id,
            event_type=trigger,
            old_state=pos.state,
            new_state=new_state,
            trigger=trigger,
            trigger_value=kwargs.get("trigger_value"),
            price=kwargs.get("price"),
            volume=kwargs.get("volume"),
            pl=kwargs.get("pl"),
        )
        self._events.append(event)
        
        # Update position
        updated = PositionSnapshot(
            **{**pos.__dict__, "state": new_state, **kwargs}
        )
        self._positions[position_id] = updated
        return updated
    
    def get(self, position_id: str) -> Optional[PositionSnapshot]:
        """Get position snapshot."""
        return self._positions.get(position_id)
    
    def list_by_state(self, state: LifecycleState) -> List[PositionSnapshot]:
        """List all positions in a state."""
        return [p for p in self._positions.values() if p.state == state]
    
    def get_events(self, position_id: str) -> List[LifecycleEvent]:
        """Get events for a position."""
        return [e for e in self._events if e.position_id == position_id]


# Global instance
_global_lifecycle: Optional[TradeLifecycle] = None


def get_trade_lifecycle() -> TradeLifecycle:
    global _global_lifecycle
    if _global_lifecycle is None:
        _global_lifecycle = TradeLifecycle()
    return _global_lifecycle