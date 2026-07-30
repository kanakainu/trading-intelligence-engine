"""TradePostmortemWriter — writes trade lesson to HCK after position closes."""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TradeOutcome:
    position_id: str
    symbol: str
    direction: str
    setup: str
    entry: float
    exit_price: float
    sl: Optional[float]
    tp: Optional[float]
    realized_pnl: float
    confidence: float
    duration_minutes: int = 0
    notes: str = ""

    @property
    def outcome(self) -> str:
        if self.realized_pnl > 0: return "WIN"
        if self.realized_pnl < 0: return "LOSS"
        return "BREAKEVEN"

    @property
    def hit_tp(self) -> bool:
        if not self.tp: return False
        if self.direction == "BUY":  return self.exit_price >= self.tp * 0.999
        return self.exit_price <= self.tp * 1.001

    @property
    def hit_sl(self) -> bool:
        if not self.sl: return False
        if self.direction == "BUY":  return self.exit_price <= self.sl * 1.001
        return self.exit_price >= self.sl * 0.999


class TradePostmortemWriter:
    """
    Writes trade postmortem to HCK after position closes.
    No trading logic. No decisions. Only memory writing.
    """

    def __init__(self, hck_bridge: Any):
        self._hck = hck_bridge

    def write(self, canonical_id: str, outcome: TradeOutcome) -> bool:
        """Write postmortem to HCK semantic memory."""
        if not self._hck: return False
        try:
            content = self._build_postmortem(outcome)
            self._hck.write_reflection(canonical_id, content, category="trade_postmortem")
            self._hck.publish_event("TRADE_POSTMORTEM", {
                "canonical_id": canonical_id,
                "position_id": outcome.position_id,
                "symbol": outcome.symbol,
                "outcome": outcome.outcome,
                "pnl": outcome.realized_pnl,
                "setup": outcome.setup,
            })
            return True
        except Exception as e:
            import logging
            logging.getLogger("TradePostmortemWriter").warning(f"write failed: {e}")
            return False

    @staticmethod
    def _build_postmortem(o: TradeOutcome) -> str:
        exit_reason = "TP_HIT" if o.hit_tp else ("SL_HIT" if o.hit_sl else "MANUAL_CLOSE")
        return (
            f"[POSTMORTEM] {o.outcome} | {o.symbol} {o.direction}\n"
            f"Setup: {o.setup} | Confidence: {o.confidence:.0%}\n"
            f"Entry: {o.entry} | Exit: {o.exit_price} | PnL: ${o.realized_pnl:.2f}\n"
            f"SL: {o.sl} | TP: {o.tp} | Exit reason: {exit_reason}\n"
            f"Duration: {o.duration_minutes}min\n"
            f"Notes: {o.notes or 'none'}"
        )
