"""StrategyOrchestrator — runs all 12 Bystra detectors on live candle tick,
ranks facts by confidence, picks best, sends to ExecutionService.

Orchestrator only. No trading logic.
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

from core.detectors.fact import Fact
from core.context.context_model import MarketContext
from core.decision.trade_decision import TradeDecision, BUY, SELL, WAIT

from detectors.snrc1_detector import Snrc1Detector
from detectors.snrc2_detector import Snrc2Detector
from detectors.snrc3_detector import Snrc3Detector
from detectors.hybrid1_detector import Hybrid1Detector
from detectors.hybrid2_detector import Hybrid2Detector
from detectors.manipulation_detector import ManipulationDetector
from detectors.qmr_detector import QmrDetector
from detectors.qmc_detector import QmcDetector
from detectors.qm2p_detector import Qm2pDetector
from detectors.qmm_detector import QmmDetector
from detectors.blindspot_detector import BlindspotDetector
from detectors.blindspot2_detector import Blindspot2Detector
from detectors.clab_detector import ClabDetector

log = logging.getLogger("StrategyOrchestrator")

DETECTORS = [
    ("SNRC1", Snrc1Detector()),
    ("SNRC2", Snrc2Detector()),
    ("SNRC3", Snrc3Detector()),
    ("HYBRID_1", Hybrid1Detector()),
    ("HYBRID_2", Hybrid2Detector()),
    ("MANIPULATION", ManipulationDetector()),
    ("QMR", QmrDetector()),
    ("QMC", QmcDetector()),
    ("QM2P", Qm2pDetector()),
    ("QMM", QmmDetector()),
    ("BLINDSPOT", BlindspotDetector()),
    ("BLINDSPOT_2", Blindspot2Detector()),
    ("CLAB", ClabDetector()),
]


class StrategyOrchestrator:
    def __init__(self, min_confidence: float = 0.55):
        self._min_confidence = min_confidence

    def run(self, context: MarketContext) -> List[Fact]:
        """Run all detectors on context. Return facts sorted by confidence desc."""
        all_facts: List[Fact] = []
        for name, detector in DETECTORS:
            try:
                facts = detector.detect(context)
                for f in facts:
                    f.metadata["detector_name"] = name
                all_facts.extend(facts)
            except Exception as e:
                log.warning(f"{name} failed: {e}")

        # Filter min confidence, sort desc
        all_facts = [f for f in all_facts if f.confidence >= self._min_confidence]
        all_facts.sort(key=lambda f: f.confidence, reverse=True)
        return all_facts

    def best_decision(self, context: MarketContext) -> TradeDecision:
        """Run all, pick best fact → TradeDecision using Bystra SOP. Returns setup with full metadata for EntryMonitor."""
        facts = self.run(context)
        if not facts:
            return TradeDecision(action=WAIT, reason="No patterns detected")

        best = facts[0]
        direction = best.metadata.get("direction", "BUY")
        entry_zone = best.metadata.get("entry_zone")  # {'high': float, 'low': float}
        danger_zone = best.metadata.get("danger_zone") # <- FIX: added this line
        # Bystra SOP: SL = structural (above base high / below base low)
        sl = best.metadata.get("sl")
        spread_buf = context.metadata.get("spread_buffer", 0.5) / 10  # 0.05 pips safety buffer
        
        # Adjust SL with spread buffer
        if direction == "BUY" and sl:
            sl = float(sl) - spread_buf  # Below base low
        elif direction == "SELL" and sl:
            sl = float(sl) + spread_buf  # Above base high
        entry_tf = best.metadata.get("entry_tf", "M5")

        if not entry_zone:
            return TradeDecision(action=WAIT, reason=f"Pattern {best.value} missing entry_zone")

        # Bystra SOP: TP = next H1 S/R zone
        h1_support = context.metadata.get("h1_support")
        h1_resistance = context.metadata.get("h1_resistance")

        tp = None
        if direction == "SELL" and sl and h1_support:
            tp_val = float(h1_support)
            risk = float(sl) - float(entry_zone['low'])
            reward = float(entry_zone['low']) - float(tp_val)
            if reward >= risk * 1.5:  # RR ≥ 1:1.5
                tp = tp_val
            else:
                tp = float(entry_zone['low']) - risk * 1.5
        elif direction == "BUY" and sl and h1_resistance:
            tp_val = float(h1_resistance)
            risk = float(entry_zone['high']) - float(sl)
            reward = float(tp_val) - float(entry_zone['high'])
            if reward >= risk * 1.5:
                tp = tp_val
            else:
                tp = float(entry_zone['high']) + risk * 1.5
        else:
            # Fallback ATR
            atr = context.metadata.get("atr", 5.0)
            mid_entry = (entry_zone['high'] + entry_zone['low']) / 2
            tp = mid_entry + atr * 1.5 if direction == "BUY" else mid_entry - atr * 1.5

        # Bundle metadata for EntryMonitor
        metadata_full = {
            "symbol": context.symbol,
            "entry_zone": entry_zone,
            "danger_zone": danger_zone,
            "sl": sl,
            "take_profit": tp,
            "entry_tf": entry_tf,
            "detector_name": best.metadata.get("detector_name")
        }

        sl_str = f"{sl:.3f}" if sl else "?"
        tp_str = f"{tp:.3f}" if tp else "?"
        ez_str = f"{entry_zone['low']:.3f}-{entry_zone['high']:.3f}"
        explanation = f"Setup={best.value} Direction={direction} EntryZone={ez_str} SL={sl_str} TP={tp_str} DZ={danger_zone}"

        decision = TradeDecision(
            action=BUY if direction == "BUY" else SELL,
            setup_id=best.value,
            setup_name=best.value,
            confidence=best.confidence,
            reason=f"Detected {best.value} on {entry_tf}. WAITING_PULLBACK.",
            explanation=explanation,
            ranking=[{"name": f.value, "conf": f.confidence} for f in facts]
        )
        # Inject metadata manually for EntryMonitor
        decision.metadata = metadata_full
        return decision
