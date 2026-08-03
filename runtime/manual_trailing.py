"""manual_trailing.py — Trailing manager for manual positions (non-TIE orders).
Polls gateway every 5s, applies money-based trailing to all positions without TIE_ comment.
Torto V4 logic: start_usd=$5, dist_usd=$2.5, step_usd=$1, be_trigger=1R.
"""
import time, logging, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gateway_client import MT5GatewayClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("ManualTrailing")

POLL_SEC = 5
URL   = os.getenv("MT5_GATEWAY_URL", "https://chips-extension-extensions-wearing.trycloudflare.com")
TOKEN = os.getenv("MT5_GATEWAY_TOKEN", "Jojo_56790@_000tUi_OO9")

START_USD = 5.0
DIST_USD  = 2.5
STEP_USD  = 1.0

_peak: dict = {}


def get_manual_positions(client):
    """Return positions where comment does NOT start with TIE_."""
    try:
        positions = client.positions() or []
        return [p for p in positions if not str(p.get("comment", "")).startswith("TIE_")]
    except Exception as e:
        log.error(f"positions fetch fail: {e}")
        return []


def compute_new_sl(pos: dict, peak_profit: float) -> float | None:
    """
    Torto V4 money-based trailing logic.
    Returns new_sl price if SL should move, else None.
    profit = pos['profit'] in account currency (MT5 auto-converts).
    """
    profit    = pos.get("profit", 0.0)
    entry     = pos.get("price_open", 0.0)
    current   = pos.get("price_current", 0.0)
    sl        = pos.get("sl") or 0.0
    is_buy    = str(pos.get("type", "")).lower() in ("buy", "0")

    if profit < START_USD:
        return None  # not enough profit yet

    # Update peak
    if profit > peak_profit:
        return None  # still rising, no trail yet (caller updates peak)

    # profit pulled back from peak — lock floor
    lock_floor = peak_profit - DIST_USD
    if lock_floor <= 0:
        return None

    # Convert lock_floor (USD) to price points
    # price_dist_per_usd = (current - entry) / profit  [approx, same direction]
    if profit == 0:
        return None
    pts_per_usd = abs(current - entry) / abs(profit)
    sl_price_offset = lock_floor * pts_per_usd

    if is_buy:
        new_sl = entry + sl_price_offset
        if new_sl <= sl + STEP_USD * pts_per_usd:
            return None  # not a meaningful improvement
        return round(new_sl, 2)
    else:
        new_sl = entry - sl_price_offset
        if new_sl >= sl - STEP_USD * pts_per_usd:
            return None
        return round(new_sl, 2)


def run():
    client = MT5GatewayClient(URL, TOKEN)
    log.info(f"ManualTrailing started. Gateway: {URL}")

    while True:
        positions = get_manual_positions(client)

        for pos in positions:
            ticket = str(pos.get("ticket"))
            profit = pos.get("profit", 0.0)

            # Update peak profit
            if ticket not in _peak:
                _peak[ticket] = profit
            elif profit > _peak[ticket]:
                _peak[ticket] = profit

            new_sl = compute_new_sl(pos, _peak[ticket])
            if new_sl:
                try:
                    resp = client.modify_order(ticket, stop_loss=new_sl)
                    log.info(f"[{ticket}] Trail SL {pos.get('sl')} -> {new_sl} | profit={profit:.2f}")
                except Exception as e:
                    log.error(f"[{ticket}] modify fail: {e}")

        # Cleanup closed tickets
        active = {str(p.get("ticket")) for p in positions}
        for t in list(_peak.keys()):
            if t not in active:
                del _peak[t]

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    run()
