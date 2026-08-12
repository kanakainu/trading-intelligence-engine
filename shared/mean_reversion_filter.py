"""Mean-Reversion Filter — Combo GS Quant (Z-Score) + Boskuh (Wick Spike).

Logic:
1. Wick Spike Rejection (Boskuh): 
   - BUY: low[0] < low[1] and close[0] > low[1]
   - SELL: high[0] > high[1] and close[0] < high[1]
2. Z-Score (GS): Checks if price is at statistical extremes.

Used as a confirmation gate for all strategies.
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

_FEATURES_PATH = "/home/ubuntu/trading-intelligence-engine/config/features.json"

@dataclass
class MeanRevVerdict:
    allowed: bool
    reason: str
    z_score: float = 0.0
    is_spike: bool = False

def _load_config() -> dict:
    try:
        with open(_FEATURES_PATH) as f:
            return json.load(f)
    except Exception:
        return {"mean_reversion_filter": True}

def check(features: Any, candles: Dict[str, List[dict]], direction: str) -> MeanRevVerdict:
    cfg = _load_config()
    if not cfg.get("mean_reversion_filter", True):
        return MeanRevVerdict(True, "mean_rev_disabled")

    m5 = candles.get("M5", [])
    if len(m5) < 3:
        return MeanRevVerdict(True, "insufficient_candles")

    # 1. Wick Spike Rejection (Boskuh Logic)
    c0 = m5[-1]  # Current
    c1 = m5[-2]  # Previous
    
    is_spike = False
    if direction == "BUY":
        # Price spikes below prev low but closes above it
        if float(c0["low"]) < float(c1["low"]) and float(c0["close"]) > float(c1["low"]):
            is_spike = True
    elif direction == "SELL":
        # Price spikes above prev high but closes below it
        if float(c0["high"]) > float(c1["high"]) and float(c0["close"]) < float(c1["high"]):
            is_spike = True

    # 2. Z-Score (GS Quant Logic)
    window = 20
    closes = [float(c["close"]) for c in m5[-window:]]
    mean = sum(closes) / len(closes)
    std = (sum((c - mean) ** 2 for c in closes) / len(closes)) ** 0.5
    z = (float(c0["close"]) - mean) / std if std > 0 else 0

    # Decision Logic:
    # If it's a spike rejection -> ALWAYS ALLOW (Powerful signal)
    if is_spike:
        return MeanRevVerdict(True, f"spike_rejection_confirm z={z:.2f}", z, True)

    # If no spike, but it's a mean-reversion setup (like Bystra), check Z-Score
    # (Optional refinement: block if chasing trend at extreme Z)
    if direction == "BUY" and z > 2.5: # Overbought extreme
        return MeanRevVerdict(False, f"overextended_no_spike_buy_blocked z={z:.2f}", z, False)
    if direction == "SELL" and z < -2.5: # Oversold extreme
        return MeanRevVerdict(False, f"overextended_no_spike_sell_blocked z={z:.2f}", z, False)

    return MeanRevVerdict(True, f"mean_rev_ok z={z:.2f}", z, False)
