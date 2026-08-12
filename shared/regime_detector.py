import logging
from enum import Enum
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("regime_detector")

class MarketRegime(Enum):
    TRENDING      = "TRENDING"       # legacy compat
    TRENDING_BULL = "TRENDING_BULL"  # strong bullish momentum
    TRENDING_BEAR = "TRENDING_BEAR"  # strong bearish momentum
    RANGING       = "RANGING"        # no clear direction
    CHOPPY        = "CHOPPY"         # squeeze / dead market
    CHAOS         = "CHAOS"          # extreme volatility — unsafe

@dataclass
class RegimeSnapshot:
    regime: MarketRegime
    strength: float         # 0-100
    adx: float
    bb_bandwidth: float
    vol_percentile: str
    suggested_engine: str   # Aggressive | SemiHFT | Hibernate

class RegimeDetector:
    """
    Automatic Market Regime Detector for TIE V4 (Nexus A12 style).
    Uses TIE FeatureSnapshot native scales:
      - momentum_score: -1..+1 (body_ratio * direction, last candle)
      - atr_percent: ATR/price ratio (M5 XAUUSD normal ~0.05-0.09)
      - distance_to_vwap: absolute price distance from VWAP

    Calibration verified live 2026-08-10:
      M5 atr% normal = 0.05-0.09. Strong momentum = |mom| > 0.25.
    """
    # TIE-native thresholds (calibrated against live feature dump)
    MOMENTUM_STRONG = 0.25      # |momentum| >= 0.25 = clear directional move
    MOMENTUM_NEUTRAL = 0.10     # |momentum| < 0.10 = no direction
    ATR_PCT_CHAOS = 0.20        # atr% >= 0.20 = dangerous volatility
    ATR_PCT_SQUEEZE = 0.05      # atr% < 0.05 = dead/squeeze market

    def detect(self, features: Any) -> RegimeSnapshot:
        # Extract TIE-native features
        momentum = 0.0
        if hasattr(features, "momentum_score") and isinstance(features.momentum_score, dict):
            momentum = float(features.momentum_score.get("M5", 0.0))

        atr_pct = 0.0
        if hasattr(features, "atr_percent") and isinstance(features.atr_percent, dict):
            atr_pct = float(features.atr_percent.get("M5", 0.0))

        vol_ratio = 1.0
        if hasattr(features, "volume_ratio") and isinstance(features.volume_ratio, dict):
            vol_ratio = float(features.volume_ratio.get("M5", 1.0))

        abs_mom = abs(momentum)

        # Priority order:
        # 1. CHAOS — extreme volatility always wins (safety)
        # 2. TRENDING — strong momentum (primary driver, ATR not required)
        # 3. CHOPPY — dead market (low ATR AND no momentum)
        # 4. RANGING — everything else

        if atr_pct >= self.ATR_PCT_CHAOS:
            regime = MarketRegime.CHAOS
            engine = "Hibernate"
            strength = min(100, 60 + (atr_pct - self.ATR_PCT_CHAOS) * 100)
            vol_pct = "EXTREME"
        elif abs_mom >= self.MOMENTUM_STRONG:
            regime = MarketRegime.TRENDING_BULL if momentum > 0 else MarketRegime.TRENDING_BEAR
            engine = "Aggressive"
            strength = min(100, 50 + abs_mom * 50)
            vol_pct = "HIGH" if atr_pct >= 0.12 else "MEDIUM"
        elif atr_pct < self.ATR_PCT_SQUEEZE and abs_mom < self.MOMENTUM_NEUTRAL:
            regime = MarketRegime.CHOPPY
            engine = "Hibernate"
            strength = 70.0
            vol_pct = "LOW"
        else:
            regime = MarketRegime.RANGING
            engine = "SemiHFT"
            strength = 60.0
            vol_pct = "MEDIUM"

        return RegimeSnapshot(
            regime=regime,
            strength=strength,
            adx=momentum,               # momentum proxy (not real ADX)
            bb_bandwidth=atr_pct,       # ATR% proxy for bandwidth
            vol_percentile=vol_pct,
            suggested_engine=engine
        )

if __name__ == "__main__":
    from types import SimpleNamespace
    d = RegimeDetector()
    # Live values 2026-08-10: mom=+0.878 atr%=0.074 -> should be TRENDING
    r = d.detect(SimpleNamespace(momentum_score={"M5": 0.878}, atr_percent={"M5": 0.074}, volume_ratio={"M5": 1.0}))
    assert r.regime == MarketRegime.TRENDING, f"Expected TRENDING got {r.regime}"
    # Strong bearish
    r2 = d.detect(SimpleNamespace(momentum_score={"M5": -0.45}, atr_percent={"M5": 0.08}, volume_ratio={"M5": 1.2}))
    assert r2.regime == MarketRegime.TRENDING, f"Expected TRENDING got {r2.regime}"
    # Squeeze: no mom, no vol
    r3 = d.detect(SimpleNamespace(momentum_score={"M5": 0.02}, atr_percent={"M5": 0.03}, volume_ratio={"M5": 0.5}))
    assert r3.regime == MarketRegime.CHOPPY, f"Expected CHOPPY got {r3.regime}"
    # Chaos: extreme vol
    r4 = d.detect(SimpleNamespace(momentum_score={"M5": 0.5}, atr_percent={"M5": 0.35}, volume_ratio={"M5": 2.0}))
    assert r4.regime == MarketRegime.CHAOS, f"Expected CHAOS got {r4.regime}"
    # Ranging: medium everything
    r5 = d.detect(SimpleNamespace(momentum_score={"M5": 0.15}, atr_percent={"M5": 0.07}, volume_ratio={"M5": 1.0}))
    assert r5.regime == MarketRegime.RANGING, f"Expected RANGING got {r5.regime}"
    print("RegimeDetector self-check OK: TRENDING/TRENDING/CHOPPY/CHAOS/RANGING all pass")
