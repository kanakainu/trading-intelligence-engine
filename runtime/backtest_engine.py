"""BacktestEngine v3 — Trailing SL + Partial TP + 200 candle forward window.
Real H1 S/R, pullback detection, RR filter ≥ 1.5, confidence filter ≥ 0.70.
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from core.context.context_model import MarketContext
from strategy.orchestrator import StrategyOrchestrator
from core.decision.trade_decision import WAIT

log = logging.getLogger("BacktestEngine")

def find_nearest_sr(h1_candles: List[Dict], direction: str, entry_price: float) -> Optional[float]:
    """Nearest S/R from H1 candles."""
    levels = []
    for c in h1_candles:
        levels.append(float(c["high"]))
        levels.append(float(c["low"]))
    
    if direction == "SELL":
        supports = [l for l in levels if l < entry_price]
        return max(supports) if supports else None
    else:
        resistances = [l for l in levels if l > entry_price]
        return min(resistances) if resistances else None

def find_swing_sr(candles: List[Dict]) -> Dict:
    """Swing S/R from candles."""
    if len(candles) < 10:
        return {"support": 0, "resistance": 0}
    
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    
    return {
        "support": min(lows[-20:]) if len(lows) >= 20 else min(lows),
        "resistance": max(highs[-20:]) if len(highs) >= 20 else max(highs)
    }

class BacktestEngine:
    def __init__(self, orchestrator: StrategyOrchestrator, min_confidence: float = 0.70):
        self.orchestrator = orchestrator
        self.min_confidence = min_confidence
        self.trades = []
        self.skipped_rr = 0
        self.skipped_conf = 0

    def run(self, symbol: str, candles: Dict[str, List[Dict]]):
        m5 = candles.get("M5", [])
        m15 = candles.get("M15", [])
        h1 = candles.get("H1", [])
        if len(m5) < 100 or len(h1) < 20:
            return {"error": "Insufficient data"}

        for i in range(80, len(m5) - 200):
            t_now = m5[i]["time"]
            h1_window = [c for c in h1 if c["time"] < t_now][-20:]
            if len(h1_window) < 5:
                continue

            price = m5[i]["close"]
            sr = find_swing_sr(h1_window)

            ctx = MarketContext(symbol=symbol, timestamp=None)
            ctx.metadata.update({
                "candles": {
                    "M5": m5[i - 80:i],
                    "M15": [c for c in m15 if c["time"] < t_now][-40:],
                    "H1": h1_window,
                },
                "current_price": price,
                "h1_support": sr["support"],
                "h1_resistance": sr["resistance"],
                "h1_trend": "bullish" if h1_window[-1]["close"] > h1_window[-5]["close"] else "bearish",
                "atr": (sr["resistance"] - sr["support"]) / 20,
                "nearest_support": sr["support"],
                "nearest_resistance": sr["resistance"],
            })

            decision = self.orchestrator.best_decision(ctx)
            if decision.action != WAIT:
                # Confidence filter
                if decision.confidence < self.min_confidence:
                    self.skipped_conf += 1
                    continue
                
                self._execute(decision, m5[i - 40 : i + 200])

        return self._report()

    def _execute(self, decision, forward_candles):
        z = decision.metadata.get("entry_zone")
        if not z:
            return

        sl_orig = decision.metadata.get("sl")
        tp = decision.metadata.get("take_profit")
        direction = decision.action
        if not sl_orig or not tp:
            return

        # RR filter
        mid_entry = (z["high"] + z["low"]) / 2
        if direction == "BUY":
            risk = mid_entry - sl_orig
            reward = tp - mid_entry
        else:
            risk = sl_orig - mid_entry
            reward = mid_entry - tp

        if risk <= 0 or reward / risk < 1.5:
            self.skipped_rr += 1
            return

        # Find pullback
        entry_idx = -1
        for idx, c in enumerate(forward_candles):
            low, high = float(c["low"]), float(c["high"])
            if direction == "BUY" and low <= z["high"] and low >= z["low"]:
                entry_idx = idx
                break
            if direction == "SELL" and high >= z["low"] and high <= z["high"]:
                entry_idx = idx
                break

        if entry_idx == -1:
            return  # no pullback

        # Walk forward with trailing SL + partial TP
        sl = sl_orig
        partial_closed = False
        peak_profit = 0

        for c in forward_candles[entry_idx:]:
            low, high = float(c["low"]), float(c["high"])
            
            # Check SL
            if direction == "BUY" and low <= sl:
                pnl = -risk if not partial_closed else 0  # if partial closed, SL hit on rest = breakeven
                self.trades.append({"setup": decision.setup_name, "result": "SL", "pnl": pnl})
                return
            if direction == "SELL" and high >= sl:
                pnl = -risk if not partial_closed else 0
                self.trades.append({"setup": decision.setup_name, "result": "SL", "pnl": pnl})
                return
            
            # Partial TP at 1R
            if not partial_closed:
                if direction == "BUY" and high >= mid_entry + risk:
                    partial_closed = True
                    peak_profit = risk  # 50% closed at 1R
                    sl = mid_entry  # move SL to breakeven
                if direction == "SELL" and low <= mid_entry - risk:
                    partial_closed = True
                    peak_profit = risk
                    sl = mid_entry
            
            # Trail SL at 50% of peak
            if partial_closed:
                if direction == "BUY":
                    current_profit = high - mid_entry
                    if current_profit > peak_profit:
                        peak_profit = current_profit
                        sl = mid_entry + peak_profit * 0.5  # trail at 50%
                else:
                    current_profit = mid_entry - low
                    if current_profit > peak_profit:
                        peak_profit = current_profit
                        sl = mid_entry - peak_profit * 0.5
            
            # Full TP
            if direction == "BUY" and high >= tp:
                total_pnl = risk + reward if not partial_closed else risk + (reward - risk)  # partial=1R + rest
                self.trades.append({"setup": decision.setup_name, "result": "TP", "pnl": total_pnl})
                return
            if direction == "SELL" and low <= tp:
                total_pnl = risk + reward if not partial_closed else risk + (reward - risk)
                self.trades.append({"setup": decision.setup_name, "result": "TP", "pnl": total_pnl})
                return

    def _report(self):
        total = len(self.trades)
        wins = len([t for t in self.trades if t["result"] == "TP"])
        losses = len([t for t in self.trades if t["result"] == "SL"])
        total_pnl = sum(t["pnl"] for t in self.trades)
        
        setups = {}
        for t in self.trades:
            s = t["setup"]
            if s not in setups:
                setups[s] = {"wins": 0, "losses": 0, "pnl": 0}
            if t["result"] == "TP":
                setups[s]["wins"] += 1
            else:
                setups[s]["losses"] += 1
            setups[s]["pnl"] += t["pnl"]

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total) if total else 0,
            "net_pnl": total_pnl,
            "avg_pnl": (total_pnl / total) if total else 0,
            "skipped_rr": self.skipped_rr,
            "skipped_conf": self.skipped_conf,
            "per_setup": setups,
        }
