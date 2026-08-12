"""Volatility Position Sizing — Goldman Sachs inspired ATR-based lot calculator.

Formula: Lot = (Equity * Risk%) / (ATR * PipValue)
Fallback: equity-based lot from fast_risk._lot(equity) when disabled.

Toggle: config/features.json → volatility_sizing: true/false
"""
import json
import os
from typing import Any, Optional

_FEATURES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "features.json")
_PIP_VALUE = 1.0  # XAUUSD: 1 pip = $1 per 0.01 lot


def _load_config() -> dict:
    try:
        with open(_FEATURES_PATH) as f:
            return json.load(f)
    except Exception:
        return {"volatility_sizing": True, "volatility_risk_pct": 0.01,
                "volatility_min_lot": 0.01, "volatility_max_lot": 0.10}


def calc_lot(equity: float, atr: float, strategy_id: str = "aggressive") -> float:
    """
    Calculate lot size based on volatility (ATR) and strategy performance.
    """
    cfg = _load_config()
    
    # Base lot calculation
    if not cfg.get("volatility_sizing", True) or atr <= 0:
        from strategies.semi_hft.fast_risk import _lot
        base_lot = _lot(equity)
    else:
        risk_pct = cfg.get("volatility_risk_pct", 0.01)
        risk_usd = equity * risk_pct
        base_lot = risk_usd / (atr * _PIP_VALUE * 100)

    # Apply Portfolio Multiplier (GS Framework 5)
    from shared.portfolio_optimizer import get_multiplier
    multiplier = get_multiplier(strategy_id)
    lot = base_lot * multiplier

    print(f"DEBUG_LOT: strat={strategy_id} base={base_lot:.2f} multi={multiplier:.2f} res={lot:.2f} atr={atr:.2f}")

    # Clamp to bounds, round to 2dp
    min_lot = cfg.get("volatility_min_lot", 0.01)
    max_lot = cfg.get("volatility_max_lot", 0.15) # Boosted max for framework 5
    lot = round(max(min_lot, min(max_lot, lot)), 2)
    return lot
