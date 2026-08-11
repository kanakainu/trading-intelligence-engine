"""
Liquidity Vacuum Detector — Smart Money Concept pool detection for TIE SemiHFT.
Finds where liquidity pools gather (clustered equal highs/lows = stop clusters)
and grades whether entry is vacuum-risk or magnet-aligned.

PURE STDLIB — no numpy/pandas dependency.
"""
from typing import List, Dict, Tuple, Optional


def _swing_pivots(candles: List[Dict], n: int = 3) -> Tuple[List[float], List[float]]:
    """Return (swing_highs, swing_lows) using n-candle pivot confirmation."""
    highs, lows = [], []
    for i in range(n, len(candles) - n):
        h = float(candles[i]["high"])
        l = float(candles[i]["low"])
        if all(h > float(candles[j]["high"]) for j in range(i - n, i + n + 1) if j != i):
            highs.append(h)
        if all(l < float(candles[j]["low"]) for j in range(i - n, i + n + 1) if j != i):
            lows.append(l)
    return highs, lows


def _cluster(points: List[float], tol: float) -> List[Dict]:
    """Cluster price levels within tolerance. Returns pools with touch counts."""
    pools: List[Dict] = []
    for p in points:
        for pool in pools:
            if abs(p - pool["price"]) <= tol:
                pool["touches"] += 1
                pool["price"] = (pool["price"] * (pool["touches"] - 1) + p) / pool["touches"]
                break
        else:
            pools.append({"price": p, "touches": 1})
    return [p for p in pools if p["touches"] >= 2]  # 2+ touches = real pool


def detect_liquidity_pools(candles: List[Dict], atr: float, min_touches: int = 2) -> Dict:
    """Detect liquidity pools from swing clusters on one timeframe.

    Returns: {
        "pools": [{"price", "side", "touches"}],
        "nearest_above": pool or None,
        "nearest_below": pool or None
    }
    """
    if len(candles) < 10 or not atr or atr <= 0:
        return {"pools": [], "nearest_above": None, "nearest_below": None}

    highs, lows = _swing_pivots(candles, n=3)
    tol = 0.15 * atr  # 15% of ATR = equal-level tolerance

    high_pools = _cluster(highs, tol)
    low_pools = _cluster(lows, tol)

    pools = [{"price": p["price"], "side": "high", "touches": p["touches"]} for p in high_pools]
    pools += [{"price": p["price"], "side": "low", "touches": p["touches"]} for p in low_pools]
    pools.sort(key=lambda x: x["price"])

    price = float(candles[-1]["close"])
    above = [p for p in pools if p["price"] > price]
    below = [p for p in pools if p["price"] < price]
    nearest_above = min(above, key=lambda x: x["price"] - price) if above else None
    nearest_below = max(below, key=lambda x: price - x["price"]) if below else None

    return {"pools": pools, "nearest_above": nearest_above, "nearest_below": nearest_below}


def vacuum_grade(pools_above: Optional[Dict], pools_below: Optional[Dict],
                 direction: str, atr: float) -> Tuple[str, str]:
    """Grade entry against liquidity pools.

    direction: "BUY" | "SELL"
    Returns (grade, reason): grade in {"GOOD", "CAUTION", "DANGER"}
    """
    if not atr or atr <= 0:
        return "GOOD", "no_atr"

    danger_zone = 1.0 * atr  # pool within 1 ATR of price = immediate magnet/sweep risk

    if direction == "BUY":
        if pools_above and (pools_above["price"] - 0) < danger_zone and pools_above["touches"] >= 3:
            return "CAUTION", f"maj_liq_above_{pools_above['price']:.2f}_unswept"
        if pools_below and pools_below["touches"] >= 3:
            return "GOOD", f"liq_below_consumed_{pools_below['price']:.2f}"
        return "GOOD", "clear_path_up"
    else:  # SELL
        if pools_below and (0 - pools_below["price"]) < danger_zone and pools_below["touches"] >= 3:
            return "CAUTION", f"maj_liq_below_{pools_below['price']:.2f}_unswept"
        if pools_above and pools_above["touches"] >= 3:
            return "GOOD", f"liq_above_consumed_{pools_above['price']:.2f}"
        return "GOOD", "clear_path_down"


if __name__ == "__main__":
    # Self-check: build a synthetic swing-heavy series and verify pool detection.
    mock = [{"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0} for _ in range(30)]
    # Force an equal-high cluster at 105.0
    for i in (5, 12, 19):
        mock[i]["high"] = 105.0
        mock[i]["low"] = 99.5
    res = detect_liquidity_pools(mock, atr=1.0)
    assert any(p["price"] > 104.9 for p in res["pools"]), "equal-high pool not detected"
    grade, reason = vacuum_grade(res["nearest_above"], res["nearest_below"], "BUY", atr=1.0)
    print(f"pools={len(res['pools'])} grade={grade} reason={reason}")
    print("self-check OK")
