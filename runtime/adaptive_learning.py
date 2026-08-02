"""Adaptive Learning Engine — Post-mortem analysis with auto-adjust.

Trade selesai → Post-mortem → Update thresholds/budgets.

NO manual tuning. Bot learns from real results.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
import sqlite3
import logging

log = logging.getLogger("AdaptiveLearning")

DB_PATH = "/home/ubuntu/trading-intelligence-engine/data/episodes.db"


@dataclass
class DetectorStats:
    name: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    pnl_total: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0


class PostMortemAnalyzer:
    """Analyze trade outcomes and auto-adjust parameters.

    Job:
    - Read last N episodes per detector
    - Calculate win rate, profit factor, avg win/loss
    - Adjust: threshold up if win rate low, budget up if PF high
    """

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
        self._stats: Dict[str, DetectorStats] = {}

    def _conn(self):
        return sqlite3.connect(DB_PATH, timeout=5)

    def analyze(self) -> Dict[str, DetectorStats]:
        """Read episodes, compute stats per detector."""
        conn = self._conn()
        cutoff = datetime.now(timezone.utc).timestamp() - (self.lookback_days * 86400)

        rows = conn.execute(
            """
            SELECT setup_name, outcome, pnl_pts
            FROM episodes
            WHERE ts >= ?
            ORDER BY ts DESC
            """,
            (cutoff,),
        ).fetchall()
        conn.close()

        stats: Dict[str, DetectorStats] = {}
        for setup, outcome, pnl in rows:
            if setup not in stats:
                stats[setup] = DetectorStats(name=setup)
            s = stats[setup]
            s.total_trades += 1
            if outcome == "WIN":
                s.wins += 1
                s.pnl_total += pnl
            elif outcome == "LOSS":
                s.losses += 1
                s.pnl_total -= pnl

        for s in stats.values():
            if s.total_trades > 0:
                s.win_rate = (s.wins / s.total_trades) * 100
            if s.losses > 0:
                gross_win = sum([r[2] for r in rows if r[0] == s.name and r[1] == "WIN"])
                gross_loss = sum([abs(r[2]) for r in rows if r[0] == s.name and r[1] == "LOSS"])
                s.profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 0.0
            if s.wins > 0:
                s.avg_win = s.pnl_total / s.wins

        self._stats = stats
        return stats

    def recommend_adjustments(self) -> Dict[str, dict]:
        """Based on stats, recommend threshold/budget changes."""
        if not self._stats:
            self.analyze()

        recommendations = {}
        for name, s in self._stats.items():
            if s.total_trades < 5:
                continue  # not enough data

            rec = {"detector": name, "action": "hold", "reason": "", "new_threshold": None, "new_budget": None}

            # Threshold logic
            # Win rate < 40% → threshold UP (+5)
            # Win rate > 60% → threshold DOWN (-5)
            if s.win_rate < 40.0:
                rec["action"] = "tighten"
                rec["reason"] = f"win_rate={s.win_rate:.1f}% < 40%"
                rec["new_threshold"] = 60  # raise
            elif s.win_rate > 60.0:
                rec["action"] = "loosen"
                rec["reason"] = f"win_rate={s.win_rate:.1f}% > 60%"
                rec["new_threshold"] = 50  # lower

            # Budget logic
            # PF > 2.0 → budget UP (+5)
            # PF < 1.0 → budget DOWN (-5)
            if s.profit_factor > 2.0:
                rec["new_budget"] = 20  # increase
                rec["reason"] += f", PF={s.profit_factor:.2f} > 2.0"
            elif s.profit_factor < 1.0 and s.profit_factor > 0:
                rec["new_budget"] = 5  # decrease
                rec["reason"] += f", PF={s.profit_factor:.2f} < 1.0"

            if rec["action"] != "hold" or rec["new_threshold"] or rec["new_budget"]:
                recommendations[name] = rec

        return recommendations


class AdaptiveThresholdManager:
    """Store + apply adaptive thresholds per detector."""

    def __init__(self, path: str = "/home/ubuntu/trading-intelligence-engine/data/adaptive_thresholds.json"):
        self.path = path
        self.thresholds: Dict[str, float] = {"default": 55.0}
        self.budgets: Dict[str, int] = {"bystra": 5, "aggressive": 15, "semi_hft": 25}
        self._load()

    def _load(self):
        import json, os
        if os.path.exists(self.path):
            try:
                data = json.load(open(self.path))
                self.thresholds = data.get("thresholds", self.thresholds)
                self.budgets = data.get("budgets", self.budgets)
            except Exception as e:
                log.warning(f"Failed to load adaptive thresholds: {e}")

    def _save(self):
        import json, os
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"thresholds": self.thresholds, "budgets": self.budgets}, f, indent=2)

    def get_threshold(self, detector: str) -> float:
        return self.thresholds.get(detector, self.thresholds["default"])

    def set_threshold(self, detector: str, value: float):
        self.thresholds[detector] = value
        self._save()
        log.info(f"Adaptive: {detector} threshold → {value}")

    def get_budget(self, strategy: str) -> int:
        return self.budgets.get(strategy.lower(), 10)

    def set_budget(self, strategy: str, value: int):
        self.budgets[strategy.lower()] = max(1, value)
        self._save()
        log.info(f"Adaptive: {strategy} budget → {value}")

    def apply_recommendations(self, recommendations: Dict[str, dict]):
        """Apply recommendations from PostMortemAnalyzer."""
        for name, rec in recommendations.items():
            if rec.get("new_threshold"):
                self.set_threshold(name, rec["new_threshold"])
            if rec.get("new_budget"):
                strategy = name.split("_")[0].lower()
                self.set_budget(strategy, rec["new_budget"])
