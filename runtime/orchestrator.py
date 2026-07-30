"""Pipeline Orchestrator — coordinates Phase 3 components. No trading logic."""
import uuid, time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from runtime.events import RuntimeEvent, EventType
from runtime.context_builder import ExecutionContext
from runtime.dispatcher import Dispatcher
from runtime.exceptions import PipelineExecutionError, ContextBuildError


class PipelineOrchestrator:
    """
    Orchestrates: Market → Context → Fact Compiler → Reasoning → Decision → Execution Contract.
    Does NOT own any Phase 3 logic — only calls them.
    """

    def __init__(self, dispatcher: Dispatcher):
        self._dispatcher = dispatcher
        self._steps: List[Callable] = []
        self._active = False

    def register_step(self, fn: Callable[[ExecutionContext], ExecutionContext]) -> None:
        self._steps.append(fn)

    def execute(self, initial_ctx: ExecutionContext) -> ExecutionContext:
        if not self._active:
            raise PipelineExecutionError("Pipeline not started")
        ctx = initial_ctx
        ctx.execution_id = ctx.execution_id or str(uuid.uuid4())[:12]
        start = time.time()
        try:
            for i, step in enumerate(self._steps):
                ctx = step(ctx)
                self._dispatcher.publish(RuntimeEvent(
                    event_type=EventType.RUNTIME_WARNING if i == len(self._steps)-1 else EventType.FACTS_COMPILED,
                    payload={"step": i, "execution_id": ctx.execution_id},
                    execution_id=ctx.execution_id,
                ))
            duration = time.time() - start
            self._dispatcher.publish(RuntimeEvent(
                event_type=EventType.EXECUTION_CONTRACT_CREATED,
                payload={"execution_id": ctx.execution_id, "duration_ms": duration*1000},
                execution_id=ctx.execution_id,
            ))
            return ctx
        except Exception as e:
            self._dispatcher.publish(RuntimeEvent(
                event_type=EventType.RUNTIME_ERROR,
                payload={"error": str(e), "execution_id": ctx.execution_id},
                execution_id=ctx.execution_id,
            ))
            raise PipelineExecutionError(f"Pipeline failed: {e}") from e

    def start(self): self._active = True
    def stop(self): self._active = False
