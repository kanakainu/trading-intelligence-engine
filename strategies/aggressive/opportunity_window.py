"""OpportunityWindow — score-based session + liquidity window."""
from datetime import datetime, timezone

def get_session_score(utc_hour: int) -> float:
    # Overlap (12-16) = 100, London=90, NY=80, Asia=40, Off=10
    if 12 <= utc_hour < 16: return 100.0
    if 7 <= utc_hour < 12: return 90.0
    if 17 <= utc_hour < 21: return 80.0
    if 0 <= utc_hour < 3: return 10.0
    return 40.0
