"""LocationEngine — is this a good location to enter?
BAD_LOCATION = NO TRADE regardless of score.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict


class LocationGrade(str, Enum):
    GOOD    = "GOOD"
    NEUTRAL = "NEUTRAL"
    BAD     = "BAD"


def _get(c: Dict, *keys, default=0.0) -> float:
    for k in keys:
        v = c.get(k)
        if v is not None:
            try: return float(v)
            except (ValueError, TypeError): pass
    return default


@dataclass
class LocationResult:
    grade:                   LocationGrade
    distance_to_structure_atr: float   # dist to nearest support/resistance / atr
    distance_to_obstacle_atr:  float   # dist to nearest opposing structure / atr
    available_room_atr:        float   # room toward TP / atr
    vwap_distance_atr:         float
    reason:                  str
    score:                   float     # 0–25


def evaluate(
    direction:    str,          # "BUY" | "SELL"
    entry_price:  float,
    candles_m5:   List[Dict],
    candles_m15:  List[Dict],
    atr:          float,
    tp_price:     float = 0.0,
) -> LocationResult:
    if atr <= 0 or not candles_m5:
        return LocationResult(LocationGrade.NEUTRAL, 0, 0, 0, 0, "no_atr", 10.0)

    cs5 = [c for c in candles_m5[-20:] if c]
    highs = [_get(c, "high", "High") for c in cs5]
    lows  = [_get(c, "low",  "Low")  for c in cs5]

    if not highs or not lows:
        return LocationResult(LocationGrade.NEUTRAL, 0, 0, 0, 0, "no_candles", 10.0)

    recent_high = max(highs[-10:])
    recent_low  = min(lows[-10:])

    # VWAP from M5
    closes = [_get(c, "close", "Close") for c in cs5]
    vwap = sum(closes) / len(closes) if closes else entry_price
    vwap_dist = abs(entry_price - vwap) / atr

    if direction == "BUY":
        dist_to_support    = (entry_price - recent_low) / atr    # lower = better
        dist_to_resistance = (recent_high - entry_price) / atr   # higher = better (room)
        available_room     = dist_to_resistance
        dist_structure     = dist_to_support
        dist_obstacle      = dist_to_resistance

        # BAD: no room above (resistance too close) OR extended too far above support
        if dist_to_resistance < 1.0:
            return LocationResult(LocationGrade.BAD, dist_structure, dist_obstacle,
                                  available_room, vwap_dist,
                                  f"resistance_too_close={dist_to_resistance:.2f}ATR", 0.0)
        if dist_to_support > 2.5:
            return LocationResult(LocationGrade.BAD, dist_structure, dist_obstacle,
                                  available_room, vwap_dist,
                                  f"too_far_from_support={dist_to_support:.2f}ATR", 0.0)
        # GOOD: near support + room above
        if dist_to_support <= 1.0 and dist_to_resistance >= 1.5:
            score = min(25.0, 25.0 - dist_to_support * 5)
            return LocationResult(LocationGrade.GOOD, dist_structure, dist_obstacle,
                                  available_room, vwap_dist,
                                  f"near_support={recent_low:.2f}", score)

    else:  # SELL
        dist_to_resistance = (recent_high - entry_price) / atr   # lower = better
        dist_to_support    = (entry_price - recent_low) / atr    # higher = better (room)
        available_room     = dist_to_support
        dist_structure     = dist_to_resistance
        dist_obstacle      = dist_to_support

        if dist_to_support < 1.0:
            return LocationResult(LocationGrade.BAD, dist_structure, dist_obstacle,
                                  available_room, vwap_dist,
                                  f"support_too_close={dist_to_support:.2f}ATR", 0.0)
        if dist_to_resistance > 2.5:
            return LocationResult(LocationGrade.BAD, dist_structure, dist_obstacle,
                                  available_room, vwap_dist,
                                  f"too_far_from_resistance={dist_to_resistance:.2f}ATR", 0.0)
        if dist_to_resistance <= 1.0 and dist_to_support >= 1.5:
            score = min(25.0, 25.0 - dist_to_resistance * 5)
            return LocationResult(LocationGrade.GOOD, dist_structure, dist_obstacle,
                                  available_room, vwap_dist,
                                  f"near_resistance={recent_high:.2f}", score)

    return LocationResult(LocationGrade.NEUTRAL, dist_structure if direction == "BUY" else dist_to_resistance,
                          dist_obstacle, available_room, vwap_dist, "neutral_zone", 12.0)
