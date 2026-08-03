"""Strategy Manager — discover, load, lifecycle, metrics for all strategies."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type, Any
from datetime import datetime
import logging

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy_manager.metrics import StrategyMetrics

logger = logging.getLogger("StrategyManager")


class StrategyManager:
    """Single gateway for all strategy lifecycle operations.

    Runtime NEVER instantiates strategies directly.
    All access goes through this manager.
    """

    _instance: Optional["StrategyManager"] = None

    def __init__(self):
        self._registry: Dict[str, BaseStrategy] = {}
        self._metrics: Dict[str, StrategyMetrics] = {}
        self._enabled: Dict[str, bool] = {}

    @classmethod
    def instance(cls) -> "StrategyManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Registration ──────────────────────────────────────────────────────
    def register(self, strategy: BaseStrategy) -> None:
        sid = strategy.id
        if sid in self._registry:
            logger.warning("Strategy %s already registered — skipping", sid)
            return
        strategy.initialize()
        self._registry[sid] = strategy
        self._metrics[sid] = StrategyMetrics(strategy_id=sid)
        self._enabled[sid] = strategy.enabled
        logger.info("Registered strategy %s v%s", strategy.name, strategy.version)

    def unregister(self, strategy_id: str) -> None:
        if strategy_id not in self._registry:
            return
        self._registry[strategy_id].shutdown()
        del self._registry[strategy_id]
        del self._metrics[strategy_id]
        del self._enabled[strategy_id]
        logger.info("Unregistered strategy %s", strategy_id)

    # ── Load / Reload ─────────────────────────────────────────────────────
    def load(self, strategy_class: Type[BaseStrategy]) -> str:
        """Instantiate + register. Returns strategy_id."""
        instance = strategy_class()
        self.register(instance)
        return instance.id

    def reload(self, strategy_id: str) -> None:
        """Shutdown + re-initialize in-place (preserves metrics)."""
        if strategy_id not in self._registry:
            raise KeyError(f"Strategy {strategy_id} not found")
        strategy = self._registry[strategy_id]
        strategy.shutdown()
        strategy.initialize()
        logger.info("Reloaded strategy %s", strategy_id)

    # ── Enable / Disable ──────────────────────────────────────────────────
    def enable(self, strategy_id: str) -> None:
        self._enabled[strategy_id] = True

    def disable(self, strategy_id: str) -> None:
        self._enabled[strategy_id] = False

    # ── Query ─────────────────────────────────────────────────────────────
    def get(self, strategy_id: str) -> Optional[BaseStrategy]:
        return self._registry.get(strategy_id)

    def list(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        result = []
        for sid, strategy in sorted(self._registry.items(), key=lambda x: -x[1].priority):
            if enabled_only and not self._enabled.get(sid, False):
                continue
            result.append({
                "id": sid,
                "name": strategy.name,
                "version": strategy.version,
                "priority": strategy.priority,
                "enabled": self._enabled.get(sid, False),
            })
        return result

    # ── Execute ───────────────────────────────────────────────────────────
    def run_all(self, context: StrategyContext) -> List[StrategyResult]:
        """Run all strategies, reloaded enabled status from disk every loop."""
        import json
        try:
            with open("/home/ubuntu/trading-intelligence-engine/config/strategy_status.json") as f:
                self._enabled = json.load(f)
        except Exception as e:
            logger.warning("Failed to reload status: %s", e)

        # Load per-symbol toggle config
        _sym_status = {}
        try:
            with open("/home/ubuntu/trading-intelligence-engine/config/symbol_status.json") as f:
                _sym_status = json.load(f)
        except Exception:
            pass

        results = []
        sym = context.scan.market.symbol.upper() if context.scan and context.scan.market else ""
        for sid, strategy in sorted(self._registry.items(), key=lambda x: -x[1].priority):
            if not self._enabled.get(sid, True):
                continue

            # Per-symbol toggle check
            if sym and sid in _sym_status:
                if not _sym_status[sid].get(sym, True):
                    logger.info("Strategy %s skipped for symbol %s (disabled)", sid, sym)
                    continue

            meta = getattr(strategy, "metadata", None)
            supported = getattr(meta, "supported_symbols", None)
            if supported and sym and sym not in [s.upper() for s in supported]:
                continue
            
            try:
                result = strategy.analyze(context)
                if result:
                    self._metrics[sid].record(result)
                    results.append(result)
                    if result.signal is None:
                        logger.info("Strategy %s returned WAIT: %s", sid, result.reason)
            except Exception as e:
                logger.error("Strategy %s failed: %s", sid, e)
        return results

    # ── Health ────────────────────────────────────────────────────────────
    def health(self) -> Dict[str, Any]:
        return {
            sid: {
                "enabled": self._enabled.get(sid, False),
                "registered": True,
                "metrics": self._metrics[sid].summary(),
            }
            for sid in self._registry
        }

    def metrics(self, strategy_id: Optional[str] = None) -> Any:
        if strategy_id:
            return self._metrics.get(strategy_id, {})
        return {sid: m.summary() for sid, m in self._metrics.items()}
