"""BystraStrategy — wraps all 14 detectors as a single strategy plugin."""
from typing import Any, Dict, List, Optional
import logging
import uuid

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction
from core.lifecycle.lifecycle_models import PositionSnapshot
from core.learning.learning_models import TradeReflection
from strategies.bystra.metadata import BYSTRA_METADATA
from strategies.bystra.config import BystraConfig

import json, os

ZONE_BLACKLIST_FILE = "/tmp/tie_bystra_zone_blacklist.json"

logger = logging.getLogger("BystraStrategy")


class BystraStrategy(BaseStrategy):
    """Bystra: 14-detector supply/demand strategy plugin.

    Runtime calls analyze(context) only.
    Detector orchestration internal — runtime never sees detector names.
    """

    def __init__(self):
        super().__init__(BYSTRA_METADATA)
        self._cfg = BystraConfig()
        self._detectors: Dict[str, Any] = {}
        # Price-zone cooldown: {(detector_name, direction, zone_price_rounded): True}
        # Cleared when price moves beyond zone_radius_pts from recorded zone.
        self._zone_seen: Dict[tuple, float] = {}  # key → entry_price recorded

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def initialize(self) -> None:
        self._detectors = self._load_detectors()
        self._initialized = True
        # Load persisted zone blacklist (survive restart)
        try:
            if os.path.exists(ZONE_BLACKLIST_FILE):
                raw = json.load(open(ZONE_BLACKLIST_FILE))
                self._zone_seen = {tuple(k.split("|")): v for k, v in raw.items()}
                logger.info("BystraStrategy loaded %d zone blacklist entries", len(self._zone_seen))
        except Exception as e:
            logger.warning("Zone blacklist load failed: %s", e)
            self._zone_seen = {}
        logger.info("BystraStrategy initialized — %d detectors", len(self._detectors))

    def observe(self, context: StrategyContext) -> None:
        """Pre-filter hook. No-op until regime gate wired."""
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        """Run all detectors → pick best fact → return StrategyResult."""
        market_ctx = context.scan.market
        facts = []

        for name, detector in self._detectors.items():
            if name not in self._cfg.enabled_detectors:
                continue
            try:
                result = detector.detect(market_ctx)
                if result:
                    facts.extend(result)
            except Exception as e:
                logger.warning("Detector %s error: %s", name, e)

        if not facts:
            return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")

        best = max(facts, key=lambda f: f.confidence)
        logger.info("Bystra best detector: %s conf=%.0f%% dir=%s", best.value, best.confidence * 100, best.metadata.get("direction", "?") if best.metadata else "?")
        if best.confidence < self._cfg.min_confidence:
            return StrategyResult(signal=None, confidence=best.confidence, reason="confidence_low")

        md = best.metadata or {}
        direction = Direction.BUY if md.get("direction") == "BUY" else Direction.SELL
        current_price = getattr(market_ctx, "current_price", 0.0) or 0.0
        if current_price == 0.0:
            # fallback: use last M5 close
            _m5 = getattr(market_ctx, "candles", {}).get("M5", [])
            if _m5:
                current_price = float(_m5[-1].get("close", 0.0))

        # Pattern blacklist: once fired at a price zone, permanently blocked (except THREE_CANDLE)
        if best.value not in self._cfg.zone_cooldown_exempt:
            zone_key = (best.value, md.get("direction", ""), round(current_price / self._cfg.zone_radius_pts))
            if zone_key in self._zone_seen:
                logger.info("Bystra pattern blacklist: %s @ zone %.0f already fired, skip", best.value, zone_key[2])
                return StrategyResult(signal=None, confidence=best.confidence, reason=f"pattern_blacklist:{best.value}")
            self._zone_seen[zone_key] = current_price  # mark fired — permanent
            try:
                with open(ZONE_BLACKLIST_FILE, "w") as f:
                    json.dump({"|".join(str(x) for x in k): v for k, v in self._zone_seen.items()}, f)
            except Exception as e:
                logger.warning("Zone blacklist save failed: %s", e)
        entry_zone = md.get("entry_zone", {})

        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol=market_ctx.symbol,
            direction=direction,
            entry_zone=entry_zone,
            confidence=best.confidence,
            timeframe=md.get("entry_tf", "M5"),
            metadata=md,
        )

        return StrategyResult(
            signal=signal,
            confidence=best.confidence,
            reason=f"{best.value} detected",
            capabilities_used=["market_structure"],
            metadata={"detector": best.value, "fact_type": best.fact_type},
        )

    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        """Bystra doesn't manage positions — lifecycle engine handles it."""
        return None

    def learn(self, reflection: TradeReflection) -> None:
        """No-op — learning engine handles post-trade analytics."""
        pass

    def shutdown(self) -> None:
        self._initialized = False
        self._detectors.clear()
        logger.info("BystraStrategy shutdown")

    # ── Internal ──────────────────────────────────────────────────────────
    def _load_detectors(self) -> Dict[str, Any]:
        """Lazy-load 14 detectors. Runtime never imports these directly."""
        from detectors.snrc1_detector import Snrc1Detector
        from detectors.snrc2_detector import Snrc2Detector
        from detectors.snrc3_detector import Snrc3Detector
        from detectors.hybrid1_detector import Hybrid1Detector
        from detectors.hybrid2_detector import Hybrid2Detector
        from detectors.manipulation_detector import ManipulationDetector
        from detectors.qmr_detector import QmrDetector
        from detectors.qmc_detector import QmcDetector
        from detectors.qmm_detector import QmmDetector
        from detectors.qm2p_detector import Qm2pDetector
        from detectors.blindspot_detector import BlindspotDetector
        from detectors.blindspot2_detector import Blindspot2Detector
        from detectors.clab_detector import ClabDetector
        from detectors.mother_candle_detector import MotherCandleDetector

        from detectors.three_candle_detector import ThreeCandleDetector

        return {
            "SNRC1": Snrc1Detector(),
            "SNRC2": Snrc2Detector(),
            "SNRC3": Snrc3Detector(),
            "HYBRID1": Hybrid1Detector(),
            "HYBRID2": Hybrid2Detector(),
            "QMR": QmrDetector(),
            "QMC": QmcDetector(),
            "QMM": QmmDetector(),
            "QM2P": Qm2pDetector(),
            "THREE_CANDLE": ThreeCandleDetector(),
        }
