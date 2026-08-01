"""Learning logger — SQLite trade records for C8 optimisation."""
import sqlite3, os
from datetime import datetime, timezone

DB_PATH = os.path.expanduser("~/.hermes/trading/c8_learning.db")

class LearningLogger:
    def __init__(self, db_path=DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db = db_path
        with sqlite3.connect(self._db) as cx:
            cx.execute("""CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, symbol TEXT, market_state TEXT,
                opportunity_score REAL, entry_reason TEXT,
                exit_reason TEXT, hold_seconds REAL,
                pnl REAL, pattern TEXT
            )""")

    def record(self, symbol="XAUUSD", market_state="", opportunity_score=0.0,
               entry_reason="", exit_reason="", hold_seconds=0.0,
               pnl=0.0, pattern=""):
        with sqlite3.connect(self._db) as cx:
            cx.execute("INSERT INTO trades VALUES (NULL,?,?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), symbol, market_state,
                 opportunity_score, entry_reason, exit_reason,
                 hold_seconds, pnl, pattern))

    def summary(self) -> dict:
        with sqlite3.connect(self._db) as cx:
            rows=cx.execute("SELECT hold_seconds,pnl,exit_reason,pattern FROM trades").fetchall()
        if not rows: return {}
        holds=[r[0] for r in rows]; pnls=[r[1] for r in rows]
        wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]
        reasons={}; patterns={}
        for _,_,er,pat in rows:
            reasons[er]=reasons.get(er,0)+1
            patterns[pat]=patterns.get(pat,0)+1
        first_ts=rows[0][0] if rows else None
        elapsed_h=1.0
        if first_ts:
            from datetime import timedelta
            try:
                t0=datetime.fromisoformat(first_ts)
                elapsed_h=max((datetime.now(timezone.utc)-t0).total_seconds()/3600, 1/60)
            except: pass
        return {
            "total": len(rows),
            "win_rate": len(wins)/len(rows),
            "avg_hold": sum(holds)/len(holds),
            "avg_profit": sum(wins)/len(wins) if wins else 0,
            "avg_loss":   sum(losses)/len(losses) if losses else 0,
            "profit_per_hour": sum(pnls)/elapsed_h,
            "by_exit_reason": reasons,
            "by_pattern": patterns,
        }


if __name__=="__main__":
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp=f.name
    lg=LearningLogger(tmp)
    lg.record(pnl=1.5, hold_seconds=90, pattern="breakout", exit_reason="tp_hit")
    lg.record(pnl=-1.0, hold_seconds=120, pattern="impulse", exit_reason="sl_hit")
    s=lg.summary()
    assert s["total"]==2
    assert s["win_rate"]==0.5
    print("learning OK:", s["win_rate"])
