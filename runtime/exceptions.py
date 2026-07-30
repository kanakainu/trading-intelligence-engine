"""Runtime exceptions — orchestration layer only."""
class RuntimeError(Exception): pass
class RuntimeInitializationError(RuntimeError): pass
class PipelineExecutionError(RuntimeError): pass
class ContextBuildError(RuntimeError): pass
class DispatcherError(RuntimeError): pass
class RuntimeStateError(RuntimeError): pass
