"""Execution Analytics — capture latency, slippage, fill quality.

Submit → Filled timing + price deviation.

NO trading logic. Pure metrics.
"""
import time
import sqlite3
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("ExecutionAnalytics")

DB_PATH = "/home/ubuntu/trading-intelligence-engine/data/episodes.db"


@dataclass
class ExecutionMetrics:
    order_id: str
    symbol: str
    direction: str
    submit_ts: float
    filled_ts: Optional[float] = None
    submit_price: float = 0.0
    filled_price: float = 0.0
    latency_ms: float = 0.0
    slippage_pts: float = 0.0
    spread_at_submit: float = 0.0


class ExecutionTracker:
    """Track order execution quality.

    Job:
    - Record submit timestamp
    - Record filled timestamp
    - Calculate latency (ms) and slippage (pts)
    - Store to DB
    """

    def __init__(self):
        self._pending: dict[str, ExecutionMetrics] = {}
        self._conn = sqlite3.connect(DB_PATH, timeout=5)
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_metrics (
                order_id TEXT PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                submit_ts REAL,
                filled_ts REAL,
                submit_price REAL,
                filled_price REAL,
                latency_ms REAL,
                slippage_pts REAL,
                spread_at_submit REAL
            )
        """)
        self._conn.commit()

    def record_submit(self, order_id: str, symbol: str, direction: str, price: float, spread: float = 0.0):
        """Call when order submitted to broker."""
        self._pending[order_id] = ExecutionMetrics(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            submit_ts=time.time(),
            submit_price=price,
            spread_at_submit=spread
        )
        log.info(f"Execution: submit {order_id} {symbol} {direction} @ {price}")

    def record_fill(self, order_id: str, filled_price: float):
        """Call when order filled by broker."""
        if order_id not in self._pending:
            log.warning(f"Execution: fill for unknown order {order_id}")
            return

        m = self._pending[order_id]
        m.filled_ts = time.time()
        m.filled_price = filled_price
        m.latency_ms = (m.filled_ts - m.submit_ts) * 1000

        # Slippage = actual - expected (absolute)
        m.slippage_pts = abs(m.filled_price - m.submit_price)

        # Store to DB
        self._conn.execute("""
            INSERT OR REPLACE INTO execution_metrics
            (order_id, symbol, direction, submit_ts, filled_ts, submit_price, filled_price, latency_ms, slippage_pts, spread_at_submit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m.order_id, m.symbol, m.direction, m.submit_ts, m.filled_ts,
            m.submit_price, m.filled_price, m.latency_ms, m.slippage_pts, m.spread_at_submit
        ))
        self._conn.commit()

        log.info(f"Execution: filled {order_id} @ {filled_price} | latency={m.latency_ms:.1f}ms slippage={m.slippage_pts:.2f}pts")

        del self._pending[order_id]

    def get_stats(self, symbol: str = None, limit: int = 100) -> dict:
        """Return avg latency/slippage for symbol."""
        query = "SELECT latency_ms, slippage_pts FROM execution_metrics"
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += f" ORDER BY submit_ts DESC LIMIT {limit}"

        rows = self._conn.execute(query, params).fetchall()
        if not rows:
            return {"avg_latency_ms": 0, "avg_slippage_pts": 0, "count": 0}

        latencies = [r[0] for r in rows if r[0]]
        slippages = [r[1] for r in rows if r[1]]

        return {
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "avg_slippage_pts": sum(slippages) / len(slippages) if slippages else 0,
            "count": len(rows)
        }
