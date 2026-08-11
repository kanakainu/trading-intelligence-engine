"""RiriMicroScalpEngine (RME) — engine-centric, score-based. No detector chains."""
import logging
import uuid
import json
import os
from datetime import datetime
from typing import Optional

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.signals.signal import Signal, Direction
from core.lifecycle.lifecycle_models import PositionSnapshot
from core.learning.learning_models import TradeReflection, TradeOutcome

from strategies.aggressive.metadata import AGGRESSIVE_METADATA
from strategies.aggressive.governor.daily_governor import DailyProfitGovernor
from strategies.aggressive.exits import evaluate_exit, ExitDecision
from strategies.aggressive.metrics.metrics_logger import MetricsLogger
from strategies.aggressive.cooldown.cooldown_engine import AdaptiveCooldown

# RME Score Engines (R1-R3)
from strategies.aggressive.market_snapshot import snapshot as get_snapshot
from strategies.aggressive.opportunity_window import get_session_score
from strategies.aggressive.momentum_engine import calculate_score as calc_momentum_score
from strategies.aggressive.velocity_engine import calculate_score as calc_velocity_score
from strategies.aggressive.microstructure_engine import calculate_score as calc_micro_score
from strategies.aggressive.liquidity_engine import calculate_score as calc_liquidity_score
from strategies.aggressive.vwap_context_engine import calculate_score as calc_vwap_score
from strategies.aggressive.entry_score_engine import calculate as entry_score, EntryScore

# Riri's Nexus + XAU-60 Guards
from strategies.aggressive.fvg_detector import get_active_fvgs
from strategies.aggressive.trendline_detector import detect_trendline_break
from strategies.aggressive.liquidity_vacuum import detect_liquidity_pools, vacuum_grade

logger = logging.getLogger(__name__)

def check_news_blackout() -> tuple[bool, str]:
    """Check if a news blackout is active from the local sentinel file."""
    path = "/tmp/tie_news_blackout.json"
    if not os.path.exists(path):
        return False, ""
    try:
        with open(path, "r") as f:
            data = json.load(f)
            if data.get("active"):
                return True, "; ".join(data.get("reasons", []))
    except:
        pass
    return False, ""

class RiriMicroScalpEngine(BaseStrategy):
    """RME — Riri MicroScalp Engine. Score-based, no gate stacking."""

    def __init__(self):
        super().__init__(AGGRESSIVE_METADATA)
        self._governor = DailyProfitGovernor()
        self._cooldown = AdaptiveCooldown()
        self._metrics = MetricsLogger()

    def initialize(self) -> None:
        self._initialized = True
        logger.info("RiriMicroScalpEngine (RME) initialized — score-based pipeline")

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        features = context.scan.features
        if not features:
            return StrategyResult(signal=None, confidence=0.0, reason="no_features")

        # --- Data prep ---
        candles_m5 = features.candles.get("M5", [])
        candles_m1 = features.candles.get("M1", [])
        spread    = features.spread if isinstance(features.spread, float) else 0.0
        atr       = features.get_atr("M5") or 0.0 # Aggressive uses M5 ATR
        vol_ratio = features.volume_ratio.get("M5", 1.0)
        price = getattr(features, "current_price", None) or context.scan.current_price or 0.0
        vwap      = features.vwap.get("M5") if hasattr(features.vwap, "get") else None
        utc_h     = getattr(features.timestamp, "hour", datetime.utcnow().hour)

        # --- Score all engines (parallel, no gates) ---
        snap    = get_snapshot(candles_m5)
        sess    = get_session_score(utc_h)
        mom     = calc_momentum_score(candles_m5)
        vel     = calc_velocity_score(candles_m5, atr)
        micro   = calc_micro_score(candles_m5, atr)
        liq     = calc_liquidity_score(vol_ratio)
        vwap_sc = calc_vwap_score(price, vwap)
        trend   = (sess * 0.5 + snap.momentum_score * 0.5)  # composite trend score

        # --- Determine direction from snapshot ---
        direction = snap.state  # "BULL"→BUY, "BEAR"→SELL, "FLAT"→NONE
        if direction == "BULL":   direction = "BUY"
        elif direction == "BEAR": direction = "SELL"
        else:                     direction = "NONE"

        # --- NEXUS TWEAK: Debate Logic (Conflict Detection) ---
        # Use M5 trend as counter-bias indicator
        counter_bias = 50.0
        if snap:
            m5_mom = snap.momentum_score # Composite trend from M5
            if direction == "BUY" and m5_mom < 40: # Weak/Bearish M5 trend for BUY
                counter_bias = (40 - m5_mom) * 2 + 50
            elif direction == "SELL" and m5_mom > 60: # Weak/Bullish M5 trend for SELL
                counter_bias = (m5_mom - 60) * 2 + 50

        # --- EntryScore aggregator — liquidity/vwap dropped from weights ---
        es = entry_score(
            momentum_score=mom,
            velocity_score=vel,
            micro_score=micro,
            liquidity_score=0.0,
            vwap_score=0.0,
            trend_score=trend,
            direction=direction,
            counter_bias_score=counter_bias,
        )

        # --- Riri's Nexus + XAU-60 Guards (Aggressive Mode) ---

        # 1. Governor (only hard gate)
        gov = self._governor.get_status()
        if gov["halted"]:
            return StrategyResult(signal=None, confidence=0.0, reason=f"gov:{gov['reason']}", metadata={"score": es.score})

        # 1b. News Sentinel Gate (Nexus-style)
        is_blackout, blackout_reason = check_news_blackout()
        if is_blackout:
            logger.warning(f"NEWS BLACKOUT ACTIVE: {blackout_reason}")
            return StrategyResult(signal=None, confidence=0.0, reason=f"news_blackout:{blackout_reason[:20]}", metadata={"score": es.score})

        # 2. Cooldown (soft guard) — quality-based: pass M5 candles for recovery check
        if not self._cooldown.can_trade(m5_candles=features.candles.get("M5", [])):
            return StrategyResult(signal=None, confidence=0.0, reason=f"cooldown:{int(self._cooldown.remaining())}s", metadata={"score": es.score})

        # 3. FVG Magnet Awareness (Research Mode - M5 only)
        if features and features.candles:
            fvgs = get_active_fvgs(features.candles, tfs=["M5"])
            for tf, fvg_list in fvgs.items():
                for fvg in fvg_list[-1:]:  # Only log latest FVG per TF
                    logger.info(f"[FVG_MAGNET] {tf} {fvg['type']} at {fvg['bottom']:.2f}-{fvg['top']:.2f} | Midpoint: {fvg['midpoint']:.2f}")

        # 4. Trendline Guard (XAU-60 Logic - M5 only)
        if features.candles:
            m5_df = features.candles.get("M5", [])
            if m5_df and atr > 0:
                is_tl_break, tl_dir = detect_trendline_break(m5_df, atr=atr)  # Pass ATR for adaptive pivot
                if not is_tl_break or tl_dir != direction:
                    return StrategyResult(signal=None, confidence=0.0,
                                          reason=f"tl_guard:NO_{direction}_BREAK",
                                          metadata={"score": es.score})

        # 5. Liquidity Vacuum Guard (Smart Money - M5 only)
        liq_vac = {"grade": "GOOD", "reason": "no_pool_data", "tf": "-"}
        if features and features.candles:
            candles = features.candles.get("M5", [])
            if candles and atr > 0:
                pools = detect_liquidity_pools(candles, atr)
                if pools["nearest_above"] or pools["nearest_below"]:
                    grade, reason = vacuum_grade(
                        pools["nearest_above"], pools["nearest_below"], direction, atr)
                    liq_vac = {"grade": grade, "reason": reason, "tf": "M5"}
                    if grade == "DANGER":
                        # Hard stop for aggressive if danger found
                        return StrategyResult(signal=None, confidence=0.0,
                                              reason=f"liq_vacuum:{liq_vac['reason']}",
                                              metadata={"score": es.score, "liq_vac": liq_vac["reason"]})
        logger.info(f"[LIQ_VACUUM] {liq_vac['grade']} {liq_vac['reason']} dir={direction}")

        # 7. Final Entry Score Check (after all guards)
        if not es.entry_ok:
            return StrategyResult(signal=None, confidence=0.0, reason=f"rme:{es.reason}",
                                  metadata={"score": es.score, "momentum": mom, "velocity": vel,
                                            "micro": micro, "liquidity": liq, "vwap": vwap_sc, "trend": trend})

        if price <= 0:
            return StrategyResult(signal=None, confidence=0.0, reason="price_zero",
                                  metadata={"score": es.score})

        # 8. Signal
        sig = Signal(
            signal_id=str(uuid.uuid4())[:8],
            strategy=self.id,
            symbol=features.symbol,
            direction=Direction.BUY if direction == "BUY" else Direction.SELL,
            timeframe="M5",
            confidence=es.score,
            entry_zone={"low": price, "high": price},
            quality_score=es.score,
            metadata={
                "score": es.score, "momentum": mom, "velocity": vel,
                "micro": micro, "liquidity": liq, "vwap": vwap_sc,
                "trend": trend, "session": sess, "state": snap.state,
                "liq_vacuum_grade": liq_vac['grade'], "liq_vacuum_reason": liq_vac['reason'],
            }
        )
        logger.info(f"RME {direction} score={es.score:.1f} sym={features.symbol} liq_vac={liq_vac['grade']}")
        return StrategyResult(
            signal=sig,
            confidence=es.score,
            reason=f"rme_score:{es.score:.1f}",
            metadata={
                "score": es.score,
                "momentum": mom,
                "velocity": vel,
                "micro": micro,
                "liquidity": liq,
                "vwap": vwap_sc,
                "trend": trend,
                "liq_vac": liq_vac['reason'], # Add to top-level metadata
            }
        )

    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        features = context.scan.features
        if not features: return None
        pos_dict = {
            "entry_price":   position.entry_price,
            "current_price": position.current_price,
            "direction":     str(position.direction.value if hasattr(position.direction, "value") else position.direction),
            "entry_time":    position.opened_at.timestamp() if position.opened_at else 0,
        }
        exit_eval = evaluate_exit(features, pos_dict)
        if exit_eval.decision == ExitDecision.HOLD: return None
        return StrategyResult(signal=None, confidence=exit_eval.urgency, reason=f"exit:{exit_eval.reason}")

    def learn(self, reflection: TradeReflection) -> None:
        won = reflection.outcome == TradeOutcome.WIN
        pnl = getattr(reflection, "realized_pl", 0.0) or 0.0
        self._governor.record_trade(pnl)
        direction = getattr(reflection, "direction", None) or getattr(reflection, "signal_direction", None)
        self._cooldown.record_trade(won, direction=str(direction).upper() if direction else None)
        self._metrics.record(
            entry_time=reflection.entry_time.timestamp() if reflection.entry_time else 0,
            exit_time=reflection.exit_time.timestamp() if reflection.exit_time else 0,
            pnl=pnl,
            exit_reason=str(reflection.exit_reason.value if hasattr(reflection.exit_reason, "value") else reflection.exit_reason),
            symbol=reflection.symbol
        )

    def shutdown(self) -> None:
        self._initialized = False

# Backward compat alias
AggressiveStrategy = RiriMicroScalpEngine
