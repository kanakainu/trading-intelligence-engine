from .base import BaseEngine

class CryptoEngine(BaseEngine):
    SYMBOLS = {
        'BTCUSD': {'spread_pts': 50.0, 'funding_rate': 0.0001, 'contract_size': 1, 'market_hours': [(0, 24)]}
    }

    def __init__(self, symbol):
        config = self.SYMBOLS.get(symbol, self.SYMBOLS['BTCUSD'])
        super().__init__(symbol, config)

    def _update_trade_logic(self, trade, row):
        self._apply_funding(trade, row['time'])

    def _apply_funding(self, trade, current_bar):
        # Funding every 8h: 0, 8, 16
        if current_bar.hour in [0, 8, 16] and current_bar.minute == 0:
            rate = self.config['funding_rate']
            # trade['funding'] -= trade_value * rate
            # ponytail: simplified funding calculation
            trade['funding'] -= (trade['entry_price'] * trade['volume'] * rate)

    def _contract_size(self, volume):
        return volume * self.config['contract_size']
