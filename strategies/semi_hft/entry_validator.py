"""Entry Validator — all 3 gates must agree."""
from dataclasses import dataclass
from .market_state import MarketState, MarketStateSnapshot
from .opportunity import OpportunityWindow, OpportunitySnapshot
from .microstructure import MicroSignal, MicrostructureSnapshot

@dataclass
class EntryDecision:
    valid:  bool
    reason: str

QUALITY_THRESHOLD = 0.65

def validate(state: MarketStateSnapshot,
             opp:   OpportunitySnapshot,
             micro: MicrostructureSnapshot) -> EntryDecision:
    if state.state not in {MarketState.EXPANDING, MarketState.TRENDING}:
        return EntryDecision(False, f"state={state.state.value}")
    if opp.window != OpportunityWindow.OPEN:
        return EntryDecision(False, f"opp_closed: {opp.reason}")
    if micro.signal == MicroSignal.NONE:
        return EntryDecision(False, "no_micro_signal")
    if micro.quality < QUALITY_THRESHOLD:
        return EntryDecision(False, f"quality={micro.quality:.2f}<{QUALITY_THRESHOLD}")
    return EntryDecision(True, f"all_gates_pass q={micro.quality:.2f}")


if __name__=="__main__":
    from datetime import datetime, timezone
    from .market_state import MarketState, MarketStateSnapshot
    from .opportunity import OpportunityWindow, OpportunitySnapshot
    from .microstructure import MicroSignal, MicrostructureSnapshot
    now=datetime.now(timezone.utc)
    s=MarketStateSnapshot(MarketState.EXPANDING,80,"x",now)
    o=OpportunitySnapshot(OpportunityWindow.OPEN,"LON",90)
    m=MicrostructureSnapshot(MicroSignal.BUY,0.75,"breakout","x")
    r=validate(s,o,m)
    assert r.valid, r.reason
    # bad state
    s2=MarketStateSnapshot(MarketState.SLEEPING,10,"x",now)
    r2=validate(s2,o,m)
    assert not r2.valid
    print("entry_validator OK")
