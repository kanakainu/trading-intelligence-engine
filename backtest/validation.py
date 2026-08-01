"""Walk Forward Analysis (WFA) validation gates.

Splits data into IS (in-sample) + OOS (out-of-sample) windows.
Gates: min OOS trades, min WFE (walk forward efficiency).

Usage:
    from backtest.validation import WFAValidator
    result = WFAValidator().validate('XAUUSD', my_strategy_fn)
"""
from __future__ import annotations
import logging
import sys
from dataclasses import dataclass
from typing import Callable

sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from backtest.runner import BacktestRunner
from backtest.risk_xray import RiskXRay

log = logging.getLogger("WFAValidator")

# Gates (ponytail: make configurable via config dict when needed)
MIN_OOS_TRADES   = 10
MIN_WFE          = 0.5   # OOS PF / IS PF >= 0.5
MIN_OOS_SHARPE   = 0.0
IS_RATIO         = 0.7   # 70% in-sample, 30% OOS


@dataclass
class WFAResult:
    passed:        bool
    is_metrics:    dict
    oos_metrics:   dict
    wfe:           float   # walk forward efficiency = OOS PF / IS PF
    reason:        str


def validate(
    symbol: str,
    strategy_fn: Callable,
    timeframe: str = "M5",
    total_bars: int = 500,
    initial_equity: float = 10_000.0,
) -> WFAResult:
    """Run IS + OOS split, check WFA gates.

    Returns WFAResult with passed=True if all gates clear.
    """
    runner  = BacktestRunner()
    xray    = RiskXRay()

    # Load full dataset once
    from backtest.pipeline import load
    df_full = load(symbol, timeframe, total_bars)

    split    = int(len(df_full) * IS_RATIO)
    df_is    = df_full.iloc[:split].reset_index(drop=True)
    df_oos   = df_full.iloc[split:].reset_index(drop=True)

    # Run IS
    result_is  = runner.run_on_df(symbol, strategy_fn, df_is,  initial_equity)
    # Run OOS
    result_oos = runner.run_on_df(symbol, strategy_fn, df_oos, initial_equity)

    m_is  = xray.analyze(result_is)
    m_oos = xray.analyze(result_oos)

    is_pf  = m_is.get("profit_factor",  0.0) or 0.0
    oos_pf = m_oos.get("profit_factor", 0.0) or 0.0
    wfe    = (oos_pf / is_pf) if is_pf > 0 else 0.0

    failures = []
    if m_oos.get("total_trades", 0) < MIN_OOS_TRADES:
        failures.append(f"OOS trades {m_oos['total_trades']} < {MIN_OOS_TRADES}")
    if wfe < MIN_WFE:
        failures.append(f"WFE {wfe:.2f} < {MIN_WFE}")
    if m_oos.get("sharpe_ratio", 0.0) < MIN_OOS_SHARPE:
        failures.append(f"OOS Sharpe {m_oos['sharpe_ratio']:.2f} < {MIN_OOS_SHARPE}")

    passed = len(failures) == 0
    reason = "PASS" if passed else " | ".join(failures)

    log.info("WFA %s %s/%s: WFE=%.2f OOS_trades=%d %s",
             symbol, timeframe, total_bars, wfe,
             m_oos.get("total_trades", 0), reason)

    return WFAResult(
        passed=passed,
        is_metrics=m_is,
        oos_metrics=m_oos,
        wfe=wfe,
        reason=reason,
    )


# Allow runner.run_on_df — patch BacktestRunner to accept pre-loaded df
# ponytail: move run_on_df into runner.py properly when P3 integrates with governance
def _patch_runner():
    """Add run_on_df to BacktestRunner if not present."""
    from backtest.runner import BacktestRunner as R
    if hasattr(R, "run_on_df"):
        return

    import pandas as pd
    from backtest.runner import BacktestResult
    from backtest.engines.cfd import CFDEngine
    from backtest.engines.crypto import CryptoEngine

    def run_on_df(self, symbol, strategy_fn, df, initial_equity=10_000.0):
        engine_cls = CryptoEngine if symbol.upper() == "BTCUSD" else CFDEngine
        engine = engine_cls(symbol)
        signals = []
        for i in range(len(df) - 1):
            sig = strategy_fn(df, i)
            if sig:
                signals.append({**sig, "bar_index": i})
        result_raw = engine.run(df, signals, initial_equity=initial_equity)
        return BacktestResult(
            symbol=symbol, timeframe="N/A", count=len(df),
            trades=result_raw["trades"],
            equity_curve=result_raw["equity_curve"],
            final_equity=result_raw["final_equity"],
        )

    R.run_on_df = run_on_df

_patch_runner()
