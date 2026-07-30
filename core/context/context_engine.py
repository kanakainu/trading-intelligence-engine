"""Context Engine — raw market data → MarketContext. No pattern detection."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from core.context.context_model import (
    MarketContext, Trend, Session, Volatility, MarketStatus
)

log = logging.getLogger(__name__)

# UTC hour ranges per session
_SESSIONS = {
    Session.ASIA:     (0,  9),
    Session.LONDON:   (7,  16),
    Session.NEW_YORK: (12, 21),
}


class ContextEngine:
    """
    Accepts raw market data dicts and produces a MarketContext.
    No pattern detection. No trading rules. No BUY/SELL/WAIT.
    """

    def build(self, market_data: Dict[str, Any]) -> MarketContext:
        symbol    = market_data.get("symbol", "UNKNOWN")
        timestamp = market_data.get("timestamp", datetime.now(timezone.utc))
        candles: List[Dict] = market_data.get("candles", [])
        spread    = float(market_data.get("spread", 0.0))
        is_open   = bool(market_data.get("market_open", True))

        trend      = self._calc_trend(candles)
        atr        = self._calc_atr(candles)
        volatility = self._classify_volatility(atr, candles)
        session    = self._detect_session(timestamp)
        status     = MarketStatus.OPEN if is_open else MarketStatus.CLOSED

        ctx = MarketContext(
            symbol=symbol,
            timestamp=timestamp,
            trend=trend,
            session=session,
            atr=atr,
            spread=spread,
            volatility=volatility,
            market_status=status,
        )
        log.info(f"Context built: {symbol} trend={trend} session={session} "
                 f"atr={atr:.4f} spread={spread:.1f} vol={volatility}")
        return ctx

    # ── internal helpers (generic math, no trading rules) ─────────────────

    def _calc_trend(self, candles: List[Dict]) -> Trend:
        if len(candles) < 3:
            return Trend.UNKNOWN
        closes = [c["close"] for c in candles[-10:]]
        first, last = closes[0], closes[-1]
        diff = (last - first) / first if first else 0
        if diff > 0.001:
            return Trend.BULLISH
        if diff < -0.001:
            return Trend.BEARISH
        return Trend.SIDEWAYS

    def _calc_atr(self, candles: List[Dict], period: int = 14) -> float:
        if len(candles) < 2:
            return 0.0
        trs = []
        for i in range(1, min(period + 1, len(candles))):
            h = candles[i]["high"]
            l = candles[i]["low"]
            pc = candles[i - 1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return sum(trs) / len(trs) if trs else 0.0

    def _classify_volatility(self, atr: float, candles: List[Dict]) -> Volatility:
        if not candles or atr == 0:
            return Volatility.LOW
        avg_close = sum(c["close"] for c in candles[-14:]) / min(14, len(candles))
        ratio = atr / avg_close if avg_close else 0
        if ratio > 0.005:
            return Volatility.HIGH
        if ratio > 0.002:
            return Volatility.MEDIUM
        return Volatility.LOW

    def _detect_session(self, ts: datetime) -> Session:
        hour = ts.hour if ts.tzinfo else ts.replace(tzinfo=timezone.utc).hour
        in_london   = _SESSIONS[Session.LONDON][0]   <= hour < _SESSIONS[Session.LONDON][1]
        in_new_york = _SESSIONS[Session.NEW_YORK][0] <= hour < _SESSIONS[Session.NEW_YORK][1]
        in_asia     = _SESSIONS[Session.ASIA][0]     <= hour < _SESSIONS[Session.ASIA][1]
        if in_london and in_new_york:
            return Session.OVERLAP
        if in_london:
            return Session.LONDON
        if in_new_york:
            return Session.NEW_YORK
        if in_asia:
            return Session.ASIA
        return Session.CLOSED
