"""Adapter exceptions — framework only, no broker logic."""


class AdapterError(Exception):
    pass

class ConnectionError(AdapterError):
    pass

class AuthenticationError(AdapterError):
    pass

class UnsupportedCapabilityError(AdapterError):
    pass

class AdapterTimeoutError(AdapterError):
    pass
