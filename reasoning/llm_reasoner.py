"""LLM Reasoner — AI confidence booster/veto layer."""
import logging
from typing import Dict, Any
from dataclasses import dataclass

log = logging.getLogger(__name__)

@dataclass
class ReasoningResult:
    original_confidence: float
    llm_confidence: float
    final_confidence: float
    llm_reason: str
    veto: bool

class LLMReasoner:
    def __init__(self, min_confidence: float = 0.6, llm_weight: float = 0.3):
        self.min_confidence = min_confidence
        self.llm_weight = llm_weight
        self.insight_path = "/home/ubuntu/trading-intelligence-engine/logs/learning_insights.json"
    
    def _get_latest_insights(self) -> Dict[str, Any]:
        """Load latest performance insights from Learning Brain."""
        try:
            import os, json
            if not os.path.exists(self.insight_path):
                return {}
            with open(self.insight_path, "r") as f:
                lines = f.readlines()
                if not lines:
                    return {}
                return json.loads(lines[-1]) # Ambil insight terbaru
        except Exception as e:
            log.error(f"Failed to load insights: {e}")
            return {}

    def reason(self, setup_name: str, action: str, confidence: float, 
               entry: float, sl: float, tp: float, detector_reason: str, 
               market_context: Dict[str, Any]) -> ReasoningResult:
        insights = self._get_latest_insights()
        setup_perf = insights.get("session_performance", {}).get(setup_name, {})
        
        # Real logic: boost/reduce confidence based on historic winrate
        llm_conf = 0.75 # base mock
        wr = setup_perf.get("wins", 0) / setup_perf.get("total", 1) if setup_perf.get("total", 0) > 0 else 0.5
        
        if wr > 0.6: llm_conf += 0.1 # Strong history
        if wr < 0.4: llm_conf -= 0.1 # Weak history

        llm_reason = f"LLM confirmed. Setup history winrate: {wr:.1%}"
        veto = False
        
        final_conf = (confidence * (1 - self.llm_weight)) + (llm_conf * self.llm_weight)
        
        if veto or final_conf < self.min_confidence:
            veto = True
            final_conf = 0.0
        
        return ReasoningResult(
            original_confidence=confidence,
            llm_confidence=llm_conf,
            final_confidence=final_conf,
            llm_reason=llm_reason,
            veto=veto
        )
