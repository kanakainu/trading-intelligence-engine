"""Shared Bystra utilities — candle analysis, engulfing, Danger Zone, HTF confirm.
All detectors import from here instead of duplicating.
"""
from typing import Any, Dict, List, Optional

TF_CHAIN = {
    "M5":  {"confirm": "M15", "bias": "H1"},
    "M15": {"confirm": "M30", "bias": "H1"},
}

# Per-pair structural buffer in price units (approx 1-2 pips + spread).
# XAUUSD: 1 pip = 0.1 USD. BTCUSD: 1 pip = 1.0 USD. GBPUSD: 1 pip = 0.0001.
PAIR_BUFFER = {
    "XAUUSD": 0.25,
    "BTCUSD": 25.0,
    "GBPUSD": 0.00025,
    "GBPJPY": 0.0025,
}

def sl_buffer(context, fallback: float = 0.25) -> float:
    """Structural buffer for context symbol. Falls back to spread_buffer (price units)
    when present, then per-pair default."""
    sym = str(getattr(context, "symbol", "") or "").upper()
    buf = PAIR_BUFFER.get(sym, fallback)
    sb = context.metadata.get("spread_buffer")
    if sb:
        buf = max(buf, float(sb))
    return buf

def get_candles(context, timeframe: str, count: int = 30) -> List[Dict]:
    """Legacy wrapper. Detectors should migrate to _get_candles on base."""
    return context.metadata.get("candles", {}).get(timeframe, [])[:count]


def is_bullish(c: Dict) -> bool:
    return float(c.get("close", 0)) > float(c.get("open", 0))

def is_bearish(c: Dict) -> bool:
    return float(c.get("close", 0)) < float(c.get("open", 0))

def body_size(c: Dict) -> float:
    return abs(float(c.get("close", 0)) - float(c.get("open", 0)))

def is_engulfing(prev: Dict, curr: Dict) -> str:
    p_open, p_close = float(prev.get("open",0)), float(prev.get("close",0))
    c_open, c_close = float(curr.get("open",0)), float(curr.get("close",0))
    p_high, p_low = max(p_open,p_close), min(p_open,p_close)
    c_high, c_low = max(c_open,c_close), min(c_open,c_close)
    if is_bullish(curr) and is_bearish(prev):
        return "bullish" if c_high >= p_high and c_low <= p_low else ""
    if is_bearish(curr) and is_bullish(prev):
        return "bearish" if c_high >= p_high and c_low <= p_low else ""
    return ""

# ── New Structural Swing S/R ────────────────────────────────────────────────

def _candle_val(c, k):
    """Safe candle value access — handles lowercase/uppercase/null keys."""
    if not isinstance(c, dict):
        return 0.0
    return float(c.get(k) or c.get(k.capitalize()) or c.get(k.upper()) or 0.0)

def find_swing_pivots(candles: List[Dict], n: int = 3) -> List[Dict]:
    """Find local pivot highs/lows where candle[i] is extreme of prev n and next n."""
    pivots = []
    for i in range(n, len(candles) - n):
        is_high = all(_candle_val(candles[i], "high") > _candle_val(candles[j], "high") for j in range(i-n, i)) and \
                  all(_candle_val(candles[i], "high") > _candle_val(candles[j], "high") for j in range(i+1, i+n+1))
        is_low = all(_candle_val(candles[i], "low") < _candle_val(candles[j], "low") for j in range(i-n, i)) and \
                 all(_candle_val(candles[i], "low") < _candle_val(candles[j], "low") for j in range(i+1, i+n+1))
        if is_high:
            pivots.append({"type": "high", "price": _candle_val(candles[i], "high"), "index": i})
        if is_low:
            pivots.append({"type": "low", "price": _candle_val(candles[i], "low"), "index": i})
    return pivots

def find_nearest_support(candles: List[Dict], price: float, htf_candles: List[Dict] = None) -> float:
    """Find nearest swing low below price. If htf_candles provided, use H1 pivots."""
    if htf_candles:
        pivots = find_swing_pivots(htf_candles)
    else:
        pivots = find_swing_pivots(candles)
    lows = [p["price"] for p in pivots if p["type"] == "low" and p["price"] < price]
    return max(lows) if lows else 0.0

def find_nearest_resistance(candles: List[Dict], price: float, htf_candles: List[Dict] = None) -> float:
    """Find nearest swing high above price. If htf_candles provided, use H1 pivots."""
    if htf_candles:
        pivots = find_swing_pivots(htf_candles)
    else:
        pivots = find_swing_pivots(candles)
    highs = [p["price"] for p in pivots if p["type"] == "high" and p["price"] > price]
    return min(highs) if highs else 999999.0

def danger_zone_touched(htf_candle: Dict, dz_level: float, direction: str) -> bool:
    """HTF candle body touches Danger Zone."""
    c_open, c_close = _candle_val(htf_candle, "open"), _candle_val(htf_candle, "close")
    body_min, body_max = min(c_open, c_close), max(c_open, c_close)
    if direction == "BUY":
        return body_max >= dz_level  # Resistance is DZ for BUY
    else:
        return body_min <= dz_level  # Support is DZ for SELL

def htf_confirm_solid(htf_candles: List[Dict], direction: str, dz_level: float) -> bool:
    """Engulfing solid (body >= 1.5x prev body) + HTF body NOT touching DZ."""
    if len(htf_candles) < 2: return False
    curr, prev = htf_candles[-1], htf_candles[-2]
    
    # Solid engulfing check
    is_solid = False
    if direction == "BUY":
        if is_bullish(curr) and body_size(curr) >= 1.5 * body_size(prev):
            is_solid = True
    else:
        if is_bearish(curr) and body_size(curr) >= 1.5 * body_size(prev):
            is_solid = True
            
    if not is_solid: return False
    
    # DZ check on candle body
    if danger_zone_touched(curr, dz_level, direction):
        return False
        
    return True

def get_base_zone(candles: List[Dict], index: int) -> Dict[str, float]:
    """Base zone is the high/low of the base candle."""
    return {
        "high": _candle_val(candles[index], "high"),
        "low": _candle_val(candles[index], "low")
    }

def check_retest(candles: List[Dict], base_zone: Dict[str, float], direction: str) -> bool:
    """Check if any recent candle (after breakout) touched the base zone."""
    curr = candles[-1]
    curr_low, curr_high = _candle_val(curr, "low"), _candle_val(curr, "high")
    
    if direction == "BUY":
        return curr_low <= base_zone["high"] and _candle_val(curr, "close") > base_zone["low"]
    else:
        return curr_high >= base_zone["low"] and _candle_val(curr, "close") < base_zone["high"]

# ── Legacy Pattern Detectors (backward compat) ──────────────────────────────

def detect_rbr(candles: List[Dict]) -> Optional[Dict]:
    """Rally → Base → Rally: swing high → pullback → break above base high."""
    if len(candles) < 5: return None
    for i in range(2, len(candles) - 2):
        h2, h1, h0 = _candle_val(candles[i-2], "high"), _candle_val(candles[i-1], "high"), _candle_val(candles[i], "high")
        if not (h2 < h1 and h0 < h1):
            continue
        base_high = float(candles[i].get("high", 0))
        base_low  = float(candles[i].get("low", 0))
        brk = candles[i+1]
        if float(brk.get("close", 0)) > base_high and is_bullish(brk):
            return {"base_high": base_high, "base_low": base_low, "entry": _candle_val(brk, "close")}
    return None

def detect_dbd(candles: List[Dict]) -> Optional[Dict]:
    """Drop → Base → Drop: swing low → pullback → break below base low."""
    if len(candles) < 5: return None
    for i in range(2, len(candles) - 2):
        l2, l1, l0 = _candle_val(candles[i-2], "low"), _candle_val(candles[i-1], "low"), _candle_val(candles[i], "low")
        if not (l2 > l1 and l0 > l1):
            continue
        base_high = float(candles[i].get("high", 0))
        base_low  = float(candles[i].get("low", 0))
        brk = candles[i+1]
        if float(brk.get("close", 0)) < base_low and is_bearish(brk):
            return {"base_high": base_high, "base_low": base_low, "entry": _candle_val(brk, "close")}
    return None

def detect_rbd(candles: list) -> dict:
    """Rally → Base → Drop."""
    if len(candles) < 5: return None
    for i in range(2, len(candles) - 2):
        h2, h1, h0 = _candle_val(candles[i-2], "high"), _candle_val(candles[i-1], "high"), _candle_val(candles[i], "high")
        if not (h2 < h1 and h0 < h1): continue
        base_high, base_low = _candle_val(candles[i], "high"), _candle_val(candles[i], "low")
        brk = candles[i+1]
        if _candle_val(brk, "close") < base_low and _candle_val(brk, "close") < _candle_val(brk, "open"):
            return {"base_high": base_high, "base_low": base_low}
    return None

def detect_dbr(candles: list) -> dict:
    """Drop → Base → Rally."""
    if len(candles) < 5: return None
    for i in range(2, len(candles) - 2):
        l2, l1, l0 = _candle_val(candles[i-2], "low"), _candle_val(candles[i-1], "low"), _candle_val(candles[i], "low")
        if not (l2 > l1 and l0 > l1): continue
        base_high, base_low = _candle_val(candles[i], "high"), _candle_val(candles[i], "low")
        brk = candles[i+1]
        if _candle_val(brk, "close") > base_high and _candle_val(brk, "close") > _candle_val(brk, "open"):
            return {"base_high": base_high, "base_low": base_low}
    return None

# ── Legacy functions kept for backward compat ───────────────────────────────

def htf_confirmation(htf_candles: List[Dict], direction: str) -> bool:
    """Legacy HTF confirmation."""
    if len(htf_candles) < 2: return False
    for i in range(1, min(3, len(htf_candles))):
        eng = is_engulfing(htf_candles[i-1], htf_candles[i])
        if direction == "BUY" and (eng == "bullish" or
                (is_bullish(htf_candles[i]) and body_size(htf_candles[i]) > body_size(htf_candles[i-1])*1.2)):
            return True
        if direction == "SELL" and (eng == "bearish" or
                (is_bearish(htf_candles[i]) and body_size(htf_candles[i]) > body_size(htf_candles[i-1])*1.2)):
            return True
    return False

def danger_zone_clear(context, direction: str, entry: float) -> bool:
    h1_sup = context.metadata.get("h1_support")
    h1_res = context.metadata.get("h1_resistance")
    if direction == "BUY" and h1_sup:
        return entry >= float(h1_sup) * (1 + 0.003)  # ZONE_TOLERANCE_PCT
    if direction == "SELL" and h1_res:
        return entry <= float(h1_res) * (1 - 0.003)
    return True

def near_strong_sr(context, direction: str, entry: float) -> bool:
    support = context.metadata.get("nearest_support")
    resistance = context.metadata.get("nearest_resistance")
    price = context.metadata.get("current_price", entry)
    if direction == "BUY" and support:
        return abs(float(price)-float(support))/float(support) < 0.003*2
    if direction == "SELL" and resistance:
        return abs(float(price)-float(resistance))/float(resistance) < 0.003*2
    return True

def ck_score(context, direction: str, base_conf: float) -> float:
    trendline_key = "trendline_bullish" if direction == "BUY" else "trendline_bearish"
    h1_trend = context.metadata.get("h1_trend", "")
    conf = base_conf
    if context.metadata.get(trendline_key):
        conf = 0.80
    if h1_trend == direction.lower():
        conf = min(conf + 0.05, 0.95)
    return min(conf, 0.95)

def is_strong_sr_broken(context, direction: str, price: float) -> bool:
    support = context.metadata.get("nearest_support")
    resistance = context.metadata.get("nearest_resistance")
    if direction == "SELL" and support: return price < float(support)
    if direction == "BUY" and resistance: return price > float(resistance)
    return False
