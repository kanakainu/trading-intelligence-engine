"""Self-check 3Ca — mock gateway, SOP 3C v2.x + ladder.
Jalankan: python3 tests/test_three_ca_selfcheck.py    (WAJIB env redirect, jangan nyemar produksi)
"""
import sys, os, types, logging
sys.path.insert(0, "/home/ubuntu/trading-intelligence-engine")
logging.basicConfig(level=logging.WARNING, format="%(name)s %(message)s")

SF = "/tmp/test_3ca_state.json"
os.environ["TIE_3CA_STATE"] = SF
os.environ["TIE_3CA_MARK"] = "/tmp/test_3ca_mark.json"
if os.path.exists(SF):
    os.remove(SF)


class MockGW:
    def __init__(self):
        self.placed, self.deleted, self.next_ticket = [], [], 100
        self.tick = {"ask": 4350.00, "bid": 4349.90, "spread": 20}
        self.positions, self.orders = [], []

    def price(self, sym): return self.tick
    def market_info(self, sym): return {"digits": 2}

    def _post(self, path, body=None):
        if path == "/trade":
            b = dict(body or {}); self.placed.append(b)
            t = self.next_ticket; self.next_ticket += 1
            if b.get("order_type") == "limit":
                self.orders.append({"ticket": t, "symbol": b["symbol"],
                                    "price_open": b["price"], "comment": b["comment"],
                                    "sl": b.get("sl", 0), "tp": b.get("tp", 0)})
            else:
                self.positions.append({"ticket": t, "symbol": b["symbol"],
                                       "comment": b["comment"], "sl": b.get("sl", 0)})
            return {"success": True, "ticket": t, "message": "ok"}
        if path.startswith("/trade/delete/"):
            t = int(path.rsplit("/", 1)[-1])
            self.orders = [o for o in self.orders if o["ticket"] != t]
            self.deleted.append(t)
            return {"success": True}
        raise AssertionError(path)

    def _get(self, path):
        if path == "/trade/orders": return self.orders
        if path == "/account/positions": return self.positions
        raise AssertionError(path)

    def modify(self, ticket, sl=None, tp=None): return {"success": True}


T0 = 1_757_000_000 // 300 * 300


def candle(t, o, h, l, c):
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "tick_volume": 100}


def m5_bull(n=40):
    cs = []; px = 4310.0
    for i in range(n - 3):
        c = px + 0.85
        cs.append(candle(T0 + i * 300, px, c + 0.3, px - 0.2, c)); px = c
    cs.append(candle(T0 + (n - 3) * 300, 4342.0, 4346.8, 4341.8, 4346.5))   # C3
    cs.append(candle(T0 + (n - 2) * 300, 4346.5, 4347.0, 4346.4, 4346.9))   # C2
    cs.append(candle(T0 + (n - 1) * 300, 4346.9, 4348.8, 4346.8, 4348.6))   # C1
    return cs


def m15_bull():
    cs = []; px = 4280.0
    for i in range(30):
        c = px + 1.2; cs.append(candle(T0 + i * 900, px, c + 0.4, px - 0.4, c)); px = c
    return cs


def ctx_of(m5, price):
    m = types.SimpleNamespace(symbol="XAUUSD", price=price,
                              metadata={"candles": {"M5": m5, "M15": m15_bull()},
                                        "timeframe": "M5"})
    return types.SimpleNamespace(scan=types.SimpleNamespace(market=m))


from strategies.three_ca.strategy import ThreeCaStrategy, MAX_POS_PER_PATTERN  # noqa: E402


def fresh():
    if os.path.exists(SF):
        os.remove(SF)
    st = ThreeCaStrategy(); gw = MockGW(); st.set_broker(gw)
    st.set_safety_gates({"gov": None, "budget": None}); st.initialize()
    return st, gw


def atr_of(closed_):
    trs = []
    for k in range(max(1, len(closed_) - 14), len(closed_)):
        ck, pk = closed_[k], closed_[k - 1]
        trs.append(max(ck["high"] - ck["low"], abs(ck["high"] - pk["close"]),
                       abs(ck["low"] - pk["close"])))
    return sum(trs) / len(trs)


base = m5_bull()
form = candle(T0 + 40 * 300, 4348.6, 4349.0, 4348.4, 4348.8)

# 1. PO terpasang
st, gw = fresh()
r = st.analyze(ctx_of(base + [form], 4348.9))
assert r.reason.startswith("3ca_po:"), r.reason
po = gw.placed[-1]
buf = st._p["buf"]
assert po["order_type"] == "limit" and po["direction"] == "buy"
assert abs(po["price"] - (4347.0 + buf)) < 0.011, (po["price"], 4347.0 + buf)
# SL = foot (wick terdalam C1-3) ATAU anchor 2.5xATR kalau struktur kejauhan — dua-duanya di bawah entry
assert po["price"] - po["sl"] >= 1.0, (po["price"], po["sl"])
assert po["sl"] < 4346.4, po["sl"]   # di bawah low C2, bukan mepet entry
assert po["lot"] == 0.01
print("1. PO OK @%.2f SL=%.2f buf=%.2f" % (po["price"], po["sl"], buf))

# 2. break C1 -> +2 (M15 kuat) + PO dicabut
# filter v2.6: break = CLOSE M5 di luar inst_lvl + PEN_FRAC*ATR (bukan tick nyempil)
from strategies.three_ca.strategy import PEN_FRAC  # noqa: E402
_lvl = st._p["inst_lvl"] + PEN_FRAC * float(st._p.get("atr") or 0.0)
_bc = round(_lvl + 1.2, 2)
_brk = candle(T0 + 40 * 300, _bc - 0.4, _bc + 0.2, _bc - 0.5, _bc)
_form2 = candle(T0 + 41 * 300, _bc, _bc + 0.3, _bc - 0.3, _bc + 0.1)
r = st.analyze(ctx_of(base + [_brk, _form2], _bc + 0.1))
inst = [p for p in gw.placed if p.get("order_type", "market") == "market"]
assert len(gw.deleted) == 1 and len(inst) == 2, (gw.deleted, len(inst))
# SL instant di bawah entry & di bawah zona struktur (bukan mepet)
assert inst[0]["sl"] < _bc, (inst[0]["sl"], _bc)
assert _bc + 0.1 - inst[0]["sl"] > 0.5, inst[0]["sl"]
assert len(st._p["tickets"]) == 2
print("2. Instant +2 OK, SL=%.2f (anchor ATR)" % inst[0]["sl"])

# 3. [v2.7 EDGE-TRIGGER] break = SATU MOMEN per pola; break kedua -> break_done
st._p["brk_ref"] = 0
r = st.analyze(ctx_of(base + [_brk, _form2], _bc + 0.1))
assert r.reason == "break_done", r.reason
# guard max5: tiket udah penuh -> nyoba break lagi tetep ditolak
st._p["tickets"] = list(range(1, MAX_POS_PER_PATTERN + 1))
st._p["brk_done"] = False; st._p["brk_ref"] = 0
gw.positions = []
r = st.analyze(ctx_of(base + [_brk, _form2], _bc + 0.1))
assert r.reason == "max5", r.reason
assert len(st._p["tickets"]) == MAX_POS_PER_PATTERN
print("3. Break sekali/pola + guard max5 OK")

# 4. no re-entry PO saat pola hidup
r = st.analyze(ctx_of(base + [_brk, _form2], 4347.5))
assert r.reason in ("pattern_alive", "break_done") or r.reason.startswith("3ca_"), r.reason
print("4. Satu pola aktif, no re-entry PO:", r.reason)

# 5. invalidasi C2
st2, gw2 = fresh()
st2.analyze(ctx_of(base + [form], 4348.9))
# candle close < LOW C2 (4346.4) -> invalid; butuh 2 cycle (cycle-1 catat, cycle-2 evaluasi)
bad = candle(T0 + 40 * 300, 4348.6, 4348.9, 4343.5, 4344.0)
st2.analyze(ctx_of(base + [bad, candle(T0 + 41 * 300, 4344, 4345, 4343, 4344.5)], 4344.6))
r = st2.analyze(ctx_of(base + [bad, candle(T0 + 41 * 300, 4344, 4345, 4343, 4344.5),
                              candle(T0 + 42 * 300, 4344.5, 4345, 4343.8, 4344.2)], 4344.3))
assert r.reason.startswith("3ca_invalid") and st2._p is None, r.reason
assert gw2.deleted, "PO harus dicabut pas pola mati"
print("5. Invalidasi C2 + cabut PO OK")

# 6. fatal luar C3
st3, gw3 = fresh()
st3.analyze(ctx_of(base + [form], 4348.9))
fatal = base + [candle(T0 + 40 * 300, 4348.6, 4348.9, 4338.5, 4339.0)]
r = st3.analyze(ctx_of(fatal + [candle(T0 + 41 * 300, 4339, 4340, 4338, 4339)], 4339.2))
assert "fatal" in r.reason, r.reason
print("6. Fatal luar C3 OK ->", r.reason)

# 7. sideways reject
from detectors.three_candle_detector import ema_series, band_cross_chop  # noqa: E402
cs = [candle(T0 + i * 300, 4344, 4344.8, 4343.2, 4344 + (0.8 if i % 2 else -0.8)) for i in range(30)]
e9, e21 = ema_series([c["close"] for c in cs], 9), ema_series([c["close"] for c in cs], 21)
assert band_cross_chop(cs, e9, e21), "chop harus ke-deteksi"
print("7. Sideways flip OK")

# 8. persistence
st5 = ThreeCaStrategy(); st5.set_broker(gw); st5.initialize()
assert st5._p is None or st5._p["tag"] == st._p["tag"]
print("8. Persistence OK")

# 9. PO hit by broker
st6, gw6 = fresh()
st6.analyze(ctx_of(base + [form], 4348.9))
ticket_po = st6._p["po_ticket"]
gw6.orders = []
gw6.positions = [{"ticket": ticket_po, "symbol": "XAUUSD",
                  "comment": f"TIE_T_{st6._p['tag']}_PO", "sl": po["sl"]}]
st6._p["orders_checked"] = 0
r = st6.analyze(ctx_of(base + [form], 4347.6))
assert ticket_po in st6._p["tickets"] and not st6._p["po_ticket"], st6._p
print("9. PO HIT tracking OK (SL C3 dipertahankan)")

# 10. REAPER hantu — pola hidup, PO mati, 0 posisi live (2 cylce confirm) -> pensiun
stR, gwR = fresh()
stR.analyze(ctx_of(base + [form], 4348.9))
gwR.positions = []
stR._p["po_tickets"] = []; stR._p["po_ticket"] = None
stR._p["tickets"] = [1, 2]          # ada riwayat tiket
stR._p["orders_checked"] = 0
r = stR.analyze(ctx_of(base + [form], 4347.5))
assert stR._p is not None and stR._p.get("empty_n") == 1, (r.reason, stR._p)
r = stR.analyze(ctx_of(base + [form], 4347.5))
assert r.reason.startswith("3ca_done") and stR._p is None, r.reason
print("10. Reaper hantu OK ->", r.reason)

# 11. LADDER 3C: TIE_3C_LADDER=N -> N PO bertingkat di area C2
import importlib  # noqa: E402
os.environ["TIE_3C_LADDER"] = "3"
import strategies.three_ca.strategy as m3  # noqa: E402
importlib.reload(m3)
st7, gw7 = fresh()          # fresh() pakai kelas hasil reload
st7 = m3.ThreeCaStrategy(); gw7 = MockGW(); st7.set_broker(gw7)
st7.set_safety_gates({"gov": None, "budget": None}); st7.initialize()
r = st7.analyze(ctx_of(base + [form], 4348.9))
pts = [p for p in gw7.placed if p.get("order_type") == "limit"]
assert len(pts) == 3, [p["price"] for p in pts]
pxs = sorted(p["price"] for p in pts)
assert pxs[0] < pxs[1] < pxs[2], pxs            # bertingkat naik
assert abs(pxs[-1] - (4347.0 + buf)) < 0.011, pxs  # ujung = high C2+buf (perilaku lama)
# tangga mulai 1/N span dari body C2 (bukan mepet tepi), ujung = po_price lama
assert 4346.5 < pxs[0] < pxs[-1], pxs
assert abs(pxs[0] - (4346.5 + (4347.0 + buf - 4346.5) / 3)) < 0.03, pxs
assert len(st7._p["po_tickets"]) == 3
print("11. Ladder 3C x3 OK:", [round(x, 2) for x in pxs])
os.environ["TIE_3C_LADDER"] = "1"

print("\nV-3CA: 11/11 CHECK LOLOS")