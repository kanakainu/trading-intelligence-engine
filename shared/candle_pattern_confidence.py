"""Candle pattern confidence — last 10 M5 candles. Not a filter, a helper.
Counts: engulfing, wick sweep (wick > body of prev candle), break high/low.
"""
from dataclasses import dataclass

@dataclass
class PatternConfidence:
    engulfing_count: int
    wick_sweep_count: int
    break_high_count: int
    break_low_count: int
    score: float  # 0-100, diagnostic only

def analyze(candles_m5: list, direction: str = "") -> PatternConfidence:
    """Last 10 M5 candles → pattern confidence. Direction optional for bias."""
    if len(candles_m5) < 11:
        return PatternConfidence(0, 0, 0, 0, 0.0)
    
    c = candles_m5[-11:]  # last 11 (need i-1)
    engulf = wick_sweep = break_h = break_l = 0
    
    for i in range(1, 11):
        curr = c[i]
        prev = c[i-1]
        o, h, l, cl = [curr.get(k, curr.get(k.capitalize(), 0)) for k in ("open","high","low","close")]
        po, ph, pl, pc = [prev.get(k, prev.get(k.capitalize(), 0)) for k in ("open","high","low","close")]
        
        # Engulfing
        bullish_eng = cl > o and cl > max(po, pc) and o < min(po, pc)
        bearish_eng = cl < o and cl < min(po, pc) and o > max(po, pc)
        if bullish_eng or bearish_eng:
            engulf += 1
        
        # Wick sweep (wick eats prev body)
        prev_body = abs(pc - po)
        upper_wick = h - max(o, cl)
        lower_wick = min(o, cl) - l
        if upper_wick > prev_body or lower_wick > prev_body:
            wick_sweep += 1
        
        # Break high/low
        if h > ph:
            break_h += 1
        if l < pl:
            break_l += 1
    
    # Score: weighted sum, directional bias if provided
    score = engulf * 15 + wick_sweep * 10 + break_h * 5 + break_l * 5
    if direction == "BUY":
        score += (break_h - break_l) * 5  # favor upward breaks
    elif direction == "SELL":
        score += (break_l - break_h) * 5
    score = min(100.0, max(0.0, score))
    
    return PatternConfidence(engulf, wick_sweep, break_h, break_l, round(score, 1))


if __name__ == "__main__":
    fake = [{"open":100+i, "high":102+i, "low":99+i, "close":101+i} for i in range(11)]
    r = analyze(fake, "BUY")
    assert r.break_high_count > 0
    print("candle_pattern_confidence OK")
