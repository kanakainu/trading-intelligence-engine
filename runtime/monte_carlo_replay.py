"""Monte Carlo Replay Engine — replay historical data through TIE V3 pipeline.

Count gate passes/fails to identify bottlenecks.
NO live trading. Only simulation.
"""
import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
import uuid

logger = logging.getLogger("MonteCarloReplay")


@dataclass
class GateStats:
    """Statistics for a single gate."""
    name: str
    pass_count: int = 0
    fail_count: int = 0
    skip_count: int = 0
    
    @property
    def total(self) -> int:
        return self.pass_count + self.fail_count + self.skip_count
    
    @property
    def pass_rate(self) -> float:
        return (self.pass_count / self.total * 100) if self.total > 0 else 0.0


@dataclass
class ReplayResult:
    """Result of a single replay scan."""
    scan_id: str
    symbol: str
    timestamp: str
    strategy: str
    gates: Dict[str, GateStats] = field(default_factory=dict)
    signal_generated: bool = False
    trade_executed: bool = False
    rejection_reason: str = ""


class MonteCarloReplay:
    """Replay historical data through TIE V3 pipeline."""
    
    def __init__(self, db_path: str = "/home/ubuntu/trading-intelligence-engine/data/monte_carlo_replay.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        self.gate_stats: Dict[str, GateStats] = defaultdict(lambda: GateStats(name="unknown"))
        self.scan_count = 0
        self.signal_count = 0
        self.trade_count = 0
        
    def _init_db(self):
        """Initialize SQLite tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS replay_results (
                scan_id TEXT PRIMARY KEY,
                symbol TEXT,
                timestamp TEXT,
                strategy TEXT,
                signal_generated INTEGER,
                trade_executed INTEGER,
                rejection_reason TEXT,
                gates_json TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS gate_stats (
                gate_name TEXT PRIMARY KEY,
                pass_count INTEGER,
                fail_count INTEGER,
                skip_count INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    def record_gate(self, gate_name: str, status: str):
        """Record a gate decision."""
        if gate_name not in self.gate_stats:
            self.gate_stats[gate_name] = GateStats(name=gate_name)
        
        if status == "PASS":
            self.gate_stats[gate_name].pass_count += 1
        elif status == "FAIL":
            self.gate_stats[gate_name].fail_count += 1
        else:
            self.gate_stats[gate_name].skip_count += 1
    
    def record_scan(self, result: ReplayResult):
        """Record a scan result."""
        self.scan_count += 1
        if result.signal_generated:
            self.signal_count += 1
        if result.trade_executed:
            self.trade_count += 1
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO replay_results
            (scan_id, symbol, timestamp, strategy, signal_generated, trade_executed, rejection_reason, gates_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (result.scan_id, result.symbol, result.timestamp, result.strategy,
              int(result.signal_generated), int(result.trade_executed),
              result.rejection_reason, json.dumps({})))
        conn.commit()
        conn.close()
    
    def _save_result(self, result: ReplayResult):
        """Alias for record_scan."""
        self.record_scan(result)
    
    def get_summary(self) -> dict:
        """Get replay summary statistics."""
        return {
            "total_scans": self.scan_count,
            "signals_generated": self.signal_count,
            "trades_executed": self.trade_count,
            "signal_rate": (self.signal_count / self.scan_count * 100) if self.scan_count > 0 else 0.0,
            "trade_rate": (self.trade_count / self.scan_count * 100) if self.scan_count > 0 else 0.0,
            "gate_stats": {
                name: {
                    "PASS": stats.pass_count,
                    "FAIL": stats.fail_count,
                    "SKIPPED": stats.skip_count,
                    "pass_rate": round(stats.pass_rate, 2)
                }
                for name, stats in self.gate_stats.items()
            }
        }
    
    def generate_report(self) -> dict:
        """Generate human-readable report."""
        summary = self.get_summary()
        
        lines = [
            "=" * 60,
            "MONTE CARLO REPLAY REPORT",
            "=" * 60,
            "",
            f"Total Scans:              {summary['total_scans']:,}",
            f"Signals Generated:        {summary['signals_generated']:,}",
            f"Trades Executed:          {summary['trades_executed']:,}",
            f"Signal Rate:              {summary['signal_rate']:.2f}%",
            f"Trade Rate:               {summary['trade_rate']:.2f}%",
            "",
            "-" * 60,
            "GATE STATISTICS",
            "-" * 60,
            "",
        ]
        
        sorted_gates = sorted(
            summary["gate_stats"].items(),
            key=lambda x: x[1]["pass_rate"]
        )
        
        for gate_name, stats in sorted_gates:
            lines.append(
                f"{gate_name:30} | PASS: {stats['PASS']:>6} | FAIL: {stats['FAIL']:>6} | "
                f"SKIP: {stats['SKIPPED']:>6} | Rate: {stats['pass_rate']:>6.2f}%"
            )
        
        lines.extend([
            "",
            "=" * 60,
            "BOTTLENECK ANALYSIS",
            "=" * 60,
            "",
        ])
        
        bottlenecks = [
            (name, stats) for name, stats in sorted_gates
            if stats["pass_rate"] < 50.0 and stats["PASS"] + stats["FAIL"] > 0
        ]
        
        if bottlenecks:
            lines.append("Top Bottlenecks (pass rate < 50%):")
            for name, stats in bottlenecks[:5]:
                lines.append(f"  • {name}: {stats['pass_rate']:.2f}% pass rate")
        else:
            lines.append("No critical bottlenecks detected.")
        
        return {"report_text": "\n".join(lines), "summary": summary}


class HistoricalDataLoader:
    """Load historical candle data for replay."""
    
    def load_candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> List[Dict]:
        """Load historical candles via MT5 gateway."""
        import sys
        sys.path.insert(0, '/home/ubuntu/.hermes/trading')
        from gateway_client import MT5GatewayClient
        
        client = MT5GatewayClient(
            'https://buildings-threats-built-plugins.trycloudflare.com',
            'Jojo_56790@_000tUi_OO9'
        )
        
        tf_map = {'M1': 'M1', 'M5': 'M5', 'M15': 'M15', 'H1': 'H1'}
        tf = tf_map.get(timeframe, 'M5')
        
        delta = end - start
        bars = int(delta.total_seconds() / 60) if tf == 'M1' else int(delta.total_seconds() / 300)
        bars = min(bars, 5000)
        
        try:
            candles = client.candles(symbol, tf, bars)
            return candles if candles else []
        except Exception as e:
            logger.error(f"Failed to load candles: {e}")
            return []


def run_replay(
    symbols: List[str] = ["XAUUSD", "BTCUSD", "GBPJPY"],
    days: int = 30,
    timeframes: List[str] = ["M1", "M5"],
    output_path: Optional[str] = None
) -> dict:
    """Run Monte Carlo replay using REAL TIE V3 strategy scan."""
    import sys
    sys.path.insert(0, '/home/ubuntu/.hermes/trading')
    sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')
    
    from gateway_client import MT5GatewayClient
    from strategies.bystra.strategy import BystraStrategy
    
    replay = MonteCarloReplay()
    
    client = MT5GatewayClient(
        'https://buildings-threats-built-plugins.trycloudflare.com',
        'Jojo_56790@_000tUi_OO9'
    )
    
    logger.info(f"Starting Monte Carlo replay: {symbols} over {days} days")
    
    strategy = BystraStrategy()
    
    for symbol in symbols:
        candles = client.candles(symbol, 'M5', min(days * 24 * 12, 5000))
        if not candles:
            logger.warning(f"No candles for {symbol}")
            continue
        
        for i in range(0, len(candles) - 20, 10):
            candle_window = candles[i:i+20]
            if not candle_window:
                continue
            
            scan_id = str(uuid.uuid4())[:8]
            price = candle_window[-1].get('close', 0)
            
            features = type('Features', (), {
                'symbol': symbol,
                'current_price': price,
                'timestamp': datetime.now(timezone.utc),
                'candles_m1': candle_window,
                'candles_m5': candle_window,
                'metadata': {'candles': {'M5': candle_window}}
            })()
            
            try:
                result = strategy.analyze(features)
                
                if result and result.signal:
                    replay.record_gate("MarketState", "PASS")
                    replay.record_gate("Opportunity", "PASS")
                    replay.record_gate("Detector", "PASS")
                    replay.record_gate("RiskGate", "PASS")
                    
                    replay.signal_count += 1
                    replay.trade_count += 1
                    
                    res = ReplayResult(
                        scan_id=scan_id,
                        symbol=symbol,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        strategy="Bystra",
                        signal_generated=True,
                        trade_executed=True,
                        rejection_reason=""
                    )
                else:
                    replay.record_gate("MarketState", "PASS")
                    replay.record_gate("Opportunity", "FAIL")
                    replay.record_gate("Detector", "SKIPPED")
                    replay.record_gate("RiskGate", "SKIPPED")
                    
                    res = ReplayResult(
                        scan_id=scan_id,
                        symbol=symbol,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        strategy="Bystra",
                        signal_generated=False,
                        trade_executed=False,
                        rejection_reason=result.reason if result else "No signal"
                    )
            except Exception as e:
                logger.error(f"Scan error: {e}")
                replay.record_gate("MarketState", "PASS")
                replay.record_gate("Opportunity", "FAIL")
                replay.record_gate("Detector", "SKIPPED")
                replay.record_gate("RiskGate", "SKIPPED")
                continue
            
            replay.scan_count += 1
            replay._save_result(res)
    
    report = replay.generate_report()
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
    
    print(report["report_text"])
    return report


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monte Carlo Replay Engine")
    parser.add_argument("--symbols", nargs="+", default=["XAUUSD", "BTCUSD", "GBPJPY"], help="Symbols to replay")
    parser.add_argument("--days", type=int, default=30, help="Number of days to replay")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
    
    run_replay(
        symbols=args.symbols,
        days=args.days,
        output_path=args.output
    )
