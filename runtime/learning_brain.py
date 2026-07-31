"""
Learning Brain — Post-trade analytics and pattern discovery.
Reads closed trades from MT5 via BrokerAdapter and stores insights in HCK.
"""
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

log = logging.getLogger("LearningBrain")

class LearningBrain:
    def __init__(self, broker, hck_log_path: str = "/home/ubuntu/trading-intelligence-engine/logs/learning_insights.json"):
        self.broker = broker
        self.hck_log_path = hck_log_path

    def run_daily_analysis(self):
        """Fetch today's closed trades and generate insights."""
        log.info("Starting daily post-trade analysis...")
        
        # 1. Fetch closed trades (last 24h)
        trades = self.broker.get_closed_trades(days=1)
        if not trades:
            log.info("No closed trades found for today.")
            return

        # 2. Basic Metrics
        stats = self._calculate_stats(trades)
        
        # 3. Pattern Analysis (per setup)
        patterns = self._analyze_patterns(trades)
        
        # 4. Insight Generation
        insight = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "total_trades": len(trades),
            "win_rate": stats['win_rate'],
            "profit_factor": stats['profit_factor'],
            "avg_rr": stats['avg_rr'],
            "net_pnl": stats['net_pnl'],
            "best_setup": patterns.get("best_setup"),
            "worst_setup": patterns.get("worst_setup"),
            "session_performance": patterns.get("sessions"),
            "raw_stats": stats
        }

        # 5. Store to HCK / Local Log
        self._save_insight(insight)
        log.info(f"Analysis complete. Winrate: {stats['win_rate']:.1%}, Net PnL: ${stats['net_pnl']:.2f}")
        return insight

    def _calculate_stats(self, trades: List[Dict]) -> Dict:
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in trades)
        gross_profit = sum(t['pnl'] for t in wins)
        gross_loss = abs(sum(t['pnl'] for t in losses))
        
        win_rate = len(wins) / len(trades) if trades else 0
        pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1)
        
        return {
            "win_rate": win_rate,
            "profit_factor": pf,
            "net_pnl": total_pnl,
            "avg_rr": self._calc_avg_rr(trades)
        }

    def _analyze_patterns(self, trades: List[Dict]) -> Dict:
        setup_stats = {}
        for t in trades:
            name = t.get('comment', 'unknown').replace('Riri_', '')
            if name not in setup_stats:
                setup_stats[name] = {"wins": 0, "total": 0, "pnl": 0}
            
            setup_stats[name]["total"] += 1
            setup_stats[name]["pnl"] += t['pnl']
            if t['pnl'] > 0:
                setup_stats[name]["wins"] += 1
        
        if not setup_stats:
            return {}

        best = max(setup_stats.items(), key=lambda x: x[1]['pnl'])[0]
        worst = min(setup_stats.items(), key=lambda x: x[1]['pnl'])[0]
        
        return {
            "best_setup": best,
            "worst_setup": worst,
            "setups": setup_stats
        }

    def _calc_avg_rr(self, trades: List[Dict]) -> float:
        # Placeholder: ideally compare realized pnl to initial risk
        return 1.5 

    def _save_insight(self, insight: Dict):
        with open(self.hck_log_path, "a") as f:
            f.write(json.dumps(insight) + "\n")
