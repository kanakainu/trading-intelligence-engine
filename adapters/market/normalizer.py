"""Data normalizer — raw provider data → standardized internal models."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
from adapters.market.models import Tick, Candle, MarketSnapshot


def normalize_timestamp(ts: Any) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def normalize_price(val: Any, precision: int = 2) -> Decimal:
    try:
        d = Decimal(str(val))
        return d.quantize(Decimal('0.01') if precision == 2 else Decimal('0.00001'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def normalize_volume(val: Any) -> Decimal:
    try:
        return Decimal(str(val)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def normalize_symbol(sym: str) -> str:
    return sym.replace('.', '').replace('/', '').upper()


def normalize_spread(ask: Decimal, bid: Decimal) -> Decimal:
    return (ask - bid).quantize(Decimal('0.01'))


def normalize_tick(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'symbol':   normalize_symbol(raw.get('symbol', '')),
        'bid':      normalize_price(raw.get('bid', 0)),
        'ask':      normalize_price(raw.get('ask', 0)),
        'spread':   normalize_spread(
                        normalize_price(raw.get('ask', 0)),
                        normalize_price(raw.get('bid', 0))),
        'timestamp': normalize_timestamp(raw.get('timestamp')),
        'volume':   normalize_volume(raw.get('volume', 0)),
    }


def normalize_candle(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'symbol':    normalize_symbol(raw.get('symbol', '')),
        'timeframe': raw.get('timeframe', 'M5'),
        'open':      normalize_price(raw.get('open', 0)),
        'high':      normalize_price(raw.get('high', 0)),
        'low':       normalize_price(raw.get('low', 0)),
        'close':     normalize_price(raw.get('close', 0)),
        'volume':    normalize_volume(raw.get('volume', 0)),
        'timestamp': normalize_timestamp(raw.get('timestamp')),
    }