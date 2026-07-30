import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

from strategy.models import StrategyDefinition, StrategyContext, StrategyStatus, StrategyHealth
from strategy.registry import StrategyRegistry
from strategy.exceptions import (
    StrategyLoadError, StrategyExecutionError, 
    StrategyContextError, StrategyRuntimeUnavailableError
)
from skills.manager import SkillManager
from skills.pipeline import SkillPipeline
from skills.context import SkillContext

# Forward declarations for Phase 3 integration
# from core.compiler import IntelligenceCompiler


class StrategyRuntime:
    """Orchestrator for Strategy Execution. No trading logic here."""

    def __init__(self, skill_manager: SkillManager, 
                 compiler: Any, # Phase 3 Intelligence Compiler
                 registry: Optional[StrategyRegistry] = None):
        self._skill_manager = skill_manager
        self._compiler = compiler
        self._registry = registry or StrategyRegistry()
        self._active_strategy_id: Optional[str] = None
        self._execution_count = 0
        self._total_runtime_ms = 0.0
        self._last_execution: Optional[datetime] = None
        self._status = "CREATED"
        self._publish_fn: Optional[Callable] = None

    def initialize(self) -> None:
        self._status = "INITIALIZED"

    def set_publish_fn(self, fn: Callable) -> None:
        self._publish_fn = fn

    def load_strategy(self, strategy_id: str) -> None:
        defn = self._registry.get_definition(strategy_id)
        if not defn:
            raise StrategyLoadError(f"Strategy {strategy_id} not registered")
        self._registry.set_status(strategy_id, StrategyStatus.LOADED)

    def activate_strategy(self, strategy_id: str) -> None:
        if self._registry.get_status(strategy_id) != StrategyStatus.LOADED:
            self.load_strategy(strategy_id)
        self._active_strategy_id = strategy_id
        self._registry.set_status(strategy_id, StrategyStatus.READY)

    def deactivate_strategy(self, strategy_id: str) -> None:
        if self._active_strategy_id == strategy_id:
            self._active_strategy_id = None
        self._registry.set_status(strategy_id, StrategyStatus.STOPPED)

    def execute(self, market_snapshot: Dict[str, Any], 
                memory_context: Dict[str, Any]) -> Any:
        """Main execution loop: Skills -> Context -> Compiler -> Decision."""
        if not self._active_strategy_id:
            return None

        start_time = time.time()
        strategy_id = self._active_strategy_id
        defn = self._registry.get_definition(strategy_id)
        self._registry.set_status(strategy_id, StrategyStatus.RUNNING)

        try:
            # 1. Pipeline Execution (Phase 4.8)
            pipeline = SkillPipeline(self._skill_manager)
            for skill_name in defn.required_skills:
                pipeline.add_step(skill_name)
            
            skill_ctx = SkillContext(market_snapshot=market_snapshot, memory_context=memory_context)
            skill_results = pipeline.execute(skill_ctx)

            # 2. Context Building
            strat_ctx = StrategyContext(
                market_context=market_snapshot,
                memory_context=memory_context,
                runtime_context={},
                skill_outputs=skill_results,
                execution_metadata={"strategy_id": strategy_id, "version": defn.version}
            )

            # 3. Intelligence Compiler Invocation (Phase 3)
            # Invoke the existing Phase 3 compiler logic
            decision_contract = self._compiler.compile(strat_ctx)

            # Update stats
            exec_ms = (time.time() - start_time) * 1000
            self._execution_count += 1
            self._total_runtime_ms += exec_ms
            self._last_execution = datetime.now(timezone.utc)
            self._registry.set_status(strategy_id, StrategyStatus.READY)

            if self._publish_fn:
                self._publish_fn("DECISION_RECEIVED", {"strategy_id": strategy_id, "decision": decision_contract})

            return decision_contract

        except Exception as e:
            self._registry.set_status(strategy_id, StrategyStatus.FAILED)
            if self._publish_fn:
                self._publish_fn("STRATEGY_FAILED", {"strategy_id": strategy_id, "error": str(e)})
            raise StrategyExecutionError(f"Strategy execution failed: {e}") from e

    def health_check(self) -> StrategyHealth:
        avg = self._total_runtime_ms / self._execution_count if self._execution_count > 0 else 0.0
        return StrategyHealth(
            active_strategy=self._active_strategy_id,
            loaded_strategies=self._registry.list_strategies(),
            execution_count=self._execution_count,
            average_runtime_ms=avg,
            last_execution=self._last_execution,
            status=self._status
        )
