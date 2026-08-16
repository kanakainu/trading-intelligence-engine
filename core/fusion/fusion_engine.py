"""Signal Fusion Engine — Merge signals from multiple detectors.

Input: List[Signal]
Output: ConsensusSignal (FusedSignal)

Logic:
1. Group by direction (BUY/SELL)
2. Detect conflicts (both directions present)
3. Detect duplicates (same strategy)
4. Score agreement/conflict/duplicate
5. If conflict -> REJECT
6. Else merge into single FusedSignal
"""
from typing import List, Dict, Any, Optional
from collections import defaultdict

from core.fusion.fusion_models import (
    FusedSignal, FusionInputs, FusionDecision
)
from core.signals import Signal, Direction


class SignalFusion:
    """
    Fuses multiple detector signals into a consensus.
    
    NO execution logic.
    NO risk logic.
    Pure signal fusion.
    """
    
    # Thresholds
    MIN_AGREEMENT = 0.4      # Below = weak consensus (was 0.6)
    MAX_CONFLICT = 0.3       # Above = conflict (reject)
    MAX_DUPLICATE = 0.5      # Above = too many same strategy
    ZONE_MERGE_TOLERANCE = 0.0005  # 0.05% for zone merging
    
    def __init__(self):
        pass
    
    def fuse(self, inputs: FusionInputs) -> FusedSignal:
        """Fuse signals into consensus."""
        signals = inputs.signals
        
        if not signals:
            return self._empty_fusion(inputs)
        
        # Group by direction
        buy_signals = [s for s in signals if s.direction == Direction.BUY]
        sell_signals = [s for s in signals if s.direction == Direction.SELL]
        
        # Check for conflict (both directions present)
        if buy_signals and sell_signals:
            return self._conflict_fusion(inputs, buy_signals, sell_signals)
        
        # Single direction - proceed
        active_signals = buy_signals if buy_signals else sell_signals
        direction = "buy" if buy_signals else "sell"
        
        # Check duplicates (same strategy)
        duplicate_score = self._compute_duplicate_score(active_signals)
        
        # Initialize agreement
        agreement = 0.0
        
        # Check if duplicate strategy dominates
        if duplicate_score > self.MAX_DUPLICATE:
            decision = FusionDecision.DUPLICATE
        else:
            # Compute agreement (zone overlap + confidence alignment)
            agreement = self._compute_agreement(active_signals)
            
            # Check if consensus strong enough
            if agreement < self.MIN_AGREEMENT:
                decision = FusionDecision.SINGLE if len(active_signals) == 1 else FusionDecision.CONFLICT
            else:
                decision = FusionDecision.CONSENSUS if len(active_signals) > 1 else FusionDecision.SINGLE
        
        # Merge entry zones
        entry_zone = self._merge_zones(active_signals)
        
        # Weighted confidence
        confidence = self._compute_weighted_confidence(active_signals)
        
        # Build fused signal
        strategies = list(set(s.strategy for s in active_signals))
        source_ids = [s.signal_id for s in active_signals]
        
        metadata = {
            "direction_signals": len(active_signals),
            "buy_count": len(buy_signals),
            "sell_count": len(sell_signals),
            "avg_confidence": sum(s.confidence for s in active_signals) / len(active_signals),
            "min_confidence": min(s.confidence for s in active_signals),
            "max_confidence": max(s.confidence for s in active_signals),
        }
        
        return FusedSignal(
            fusion_id=f"fusion_{inputs.symbol}_{inputs.scan_id}",
            symbol=inputs.symbol,
            direction=direction,
            decision=decision,
            confidence=confidence,
            agreement=agreement,
            conflict_score=0.0,
            duplicate_score=duplicate_score,
            entry_zone=entry_zone,
            source_signals=source_ids,
            strategies=strategies,
            count=len(active_signals),
            metadata=metadata,
            created_at=inputs.timestamp,
        )
    
    def _empty_fusion(self, inputs: FusionInputs) -> FusedSignal:
        return FusedSignal(
            fusion_id=f"fusion_{inputs.symbol}_{inputs.scan_id}",
            symbol=inputs.symbol,
            direction="none",
            decision=FusionDecision.NO_SIGNALS,
            confidence=0.0,
            agreement=0.0,
            conflict_score=0.0,
            duplicate_score=0.0,
            entry_zone={"low": 0.0, "high": 0.0},
            metadata={"reason": "no_signals"},
            created_at=inputs.timestamp,
        )
    
    def _conflict_fusion(
        self,
        inputs: FusionInputs,
        buy_signals: List[Signal],
        sell_signals: List[Signal],
    ) -> FusedSignal:
        """Handle opposing signals — REJECT."""
        all_signals = buy_signals + sell_signals
        
        # Compute conflict score
        buy_conf = sum(s.confidence for s in buy_signals) / len(buy_signals)
        sell_conf = sum(s.confidence for s in sell_signals) / len(sell_signals)
        conflict_score = min(buy_conf, sell_conf) / max(buy_conf, sell_conf) if max(buy_conf, sell_conf) > 0 else 1.0
        
        return FusedSignal(
            fusion_id=f"fusion_{inputs.symbol}_{inputs.scan_id}",
            symbol=inputs.symbol,
            direction="conflict",
            decision=FusionDecision.CONFLICT,
            confidence=0.0,
            agreement=0.0,
            conflict_score=conflict_score,
            duplicate_score=0.0,
            entry_zone={"low": 0.0, "high": 0.0},
            source_signals=[s.signal_id for s in all_signals],
            strategies=list(set(s.strategy for s in all_signals)),
            count=len(all_signals),
            metadata={
                "buy_count": len(buy_signals),
                "sell_count": len(sell_signals),
                "buy_avg_conf": round(buy_conf, 3),
                "sell_avg_conf": round(sell_conf, 3),
                "reason": "opposing_directions",
            },
            created_at=inputs.timestamp,
        )
    
    def _compute_duplicate_score(self, signals: List[Signal]) -> float:
        """Detect same strategy firing multiple times."""
        strategy_counts = defaultdict(int)
        for s in signals:
            strategy_counts[s.strategy] += 1
        
        total = len(signals)
        duplicates = sum(1 for count in strategy_counts.values() if count > 1)
        
        if total <= 1:
            return 0.0
        
        return duplicates / total
    
    def _compute_agreement(self, signals: List[Signal]) -> float:
        """
        Agreement = zone_overlap * confidence_alignment
        """
        if len(signals) <= 1:
            return 1.0
        
        # Zone overlap (how much entry zones intersect)
        zone_overlap = self._compute_zone_overlap(signals)
        
        # Confidence alignment (how similar are confidences)
        confs = [s.confidence for s in signals]
        conf_std = (sum((c - sum(confs)/len(confs))**2 for c in confs) / len(confs))**0.5
        conf_alignment = max(0.0, 1.0 - conf_std * 2)  # Penalize spread
        
        return (zone_overlap * 0.7 + conf_alignment * 0.3)
    
    def _compute_zone_overlap(self, signals: List[Signal]) -> float:
        """Compute intersection over union of entry zones."""
        if len(signals) <= 1:
            return 1.0
        
        # Get all zones - handle single-point entry_zone
        zones = []
        for s in signals:
            ez = s.entry_zone
            if "low" in ez and "high" in ez:
                zones.append((ez["low"], ez["high"]))
            elif "low" in ez:
                zones.append((ez["low"], ez["low"]))
            elif "high" in ez:
                zones.append((ez["high"], ez["high"]))
            elif "price" in ez:
                zones.append((ez["price"], ez["price"]))
        
        # Find intersection
        max_low = max(z[0] for z in zones)
        min_high = min(z[1] for z in zones)
        
        intersection = max(0.0, min_high - max_low)
        
        # Union
        min_low = min(z[0] for z in zones)
        max_high = max(z[1] for z in zones)
        union = max_high - min_low
        
        if union == 0:
            return 1.0
        
        return intersection / union
    
    def _compute_weighted_confidence(self, signals: List[Signal]) -> float:
        """Weighted average by confidence (higher conf = more weight)."""
        total_weight = sum(s.confidence for s in signals)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(s.confidence * s.confidence for s in signals)
        return weighted_sum / total_weight
    
    def _merge_zones(self, signals: List[Signal]) -> Dict[str, float]:
        """Merge entry zones - take intersection if overlapping, else union."""
        if len(signals) == 1:
            return signals[0].entry_zone
        
        # Extract zones safely
        zones = []
        for s in signals:
            ez = s.entry_zone
            if "low" in ez and "high" in ez:
                zones.append((ez["low"], ez["high"]))
            elif "low" in ez:
                zones.append((ez["low"], ez["low"]))
            elif "high" in ez:
                zones.append((ez["high"], ez["high"]))
            elif "price" in ez:
                zones.append((ez["price"], ez["price"]))
        
        if not zones:
            return signals[0].entry_zone
        
        # Try intersection first
        max_low = max(z[0] for z in zones)
        min_high = min(z[1] for z in zones)
        
        if max_low < min_high:
            # Valid intersection
            return {"low": max_low, "high": min_high}
        
        # No intersection - take tightest union around highest confidence
        best = max(signals, key=lambda s: s.confidence)
        return best.entry_zone


# Global instance
_global_fusion: Optional[SignalFusion] = None


def get_signal_fusion() -> SignalFusion:
    global _global_fusion
    if _global_fusion is None:
        _global_fusion = SignalFusion()
    return _global_fusion


def fuse_signals(inputs: FusionInputs) -> FusedSignal:
    """Convenience function."""
    fusion = get_signal_fusion()
    return fusion.fuse(inputs)