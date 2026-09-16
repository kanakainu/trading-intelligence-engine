"""ThreeCa v2.0 — 3-Candle SOP Boskuh (final spec 13-Sep-2026, sesi refine).

Arsitektur: DIRECT EXECUTOR. Strategi pegang own order lifecycle (PO limit,
pyramiding market, cancel) lewat MT5GatewayClient — TIDAK lewat fusion/planner/
gate EA-parity RiriScalps ("jangan tabrakan sama gate logic lama", 13-Sep).
Global safety di-inject runtime: halt flag, DD guard, governor, budget.

SOP (ringkas — detail di dokumen Boskuh):
  pola   C3 besar → C2 kecil → C1 besar, searah; C2<=60% tetangga & <0.40 ATR;
         High C2<=High C1 (bull)/Low C2>=Low C1 (bear); EMA9/21 M5 searah
         (close C1+C2); sideways reject (5 candle di pita EMA); M15 = flag.
  PO     BUY LIMIT @ High C2+buf / SELL LIMIT @ Low C2-buf; SL = ekstrem C3∓buf;
         buf = 2x spread (freeze saat order dipasang).
  valid  gak ada M5 close < LOW C2 (buy) / > HIGH C2 (sell).
  batal  close nembus C2 -> PO dicabut -> pola baru boleh opposite.
  fatal  close di luar C3 -> entry opposite diperkuat.
  instant harga tembus HIGH C1+buf (buy)/LOW C1-buf (sell) -> PO dihapus,
         SL = LOW C2 - buf (buy)/HIGH C2 + buf (sell); +1 (M5) / +2 (M5+M15);
         jatah kumulatif 5 posisi/pola (lot 0.01, @0.05 penuh).
  retest PO kejepit -> SL C3 (trailing three_ca yang megang).
  exit   manual_trailing_v2 profile three_ca: start $1 -> lock $1, lock 50% peak,
         TP jaring 3.5R.
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

from detectors.three_candle_detector import ThreeCandleDetector

logger = logging.getLogger("ThreeCa")

LOT = 0.01                # per posisi — 5 posisi = 0.05 (spek Boskuh)
MAX_POS_PER_PATTERN = 5
TP_R = 3.5                # jaring; exit asli = trailing three_ca
CHASE_LIMIT = 8.0         # $ menjauh dr ref sejak break pertama = ngejar, skip
HALT_FLAG = "/tmp/tie_halt"

# ── ablation knobs (backtest only; default = SOP live persis) ──
PEN_FRAC = float(os.environ.get("TIE_PEN_FRAC", "0.3"))
GHOST_ON = os.environ.get("TIE_GHOST", "1") == "1"
FOOT_SL = os.environ.get("TIE_FOOT_SL", "1") == "1"
HOLD_OK = os.environ.get("TIE_HOLD", "1") == "1"
STATE_VERSION = 3         # bump = reset state bawaan versi lama


def _noop():
    return None


class ThreeCaStrategy(BaseStrategy):
    """3C compression per SOP Boskuh 13-Sep — PO + pyramiding + direct executor."""

    def __init__(self):
        meta = StrategyMetadata(
            id="three_ca_v2",
            name="ThreeCa",
            version="2.9.4",
            priority=85,
            author="Boskuh+Sasa",
            description="3C SOP: PO limit @C2 (buf 2xspread), SL C3; instant break C1 "
                        "SL C2; pyramid max 5/pola (M5+M15=2/momen); trailing v2"
        )
        super().__init__(meta)
        self._detector = ThreeCandleDetector()
        self._p = None
        self._last_pattern = None
        self._gate = None
        self._gw = None
        self._gw_ok = None
        self._gw_probe_t = 0.0
        self._spread_cached = 0.20
        self._digits = 2
        self._last_positions = []   # cache dari runtime (hemat call)
        self._counter = None          # [v2.5] counter armed setelah kill FATAL luar C3
        self._ghost = None            # [v2.9.3] pola pensiun-due-close: memo gate3

    # ── wiring (runtime manggil ini) ──────────────────────────────────────
    def set_broker(self, client):        # MT5GatewayClient
        self._gw = client

    def set_safety_gates(self, gates: dict):
        """{'dd_ok_fn','gov','budget'} — global safety warisan (semua opsional)."""
        self._gate = gates

    def set_positions_cache(self, positions: list):
        self._last_positions = positions or []

    def initialize(self) -> None:
        self._initialized = True
        self._load_state()

    def observe(self, context: StrategyContext) -> None:
        pass

    def shutdown(self) -> None:
        self._initialized = False

    # ── persistence (restart-proof) ───────────────────────────────────────
    @property
    def _state_path(self):
        # test boleh redirect (TIE_3CA_STATE) biar gak nyemar state produksi
        return os.environ.get("TIE_3CA_STATE") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".three_ca_state.json")

    def _save_state(self):
        try:
            json.dump({"version": STATE_VERSION, "pattern": self._p,
                       "last_pattern": self._last_pattern,
                       "ghost": self._ghost},
                      open(self._state_path, "w"))
        except Exception as e:
            logger.warning("[3Ca] state save gagal: %s", e)

    def _load_state(self):
        try:
            d = json.load(open(self._state_path))
            if d.get("version") != STATE_VERSION:
                logger.info("[3Ca] versi state beda (v%s) — reset", d.get("version"))
                return
            self._p = d.get("pattern")
            self._last_pattern = d.get("last_pattern")
            self._ghost = d.get("ghost")
            if self._p:
                logger.info("[3Ca] RECOVER %s dir=%s tickets=%s po=%s",
                            self._p.get("tag"), self._p.get("dir"),
                            self._p.get("tickets"), self._p.get("po_ticket"))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("[3Ca] state load gagal: %s", e)

    # ── broker helpers ────────────────────────────────────────────────────
    def _spread(self, sym):
        """spread dalem $ harga. Exness XAU: info.spread = point (1 point=0.001)
        ATAU via tick ask-bid — pake tick, lebih akurat."""
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
        """-> (ok, ticket, msg). price != None => LIMIT, else market."""
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

    def _cancel_po(self):
        t = (self._p or {}).get("po_ticket")
        if not t:
            return
        try:
            self._gw._post(f"/trade/delete/{int(t)}")
            logger.info("[3Ca] PO %s dicabut", t)
        except Exception as e:
            logger.info("[3Ca] PO %s dicabut (mungkin udah kefill): %s", t, str(e)[:50])
        self._p["po_ticket"] = None

    def _pending_orders(self):
        try:
            return self._gw._get("/trade/orders") or []
        except Exception:
            return None   # None = network error, jangan spekulasi

    @staticmethod
    def _p_cpre(tag, d):
        return f"3C_{'B' if d == 'BUY' else 'S'}_{tag}"

    def _live_pos(self, sym):
        """posisi live pola aktif (query langsung — hemat, pola hidup cuma 1)."""
        try:
            src = self._gw._get("/account/positions") or []
        except Exception:
            return []
        prefix = self._p.get("cpre", f"TIE_T_{self._p['tag']}") if self._p else "TIE_T_"
        return [p for p in src
                if str(p.get("symbol", "")).upper().startswith(sym.upper())
                and str(p.get("comment", "")).startswith(prefix)]

    # ── safety global (diinjeksi runtime; fail-open per komponen) ─────────
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
        g = (self._gate or {}).get("budget")
        if not g:
            return
        for _ in range(n):
            try:
                g.consume("three_ca")
            except Exception:
                break

    # ── siklus utama (runtime manggil tiap scan ~10 dtk) ──────────────────
    def analyze(self, context: StrategyContext) -> StrategyResult:
        if self._gw is None:
            return StrategyResult(signal=None, confidence=0.0, reason="no_broker")

        # [GUARD gw-versi] PO butuh /trade/orders + order_type limit di gateway.
        # Gateway lama diamin-amin limit => jadi MARKET = bencana. Probe 1x/5mnt.
        if self._gw_ok is None or time.time() - self._gw_probe_t > 300:
            self._gw_probe_t = time.time()
            try:
                self._gw._get("/trade/orders")
                self._gw_ok = True
            except Exception:
                if self._gw_ok is not False:
                    logger.warning("[3Ca] GATEWAY LAMA: /trade/orders gak ada — 3Ca "
                                   "DIBEKUKIN sampai Windows pake server baru (limit)")
                self._gw_ok = False
        if not self._gw_ok:
            return StrategyResult(signal=None, confidence=0.0, reason="gateway_old")

        mc = context.scan.market
        sym = mc.symbol
        now = time.time()
        price = mc.price or 0.0
        m5 = (mc.metadata.get("candles") or {}).get("M5", [])
        if len(m5) < 5 or price <= 0:
            return StrategyResult(signal=None, confidence=0.0, reason="no_data")

        closed = m5[:-1]          # M5 closed (bar forming dibuang)
        c1_t = int(closed[-1].get("time", 0) or 0)

        # heartbeat deck (state cycle terakhir — cukup utk panel 3C)
        self._publish(mc, price)

        # [v2.9.3] GHOST: pola pensiun due-close (korban wick) <=15mnt lalu
        # close fatal luar gate3 => tetap arm counter. Jalan cuma saat no-pattern.
        if self._ghost and not self._p and GHOST_ON:
            g = self._ghost
            if now - g["t"] > 900 or (closed and int(closed[-1]["time"]) <= g["t"]):
                if now - g["t"] > 900:
                    self._ghost = None
            else:
                _c = closed[-1]
                _cc = float(_c["close"])
                _fatal = _cc < g["gate3"] if g["dir"] == "BUY" else _cc > g["gate3"]
                if _fatal:
                    self._counter = {"dir": "BUY" if g["dir"] == "SELL" else "SELL", "t": now}
                    logger.info("[3Ca] counter %s armed dari GHOST %s — close fatal luar C3 %.2f",
                                self._counter["dir"], g["tag"], g["gate3"])
                    self._ghost = None
                    self._save_state()
                elif int(_c["time"]) > g["t"] + 3 * 300:
                    self._ghost = None  # 3 candle lewat tanpa fatal = bener2 kelar

        # ── fase 0: pola hidup -> rawat; SATU pola aktif, deteksi baru noleh ──
        if self._p:
            why = self._manage_pattern(sym, price, closed, c1_t, now)
            return StrategyResult(signal=None, confidence=0.0, reason=why or "pattern_alive")

        # ── fase 1: deteksi pola baru ──
        ok, why = self._allowed_global(now, "three_ca")
        if not ok:
            return StrategyResult(signal=None, confidence=0.0, reason=f"global:{why}")

        facts = self._detector.detect(mc)
        if not facts:
            return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")
        md = facts[0].metadata
        tag = md["pattern_tag"]
        if tag == self._last_pattern:
            return StrategyResult(signal=None, confidence=0.0, reason="pattern_seen")
        self._last_pattern = tag

        d = md["direction"]
        c1, c2, c3 = md["c1"], md["c2"], md["c3"]
        spr = self._spread(sym)
        buf = round(max(2 * spr, 0.01) + 0.01, 2)   # 2x spread + margin, min $0.02
        h1, l1 = float(c1["high"]), float(c1["low"])
        h2, l2 = float(c2["high"]), float(c2["low"])
        h3, l3 = float(c3["high"]), float(c3["low"])

        # [v2.5 SOP counter Boskuh] pola PERTAMA searah counter dlm 30 mnt:
        # SL PO = extreme C2 (bukan C3) — tembok retrace paling deket.
        cnt = getattr(self, "_counter", None)
        cnt_mode = bool(cnt and cnt["dir"] == d and (now - cnt["t"]) < 1800)

        # [v2.9.2 kaki pola] tembok SL = wick TERDALAM dari C1+C2+C3 (P78400:
        # sumbu C1 nyapu stop persis di bawah Low C3). sl_wall dipakai PO & entry.
        if d == "BUY":
            po_price = self._r(h2 + buf)
            po_sl = (self._r(min(l1, l2) - buf) if cnt_mode
                     else self._r(min(l1, l2, l3) - buf if FOOT_SL else l3 - buf))
            inst_lvl = self._r(h1 + buf)
            gate2, gate3 = self._r(l2), self._r(l3)
        else:
            po_price = self._r(l2 - buf)
            po_sl = (self._r(max(h1, h2) + buf) if cnt_mode
                     else self._r(max(h1, h2, h3) + buf if FOOT_SL else h3 + buf))
            inst_lvl = self._r(l1 - buf)
            gate2, gate3 = self._r(h2), self._r(h3)
        if cnt_mode:
            self._counter = None
            logger.info("[3Ca] %s COUNTER %s -> SL PO = extreme C2 %.2f", tag, d, po_sl)

        # [v2.8 Boskuh: NO-SKIP + SL STRUKTURAL] tembok C3 dipegang AJAIB sampai
        # batas gila 2.5x ATR (dulu cap $5/$8 + anchor 1.2 -> SL mepet noise).
        risk_po = abs(po_price - po_sl)
        atr_det = float(md.get("atr") or 0.0)
        if atr_det > 0 and risk_po > 2.5 * atr_det:
            po_sl = (self._r(po_price - 2.5 * atr_det) if d == "BUY"
                     else self._r(po_price + 2.5 * atr_det))
            risk_po = abs(po_price - po_sl)
            logger.info("[3Ca] %s %s PO SL gila->anchor 2.5ATR: sl=%.2f risk=$%.2f",
                        tag, d, po_sl, risk_po)

        side = "buy" if d == "BUY" else "sell"
        okp, ticket, msg = self._place(sym, side, LOT, price=po_price,
                                       sl=po_sl, comment=self._p_cpre(tag, d) + "_PO")
        if not okp:
            logger.warning("[3Ca] %s PO GAGAL pasang: %s", tag, msg)
            return StrategyResult(signal=None, confidence=0.0, reason=f"po_fail:{msg}")

        self._p = {
            "tag": tag, "dir": d, "buf": buf, "atr": atr_det,
            "cpre": f"3C_{'B' if d == 'BUY' else 'S'}_{tag}",  # [v2.6 comment simple]
            "po_price": po_price, "po_sl": po_sl, "po_ticket": int(ticket),
            "inst_lvl": inst_lvl, "gate2": gate2, "gate3": gate3,
            "sl_wall": po_sl,
            "tickets": [], "m15": bool(md.get("trend_m15")),
            "c1_t": c1_t, "created": now,
            "brk_ref": 0.0, "brk_t": 0.0, "orders_checked": 0.0,
            "brk_done": False,  # [v2.7] break dieksekusi sekali/pola
            "g2b": 0,  # [v2.9] ts close nembus C2 (warning, nunggu hold)
        }
        self._consume_budget()
        self._save_state()
        logger.info("[3Ca] %s %s PO#%s @%.2f SL=%.2f buf=%.2f | break@%.2f gate2=%.2f "
                    "(M15 %s, risk $%.2f)", tag, d, ticket, po_price, po_sl, buf,
                    inst_lvl, gate2, "KUAT" if self._p["m15"] else "lemah", risk_po)
        self._mark_dashboard("armed", d, po_price, price)
        return StrategyResult(signal=None, confidence=0.0, reason=f"3ca_po:{po_price:.2f}")

    # ── mesin negara: pola hidup ──────────────────────────────────────────
    def _manage_pattern(self, sym, price, closed, c1_t, now):
        """None = lanjut; str = pola mati / alasan skip cycle ini."""
        p = self._p
        d, tag = p["dir"], p["tag"]

        # 1) deteksi PO tereksekusi: order ilang dr /orders -> tanya positions.
        #    Ada di positions = FILLED (SL C3 warisan broker). Gak ada dua2nya = reject.
        if p.get("po_ticket") and (now - p.get("orders_checked", 0)) >= 5:
            p["orders_checked"] = now
            orders = self._pending_orders()
            if orders is not None:
                still = any(int(o.get("ticket", 0)) == int(p["po_ticket"]) for o in orders)
                if not still:
                    pos = self._gw._get("/account/positions") or []
                    filled = any(int(x.get("ticket", 0)) == int(p["po_ticket"]) for x in pos)
                    self._last_positions = pos
                    if filled:
                        p["tickets"].append(int(p["po_ticket"]))
                        logger.info("[3Ca] %s PO HIT -> #%s live (SL C3=%.2f, trailing "
                                    "tiga_ca yang megang) [%d/5]", tag, p["po_ticket"],
                                    p["po_sl"], len(p["tickets"]))
                    else:
                        logger.info("[3Ca] %s PO#%s reject/expired — dilupakan",
                                    tag, p["po_ticket"])
                    p["po_ticket"] = None
                    self._save_state()

        # 2) evaluasi M5 closed baru: validasi gerbang C2 / fatal C3
        for c in [x for x in closed if int(x.get("time", 0) or 0) > p["c1_t"]]:
            cc = float(c["close"])
            p["c1_t"] = int(c.get("time", 0) or 0)
            broke2 = cc < p["gate2"] if d == "BUY" else cc > p["gate2"]
            # [v2.9 CLOSE-or-HOLD Boskuh] body close nembus C2 (non-fatal) dulu cuma
            # WARNING; MATI cuma kalau close BERIKUTNYA masih di luar C2 (hold).
            # Close tarik balik ke dalam = false alarm, pola lanjut normal.
            # Fatal luar C3 tetap langsung mati + arm counter (v2.5 gak berubah).
            fatal = cc < p["gate3"] if d == "BUY" else cc > p["gate3"]
            if fatal:
                self._counter = {"dir": "BUY" if d == "SELL" else "SELL", "t": now}
                logger.info("[3Ca] counter %s armed — close fatal luar C3 (SL counter = C2)",
                            self._counter["dir"])
                self._kill_pattern(sym, f"close FATAL luar C3 @{'<' if d=='BUY' else '>'}"
                                   f"{p['gate3']:.2f}", price)
                return f"3ca_invalid:{tag}_fatal"
            if broke2:
                if p.get("g2b") or not HOLD_OK:
                    self._kill_pattern(sym, f"HOLD {int((int(c.get('time',0))-p['g2b'])/60)}m "
                                            f"close di luar C2 {'<LOW' if d=='BUY' else '>HIGH'}", price)
                    return f"3ca_invalid:{tag}_hold"
                p["g2b"] = int(c.get("time", 0) or 0)
                logger.info("[3Ca] %s WARNING close nembus C2 @%.2f — nunggu hold candle berikut",
                            tag, cc)
                self._save_state()
            elif p.get("g2b"):
                logger.info("[3Ca] %s false alarm — close balik dalem C2, pola lanjut", tag)
                p["g2b"] = 0
                self._save_state()
        self._save_state()

        # [v2.4 REAPER HANTU] jatah SOP abis + PO gak ada + semua posisi pola udah keluar
        # -> pola dipensiunkan. Tanpa ini deck nempel "PATTERN" selamanya walau trade
        # bubar semua (bukti P68300: 12 tiket, 0 live, phase masih PATTERN).
        # Konfirmasi 2 cycle beruntun — query posisi bisa ngawur balik [] pas network glitch.
        # [v2.9.1 fix zombie 15-Sep] dulu reaper hanya jalan kalau JATAH ABIS (>=5) —
        # P50200: 2 ticket, semua posisi udah close, PO engga ada, gate gak pernah
        # ke-hold -> pola nempel "SELL" selamanya & BLOKIR deteksi pola baru.
        # Reaper sekarang: ticket ada + PO mati + 0 live (2x confirm) = PENSIUN,
        # mau jatah 2 apa 5.
        if p.get("tickets") and not p.get("po_ticket"):
            try:
                src = self._gw._get("/account/positions") or []
                any_live = any(str(x.get("comment", "")).startswith(f"3C_") and tag in str(x.get("comment", "")) for x in src)
            except Exception:
                any_live = True
            if any_live:
                p["empty_n"] = 0
            else:
                p["empty_n"] = p.get("empty_n", 0) + 1
                if p["empty_n"] >= 2:
                    # [v2.9.3] ghost: SL disapu wick, pola pensiun DULUAN — tapi
                    # close fatal luar C3 yang dateng 1-3 candle kemudian tetap
                    # sah nge-arm counter. Memo gate3 sebelum dibersihin.
                    self._ghost = ({"dir": p["dir"], "gate3": p["gate3"],
                                   "tag": p["tag"], "t": now} if GHOST_ON else None)
                    logger.info("[3Ca] %s GHOST 15mnt — close fatal luar %.2f masih arm counter",
                                p["tag"], p["gate3"])
                    self._kill_pattern(sym, "semua posisi close, PO mati — pola pensiun", price)
                    return f"3ca_done:{tag}"
        # [v2.6 filter penetrasi Boskuh] break = CLOSE M5 di luar inst_lvl minus
        # 0.3×ATR — bukan tick nyempil. Bukt: P94400 break $0.6 doang -> fakeout V.
        last_c = float(closed[-1]["close"]) if closed else 0.0
        pen = PEN_FRAC * float(p.get("atr") or 0.0)
        broke = (last_c > p["inst_lvl"] + pen) if d == "BUY" \
            else (last_c < p["inst_lvl"] - pen)
        if not broke:
            return None
        # [v2.7 EDGE-TRIGGER Boskuh fix 15-Sep] P43900: break di-fire ULANG tiap 15 detik
        # selama close masih di luar level -> jatah 5 habis dalam 66 detik, semua SL bareng.
        # Break = SATU MOMEN per pola (mirror EA: cuma jalan saat PO masih ada).
        if p.get("brk_done"):
            return "break_done"

        live = self._live_pos(sym)
        # [v2.2 ANTI-STAMPEDE] query posisi ke-gateway bisa balik [] pas network error/requote —
        # guard max5 jadi bolong, strategi nembak 22x berturut-turut (bukti log 14-Sep 10:29-10:41).
        # Fallback: kalau live kosong padahal tickets tercatat, pakai hitungan tickets.
        n_live = len(live)
        if n_live == 0 and p.get("tickets"):
            n_live = len(p["tickets"])
        # [v2.3 SOP Boskuh] jatah = KUMULATIF 5/pola, bukan concurrent. Ticket nabung terus
        # walau posisi udah di-close trailing — jangan bisa entry ke-6 dst (bukti P68300: 12 tiket).
        if len(p.get("tickets", [])) >= MAX_POS_PER_PATTERN:
            return "max5"
        if n_live >= MAX_POS_PER_PATTERN:
            return "max5"
        ok, why = self._allowed_global(now, "three_ca")
        if not ok:
            return f"global:{why}"

        # anti-chase: break udah keliatan, harga kabur >CHASE_LIMIT$ -> jangan dikejar
        if p["brk_ref"]:
            gone = abs(price - p["brk_ref"])
            if gone > CHASE_LIMIT:
                self._kill_pattern(sym, f"chase ${gone:.1f}>${CHASE_LIMIT}", price)
                return "chase"
        else:
            p["brk_ref"], p["brk_t"] = price, now

        # aturan SOP: entry instant => PO dihapus
        if p.get("po_ticket"):
            self._cancel_po()

        quota = 2 if p["m15"] else 1
        quota = min(quota, MAX_POS_PER_PATTERN - n_live)
        if quota <= 0:
            return "max5"
        # [v2.9.2] market-entry pakai tembok KAKI POLA yang sama dgn PO (dulu C2).
        _wall = p.get("sl_wall") if FOOT_SL else None
        if _wall is None:  # pola lahir sebelum v2.9.2 (state lama) -> fallback C2
            _wall = (self._r(p["gate2"] - p["buf"]) if d == "BUY"
                     else self._r(p["gate2"] + p["buf"]))
        sl_i = _wall
        risk_i = abs(price - sl_i)
        # [v2.8 SL STRUKTURAL Boskuh 15-Sep] anchor 1.2x ATR DIKETATIN: dulu SL
        # tembok C2 selalu dipencet kalau > 1.2 ATR -> hasilnya duduk DI BAWAH
        # C2 (P43900: SL 4307.9 vs spike 4308.13, struktur utuh tapi 2 SL).
        # Sekarang: tembok C2 valid SELAMA <= 2.5x ATR; anchor cuma buat yang
        # kejauhan gila (> 2.5 ATR, harga udah terbang jauh dari pola).
        atr_now = 0.0
        try:
            trs = []
            for k in range(max(1, len(closed) - 14), len(closed)):
                ck, pk = closed[k], closed[k - 1]
                trs.append(max(float(ck["high"]) - float(ck["low"]),
                               abs(float(ck["high"]) - float(pk["close"])),
                               abs(float(ck["low"]) - float(pk["close"]))))
            atr_now = sum(trs) / len(trs) if trs else 0.0
        except Exception:
            pass
        if atr_now and atr_now > 0:
            floor_sl = atr_now * 2.5   # [v2.8] batas 'gila' — di bawah ini tembok C2 dipegang
            if risk_i > floor_sl:
                sl_i = self._r(price + floor_sl) if d == "SELL" else self._r(price - floor_sl)
                risk_i = abs(price - sl_i)
                logger.info("[3Ca] %s SL wide->anchor ATR: sl=%.2f risk=$%.2f", tag, sl_i, risk_i)
        if risk_i < 0.3:
            logger.info("[3Ca] %s break, risk entry $%.2f < $0.3 — skip", tag, risk_i)
            return "risk_out"
        tp_i = price + TP_R * risk_i * (1 if d == "BUY" else -1)
        side = "buy" if d == "BUY" else "sell"
        placed = 0
        for i in range(quota):
            okm, t, msg = self._place(sym, side, LOT, sl=sl_i, tp=tp_i,
                                      comment=self._p_cpre(tag, d) + f"_X{i}")
            if not okm:
                logger.warning("[3Ca] %s instant #%d GAGAL: %s", tag, i, msg)
                break
            p["tickets"].append(int(t))
            placed += 1
        p["brk_done"] = True  # [v2.7] seumur pola, gak ada break ke-2
        if placed:
            self._consume_budget(placed)
            logger.info("[3Ca] %s BREAK C1 @%.2f -> +%d posisi SL=%.2f TP=%.2f "
                        "(total %d/5, M15 %s)", tag, price, placed, sl_i, tp_i,
                        len(p["tickets"]), "KUAT" if p["m15"] else "lemah")
            self._save_state()
        return None

    def _kill_pattern(self, sym, why, price):
        """Pola mati: PO dicabut. Posisi yang udah jalan DIBIARKAN — trailing
        three_ca + SL masing2 yang ngurus (SOP Boskuh: exit urusan trailing)."""
        p = self._p
        logger.info("[3Ca] %s MATI (%s) @%.2f | %d posisi live diserahkeun trailing",
                    p["tag"], why, price, len(p["tickets"]))
        self._cancel_po()
        self._p = None
        self._save_state()
        self._mark_dashboard("dead", "", 0, price)

    def _mark_dashboard(self, status, d, lvl, price, extra=None):
        """State 3Ca utk dashboard (file; deck bacanya via /api/3ca)."""
        try:
            m = {"ts": datetime.now(timezone.utc).isoformat(), "status": status,
                 "dir": d, "level": lvl, "price": price,
                 "pattern": (self._p or {}).get("tag", "")}
            if extra:
                m.update(extra)
            json.dump(m, open(os.environ.get("TIE_3CA_MARK", "/tmp/tie_3ca_mark.json"), "w"))
        except Exception:
            pass

    def _publish(self, mc, price):
        """Snapshot state 3Ca utk deck: pattern, PO, jatah, level break, tren EMA."""
        try:
            p = self._p or {}
            em = self._ema_trend(mc)
            json.dump({
                "ts": datetime.now(timezone.utc).isoformat(),
                "phase": ("PATTERN" if p else ("FROZEN" if not getattr(self, "_gw_ok", True) else "WATCH")),
                "pattern": p.get("tag", ""), "dir": p.get("dir", ""),
                "po_price": p.get("po_price"), "po_sl": p.get("po_sl"),
                "po_active": bool(p.get("po_ticket")),
                "break_level": p.get("inst_lvl"), "gate2": p.get("gate2"),
                "positions": len(p.get("tickets", [])), "max_pos": MAX_POS_PER_PATTERN,
                "m15_kuat": p.get("m15", False), "buf": p.get("buf"),
                "price": price, **em,
            }, open(os.environ.get("TIE_3CA_MARK", "/tmp/tie_3ca_mark.json"), "w"))
        except Exception:
            pass

    def _ema_trend(self, mc):
        """Tren EMA9/21 M5 & M15 (close terakhir) — utk panel 3C deck."""
        out = {"m5_trend": "--", "m15_trend": "--"}
        try:
            for tf, key in (("M5", "m5_trend"), ("M15", "m15_trend")):
                cs = (mc.metadata.get("candles") or {}).get(tf, [])[:-1]
                if len(cs) < 22:
                    continue
                closes = [float(c.get("close", 0)) for c in cs]
                from detectors.three_candle_detector import ema_series
                e9, e21 = ema_series(closes, 9)[-1], ema_series(closes, 21)[-1]
                out[key] = "BULL" if closes[-1] > max(e9, e21) \
                    else "BEAR" if closes[-1] < min(e9, e21) else "MIX"
        except Exception:
            pass
        return out
