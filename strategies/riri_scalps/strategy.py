import uuid
import logging
from typing import Optional, Tuple, List, Dict

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction

logger = logging.getLogger("RiriScalps")

# --- SETTINGS ---
SWING_LOOKBACK   = 12       # was 10 — more stable structure
RETEST_MAX_BARS  = 5       # was 4 — give price room to breath
RETEST_TOL_ATR   = 0.25    # was 0.20
WICK_BODY_RATIO  = 2.0     # was 1.5 — stricter wick rejection
ENG_C_PROXIMITY  = 0.5     # was 2.0 — TIGHT proximity to swing levels (0.5x ATR)
VOL_SPIKE_RATIO  = 1.5     # volume must be 1.5x avg for Engine A

_breakout_state: dict = {}

def is_bullish(c): return float(c.get("close", 0)) > float(c.get("open", 0))
def is_bearish(c): return float(c.get("close", 0)) < float(c.get("open", 0))
def body_size(c): return abs(float(c.get("close", 0)) - float(c.get("open", 0)))

def _swing_levels(candles: list, lookback: int) -> Tuple[float, float]:
    recent = candles[-lookback-2:-2]
    if not recent: return 0.0, 999999.0
    return (max(float(c.get("high", 0)) for c in recent),
            min(float(c.get("low", 0)) for c in recent))

def _get_m15_trend(m15_candles: List[Dict]) -> str:
    if len(m15_candles) < 6: return "NONE"
    bull = sum(1 for c in m15_candles[-6:-1] if is_bullish(c))
    bear = sum(1 for c in m15_candles[-6:-1] if is_bearish(c))
    if bull >= 3: return "BULL"
    if bear >= 3: return "BEAR"
    return "NONE"

class RiriScalpsStrategy(BaseStrategy):
    def __init__(self):
        meta = StrategyMetadata(
            id="riri_scalps_v1",
            name="RiriScalps",
            version="2.0.0",
            priority=95,
            author="Riri",
            description="Whale Hunter Edition: FVG Retest + Structural Flow + Liquidity Sweep"
        )
        super().__init__(meta)
        self._last_candle_key = None

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market
        candles_m5 = market_ctx.metadata.get("candles", {}).get("M5", [])
        candles_m15 = market_ctx.metadata.get("candles", {}).get("M15", [])
        
        if len(candles_m5) < SWING_LOOKBACK + 5:
            return StrategyResult(signal=None, confidence=0.0, reason="low_data")

        price  = market_ctx.price or candles_m5[-1]["close"]
        atr    = market_ctx.atr or 2.0
        sym    = market_ctx.symbol

        # ── GLOBAL FILTER: M15 Trend ──
        trend_m15 = _get_m15_trend(candles_m15)

        # Same-candle guard
        lc = candles_m5[-2]
        ckey = f"{lc['high']}_{lc['low']}_{lc['close']}"
        if ckey == getattr(self, "_last_candle_key", None):
            # Engine B (retest) exempt from same-candle guard to allow price hit
            pass 
        else:
            self._last_candle_key = ckey

        # ── ENGINE A: Whale FVG (Imbalance) ──
        avg_body = sum(body_size(c) for c in candles_m5[-11:-1]) / 10
        avg_vol  = sum(float(c.get("tick_volume", 1)) for c in candles_m5[-11:-1]) / 10
        spike_c  = candles_m5[-2]
        s_body   = body_size(spike_c)
        s_vol    = float(spike_c.get("tick_volume", 0))

        if s_body > (avg_body * 2.5) and s_vol > (avg_vol * VOL_SPIKE_RATIO):
            # Bullish Spike -> BUY on 30-70% retest
            if is_bullish(spike_c) and trend_m15 == "BULL":
                # Retest zone: between 30% and 70% of the body
                top = spike_c["open"] + s_body * 0.7
                btm = spike_c["open"] + s_body * 0.3
                if btm <= price <= top:
                    return self._emit(sym, Direction.BUY, price, 0.88, "A_whale_fvg_buy", 
                                     spike_c["low"] - 0.2, price + 4.0, market_ctx)
            # Bearish Spike -> SELL on 30-70% retest
            elif is_bearish(spike_c) and trend_m15 == "BEAR":
                top = spike_c["open"] - s_body * 0.3
                btm = spike_c["open"] - s_body * 0.7
                if btm <= price <= top:
                    return self._emit(sym, Direction.SELL, price, 0.88, "A_whale_fvg_sell", 
                                     spike_c["high"] + 0.2, price - 4.0, market_ctx)

        # ── ENGINE B: Structure Flow (Break + Retest) ──
        sh, sl = _swing_levels(candles_m5, SWING_LOOKBACK)
        lc_close = float(spike_c["close"])
        
        # Detect Breakout
        if lc_close > sh and trend_m15 == "BULL":
            _breakout_state[sym] = {"dir": "BUY", "lvl": sh, "bars": 0}
        elif lc_close < sl and trend_m15 == "BEAR":
            _breakout_state[sym] = {"dir": "SELL", "lvl": sl, "bars": 0}
        
        # Check Retest
        if sym in _breakout_state:
            st = _breakout_state[sym]
            st["bars"] += 1
            if st["bars"] > RETEST_MAX_BARS:
                del _breakout_state[sym]
            elif abs(price - st["lvl"]) <= (atr * RETEST_TOL_ATR):
                direction = Direction.BUY if st["dir"] == "BUY" else Direction.SELL
                stop = sl if direction == Direction.BUY else sh
                target = price + (4.0 if direction == Direction.BUY else -4.0)
                del _breakout_state[sym]
                return self._emit(sym, direction, price, 0.85, f"B_struct_flow_{st['dir']}", stop, target, market_ctx)

        # ── ENGINE C: Liquidity Sweep (Wick Reject) ──
        u_wick = float(spike_c["high"]) - max(float(spike_c["close"]), float(spike_c["open"]))
        l_wick = min(float(spike_c["close"]), float(spike_c["open"])) - float(spike_c["low"])
        
        if s_body > 0:
            # Bullish Reject at SL (Swing Low)
            if l_wick > WICK_BODY_RATIO * s_body and is_bullish(spike_c) and trend_m15 == "BULL":
                if abs(price - sl) <= ENG_C_PROXIMITY * atr:
                    return self._emit(sym, Direction.BUY, price, 0.82, "C_liq_sweep_buy", sl - 0.2, price + 4.0, market_ctx)
            # Bearish Reject at SH (Swing High)
            elif u_wick > WICK_BODY_RATIO * s_body and is_bearish(spike_c) and trend_m15 == "BEAR":
                if abs(price - sh) <= ENG_C_PROXIMITY * atr:
                    return self._emit(sym, Direction.SELL, price, 0.82, "C_liq_sweep_sell", sh + 0.2, price - 4.0, market_ctx)

        return StrategyResult(signal=None, confidence=0.0, reason="no_setup")

    def _emit(self, sym, sig_dir, price, conf, reason, sl, tp, ctx) -> StrategyResult:
        logger.info(f"[RIRI] {reason} at {price:.2f} SL={sl:.2f} TP={tp:.2f}")
        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol=sym,
            direction=sig_dir,
            entry_zone={"price": price, "high": price + 0.2, "low": price - 0.2},
            confidence=conf,
            timeframe="M5"
        )
        return StrategyResult(
            signal=signal,
            confidence=conf,
            reason=reason,
            metadata={
                "setup_type": "R",
                "sl": sl,
                "tp": tp,
                "volume": 0.05,
                "strategy_code": "R"
            }
        )

    def shutdown(self) -> None:
        _breakout_state.clear()
