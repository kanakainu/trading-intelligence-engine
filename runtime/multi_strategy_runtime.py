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
        strategy_codes = {"bystra": "B", "three_ca": "T", "riri_scalps": "R", "aggressive": "A", "semi_hft": "S"}
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
        
        # Inject metadata into TradePlan for Order Comment/Monitor
        if plan:
            if plan.metadata is None:
                object.__setattr__(plan, 'metadata', {})
            # Prefer engine-level code emitted by strategy (F, A, C, D, E1, E2, 3Ca)
            # so order comment shows WHICH engine fired, not just the strategy family
            plan.metadata['strategy_code'] = md.get("strategy_code") or code_str
            plan.metadata['cutloss'] = md.get("cutloss") # 3Ca smart cutloss
            plan.metadata['setup_type'] = md.get("setup_type")
            plan.metadata['volume'] = md.get("volume") # preserve strategy volume
            plan.metadata['nyao_score'] = md.get("nyao_score")  # dampener penalty math
            plan.metadata['nyao_thr'] = md.get("nyao_thr")
            # [V-SLBOS 11-Sep] bawa SL/TP JANGKAR strategi asli: planner pernah
            # nge-override SL clamp $2.5 -> swing H1 $9.6 (log 14:35). Runtime wajib restore.
            plan.metadata['strategy_sl'] = md.get('sl')
            plan.metadata['strategy_tp'] = md.get('take_profit')
            plan.metadata['emit_price'] = md.get('emit_price')

        dt = (time.perf_counter() - t0) * 1000
        logger.info(
            "Scan %.1fms — strategies=%d signals=%d dir=%s source=%s",
            dt, len(results), len(signals), fused.direction, best_src.strategy,
        )
        return plan

    def register(self, strategy_class) -> str:
        """Load + register strategy. Returns strategy_id."""
        return self._manager.load(strategy_class)
