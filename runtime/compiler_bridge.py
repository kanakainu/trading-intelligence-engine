"""
CompilerBridge — Phase 5.1 Runtime Migration.
Phase 6.2: HCK Bridge integration — inject episodic/semantic memory before compile.

Converts ExecutionContext (Phase 4 runtime) → Phase 3 pipeline invocation.
Pipeline: ExecutionContext → MarketContext → FactSet → SetupMatch[] → TradeDecision

No trading logic here. Pure orchestration bridge.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from core.context.context_model import MarketContext, Trend, Session, Volatility, MarketStatus
from core.facts.fact_compiler import FactCompiler
from core.setup.setup_resolver import SetupResolver
from core.decision.decision_pipeline import DecisionPipeline
from core.decision.trade_decision import TradeDecision
from core.decision.decision_policy import DecisionPolicy
from runtime.context_builder import ExecutionContext

log = logging.getLogger(__name__)

# Mapping helpers — convert raw string market data to Phase 3 enums
_TREND_MAP = {
    "bullish": Trend.BULLISH, "bearish": Trend.BEARISH,
    "sideways": Trend.SIDEWAYS, "ranging": Trend.SIDEWAYS,
}
_SESSION_MAP = {
    "asia": Session.ASIA, "asian": Session.ASIA,
    "london": Session.LONDON, "europe": Session.LONDON,
    "new_york": Session.NEW_YORK, "ny": Session.NEW_YORK, "newyork": Session.NEW_YORK,
    "overlap": Session.OVERLAP,
}
_VOL_MAP = {
    "low": Volatility.LOW, "normal": Volatility.LOW,
    "medium": Volatility.MEDIUM, "moderate": Volatility.MEDIUM,
    "high": Volatility.HIGH, "extreme": Volatility.HIGH,
}


class CompilerBridge:
    """
    Bridges Phase 4 ExecutionContext to Phase 3 Intelligence Compiler.
    Phase 6.2: optional HCKBridge injects episodic/semantic context before compile.
    Owns NO trading logic — only translation + invocation.
    """

    def __init__(
        self,
        setup_definitions: List[Dict[str, Any]],
        policy: Optional[DecisionPolicy] = None,
        hck_bridge: Any = None,
    ):
        self._fact_compiler = FactCompiler()
        self._setup_resolver = SetupResolver(setup_definitions)
        self._decision_pipeline = DecisionPipeline(policy or DecisionPolicy())
        self._hck: Any = hck_bridge  # optional HCKBridge

    def compile(self, ctx: ExecutionContext) -> TradeDecision:
        """
        Main bridge entry point.
        ExecutionContext → [HCK context inject] → MarketContext → FactSet → SetupMatch[] → TradeDecision
        """
        # ── Phase 6.2: inject HCK memory into ctx.memory ──────────────────
        if self._hck:
            canonical_id = ctx.metadata.get("canonical_id") or ctx.metadata.get("user_id", "system")
            try:
                episodes = self._hck.get_recent_episodes(canonical_id, limit=5)
                semantic  = self._hck.get_semantic_memory(canonical_id, limit=10)
                ctx.memory["hck_episodes"] = episodes
                ctx.memory["hck_semantic"]  = semantic
                log.info(f"HCK injected: {len(episodes)} eps, {len(semantic)} sem for {canonical_id}")
            except Exception as e:
                log.warning(f"HCK inject failed (non-fatal): {e}")
        # ──────────────────────────────────────────────────────────────────
        market_ctx = self._build_market_context(ctx)
        fact_set = self._fact_compiler.compile(market_ctx)
        fact_names: Set[str] = {f.name for f in fact_set._facts}
        context_facts: Dict[str, str] = {
            "trend": market_ctx.trend.value,
            "session": market_ctx.session.value,
            "volatility": market_ctx.volatility.value,
            "market_status": market_ctx.market_status.value,
        }
        pattern_ids: Set[str] = set(ctx.runtime.get("pattern_ids", []))
        setup_matches = self._setup_resolver.resolve(fact_names, pattern_ids, context_facts)
        decision = self._decision_pipeline.decide(
            candidates=setup_matches,
            context={**ctx.market, **ctx.runtime, "execution_id": ctx.execution_id},
        )
        log.info(
            f"CompilerBridge: exec={ctx.execution_id} "
            f"facts={len(fact_names)} matches={len(setup_matches)} "
            f"decision={decision.action}"
        )
        return decision

    # ── private ──────────────────────────────────────────────────────────
    def _build_market_context(self, ctx: ExecutionContext) -> MarketContext:
        m = ctx.market
        raw_trend = str(m.get("trend", "unknown")).lower()
        raw_session = str(m.get("session", "closed")).lower()
        raw_vol = str(m.get("volatility", "low")).lower()
        raw_status = str(m.get("market_status", "open")).lower()

        return MarketContext(
            symbol=m.get("symbol", ctx.metadata.get("symbol", "UNKNOWN")),
            timestamp=m.get("timestamp") or ctx.timestamp or datetime.now(timezone.utc),
            trend=_TREND_MAP.get(raw_trend, Trend.UNKNOWN),
            session=_SESSION_MAP.get(raw_session, Session.CLOSED),
            atr=float(m.get("atr", 0.0)),
            spread=float(m.get("spread", 0.0)),
            volatility=_VOL_MAP.get(raw_vol, Volatility.LOW),
            market_status=MarketStatus.OPEN if raw_status == "open" else MarketStatus.CLOSED,
            metadata=m.get("metadata", {}),
        )
