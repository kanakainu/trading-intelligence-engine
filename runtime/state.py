"""Runtime lifecycle states."""
from enum import Enum


class RuntimeState(str, Enum):
    CREATED      = "CREATED"
    INITIALIZED  = "INITIALIZED"
    STARTED      = "STARTED"
    PAUSED       = "PAUSED"
    RUNNING      = "RUNNING"
    STOPPING     = "STOPPING"
    STOPPED      = "STOPPED"
    SHUTDOWN     = "SHUTDOWN"
    ERROR        = "ERROR"
