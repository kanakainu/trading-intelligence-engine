"""TwoE v1.0 — pola 2-Engulfing SOP Boskuh (14-Sep-2026).

Arsitektur: DIRECT EXECUTOR (sama kayak ThreeCa) — own order lifecycle lewat
MT5GatewayClient, global safety di-inject runtime (halt/DD/governor/budget).

SOP:
  SELL:  C2 Bull kecil -> C1 Bear BESAR; High C1 > High C2; body C1 >= 3x body C2.
  BUY:   mirror (C2 Bear kecil -> C1 Bull besar; Low C1 < Low C2).
  Entry area = dari body C2 s/d close body C1: 4 SELL LIMIT even-split (E2..E5).
  Entry 1 = harga break LOW C1 - buf -> market SELL, ladder dicabut (Boskuh:
            break = harga lari, nunggu retrace = rata-rata rugi).
  SL ALL POSISI = High C1 + buf (satu garis buat semua). TP per posisi = 3.5R
            jaring; exit asli = trailing profile two_e (peak-lock, warisan 3C).
  Batal   = M5 close > High C1 -> pola mati, PO dicabut, posisi dibiarin trailing.
  Max 5 posisi/pola (4 ladder + 1 break), lot 0.01, budget global kehitung.
"""
import os
import json
import time
import uuid
import logging
from datetime import datetime, timezone

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from detectors.three_candle_detector import ema_series

logger = logging.getLogger("TwoE")

LOT = 0.01
MAX_POS = 5                  # 4 ladder + 1 break
# [AUDIT Sasa 16-Sep] knob ablation: ladder L1-L4 ternyata PF ~1.0 / rugi.
# TIE_2E_LADDER=off -> cuma jalur BREAK (X1) yang jalan. Default tetap "on" (SOP live).
LADDER_ON = os.environ.get("TIE_2E_LADDER", "on") != "off"
TP_R = 3.5
BODY_RATIO = 2.5             # [v1.4 Boskuh] body C1 >= 2.5x body C2 — 3x kelangkaan, 2x kemasukan fake engulf
HALT_FLAG = "/tmp/tie_halt"
PEN_FRAC = float(os.environ.get("TIE_PEN_FRAC", "0.3"))   # ablation knob
PEN_FRAC = float(os.environ.get("TIE_PEN_FRAC", "0.3"))
STATE_VERSION = 1


def _noop():
    return None


class TwoEStrategy(BaseStrategy):

    def __init__(self):
        meta = StrategyMetadata(
            id="two_e_v1",
            name="TwoE",
            version="1.8.3",
            priority=84,
            author="Boskuh+Riri",
            description="2-Engulfing: 4 limit di area C2body-C1close + market "
                        "break C1-low; SL all di extreme C1; max 5/pola"
        )
        super().__init__(meta)
        self._p = None
        self._last_pattern = None
        self._gate = None
        self._gw = None
        self._spread_cached = 0.20
        self._digits = 2

    # ── wiring ─────────────────────────────────────────────────────────────
    def set_broker(self, client):
        self._gw = client

    def set_safety_gates(self, gates: dict):
        self._gate = gates

    def set_positions_cache(self, positions: list):
        pass

    def initialize(self) -> None:
        self._initialized = True
        self._load_state()

    def observe(self, context) -> None:
        pass

    def shutdown(self) -> None:
        self._initialized = False

    # ── persistence ────────────────────────────────────────────────────────
    @property
    def _state_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            ".two_e_state.json")

    def _save_state(self):
        try:
            json.dump({"version": STATE_VERSION, "pattern": self._p,
                       "last_pattern": self._last_pattern,
                       "ghost": getattr(self, "_ghost", None)},
                      open(self._state_path, "w"))
        except Exception as e:
            logger.warning("[2E] state save gagal: %s", e)

    def _load_state(self):
        try:
            d = json.load(open(self._state_path))
            if d.get("version") != STATE_VERSION:
                logger.info("[2E] versi state beda — reset")
                return
            self._p = d.get("pattern")
            self._last_pattern = d.get("last_pattern")
            self._ghost = d.get("ghost")
            if self._p:
                logger.info("[2E] RECOVER %s dir=%s tickets=%s po=%s",
                            self._p.get("tag"), self._p.get("dir"),
                            self._p.get("tickets"), self._p.get("po"))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("[2E] state load gagal: %s", e)

    # ── broker helpers ─────────────────────────────────────────────────────
    def _spread(self, sym):
        try:
            p = self._gw.price(sym)
            ask, bid = float(p.get("ask", 0)), float(p.get("bid", 0))
            s = ask - bid if ask > bid > 0 else float(p.get("spread", 0)) / 1000.0
            if s > 0:
                self._spread_cached = s
        except Exception:
            pass
        return self._spread_cached

    def _r(self, v):
        return round(v, self._digits)

    def _place(self, sym, side, lot, price=None, sl=None, tp=None, comment=""):
        body = {"symbol": sym, "direction": side, "lot": lot, "comment": comment,
                "signal_id": str(uuid.uuid4())}
        if price is not None:
            body["order_type"] = "limit"
            body["price"] = price
        if sl:
            body["sl"] = self._r(sl)
        if tp:
            body["tp"] = self._r(tp)
        try:
            r = self._gw._post("/trade", body=body)
            if r.get("success"):
                return True, int(r["ticket"]), r.get("message", "")
            return False, None, str(r.get("message") or r.get("detail") or "rejected")[:60]
        except Exception as e:
            return False, None, str(e)[:60]

    def _delete_order(self, t):
        try:
            self._gw._post(f"/trade/delete/{int(t)}")
            return True
        except Exception:
            return False

    def _pending_orders(self):
        try:
            return self._gw._get("/trade/orders") or []
        except Exception:
            return None

    def _live_pos(self, sym):
        try:
            src = self._gw._get("/account/positions") or []
        except Exception:
            return None               # None = network error, jangan spekulasi
        prefix = self._p.get("cpre", f"TIE_E_{self._p['tag']}") if self._p else "TIE_E_"
        return [p for p in src
                if str(p.get("symbol", "")).upper().startswith(sym.upper())
                and str(p.get("comment", "")).startswith(prefix)]

    def _allowed_global(self, now, budget_key):
        if os.path.exists(HALT_FLAG):
            return False, "halt_flag"
        g = self._gate or {}
        if g.get("dd_ok_fn") and not g["dd_ok_fn"]():
            return False, "dd_guard"
        gov = g.get("gov")
        if gov:
            try:
                ok, why = gov.can_trade()
                if not ok:
                    return False, f"governor:{why}"
            except Exception:
                pass
        b = g.get("budget")
        if b:
            try:
                if not b.can_consume(budget_key):
                    return False, "budget"
            except Exception:
                pass
        return True, ""

    def _consume_budget(self, n=1):
        b = (self._gate or {}).get("budget")
        for _ in range(n):
            try:
                b.consume("two_e")
            except Exception:
                break

    # ── deteksi pola (2 candle, strict Boskuh) ────────────────────────────
    @staticmethod
    def _detect(c1, c2):
        o1, h1, l1, cl1 = (float(c1["open"]), float(c1["high"]),
                           float(c1["low"]), float(c1["close"]))
        o2, h2, l2, cl2 = (float(c2["open"]), float(c2["high"]),
                           float(c2["low"]), float(c2["close"]))
        b1, b2 = abs(cl1 - o1), abs(cl2 - o2)
        if b1 <= 0 or b2 <= 0 or b1 < BODY_RATIO * b2:
            return None
        if cl2 > o2 and cl1 < o1 and h1 > h2 \
                and l2 >= l1 and l2 >= cl1:      # SELL [v1.7: Low C2 ga boleh
            return "SELL"                        #  lebih bawah dr Low C1 & Close C1]
        if cl2 < o2 and cl1 > o1 and l1 < l2 \
                and h2 <= h1 and h2 <= cl1:      # BUY  [v1.7 mirror: High C2 ga
            return "BUY"                         #  boleh lebih tinggi dr High/Close C1]
        return None

    # ── siklus utama ───────────────────────────────────────────────────────
    def analyze(self, context: StrategyContext) -> StrategyResult:
        if self._gw is None:
            return StrategyResult(signal=None, confidence=0.0, reason="no_broker")
        mc = context.scan.market
        sym = mc.symbol
        now = time.time()
        price = mc.price or 0.0
        m5 = (mc.metadata.get("candles") or {}).get("M5", [])
        if len(m5) < 5 or price <= 0:
            return StrategyResult(signal=None, confidence=0.0, reason="no_data")
        closed = m5[:-1]
        self._publish(price)   # heartbeat deck (sama kayak 3Ca) — fase WATCH ikut kesaji

        # [v1.8.1 GHOST] pola pensiun due-close (korban wick) lalu close fatal
        # luar extreme C1 telat <=15mnt => tetap arm counter (mirror 3C v2.9.3).
        g = getattr(self, "_ghost", None)
        if g and not self._p:
            if now - g["t"] > 900:
                self._ghost = None
            elif int(closed[-1].get("time", 0) or 0) > g["t"]:
                _cc = float(closed[-1]["close"])
                _fatal = _cc < g["l1"] if g["dir"] == "BUY" else _cc > g["h1"]
                if _fatal:
                    self._counter = {"dir": "BUY" if g["dir"] == "SELL" else "SELL",
                                     "t": now}
                    logger.info("[2E] counter %s armed dari GHOST %s — close fatal luar C1",
                                self._counter["dir"], g["tag"])
                    self._ghost = None
                    self._save_state()
                elif int(closed[-1]["time"]) > g["t"] + 3 * 300:
                    self._ghost = None

        if self._p:
            why = self._manage(sym, price, closed, now)
            self._publish(price)
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=why or "pattern_alive")

        ok, why = self._allowed_global(now, "two_e")
        if not ok:
            return StrategyResult(signal=None, confidence=0.0, reason=f"global:{why}")

        c1, c2 = closed[-1], closed[-2]
        d = self._detect(c1, c2)
        if not d:
            return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")
        # [v1.6 filter Boskuh] C1 wajib close DI LUAR pita EMA9&EMA21 searah:
        # BUY -> close C1 > EMA9 & > EMA21 | SELL -> < keduanya.
        # Tanpa ini: engulf "valid" nangkep pisau jatuh di bawah EMA = loss gede.
        if len(closed) >= 25:
            closes = [float(x.get("close", 0)) for x in closed]
            e9 = ema_series(closes, 9)[-1]
            e21 = ema_series(closes, 21)[-1]
            cl1f = float(c1.get("close", 0))
            # [SOP-16B Boskuh] ALIGNMENT dulu: EMA9 vs EMA21 harus searah arah trade —
            # sell tanpa 9<21 = jualan di struktur naik (kronologi 12:15: 4 L rugi)
            _align = os.environ.get("TIE_EMA_ALIGN", "3c") == "on"   # [16C] default: 2E BEBAS (hanya "on" penuh yang ngiket)
            ok_ema = (cl1f > e9 and cl1f > e21 and (e9 > e21 or not _align)) if d == "BUY" \
                else (cl1f < e9 and cl1f < e21 and (e9 < e21 or not _align))
            if not ok_ema:
                return StrategyResult(signal=None, confidence=0.0, reason="ema_filter")
        tag = f"E{int(float(c1.get('time', 0)) or 0) % 100000}"
        if tag == self._last_pattern:
            return StrategyResult(signal=None, confidence=0.0, reason="pattern_seen")
        self._last_pattern = tag

        spr = self._spread(sym)
        buf = round(max(2 * spr, 0.01) + 0.01, 2)
        o1, h1, l1, cl1 = (float(c1["open"]), float(c1["high"]),
                           float(c1["low"]), float(c1["close"]))
        o2, h2, l2, cl2 = (float(c2["open"]), float(c2["high"]),
                           float(c2["low"]), float(c2["close"]))

        # [v1.3 SOP counter Boskuh] pola PERTAMA searah counter yang ke-detect
        # dalem window 30 menit -> SL bukan extreme C1, tapi extreme c2 (+buf):
        # c2 = retrace yang ditolak di garis patah = tembok SL paling deket & sah.
        cnt = getattr(self, "_counter", None)
        cnt_mode = bool(cnt and cnt["dir"] == d and (now - cnt["t"]) < 1800)
        if d == "SELL":
            sl = self._r(h2 + buf) if cnt_mode else self._r(h1 + buf)
            zone_lo, zone_hi = cl1, max(cl2, o2)          # C1 close .. body C2 top
            inst = self._r(l1 - buf)                      # break low C1
        else:
            sl = self._r(l2 - buf) if cnt_mode else self._r(l1 - buf)
            zone_lo, zone_hi = min(cl2, o2), cl1          # body C2 bottom .. C1 close
            inst = self._r(h1 + buf)
        if cnt_mode:
            self._counter = None   # sekali pake = counter selesai
            logger.info("[2E] %s COUNTER %s -> SL = extreme C2 %.2f", tag, d, sl)

        cpre = f"2E_{'B' if d == 'BUY' else 'S'}_{tag}"   # [v1.8 comment simple]
        # ladder 4 level even-split area entry (Boskuh: body C2 s/d close C1)
        span = abs(zone_hi - zone_lo)
        po = []
        side = "sell" if d == "SELL" else "buy"
        placed = 0
        for i in range(1, 5) if LADDER_ON else []:
            px = self._r(zone_lo + span * i / 5.0 if d == "SELL"
                         else zone_hi - span * i / 5.0)
            tp = self._r(px - TP_R * (sl - px)) if d == "SELL" else \
                 self._r(px + TP_R * (px - sl))
            okm, t, msg = self._place(sym, side, LOT, price=px, sl=sl, tp=tp,
                                      comment=cpre + f"_L{i}")
            if not okm:
                logger.warning("[2E] %s LIMIT L%d gagal @%.2f: %s", tag, i, px, msg)
                continue
            po.append({"ticket": int(t), "price": px})
            placed += 1
        if not placed and LADDER_ON:
            return StrategyResult(signal=None, confidence=0.0, reason="po_failed")
        if not placed:
            logger.info("[2E] %s ladder OFF (ablation) — nunggu BREAK aja", tag)
        self._consume_budget(placed)

        self._p = {"tag": tag, "dir": d, "sl": sl, "inst": inst, "po": po,
                   "cpre": f"2E_{'B' if d == 'BUY' else 'S'}_{tag}",
                   "tickets": [], "inst_fired": False, "created": now,
                   "h1": self._r(h1), "l1": self._r(l1), "buf": buf}
        self._save_state()
        logger.info("[2E] %s %s pola: %d LIMIT @%.2f-%.2f SL_ALL=%.2f break@%.2f",
                    tag, d, placed, po[0]["price"], po[-1]["price"], sl, inst)
        self._publish(price)
        return StrategyResult(signal=None, confidence=0.0, reason="pattern_new")

    # ── rawat pola: fill tracking + break entry + kill ─────────────────────
    def _manage(self, sym, price, closed, now):
        p = self._p
        d = p["dir"]

        # 1) PO filled? (ilang dr /orders -> cek positions)
        orders = self._pending_orders()
        if orders is not None and p["po"]:
            live_ids = {int(o.get("ticket", -1)) for o in orders}
            still = []
            for o in p["po"]:
                if int(o["ticket"]) not in live_ids:
                    p["tickets"].append(int(o["ticket"]))
                    logger.info("[2E] %s LIMIT #%d filled -> posisi (total %d)",
                                p["tag"], int(o["ticket"]), len(p["tickets"]))
                else:
                    still.append(o)
            p["po"] = still
            self._save_state()

        # 2) posisi live utk break (anti-stampede: None = network, skip)
        live = self._live_pos(sym)

        # 3) KILL: M5 close nembus extreme C1 = pola batal — [v1.2 SOP counter]
        #    close DI BAWAH Low C1 -> breakdown valid, momentum lanjut turun ->
        #    break itu sendiri = SL entry counter SELL (counter = mirror 2E normal).
        #    Counter TIDAK dieksekusi 2E — nunggu pattern opposite ke-deteksi fresh.
        #    Zona ladder udah dilewatin -> sisa PO dijamin dicabut (log kill nyebut
        #    "counter-confirmed").
        last_c = float(closed[-1]["close"])
        if d == "SELL" and last_c > p["h1"]:
            self._counter = {"dir": "BUY", "t": now}   # [v1.3] breakdown/bullout =
            logger.info("[2E] counter %s armed (SL = extreme c2 pola berikutnya)",
                        "BUY" if d == "SELL" else "SELL")
            return self._kill("close > High C1 — counter BUY confirmed (SL = High C2 baru)")
        if d == "BUY" and last_c < p["l1"]:
            self._counter = {"dir": "SELL", "t": now}
            logger.info("[2E] counter %s armed (SL = extreme c2 pola berikutnya)",
                        "SELL" if d == "BUY" else "BUY")
            return self._kill("close < Low C1 — counter SELL confirmed (SL = Low C2 baru)")
        # [catatan v1.2] zona-kill by-price DIHAPUS dari sini: break Entry 1 (level
        # C1±buf) selalu lebih dulu daripada zona C1±2buf — naruh kill ini di atas
        # break bikin pola mati sebelum Entry 1 sempet eksekusi (bug urutan).

        # 4) BREAK -> Entry 1 market (sekali per pola), ladder dicabut
        #    [v1.8 filter penetrasi Boskuh] CLOSE M5 harus di luar inst ± 0.3×ATR14
        #    — tick nyempil $0.6 = fakeout (bukti loss 3C P94400, rule yang sama).
        _trs = [float(c["high"]) - float(c["low"]) for c in closed[-15:]]
        _atr = (sum(_trs) / len(_trs)) if _trs else 0.0
        _pen = PEN_FRAC * _atr
        broke = (d == "SELL" and last_c < p["inst"] - _pen) or \
                (d == "BUY" and last_c > p["inst"] + _pen)
        if broke and not p["inst_fired"]:
            if p["po"]:
                for o in p["po"]:
                    self._delete_order(o["ticket"])
                logger.info("[2E] %s break -> %d ladder dicabut", p["tag"], len(p["po"]))
                p["po"] = []
            n_now = len(live) if live is not None else len(p["tickets"])
            if n_now >= MAX_POS:
                p["inst_fired"] = True
                self._save_state()
                return "max5"
            sl = p["sl"]
            tp = self._r(price - TP_R * (sl - price)) if d == "SELL" else \
                 self._r(price + TP_R * (price - sl))
            side = "sell" if d == "SELL" else "buy"
            # [v1.5b] retry on-the-spot: break = harga ngempyur, deviasi gateway
            # 30pt kadang kelewat. 3 attempt jeda 0.7s — menang di gelombang sama.
            okm = t = None; msg = ""
            for _try in range(3):
                okm, t, msg = self._place(sym, side, LOT, sl=sl, tp=tp,
                                          comment=p["cpre"] + "_X1")
                if okm:
                    break
                time.sleep(0.7)
            if okm:
                p["inst_fired"] = True   # [v1.5] flag HANYA kalau sukses — dulu
                #                      di-set sebelum cek: Entry1 kena Requote ->
                #                      pola mati tanpa instant entry (E88100 19:20)
                p["tickets"].append(int(t))
                self._consume_budget()
                logger.info("[2E] %s BREAK C1 @%.2f -> Entry1 #%s SL=%.2f TP=%.2f",
                            p["tag"], price, t, sl, tp)
            else:
                logger.warning("[2E] %s Entry1 GAGAL: %s", p["tag"], msg)
            self._save_state()
            return None

        # 5) selesai kalau semua PO habis & posisi udah diurus trailing
        if p["inst_fired"] and not p["po"]:
            n_now = len(live) if live is not None else len(p["tickets"])
            if n_now == 0:
                self._ghost = {"dir": d, "h1": p.get("h1"), "l1": p.get("l1"),
                               "tag": p["tag"], "t": now}   # [v1.8.1]
                logger.info("[2E] %s GHOST 15mnt — close fatal luar C1 masih arm counter",
                            p["tag"])
                return self._kill("semua posisi close")
        return None

    def _kill(self, why):
        p = self._p
        logger.info("[2E] %s MATI (%s) | %d tickets tercatat, %d PO tersisa",
                    p["tag"], why, len(p["tickets"]), len(p["po"]))
        for o in p["po"]:
            self._delete_order(o["ticket"])
        self._p = None
        self._save_state()
        self._publish(price=None)
        return "killed"

    # ── deck feed (mirror /tmp/tie_3ca_mark.json shape-nya) ────────────────
    def _publish(self, price=None):
        """Snapshot state 2E utk deck TUIUL: fase, ladder PO, SL all, break."""
        try:
            p = self._p or {}
            json.dump({
                "ts": datetime.now(timezone.utc).isoformat(),
                "phase": "PATTERN" if p else "WATCH",
                "pattern": p.get("tag", ""), "dir": p.get("dir", ""),
                "po_prices": [o["price"] for o in p.get("po", [])],
                "po_count": len(p.get("po", [])),
                "ladder_on": LADDER_ON, "ladder_max": 4,
                "sl_all": p.get("sl"), "break_level": p.get("inst"),
                "h1": p.get("h1"), "l1": p.get("l1"), "buf": p.get("buf"),
                "positions": len(p.get("tickets", [])), "max_pos": MAX_POS,
                "inst_fired": bool(p.get("inst_fired")),
                "price": price,
            }, open("/tmp/tie_two_e_mark.json", "w"))
        except Exception:
            pass
