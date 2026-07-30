"""Fact Compiler — MarketContext → FactSet. No Setup, no Decision, no YAML."""
import logging
from typing import List
from core.context.context_model import MarketContext, Trend, Session, Volatility, MarketStatus
from core.facts.typed_facts import (
    TypedFact, TrendFact, SessionFact, ATRFact, SpreadFact,
    VolatilityFact, MarketStatusFact,
)
from core.facts.fact_compiler_set import TypedFactSet

log = logging.getLogger(__name__)


class FactCompiler:
    """
    Converts MarketContext → TypedFactSet.
    Reads nothing from YAML. Knows nothing about Setups or Decisions.
    Output = objective market observations only.
    """

    def compile(self, context: MarketContext) -> "TypedFactSet":
        facts: List[TypedFact] = []

        # Trend
        facts.append(TrendFact(
            value=context.trend.value,
            timeframe=getattr(context, "timeframe", ""),
        ))

        # Session
        facts.append(SessionFact(value=context.session.value))

        # ATR classification
        if context.atr > 0:
            facts.append(ATRFact(value=round(context.atr, 5)))

        # Spread classification
        facts.append(SpreadFact(
            value="high" if context.spread > 300 else "normal",
            metadata={"raw": context.spread},
        ))

        # Volatility
        facts.append(VolatilityFact(value=context.volatility.value))

        # Market status
        facts.append(MarketStatusFact(value=context.market_status.value))

        fs = TypedFactSet(symbol=context.symbol, timestamp=context.timestamp)
        for f in facts:
            fs.add(f)

        log.info(f"FactCompiler compiled {len(fs)} facts for {context.symbol}")
        return fs
