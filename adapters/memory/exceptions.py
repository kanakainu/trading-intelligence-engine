"""Memory adapter exceptions — framework only."""
from adapters.exceptions import AdapterError

class MemoryConnectionError(AdapterError): pass
class MemoryUnavailableError(AdapterError): pass
class MemoryQueryError(AdapterError): pass
class MemoryWriteError(AdapterError): pass