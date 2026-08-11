"""
FVG Midpoint Detector V2 — Multi-TF Support (M5, M15).
Logic: Detect Fair Value Gaps and calculate Midpoint (Consequent Encroachment).
"""
import numpy as np
from typing import List, Dict, Optional

def detect_fvgs_from_candles(candles: List[Dict], min_gap_pts: float = 50.0) -> List[Dict]:
    """Finds FVGs in raw candle list."""
    fvgs = []
    if len(candles) < 3:
        return fvgs

    for i in range(2, len(candles)):
        c1 = candles[i-2] # Candle 1
        c3 = candles[i]   # Candle 3
        
        low3 = float(c3['low'])
        high1 = float(c1['high'])
        high3 = float(c3['high'])
        low1 = float(c1['low'])

        # Bullish FVG
        if low3 > high1:
            size = low3 - high1
            if size >= min_gap_pts:
                fvgs.append({
                    "type": "BULLISH",
                    "top": low3,
                    "bottom": high1,
                    "midpoint": (low3 + high1) / 2,
                    "size": size,
                    "index": i-1
                })
        
        # Bearish FVG
        elif high3 < low1:
            size = low1 - high3
            if size >= min_gap_pts:
                fvgs.append({
                    "type": "BEARISH",
                    "top": low1,
                    "bottom": high3,
                    "midpoint": (low1 + high3) / 2,
                    "size": size,
                    "index": i-1
                })
    return fvgs

def get_active_fvgs(context_candles: Dict[str, List[Dict]], tfs: List[str] = ["M5", "M15"]) -> Dict[str, List[Dict]]:
    """Scans multiple timeframes for FVGs."""
    results = {}
    # Thresholds: M5 (50 pts), M15 (100 pts)
    thresholds = {"M5": 50.0, "M15": 100.0}
    
    for tf in tfs:
        candles = context_candles.get(tf, [])
        if candles:
            results[tf] = detect_fvgs_from_candles(candles, min_gap_pts=thresholds.get(tf, 50.0))
    return results
