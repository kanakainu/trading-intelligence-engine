import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from backtest.pipeline import load
from backtest.engines.cfd import CFDEngine
from backtest.engines.crypto import CryptoEngine

@dataclass
class BacktestResult:
    trades: List[dict]
    equity_curve: List[float]
    final_equity: float
    symbol: str
    timeframe: str
    count: int

class BacktestRunner:
    def run(self, symbol, strategy_fn, timeframe='M5', count=500, initial_equity=10000.0):
        df = load(symbol, timeframe, count)
        
        # ATR for dynamic spread
        if 'atr' not in df.columns:
            high_low = df['high'] - df['low']
            high_cp = (df['high'] - df['close'].shift()).abs()
            low_cp = (df['low'] - df['close'].shift()).abs()
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            df['atr'] = tr.rolling(14).mean().fillna(0)

        engine = CryptoEngine(symbol) if 'BTC' in symbol else CFDEngine(symbol)
        
        signals = []
        for i in range(len(df)):
            sig = strategy_fn(df, i)
            if sig:
                sig['bar_index'] = i
                signals.append(sig)
        
        res = engine.run(df, signals, initial_equity)
        return BacktestResult(
            trades=res['trades'],
            equity_curve=res['equity_curve'],
            final_equity=res['final_equity'],
            symbol=symbol,
            timeframe=timeframe,
            count=count
        )
