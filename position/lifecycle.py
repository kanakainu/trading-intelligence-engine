"""Position lifecycle state machine — validates every transition."""
from position.models import PositionStatus
from position.exceptions import InvalidPositionStateError


VALID_TRANSITIONS = {
    PositionStatus.CREATED:          {PositionStatus.SUBMITTED, PositionStatus.REJECTED, PositionStatus.ERROR},
    PositionStatus.SUBMITTED:        {PositionStatus.OPEN, PositionStatus.REJECTED, PositionStatus.ERROR},
    PositionStatus.OPEN:             {PositionStatus.MODIFIED, PositionStatus.PARTIALLY_CLOSED, PositionStatus.CLOSING, PositionStatus.CLOSED, PositionStatus.ERROR},
    PositionStatus.PARTIALLY_CLOSED: {PositionStatus.OPEN, PositionStatus.MODIFIED, PositionStatus.CLOSING, PositionStatus.CLOSED},
    PositionStatus.MODIFIED:         {PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED, PositionStatus.CLOSING, PositionStatus.CLOSED},
    PositionStatus.CLOSING:          {PositionStatus.CLOSED, PositionStatus.OPEN, PositionStatus.ERROR},
    PositionStatus.CLOSED:           set(),
    PositionStatus.REJECTED:         {PositionStatus.SUBMITTED, PositionStatus.CLOSED},
    PositionStatus.ERROR:            {PositionStatus.CLOSED, PositionStatus.CREATED},
}


def validate_transition(current: PositionStatus, target: PositionStatus) -> bool:
    """Return True if transition is valid, else raise."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidPositionStateError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Allowed: {[s.value for s in allowed] if allowed else 'terminal'}"
        )
    return True
