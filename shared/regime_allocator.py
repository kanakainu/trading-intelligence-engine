import json
import logging
from dataclasses import dataclass, asdict
from typing import Any

from shared.regime_detector import MarketRegime, RegimeSnapshot

logger = logging.getLogger("regime_allocator")

# NOTE: MarketRegime & RegimeSnapshot imported from regime_detector.
# Critical: duplicated enum classes would break equality (TRENDING != TRENDING).

class RegimeAllocator:
    """
    Nexus A12 'El Estratega' — Automatic Regime Allocator.
    Detects market regime and switches active strategies via
    config/strategy_status.json (reloaded by StrategyManager.run_all() every loop).
    """

    STRATEGY_STATUS_PATH = "/home/ubuntu/trading-intelligence-engine/config/strategy_status.json"

    # Strategy IDs in TIE V4
    STRATEGY_IDS = {
        "aggressive": "aggressive_v1",
        "semi_hft": "semi_hft_c8_v4",
        "bystra": "bystra_v1",
    }

    def __init__(self, detector: Any):
        self._detector = detector
        self._current_regime: MarketRegime | None = None
        self._last_switch_ts = 0.0
        self._min_switch_interval = 600.0  # 10 min — avoid flapping

    def allocate(self, features: Any, now_ts: float) -> RegimeSnapshot:
        """Detect regime and apply engine allocation. Returns snapshot."""
        import time
        snap = self._detector.detect(features)

        regime_changed = snap.regime != self._current_regime
        cooldown_elapsed = (now_ts - self._last_switch_ts) > self._min_switch_interval
        
        # Fast-path for critical regimes
        is_fast_path = snap.regime in (MarketRegime.TRENDING, MarketRegime.TRENDING_BULL,
                                       MarketRegime.TRENDING_BEAR, MarketRegime.CHAOS, MarketRegime.CHOPPY)

        # Apply if:
        # 1. First run (initial state)
        # 2. Regime changed AND (Cooldown elapsed OR it's a Fast-Path regime)
        if self._current_regime is None or (regime_changed and (cooldown_elapsed or is_fast_path)):
            self._apply(snap)
            self._current_regime = snap.regime
            self._last_switch_ts = now_ts
            logger.debug("REGIME SWITCH: %s -> %s (engine=%s, fast_path=%s)", 
                        self._current_regime.value if self._current_regime else "?", 
                        snap.regime.value, snap.suggested_engine, is_fast_path)

        return snap

    def _apply(self, snap: RegimeSnapshot) -> None:
        """SOPAN MODE: Only logs suggestions, does NOT overwrite manual dashboard settings."""
        regime = snap.regime
        logger.debug("REGIME SUGGESTION: %s -> Use %s", regime.value, snap.suggested_engine)
        
        # We skip writing to STRATEGY_STATUS_PATH to prevent fighting with the Dashboard.
        # Mas Wisnu has full control now.
        return

    def current(self) -> MarketRegime | None:
        return self._current_regime
