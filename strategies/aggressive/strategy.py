"""
AggressiveStrategy (The Street Fighter v2.1)
Fokus: Momentum Spike M1 via SetupDetector (MOMENTUM_BREAK).
Gate: Z-Score Anti-Pucuk (fallback only).
"""
from typing import Any, Dict, List, Optional
import logging
import uuid
from datetime import datetime

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction
from shared.setup_detector import detect, SetupType, SetupDirection
from shared.market_context import build as build_market_ctx

logger = logging.getLogger("AggressiveStrategy")

class AggressiveStrategy(BaseStrategy):
    def __init__(self):
        meta = StrategyMetadata(
            id="aggressive_v1",
            name="Aggressive Momentum",
            version="2.1.0",
            priority=80,
            author="Sasa",
            description="Momentum Breakout via SetupDetector + Z-Score fallback."
        )
        super().__init__(meta)

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market
        candles_m1 = context.scan.features.candles.get("M1", [])
        candles_m5 = context.scan.features.candles.get("M5", [])
        candles_m15 = context.scan.features.candles.get("M15", [])
        
        if not candles_m1 or len(candles_m1) < 5:
            return StrategyResult(signal=None, confidence=0.0, reason="insufficient_m1_data")

        price = market_ctx.price
        z_score = market_ctx.vwap_z_score
        atr = market_ctx.atr

        # Initialize fallback vars
        vol_spike = False
        bypass_z_gate = False

        # Build shared MarketContext for SetupDetector
        _shared_ctx = build_market_ctx(
            candles_m15=candles_m15,
            candles_m5=candles_m5,
            candles_m1=candles_m1,
            current_price=price,
            atr_m5=atr,
        )

        # 1. TRY STRUCTURAL SETUP via SetupDetector (M5 context for structure)
        _setup = detect(
            ctx=_shared_ctx,
            candles_m5=candles_m5,
            candles_m1=candles_m1,
            current_price=price,
        )

        signal_dir = None
        reason = "no_setup"
        confidence = 0.0
        bypass_z_gate = False

        # Priority 1: MOMENTUM_BREAK (high confidence, bypass Z-gate)
        if _setup and _setup.type == SetupType.MOMENTUM_BREAK:
            if _setup.direction == SetupDirection.BUY:
                signal_dir = Direction.BUY
                reason = f"momentum_break_up_quality={_setup.quality:.2f}"
            elif _setup.direction == SetupDirection.SELL:
                signal_dir = Direction.SELL
                reason = f"momentum_break_down_quality={_setup.quality:.2f}"
            confidence = 0.85
            bypass_z_gate = True
            logger.info(f"[AGGR] MOMENTUM_BREAK: dir={_setup.direction} quality={_setup.quality:.2f} BYPASS Z-GATE")

        # Priority 2: Structural setups (TREND_PULLBACK, BREAKOUT_RETEST, LIQUIDITY_SWEEP, RANGE_EDGE)
        elif _setup and _setup.type != SetupType.NONE:
            _dir_str = "BUY" if _setup.direction == SetupDirection.BUY else "SELL"
            
            # === LOCATION ENGINE ===
            try:
                from shared.location_engine import evaluate as eval_location, LocationGrade
                _loc = eval_location(_dir_str, price, candles_m5, candles_m15, atr)
                if _loc.grade == LocationGrade.BAD:
                    logger.info(f"[AGGR] BLOCK: BAD Location ({_loc.reason})")
                    return StrategyResult(signal=None, confidence=0.0, reason=f"bad_location:{_loc.reason}")
            except Exception as e:
                logger.warning(f"[AGGR] LocationEngine error: {e}")
                _loc = None

            # === TRIGGER ENGINE (M1) ===
            try:
                from shared.trigger_engine import evaluate as eval_trigger, TriggerSignal
                _trig = eval_trigger(_dir_str, candles_m1, atr)
                if _trig.signal != TriggerSignal.ARMED:
                    logger.info(f"[AGGR] WAIT: No M1 Trigger ({_trig.reason})")
                    return StrategyResult(signal=None, confidence=0.0, reason=f"no_trigger:{_trig.reason}")
            except Exception as e:
                logger.warning(f"[AGGR] TriggerEngine error: {e}")
                _trig = None

            # === TELEMETRY ===
            try:
                from shared.entry_telemetry import log_candidate, CandidateRecord
                log_candidate(CandidateRecord(
                    strategy="Aggressive",
                    symbol="XAUUSD",
                    direction=_dir_str,
                    regime=str(getattr(_shared_ctx, "regime", "UNKNOWN")),
                    setup_type=_setup.type.value,
                    location_grade=str(_loc.grade.name) if _loc else "UNKNOWN",
                    location_score=_loc.score if _loc else 0.0,
                    vwap_dist_atr=getattr(_shared_ctx, "vwap_distance_atr", 0.0),
                    available_room_atr=_loc.available_room_atr if _loc else 0.0,
                    trigger_signal=str(_trig.signal.name) if _trig else "UNKNOWN",
                    trigger_strength=_trig.strength if _trig else 0.0,
                    setup_quality=_setup.quality,
                    entry_price=price,
                    decision="ENTRY"
                ))
            except Exception as e:
                logger.warning(f"[AGGR] Telemetry error: {e}")

            signal_dir = Direction.BUY if _setup.direction == SetupDirection.BUY else Direction.SELL
            reason = f"{_setup.type.value}_{_dir_str.lower()}_quality={_setup.quality:.2f}"
            confidence = min(0.8, _setup.quality / 100.0)
            logger.info(f"[AGGR] STRUCTURAL: {_setup.type.value} dir={_dir_str} quality={_setup.quality:.2f}")
            
            # Use zone_price for entry_zone for proper SL/TP
            entry_zone = {"price": price, "high": price + 0.5, "low": price - 0.5}
            if _setup.zone_price:
                entry_zone = {"price": _setup.zone_price, "high": _setup.zone_price + 0.5, "low": _setup.zone_price - 0.5}

        # Priority 3: Fallback M1 spike (original street fighter logic)
        else:
            last_candle = candles_m1[-1]
            is_bullish = last_candle['close'] > last_candle['open']
            is_bearish = last_candle['close'] < last_candle['open']
            
            last_body = abs(candles_m1[-1]['close'] - candles_m1[-1]['open'])
            vol_spike = last_body > 0.2 * atr if atr > 0 else False

            logger.info(f"[AGGR] FALLBACK M1 Price={price:.2f} Z={z_score:.2f} ATR={atr:.2f} Body={last_body:.2f} Bullish={is_bullish} Bearish={is_bearish} VolSpike={vol_spike}")

            if is_bullish and vol_spike:
                if z_score < 1.5:
                    signal_dir = Direction.BUY
                    reason = f"momentum_spike_up_z={z_score:.2f}"
                    confidence = 0.75
                else:
                    reason = f"pucuk_buy_blocked_z={z_score:.2f}"
            
            elif is_bearish and vol_spike:
                if z_score > -1.5:
                    signal_dir = Direction.SELL
                    reason = f"momentum_spike_down_z={z_score:.2f}"
                    confidence = 0.75
                else:
                    reason = f"lembah_sell_blocked_z={z_score:.2f}"

        if not signal_dir:
            return StrategyResult(signal=None, confidence=0.0, reason=reason)

        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol="XAUUSD",
            direction=signal_dir,
            entry_zone={"price": price, "high": price + 0.5, "low": price - 0.5},
            confidence=confidence,
            timeframe="M1"
        )

        return StrategyResult(
            signal=signal,
            confidence=confidence,
            reason=reason,
            metadata={
                "z_score": z_score, 
                "vol_spike": vol_spike,
                "bypass_z_gate": bypass_z_gate,
                "setup_type": _setup.type.value if _setup and _setup.type != SetupType.NONE else "M1_SPIKE"
            }
        )

    def shutdown(self) -> None:
        self._initialized = False