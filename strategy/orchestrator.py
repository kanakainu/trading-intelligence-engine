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
from detectors.mother_candle_detector import MotherCandleDetector
from reasoning.llm_reasoner import LLMReasoner

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
    ("MOTHER_CANDLE", MotherCandleDetector()),
]


class StrategyOrchestrator:
    def __init__(self, min_confidence: float = 0.55):
        self._min_confidence = min_confidence
        self.llm_reasoner = LLMReasoner(min_confidence=min_confidence, llm_weight=0.3)

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
        
        price = context.metadata.get("current_price", 0.0)
        entry_tf = best.metadata.get("entry_tf", "M5")

        # Ensure entry_zone exists before any zone math
        if not entry_zone:
            return TradeDecision(action=WAIT, reason=f"Pattern {best.value} missing entry_zone")
        
        # ── Danger Zone ────────────────────────────────────────────────
        # Use detector's per-setup DZ if set; fallback to H1 S/R
        h1_support = context.metadata.get("h1_support")
        h1_resistance = context.metadata.get("h1_resistance")
        det_dz = best.metadata.get("danger_zone")
        if det_dz is not None:
            danger_zone = float(det_dz)  # detector-level structural invalidation
        elif direction == "SELL" and h1_resistance:
            danger_zone = float(h1_resistance)
        elif direction == "BUY" and h1_support:
            danger_zone = float(h1_support)
        else:
            danger_zone = None
        
        # ── Stop Loss — entry_tf swing pivots, not H1 ─────────────────
        buf_val = context.metadata.get("spread_buffer", 0.5)
        buf = max(buf_val / 10, 0.25)  # default min buffer

        # SL reference = entry_zone edge (SL must be OUTSIDE zone)
        # SELL: entry_zone['high'] is the invalidation edge → SL above it
        # BUY:  entry_zone['low'] is the invalidation edge → SL below it
        ez_ref = float(entry_zone['high']) if direction == "SELL" else float(entry_zone['low'])
        if direction == "SELL":
            # SL = lowest swing HIGH above entry_zone high
            sl = None
            for tf_key in [entry_tf, "H1"]:
                tf_candles = context.metadata.get("candles", {}).get(tf_key, [])
                if not tf_candles: continue
                from detectors.common import find_swing_pivots
                pivots = find_swing_pivots(tf_candles, n=2)
                swing_highs = sorted(
                    [p["price"] for p in pivots if p["type"] == "high" and p["price"] > ez_ref],
                    reverse=False
                )
                if swing_highs:
                    sl = swing_highs[0] + buf
                    break
            if sl is None:
                sl = best.metadata.get("sl")
        else:
            # SL = highest swing LOW below entry_zone low
            sl = None
            for tf_key in [entry_tf, "H1"]:
                tf_candles = context.metadata.get("candles", {}).get(tf_key, [])
                if not tf_candles: continue
                from detectors.common import find_swing_pivots
                pivots = find_swing_pivots(tf_candles, n=2)
                swing_lows = sorted(
                    [p["price"] for p in pivots if p["type"] == "low" and p["price"] < ez_ref],
                    reverse=True
                )
                if swing_lows:
                    sl = swing_lows[0] - buf
                    break
            if sl is None:
                sl = best.metadata.get("sl")
        
        # ── Take Profit — nearest H1 S/R with ≥1.5 RR ─────────────────
        tp = None
        mid_entry = (entry_zone['high'] + entry_zone['low']) / 2
        if direction == "SELL" and sl and h1_support:
            risk = float(sl) - float(entry_zone['low'])
            tp_val = float(h1_support)
            reward = float(entry_zone['low']) - tp_val
            if risk > 0 and reward >= risk * 1.5:
                tp = tp_val
            else:
                # Project TP at 1.5 RR minimum
                tp = mid_entry - risk * 1.5
        elif direction == "BUY" and sl and h1_resistance:
            risk = float(entry_zone['high']) - float(sl)
            tp_val = float(h1_resistance)
            reward = tp_val - float(entry_zone['high'])
            if risk > 0 and reward >= risk * 1.5:
                tp = tp_val
            else:
                tp = mid_entry + risk * 1.5
        else:
            # Fallback: ATR-based at 1.5 RR
            atr = context.metadata.get("atr", 5.0)
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

        # LLM Reasoner — confirm/veto before finalize
        if decision.action != WAIT:
            reasoning_result = self.llm_reasoner.reason(
                setup_name=decision.setup_name,
                action=decision.action,
                confidence=decision.confidence,
                entry=(entry_zone['low'] + entry_zone['high']) / 2,
                sl=sl or 0,
                tp=tp or 0,
                detector_reason=decision.reason,
                market_context=context.metadata
            )

            if reasoning_result.veto:
                log.info(f"LLM veto: {reasoning_result.llm_reason}")
                return TradeDecision(action=WAIT, setup_name="LLM_VETO", confidence=0.0,
                                     reason=f"Vetoed by LLM: {reasoning_result.llm_reason}")

            decision.confidence = reasoning_result.final_confidence
            decision.reason = f"{decision.reason} | LLM: {reasoning_result.llm_reason}"
            # Update metadata with final confidence
            decision.metadata["confidence"] = reasoning_result.final_confidence

        return decision
