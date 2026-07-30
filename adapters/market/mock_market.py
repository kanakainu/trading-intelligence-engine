"""Mock market provider — synthetic ticks, candles, regimes. No real API."""
import random
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from adapters.lifecycle import AdapterState
from adapters.market.base import MarketAdapterBase
from adapters.market.models import Tick, Candle, MarketSnapshot, HealthReport
from adapters.market.normalizer import normalize_tick, normalize_candle
from adapters.market.cache import MarketCache
from adapters.market.exceptions import MarketConnectionError, SubscriptionError


class MockMarketAdapter(MarketAdapterBase):
    """
    Mock market provider — synthetic ticks, candles, regimes.
    No external API. Pure in-memory simulation.
    """
    def __init__(self, seed: int = 42):
        super().__init__()
        self._rng = random.Random(42)
        self._cache = MarketCache(default_ttl=5)
        self._subscriptions: Dict[str, Dict[str, Decimal]] = {}  # symbol -> {bid, ask}
        self._candles: Dict[str, Dict[str, List]] = {}
        self._regime = "ranging"
        self._last_price = Decimal('2000.00')
        self._trend = Decimal('0.0')
        self._symbols = {"XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "ETHUSD"}

    @property
    def name(self) -> str: return "mock_market"

    def initialize(self):
        self._set_state(AdapterState.INITIALIZED)
        self._init_symbols()

    def connect(self):
        self._set_state(AdapterState.CONNECTED)
        self._start_generator()

    def disconnect(self):
        self._set_state(AdapterState.DISCONNECTED)
        self._running = False

    def health_check(self) -> Dict:
        return {
            "provider": "mock",
            "status": self._state.value,
            "connected": self._state.value == "CONNECTED",
            "subscriptions": list(self._subscriptions.keys()),
            "latency_ms": 0.5,
            "last_tick": datetime.now().isoformat(),
            "error": None
        }

    # ── internal ──
    def _init_symbols(self):
        for sym in self._symbols:
            mid = Decimal('2000') if sym == 'XAUUSD' else Decimal('1.0800')
            spread = Decimal('20') if sym == 'XAUUSD' else Decimal('10')
            self._subscriptions[sym] = {
                'bid': mid - Decimal('0.5'),
                'ask': mid + Decimal('0.5'),
            }

    def _start_generator(self):
        self._running = True
        self._gen_thread = threading.Thread(target=self._generate_loop, daemon=True)
        self._running = True
        self._gen_thread.start()

    def _generate_loop(self):
        while self._running and self._state.value == "CONNECTED":
            self._update_prices()
            time.sleep(0.1)

    def _update_prices(self):
        for sym in self._symbols:
            sub = self._subscriptions[sym]
            # Random walk with regime
            change = self._rng.uniform(-0.05, 0.05) + float(self._trend)
            mid = Decimal(str(self._rng.uniform(
                float(self._last_price) - 0.1, float(self._last_price) + 0.1
            ))) if hasattr(self, '_last_price') else Decimal('2000')
            spread = Decimal('20')
            bid = mid - spread / 2
            ask = mid + spread / 2
            self._subscriptions[sym] = {'bid': bid, 'ask': ask}

            # Cache tick
            from adapters.market.models import Tick
            from decimal import Decimal
            tick = Tick(
                symbol=sym, bid=bid, ask=ask,
                spread=Decimal('20'),
                timestamp=datetime.now(timezone.utc)
            )
            self._cache.set_tick(Tick(symbol=sym, bid=bid, ask=ask, spread=Decimal('20'),
                                     timestamp=datetime.now(timezone.utc)))

    def subscribe(self, symbol: str):
        self._subscriptions.setdefault(symbol, {'bid': Decimal('0'), 'ask': Decimal('0')})

    def unsubscribe(self, symbol: str):
        self._subscriptions.pop(symbol, None)

    def get_latest_tick(self, symbol: str) -> Optional[Dict]:
        return self._cache.get_tick(symbol)

    def get_latest_candle(self, symbol: str, timeframe: str):
        return None  # TODO

    def get_market_snapshot(self, symbol: str):
        return None  # TODO