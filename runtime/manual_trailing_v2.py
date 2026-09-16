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

# [17-Sep] retry modify SL/TP — requote = gangguan sesaat, bukan penolakan final.
MODIFY_RETRY   = max(1, int(os.environ.get("TIE_MODIFY_RETRY", "4")))
MODIFY_BACKOFF = float(os.environ.get("TIE_MODIFY_BACKOFF", "0.6"))
URL                  = os.getenv("MT5_GATEWAY_URL",   "https://statute-expired-chapter-subscribers.trycloudflare.com")
TOKEN                = os.getenv("MT5_GATEWAY_TOKEN", "Xs-EjloGUf_WxDlpLHEkRNbbVcsmtRlV")
HEADERS              = {"Authorization": f"Bearer {TOKEN}"}
TIE_HEARTBEAT_PATH   = "/tmp/tie_production_heartbeat.txt"
HEARTBEAT_TIMEOUT_SEC = 30

STRATEGY_MAP = {
    "B":   "bystra",
    "BA":  "bystra",
    "BAS": "bystra",
    "R":   "riri_scalps_v1",
    "F":   "riri_scalps_v1",   # Engine F (EA Nyao port)
    "RIRI_SCALPS": "riri_scalps_v1",
    "T":   "three_ca",          # [3Ca v2.0] comment TIE_T_<tag>_* — jangan sampe jatuh ke fallback
    "3CA": "three_ca",         # ThreeCa: peak-lock model
    "E":   "two_e",            # [2E] comment TIE_E_<tag>_Lx/X1 — satu keluarga peak-lock
    "3C":  "three_ca",         # [v2.6 comment simple] 3C_B_/3C_S_
    "2E":  "two_e",            # [v2.6] 2E_B_/2E_S_
}

# ========= EA PARITY TRAILING (port of RiriScalps.mq5 ManageTrailingTPSL) =========
# EA default: trail aktif begitu profit >= MinBreakEvenProfit*ProfitThresholdMultiplier
# (= $0.75 @0.05), jarak trail $0.2 (INPUT_DOLLAR), SL tak pernah mundur,
# BE-lock: SL minimal = entry + spread + $0.5-offset (BUY; mirror utk SELL).
# TIE lama: start $1.0 + dist $0.5 + lock 50% peak → profit $0.80-0.99 gak
# kesentuh sama sekali → balik ke SL penuh. EA udah ngamanin. Itu selisihnya.
def _ea_parity_sl(pos, profile, spread_price):
    direction  = str(pos.get("direction", "")).upper()
    entry      = float(pos.get("price_open", 0) or 0)
    current_sl = float(pos.get("sl", 0) or 0)
    profit     = float(pos.get("profit", 0) or 0)
    volume     = float(pos.get("volume", 0.01) or 0.01)
    current_px = float(pos.get("current_price", 0) or pos.get("price_current", 0) or 0)
    if not entry or not current_px or volume <= 0:
        return None
    min_be   = float(profile.get("min_be_profit", 0.5))
    mult     = float(profile.get("profit_mult", 1.5))
    trail_usd = float(profile.get("trail_dollar", 0.2))
    threshold = min_be * mult
    if min_be > 0 and profit < threshold:
        return None  # EA: TrailingSLOnProfitableOnly
    usd_per_point = volume * 100.0          # XAUUSD: 1 lot = 100 oz
    trail_dist = trail_usd / usd_per_point
    # BE-lock price (EA CalculateBreakEvenPrice w/o commission/swap: entry+spread+minProfit)
    be_off = (min_be / usd_per_point) if min_be > 0 else 0.0
    if direction == "BUY":
        if current_px - entry < trail_dist:
            return None  # EA: profitPoints >= finalTrailingPoints
        sl = current_px - trail_dist
        sl = min(sl, current_px - 0.05)     # EA: clamp maxAllowedSL = BID - minDistance
        be = entry + (spread_price or 0.0) + be_off
        sl = max(sl, be)                    # EA: break-even lock floor (setelah clamp)
        if sl >= current_px:
            return None                     # EA safety: calculatedSL < BID, skip modify
        if current_sl == 0 or sl > current_sl + 0.005:  # EA: only move UP
            return round(sl, 3)
    else:
        if entry - current_px < trail_dist:
            return None
        sl = current_px + trail_dist
        sl = max(sl, current_px + 0.05)     # EA: clamp minAllowedSL = ASK + minDistance
        be = entry - (spread_price or 0.0) - be_off
        sl = min(sl, be)                    # EA: BE-lock cap (SELL)
        if sl <= current_px:
            return None                     # EA safety: calculatedSL > ASK
        if current_sl == 0 or sl < current_sl - 0.005:  # EA: only move DOWN
            return round(sl, 3)
    return None


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


def get_spread(symbol: str = "XAUUSD") -> float:
    """Live spread in PRICE units (ask-bid) — EA pakai ini buat BE-lock."""
    try:
        r = requests.get(f"{URL}/trade/price/{symbol}", headers=HEADERS, timeout=5)
        j = r.json()
        return max(0.0, float(j.get("ask", 0)) - float(j.get("bid", 0)))
    except Exception:
        return 0.0  # fail-open: BE-lock tanpa komponen spread


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
    if not comment or not comment.startswith(("TIE_", "3C_", "2E_")):
        return "riri_scalps_v1"
    parts = comment.split("_")
    if parts[0] in ("3C", "2E"):
        return STRATEGY_MAP[parts[0]]
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
    """Modify SL/TP via MT5 Gateway — RETRY cerdas (requote = gangguan sesaat).

    [17-Sep fix, selaras adapters/broker/mt5_broker.py] Dulu sekali requote langsung
    dibuang: BE-lock gagal, posisi balik ke SL awal dan kena SL padahal udah profit
    (bukti E77100 #3830163215: 3x BE-lock `SL 4349.16 -> 4341.47` ditolak -> loss).
    """
    payload = {"ticket": ticket, "sl": new_sl}
    if tp:
        payload["tp"] = tp
    transient_kw = ("requote", "off quote", "off quotes", "busy", "timeout",
                    "timed out", "connection", "temporarily", "try again",
                    "price changed", "invalid price", "slippage", "server")
    last = ""
    attempt = 0
    while attempt < MODIFY_RETRY:
        attempt += 1
        try:
            r = requests.post(f"{URL}/trade/modify", headers=HEADERS, json=payload, timeout=5)
            r.raise_for_status()
            if attempt > 1:
                log.info(f"[{ticket}] modify berhasil di percobaan {attempt}/{MODIFY_RETRY}")
            return r.json()
        except Exception as e:
            last = str(e)
            low = last.lower()
            code = getattr(getattr(e, "response", None), "status_code", None)
            transient = (isinstance(code, int) and (code == 429 or code >= 500)) or \
                        any(k in low for k in transient_kw)
            if not transient:
                break                     # permanen / gak dikenal -> jangan spam
            if attempt < MODIFY_RETRY:
                # geser SL menjauh dari harga (arah aman) — lepas dari zona requote
                try:
                    _pos = next((x for x in get_positions()
                                 if str(x.get("ticket")) == str(ticket)), None)
                    if _pos and new_sl:
                        _side = "buy" if str(_pos.get("type", "")).lower() in ("0", "buy") else "sell"
                        _b = 0.2 * attempt
                        new_sl = round(new_sl - _b if _side == "buy" else new_sl + _b, 2)
                        payload["sl"] = new_sl
                except Exception:
                    pass
                time.sleep(MODIFY_BACKOFF * attempt)
    log.warning(f"[{ticket}] modify GAGAL {attempt}x ({last[:80]})")
    raise RuntimeError(last)


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
            tie_positions = [p for p in positions if str(p.get("comment", "")).startswith(("TIE_", "3C_", "2E_"))]

            # === ALWAYS EXECUTE TRAILING (Manual Trailing = Primary SL Manager) ===
            if tie_positions:
                _spread_cache = {}
                for pos in tie_positions:
                    ticket      = str(pos.get("ticket"))
                    profile_key = extract_profile_key(pos.get("comment", ""))
                    profile     = current_profiles.get(profile_key, current_profiles["riri_scalps_v1"])

                    if profile.get("ea_parity"):
                        # EA RiriScalps default: trail $0.2 + BE-lock entry+spread+$0.5
                        _sym = pos.get("symbol", "XAUUSD")
                        if _sym not in _spread_cache:
                            _spread_cache[_sym] = get_spread(_sym)
                        new_sl = _ea_parity_sl(pos, profile, _spread_cache[_sym])
                    else:
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