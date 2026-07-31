"""Opportunity Engine Package — Pre-detector market filter.

Usage:
    from core.opportunity import evaluate_opportunity, OpportunityInputs
    
    inputs = OpportunityInputs(
        spread=0.3,
        atr_percent=0.005,
        volume_ratio=1.2,
        regime_name="TRENDING",
        adx=30.0,
        current_time=datetime.now(timezone.utc),
        symbol="XAUUSD",
        scan_id="scan_123"
    )
    
    opportunity = evaluate_opportunity(inputs)
    
    if not opportunity.market_allowed:
        print(f"Blocked: {opportunity.reason.value}")
        # Skip detectors
    else:
        print(f"Priority: {opportunity.priority}/10")
        # Run detectors
"""
from core.opportunity.opportunity_models import (
    OpportunitySnapshot,
    OpportunityInputs,
    OpportunityDecision,
    BlockReason,
)
from core.opportunity.opportunity_engine import (
    OpportunityEngine,
    get_opportunity_engine,
    evaluate_opportunity,
)

__all__ = [
    "OpportunitySnapshot",
    "OpportunityInputs",
    "OpportunityDecision",
    "BlockReason",
    "OpportunityEngine",
    "get_opportunity_engine",
    "evaluate_opportunity",
]

__version__ = "1.0.0"