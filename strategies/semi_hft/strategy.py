"""SemiHFT Strategy V4 — score-based pipeline, no gate stacking."""
import logging
import uuid
import json
import os
from datetime import datetime
from typing import Optional

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_metadata import StrategyMetadata
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.learning.learning_models import TradeReflection, TradeOutcome
from core.signals.signal import Signal, Direction

from .market_snapshot import snapshot as market_snapshot, MarketSnapshot
from .volatility_engine import calculate_score as vol_score
from .liquidity_map import calculate_score as liq_score
from .opportunity_window import get_session_score
from .market_pulse_engine import calculate_score as pulse_score
from .tick_velocity_engine import calculate_score as tick_vel_score
from .micro_momentum_engine import calculate_score as micro_score, MicroSignal
from .trendline_detector import detect_trendline_break
from .fvg_detector import get_active_fvgs
from .liquidity_vacuum import detect_liquidity_pools, vacuum_grade
from .entry_score import calculate as entry_score
from .fast_risk import plan as fast_risk
from .position_heat import calculate as pos_heat, HeatSnapshot
from .exit_intelligence import evaluate as exit_intel
from .daily_governor import DailyGovernor
from .learning import LearningLogger
from shared.pullback_filter import PullbackFilter

# Shared context-setup-location-trigger pipeline (Phase 2 refactor)
from shared.market_context import build as build_market_context
from shared.setup_detector import detect as detect_setup, SetupType
from shared.location_engine import evaluate as eval_location, LocationGrade
from shared.trigger_engine import evaluate as eval_trigger, TriggerSignal

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

METADATA = StrategyMetadata(
    id="semi_hft_c8_v4",
    name="SemiHFT V4",
    version="4.0",
    author="Riri & Sasa",
    description="V4 — Score-based micro scalping, XAUUSD. No gate stacking.",
    supported_symbols=["XAUUSD"],
    supported_timeframes=["M1"],
)

class SemiHFTStrategyV4(BaseStrategy):
    def __init__(self):
        super().__init__(METADATA)
        self._gov = DailyGovernor()
        self._log = LearningLogger()
        self._pullback = PullbackFilter()
        # Observe-time state
        self._snap: MarketSnapshot | None = None
        self._vol = self._liq = self._sess = self._pulse = self._vel = 0.0
        self._micro = None  # MicroMomentumSnapshot
        logger.info("SemiHFTStrategyV4 init — C8 Score Pipeline + Pullback Filter")

    def initialize(self): self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        f = context.scan.features
        if not f: return
        m1 = f.candles.get("M1", [])
        utc_h = getattr(f.timestamp, "hour", datetime.utcnow().hour)
        self._snap  = market_snapshot(m1)
        self._vol   = vol_score(symbol=f.symbol, atr_m5=getattr(f, "atr_m5", 0.0) or 0.0)
        self._liq   = liq_score(symbol=f.symbol, spread=getattr(f, "spread", 0.0) or 0.0, candles_m1=m1)
        self._sess  = get_session_score(utc_h)
        self._pulse = pulse_score(m1)
        self._vel   = tick_vel_score(m1)
        self._micro = micro_score(m1)

    def _score_meta(self, score: float = 0.0, extra: "dict | None" = None) -> dict:
        """Build score metadata from current observe snapshot."""
        m = {"score": score, "momentum": getattr(self._snap, "momentum_score", 0.0) if self._snap else 0.0,
             "velocity": self._vel, "liquidity": self._liq,
             "volatility": self._vol, "pulse": self._pulse}
        if extra:
            m.update(extra)
        return m

    def analyze(self, context: StrategyContext) -> StrategyResult:
        if not self._initialized or self._snap is None:
            return StrategyResult(signal=None, confidence=0.0, reason="init_pending",
                                  metadata={"score": 0.0})

        # 1. Governor (only hard gate)
        if self._gov.is_halted():
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"gov:{self._gov.get_status()['reason']}",
                                  metadata=self._score_meta())

        # 1b. News Sentinel Gate (Nexus-style)
        is_blackout, blackout_reason = check_news_blackout()
        if is_blackout:
            logger.warning(f"NEWS BLACKOUT ACTIVE: {blackout_reason}")
            return StrategyResult(signal=None, confidence=0.0, reason=f"news_blackout:{blackout_reason[:20]}")

        # === PHASE 2: CONTEXT → SETUP → LOCATION (M15/M5 first, M1 is trigger only) ===
        _f = context.scan.features
        _c15 = _f.candles.get("M15", []) if _f else []
        _c5  = _f.candles.get("M5",  []) if _f else []
        _c1  = _f.candles.get("M1",  []) if _f else []
        _atr = (_f.get_atr("M5") or 0.0) if _f else 0.0
        _price = (getattr(_f, "current_price", None) or getattr(_f, "bid", 0.0) or 0.0) if _f else 0.0

        _ctx   = build_market_context(_c15, _c5, _c1, _price, _atr)
        _setup = detect_setup(_ctx, _c5, _c1, _price)
        if not _setup.is_valid:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"no_setup:{_setup.reason}",
                                  metadata=self._score_meta(extra={"regime": _ctx.regime, "setup": "NONE"}))

        _struct_dir = _setup.direction.value  # M15/M5 decides direction

        # Location check — BAD = no trade
        _loc = eval_location(_struct_dir, _price, _c5, _c15, _atr)
        if _loc.grade == LocationGrade.BAD:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"bad_location:{_loc.reason}",
                                  metadata=self._score_meta(extra={"location": "BAD",
                                                                    "room_atr": _loc.available_room_atr}))

        logger.info(f"[SEMI] Setup={_setup.type} Dir={_struct_dir} Loc={_loc.grade}({_loc.score:.0f}) "
                    f"Regime={_ctx.regime} VwapDist={_ctx.vwap_distance_atr:.2f}ATR "
                    f"Zone={_setup.zone_price:.3f} Room={_loc.available_room_atr:.2f}ATR")

        # 2. Micro direction (M1) = timing only — must align with structural direction
        micro = self._micro
        if micro is None or micro.signal == MicroSignal.NONE:
            return StrategyResult(signal=None, confidence=0.0, reason="no_micro",
                                  metadata=self._score_meta(extra={"micro": getattr(micro, "score", 0.0) if micro else 0.0}))

        direction = micro.signal.value  # "BUY" | "SELL"

        # M1 micro must align with M15/M5 structural direction
        if direction != _struct_dir:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"m1_contra_structure:{direction}_vs_{_struct_dir}",
                                  metadata=self._score_meta(extra={"m1_dir": direction, "struct_dir": _struct_dir}))

        # 🧲 NEXUS TWEAK: Liquidity Vacuum Guard (Smart Money)
        liq_vac = {"grade": "GOOD", "reason": "no_pool_data", "tf": "-"}
        f = context.scan.features
        if f and f.candles:
            for tf in ("M5", "M15"):
                candles = f.candles.get(tf, [])
                if not candles:
                    continue
                atr = f.atr.get(tf, 0.0) or 0.0
                pools = detect_liquidity_pools(candles, atr)
                if pools["nearest_above"] or pools["nearest_below"]:
                    grade, reason = vacuum_grade(
                        pools["nearest_above"], pools["nearest_below"], direction, atr)
                    liq_vac = {"grade": grade, "reason": reason, "tf": tf}
                    if grade == "DANGER":
                        break
        if liq_vac["grade"] == "DANGER":
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"liq_vacuum:{liq_vac['reason']}",
                                  metadata=self._score_meta(extra={"liq_vac": liq_vac["reason"]}))
        logger.info(f"[LIQ_VACUUM] {liq_vac['grade']} {liq_vac['reason']} dir={direction}")
        
        # 5b. Z-Score Overextension Guard (Goldman Sachs inspired)
        from shared.zscore_filter import check as _zscore_check
        z_verdict = _zscore_check(f, f.candles if f else {}, direction)
        if not z_verdict.allowed:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"zscore:{z_verdict.reason}",
                                  metadata=self._score_meta(extra={
                                      "zscore_block": z_verdict.reason,
                                      "z_score": z_verdict.z_score
                                  }))
        logger.info(f"[ZSCORE] {z_verdict.reason}")

        # 🧲 PULLBACK FILTER (M5/M15 aligned entries)
        f = context.scan.features
        _regime = context.scan.regime
        _regime_name = context.scan.get_regime_name() if hasattr(context.scan, "get_regime_name") else str(getattr(_regime, "regime", None) and getattr(_regime, "regime").name or "").upper()
        # confidence (0-1) → strength (0-100); regime_strength >= 70 triggers trending_override
        _regime_strength = int((getattr(_regime, "strength", 0) or getattr(_regime, "confidence", 0) or 0) * 100)
        if f and f.candles and hasattr(f, "current_price"):
            pullback = self._pullback.check(
                f.candles, direction, f.current_price,
                regime=_regime_name, regime_strength=_regime_strength,
                features=f
            )
            if not pullback.allowed:
                return StrategyResult(signal=None, confidence=0.0,
                                      reason=f"pullback:{pullback.reason}",
                                      metadata=self._score_meta(extra={
                                          "pullback": pullback.reason,
                                          "m15_trend": pullback.m15_trend,
                                          "pullback_pct": pullback.pullback_pct
                                      }))
            logger.info(f"[PULLBACK] {pullback.reason} | M15={pullback.m15_trend}")

        # 🔥 MACD MOMENTUM GATE — Goldman Sachs inspired confirm filter
        from shared.macd_gate import check as _macd_check
        macd_verdict = _macd_check(f, f.candles if f else {}, direction)
        if not macd_verdict.allowed:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"macd:{macd_verdict.reason}",
                                  metadata=self._score_meta(extra={
                                      "macd_block": macd_verdict.reason,
                                      "macd_value": macd_verdict.macd_value,
                                      "signal_value": macd_verdict.signal_value
                                  }))
        logger.info(f"[MACD] {macd_verdict.reason}")

        # 🧠 NEXUS TWEAK: Calculate Counter-Bias (Conflict)
        # For BUY signal, look for SELL evidence in snapshot momentum
        counter_bias = 50.0
        if self._snap:
            # If we want BUY, but snap momentum is strongly BEARISH (< 35)
            if direction == "BUY" and self._snap.momentum_score < 35:
                counter_bias = (35 - self._snap.momentum_score) + 50
            # If we want SELL, but snap momentum is strongly BULLISH (> 65)
            elif direction == "SELL" and self._snap.momentum_score > 65:
                counter_bias = (self._snap.momentum_score - 65) + 50

        es = entry_score(
            momentum_score   = self._snap.momentum_score,
            velocity_score   = self._vel,
            liquidity_score  = self._liq,
            volatility_score = self._vol,
            pulse_score      = self._pulse,
            micro_score      = micro.score,
            direction        = direction,
            pattern          = micro.pattern,
            counter_bias_score = counter_bias,
        )
        if not es.entry_ok:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"entry_low:{es.score:.0f}",
                                  metadata={"score": es.score, "momentum": self._snap.momentum_score,
                                            "velocity": self._vel, "liquidity": self._liq,
                                            "volatility": self._vol, "pulse": self._pulse, "micro": micro.score})

        # 2b. M5 guard (L2 range compression + L3 reversal kill-switch)
        f0 = context.scan.features
        m5 = f0.candles.get("M5", []) if hasattr(f0, "candles") else []
        price_now = getattr(f0, "current_price", None) or getattr(f0, "bid", 0.0) or \
                    (float(m5[-1].get("close") or m5[-1].get("Close") or 0) if m5 else 0.0)
        guard = m5_guard(m5, direction, price_now)
        if guard != "OK":
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"m5_guard:{guard}",
                                  metadata=self._score_meta(extra={"m5_guard": guard, "price": price_now}))

        # 3. Risk plan (sole hard-reject: entry/equity == 0)
        f = context.scan.features
        _m1 = f.candles.get("M1", [])
        price  = getattr(f, "current_price", None) or getattr(f, "bid", 0.0) or \
                 (float(_m1[-1].get("close") or _m1[-1].get("Close") or 0) if _m1 else 0.0)
        equity = getattr(f, "equity", 500.0) or 500.0
        atr_m5 = f.get_atr("M5") or 0.0
        rp = fast_risk(direction=direction, entry=price,
                       candles_m5=f.candles.get("M5", []),
                       equity=equity, atr=atr_m5, strategy_id="semi_hft",
                       pattern=micro.pattern, zone_price=_setup.zone_price)
        if not rp.valid:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"risk:{rp.reason}")

        # 4. Position heat (soft check)
        pos = [context.position] if context.position else []
        heat = pos_heat(positions=pos, equity=equity)
        if heat.heat_score > 90:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"heat:{heat.heat_score:.0f}")

        # 4b. Trendline Guard (XAU-60 Logic)
        m1_df = getattr(context, "m1_data", None)
        if m1_df is not None and not m1_df.empty:
            is_tl_break, tl_dir = detect_trendline_break(m1_df)
            if not is_tl_break or tl_dir != direction:
                return StrategyResult(signal=None, confidence=0.0,
                                      reason=f"tl_guard:NO_{direction}_BREAK",
                                      metadata=self._score_meta(score=es.score))

        # 5. Signal
        conf = min(100.0, es.score)
        sig = Signal(
            signal_id       = str(uuid.uuid4())[:8],
            strategy        = self.metadata.id,
            symbol          = f.symbol,
            direction       = Direction.BUY if direction == "BUY" else Direction.SELL,
            entry_zone      = {"low": price - 0.5, "high": price + 0.5},
            confidence      = conf,
            timeframe       = "M1",
            entry_price_hint= price,
            quality_score   = es.score,
            metadata        = {
                "lot": rp.lot, "sl": rp.sl, "tp": rp.tp, "rr": rp.rr,
                "pattern": micro.pattern, "entry_score": es.score,
                "vol": self._vol, "liq": self._liq, "pulse": self._pulse,
                "vel": self._vel, "micro": micro.score,
            }
        )
        logger.info(f"C8V4 {direction} entry={price} sl={rp.sl} tp={rp.tp} "
                    f"lot={rp.lot} pattern={micro.pattern} score={es.score:.1f}")
        # Telemetry
        try:
            from shared.entry_telemetry import log_candidate, CandidateRecord
            _rr = round(abs(rp.tp - price) / abs(price - rp.sl), 2) if abs(price - rp.sl) > 0 else 0.0
            log_candidate(CandidateRecord(
                strategy="SemiHFT", symbol=str(f.symbol), direction=direction,
                regime=str(_setup.direction.value if hasattr(_setup,"direction") else ""),
                setup_type=str(_setup.type.value),
                location_grade=str(_loc.grade.value), available_room_atr=_loc.available_room_atr,
                vwap_dist_atr=_ctx.vwap_distance_atr,
                dist_structure_atr=_loc.distance_to_structure_atr,
                dist_obstacle_atr=_loc.distance_to_obstacle_atr,
                location_reason=_loc.reason,
                trigger_signal=str(_trig.signal.value) if '_trig' in dir() else "ARMED", trigger_score=_trig.strength if '_trig' in dir() else 0.0,
                trigger_strength=_trig.strength if '_trig' in dir() else 0.0,
                setup_score=float(_setup.quality), zone_price=float(_setup.zone_price),
                m15_bias=str(_ctx.m15_bias.value), m5_structure=str(_ctx.m5_structure.value),
                atr=float(atr_m5), spread=float(f.spread if isinstance(f.spread, float) else 0.0),
                entry_price=float(price), sl=float(rp.sl), tp=float(rp.tp), rr=_rr,
                structural_rr=round(_loc.available_room_atr / max(abs(price - rp.sl) / max(atr_m5,0.01), 0.01), 2),
                decision="ENTRY", filter_trace=[],
            ))
        except Exception as _te:
            logger.debug("telemetry error: %s", _te)
        return StrategyResult(
            signal=sig,
            confidence=conf,
            reason=f"c8v4_{micro.pattern}",
            metadata={
                "score": es.score,
                "momentum": self._snap.momentum_score,
                "velocity": self._vel,
                "liquidity": self._liq,
                "volatility": self._vol,
                "pulse": self._pulse,
                "micro": micro.score,
            }
        )

    def learn(self, reflection: TradeReflection) -> None:
        pnl = getattr(reflection, "realized_pl", 0.0) or 0.0
        self._gov.record_trade(pnl)
        self._log.record(
            symbol          = getattr(reflection, "symbol", "XAUUSD"),
            market_state    = self._snap.state.value if self._snap else "",
            opportunity_score=self._sess,
            entry_reason    = "",
            exit_reason     = str(reflection.exit_reason.value),
            hold_seconds    = getattr(reflection, "duration_seconds", 0.0) or 0.0,
            pnl             = pnl,
            pattern         = getattr(reflection, "entry_regime", ""),
        )

    def shutdown(self): self._initialized = False


def m5_guard(m5, direction, price):
    """L2+L3 HFT guard — pure price action, no lagging indicators."""
    if len(m5) < 30:
        return "OK"
    try:
        last_2 = m5[-2:]
        h1, l1, c1 = float(last_2[0].get("high") or last_2[0].get("High") or 0), \
                     float(last_2[0].get("low")  or last_2[0].get("Low")  or 0), \
                     float(last_2[0].get("close")or last_2[0].get("Close")or 0)
        h2, l2, c2 = float(last_2[1].get("high") or last_2[1].get("High") or 0), \
                     float(last_2[1].get("low")  or last_2[1].get("Low")  or 0), \
                     float(last_2[1].get("close")or last_2[1].get("Close")or 0)
    except (TypeError, ValueError, IndexError):
        return "OK"
    if direction == "BUY" and h2 < h1 and l2 < l1 and c2 < c1:
        return "BLOCK_REVERSAL"
    if direction == "SELL" and h2 > h1 and l2 > l1 and c2 > c1:
        return "BLOCK_REVERSAL"
    try:
        recent_10 = m5[-10:]
        prev_20 = m5[-30:-10]
        hi_10 = max(float(c.get("high") or c.get("High") or 0) for c in recent_10)
        lo_10 = min(float(c.get("low")  or c.get("Low")  or 0) for c in recent_10)
        hi_20 = max(float(c.get("high") or c.get("High") or 0) for c in prev_20)
        lo_20 = min(float(c.get("low")  or c.get("Low")  or 0) for c in prev_20)
    except (TypeError, ValueError):
        return "OK"
    cur = hi_10 - lo_10
    prev = hi_20 - lo_20
    if prev > 0 and cur < prev * 0.7:
        if lo_10 <= price <= hi_10:
            return "BLOCK_RANGE"
    return "OK"
