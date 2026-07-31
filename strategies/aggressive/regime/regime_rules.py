"""Aggressive Regime Rules — thresholds."""

# Trend classification
STRONG_TREND_ADX = 25
WEAK_TREND_ADX = 20
RANGING_ADX = 15

# Volatility bands
HIGH_VOLATILITY_ATR_PCT = 0.02
LOW_VOLATILITY_ATR_PCT = 0.005

# EMA slope threshold (change per period)
STRONG_SLOPE_THRESHOLD = 0.0005

# Liquidity proxy (volume ratio vs MA)
LOW_LIQUIDITY_VOLUME_RATIO = 0.7
