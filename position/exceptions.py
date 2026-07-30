"""Position-specific exceptions."""
class PositionError(Exception): pass
class PositionNotFoundError(PositionError): pass
class PositionSynchronizationError(PositionError): pass
class InvalidPositionStateError(PositionError): pass
class PositionLifecycleError(PositionError): pass
class PositionManagerUnavailableError(PositionError): pass
