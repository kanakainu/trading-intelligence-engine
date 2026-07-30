"""Context Registry — stores active MarketContext per symbol."""
import logging
from typing import Dict, Optional
from core.context.context_model import MarketContext

log = logging.getLogger(__name__)


class ContextRegistry:
    def __init__(self):
        self._store: Dict[str, MarketContext] = {}

    def update(self, ctx: MarketContext) -> None:
        self._store[ctx.symbol] = ctx
        log.debug(f"ContextRegistry updated: {ctx.symbol}")

    def get(self, symbol: str) -> Optional[MarketContext]:
        return self._store.get(symbol)

    def all(self) -> Dict[str, MarketContext]:
        return dict(self._store)

    def clear(self, symbol: Optional[str] = None) -> None:
        if symbol:
            self._store.pop(symbol, None)
        else:
            self._store.clear()
