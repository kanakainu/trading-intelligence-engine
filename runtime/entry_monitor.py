"""EntryMonitor — Background watcher for Bystra Pullback setups.
Monitors live price vs Entry Zone and Danger Zone.
Executes Market Order only after reaction confirmation.
"""
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timezone

from core.decision.trade_decision import TradeDecision, BUY, SELL
from adapters.broker.models import OrderRequest

log = logging.getLogger("EntryMonitor")

class ActiveSetup:
    def __init__(self, decision: TradeDecision, metadata: Dict):
        self.decision = decision
        self.symbol = metadata.get("symbol", "XAUUSD")
        self.direction = decision.action # BUY/SELL
        self.entry_zone = metadata.get("entry_zone") # {'high': f, 'low': f}
        self.danger_zone = metadata.get("danger_zone")
        self.sl = metadata.get("sl")
        self.tp = metadata.get("take_profit")
        self.setup_name = decision.setup_name
        self.created_at = datetime.now(timezone.utc)
        self.status = "PENDING_PULLBACK"

class EntryMonitor:
    def __init__(self, broker, gateway):
        self.broker = broker
        self.gateway = gateway
        self.watchlist: List[ActiveSetup] = []

    def add_setup(self, decision: TradeDecision):
        """Add new setup to monitor. metadata must contain entry_zone."""
        meta = decision.metadata
        if not meta.get("entry_zone"):
            log.warning(f"Setup {decision.setup_name} missing entry_zone. Ignored.")
            return

        setup = ActiveSetup(decision, meta)
        # Avoid duplicate setup on same zone
        for s in self.watchlist:
            if s.setup_name == setup.setup_name and s.direction == setup.direction:
                return

        self.watchlist.append(setup)
        log.info(f"Added {setup.setup_name} {setup.direction} to watchlist. Waiting for pullback...")

    def update(self):
        """Main loop tick: check price vs zones for all setups."""
        if not self.watchlist:
            return

        for setup in self.watchlist[:]:
            try:
                price_data = self.gateway.price(setup.symbol)
                price = price_data['bid'] if setup.direction == "SELL" else price_data['ask']

                # 1. Check Danger Zone
                if setup.direction == "SELL" and setup.danger_zone and price >= setup.danger_zone:
                    log.info(f"Setup {setup.setup_name} INVALID: Price hit Danger Zone {setup.danger_zone}")
                    self.watchlist.remove(setup)
                    continue
                if setup.direction == "BUY" and setup.danger_zone and price <= setup.danger_zone:
                    log.info(f"Setup {setup.setup_name} INVALID: Price hit Danger Zone {setup.danger_zone}")
                    self.watchlist.remove(setup)
                    continue

                # 2. Check Entry Zone
                z = setup.entry_zone
                in_zone = z['low'] <= price <= z['high']

                if setup.status == "PENDING_PULLBACK":
                    if in_zone:
                        setup.status = "IN_ZONE"
                        log.info(f"Setup {setup.setup_name} entered Entry Zone. Monitoring reaction...")

                elif setup.status == "IN_ZONE":
                    # Check Rejection (Simple: price is in zone and last candle on M1 shows wick or flip)
                    # For now: if price is in zone and hasn't broken SL, we look for 'rejection'
                    # Better reaction logic: wait 1 min candle close inside zone
                    is_rejected = self._check_reaction(setup, price)
                    if is_rejected:
                        log.info(f"REACTION CONFIRMED for {setup.setup_name}. Executing Market Order...")
                        self._execute_market(setup, price)
                        self.watchlist.remove(setup)

            except Exception as e:
                log.error(f"Error monitoring {setup.setup_name}: {e}")

    def _check_reaction(self, setup: ActiveSetup, current_price: float) -> bool:
        """Verify price respects the zone (not breaking SL)."""
        # Simplest reaction: Price touched zone and stayed there for 1 tick without breaking SL
        # In Bystra: Wait for rejection wick or engulfing on smaller TF
        # Logic: If price still in zone after being 'IN_ZONE', we trigger.
        # Mas'ku: 'Jika ada reaksi tidak tembus zona entry maka langsung entry market'
        if setup.direction == "SELL":
            return current_price <= setup.entry_zone['high'] # Still below high
        else:
            return current_price >= setup.entry_zone['low'] # Still above low

    def _execute_market(self, setup: ActiveSetup, price: float):
        req = OrderRequest(
            symbol=setup.symbol,
            side=setup.direction,
            volume=0.01,
            order_type="market",
            stop_loss=setup.sl,
            take_profit=setup.tp,
            comment=f"Bystra_{setup.setup_name}"
        )
        res = self.broker.submit_order(req)
        if res.status == "FILLED":
            log.info(f"Order {res.order_id} FILLED for {setup.setup_name}")
        else:
            log.error(f"Order REJECTED for {setup.setup_name}: {res.error}")
