"""Risk layer exceptions — specific to risk evaluation."""
class RiskError(Exception): pass
class RiskEvaluationError(RiskError): pass
class PolicyExecutionError(RiskError): pass
class ConfigurationError(RiskError): pass
class RiskEngineUnavailableError(RiskError): pass
