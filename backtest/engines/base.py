import pandas as pd
import numpy as np
from abc import ABC, abstractmethod

class BaseEngine(ABC):
    def __init__(self, symbol, config):
        self.symbol = symbol
        self.config = config
        self.trades = []
        self.equity_curve = []
        self.equity = 0.0

    def run(self, df, signals, initial_equity=10000.0):
        self.equity = initial_equity
        self.equity_curve = [self.equity]
        open_trade = None
        
        # signals is list of {bar_index, direction, sl, tp, volume}
        sig_map = {s['bar_index']: s for s in signals}

        for i in range(len(df)):
            row = df.iloc[i]
            curr_time = row['time']
            
            # Check exit if trade open
            if open_trade:
                self._apply_swap(open_trade, curr_time)
                self._update_trade_logic(open_trade, row) # Hook for funding etc
                
                # SL/TP check
                price_high = row['high']
                price_low = row['low']
                exit_price = None
                reason = None
                
                if open_trade['direction'] == 'buy':
                    if price_low <= open_trade['sl']:
                        exit_price = open_trade['sl']
                        reason = 'sl'
                    elif price_high >= open_trade['tp']:
                        exit_price = open_trade['tp']
                        reason = 'tp'
                else: # sell
                    if price_high >= open_trade['sl']:
                        exit_price = open_trade['sl']
                        reason = 'sl'
                    elif price_low <= open_trade['tp']:
                        exit_price = open_trade['tp']
                        reason = 'tp'
                
                if exit_price:
                    pnl = self._calc_pnl(open_trade, exit_price)
                    self.equity += pnl
                    open_trade.update({'exit_price': exit_price, 'exit_time': curr_time, 'pnl': pnl, 'reason': reason})
                    self.trades.append(open_trade)
                    open_trade = None

            # T+1 execution logic
            # If signal at T-1, execute at T open
            prev_idx = i - 1
            if not open_trade and prev_idx in sig_map and self._is_market_open(curr_time):
                sig = sig_map[prev_idx]
                entry_price = self._apply_spread(row['open'], sig['direction'], row.get('atr', 0))
                open_trade = {
                    'direction': sig['direction'],
                    'entry_price': entry_price,
                    'entry_time': curr_time,
                    'sl': sig['sl'],
                    'tp': sig['tp'],
                    'volume': sig['volume'],
                    'swap': 0.0,
                    'funding': 0.0
                }
            
            self.equity_curve.append(self.equity)

        return {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'final_equity': self.equity
        }

    def _apply_spread(self, price, direction, atr=0):
        spread = self.config.get('spread_pts', 0)
        if hasattr(self, '_calc_dynamic_spread'):
            spread = self._calc_dynamic_spread(atr)
        return price + spread if direction == 'buy' else price - spread

    def _apply_swap(self, trade, current_bar):
        # swap per night logic
        # current_bar and prev_bar check for midnight cross
        # ponytail: simplified daily check
        if hasattr(current_bar, 'hour') and current_bar.hour == 0 and current_bar.minute == 0:
            trade['swap'] += self.config.get('swap_per_lot_per_night', 0) * trade['volume']

    def _is_market_open(self, bar_time):
        hours = self.config.get('market_hours', [(0, 24)])
        # simplified check
        h = bar_time.hour
        for start, end in hours:
            if start <= h < end:
                return True
        return False

    def _calc_pnl(self, trade, exit_price):
        diff = (exit_price - trade['entry_price']) if trade['direction'] == 'buy' else (trade['entry_price'] - exit_price)
        # diff in price * contract_size * volume * pip_value
        # but usually pip_value is built into contract_size/volume logic
        # per prompt: pnl = diff * contract_size * volume
        return diff * self._contract_size(trade['volume']) + trade['swap'] + trade.get('funding', 0)

    def _update_trade_logic(self, trade, row):
        pass

    @abstractmethod
    def _contract_size(self, volume):
        pass
