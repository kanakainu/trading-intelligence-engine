"""OpportunityWindow — session-based scoring."""
from datetime import datetime, timezone

def get_session_score(utc_hour: int) -> float:
    """Session scoring 0-100. Higher = peak market activity."""
    h = utc_hour
    
    # Peak volatility hours (London/NY overlap)
    if 12 <= h < 16:  return 100.0 # Peak Overlap
    if 7 <= h < 16:   return 90.0  # London
    if 12 <= h < 21:  return 85.0  # NY
    
    # Asia session - crypto active
    return 70.0  

if __name__ == "__main__":
    for h in range(0, 24, 4):
        print(f"UTC {h:02d}:00 Score: {get_session_score(h)}")
