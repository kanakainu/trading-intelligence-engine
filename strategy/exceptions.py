class StrategyError(Exception): pass
class StrategyLoadError(StrategyError): pass
class StrategyExecutionError(StrategyError): pass
class StrategyContextError(StrategyError): pass
class StrategyRegistryError(StrategyError): pass
class StrategyRuntimeUnavailableError(StrategyError): pass
