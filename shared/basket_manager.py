"""Basket Manager — Goldman Sachs inspired basket trade management.

Logic:
- Accumulate profit for all BUY or SELL positions.
- If positions >= 3 and Total Profit >= threshold ($3.0) -> Close all on that side.
"""
import logging
import json
import os

log = logging.getLogger("basket_manager")
_FEATURES_PATH = "/home/ubuntu/trading-intelligence-engine/config/features.json"

def process_baskets(broker, positions):
    """
    Check and close profit baskets.
    """
    try:
        if not os.path.exists(_FEATURES_PATH):
            return
            
        with open(_FEATURES_PATH) as f:
            cfg = json.load(f)
            
        if not cfg.get("basket_tp", True):
            return

        threshold = cfg.get("basket_tp_threshold", 3.0)  # Min profit to close the basket
        min_pos = cfg.get("basket_tp_min_pos", 3)      # Min positions to trigger basket TP

        buys = [p for p in positions if getattr(p, "direction", getattr(p, "side", "")).upper() == "BUY"]
        sells = [p for p in positions if getattr(p, "direction", getattr(p, "side", "")).upper() == "SELL"]

        # Process BUYs
        if len(buys) >= min_pos:
            total_buy_profit = sum(getattr(p, "unrealized_profit", 0.0) for p in buys)
            if total_buy_profit >= threshold:
                log.info(f"🧺 BASKET TP (BUY): Profit ${total_buy_profit:.2f} reached. Closing {len(buys)} positions.")
                for p in buys:
                    broker.close_position(str(p.position_id))

        # Process SELLs
        if len(sells) >= min_pos:
            total_sell_profit = sum(getattr(p, "unrealized_profit", 0.0) for p in sells)
            if total_sell_profit >= threshold:
                log.info(f"🧺 BASKET TP (SELL): Profit ${total_sell_profit:.2f} reached. Closing {len(sells)} positions.")
                for p in sells:
                    broker.close_position(str(p.position_id))
                    
    except Exception as e:
        log.error(f"Basket processing error: {e}")
