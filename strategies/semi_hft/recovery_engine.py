"""Recovery Engine — logic to mitigate losses after a losing streak."""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class RecoveryPlan:
    action: str  # e.g., 'hold', 'reduce_risk', 'stop_trading'
    reason: str
    modifier: float = 0.0  # e.g., reduce_lot_by_pct

# Configuration
MAX_CONSECUTIVE_LOSSES = 3
RECOVERY_FACTOR = 0.5  # Reduce lot by 50% after N losses

def evaluate(consec_losses: int, current_lot: float, equity: float) -> RecoveryPlan:
    """Determine recovery action based on consecutive losses."""
    if consec_losses >= MAX_CONSECUTIVE_LOSSES:
        # If we've had N losses, start reducing risk
        new_lot = current_lot * RECOVERY_FACTOR
        if new_lot < 0.01:  # Minimum lot size
            return RecoveryPlan('stop_trading', 'min_lot_reached', 0.0)
        return RecoveryPlan('reduce_risk', f'consec_loss>={MAX_CONSECUTIVE_LOSSES}', new_lot)
    
    # Default: hold, no changes
    return RecoveryPlan('hold', 'ok', current_lot)

if __name__ == "__main__":
    # Test cases
    print("Test 1: No recovery needed")
    plan1 = evaluate(consec_losses=2, current_lot=0.1, equity=1000)
    assert plan1.action == 'hold', f"Expected 'hold', got {plan1.action}"
    
    print("Test 2: Reduce risk")
    plan2 = evaluate(consec_losses=3, current_lot=0.1, equity=1000)
    assert plan2.action == 'reduce_risk', f"Expected 'reduce_risk', got {plan2.action}"
    assert plan2.modifier == 0.05, f"Expected lot 0.05, got {plan2.modifier}"
    
    print("Test 3: Stop trading (min lot)")
    plan3 = execute(consec_losses=4, current_lot=0.02, equity=1000)
    assert plan3.action == 'stop_trading', f"Expected 'stop_trading', got {plan3.action}"
    
    print("Recovery Engine OK")
