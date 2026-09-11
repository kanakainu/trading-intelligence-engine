"""TIE live config — MT5 demo (Exness). DO NOT commit credentials."""
import os

GATEWAY_URL   = os.getenv("MT5_GATEWAY_URL",   "https://legends-api-disable-morrison.trycloudflare.com")
GATEWAY_TOKEN = os.getenv("MT5_GATEWAY_TOKEN", "Xs-EjloGUf_WxDlpLHEkRNbbVcsmtRlV")
SYMBOLS       = ["XAUUSD"]
TELEGRAM_CHAT_ID = "1987405029"
DEFAULT_LOT   = 0.01
CANONICAL_ID  = "boskuh"
