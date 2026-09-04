import json
import os
from datetime import datetime

STATUS_FILE = "/home/ubuntu/tie-dashboard/data/tie_status.json"
HISTORY_FILE = "/home/ubuntu/tie-dashboard/data/tie_daily_history.json"

def update_history():
    if not os.path.exists(STATUS_FILE):
        return

    try:
        with open(STATUS_FILE, "r") as f:
            status = json.load(f)
        
        daily_pnl = status.get("daily_pnl", 0)
        # Use Jakarta time for date
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        history = {}
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        
        # Update entry for today
        history[date_str] = {
            "pnl": daily_pnl,
            "last_update": datetime.now().isoformat()
        }
        
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
            
        print(f"Updated history for {date_str}: ${daily_pnl}")
    except Exception as e:
        print(f"Error updating history: {e}")

if __name__ == "__main__":
    update_history()
