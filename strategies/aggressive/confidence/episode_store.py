"""EpisodeStore — sqlite3 trade outcome memory for ConfidenceEngine.

Stores (symbol, setup_name, direction, outcome) per trade.
Feeds historical_success_rate into compute_confidence().

ponytail: add regime/session filter when enough data accumulated (>200 episodes).
"""
from __future__ import annotations
import sqlite3
import os
import logging
from contextlib import contextmanager

log = logging.getLogger("EpisodeStore")

DB_PATH = os.environ.get("TIE_EPISODE_DB", "/home/ubuntu/trading-intelligence-engine/data/episodes.db")

_CREATE = """
CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    symbol      TEXT NOT NULL,
    setup_name  TEXT NOT NULL,
    direction   TEXT NOT NULL,
    outcome     TEXT NOT NULL,   -- WIN | LOSS | BREAKEVEN
    pnl_pts     REAL DEFAULT 0.0
)
"""
_IDX = "CREATE INDEX IF NOT EXISTS ep_sym_setup ON episodes(symbol, setup_name)"


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=5)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _ensure():
    with _conn() as c:
        c.execute(_CREATE)
        c.execute(_IDX)


_ensure()


def record(symbol: str, setup_name: str, direction: str, outcome: str, pnl_pts: float = 0.0) -> None:
    """Record trade outcome. outcome = WIN | LOSS | BREAKEVEN."""
    import time
    with _conn() as c:
        c.execute(
            "INSERT INTO episodes(ts, symbol, setup_name, direction, outcome, pnl_pts) VALUES (?,?,?,?,?,?)",
            (time.time(), symbol.upper(), setup_name, direction.upper(), outcome.upper(), pnl_pts)
        )
    log.debug("Episode recorded: %s %s %s %s pnl=%.2f", symbol, setup_name, direction, outcome, pnl_pts)


def success_rate(symbol: str, setup_name: str, min_episodes: int = 5) -> float:
    """Return WIN rate 0-100 for symbol+setup. Returns 50.0 (neutral) if < min_episodes."""
    with _conn() as c:
        rows = c.execute(
            "SELECT outcome FROM episodes WHERE symbol=? AND setup_name=? ORDER BY ts DESC LIMIT 50",
            (symbol.upper(), setup_name)
        ).fetchall()
    if len(rows) < min_episodes:
        return 50.0  # neutral — not enough data
    wins = sum(1 for (o,) in rows if o == "WIN")
    return round((wins / len(rows)) * 100, 1)


def recent_stats(symbol: str, limit: int = 20) -> dict:
    """Return {total, wins, losses, win_rate} for last N episodes of symbol."""
    with _conn() as c:
        rows = c.execute(
            "SELECT outcome FROM episodes WHERE symbol=? ORDER BY ts DESC LIMIT ?",
            (symbol.upper(), limit)
        ).fetchall()
    total = len(rows)
    wins  = sum(1 for (o,) in rows if o == "WIN")
    losses = sum(1 for (o,) in rows if o == "LOSS")
    return {"total": total, "wins": wins, "losses": losses,
            "win_rate": round((wins / total * 100) if total else 0.0, 1)}
