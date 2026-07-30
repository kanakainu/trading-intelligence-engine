"""ExecutionService — orchestrates execution pipeline end-to-end.
Phase 6.2: HCK Bridge wired — write episode after trade, inject goals into risk context.
"""
from typing import Any, Callable, List, Optional
from core.execution.execution_contract import ExecutionContract
from core.rules.plugins.plugin_registry import PluginRegistry
from core.rules.plugins.plugin_loader import PluginLoader
from runtime.execution_runtime import ExecutionRuntime
from runtime.execution_result import ExecutionResult
from runtime.runtime_logger import RuntimeLogger


class ExecutionService:
    """
    Full execution pipeline:
    1. Build risk context (optionally enriched with HCK goals)
    2. Run risk plugins (gate)
    3. If APPROVE → ExecutionRuntime.execute()
    4. If FILLED → write episode to HCK
    5. Return ExecutionResult
    """

    def __init__(self, execution_runtime: ExecutionRuntime,
                 risk_registry: Optional[PluginRegistry] = None,
                 logger: Optional[RuntimeLogger] = None,
                 hck_bridge: Any = None):
        self._runtime = execution_runtime
        self._risk_loader = PluginLoader(risk_registry) if risk_registry else None
        self._log = logger or RuntimeLogger()
        self._hck: Any = hck_bridge  # Phase 6.2: optional HCKBridge

    def submit(self, contract: ExecutionContract,
               context: dict = None, facts: dict = None) -> ExecutionResult:
        ctx = context or {}
        facts = facts or {}
        canonical_id = ctx.get("canonical_id") or contract.metadata.get("canonical_id", "system")

        # ── Phase 6.2: enrich context with HCK goals ──────────────────────
        if self._hck:
            try:
                goals = self._hck.get_goals(canonical_id)
                if goals:
                    ctx["hck_goals"] = goals
                    # Extract daily target from goals if present
                    for g in goals:
                        content = g.get("content", "")
                        if "daily_target" in content.lower():
                            ctx.setdefault("daily_target_from_hck", content)
            except Exception as e:
                self._log.log_error(contract.contract_id, f"HCK goal fetch failed: {e}")
        # ──────────────────────────────────────────────────────────────────

        # 1. Risk gate
        if self._risk_loader:
            results = self._risk_loader.run_all(ctx, facts, decision=None)
            for r in results:
                if r.status == "REJECT":
                    self._log.log_order_rejected(contract.contract_id, r.reason)
                    return ExecutionResult(
                        success=False,
                        contract_id=contract.contract_id,
                        status="RISK_REJECTED",
                        error=r.reason,
                    )

        # 2. Execute
        result = self._runtime.execute(contract)

        # ── Phase 6.2: write episode to HCK after filled ──────────────────
        if self._hck and result.success and result.status == "FILLED":
            try:
                user_msg = (
                    f"Trade: {contract.direction} {contract.symbol} "
                    f"entry={contract.entry} sl={contract.sl} tp={contract.tp} "
                    f"setup={contract.setup} conf={contract.confidence:.0%}"
                )
                bot_reply = (
                    f"Executed: order_id={result.order_id} "
                    f"filled_price={result.filled_price} "
                    f"filled_volume={result.filled_volume}"
                )
                self._hck.write_episode(canonical_id, user_msg, bot_reply,
                                        metadata={"contract_id": contract.contract_id,
                                                  "symbol": contract.symbol})
                self._hck.publish_event("TRADE_EXECUTED", {
                    "canonical_id": canonical_id,
                    "contract_id": contract.contract_id,
                    "symbol": contract.symbol,
                    "direction": contract.direction,
                    "filled_price": result.filled_price,
                })
            except Exception as e:
                self._log.log_error(contract.contract_id, f"HCK episode write failed: {e}")
        # ──────────────────────────────────────────────────────────────────

        return result
