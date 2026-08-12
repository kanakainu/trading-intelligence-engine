"""
manual_trailing_v2.py — Failsafe Trailing Manager (Shadow Mode)
Contek dari manual_trailing.py Torto V4 logic. Jadi cadangan kalau TIE Production mati.

MODE:
- SHADOW: Cuma nonton posisi TIE_, gak aktif modify.
- ACTIVE: Kalau TIE heartbeat loss > 30s, take over trailing.

Hedge Close Logic:
- Deteksi BUY + SELL open bersamaan per symbol
- Kalau total floating profit semua posisi > HEDGE_CLOSE_USD → close semua

Profiles:
- bystra:     start $3.0, dist $2.5, be_lock $1.0
- aggressive: start $2.0, dist $0.5, be_lock $1.0
- semi_hft:   start $2.0, dist $0.5, be_lock $1.0
"""
import sys, os, time, logging, requests, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ManualTrailingV2")

# ========= CONFIG =========
POLL_SEC             = 5
URL                  = os.getenv("MT5_GATEWAY_URL",   "https://chips-extension-extensions-wearing.trycloudflare.com")
TOKEN                = os.getenv("MT5_GATEWAY_TOKEN", "Jojo_56790@_000tUi_OO9")
HEADERS              = {"Authorization": f"Bearer {TOKEN}"}
TIE_HEARTBEAT_PATH   = "/tmp/tie_production_heartbeat.txt"
HEARTBEAT_TIMEOUT_SEC = 30

# Hedge close trigger — kalau BUY+SELL open bersamaan & total profit > ini → close semua
HEDGE_CLOSE_USD = 3.0

# BE lock offset in USD (dikunci $1.5 profit setelah phase 1 trigger)
BE_LOCK_USD = 1.5

# ========= PROFILES =========
PROFILES = {
    "bystra":     {"start": 3.0, "dist": 2.5},
    "aggressive": {"start": 1.5, "dist": 0.8},
    "semi_hft":   {"start": 1.5, "dist": 1.0},
}

STRATEGY_MAP = {
    "B":   "bystra",
    "BA":  "bystra",
    "BAS": "bystra",
    "A":   "aggressive",
    "S":   "semi_hft",
}

# Peak profit tracker per ticket
_peak: dict = {}

# ========= HELPERS =========
def check_tie_alive():
    if not os.path.exists(TIE_HEARTBEAT_PATH):
        return False
    try:
        with open(TIE_HEARTBEAT_PATH) as f:
            age = time.time() - float(f.read().strip())
        return age < HEARTBEAT_TIMEOUT_SEC
    except Exception as e:
        log.warning(f"Heartbeat read error: {e}")
        return False


def get_positions():
    try:
        r = requests.get(f"{URL}/account/positions", headers=HEADERS, timeout=5)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        log.error(f"Positions fetch fail: {e}")
        return []


def process_baskets(positions):
    """
    Basket Take Profit logic:
    - BUY positions >= 3 and Total Profit BUY >= $3.0 -> CLOSE ALL BUY
    - SELL positions >= 3 and Total Profit SELL >= $3.0 -> CLOSE ALL SELL
    """
    buys = [p for p in positions if p.get("type", "").upper() == "BUY" or p.get("type") == 0]
    sells = [p for p in positions if p.get("type", "").upper() == "SELL" or p.get("type") == 1]

    # BUY Basket
    if len(buys) >= 3:
        total_buy_profit = sum(p.get("profit", 0.0) for p in buys)
        if total_buy_profit >= 3.0:
            log.info(f"BASKET TP: Closing {len(buys)} BUY positions (Total Profit: ${total_buy_profit:.2f})")
            for p in buys:
                close_position(p["ticket"], p)

    # SELL Basket
    if len(sells) >= 3:
        total_sell_profit = sum(p.get("profit", 0.0) for p in sells)
        if total_sell_profit >= 3.0:
            log.info(f"BASKET TP: Closing {len(sells)} SELL positions (Total Profit: ${total_sell_profit:.2f})")
            for p in sells:
                close_position(p["ticket"], p)


def extract_profile_key(comment):
    """TIE_S_BUY → semi_hft, TIE_A_SELL → aggressive, etc."""
    if not comment or not comment.startswith("TIE_"):
        return "aggressive"  # default fallback
    parts = comment.split("_")
    code = parts[1] if len(parts) >= 2 else "A"
    strategy_id = STRATEGY_MAP.get(code, "aggressive")
    if "semi_hft" in strategy_id:
        return "semi_hft"
    if "aggressive" in strategy_id:
        return "aggressive"
    return "bystra"


def compute_new_sl(pos, profile):
    """
    Torto V4 logic (contek manual_trailing.py).
    Phase 1: profit >= START → lock BE + $BE_LOCK_USD dari entry
    Phase 2: profit pullback dari peak → lock (peak - dist)
    """
    profit  = pos.get("profit", 0.0)
    entry   = pos.get("open_price", 0.0)
    current = pos.get("current_price", 0.0)
    sl      = pos.get("sl") or 0.0
    is_buy  = str(pos.get("direction", "")).lower() == "buy"
    ticket  = str(pos.get("ticket"))

    if profit < profile["start"] or current == entry or profit == 0:
        return None

    pts_per_usd = abs(current - entry) / abs(profit)

    # Phase 1: BE lock — ngunci $BE_LOCK_USD dari entry
    be_sl = entry + (BE_LOCK_USD * pts_per_usd if is_buy else -(BE_LOCK_USD * pts_per_usd))
    be_sl = round(be_sl, 2)

    if sl == 0.0 or (is_buy and be_sl > sl) or (not is_buy and be_sl < sl):
        log.info(f"[{ticket}] BE lock ${BE_LOCK_USD} → SL {be_sl:.2f} | profit ${profit:.2f}")
        return be_sl

    # Phase 2: Dynamic trail dari peak
    if ticket not in _peak or profit > _peak[ticket]:
        _peak[ticket] = profit

    lock_floor = _peak[ticket] - profile["dist"]
    if lock_floor <= 0:
        return None

    sl_offset = lock_floor * pts_per_usd
    new_sl = round(entry + (sl_offset if is_buy else -sl_offset), 2)

    if (is_buy and new_sl > sl) or (not is_buy and new_sl < sl):
        log.info(f"[{ticket}] Trail: profit ${profit:.2f} peak ${_peak[ticket]:.2f} locked ${lock_floor:.2f} → SL {new_sl:.2f}")
        return new_sl

    return None


def close_position(ticket, pos):
    """Market close posisi via gateway."""
    is_buy  = str(pos.get("direction", "")).lower() == "buy"
    side    = "sell" if is_buy else "buy"
    volume  = pos.get("volume", 0.01)
    symbol  = pos.get("symbol", "XAUUSD")
    payload = {
        "ticket": int(ticket),
        "action": "close",
        "symbol": symbol,
        "volume": volume,
        "type":   side,
    }
    try:
        r = requests.post(f"{URL}/trade/close/{int(ticket)}", json=payload, headers=HEADERS, timeout=5)
        r.raise_for_status()
        log.info(f"[{ticket}] CLOSED (hedge exit) | profit ${pos.get('profit', 0):.2f}")
        return True
    except Exception as e:
        log.error(f"[{ticket}] Close fail: {e}")
        return False


def modify_order(ticket, new_sl, tp=None):
    payload = {"ticket": int(ticket), "sl": new_sl, "tp": tp or 0}
    try:
        r = requests.post(f"{URL}/trade/modify", json=payload, headers=HEADERS, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error(f"Modify fail: {e}")
        raise


def check_hedge_close(positions):
    """
    Deteksi BUY + SELL open bersamaan per symbol.
    Kalau total profit semua posisi itu > HEDGE_CLOSE_USD → close semua.
    Returns list of tickets to close.
    """
    from collections import defaultdict
    by_symbol = defaultdict(list)
    for pos in positions:
        by_symbol[pos.get("symbol", "")].append(pos)

    to_close = []
    for symbol, pos_list in by_symbol.items():
        directions = {str(p.get("direction", "")).lower() for p in pos_list}
        if "buy" not in directions or "sell" not in directions:
            continue  # bukan hedge, skip

        total_profit = sum(p.get("profit", 0.0) for p in pos_list)
        if total_profit >= HEDGE_CLOSE_USD:
            log.warning(
                f"[HEDGE] {symbol}: {len(pos_list)} pos (BUY+SELL) total profit ${total_profit:.2f} "
                f">= ${HEDGE_CLOSE_USD} → close all"
            )
            to_close.extend(pos_list)

    return to_close


# ========= MAIN LOOP =========
def run():
    log.info("Manual Trailing V2 (Shadow Mode) started.")
    log.info(f"Heartbeat: {TIE_HEARTBEAT_PATH} | Hedge close: ${HEDGE_CLOSE_USD} | BE lock: ${BE_LOCK_USD}")

    while True:
        try:
            tie_alive = check_tie_alive()
            positions = get_positions()
            tie_positions = [p for p in positions if str(p.get("comment", "")).startswith("TIE_")]

            # === HEDGE CLOSE (selalu aktif, SHADOW atau ACTIVE) ===
            if tie_positions:
                hedge_targets = check_hedge_close(tie_positions)
                for pos in hedge_targets:
                    ticket = str(pos.get("ticket"))
                    close_position(ticket, pos)
                    _peak.pop(ticket, None)
                
                # === BASKET TP (BUY/SELL >= 3 and Profit >= $3.0) ===
                # Toggle: config/features.json → basket_tp: true/false
                try:
                    _feat_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "features.json")
                    with open(_feat_path) as _ff:
                        _feat = json.load(_ff)
                    _basket_on = _feat.get("basket_tp", True)
                except Exception:
                    _basket_on = True
                if _basket_on:
                    process_baskets(tie_positions)

                # Kalau ada yg di-close, skip trailing tick ini
                if hedge_targets:
                    time.sleep(POLL_SEC)
                    continue

            # === SHADOW MODE — skip trailing when TIE alive ===
            if tie_alive:
                time.sleep(POLL_SEC)
                continue

            # === ACTIVE MODE — TIE mati ===
            if not tie_positions:
                time.sleep(POLL_SEC)
                continue

            log.warning(f"[ACTIVE] TIE heartbeat lost > {HEARTBEAT_TIMEOUT_SEC}s. Taking over trailing...")

            for pos in tie_positions:
                ticket      = str(pos.get("ticket"))
                profile_key = extract_profile_key(pos.get("comment", ""))
                profile     = PROFILES.get(profile_key, PROFILES["aggressive"])

                new_sl = compute_new_sl(pos, profile)
                if new_sl:
                    try:
                        modify_order(ticket, new_sl, tp=pos.get("tp"))
                        log.info(f"[{ticket}] MODIFIED SL → {new_sl}")
                    except Exception as e:
                        log.error(f"[{ticket}] Modify failed: {e}")

            # Cleanup peak untuk posisi yg udah close
            active_tickets = {str(p.get("ticket")) for p in tie_positions}
            for t in list(_peak):
                if t not in active_tickets:
                    del _peak[t]

            time.sleep(POLL_SEC)

        except KeyboardInterrupt:
            log.info("Manual Trailing V2 stopped.")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(POLL_SEC)


if __name__ == "__main__":
    run()
