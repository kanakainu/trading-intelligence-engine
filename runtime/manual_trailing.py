"""manual_trailing.py — Trailing manager for manual positions (non-TIE orders).
Polls gateway every 5s, applies money-based trailing to all positions without TIE_ comment.
Torto V4 logic: start_usd=$5, dist_usd=$2.5, step_usd=$1.
Auto SL/TP: uses Bystra swing pivot logic (H1 candles) for positions with sl==0.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import time, logging, requests
from detectors.common import find_nearest_support, find_nearest_resistance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("ManualTrailing")

POLL_SEC   = 5
URL        = os.getenv("MT5_GATEWAY_URL",   "https://statute-expired-chapter-subscribers.trycloudflare.com")
TOKEN      = os.getenv("MT5_GATEWAY_TOKEN", "Xs-EjloGUf_WxDlpLHEkRNbbVcsmtRlV")
HEADERS    = {"Authorization": f"Bearer {TOKEN}"}

START_USD  = 5.0
DIST_USD   = 2.5
STEP_USD   = 1.0
RR_RATIO   = 1.5   # TP = SL_dist * 1.5

_peak: dict = {}


def get_manual_positions():
    """Return positions where comment does NOT start with TIE_."""
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        r = requests.get(f"{URL}/account/positions", headers=headers, timeout=5)
        r.raise_for_status()
        positions = r.json() or []
        return [p for p in positions if not str(p.get("comment", "")).startswith("TIE_")]
    except Exception as e:
        log.error(f"positions fetch fail: {e}")
        return []


def compute_new_sl(pos: dict, peak_profit: float) -> float | None:
    """
    Torto V4 money-based trailing logic.
    Phase 1: profit >= START_USD → lock SL to break-even (entry price).
    Phase 2: profit pulled back DIST_USD from peak → trail SL to lock floor.
    """
    profit    = pos.get("profit", 0.0)
    entry     = pos.get("open_price", 0.0)
    current   = pos.get("current_price", 0.0)
    sl        = pos.get("sl") or 0.0
    direction = str(pos.get("direction", "")).lower()
    is_buy    = direction == "buy"

    if profit < START_USD:
        return None

    if current == entry or profit == 0:
        return None

    pts_per_usd = abs(current - entry) / abs(profit)

    # Phase 1: Profit lock — move SL to Entry + $1.5 if profit >= $5
    # Move SL to Entry + $1.5 (or Entry - $1.5 for SELL)
    be_lock_offset = 1.5
    be_sl = entry + (be_lock_offset if is_buy else -be_lock_offset)
    
    if sl == 0.0 or (is_buy and sl < be_sl) or (not is_buy and sl > be_sl):
        return round(be_sl, 2)

    # Phase 2: Dynamic trail based on peak profit pullback
    if profit >= peak_profit:
        return None  # still rising, no trail move yet

    lock_floor = peak_profit - DIST_USD
    # ... (rest of trail logic)
    if lock_floor <= 0:
        return None

    sl_price_offset = lock_floor * pts_per_usd

    if is_buy:
        new_sl = entry + sl_price_offset
        if new_sl <= sl + STEP_USD * pts_per_usd:
            return None
        return round(new_sl, 2)
    else:
        new_sl = entry - sl_price_offset
        if new_sl >= sl - STEP_USD * pts_per_usd:
            return None
        return round(new_sl, 2)


def get_candles(symbol: str, tf: str = "H1", count: int = 100):
    """Fetch H1 candles from gateway for Bystra swing pivot analysis."""
    try:
        r = requests.get(
            f"{URL}/trade/candles/{symbol}",
            params={"tf": tf, "count": count},
            headers=HEADERS,
            timeout=10
        )
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        log.error(f"candles fetch fail: {e}")
        return []


def auto_sltp(pos: dict):
    """
    Auto-set SL/TP for manual positions with sl==0.
    Uses Bystra swing pivot logic (H1 candles):
    - SELL → SL = nearest swing high above entry
    - BUY → SL = nearest swing low below entry
    - TP = entry ± (SL_dist × RR_RATIO)
    """
    sl = pos.get("sl") or 0.0
    if sl != 0.0:
        return  # already has SL

    symbol    = pos.get("symbol", "")
    entry     = pos.get("open_price", 0.0)
    direction = str(pos.get("direction", "")).lower()
    is_buy    = direction == "buy"
    ticket    = str(pos.get("ticket"))

    # Fetch H1 candles
    candles = get_candles(symbol, tf="H1", count=100)
    if not candles:
        log.warning(f"[{ticket}] No H1 candles for {symbol}, skip auto SL/TP")
        return

    # Find swing pivot SL
    if is_buy:
        sl_price = find_nearest_support(candles, entry)
    else:
        sl_price = find_nearest_resistance(candles, entry)

    if sl_price == 0.0 or sl_price == entry:
        log.warning(f"[{ticket}] No valid swing pivot found, skip auto SL/TP")
        return

    # Calculate TP (RR_RATIO = 1.5)
    sl_dist = abs(entry - sl_price)
    if is_buy:
        tp_price = entry + (sl_dist * RR_RATIO)
    else:
        tp_price = entry - (sl_dist * RR_RATIO)

    # Apply via gateway
    try:
        modify_order(ticket, sl_price, tp_price)
        log.info(f"[{ticket}] Auto SL/TP set: SL={sl_price:.2f}, TP={tp_price:.2f} (RR={RR_RATIO})")
    except Exception as e:
        log.error(f"[{ticket}] auto SL/TP fail: {e}")


def modify_order(ticket: str, stop_loss: float, take_profit: float = 0.0):
    """Modify SL via gateway REST API."""
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        r = requests.post(
            f"{URL}/trade/modify",
            json={"ticket": int(ticket), "sl": stop_loss, "tp": take_profit},
            headers=headers,
            timeout=5
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise Exception(f"modify fail: {e}")


def run():
    log.info(f"ManualTrailing started. Gateway: {URL}")

    while True:
        positions = get_manual_positions()
        positions = get_manual_positions()
        for pos in positions:
            ticket = str(pos.get("ticket"))
            profit = pos.get("profit", 0.0)

            # Auto SL/TP for positions without SL
            auto_sltp(pos)

            if ticket not in _peak:
                _peak[ticket] = profit
            elif profit > _peak[ticket]:
                _peak[ticket] = profit

            new_sl = compute_new_sl(pos, _peak[ticket])
            if new_sl:
                try:
                    modify_order(ticket, new_sl)
                    log.info(f"[{ticket}] Trail SL {pos.get('sl')} -> {new_sl} | profit={profit:.2f}")
                except Exception as e:
                    log.error(f"[{ticket}] modify fail: {e}")

        active = {str(p.get("ticket")) for p in positions}
        for t in list(_peak.keys()):
            if t not in active:
                del _peak[t]

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    run()
