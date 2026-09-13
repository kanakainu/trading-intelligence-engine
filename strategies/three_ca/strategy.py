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
STATE_VERSION = 3         # bump = reset state bawaan versi lama


def _noop():
    return None


class ThreeCaStrategy(BaseStrategy):
    """3C compression per SOP Boskuh 13-Sep — PO + pyramiding + direct executor."""

    def __init__(self):
        meta = StrategyMetadata(
            id="three_ca_v2",
            name="ThreeCa",
            version="2.0.0",
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
        self._spread_cached = 0.20
        self._digits = 2
        self._last_positions = []   # cache dari runtime (hemat call)

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
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".three_ca_state.json")

    def _save_state(self):
        try:
            json.dump({"version": STATE_VERSION, "pattern": self._p,
                       "last_pattern": self._last_pattern},
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

    def _live_pos(self, sym):
        """posisi live pola aktif (query langsung — hemat, pola hidup cuma 1)."""
        try:
            src = self._gw._get("/account/positions") or []
        except Exception:
            return []
        prefix = f"TIE_T_{self._p['tag']}" if self._p else "TIE_T_"
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

        mc = context.scan.market
        sym = mc.symbol
        now = time.time()
        price = mc.price or 0.0
        m5 = (mc.metadata.get("candles") or {}).get("M5", [])
        if len(m5) < 5 or price <= 0:
            return StrategyResult(signal=None, confidence=0.0, reason="no_data")

        closed = m5[:-1]          # M5 closed (bar forming dibuang)
        c1_t = int(closed[-1].get("time", 0) or 0)

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

        if d == "BUY":
            po_price, po_sl = self._r(h2 + buf), self._r(l3 - buf)
            inst_lvl = self._r(h1 + buf)
            gate2, gate3 = self._r(l2), self._r(l3)
        else:
            po_price, po_sl = self._r(l2 - buf), self._r(h3 + buf)
            inst_lvl = self._r(l1 - buf)
            gate2, gate3 = self._r(h2), self._r(h3)

        # pola kegedean? limit $5; $8 kalau M5+M15 kompak (SOP no.2 Boskuh)
        risk_po = abs(po_price - po_sl)
        cap = 8.0 if md.get("trend_m15") else 5.0
        if risk_po > cap:
            logger.info("[3Ca] %s %s SKIP: risk PO $%.2f > $%.0f (M15 %s)",
                        tag, d, risk_po, cap, "ON" if md.get("trend_m15") else "off")
            return StrategyResult(signal=None, confidence=0.0, reason=f"too_wide:{risk_po:.2f}")

        side = "buy" if d == "BUY" else "sell"
        okp, ticket, msg = self._place(sym, side, LOT, price=po_price,
                                       sl=po_sl, comment=f"TIE_T_{tag}_PO")
        if not okp:
            logger.warning("[3Ca] %s PO GAGAL pasang: %s", tag, msg)
            return StrategyResult(signal=None, confidence=0.0, reason=f"po_fail:{msg}")

        self._p = {
            "tag": tag, "dir": d, "buf": buf,
            "po_price": po_price, "po_sl": po_sl, "po_ticket": int(ticket),
            "inst_lvl": inst_lvl, "gate2": gate2, "gate3": gate3,
            "tickets": [], "m15": bool(md.get("trend_m15")),
            "c1_t": c1_t, "created": now,
            "brk_ref": 0.0, "brk_t": 0.0, "orders_checked": 0.0,
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
            if broke2:
                fatal = cc < p["gate3"] if d == "BUY" else cc > p["gate3"]
                self._kill_pattern(sym, f"close {'<LOW C2' if d=='BUY' else '>HIGH C2'}"
                                   + (" (FATAL luar C3)" if fatal else ""), price)
                return f"3ca_invalid:{tag}" + ("_fatal" if fatal else "")
        self._save_state()

        # 3) trigger break C1 -> instant/pyramid
        broke = price > p["inst_lvl"] if d == "BUY" else price < p["inst_lvl"]
        if not broke:
            return None

        live = self._live_pos(sym)
        if len(live) >= MAX_POS_PER_PATTERN:
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
        quota = min(quota, MAX_POS_PER_PATTERN - len(live))
        sl_i = self._r(p["gate2"] - p["buf"]) if d == "BUY" else self._r(p["gate2"] + p["buf"])
        risk_i = abs(price - sl_i)
        if risk_i < 0.3 or risk_i > 9.5:
            logger.info("[3Ca] %s break, risk entry $%.2f di luar 0.3-9.5 — skip", tag, risk_i)
            return "risk_out"
        tp_i = price + TP_R * risk_i * (1 if d == "BUY" else -1)
        side = "buy" if d == "BUY" else "sell"
        placed = 0
        for i in range(quota):
            okm, t, msg = self._place(sym, side, LOT, sl=sl_i, tp=tp_i,
                                      comment=f"TIE_T_{tag}_X{i}")
            if not okm:
                logger.warning("[3Ca] %s instant #%d GAGAL: %s", tag, i, msg)
                break
            p["tickets"].append(int(t))
            placed += 1
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

    def _mark_dashboard(self, status, d, lvl, price):
        """SOP no.10: tandain warna candle / state di dashboard (file; endpoint
        menyusul kalau Boskuh mau tile khusus)."""
        try:
            json.dump({"ts": datetime.now(timezone.utc).isoformat(), "status": status,
                       "dir": d, "level": lvl, "price": price,
                       "pattern": (self._p or {}).get("tag", "")},
                      open("/tmp/tie_3ca_mark.json", "w"))
        except Exception:
            pass
