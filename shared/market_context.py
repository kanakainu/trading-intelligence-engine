from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import List

class Regime(Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGING = "RANGING"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"

class StructureBias(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

@dataclass
class MarketContext:
    regime: Regime
    m15_bias: StructureBias
    m5_structure: StructureBias
    vwap_distance_atr: float
    atr: float
    price: float
    timestamp: datetime

def build(candles_m15: List[dict], candles_m5: List[dict], candles_m1: List[dict], current_price: float, atr_m5: float) -> MarketContext:
    # M15 bias: last 3 candles, if 2/3 bullish (close > open) -> BULLISH, else BEARISH, else NEUTRAL
    # ponytail: simplified 2/3 logic.
    m15_subset = candles_m15[-3:]
    bullish_count = sum(1 for c in m15_subset if c['close'] > c['open'])
    bearish_count = sum(1 for c in m15_subset if c['close'] < c['open'])
    
    if bullish_count >= 2:
        m15_bias = StructureBias.BULLISH
    elif bearish_count >= 2:
        m15_bias = StructureBias.BEARISH
    else:
        m15_bias = StructureBias.NEUTRAL

    # M5 structure: last 5 candles higher highs + higher lows = BULLISH, lower lows + lower highs = BEARISH, else NEUTRAL
    m5_subset = candles_m5[-5:]
    if len(m5_subset) < 5:
        m5_structure = StructureBias.NEUTRAL
    else:
        hh = all(m5_subset[i]['high'] >= m5_subset[i-1]['high'] for i in range(1, 5))
        hl = all(m5_subset[i]['low'] >= m5_subset[i-1]['low'] for i in range(1, 5))
        ll = all(m5_subset[i]['low'] <= m5_subset[i-1]['low'] for i in range(1, 5))
        lh = all(m5_subset[i]['high'] <= m5_subset[i-1]['high'] for i in range(1, 5))
        
        if hh and hl:
            m5_structure = StructureBias.BULLISH
        elif ll and lh:
            m5_structure = StructureBias.BEARISH
        else:
            m5_structure = StructureBias.NEUTRAL

    # Regime logic
    if m15_bias == StructureBias.BULLISH and m5_structure == StructureBias.BULLISH:
        regime = Regime.TRENDING_BULL
    elif m15_bias == StructureBias.BEARISH and m5_structure == StructureBias.BEARISH:
        regime = Regime.TRENDING_BEAR
    elif m15_bias == StructureBias.NEUTRAL and m5_structure == StructureBias.NEUTRAL:
        regime = Regime.RANGING
    else:
        regime = Regime.TRANSITION

    # vwap_distance_atr: abs(price - vwap) / atr. vwap = mean of M5 closes.
    m5_closes = [c['close'] for c in candles_m5]
    vwap = sum(m5_closes) / len(m5_closes) if m5_closes else current_price
    vwap_distance_atr = abs(current_price - vwap) / atr_m5 if atr_m5 > 0 else 0.0

    return MarketContext(
        regime=regime,
        m15_bias=m15_bias,
        m5_structure=m5_structure,
        vwap_distance_atr=vwap_distance_atr,
        atr=atr_m5,
        price=current_price,
        timestamp=datetime.now()
    )
