"""
manual_trailing_v2.py — Failsafe Trailing Manager (Shadow Mode)
Contek dari manual_trailing.py Torto V4 logic. Jadi cadangan kalau TIE Production mati.

MODE:
- SHADOW: Cuma nonton posisi TIE_, gak aktif modify.
- ACTIVE: Kalau TIE heartbeat loss > 30s, take over trailing.

Hedge Close Logic:
- Deteksi BUY + SELL open bersamaan per symbol
- Kalau total floating profit semua posisi > current_hedge_close → close semua

Profiles:
- bystra:     start $3.0, dist $2.5, be_lock $1.0
- aggressive: start $2.0, dist $0.5, be_lock $1.0
- semi_hft:   start $2.0, dist $0.5, be_lock $1.0
"""
import sys, os, time, logging, requests, json, yaml
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ManualTrailingV2")

# ========= DYNAMIC CONFIG =========
CONFIG_DIR = Path("/home/ubuntu/trading-intelligence-engine/config")
TRAILING_CONFIG_PATH = CONFIG_DIR / "trailing_profiles.yaml"
FEATURES_CONFIG_PATH = CONFIG_DIR / "features.json"

def load_dynamic_config():
    profiles = {"bystra": {"start": 3.0, "dist": 2.5}, "aggressive": {"start": 1.5, "dist": 0.8}, "semi_hft": {"start": 1.5, "dist": 1.0}}
    be_lock_usd = 1.5
    hedge_close_usd = 3.0
    try:
        if TRAILING_CONFIG_PATH.exists():
            with open(TRAILING_CONFIG_PATH) as f: 
                cfg = yaml.safe_load(f)
                profiles = cfg.get("profiles", profiles)
                first_strat = list(profiles.keys())[0]
                be_lock_usd = profiles[first_strat].get("be_lock", be_lock_usd)
        if FEATURES_CONFIG_PATH.exists():
            with open(FEATURES_CONFIG_PATH) as f:
                fcfg = json.load(f)
                hedge_close_usd = fcfg.get("basket_tp_threshold", hedge_close_usd)
    except: pass
    return profiles, be_lock_usd, hedge_close_usd
POLL_SEC             = 5
URL                  = os.getenv("MT5_GATEWAY_URL",   "https://chips-extension-extensions-wearing.trycloudflare.com")
TOKEN                = os.getenv("MT5_GATEWAY_TOKEN", "Jojo_56790@_000tUi_OO9")
TIE_HEARTBEAT_PATH   = "/tmp/tie_production_heartbeat.txt"
HEARTBEAT_TIMEOUT_SEC = 30

# Hedge close trigger — kalau BUY+SELL open bersamaan & total profit > ini → close semua

# BE lock offset in USD (dikunci $1.5 profit setelah phase 1 trigger)

# ========= PROFILES =========

STRATEGY_MAP = {
    "B":   "bystra",
    "BA":  "bystra",
    "BAS": "bystra",
    "A":   "aggressive",
    "S":   "semi_hft",

# Peak profit tracker per ticket

# ========= HELPERS =========
def check_tie_alive():
    if not os.path.exists(TIE_HEARTBEAT_PATH):
        return False
    try:
        with open(TIE_HEARTBEAT_PATH) as f:
            age = time.time() - float(f.read().strip())
        return age < HEARTBEAT_TIMEOUT_SEC
    except Exception as e:
        return False


def get_positions():
    try:
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
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
            for p in buys:
                close_position(p["ticket"], p)

    # SELL Basket
    if len(sells) >= 3:
        total_sell_profit = sum(p.get("profit", 0.0) for p in sells)
        if total_sell_profit >= 3.0:
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
    Phase 1: profit >= START → lock BE + $current_be_lock dari entry
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

    # Phase 1: BE lock — ngunci $current_be_lock dari entry
    be_sl = entry + (current_be_lock * pts_per_usd if is_buy else -(current_be_lock * pts_per_usd))
    be_sl = round(be_sl, 2)

    if sl == 0.0 or (is_buy and be_sl > sl) or (not is_buy and be_sl < sl):
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
    try:
        r.raise_for_status()
        return True
    except Exception as e:
        return False


def modify_order(ticket, new_sl, tp=None):
    try:
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise


def check_hedge_close(positions):
    """
    Deteksi BUY + SELL open bersamaan per symbol.
    Kalau total profit semua posisi itu > current_hedge_close → close semua.
    Returns list of tickets to close.
    """
    from collections import defaultdict
    by_symbol = defaultdict(list)
    for pos in positions:
        by_symbol[pos.get("symbol", "")].append(pos)

    to_close = []
    for symbol, pos_list in by_symbol.items():
        if "buy" not in directions or "sell" not in directions:
            continue  # bukan hedge, skip

        total_profit = sum(p.get("profit", 0.0) for p in pos_list)
        if total_profit >= current_hedge_close:
            log.warning(
            )
            to_close.extend(pos_list)

    return to_close


# ========= MAIN LOOP =========
def run():
    log.info("Manual Trailing V2 (Shadow Mode) started.")

    while True:
        current_profiles, current_be_lock, current_hedge_close = load_dynamic_config()
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

            # === SHADOW MODE — disabled, always run trailing ===
            # if tie_alive:
            #     time.sleep(POLL_SEC)
            #     continue

            # === ACTIVE MODE — TIE mati (only if tie_alive=False) ===
            if not tie_alive:
                if not tie_positions:
                    time.sleep(POLL_SEC)
                    continue


                for pos in tie_positions:
                    ticket      = str(pos.get("ticket"))
                    profile_key = extract_profile_key(pos.get("comment", ""))
                    profile     = current_profiles.get(profile_key, current_profiles["aggressive"])

                    new_sl = compute_new_sl(pos, profile)
                    if new_sl:
                        try:
                            modify_order(ticket, new_sl, tp=pos.get("tp"))
                        except Exception as e:

                # Cleanup peak untuk posisi yg udah close
                for t in list(_peak):
                    if t not in active_tickets:
                        del _peak[t]

            time.sleep(POLL_SEC)

        except KeyboardInterrupt:
            log.info("Manual Trailing V2 stopped.")
            break
        except Exception as e:
            time.sleep(POLL_SEC)


if __name__ == "__main__":
    run()
