"""TUIUL replay-sim — FULL state-machine backtest SOP 3C/2E v2.9.4/v1.8.1.

Kelas strategi ASLI disuapin candle M5/M15 histori lewat mock gateway:
limit fill gap-aware, SL/TP wick-touch (SL win = konservatif), trailing pakai
fungsi ASLI compute_new_sl, jam difake (time.time) supaya quota-30m/ghost-15m/
anti-chase jalan dalam waktu market, bukan waktu dinding.

Jalankan:  python3 backtest/tuiul_replay.py --bars 8000
Output :  backtest/reports/tuiul_replay_<ts>.json + metrik stdout.
"""
from __future__ import annotations
import sys, os, json, time, types, argparse, datetime
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')
sys.path.insert(0, '/home/ubuntu/.hermes/trading')
os.environ.setdefault("TIE_3CA_STATE", "/tmp/bt_3ca_state.json")
os.environ.setdefault("TIE_3CA_MARK", "/tmp/bt_3ca_mark.json")
os.environ.setdefault("TIE_2E_MARK", "/tmp/bt_2e_mark.json")

import strategies.three_ca.strategy as m3
import strategies.two_e.strategy as m2
import runtime.manual_trailing_v2 as mtr
import runtime.trading_intelligence as ti
from runtime.trading_intelligence import DailyProfitGovernorV2, TradeBudgetManager

mtr.current_be_lock = 1.0
mtr._peak.clear()

try:
    import yaml
    PROFILES = (yaml.safe_load(open('/home/ubuntu/trading-intelligence-engine/'
                                    'config/trailing_profiles.yaml')) or {})
    PROFILES = PROFILES.get('profiles', PROFILES)
except Exception:
    PROFILES = {}
PROFILES.setdefault('three_ca', {'start': 1.0, 'dist': 0.5, 'lock_ratio': 0.5, 'lock_min': 1.0})
PROFILES.setdefault('two_e', {'start': 1.0, 'dist': 0.5, 'lock_ratio': 0.5, 'lock_min': 1.0})

CLOCK = {'t': 0.0}


class FakeTime:
    @staticmethod
    def time():
        return CLOCK['t']
    @staticmethod
    def sleep(x):
        pass


m3.time = FakeTime()
m2.time = FakeTime()


class FakeDateTime:
    """datetime shim: now() = clock pasar, format sama utk governor."""
    @staticmethod
    def now(tz=None):
        return datetime.datetime.fromtimestamp(CLOCK['t'], tz or datetime.timezone.utc)
ti.datetime = FakeDateTime()


def _redirect_state(cls, path):
    cls._state_path = property(lambda self: path)


class SimGW:
    def __init__(self, spread=0.18, gov=None):
        self.spread = spread
        self.gov = gov
        self.orders = {}
        self.positions = {}
        self._next = 1000
        self.cur_c = (0, 0, 0, 0, 1.0)
        self.fills = []

    def price(self, sym):
        c = self.cur_c[4]
        return {"bid": c - self.spread / 2, "ask": c + self.spread / 2}

    def _get(self, path, params=None, **kw):
        if path.startswith("/trade/orders"):
            return [{"ticket": int(t)} for t in self.orders]
        if path.startswith("/account/positions"):
            return [dict(p) for p in self.positions.values()]
        if path.startswith("/account"):
            return {"balance": 1000.0, "equity": 1000.0}
        raise AssertionError(f"_get {path}")

    def _post(self, path, body=None):
        body = body or {}
        if path == "/trade":
            t = self._next; self._next += 1
            if body.get("order_type") == "limit":
                self.orders[t] = dict(body, _tk=t)
            else:
                sgn = 1 if body["direction"] == "buy" else -1
                px = self.cur_c[4] + sgn * self.spread / 2
                self._open(t, px, body)
                self.fills.append({"kind": "entry", "t": CLOCK['t'], "price": round(px, 2),
                                   "comment": body.get("comment", ""), "way": "market"})
            return {"success": True, "ticket": t}
        if path.startswith("/trade/delete/"):
            self.orders.pop(int(path.rsplit("/", 1)[1]), None)
            return {"success": True}
        if path.startswith("/trade/modify/"):
            t = int(path.rsplit("/", 1)[1])
            dst = self.positions.get(t) or self.orders.get(t)
            if dst:
                for k in ("sl", "tp"):
                    if body.get(k):
                        dst[k] = float(body[k])
            return {"success": True}
        if path.startswith("/trade/close/"):
            t = int(path.rsplit("/", 1)[1])
            self._close(t, self.cur_c[4], "engine-close")
            return {"success": True}
        raise AssertionError(f"_post {path}")

    def _open(self, t, px, rec):
        self.positions[t] = {"ticket": t, "symbol": rec.get("symbol", "XAUUSD"),
                             "direction": rec["direction"], "volume": float(rec.get("lot", 0.01)),
                             "price_open": round(px, 2), "sl": float(rec.get("sl", 0) or 0),
                             "tp": float(rec.get("tp", 0) or 0), "comment": rec.get("comment", ""),
                             "profit": 0.0, "current_price": px}

    def _pnl(self, pos, px):
        sgn = 1 if pos["direction"] == "buy" else -1
        return (px - pos["price_open"]) * sgn * 100.0 * pos["volume"]

    def _close(self, t, px, reason):
        pos = self.positions.pop(t, None)
        if not pos:
            return
        # [AUDIT Sasa 16-Sep] harga exit kena SEBERANG spread + slippage kecil.
        # Sebelumnya cuma geser 0.02 -> spread nol biaya, backtest ketipu optimis.
        half = self.spread / 2.0
        px = px - half - 0.02 if pos["direction"] == "buy" else px + half + 0.02
        pnl = self._pnl(pos, px)
        self.fills.append({"kind": "exit", "t": CLOCK['t'], "price": round(px, 2),
                           "comment": pos["comment"], "pnl": round(pnl, 2), "reason": reason})
        if self.gov:
            self.gov.record_realized(pnl)   # governor ASLI, aturan live

    def step(self, candle):
        o, h, l = float(candle["open"]), float(candle["high"]), float(candle["low"])
        # spread riil = jarak harga beli/jual; order limit kena sisi kita, exit kena sisi lawan
        for tk in list(self.orders):
            rec = self.orders[tk]
            px = float(rec["price"])
            _ = o, h, l
            if rec["direction"] == "buy" and l <= px:
                self.orders.pop(tk); self._open(tk, min(o, px), rec)
                self.fills.append({"kind": "entry", "t": CLOCK['t'], "price": round(min(o, px), 2),
                                   "comment": rec.get("comment", ""), "way": "PO"})
            elif rec["direction"] == "sell" and h >= px:
                self.orders.pop(tk); self._open(tk, max(o, px), rec)
                self.fills.append({"kind": "entry", "t": CLOCK['t'], "price": round(max(o, px), 2),
                                   "comment": rec.get("comment", ""), "way": "PO"})
        for tk in list(self.positions):
            pos = self.positions[tk]
            buy = pos["direction"] == "buy"
            hit_sl = pos["sl"] and ((buy and l <= pos["sl"]) or (not buy and h >= pos["sl"]))
            hit_tp = pos["tp"] and ((buy and h >= pos["tp"]) or (not buy and l <= pos["tp"]))
            if hit_sl:
                self._close(tk, pos["sl"], "SL")
            elif hit_tp:
                self._close(tk, pos["tp"], "TP")
        # trailing peak-lock — fungsi ASLI, jalan per candle close (live: per-tick)
        for tk, pos in self.positions.items():
            pos["current_price"] = self.cur_c[4]
            pos["profit"] = self._pnl(pos, self.cur_c[4])
            cmt = str(pos["comment"])
            if cmt.startswith(("3C_", "2E_", "TIE_T_", "TIE_E_")):
                prof = PROFILES.get("two_e" if cmt.startswith(("2E_", "TIE_E_")) else "three_ca")
                ns = mtr.compute_new_sl(pos, prof)
                if ns:
                    pos["sl"] = ns


def context_for(m5win, m15win, price):
    mc = types.SimpleNamespace(symbol="XAUUSD", price=price,
                               metadata={"candles": {"M5": m5win, "M15": m15win}})
    return types.SimpleNamespace(scan=types.SimpleNamespace(market=mc), position=None,
                                 timestamp=datetime.datetime.now())


def build_m15(m5):
    agg = {}
    for x in m5:
        t = int(x["time"]); k = t - (t % 900)
        a = agg.get(k)
        if a is None:
            agg[k] = {"time": k, "open": float(x["open"]), "high": float(x["high"]),
                      "low": float(x["low"]), "close": float(x["close"])}
        else:
            a["high"] = max(a["high"], float(x["high"])); a["low"] = min(a["low"], float(x["low"]))
            a["close"] = float(x["close"])
    return agg


def fetch_m5(count):
    """MT5 python via gateway gak bisa offset — pakai loader lama (pos-fixed),
    limit riil ~ Exness tersaji; lebih dari itu minta data lokal."""
    from gateway_client import MT5GatewayClient
    from config.live import GATEWAY_URL, GATEWAY_TOKEN
    gw = MT5GatewayClient(GATEWAY_URL, GATEWAY_TOKEN, timeout=60)
    r = gw.candles("XAUUSD", "M5", min(count, 10000))
    r = r if isinstance(r, list) else r.get("candles", [])
    seen = set(); out = []
    for x in sorted(r, key=lambda y: int(y["time"])):
        t = int(x["time"])
        if t not in seen:
            seen.add(t); out.append(x)
    return out


def run(m5, spread=0.18):
    for f in ("/tmp/bt_3ca_state.json", "/tmp/bt_2e_state.json"):
        if os.path.exists(f):
            os.remove(f)
    _redirect_state(m2.TwoEStrategy, "/tmp/bt_2e_state.json")
    gov = DailyProfitGovernorV2(daily_target=float(os.environ.get("TIE_GOV_TARGET", "30")),
                                daily_loss_limit=float(os.environ.get("TIE_GOV_LOSS", "200")))
    budget = TradeBudgetManager()
    sim = SimGW(spread=spread, gov=gov if os.environ.get("TIE_SIM_GOV", "1") == "1" else None)
    s3 = m3.ThreeCaStrategy(); s2 = m2.TwoEStrategy()
    s3.set_broker(sim); s2.set_broker(sim)
    s3.set_safety_gates({"gov": sim.gov or gov, "budget": budget})
    s2.set_safety_gates({"gov": sim.gov or gov, "budget": budget})
    s3.initialize(); s2.initialize()
    s3._gw_ok = True; s3._gw_probe_t = 1e18   # probe skip (mock dukung limit)
    m15map = build_m15(m5)
    keys = sorted(m15map)
    import bisect
    errs = []
    for i in range(40, len(m5) - 1):
        x = m5[i]
        CLOCK['t'] = float(int(x["time"])) + 300.0    # = detik close candle i (tick pertama candle i+1)
        sim.step(x)
        forming = dict(m5[i + 1])
        sim.cur_c = (int(forming["time"]), float(forming["open"]), float(forming["high"]),
                     float(forming["low"]), float(forming["close"]))
        # slice window: closed s/d i, + 1 slot forming BERSIH (anti bocor masa depan)
        m5win = [{k: float(v) if k != "time" else int(v)
                  for k, v in y.items() if k in ("time", "open", "high", "low", "close")}
                 for y in m5[max(0, i - 39):i + 1]]
        m5win.append({"time": int(forming["time"]), "open": float(x["close"]),
                      "high": float(x["close"]), "low": float(x["close"]),
                      "close": float(x["close"])})
        k15 = int(x["time"]) - (int(x["time"]) % 900)
        j = bisect.bisect_left(keys, k15)
        hist15 = [m15map[k] for k in keys[:j]][-40:]
        if len(hist15) >= 25:
            for st in (s3, s2):
                try:
                    st.analyze(context_for(m5win, hist15, float(x["close"])))
                except Exception as e:
                    errs.append(f"{type(st).__name__} @{int(x['time'])}: {e}")
        while sim.fills:
            f = sim.fills.pop(0)
            yield f
    if errs:
        print("ERR uniq:", *sorted(set(errs))[:8], sep="\n  ")


def metrics(trades):
    ex = [t for t in trades if t["kind"] == "exit"]
    en = [t for t in trades if t["kind"] == "entry"]
    if not ex:
        return {"entries": len(en), "trades": 0}
    pnls = [t["pnl"] for t in ex]
    wins = [p for p in pnls if p > 0]
    gw_, gl_ = sum(wins) or 1e-9, -(sum(p for p in pnls if p <= 0)) or 1e-9
    cur = peak = 1000.0; mdd = 0.0
    for p in pnls:
        cur += p; peak = max(peak, cur); mdd = max(mdd, (peak - cur) / peak * 100)
    br = {}
    for t in ex:
        br[t["reason"]] = br.get(t["reason"], 0) + 1
    bt = {}
    for t in ex:
        k = "3C" if t["comment"].startswith(("3C_", "TIE_T_")) else "2E" if t["comment"].startswith(("2E_", "TIE_E_")) else "?"
        s = bt.setdefault(k, [0, 0.0])
        s[0] += 1; s[1] += t["pnl"]
    return {"entries": len(en), "exits": len(ex), "win_rate": round(len(wins) / len(ex) * 100, 1),
            "net_pnl": round(sum(pnls), 2), "profit_factor": round(gw_ / gl_, 2),
            "avg_win": round(gw_ / max(len(wins), 1), 2),
            "avg_loss": round(-gl_ / max(len(ex) - len(wins), 1), 2),
            "max_dd_pct": round(mdd, 2), "by_reason": br, "by_engine": bt,
            "worst": min(pnls), "best": max(pnls)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=8000)
    ap.add_argument("--spread", type=float, default=0.18,
                    help="spread XAUUSD dlm $ (default 0.18; stress-test: coba 0.25/0.35)")
    a = ap.parse_args()
    t0 = time.time()
    m5 = fetch_m5(a.bars)
    if not m5:
        sys.exit("gateway candles kosong")
    d0 = datetime.datetime.utcfromtimestamp(int(m5[0]["time"]))
    d1 = datetime.datetime.utcfromtimestamp(int(m5[-1]["time"]))
    print(f"data M5 = {len(m5)} candle  {d0} .. {d1} UTC  (~{(d1-d0).days} hari)  spread=${a.spread:.2f}")
    trades = list(run(m5, spread=a.spread))
    mt = metrics(trades)
    print(json.dumps(mt, indent=1))
    print(f"elapsed {time.time()-t0:.0f}s")
    os.makedirs("backtest/reports", exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    json.dump({"meta": {"source": "mt5_gateway_exness", "symbol": "XAUUSD",
                        "tf": "M5", "spread_usd": a.spread, "bars_arg": a.bars},
               "metrics": mt, "window": [str(d0), str(d1)], "bars": len(m5),
               "trades": trades},
              open(f"backtest/reports/tuiul_replay_{stamp}.json", "w"), default=str)
    print(f"saved backtest/reports/tuiul_replay_{stamp}.json")
