"""
manual_trailing_v2.py — Failsafe Trailing Manager (Primary SL Manager)
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
    profiles = {
        "riri_scalps_v1": {"start": 1.5, "dist": 0.8},
        "bystra":     {"start": 3.0, "dist": 2.5},
    }
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
URL                  = os.getenv("MT5_GATEWAY_URL",   "https://buildings-threats-built-plugins.trycloudflare.com")
TOKEN                = os.getenv("MT5_GATEWAY_TOKEN", "Jojo_56790@_000tUi_OO9")
HEADERS              = {"Authorization": f"Bearer {TOKEN}"}
TIE_HEARTBEAT_PATH   = "/tmp/tie_production_heartbeat.txt"
HEARTBEAT_TIMEOUT_SEC = 30

STRATEGY_MAP = {
    "B":   "bystra",
    "BA":  "bystra",
    "BAS": "bystra",
    "R":   "riri_scalps_v1",
    "F":   "riri_scalps_v1",   # Engine F (EA Nyao port) — same trailing profile
    "3CA": "riri_scalps_v1",   # ThreeCa (was falling to default by luck)
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
    Close hedged BUY+SELL per symbol kalau total profit >= HEDGE_CLOSE_USD.
    Return list of tickets to close.
    """
    by_symbol = {}
    for p in positions:
        sym = p.get("symbol", "")
        if not sym: continue
        by_symbol.setdefault(sym, []).append(p)

    to_close = []
    for symbol, pos_list in by_symbol.items():
        directions = {str(p.get("direction", "")).lower() for p in pos_list}
        if "buy" not in directions or "sell" not in directions:
            continue  # bukan hedge, skip

        total_profit = sum(p.get("profit", 0.0) for p in pos_list)
        if total_profit >= current_hedge_close:
            log.warning(
                f"[HEDGE] {symbol}: {len(pos_list)} pos (BUY+SELL) total profit ${total_profit:.2f} "
                f">= ${current_hedge_close} → close all"
            )
            to_close.extend(pos_list)

    return to_close


def extract_profile_key(comment: str) -> str:
    if not comment or not comment.startswith("TIE_"):
        return "riri_scalps_v1"
    parts = comment.split("_")
    return STRATEGY_MAP.get(parts[1].upper(), "riri_scalps_v1") if len(parts) >= 2 else "riri_scalps_v1"


def compute_new_sl(pos, profile):
    ticket      = str(pos.get("ticket"))
    direction   = str(pos.get("direction", "")).upper()
    entry       = float(pos.get("price_open", 0) or 0)
    current_sl  = float(pos.get("sl", 0) or 0)
    profit      = float(pos.get("profit", 0) or 0)
    current_px  = float(pos.get("current_price", 0) or pos.get("price_current", 0) or 0)
    volume      = float(pos.get("volume", 0.01) or 0.01)

    if profit < 0 or not current_px or not entry:
        return None  # Belum profit / data belum lengkap, gak trailing

    # Peak profit tracking (basis kunci lock)
    peak = _peak.get(ticket, 0)
    if profit > peak:
        _peak[ticket] = peak = profit

    # XAUUSD: 1 lot = 100 oz → $100 per 1.0 poin harga per lot
    usd_per_point = volume * 100.0
    start    = profile["start"]
    dist     = profile["dist"]
    lock_r   = profile.get("lock_ratio", 0.5)   # kunci 50% dari puncak profit
    lock_min = profile.get("lock_min", 1.0)     # $ floor — lebih dari spread, anti slippage-loss

    # Phase 1: BE+buffer lock (SL masih original)
    if profit >= current_be_lock and current_sl == 0:
        buf = max(0.1, lock_min / usd_per_point)
        return round(entry + buf if direction == "BUY" else entry - buf, 2)

    if profit < start:
        return None

    # Phase 2: trailing = max(jarak harga, floor lock profit)
    lock_off = max(lock_min, peak * lock_r) / usd_per_point
    if direction == "BUY":
        new_sl = max(current_px - dist, entry + lock_off)
        new_sl = min(new_sl, current_px - 0.05)          # SL wajib di bawah harga
        if (current_sl == 0 or new_sl > current_sl + 0.04) and new_sl > entry:
            return round(new_sl, 2)
    else:  # SELL
        new_sl = min(current_px + dist, entry - lock_off)
        new_sl = max(new_sl, current_px + 0.05)          # SL wajib di atas harga
        if (current_sl == 0 or new_sl < current_sl - 0.04) and new_sl < entry:
            return round(new_sl, 2)

    return None


def modify_order(ticket, new_sl, tp=None):
    """Modify SL/TP via MT5 Gateway."""
    payload = {"ticket": ticket, "sl": new_sl}
    if tp:
        payload["tp"] = tp
    r = requests.post(f"{URL}/trade/modify", headers=HEADERS, json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


# ========= MAIN LOOP =========
def run():
    log.info("Manual Trailing V2 (Primary SL Manager) started.")
    
    while True:
        try:
            # Load dynamic config at each loop iteration
            global current_profiles, current_be_lock, current_hedge_close
            current_profiles, current_be_lock, current_hedge_close = load_dynamic_config()
            
            tie_alive = check_tie_alive()
            positions = get_positions()
            tie_positions = [p for p in positions if str(p.get("comment", "")).startswith("TIE_")]

            # === ALWAYS EXECUTE TRAILING (Manual Trailing = Primary SL Manager) ===
            if tie_positions:
                for pos in tie_positions:
                    ticket      = str(pos.get("ticket"))
                    profile_key = extract_profile_key(pos.get("comment", ""))
                    profile     = current_profiles.get(profile_key, current_profiles["riri_scalps_v1"])

                    new_sl = compute_new_sl(pos, profile)
                    if new_sl:
                        try:
                            modify_order(ticket, new_sl, tp=pos.get("tp"))
                            log.info(f"[{ticket}] MODIFIED SL → {new_sl} (profit=${pos.get('profit',0):.2f})")
                        except Exception as e:
                            log.error(f"[{ticket}] MODIFY FAIL: {e}")

            # === HEDGE CLOSE (selalu aktif) ===
            if tie_positions:
                hedge_targets = process_baskets(tie_positions)
                for pos in hedge_targets:
                    ticket = str(pos.get("ticket"))
                    try:
                        r = requests.post(f"{URL}/trade/close/{ticket}",
                                        headers=HEADERS, timeout=5)
                        r.raise_for_status()
                        log.info(f"[HEDGE CLOSE] {ticket} closed.")
                    except Exception as e:
                        log.error(f"[HEDGE CLOSE FAIL] {ticket}: {e}")

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