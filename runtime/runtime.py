"""Intelligence Runtime — main orchestration layer. Event-driven, modular."""
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from runtime.state import RuntimeState
from runtime.events import RuntimeEvent, EventType
from runtime.dispatcher import Dispatcher
from runtime.orchestrator import PipelineOrchestrator
from runtime.context_builder import ExecutionContext
from runtime.health import RuntimeHealth
from runtime.registry import ComponentRegistry
from runtime.exceptions import RuntimeInitializationError, RuntimeStateError
from runtime.compiler_bridge import CompilerBridge


class IntelligenceRuntime:
    """
    Main runtime orchestrator. Coordinates adapters, Phase 3 compiler, memory, events.
    Owns NO trading logic. Pure orchestration.
    """

    def __init__(self, setup_definitions: list = None):
        self._state = RuntimeState.CREATED
        self._start_time: Optional[float] = None
        self._dispatcher = Dispatcher()
        self._orchestrator = PipelineOrchestrator(self._dispatcher)
        self._registry = ComponentRegistry()
        self._context_builders: List[Callable] = []
        self._processed_events = 0
        self._last_error: Optional[str] = None
        self._compiler_bridge: Optional[CompilerBridge] = (
            CompilerBridge(setup_definitions) if setup_definitions is not None else None
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def initialize(self) -> None:
        if self._state != RuntimeState.CREATED:
            raise RuntimeStateError(f"Cannot initialize from {self._state.value}")
        self._state = RuntimeState.INITIALIZED

    def start(self) -> None:
        if self._state not in (RuntimeState.INITIALIZED, RuntimeState.PAUSED):
            raise RuntimeStateError(f"Cannot start from {self._state.value}")
        self._orchestrator.start()
        self._start_time = time.time()
        self._state = RuntimeState.RUNNING
        self._dispatcher.publish(RuntimeEvent(event_type=EventType.RUNTIME_WARNING,
                                              payload={"msg": "Runtime started"}))

    def pause(self) -> None:
        if self._state != RuntimeState.RUNNING:
            raise RuntimeStateError(f"Cannot pause from {self._state.value}")
        self._orchestrator.stop()
        self._state = RuntimeState.PAUSED

    def resume(self) -> None:
        if self._state != RuntimeState.PAUSED:
            raise RuntimeStateError(f"Cannot resume from {self._state.value}")
        self._orchestrator.start()
        self._state = RuntimeState.RUNNING

    def stop(self) -> None:
        if self._state not in (RuntimeState.RUNNING, RuntimeState.PAUSED):
            raise RuntimeStateError(f"Cannot stop from {self._state.value}")
        self._orchestrator.stop()
        self._state = RuntimeState.STOPPED

    def shutdown(self) -> None:
        self.stop()
        self._dispatcher.clear()
        self._registry = ComponentRegistry()
        self._state = RuntimeState.SHUTDOWN

    # ── Context Building ───────────────────────────────────────────────────
    def add_context_builder(self, fn: Callable[[Dict], ExecutionContext]) -> None:
        self._context_builders.append(fn)

    def build_context(self, market_data: Dict, memory_data: Dict,
                      runtime_meta: Dict) -> ExecutionContext:
        ctx = ExecutionContext(market=market_data, memory=memory_data,
                               runtime=runtime_meta)
        for builder in self._context_builders:
            ctx = builder(ctx)
        self._dispatcher.publish(RuntimeEvent(event_type=EventType.CONTEXT_READY,
                                              payload={"execution_id": ctx.execution_id}))
        return ctx

    # ── Pipeline Execution ─────────────────────────────────────────────────
    def register_pipeline_step(self, fn: Callable[[ExecutionContext], ExecutionContext]) -> None:
        self._orchestrator.register_step(fn)

    def execute(self, ctx: ExecutionContext) -> ExecutionContext:
        if self._state != RuntimeState.RUNNING:
            raise RuntimeStateError(f"Runtime must be RUNNING, got {self._state.value}")
        try:
            result = self._orchestrator.execute(ctx)
            self._processed_events += 1
            return result
        except Exception as e:
            self._last_error = str(e)
            raise

    def compile(self, ctx: ExecutionContext):
        """Wire ExecutionContext → Phase 3 Intelligence Compiler → TradeDecision."""
        if not self._compiler_bridge:
            raise RuntimeStateError("No setup_definitions provided — CompilerBridge not initialised")
        return self._compiler_bridge.compile(ctx)

    # ── Event System ───────────────────────────────────────────────────────
    def subscribe(self, event_type: EventType, handler: Callable[[RuntimeEvent], None]) -> None:
        self._dispatcher.subscribe(event_type, handler)

    def publish(self, event: RuntimeEvent) -> None:
        self._dispatcher.publish(event)

    # ── Health & State ─────────────────────────────────────────────────────
    def get_state(self) -> RuntimeState:
        return self._state

    def health(self) -> RuntimeHealth:
        uptime = (time.time() - self._start_time) if self._start_time else 0.0
        return RuntimeHealth(
            runtime_status=self._state.value,
            adapters_status={},  # populated by adapter registry in Phase 4.6+
            compiler_status="READY" if self._orchestrator._active else "IDLE",
            memory_status="READY",
            active_pipeline="default" if self._orchestrator._active else None,
            uptime_seconds=uptime,
            last_error=self._last_error,
            processed_events=self._processed_events,
        )

    def register_component(self, name: str, component: Any) -> None:
        self._registry.register(name, component)

    def get_component(self, name: str):
        return self._registry.get(name)
