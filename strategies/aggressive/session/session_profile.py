"""Session Profile — scored trading sessions with threshold gate.

Scores based on historical liquidity + volatility of each session for XAUUSD.
Output: SessionSnapshot (name, score 0-100, allowed bool)
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class SessionSnapshot:
    session:  str    # LONDON | NEW_YORK | ASIAN | OVERLAP | OFF
    score:    int    # 0-100
    allowed:  bool   # score >= MIN_SCORE


# Session scores — tuned for XAUUSD semi-HFT
SESSION_SCORES = {
    "OVERLAP":   98,   # London + NY overlap = most liquid
    "LONDON":    95,
    "NEW_YORK":  88,
    "ASIAN":     55,   # XAUUSD tetap liquid pagi WIB
    "OFF":       10,   # dead hours 00-02 UTC
}

MIN_SCORE = 50   # below = skip trading


def _session_name(utc_hour: int) -> str:
    """Map UTC hour → session name."""
    # London: 07-16 UTC
    # New York: 12-21 UTC
    # Overlap: 12-16 UTC
    # Asian: 00-07 UTC
    if 12 <= utc_hour < 16:
        return "OVERLAP"
    elif 7 <= utc_hour < 12 or 16 <= utc_hour < 17:
        return "LONDON"
    elif 17 <= utc_hour < 21:
        return "NEW_YORK"
    elif 0 <= utc_hour < 3:
        return "OFF"
    else:
        return "ASIAN"


def evaluate_session(now: datetime = None) -> SessionSnapshot:
    if now is None:
        now = datetime.now(timezone.utc)
    name  = _session_name(now.hour)
    score = SESSION_SCORES.get(name, 10)
    return SessionSnapshot(
        session=name,
        score=score,
        allowed=score >= MIN_SCORE,
    )


if __name__ == "__main__":
    from datetime import timezone
    # London hour = 10 UTC
    t = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    snap = evaluate_session(t)
    assert snap.session == "LONDON" and snap.allowed, f"Got {snap}"
    # Asian = not allowed
    t2 = datetime(2026, 1, 1, 4, 0, tzinfo=timezone.utc)
    snap2 = evaluate_session(t2)
    assert not snap2.allowed, f"Asian should be blocked, got {snap2}"
    print(f"OK: {snap.session}={snap.score}, {snap2.session}={snap2.score}")
