"""Portfolio Optimizer — Goldman Sachs inspired dynamic allocation.

Calculates strategy performance metrics and provides a lot multiplier:
- Strong performance -> 1.5x lot
- Weak performance -> 0.5x lot (protection)
- Average -> 1.0x

Metrics based on rolling 24h performance from MT5 history.
"""
import json
import os
from typing import Dict

_FEATURES_PATH = "/home/ubuntu/trading-intelligence-engine/config/features.json"
_PERF_CACHE = "/tmp/tie_strategy_perf.json"

def _load_config() -> dict:
    try:
        with open(_FEATURES_PATH) as f:
            return json.load(f)
    except Exception:
        return {"auto_allocation": True}

def get_multiplier(strategy_id: str) -> float:
    """
    Returns a lot multiplier (0.5 to 1.5) based on strategy performance.
    """
    cfg = _load_config()
    if not cfg.get("auto_allocation", True):
        return 1.0

    try:
        if not os.path.exists(_PERF_CACHE):
            return 1.0
        
        with open(_PERF_CACHE) as f:
            perf_data = json.load(f)
            
        strat_perf = perf_data.get(strategy_id, {})
        win_rate = strat_perf.get("win_rate", 0.5)
        profit_factor = strat_perf.get("profit_factor", 1.0)

        # GS Optimization Logic
        if win_rate >= 0.65 and profit_factor >= 1.5:
            return 1.5  # On fire!
        if win_rate <= 0.40 or profit_factor <= 0.8:
            return 0.5  # Protection mode
            
        return 1.0
    except Exception:
        return 1.0

def update_performance(stats: Dict[str, dict]):
    """Called by manager/observatory to update rolling performance."""
    try:
        with open(_PERF_CACHE, "w") as f:
            json.dump(stats, f, indent=4)
    except Exception:
        pass
