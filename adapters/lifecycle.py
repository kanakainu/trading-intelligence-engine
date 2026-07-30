"""Adapter lifecycle states."""
from enum import Enum


class AdapterState(str, Enum):
    CREATED      = "CREATED"
    INITIALIZED  = "INITIALIZED"
    CONNECTED    = "CONNECTED"
    ERROR        = "ERROR"
    DISCONNECTED = "DISCONNECTED"
