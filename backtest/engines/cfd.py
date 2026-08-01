from .base import BaseEngine

class CFDEngine(BaseEngine):
    SYMBOLS = {
        'XAUUSD': {'spread_pts': 0.5, 'swap_per_lot_per_night': -0.35, 'pip_value': 1.0, 'contract_size': 100, 'market_hours': [(0, 23)]},
        'GBPJPY': {'spread_pts': 0.003, 'swap_per_lot_per_night': -0.20, 'pip_value': 0.07, 'contract_size': 100000, 'market_hours': [(0, 23)]}
    }

    def __init__(self, symbol):
        config = self.SYMBOLS.get(symbol, self.SYMBOLS['XAUUSD'])
        super().__init__(symbol, config)

    def _calc_dynamic_spread(self, atr):
        base = self.config['spread_pts']
        return max(base, atr * 0.02)

    def _contract_size(self, volume):
        return volume * self.config['contract_size']

    def _is_market_open(self, bar_time):
        # Weekday check
        if bar_time.weekday() >= 5: return False
        return super()._is_market_open(bar_time)
