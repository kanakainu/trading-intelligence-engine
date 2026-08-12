"""Entry quality telemetry — logs every candidate (entry + rejected) to SQLite.
Fields match TIE V4 Entry Quality Validation Pass spec (Aug 2026).
No look-ahead: all values captured at decision time only.
"""
import sqlite3, json, logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("entry_telemetry")

DB_PATH = Path("/home/ubuntu/trading-intelligence-engine/data/candidates.db")

# ── Schema ──────────────────────────────────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    strategy        TEXT,           -- RME | SemiHFT | Bystra
    symbol          TEXT,
    regime          TEXT,
    setup_type      TEXT,
    direction       TEXT,           -- BUY | SELL | NONE

    -- Location
    location_grade  TEXT,           -- GOOD | NEUTRAL | BAD
    location_score  REAL,
    vwap_dist_atr   REAL,
    dist_structure_atr REAL,
    dist_obstacle_atr  REAL,
    available_room_atr REAL,
    location_reason TEXT,

    -- Trigger
    trigger_signal  TEXT,           -- ARMED | WAIT | NONE
    trigger_score   REAL,
    trigger_strength REAL,

    -- Setup
    setup_score     REAL,
    setup_quality   REAL,
    zone_price      REAL,

    -- Market context
    m15_bias        TEXT,
    m5_structure    TEXT,
    atr             REAL,
    spread          REAL,

    -- Risk
    entry_price     REAL,
    sl              REAL,
    tp              REAL,
    rr              REAL,           -- mathematical RR
    structural_rr   REAL,          -- room / sl_dist (structural RR)
    lot             REAL,

    -- Decision
    decision        TEXT,           -- ENTRY | WAIT | REJECT
    rejection_reason TEXT,
    filter_trace    TEXT,           -- JSON array

    -- Classification (post-hoc, filled by followthrough tracker)
    entry_class     TEXT,           -- A B C D E F G (per spec)

    -- Follow-through (filled after N candles by followthrough tracker)
    mfe_1  REAL, mfe_3  REAL, mfe_5  REAL,
    mae_1  REAL, mae_3  REAL, mae_5  REAL,
    time_to_pos_r   REAL,           -- candles to positive R
    time_to_tp      REAL,           -- candles to TP
    final_result_r  REAL,           -- final R outcome

    -- Lateness detection
    is_late         INTEGER DEFAULT 0,  -- 1 = LATE_ENTRY
    lateness_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_ts      ON candidates(ts);
CREATE INDEX IF NOT EXISTS idx_setup   ON candidates(setup_type);
CREATE INDEX IF NOT EXISTS idx_decision ON candidates(decision);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.executescript(_DDL)
    return c


# ── Dataclass ────────────────────────────────────────────────────────────────
@dataclass
class CandidateRecord:
    strategy:           str   = ""
    symbol:             str   = "XAUUSD"
    regime:             str   = ""
    setup_type:         str   = ""
    direction:          str   = ""
    location_grade:     str   = ""
    location_score:     float = 0.0
    vwap_dist_atr:      float = 0.0
    dist_structure_atr: float = 0.0
    dist_obstacle_atr:  float = 0.0
    available_room_atr: float = 0.0
    location_reason:    str   = ""
    trigger_signal:     str   = ""
    trigger_score:      float = 0.0
    trigger_strength:   float = 0.0
    setup_score:        float = 0.0
    setup_quality:      float = 0.0
    zone_price:         float = 0.0
    m15_bias:           str   = ""
    m5_structure:       str   = ""
    atr:                float = 0.0
    spread:             float = 0.0
    entry_price:        float = 0.0
    sl:                 float = 0.0
    tp:                 float = 0.0
    rr:                 float = 0.0
    structural_rr:      float = 0.0
    lot:                float = 0.0
    decision:           str   = "WAIT"
    rejection_reason:   str   = ""
    filter_trace:       list  = field(default_factory=list)
    is_late:            int   = 0
    lateness_reason:    str   = ""


def log_candidate(rec: CandidateRecord) -> int:
    """Insert candidate. Returns row id."""
    try:
        d = asdict(rec)
        d["ts"] = datetime.utcnow().isoformat()
        d["filter_trace"] = json.dumps(d["filter_trace"])
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        with _conn() as c:
            cur = c.execute(f"INSERT INTO candidates ({cols}) VALUES ({placeholders})", list(d.values()))
            return int(cur.lastrowid or -1)
    except Exception as e:
        logger.error("telemetry write failed: %s", e)
        return -1


def update_followthrough(row_id: int, **kwargs) -> None:
    """Update MFE/MAE/class after N candles. Only call with known values."""
    if row_id <= 0:
        return
    try:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [row_id]
        with _conn() as c:
            c.execute(f"UPDATE candidates SET {sets} WHERE id=?", vals)
    except Exception as e:
        logger.error("followthrough update failed: %s", e)


def classify_entry(mfe_1: float, mae_1: float, mae_3: float,
                   available_room: float, trigger_score: float,
                   is_late: bool, location_grade: str) -> str:
    """Post-hoc entry quality grade per spec."""
    if is_late and mae_1 > 0.3:  return "F"  # immediate adverse + late
    if mae_3 > available_room:   return "F"  # MAE wiped room
    if mfe_1 <= 0 and mae_1 > 0.5: return "F"
    if is_late:                  return "C"
    if location_grade == "BAD":  return "D"
    if trigger_score < 10:       return "E"
    if mfe_1 > 0.3 and mae_1 < 0.2: return "A"
    return "B"


# Self-check
if __name__ == "__main__":
    rid = log_candidate(CandidateRecord(
        strategy="RME", direction="BUY", decision="ENTRY",
        regime="TRENDING_BULL", setup_type="TREND_PULLBACK",
        location_grade="GOOD", available_room_atr=1.5, atr=2.0,
        entry_price=2400.0, sl=2397.0, tp=2406.0, rr=2.0
    ))
    assert rid > 0, "insert failed"
    update_followthrough(rid, mfe_1=0.8, mae_1=0.1, entry_class="A")
    print(f"entry_telemetry OK — row {rid}")
