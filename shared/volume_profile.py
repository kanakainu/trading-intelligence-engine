"""Volume Profile — POC / Value Area confirmation layer.

Detects where "big money" traded (Point of Control) and the 70% Value Area.
Used as a QUALITY SCORE for entries, NOT a hard block (fail-open).

Logic:
- POC  = price level with max volume (M5)
- VAH  = upper edge of 70% value area
- VAL  = lower edge of 70% value area
- Entry near POC / inside value area → higher quality
- Entry in low-volume node → lower quality, but NEVER blocked

Toggle: config/features.json → volume_profile: true/false
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

_FEATURES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "features.json")
BINS = 30  # Price bins for volume histogram
VA_PCT = 0.70  # Value Area volume coverage


def _load_config() -> dict:
    try:
        with open(_FEATURES_PATH) as f:
            return json.load(f)
    except Exception:
        return {"volume_profile": True}


@dataclass
class VolumeProfileVerdict:
    allowed: bool
    quality_score: float  # 0.0-1.0 — entry quality from volume structure
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0
    reason: str = ""


def _bins(price_range: float, bin_count: int) -> float:
    return price_range / bin_count if bin_count else 0.0


def compute_profile(candles: List[dict]) -> Dict[str, float]:
    """Build volume histogram from M5 candles → POC/VAH/VAL."""
    if not candles:
        return {}
    lows = [float(c.get("low", 0)) for c in candles]
    highs = [float(c.get("high", 0)) for c in candles]
    vols = [float(c.get("tick_volume", c.get("volume", 0))) for c in candles]
    if not lows or not highs:
        return {}
    lo, hi = min(lows), max(highs)
    if hi <= lo:
        return {}
    bw = _bins(hi - lo, BINS)
    if bw <= 0:
        return {}
    # Histogram
    hist = [0.0] * BINS
    for l, h, v in zip(lows, highs, vols):
        # candle spans multiple bins — distribute volume
        i0 = int((l - lo) / bw)
        i1 = int((h - lo) / bw)
        i0 = max(0, min(BINS - 1, i0))
        i1 = max(0, min(BINS - 1, i1))
        per_bin = v / max(1, i1 - i0 + 1)
        for i in range(i0, i1 + 1):
            hist[i] += per_bin
    poc_idx = hist.index(max(hist))
    poc = lo + bw * (poc_idx + 0.5)
    # Value area — expand from POC until 70% volume covered
    total_vol = sum(hist)
    if total_vol <= 0:
        return {"poc": poc, "vah": hi, "val": lo}
    target = total_vol * VA_PCT
    acc = hist[poc_idx]
    lo_idx = hi_idx = poc_idx
    while acc < target and (lo_idx > 0 or hi_idx < BINS - 1):
        below = hist[lo_idx - 1] if lo_idx > 0 else -1
        above = hist[hi_idx + 1] if hi_idx < BINS - 1 else -1
        if below >= above:
            lo_idx -= 1
            acc += hist[lo_idx]
        else:
            hi_idx += 1
            acc += hist[hi_idx]
    vah = lo + bw * (hi_idx + 1)
    val = lo + bw * lo_idx
    return {"poc": poc, "vah": vah, "val": val}


def check(candles: Dict[str, List[dict]], price: float, direction: str) -> VolumeProfileVerdict:
    """Volume Profile confirmation. Fail-open — NEVER hard blocks."""
    cfg = _load_config()
    if not cfg.get("volume_profile", True):
        return VolumeProfileVerdict(True, 0.5, reason="volume_profile_disabled")

    m5 = candles.get("M5", [])
    if len(m5) < 10:
        return VolumeProfileVerdict(True, 0.5, reason="insufficient_candles_skip")

    prof = compute_profile(m5[-40:])
    if not prof or prof["poc"] <= 0:
        return VolumeProfileVerdict(True, 0.5, reason="flat_market_skip")

    poc, vah, val = prof["poc"], prof["vah"], prof["val"]
    if val <= 0 or vah <= poc:
        return VolumeProfileVerdict(True, 0.5, reason="invalid_profile_skip")

    # Quality scoring
    in_value_area = val <= price <= vah
    near_poc = abs(price - poc) / max(1e-9, (vah - val)) < 0.15
    score = 0.5
    if in_value_area:
        score += 0.25
    if near_poc:
        score += 0.25
    # Directional edge: BUY below POC (upside room), SELL above POC (downside room)
    if direction == "BUY" and price < poc:
        score += 0.1
    elif direction == "SELL" and price > poc:
        score += 0.1
    score = min(1.0, max(0.0, score))

    reason = f"poc={poc:.2f} vah={vah:.2f} val={val:.2f} score={score:.2f}"
    return VolumeProfileVerdict(True, score, poc, vah, val, reason)
