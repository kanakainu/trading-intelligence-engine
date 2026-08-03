"""manual_trailing.py — Trailing manager for manual positions (non-TIE orders).
Polls gateway every 5s, applies money-based trailing to all positions without TIE_ comment.
Torto V4 logic: start_usd=$5, dist_usd=$2.5, step_usd=$1.
"""
import time, logging, os, requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("ManualTrailing")

POLL_SEC = 5
URL   = os.getenv("MT5_GATEWAY_URL", "https://chips-extension-extensions-wearing.trycloudflare.com")
TOKEN = os.getenv("MT5_GATEWAY_TOKEN", "Jojo_56790@_000tUi_OO9")

START_USD = 5.0
DIST_USD  = 2.5
STEP_USD  = 1.0

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
    Returns new_sl price if SL should move, else None.
    profit = pos['profit'] in account currency (MT5 auto-converts).
    """
    profit    = pos.get("profit", 0.0)
    entry     = pos.get("open_price", 0.0)
    current   = pos.get("current_price", 0.0)
    sl        = pos.get("sl") or 0.0
    direction = str(pos.get("direction", "")).lower()
    is_buy    = direction == "buy"

    if profit < START_USD:
        return None

    if profit > peak_profit:
        return None

    lock_floor = peak_profit - DIST_USD
    if lock_floor <= 0:
        return None

    if profit == 0:
        return None
    pts_per_usd = abs(current - entry) / abs(profit)
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


def modify_order(ticket: str, stop_loss: float):
    """Modify SL via gateway REST API."""
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        r = requests.post(
            f"{URL}/order/modify",
            json={"ticket": ticket, "sl": stop_loss},
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

        for pos in positions:
            ticket = str(pos.get("ticket"))
            profit = pos.get("profit", 0.0)

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
