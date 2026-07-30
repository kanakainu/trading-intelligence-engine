"""Broker-specific exceptions."""
from adapters.exceptions import AdapterError


class BrokerConnectionError(AdapterError): pass
class OrderRejectedError(AdapterError): pass
class InsufficientMarginError(AdapterError): pass
class SymbolNotFoundError(AdapterError): pass
class BrokerTimeoutError(AdapterError): pass
