from dataclasses import dataclass
from strategies.aggressive.session.session_profile import SessionSnapshot
from strategies.aggressive.liquidity.liquidity_engine import LiquiditySnapshot, LiquidityState
from strategies.aggressive.market_pulse.market_pulse import PulseSnapshot

@dataclass
class OpportunitySnapshot:
    window: str  # OPEN | CLOSED
    reason: str
    score: float

class OpportunityWindow:
    def __init__(self, max_spread=2.0):
        self.max_spread = max_spread

    def evaluate(self, session: SessionSnapshot, liquidity: LiquiditySnapshot, pulse: PulseSnapshot, spread: float) -> OpportunitySnapshot:
        reasons = []
        if not session.allowed:
            reasons.append(f"session_closed({session.session})")
        if liquidity.state != LiquidityState.LIKELY_LIQUID:
            reasons.append(f"low_liquidity({liquidity.state.value})")
        if pulse.pulse < 40:
            reasons.append(f"low_pulse({pulse.pulse})")
        if spread > self.max_spread:
            reasons.append(f"high_spread({spread})")
        
        score = (session.score * 0.3 + liquidity.score * 0.3 + pulse.pulse * 0.4)
        if spread > 0:
            score *= min(1.0, self.max_spread / spread)
        
        window = "OPEN" if not reasons else "CLOSED"
        reason_str = "OK" if window == "OPEN" else " | ".join(reasons)
        
        return OpportunitySnapshot(window=window, reason=reason_str, score=round(min(score, 100), 2))

if __name__ == '__main__':
    from strategies.aggressive.liquidity.liquidity_engine import LiquidityState
    from enum import Enum
    class Mock: pass
    s = Mock(); s.allowed = True; s.session = 'LONDON'; s.score = 80
    l = Mock(); l.state = LiquidityState.LIKELY_LIQUID; l.score = 90
    p = Mock(); p.pulse = 60
    engine = OpportunityWindow()
    snap = engine.evaluate(s, l, p, 1.0)
    assert snap.window == "OPEN"
    snap2 = engine.evaluate(s, l, p, 3.0)
    assert snap2.window == "CLOSED"
    print("OpportunityWindow OK")
