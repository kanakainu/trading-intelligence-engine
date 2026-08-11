"""Multi Strategy Runtime — replaces detector-direct pipeline.

Pipeline:
    ScanContext → StrategyManager.run_all() → FusionEngine → TradePlanner → Risk → Entry

Runtime knows ONLY BaseStrategy interface. Zero detector imports.
"""
from __future__ import annotations
import logging
import time
import uuid
from typing import List, Optional

from core.context.scan_context import ScanContext
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy_manager.manager import StrategyManager
from core.fusion.fusion_engine import SignalFusion as FusionEngine
from core.fusion.fusion_models import FusionInputs
from core.signals.signal import Signal
from core.planner.trade_planner import TradePlanner
from core.planner.planner_models import TradePlan, PlannerInputs

logger = logging.getLogger("MultiStrategyRuntime")


class MultiStrategyRuntime:
    """Single scan loop. Runs all active strategies, fuses signals, plans trade."""

    def __init__(self, manager: StrategyManager):
        self._manager = manager
        self._fusion = FusionEngine()
        self._planner = TradePlanner()

    def scan(self, scan_ctx: ScanContext) -> Optional[TradePlan]:
        """Full scan cycle. Returns TradePlan or None."""
        t0 = time.perf_counter()

        # 1. Wrap into StrategyContext
        ctx = StrategyContext(scan=scan_ctx)

        # 2. Run all enabled strategies via manager
        results: List[StrategyResult] = self._manager.run_all(ctx)
        if not results:
            return None

        # 3. Collect valid signals
        signals: List[Signal] = [r.signal for r in results if r.signal is not None]
        if not signals:
            return None

        # 4. Fuse signals
        scan_id = str(uuid.uuid4())
        fusion_inputs = FusionInputs(
            signals=signals,
            symbol=scan_ctx.market.symbol,
            scan_id=scan_id,
        )
        fused = self._fusion.fuse(fusion_inputs)
        if not fused or fused.decision.value in ("conflict", "no_signals"):
            return None

        # Build strategy code prefix for comment
        strategy_codes = {"bystra": "B", "aggressive": "A", "semi_hft": "S"}
        contributing = [s.strategy.split("_")[0] for s in signals if s.direction.value.lower() == fused.direction]
        code_str = "".join(sorted([strategy_codes.get(s, s[0].upper()) for s in contributing]))
        
        # Pick best source for metadata
        best_src = next(
            (s for s in signals if s.direction.value.lower() == fused.direction),
            signals[0]
        )
        md = best_src.metadata or {}

        # 5. Plan trade
        planner_inputs = PlannerInputs(
            symbol=fused.symbol,
            direction=fused.direction.upper(),
            entry_zone=fused.entry_zone,
            confidence=fused.confidence,
            strategies=fused.strategies,
            timeframe=best_src.timeframe,
            h1_support=scan_ctx.h1_support,
            h1_resistance=scan_ctx.h1_resistance,
            detector_danger_zone=md.get("danger_zone"),
            detector_sl=md.get("sl"),
            candles=scan_ctx.market.metadata.get("candles", {}),
            scan_id=scan_id,
            balance=getattr(scan_ctx.market, "balance", 1000.0),
            risk_per_trade_pct=2.0,  # was 1.0 — more aggressive sizing
        )
        plan = self._planner.plan(planner_inputs)
        
        # Inject strategy code into metadata for order comment
        if plan and plan.metadata is None:
            object.__setattr__(plan, 'metadata', {})
        if plan:
            plan.metadata['strategy_code'] = code_str  # B, BA, BAS

        dt = (time.perf_counter() - t0) * 1000
        logger.info(
            "Scan %.1fms — strategies=%d signals=%d dir=%s source=%s",
            dt, len(results), len(signals), fused.direction, best_src.strategy,
        )
        return plan

    def register(self, strategy_class) -> str:
        """Load + register strategy. Returns strategy_id."""
        return self._manager.load(strategy_class)
