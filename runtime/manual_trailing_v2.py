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
    profiles = {
        "bystra":     {"start": 3.0, "dist": 2.5},
        "aggressive": {"start": 1.5, "dist": 0.8},
        "semi_hft":   {"start": 1.5, "dist": 1.0},
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
URL                  = os.getenv("MT5_GATEWAY_URL",   "https://chips-extension-extensions-wearing.trycloudflare.com")
TOKEN                = os.getenv("MT5_GATEWAY_TOKEN", "Jojo_56790@_000tUi_OO9")
HEADERS              = {"Authorization": f"Bearer {TOKEN}"}
TIE_HEARTBEAT_PATH   = "/tmp/tie_production_heartbeat.txt"
HEARTBEAT_TIMEOUT_SEC = 30

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
        return "aggressive"
    parts = comment.split("_")
    return STRATEGY_MAP.get(parts[1].upper(), "aggressive") if len(parts) >= 2 else "aggressive"


def compute_new_sl(pos, profile):
    ticket      = str(pos.get("ticket"))
    direction   = str(pos.get("direction", "")).upper()
    entry       = float(pos.get("price_open", 0) or 0)
    current_sl  = float(pos.get("sl", 0) or 0)
    current_tp  = float(pos.get("tp", 0) or 0)
    profit      = float(pos.get("profit", 0) or 0)
    current_px  = float(pos.get("price_current", 0) or 0)

    if profit < 0:
        return None  # Belum profit, gak trailing

    # Peak profit tracking
    prev_peak = _peak.get(ticket, 0)
    if profit > prev_peak:
        _peak[ticket] = profit

    # Phase 1: BE Lock
    if profit >= current_be_lock and current_sl == 0:
        return round(entry, 2)  # Move SL to BE (entry price)

    # Phase 2: Trailing
    if profit >= profile["start"]:
        # Tentukan trailing distance
        trail_dist = profile["dist"]
        
        if direction == "BUY":
            new_sl = current_px - trail_dist
            if current_sl == 0 or new_sl > current_sl:
                return round(new_sl, 2)
        else:  # SELL
            new_sl = current_px + trail_dist
            if current_sl == 0 or new_sl < current_sl:
                return round(new_sl, 2)

    return None


def modify_order(ticket, new_sl, tp=None):
    """Modify SL/TP via MT5 Gateway."""
    payload = {"ticket": ticket, "sl": new_sl}
    if tp:
        payload["tp"] = tp
    r = requests.post(f"{URL}/account/position/modify", headers=HEADERS, json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


# ========= MAIN LOOP =========
def run():
    log.info("Manual Trailing V2 (Shadow Mode) started.")
    
    while True:
        try:
            # Load dynamic config at each loop iteration
            global current_profiles, current_be_lock, current_hedge_close
            current_profiles, current_be_lock, current_hedge_close = load_dynamic_config()
            
            tie_alive = check_tie_alive()
            positions = get_positions()
            tie_positions = [p for p in positions if str(p.get("comment", "")).startswith("TIE_")]

            # === HEDGE CLOSE (selalu aktif, SHADOW atau ACTIVE) ===
            if tie_positions:
                hedge_targets = process_baskets(tie_positions)
                for pos in hedge_targets:
                    ticket = str(pos.get("ticket"))
                    try:
                        r = requests.post(f"{URL}/account/position/close", 
                                        headers=HEADERS, json={"ticket": ticket}, timeout=5)
                        r.raise_for_status()
                        log.info(f"[HEDGE CLOSE] {ticket} closed.")
                    except Exception as e:
                        log.error(f"[HEDGE CLOSE FAIL] {ticket}: {e}")

            # === SHADOW MODE — TIE hidup, cuma monitor ===
            if tie_alive:
                for pos in tie_positions:
                    ticket      = str(pos.get("ticket"))
                    profile_key = extract_profile_key(pos.get("comment", ""))
                    profile     = current_profiles.get(profile_key, current_profiles["aggressive"])

                    new_sl = compute_new_sl(pos, profile)
                    if new_sl:
                        log.info(f"[SHADOW] {ticket}: suggest SL={new_sl} (profit=${pos.get('profit',0):.2f})")

            # === ACTIVE MODE — TIE mati ===
            else:
                if not tie_positions:
                    time.sleep(POLL_SEC)
                    continue

                log.warning(f"[ACTIVE] TIE heartbeat lost > {HEARTBEAT_TIMEOUT_SEC}s. Taking over trailing...")

                for pos in tie_positions:
                    ticket      = str(pos.get("ticket"))
                    profile_key = extract_profile_key(pos.get("comment", ""))
                    profile     = current_profiles.get(profile_key, current_profiles["aggressive"])

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