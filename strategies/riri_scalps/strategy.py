import uuid
import logging
import math
from typing import Optional, Tuple, List, Dict

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction

logger = logging.getLogger("RiriScalps")

# --- SETTINGS ---
SWING_LOOKBACK   = 12
RETEST_MAX_BARS  = 5
RETEST_TOL_ATR   = 0.25
WICK_BODY_RATIO  = 2.0
ENG_C_PROXIMITY  = 0.5
VOL_SPIKE_RATIO  = 1.5

# --- NEW SETTINGS (v3.0.0) ---
ADX_PERIOD       = 14
ADX_THRESHOLD    = 20       # below = weak trend → skip Engine B
THRUST_FILTER      = True   # [V-THRUST 11-Sep] audit 43 trade: entry tanpa thrust (bar trigger gak
                            # searah / bar sebelumnya melawan) = WR 14-25%, net -18. Dengan thrust
                            # (signal bar + 1 bar sebelumnya searah): WR 88%+, net +16.8. Ini filter
                            # kualitas entry, bukan perisai SL. Mode ketat: 2 bar sebelumnya juga searah.
THRUST_STRICT      = False  # True = butuh 2 bar prev searah (audit: +0.2$ doang, tapi trade -3)
SL_MAX_DIST_USD    = 2.5    # [V-TRUNC 10-Sep] plafon jarak SL dlm $ utk 0.01 lot (XAUUSD: $1 jarak = $1 rugi).
                            # Bukti: 11 loss RiriScalps net -42.82 (worst -10.69) vs 34 win cuma +0.97 rata2 —
                            # SL struktur M5 bisa lari 3-10x ATR, satu runner = 10 copet profit hangus.
                            # Clamp: SL struktur tetap dipakai kalau <= plafon; kalau kelebaran, dipotong ke plafon.
EA_ONLY_MODE     = True     # True = only Engine F (EA Nyao port) trades; A/C/D/E1/E2 disabled
RSI_PERIOD       = 14
MACD_FAST        = 12
MACD_SLOW        = 26
MACD_SIGNAL      = 9
BB_PERIOD        = 20
BB_STD           = 2.0
POSITION_PCT     = 0.02     # 2% of balance per trade
MAX_LOT          = 0.10     # hard cap
MIN_LOT          = 0.01     # minimum lot
MAX_LOSS_PER_TRADE_USD = 4.0  # [V-CAP 10-Sep] rugi maksimum dolar per trade utk 0.01-lot XAUUSD:
                              # lot dibatasi s.t. lot × sl_dist × 100 <= cap. Bukti: sizing % bikin
                              # SL 2.5$ jadi lot 0.04 = risk $10 — pager SL doang percuma kalau lot ngembang.

_breakout_state: dict = {}  # DEPRECATED: Engine B removed, kept for import compat

# ── HELPERS ──
def is_bullish(c): return float(c.get("close", 0)) > float(c.get("open", 0))
def is_bearish(c): return float(c.get("close", 0)) < float(c.get("open", 0))
def body_size(c): return abs(float(c.get("close", 0)) - float(c.get("open", 0)))
def _hlc(c): return float(c.get("high",0)), float(c.get("low",0)), float(c.get("close",0))

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

# ── FRESH SUPPORT/RESISTANCE DETECTION (structure-based SL/TP) ──

def _find_pivot_highs(candles: List[Dict], left: int = 3, right: int = 3) -> List[Tuple[int, float]]:
    """Find swing high pivots: candle whose high is highest of left+right neighbors."""
    pivots = []
    for i in range(left, len(candles) - right):
        h = float(candles[i]["high"])
        is_pivot = True
        for j in range(i - left, i + right + 1):
            if j == i: continue
            if float(candles[j]["high"]) >= h:
                is_pivot = False
                break
        if is_pivot:
            pivots.append((i, h))
    return pivots

def _find_pivot_lows(candles: List[Dict], left: int = 3, right: int = 3) -> List[Tuple[int, float]]:
    """Find swing low pivots: candle whose low is lowest of left+right neighbors."""
    pivots = []
    for i in range(left, len(candles) - right):
        l = float(candles[i]["low"])
        is_pivot = True
        for j in range(i - left, i + right + 1):
            if j == i: continue
            if float(candles[j]["low"]) <= l:
                is_pivot = False
                break
        if is_pivot:
            pivots.append((i, l))
    return pivots

def _is_fresh(candles: List[Dict], level: float, from_idx: int, tol: float = 0.5) -> bool:
    """Check if S/R level hasn't been touched by any candle after from_idx."""
    for i in range(from_idx + 1, len(candles)):
        if float(candles[i]["low"]) <= level + tol and float(candles[i]["high"]) >= level - tol:
            return False  # level was touched → not fresh
    return True

def _find_fresh_sr(candles: List[Dict], price: float, atr: float,
                   left: int = 3, right: int = 3, max_levels: int = 8) -> Dict:
    """
    Find nearest fresh (untested) support below price and resistance above price.
    Returns: {"support": float|None, "resistance": float|None, "all_supports": [...], "all_resistances": [...]}
    """
    tol = atr * 0.15  # tolerance for "touch" detection (15% of ATR)

    # Find pivots
    swing_highs = _find_pivot_highs(candles, left, right)
    swing_lows = _find_pivot_lows(candles, left, right)

    # Filter fresh levels
    fresh_resistance = []
    fresh_support = []

    for idx, level in swing_highs:
        if level > price and _is_fresh(candles, level, idx, tol):
            fresh_resistance.append((idx, level))

    for idx, level in swing_lows:
        if level < price and _is_fresh(candles, level, idx, tol):
            fresh_support.append((idx, level))

    # Sort: resistance ascending (nearest first), support descending (nearest first)
    fresh_resistance.sort(key=lambda x: x[1])
    fresh_support.sort(key=lambda x: -x[1])

    # Take nearest N
    result = {
        "support": fresh_support[0][1] if fresh_support else None,
        "resistance": fresh_resistance[0][1] if fresh_resistance else None,
        "all_supports": [s[1] for s in fresh_support[:max_levels]],
        "all_resistances": [r[1] for r in fresh_resistance[:max_levels]],
    }
    return result

def _thrust_ok(candles_m5, is_buy: bool) -> bool:
    """[V-THRUST] bar trigger = candles_m5[-2] (bar M5 terakhir yang CLOSED; [-1] masih hidup).
    Butuh: bar trigger searah trade + minimal 1 bar sebelumnya searah."""
    if len(candles_m5) < 4:
        return False
    sig = candles_m5[-2]
    prev = candles_m5[-3]
    need_up = (float(sig["close"]) > float(sig["open"])) if is_buy else (float(sig["close"]) < float(sig["open"]))
    prev_up = (float(prev["close"]) > float(prev["open"])) if is_buy else (float(prev["close"]) < float(prev["open"]))
    if not (need_up and prev_up):
        return False
    if THRUST_STRICT:
        p2 = candles_m5[-4]
        p2_up = (float(p2["close"]) > float(p2["open"])) if is_buy else (float(p2["close"]) < float(p2["open"]))
        return bool(p2_up)
    return True


def _get_sl_tp(direction: Direction, price: float, sr: Dict, atr: float) -> Tuple[float, float]:
    """
    Compute SL/TP from fresh S/R levels.
    BUY: SL = nearest fresh support (below), TP = nearest fresh resistance (above)
    SELL: SL = nearest fresh resistance (above), TP = nearest fresh support (below)
    Fallback to ATR-based if no fresh S/R found (safety net).
    """
    min_sl_dist = atr * 0.5  # minimum SL distance (safety)

    if direction == Direction.BUY:
        # SL: nearest fresh support below price
        if sr["support"] is not None:
            sl = sr["support"] - atr * 0.1  # slightly below support
        else:
            sl = price - atr * 1.5  # fallback
        # Ensure minimum distance
        if abs(price - sl) < min_sl_dist:
            sl = price - min_sl_dist
        # TP: nearest fresh resistance above price
        if sr["resistance"] is not None:
            tp = sr["resistance"] - atr * 0.05  # slightly before resistance (conservative)
        else:
            tp = price + atr * 3.0  # fallback
        # Ensure positive RR
        if tp <= price:
            tp = price + abs(price - sl) * 1.5
    else:  # SELL
        # SL: nearest fresh resistance above price
        if sr["resistance"] is not None:
            sl = sr["resistance"] + atr * 0.1  # slightly above resistance
        else:
            sl = price + atr * 1.5  # fallback
        # Ensure minimum distance
        if abs(sl - price) < min_sl_dist:
            sl = price + min_sl_dist
        # TP: nearest fresh support below price
        if sr["support"] is not None:
            tp = sr["support"] + atr * 0.05  # slightly above support (conservative)
        else:
            tp = price - atr * 3.0  # fallback
        # Ensure positive RR
        if tp >= price:
            tp = price - abs(sl - price) * 1.5

    # [V-TRUNC] plafon jarak SL — jangan biarin struktur jauh ngasih risk liar
    if direction == Direction.BUY:
        sl = max(sl, price - SL_MAX_DIST_USD)
    else:
        sl = min(sl, price + SL_MAX_DIST_USD)
    return sl, tp

# ── INDICATOR COMPUTATIONS (adapted from Fincept IndicatorEngine) ──

def _ema(src: List[float], period: int) -> List[float]:
    """EMA series — returns list same length as src, NaN-padded."""
    if len(src) < period: return [float('nan')] * len(src)
    k = 2.0 / (period + 1)
    out = [float('nan')] * (period - 1)
    out.append(sum(src[:period]) / period)
    for i in range(period, len(src)):
        out.append(src[i] * k + out[-1] * (1 - k))
    return out

def _sma(src: List[float], period: int) -> List[float]:
    if len(src) < period: return [float('nan')] * len(src)
    out = [float('nan')] * (period - 1)
    for i in range(period - 1, len(src)):
        out.append(sum(src[i-period+1:i+1]) / period)
    return out

def _compute_rsi(closes: List[float], period: int = 14) -> float:
    """Single RSI value (last bar)."""
    if len(closes) < period + 1: return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas[-period:]]
    losses = [abs(min(d, 0)) for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def _compute_macd(closes: List[float], fast=12, slow=26, sig=9) -> Tuple[float, float, float]:
    """Returns (macd_line, signal_line, histogram)."""
    if len(closes) < slow + sig: return 0.0, 0.0, 0.0
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow) if not (math.isnan(f) or math.isnan(s))]
    if len(macd_line) < sig: return 0.0, 0.0, 0.0
    signal_line = _ema(macd_line, sig)
    ml = macd_line[-1]
    sl = signal_line[-1] if not math.isnan(signal_line[-1]) else 0.0
    return ml, sl, ml - sl

def _compute_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """ADX value (0-100)."""
    n = len(closes)
    if n < period * 2: return 25.0  # default neutral
    tr_list, plus_dm, minus_dm = [], [], []
    for i in range(1, n):
        h, l, prev_c = highs[i], lows[i], closes[i-1]
        tr_list.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        up = highs[i] - highs[i-1]
        down = lows[i-1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
    # Wilder smoothing
    def wilder_smooth(data, p):
        out = [sum(data[:p])]
        for i in range(p, len(data)):
            out.append(out[-1] - out[-1] / p + data[i])
        return out
    if len(tr_list) < period: return 25.0
    atr_s = wilder_smooth(tr_list, period)
    pdm_s = wilder_smooth(plus_dm, period)
    mdm_s = wilder_smooth(minus_dm, period)
    min_len = min(len(atr_s), len(pdm_s), len(mdm_s))
    if min_len < 2: return 25.0
    dx_list = []
    for i in range(min_len):
        a = atr_s[i] if i < len(atr_s) else atr_s[-1]
        if a == 0: continue
        pdi = 100 * (pdm_s[i] if i < len(pdm_s) else 0) / a
        mdi = 100 * (mdm_s[i] if i < len(mdm_s) else 0) / a
        denom = pdi + mdi
        if denom == 0: continue
        dx_list.append(100 * abs(pdi - mdi) / denom)
    if len(dx_list) < period: return 25.0
    adx = sum(dx_list[-period:]) / period
    return adx

def _compute_bollinger(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
    """Returns (upper, middle, lower)."""
    if len(closes) < period: return 0, 0, 0
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    return mid + std_dev * std, mid, mid - std_dev * std

def _compute_vwap_from_candles(candles: List[Dict]) -> float:
    """Approximate VWAP from candle data."""
    cum_vol = 0
    cum_tp_vol = 0
    for c in candles:
        h, l, cl = _hlc(c)
        v = float(c.get("tick_volume", 1))
        tp = (h + l + cl) / 3
        cum_tp_vol += tp * v
        cum_vol += v
    return cum_tp_vol / cum_vol if cum_vol > 0 else 0

def _calc_lot(balance: float, price: float, atr: float, sl_dist: float) -> float:
    """Position % sizing — risk POSITION_PCT of balance per trade."""
    if balance <= 0 or price <= 0 or sl_dist <= 0:
        return MIN_LOT
    risk_amount = balance * POSITION_PCT
    # XAUUSD: 0.01 lot = $0.10 per point
    # risk_amount = lot * sl_dist * 100
    lot = risk_amount / (sl_dist * 100)
    # [V-CAP] lot ceiling by dolar loss — turun-only, kalau 0.01 masih > cap -> 0 (skip)
    lot_cap = MAX_LOSS_PER_TRADE_USD / (sl_dist * 100)
    lot = max(0.0, min(lot, lot_cap))
    lot = math.floor(lot * 100 + 1e-8) / 100  # turun ke step 0.01, jangan naik
    if lot < MIN_LOT:
        return 0.0  # terlalu lebar utk cap — engine skip order (lot 0 = no trade)
    lot = min(MAX_LOT, lot)
    return lot


# ── NYAO SCALPER SIGNAL SCORING (adapted from Nyao v43 by Elriz Wiraswara) ──
# Multi-factor composite score (0-10) that measures SIGNAL QUALITY, not just indicator match.
# Each component scores independently — a strong trend can compensate for weak momentum.
NYAO_SCORE_THRESHOLD = 4.5   # EA default: MinBuySignalScore/MinSellSignalScore = 4.5
NYAO_SMOOTH_N = 3            # candles for weighted average smoothing
NYAO_BLEND = 0.40            # current candle blend factor
NYAO_VELOCITY_WINDOW = 2.0   # velocity normalization window

# Component weights (matching Nyao's scoring architecture)
NYAO_TREND_WEIGHT = 1.5      # EMA alignment
NYAO_SLOPE_WEIGHT = 1.5      # EMA slope confirmation
NYAO_MOM_BASE_WEIGHT = 1.0   # RSI sweet spot
NYAO_MOM_TRIGGER_WEIGHT = 0.5 # RSI breakout zone
NYAO_BODY_MOM_WEIGHT = 1.5   # body momentum (current > avg)
NYAO_CHOP_HIGH = 2.0         # vol ratio > 1.0 = strong trend
NYAO_CHOP_MED = 1.0          # vol ratio > 0.8 = weak trend
NYAO_CHOP_LOW = 0.0          # vol ratio < 0.8 = chop risk
NYAO_VOL_HIGH = 1.0          # vol ratio > 1.2
NYAO_VOL_LOW = 0.0           # vol ratio <= 1.2
NYAO_PEAK_WEIGHT = 1.0       # breakout above recent high/low
NYAO_WICK_WEIGHT = 1.0       # wick rejection penalty
NYAO_MIN_BODY_RATIO = 1.5    # min body ratio for wick calc
NYAO_MIN_VOL_RATIO = 0.6     # dead market filter (ATR/avgATR)
NYAO_BODY_LOOKBACK = 10      # lookback for avg body size
NYAO_IMPULSE_LOOKBACK = 3    # impulse detection lookback
NYAO_IMPULSE_WEIGHT = 1.0    # impulse boost weight
NYAO_CONSEC_BOOST = 1.0      # EA: ConsecutiveCandleThresholdBoost (per consecutive entry candle)
NYAO_MAX_CANDLE_BOOSTS = 3   # EA: MaxConsecutiveCandleBoosts (cap the escalation)


def _compute_nyao_raw_score(candles: List[Dict], direction: str, idx: int = 0) -> Tuple[float, Dict]:
    """
    Nyao-style multi-factor signal scoring (adapted from MQL5 to Python).
    Returns (score 0-10, component_dict).
    direction: "BUY" or "SELL"
    idx: 0 = current candle, 1+ = closed candles (for smoothing).
    """
    if idx + NYAO_BODY_LOOKBACK + 5 >= len(candles):
        return 0.0, {}

    is_buy = (direction == "BUY")

    # --- Fetch candle data ---
    c0 = candles[-1 - idx]
    closes_window = [float(candles[-1 - idx - j]["close"]) for j in range(NYAO_BODY_LOOKBACK + 5)]
    closes_window.reverse()  # oldest first

    ema_fast_vals = _ema(closes_window, 5)
    ema_slow_vals = _ema(closes_window, 12)
    rsi_vals = closes_window

    ema_fast = ema_fast_vals[-1] if not math.isnan(ema_fast_vals[-1]) else 0
    ema_slow = ema_slow_vals[-1] if not math.isnan(ema_slow_vals[-1]) else 0
    ema_fast_prev = ema_fast_vals[-4] if len(ema_fast_vals) > 3 and not math.isnan(ema_fast_vals[-4]) else ema_fast

    rsi = _compute_rsi(rsi_vals, 8)  # Nyao uses RSI(8)

    highs = [float(candles[-1 - idx - j]["high"]) for j in range(NYAO_BODY_LOOKBACK + 5)]
    lows  = [float(candles[-1 - idx - j]["low"]) for j in range(NYAO_BODY_LOOKBACK + 5)]
    highs.reverse(); lows.reverse()

    atr_vals = []
    for k in range(1, len(closes_window)):
        tr = max(highs[k] - lows[k], abs(highs[k] - closes_window[k-1]), abs(lows[k] - closes_window[k-1]))
        atr_vals.append(tr)
    current_atr = sum(atr_vals[-8:]) / min(8, len(atr_vals)) if atr_vals else 0

    avg_atr = sum(atr_vals[-10:]) / min(10, len(atr_vals)) if atr_vals else current_atr
    vol_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0

    current_body = abs(float(c0["close"]) - float(c0["open"]))
    sum_body = sum(abs(float(candles[-1 - idx - j]["close"]) - float(candles[-1 - idx - j]["open"]))
                   for j in range(1, min(NYAO_BODY_LOOKBACK + 1, len(candles) - idx)))
    avg_body = sum_body / NYAO_BODY_LOOKBACK if NYAO_BODY_LOOKBACK > 0 else current_body

    # --- 1. TREND SCORE (max 3.0) ---
    trend_score = 0.0
    if is_buy:
        if ema_fast > ema_slow: trend_score += NYAO_TREND_WEIGHT
        if ema_fast > ema_fast_prev: trend_score += NYAO_SLOPE_WEIGHT
    else:
        if ema_fast < ema_slow: trend_score += NYAO_TREND_WEIGHT
        if ema_fast < ema_fast_prev: trend_score += NYAO_SLOPE_WEIGHT
    trend_score = min(trend_score, 3.0)

    # --- 2. MOMENTUM SCORE (max 3.0) + IMPULSE ---
    base_mom = 0.0
    if is_buy:
        if 50 < rsi < 80: base_mom += NYAO_MOM_BASE_WEIGHT
        if rsi > 60: base_mom += NYAO_MOM_TRIGGER_WEIGHT
        if current_body > avg_body: base_mom += NYAO_BODY_MOM_WEIGHT
    else:
        if 20 < rsi < 50: base_mom += NYAO_MOM_BASE_WEIGHT
        if rsi < 40: base_mom += NYAO_MOM_TRIGGER_WEIGHT
        if current_body > avg_body: base_mom += NYAO_BODY_MOM_WEIGHT

    # Impulse detection (body acceleration + range acceleration + continuity)
    body_accel = min(current_body / avg_body, 3.0) if avg_body > 0 else 1.0
    current_range = float(c0["high"]) - float(c0["low"])
    sum_range = sum(float(candles[-1 - idx - j]["high"]) - float(candles[-1 - idx - j]["low"])
                    for j in range(1, min(NYAO_BODY_LOOKBACK + 1, len(candles) - idx)))
    avg_range = sum_range / NYAO_BODY_LOOKBACK if NYAO_BODY_LOOKBACK > 0 else current_range
    range_accel = min(current_range / avg_range, 3.0) if avg_range > 0 else 1.0

    same_dir = 0
    for k in range(NYAO_IMPULSE_LOOKBACK):
        ck = candles[-1 - idx - k]
        if is_buy and float(ck["close"]) > float(ck["open"]): same_dir += 1
        elif not is_buy and float(ck["close"]) < float(ck["open"]): same_dir += 1
        else: break
    continuity = min(same_dir / NYAO_IMPULSE_LOOKBACK, 1.0)

    raw_impulse = min(max((0.5 * body_accel + 0.3 * range_accel + 0.2 * continuity) / 2.0, 0), 1.0)
    mom_score = base_mom * (1.0 + NYAO_IMPULSE_WEIGHT * raw_impulse)
    mom_score = min(mom_score, 3.0)

    # --- 3. CHOP SCORE (max 2.0) — dead market filter ---
    if NYAO_MIN_VOL_RATIO > 0 and vol_ratio > 0 and vol_ratio < NYAO_MIN_VOL_RATIO:
        return 0.0, {}  # dead market — block entirely

    chop_score = NYAO_CHOP_HIGH if vol_ratio > 1.0 else (NYAO_CHOP_MED if vol_ratio > 0.8 else NYAO_CHOP_LOW)
    chop_score = min(chop_score, 2.0)

    # --- 4. VOLATILITY SCORE (max 1.0) ---
    vol_score = NYAO_VOL_HIGH if vol_ratio > 1.2 else NYAO_VOL_LOW

    # --- 5. PEAK BREAKOUT SCORE (max 1.0) ---
    local_extreme = float(candles[-2 - idx]["high"]) if is_buy else float(candles[-2 - idx]["low"])
    for k in range(2, min(6, len(candles) - idx)):
        ck = candles[-1 - idx - k]
        if is_buy: local_extreme = max(local_extreme, float(ck["high"]))
        else: local_extreme = min(local_extreme, float(ck["low"]))

    breakout = False
    if is_buy and float(c0["close"]) > local_extreme: breakout = True
    if not is_buy and float(c0["close"]) < local_extreme: breakout = True
    peak_score = NYAO_PEAK_WEIGHT if breakout else 0.0

    # --- 6. WICK REJECTION PENALTY ---
    max_oc = max(float(c0["open"]), float(c0["close"]))
    min_oc = min(float(c0["open"]), float(c0["close"]))
    upper_wick = float(c0["high"]) - max_oc
    lower_wick = min_oc - float(c0["low"])
    safe_body = max(current_body, avg_body * NYAO_MIN_BODY_RATIO)
    penalty_wick = 0.0
    if safe_body > 0:
        rejection = (upper_wick if is_buy else lower_wick) / safe_body
        penalty_wick = rejection * NYAO_WICK_WEIGHT

    # --- FINAL SCORE ---
    raw = trend_score + mom_score + chop_score + peak_score + vol_score - penalty_wick
    raw = max(0, min(10.0, raw))

    components = {
        "trend": round(trend_score, 2), "momentum": round(mom_score, 2),
        "impulse": round(raw_impulse, 3), "chop": round(chop_score, 2),
        "peak": round(peak_score, 2), "volatility": round(vol_score, 2),
        "wick_penalty": round(penalty_wick, 2), "vol_ratio": round(vol_ratio, 3),
        "rsi": round(rsi, 1), "ema_fast": round(ema_fast, 2), "ema_slow": round(ema_slow, 2),
    }
    return raw, components


def _compute_nyao_smoothed_score(candles: List[Dict], direction: str) -> Tuple[float, float, Dict]:
    """
    Nyao-style smoothed signal score with velocity tracking.
    Returns (smoothed_score 0-10, velocity, components).
    """
    N = min(NYAO_SMOOTH_N, 5)
    weighted_sum = 0.0
    weight_total = 0.0
    components = {}

    for i in range(1, N + 1):
        score_i, comp = _compute_nyao_raw_score(candles, direction, idx=i)
        if i == 1:  # use candle[1] components for reporting
            components = comp
        weight = float(N - i + 1)  # linear decay
        weighted_sum += score_i * weight
        weight_total += weight

    base_score = weighted_sum / weight_total if weight_total > 0 else 0
    current_score, _ = _compute_nyao_raw_score(candles, direction, idx=0)
    smoothed = base_score * (1.0 - NYAO_BLEND) + current_score * NYAO_BLEND
    smoothed = max(0, min(10.0, smoothed))

    # Velocity = score delta (would need prev_score from state — use 0 for first calc)
    velocity = 0.0  # will be tracked via _nyao_state

    return smoothed, velocity, components


_nyao_state: dict = {"buy_score": 0.0, "sell_score": 0.0, "last_bar": 0}


# Previous SL/TP engine function (line ~133)


class RiriScalpsStrategy(BaseStrategy):
    def __init__(self):
        meta = StrategyMetadata(
            id="riri_scalps_v1",
            name="RiriScalps",
            version="3.3.0",
            priority=95,
            author="Riri",
            description="v3.3: +Engine F (Nyao Score) + REMOVED Engine B. A(FVG)+C(Sweep)+D(RSI/MACD)+E1(VWAP)+E2(BB/RSI)+F(Nyao)"
        )
        super().__init__(meta)
        self._last_candle_key = None

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market
        candles_m5 = market_ctx.metadata.get("candles", {}).get("M5", [])
        candles_m15 = market_ctx.metadata.get("candles", {}).get("M15", [])

        # === EA PARITY (2026-09-08): skor dihitung di bar CLOSED saja ===
        # Gateway menyertakan bar forming sebagai elemen terakhir. EA (EnableNewBarEntryOnly)
        # mengevaluasi pada awal bar baru memakai candle yang sudah mati. Selama ini TIE
        # menghitung skor pada bar yang masih napas → entry muncul di menit yang EA diem
        # (bukti loss 19:12 -45.76 & 20:25 -30.76: keduanya TIE-only entries).
        import time as _time
        _nowts = _time.time()
        if candles_m5 and _nowts - float(candles_m5[-1].get("time", 0)) < 300:
            candles_m5 = candles_m5[:-1]
        if candles_m15 and _nowts - float(candles_m15[-1].get("time", 0)) < 900:
            candles_m15 = candles_m15[:-1]

        if len(candles_m5) < SWING_LOOKBACK + 5:
            return StrategyResult(signal=None, confidence=0.0, reason="low_data")

        price  = market_ctx.price or candles_m5[-1]["close"]
        atr    = market_ctx.atr or 2.0
        sym    = market_ctx.symbol
        z_score = market_ctx.vwap_z_score or 0.0

        # Balance for position sizing
        balance = market_ctx.metadata.get("balance", 500.0)

        # ── GLOBAL FILTER: M15 Trend ──
        trend_m15 = _get_m15_trend(candles_m15)

        # Session
        session = getattr(market_ctx, 'session', None) or market_ctx.metadata.get("session", "")
        is_london = str(session).upper() == "LONDON"

        # Pre-compute indicators for all engines
        closes = [float(c["close"]) for c in candles_m5]
        highs  = [float(c["high"]) for c in candles_m5]
        lows   = [float(c["low"]) for c in candles_m5]
        rsi_val = _compute_rsi(closes, RSI_PERIOD)
        macd_line, macd_signal, macd_hist = _compute_macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        adx_val = _compute_adx(highs, lows, closes, ADX_PERIOD)
        bb_upper, bb_mid, bb_lower = _compute_bollinger(closes, BB_PERIOD, BB_STD)
        vwap_val = _compute_vwap_from_candles(candles_m5[-30:])
        sh, sl_lvl = _swing_levels(candles_m5, SWING_LOOKBACK)

        # [NEW] Fresh S/R levels for structure-based SL/TP
        sr = _find_fresh_sr(candles_m5, price, atr, left=3, right=3)

        # Same-candle guard
        lc = candles_m5[-2]
        ckey = f"{lc['high']}_{lc['low']}_{lc['close']}"
        if ckey == getattr(self, "_last_candle_key", None):
            pass
        else:
            self._last_candle_key = ckey

        # ── EA_ONLY_MODE: engines A/C/D/E1/E2 disabled — only Engine F (Nyao port) trades ──
        if not EA_ONLY_MODE:
            # ── ENGINE A: Whale FVG (Imbalance) ── [UNCHANGED]
            avg_body = sum(body_size(c) for c in candles_m5[-11:-1]) / 10
            avg_vol  = sum(float(c.get("tick_volume", 1)) for c in candles_m5[-11:-1]) / 10
            spike_c  = candles_m5[-2]
            s_body   = body_size(spike_c)
            s_vol    = float(spike_c.get("tick_volume", 0))

            if s_body > (avg_body * 2.5) and s_vol > (avg_vol * VOL_SPIKE_RATIO):
                if is_bullish(spike_c) and trend_m15 == "BULL":
                    top = spike_c["open"] + s_body * 0.7
                    btm = spike_c["open"] + s_body * 0.3
                    if btm <= price <= top:
                        sl_s, tp_s = _get_sl_tp(Direction.BUY, price, sr, atr)
                        lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                        return self._emit(sym, Direction.BUY, price, 0.88, "A_whale_fvg_buy",
                                         sl_s, tp_s, market_ctx, lot)
                elif is_bearish(spike_c) and trend_m15 == "BEAR":
                    top = spike_c["open"] - s_body * 0.3
                    btm = spike_c["open"] - s_body * 0.7
                    if btm <= price <= top:
                        sl_s, tp_s = _get_sl_tp(Direction.SELL, price, sr, atr)
                        lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                        return self._emit(sym, Direction.SELL, price, 0.88, "A_whale_fvg_sell",
                                         sl_s, tp_s, market_ctx, lot)

            # ── ENGINE B: REMOVED — was B_struct_flow (Break + Retest), consistently lossy ──
            # Previous issues: duplicate entries, Z-Score false triggers, regime mismatch
            # User decision: remove entirely, keep A/C/D/E1/E2 only

            # ── ENGINE C: Liquidity Sweep (Wick Reject) ── [UNCHANGED]
            u_wick = float(spike_c["high"]) - max(float(spike_c["close"]), float(spike_c["open"]))
            l_wick = min(float(spike_c["close"]), float(spike_c["open"])) - float(spike_c["low"])

            if s_body > 0:
                if l_wick > WICK_BODY_RATIO * s_body and is_bullish(spike_c) and trend_m15 == "BULL":
                    if abs(price - sl_lvl) <= ENG_C_PROXIMITY * atr:
                        sl_s, tp_s = _get_sl_tp(Direction.BUY, price, sr, atr)
                        lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                        return self._emit(sym, Direction.BUY, price, 0.82, "C_liq_sweep_buy", sl_s, tp_s, market_ctx, lot)
                elif u_wick > WICK_BODY_RATIO * s_body and is_bearish(spike_c) and trend_m15 == "BEAR":
                    if abs(price - sh) <= ENG_C_PROXIMITY * atr:
                        sl_s, tp_s = _get_sl_tp(Direction.SELL, price, sr, atr)
                        lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                        return self._emit(sym, Direction.SELL, price, 0.82, "C_liq_sweep_sell", sl_s, tp_s, market_ctx, lot)

            # ── ENGINE D: RSI + MACD Confluence (from Fincept LIB-RSI-MACD) ── [NEW]
            # BUY: RSI < 45 AND MACD crosses above signal
            # SELL: RSI > 55 AND MACD crosses below signal
            prev_closes = closes[:-1]
            prev_macd_l, prev_macd_s, prev_hist = _compute_macd(prev_closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)

            if rsi_val < 45 and macd_hist > 0 and prev_hist <= 0:
                sl_s, tp_s = _get_sl_tp(Direction.BUY, price, sr, atr)
                lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                return self._emit(sym, Direction.BUY, price, 0.80, "D_rsi_macd_buy", sl_s, tp_s, market_ctx, lot)

            if rsi_val > 55 and macd_hist < 0 and prev_hist >= 0:
                sl_s, tp_s = _get_sl_tp(Direction.SELL, price, sr, atr)
                lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                return self._emit(sym, Direction.SELL, price, 0.80, "D_rsi_macd_sell", sl_s, tp_s, market_ctx, lot)

            # ── ENGINE E1: VWAP Cross (from Fincept LIB-VWAP-RECLAIM) ── [NEW]
            # BUY: price crosses above VWAP (prev candle below, current above)
            if len(candles_m5) >= 3:
                prev_close = float(candles_m5[-3]["close"])
                if prev_close < vwap_val and price > vwap_val and rsi_val < 55:
                    sl_s, tp_s = _get_sl_tp(Direction.BUY, price, sr, atr)
                    lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                    return self._emit(sym, Direction.BUY, price, 0.75, "E1_vwap_cross_buy", sl_s, tp_s, market_ctx, lot)

                if prev_close > vwap_val and price < vwap_val and rsi_val > 45:
                    sl_s, tp_s = _get_sl_tp(Direction.SELL, price, sr, atr)
                    lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                    return self._emit(sym, Direction.SELL, price, 0.75, "E1_vwap_cross_sell", sl_s, tp_s, market_ctx, lot)

            # ── ENGINE E2: Bollinger + RSI Mean Reversion (from Fincept LIB-BB-RSI) ── [NEW]
            # BUY: price < BB lower AND RSI < 30 (oversold bounce)
            if bb_lower > 0 and price < bb_lower and rsi_val < 30:
                sl_s, tp_s = _get_sl_tp(Direction.BUY, price, sr, atr)
                # Override TP to BB middle (mean reversion target)
                if bb_mid > price:
                    tp_s = bb_mid
                lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                return self._emit(sym, Direction.BUY, price, 0.78, "E2_bb_rsi_buy", sl_s, tp_s, market_ctx, lot)

            # SELL: price > BB upper AND RSI > 70 (overbought reversal)
            if bb_upper > 0 and price > bb_upper and rsi_val > 70:
                sl_s, tp_s = _get_sl_tp(Direction.SELL, price, sr, atr)
                # Override TP to BB middle (mean reversion target)
                if bb_mid < price:
                    tp_s = bb_mid
                lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                return self._emit(sym, Direction.SELL, price, 0.78, "E2_bb_rsi_sell", sl_s, tp_s, market_ctx, lot)

        # ── ENGINE F: Nyao Scalper Multi-Factor Score (adapted from Nyao v43) ── [NEW]
        # Composite signal quality score (0-10) — different approach from individual indicators.
        # Instead of requiring specific indicator matches, scores trend+momentum+volatility+breakout
        # independently. A strong trend can compensate for weak momentum, and vice versa.
        # Also includes dead-market filter (vol ratio < 0.6) and wick rejection penalty.
        # NEW-BAR ONLY: only evaluate on new M5 bar (like Nyao's EnableNewBarEntryOnly)
        nyao_bar_time = candles_m5[-2].get("time", 0) if len(candles_m5) >= 2 else 0
        if nyao_bar_time != _nyao_state.get("last_bar", 0):
            _nyao_state["last_bar"] = nyao_bar_time

            buy_score, buy_vel, buy_comp = _compute_nyao_smoothed_score(candles_m5, "BUY")
            sell_score, sell_vel, sell_comp = _compute_nyao_smoothed_score(candles_m5, "SELL")

            # Track velocity (score change from previous scan) — REPORTING ONLY.
            # EA v43 uses velocity for position sizing, NOT as an entry gate.
            prev_buy = _nyao_state.get("buy_score", 0.0)
            prev_sell = _nyao_state.get("sell_score", 0.0)
            buy_velocity = buy_score - prev_buy
            sell_velocity = sell_score - prev_sell
            _nyao_state["buy_score"] = buy_score
            _nyao_state["sell_score"] = sell_score

            # CONSECUTIVE CANDLE THRESHOLD ESCALATION (EA: ConsecutiveCandleThresholdBoost)
            # Raise threshold when recent bars already fired entries — prevents chasing
            # the move and entering at the peak of an extended candle run.
            _buy_thr = NYAO_SCORE_THRESHOLD + min(_nyao_state.get("consec_buy", 0), NYAO_MAX_CANDLE_BOOSTS) * NYAO_CONSEC_BOOST
            _sell_thr = NYAO_SCORE_THRESHOLD + min(_nyao_state.get("consec_sell", 0), NYAO_MAX_CANDLE_BOOSTS) * NYAO_CONSEC_BOOST

            # BUY: score >= threshold + buy dominates sell (EA gate: adjustedScore >= adjustedThreshold)
            _thr_buy = (not THRUST_FILTER) or _thrust_ok(candles_m5, True)
            if buy_score >= _buy_thr and buy_score > sell_score and not _thr_buy:
                logger.info(f"[NYAO] BUY score={buy_score:.2f} DIBLOCK thrust-filter (bar trigger/prev gak searah)")
            if buy_score >= _buy_thr and buy_score > sell_score and _thr_buy:
                _nyao_state["consec_buy"] = _nyao_state.get("consec_buy", 0) + 1
                _nyao_state["consec_sell"] = 0
                sl_s, tp_s = _get_sl_tp(Direction.BUY, price, sr, atr)
                lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                conf = min(0.90, 0.70 + buy_score * 0.02)
                logger.info(f"[NYAO] BUY score={buy_score:.2f} thr={_buy_thr:.1f} vel={buy_velocity:+.2f} comp={buy_comp}")
                res = self._emit(sym, Direction.BUY, price, conf, "F_nyao_buy",
                                 sl_s, tp_s, market_ctx, lot)
                res.metadata["nyao_score"] = buy_score   # for dampener penalty math
                res.metadata["nyao_thr"] = _buy_thr
                return res

            # SELL: score >= threshold + sell dominates buy
            _thr_sell = (not THRUST_FILTER) or _thrust_ok(candles_m5, False)
            if sell_score >= _sell_thr and sell_score > buy_score and not _thr_sell:
                logger.info(f"[NYAO] SELL score={sell_score:.2f} DIBLOCK thrust-filter (bar trigger/prev gak searah)")
            if sell_score >= _sell_thr and sell_score > buy_score and _thr_sell:
                _nyao_state["consec_sell"] = _nyao_state.get("consec_sell", 0) + 1
                _nyao_state["consec_buy"] = 0
                sl_s, tp_s = _get_sl_tp(Direction.SELL, price, sr, atr)
                lot = _calc_lot(balance, price, atr, abs(price - sl_s))
                conf = min(0.90, 0.70 + sell_score * 0.02)
                logger.info(f"[NYAO] SELL score={sell_score:.2f} thr={_sell_thr:.1f} vel={sell_velocity:+.2f} comp={sell_comp}")
                res = self._emit(sym, Direction.SELL, price, conf, "F_nyao_sell",
                                 sl_s, tp_s, market_ctx, lot)
                res.metadata["nyao_score"] = sell_score
                res.metadata["nyao_thr"] = _sell_thr
                return res

            # No entry this bar → decay escalation (EA resets when candle has no trade)
            _nyao_state["consec_buy"] = max(0, _nyao_state.get("consec_buy", 0) - 1)
            _nyao_state["consec_sell"] = max(0, _nyao_state.get("consec_sell", 0) - 1)

        return StrategyResult(signal=None, confidence=0.0, reason="no_setup")

    def _emit(self, sym, sig_dir, price, conf, reason, sl, tp, ctx, lot=0.05) -> StrategyResult:
        if lot <= 0:
            # [V-CAP] SL selebar itu gak muat di loss cap $4 — skip bersih, jangan kirim lot 0
            logger.info(f"[RIRI] SKIP {reason}: lot=0 (sl_dist={abs(price-sl):.2f} > loss cap)")
            return StrategyResult(signal=None, confidence=0.0, reason="cap_skip")
        sl_dist = abs(price - sl)
        min_tp = sl_dist * 1.5
        if tp > 0:
            if sig_dir == Direction.BUY:
                final_tp = max(tp, price + min_tp)  # BUY: TP above price, take larger (farther)
            else:
                # SELL: TP below price, take max (closest to price = safest target)
                target_floor = price - min_tp
                final_tp = max(tp, target_floor) if tp < price else target_floor
        else:
            final_tp = price + (min_tp if sig_dir == Direction.BUY else -min_tp)
        logger.info(f"[RIRI] {reason} at {price:.2f} SL={sl:.2f} TP={final_tp:.2f} lot={lot} (sl_dist={sl_dist:.2f})")
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
                "take_profit": final_tp,
                "volume": lot,
                "strategy_code": reason[0]  # A/B/C/D/E
            }
        )

    def observe(self, context: StrategyContext) -> None:
        pass

    def shutdown(self) -> None:
        _breakout_state.clear()
