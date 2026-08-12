"""Follow-through tracker — updates MFE/MAE/class after N candles.
Called from tie_production.py scan loop. No look-ahead: only uses
candles already closed at call time.
"""
import logging
from typing import Dict, List
from shared.entry_telemetry import update_followthrough, classify_entry

logger = logging.getLogger("followthrough_tracker")

# In-memory pending: {row_id: {"entry": float, "direction": str, "sl": float,
#                               "tp": float, "candles_seen": int,
#                               "mfe": float, "mae": float,
#                               "available_room": float, "trigger_score": float,
#                               "location_grade": str, "mfe_1": float, "mae_1": float,
#                               "mfe_3": float, "mae_3": float}}
_pending: Dict[int, dict] = {}

_TRACK_CANDLES = 5


def register(row_id: int, entry: float, direction: str,
             sl: float, tp: float,
             available_room_atr: float = 1.0,
             trigger_score: float = 0.0,
             location_grade: str = "NEUTRAL") -> None:
    """Register a new entry for follow-through tracking."""
    if row_id <= 0:
        return
    _pending[row_id] = {
        "entry": entry, "direction": direction, "sl": sl, "tp": tp,
        "candles_seen": 0,
        "mfe": 0.0, "mae": 0.0,
        "mfe_1": None, "mae_1": None,
        "mfe_3": None, "mae_3": None,
        "available_room": available_room_atr,
        "trigger_score": trigger_score,
        "location_grade": location_grade,
        "hit_tp": False, "time_to_pos_r": None, "time_to_tp": None,
    }


def tick(candle: Dict) -> None:
    """Call once per new closed M1 candle. Updates all pending entries."""
    if not _pending:
        return
    high  = float(candle.get("high",  candle.get("High",  0)))
    low   = float(candle.get("low",   candle.get("Low",   0)))
    done  = []
    for rid, s in _pending.items():
        s["candles_seen"] += 1
        n = s["candles_seen"]
        e = s["entry"]
        if s["direction"] == "BUY":
            mfe_now = max(high - e, 0.0)
            mae_now = max(e - low,  0.0)
        else:
            mfe_now = max(e - low,  0.0)
            mae_now = max(high - e, 0.0)
        s["mfe"] = max(s["mfe"], mfe_now)
        s["mae"] = max(s["mae"], mae_now)
        if n == 1:
            s["mfe_1"] = s["mfe"]; s["mae_1"] = s["mae"]
        if n == 3:
            s["mfe_3"] = s["mfe"]; s["mae_3"] = s["mae"]
        if s["time_to_pos_r"] is None and mfe_now > mae_now and mfe_now > 0:
            s["time_to_pos_r"] = n
        tp_hit = (s["direction"] == "BUY" and high >= s["tp"]) or \
                 (s["direction"] == "SELL" and low  <= s["tp"])
        if tp_hit and s["time_to_tp"] is None:
            s["time_to_tp"] = n
        if n >= _TRACK_CANDLES:
            done.append(rid)
    for rid in done:
        _flush(rid)


def _flush(rid: int) -> None:
    s = _pending.pop(rid, None)
    if s is None:
        return
    atr = s["available_room"] if s["available_room"] > 0 else 1.0
    grade = classify_entry(
        mfe_1=s["mfe_1"] or 0.0,
        mae_1=s["mae_1"] or 0.0,
        mae_3=s["mae_3"] or 0.0,
        available_room=atr,
        trigger_score=s["trigger_score"],
        is_late=False,
        location_grade=s["location_grade"],
    )
    update_followthrough(
        rid,
        mfe_1=s["mfe_1"], mfe_3=s["mfe_3"], mfe_5=s["mfe"],
        mae_1=s["mae_1"], mae_3=s["mae_3"], mae_5=s["mae"],
        time_to_pos_r=s["time_to_pos_r"],
        time_to_tp=s["time_to_tp"],
        entry_class=grade,
    )
    logger.debug("followthrough flushed rid=%d grade=%s mfe5=%.2f mae5=%.2f",
                 rid, grade, s["mfe"], s["mae"])


if __name__ == "__main__":
    from shared.entry_telemetry import log_candidate, CandidateRecord
    rid = log_candidate(CandidateRecord(strategy="TEST", direction="BUY",
                                        decision="ENTRY", entry_price=2400.0,
                                        sl=2397.0, tp=2406.0))
    register(rid, 2400.0, "BUY", 2397.0, 2406.0, available_room_atr=2.0, trigger_score=15.0)
    for i in range(5):
        tick({"high": 2400.5 + i, "low": 2399.0 + i})
    assert rid not in _pending, "should be flushed"
    print("followthrough_tracker OK")
