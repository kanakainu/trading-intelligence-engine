"""
Trendline Break Detector — Ported from XAU-60 logic for TIE SemiHFT.
PURE NUMPY VERSION (No Pandas dependency for runtime safety).
"""
import numpy as np
from typing import List, Dict, Optional, Tuple

def detect_trendline_break(candles: List[Dict], atr: float, min_touches: int = 3, lookback: int = 20) -> Tuple[bool, Optional[str]]:
    """
    Detects if current price has broken a valid trendline (Bullish or Bearish).
    Returns (is_break, direction) where direction is "BUY" or "SELL" or None.
    Requires ATR for dynamic tolerance.
    """
    if len(candles) < lookback + min_touches:
        return False, None

    highs = np.array([float(c["high"]) for c in candles])
    lows = np.array([float(c["low"]) for c in candles])
    closes = np.array([float(c["close"]) for c in candles])

    current_price = closes[-1]
    
    # Dynamic tolerance based on ATR
    break_tolerance = 0.2 * atr # 20% of ATR for a valid break

    # --- Detect Swing Highs/Lows (simplified 3-candle pivot) ---
    # Find swing highs
    swing_high_indices = []
    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            swing_high_indices.append(i)
    
    # Find swing lows
    swing_low_indices = []
    for i in range(1, len(lows) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            swing_low_indices.append(i)

    # --- Detect Trendline Breaks ---
    is_break = False
    direction: Optional[str] = None

    # Check for Bearish Trendline Break (price breaking above descending trendline)
    valid_desc_tls = []
    for i in range(len(swing_high_indices)):
        for j in range(i + 1, len(swing_high_indices)):
            p1_idx = swing_high_indices[i]
            p2_idx = swing_high_indices[j]
            if p2_idx - p1_idx < min_touches: continue # Need enough distance for touches

            # Line equation y = mx + b
            x1, y1 = p1_idx, highs[p1_idx]
            x2, y2 = p2_idx, highs[p2_idx]
            
            if x2 == x1: continue
            m = (y2 - y1) / (x2 - x1)
            b = y1 - m * x1

            # Only consider descending lines for bearish trendlines
            if m >= 0: continue

            # Check for touches (simplified: if candles are near the line)
            touches = 0
            for k in range(p1_idx, p2_idx + 1):
                line_val = m * k + b
                if abs(highs[k] - line_val) <= break_tolerance:
                    touches += 1
            
            if touches >= min_touches:
                # Check if current price broke above the line
                predicted_line_val_at_current = m * (len(candles) - 1) + b
                if current_price > predicted_line_val_at_current + break_tolerance:
                    is_break = True
                    direction = "BUY"
                    valid_desc_tls.append((m, b))
                    break # Found a valid break, no need to check others
        if is_break: break

    if is_break: # Already found a break, return
        return is_break, direction

    # Check for Bullish Trendline Break (price breaking below ascending trendline)
    valid_asc_tls = []
    for i in range(len(swing_low_indices)):
        for j in range(i + 1, len(swing_low_indices)):
            p1_idx = swing_low_indices[i]
            p2_idx = swing_low_indices[j]
            if p2_idx - p1_idx < min_touches: continue

            # Line equation y = mx + b
            x1, y1 = p1_idx, lows[p1_idx]
            x2, y2 = p2_idx, lows[p2_idx]

            if x2 == x1: continue
            m = (y2 - y1) / (x2 - x1)
            b = y1 - m * x1

            # Only consider ascending lines for bullish trendlines
            if m <= 0: continue

            # Check for touches (simplified)
            touches = 0
            for k in range(p1_idx, p2_idx + 1):
                line_val = m * k + b
                if abs(lows[k] - line_val) <= break_tolerance:
                    touches += 1
            
            if touches >= min_touches:
                # Check if current price broke below the line
                predicted_line_val_at_current = m * (len(candles) - 1) + b
                if current_price < predicted_line_val_at_current - break_tolerance:
                    is_break = True
                    direction = "SELL"
                    valid_asc_tls.append((m, b))
                    break # Found a valid break, no need to check others
        if is_break: break

    return is_break, direction


if __name__ == "__main__":
    # Simple Test Cases
    test_candles_bullish_break = [
        {"high": 10.0, "low": 9.0, "close": 9.5},  # 0
        {"high": 11.0, "low": 9.5, "close": 10.5}, # 1
        {"high": 10.5, "low": 9.8, "close": 10.0}, # 2 (Swing High 1)
        {"high": 11.5, "low": 10.0, "close": 11.0}, # 3
        {"high": 10.8, "low": 10.2, "close": 10.5}, # 4 (Swing High 2)
        {"high": 12.0, "low": 10.5, "close": 11.5}, # 5
        {"high": 11.2, "low": 10.7, "close": 11.0}, # 6 (Swing High 3)
        {"high": 13.0, "low": 11.5, "close": 12.5}, # 7 (Break above trendline from 2,4,6)
        {"high": 14.0, "low": 12.0, "close": 13.5}, # 8
    ]
    # ATR for testing
    test_atr = 0.5

    print("--- Testing Bullish Break ---")
    break_status, brk_dir = detect_trendline_break(test_candles_bullish_break, test_atr)
    print(f"Break: {break_status}, Direction: {brk_dir}") # Expected: True, BUY
    assert break_status is True and brk_dir == "BUY", "Bullish break not detected correctly"

    test_candles_bearish_break = [
        {"high": 15.0, "low": 14.0, "close": 14.5}, # 0
        {"high": 14.5, "low": 13.5, "close": 14.0}, # 1
        {"high": 14.0, "low": 13.0, "close": 13.5}, # 2 (Swing Low 1)
        {"high": 13.5, "low": 12.5, "close": 13.0}, # 3
        {"high": 13.0, "low": 12.0, "close": 12.5}, # 4 (Swing Low 2)
        {"high": 12.5, "low": 11.5, "close": 12.0}, # 5
        {"high": 12.0, "low": 11.0, "close": 11.5}, # 6 (Swing Low 3)
        {"high": 10.0, "low": 9.0, "close": 9.5},   # 7 (Break below trendline from 2,4,6)
        {"high": 8.0, "low": 7.0, "close": 7.5},    # 8
    ]

    print("\n--- Testing Bearish Break ---")
    break_status, brk_dir = detect_trendline_break(test_candles_bearish_break, test_atr)
    print(f"Break: {break_status}, Direction: {brk_dir}") # Expected: True, SELL
    assert break_status is True and brk_dir == "SELL", "Bearish break not detected correctly"

    test_candles_no_break = [
        {"high": 10.0, "low": 9.0, "close": 9.5}, # 0
        {"high": 10.1, "low": 9.1, "close": 9.6}, # 1
        {"high": 10.2, "low": 9.2, "close": 9.7}, # 2
        {"high": 10.3, "low": 9.3, "close": 9.8}, # 3
        {"high": 10.4, "low": 9.4, "close": 9.9}, # 4
        {"high": 10.5, "low": 9.5, "close": 10.0}, # 5
        {"high": 10.6, "low": 9.6, "close": 10.1}, # 6
        {"high": 10.7, "low": 9.7, "close": 10.2}, # 7
        {"high": 10.8, "low": 9.8, "close": 10.3}, # 8
    ]
    print("\n--- Testing No Break (Flat) ---")
    break_status, brk_dir = detect_trendline_break(test_candles_no_break, test_atr)
    print(f"Break: {break_status}, Direction: {brk_dir}") # Expected: False, None
    assert break_status is False and brk_dir is None, "No break not detected correctly"

    print("\nAll tests passed!")
