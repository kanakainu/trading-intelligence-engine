"""Divergence Detector — RSI divergence on M5 (confirmation layer).

Detects classic RSI divergence between last two swing points:
- Bearish divergence: price HH (higher high) + RSI LH (lower high) → SELL confirm
- Bullish divergence:  price LL (lower low)  + RSI HL (higher low)  → BUY confirm

Used as CONFIRMATION only — fail-open, NEVER hard blocks entries.
Entry direction aligned with divergence → bonus quality.
Entry against divergence → quality penalty, but entry still allowed.

Toggle: config/features.json → divergence_detector: true/false
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

_FEATURES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "features.json")
RSI_PERIOD = 14
SWING_MIN = 3  # candles each side for swing point confirmation


def _load_config() -> dict:
    try:
        with open(_FEATURES_PATH) as f:
            return json.load(f)
    except Exception:
        return {"divergence_detector": True}


@dataclass
class DivergenceVerdict:
    allowed: bool
    divergence: bool  # divergence exists
    direction_aligned: bool  # divergence supports entry direction
    kind: str = ""  # "bullish" / "bearish"
    quality_score: float = 0.5
    reason: str = ""


def _rsi(closes: List[float], period: int = RSI_PERIOD) -> List[float]:
    """Classic Wilder RSI."""
    if len(closes) < period + 1:
        return []
    gains, losses = [], []
    for i in range(1, len(closes)):
        chg = closes[i] - closes[i - 1]
        gains.append(max(0, chg))
        losses.append(max(0, -chg))
    # Wilder smoothing
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi = [0.0] * len(closes)
    for i in range(period, len(closes)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        rsi[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return rsi


def _find_swings(closes: List[float], prices: List[float], min_bars: int = SWING_MIN) -> List[dict]:
    """Find swing highs/lows (fractal style)."""
    swings = []
    for i in range(min_bars, len(closes) - min_bars):
        left = closes[i - min_bars:i]
        right = closes[i + 1:i + 1 + min_bars]
        if not left or not right:
            continue
        if closes[i] == max(left + [closes[i]] + right):
            swings.append({"idx": i, "type": "high", "price": prices[i], "rsi": closes[i]})
        if closes[i] == min(left + [closes[i]] + right):
            swings.append({"idx": i, "type": "low", "price": prices[i], "rsi": closes[i]})
    return swings


def check(candles: Dict[str, List[dict]], direction: str) -> DivergenceVerdict:
    """RSI divergence confirmation. Fail-open — NEVER hard blocks."""
    cfg = _load_config()
    if not cfg.get("divergence_detector", True):
        return DivergenceVerdict(True, False, False, reason="divergence_disabled")

    m5 = candles.get("M5", [])
    if len(m5) < RSI_PERIOD + SWING_MIN * 2 + 5:
        return DivergenceVerdict(True, False, False, reason="insufficient_candles_skip")

    closes = [float(c.get("close", 0)) for c in m5]
    prices = [float(c.get("close", 0)) for c in m5]
    rsi = _rsi(closes)
    if len(rsi) != len(closes):
        return DivergenceVerdict(True, False, False, reason="rsi_calc_skip")

    # RSI series as "closes" for swing detection
    swings = _find_swings(rsi, prices)
    if len(swings) < 2:
        return DivergenceVerdict(True, False, False, reason="no_swings_skip")

    # Last two same-type swings
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]
    div = False
    kind = ""
    aligned = False

    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        # Price HH + RSI LH → bearish divergence
        if b["price"] > a["price"] and b["rsi"] < a["rsi"]:
            div = True
            kind = "bearish"
            aligned = direction == "SELL"
    if len(lows) >= 2 and not div:
        a, b = lows[-2], lows[-1]
        # Price LL + RSI HL → bullish divergence
        if b["price"] < a["price"] and b["rsi"] > a["rsi"]:
            div = True
            kind = "bullish"
            aligned = direction == "BUY"

    score = 0.65 if (div and aligned) else (0.35 if div else 0.5)
    reason = f"kind={kind} div={div} aligned={aligned}" if div else "no_divergence"
    return DivergenceVerdict(True, div, aligned, kind, score, reason)
