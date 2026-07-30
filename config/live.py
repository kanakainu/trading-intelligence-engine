"""TIE live config — MT5 demo (Exness). DO NOT commit credentials."""
import os

GATEWAY_URL   = os.getenv("MT5_GATEWAY_URL",   "https://chips-extension-extensions-wearing.trycloudflare.com")
GATEWAY_TOKEN = os.getenv("MT5_GATEWAY_TOKEN", "Jojo_56790@_000tUi_OO9")
SYMBOLS       = ["XAUUSD"]
DEFAULT_LOT   = 0.01
CANONICAL_ID  = "boskuh"
