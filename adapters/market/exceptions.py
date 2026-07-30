"""Market data exceptions — framework only."""
from adapters.exceptions import AdapterError

class MarketConnectionError(AdapterError): pass
class SubscriptionError(AdapterError): pass
class DataUnavailableError(AdapterError): pass
class InvalidSymbolError(AdapterError): pass
class MarketTimeoutError(AdapterError): pass