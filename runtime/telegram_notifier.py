"""Telegram Notifier — push alerts ONLY for critical events to Trading Room group."""
import logging
log = logging.getLogger(__name__)

TRADING_ROOM_CHAT_ID = "-1004418586484"  # Trading Room group ONLY

class TelegramNotifier:
    def __init__(self, chat_id: str = TRADING_ROOM_CHAT_ID):
        self.chat_id = chat_id
    
    def notify_setup_detected(self, setup_name: str, action: str, confidence: float, price: float):
        """Log only — no spam."""
        log.info(f"[TIE] Setup detected: {setup_name} {action} conf={confidence:.0%} price={price:.2f}")
    
    def notify_order_filled(self, order_id: str, symbol: str, side: str, volume: float, price: float):
        msg = f"✅ <b>ORDER FILLED #{order_id}</b>\n{symbol} {side} {volume} lot @ {price:.2f}"
        self._send(msg)
    
    def notify_sl_hit(self, position_id: str, pnl: float):
        sign = "" if pnl < 0 else "+"
        msg = f"🛑 <b>SL HIT #{position_id}</b>\nP&L: ${sign}{pnl:.2f}"
        self._send(msg)
    
    def notify_tp_hit(self, position_id: str, pnl: float):
        sign = "" if pnl < 0 else "+"
        msg = f"🎯 <b>TP HIT #{position_id}</b>\nP&L: ${sign}{pnl:.2f}"
        self._send(msg)
    
    def notify_entry_zone(self, setup_name: str, symbol: str, price: float):
        """Log only — no spam."""
        log.info(f"[TIE] Entry zone: {setup_name} {symbol} price={price:.2f}")
    
    def notify_danger_zone(self, setup_name: str, symbol: str, reason: str):
        """Log only — no spam."""
        log.warning(f"[TIE] Danger zone: {setup_name} {symbol} {reason}")
    
    def notify_risk_gate_blocked(self, symbol: str, setup_name: str, reasons: str):
        """Log only — no spam."""
        log.info(f"[TIE] Risk gate blocked: {setup_name} {symbol} {reasons}")
    
    def _send(self, message: str):
        try:
            import sys
            import requests
            sys.path.insert(0, "/home/ubuntu/trading-intelligence-engine")
            from config.live import TELEGRAM_CHAT_ID as cfg_chat
            
            # Use main Hermes bot token (loaded from config or fallback)
            import os
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            if not token:
                import yaml
                with open("/home/ubuntu/.hermes/config.yaml") as f:
                    cfg = yaml.safe_load(f)
                token = cfg.get("platforms", {}).get("telegram", {}).get("token", "")
            
            if not token:
                return False
                
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            
            payload = {
                "chat_id": TRADING_ROOM_CHAT_ID,  # Always Trading Room group
                "text": message,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Telegram send failed: {e}")
            return False