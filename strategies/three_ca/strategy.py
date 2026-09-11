"""
ThreeCa v1.2 — Big-Small-Big 3-Candle Compression (definisi Boskuh)
Pattern: C3 besar → C2 kecil (kunci) → C1 besar; 3 candle searah semua.
ARMED v1.3 (Boskuh 11-Sep): setelah 3-candle terdeteksi (C1 closed), JANGAN entry dulu —
tunggu candle ONGOING berikutnya menembus HIGH C1 (BUY) / LOW C1 (SELL). Tembus = konfirmasi
momentum, entry market. Tutup candle tanpa tembus = sinyal batal. SL tetap ekstrem C3.
"""
import uuid
import logging

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction

from detectors.three_candle_detector import ThreeCandleDetector

logger = logging.getLogger("ThreeCa")

BREAK_BUFFER = 0.03   # $越过 level C1 dianggap break (anti noise tick)
TP_R = 4.0  # TP lebar — exit sesungguhnya dipegang manual_trailing_v2 (lock $1/trail $0.5).
            # Replay: TP 2R avg -$1.23 vs trailing +$4.58. Jangan ketus TP dekat.


class ThreeCaStrategy(BaseStrategy):
    """3-Candle compression-breakout — standalone entry."""

    def __init__(self):
        meta = StrategyMetadata(
            id="three_ca_v1",
            name="ThreeCa",
            version="1.3.0",
            priority=85,
            author="Sasa",
            description="big-small-big 3 searah; entry HANYA setelah candle ongoing break high/low C1; SL C3; trailing v2"
        )
        super().__init__(meta)
        self._detector = ThreeCandleDetector()
        self._arm = None   # pola nunggu konfirmasi break C1: {dir, level, sl, ckey, risk_req}

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market
        sym = market_ctx.symbol
        price = market_ctx.price or (market_ctx.metadata.get("candles", {}).get("M5", [])[-1]["close"] if market_ctx.metadata.get("candles", {}).get("M5", []) else 0)

        m5 = (market_ctx.metadata.get("candles") or {}).get("M5", [])

        # ── [ARMED] evaluasi konfirmasi break dari candle ongoing ──
        if self._arm:
            lc_now = (m5[-2] if len(m5) >= 2 else (m5[-1] if m5 else None))
            key_now = f"{(lc_now or {}).get('time')}_{(lc_now or {}).get('close')}" if lc_now else None
            if key_now != self._arm["ckey"]:
                logger.info("[3Ca] ARM EXPIRED: candle konfirmasi tertutup tanpa break C1 — sinyal batal")
                self._arm = None
            else:
                is_buy = self._arm["dir"] == "BUY"
                lvl = self._arm["level"]
                brk = (price > lvl + BREAK_BUFFER) if is_buy else (price < lvl - BREAK_BUFFER)
                risk_now = abs(price - self._arm["sl"])
                if brk and risk_now <= 5.0 and risk_now > 0.5:
                    direction = Direction.BUY if is_buy else Direction.SELL
                    sl = self._arm["sl"]
                    tp = price + TP_R * risk_now * (1 if is_buy else -1)
                    self._arm = None
                    self._last_candle_key = key_now
                    logger.info(f"[3Ca] BREAK CONFIRMED {direction.name}: harga {price:.2f} tembus "
                                f"C1 {'high' if is_buy else 'low'} {lvl:.2f} → ENTRY. SL={sl:.2f} "
                                f"TP={tp:.2f} (risk=${risk_now:.2f})")
                    signal = Signal(
                        signal_id=str(uuid.uuid4()), strategy=self.id, symbol=sym,
                        direction=direction,
                        entry_zone={"price": price, "high": price+0.2, "low": price-0.2},
                        confidence=0.85, timeframe="M5",
                        metadata={"sl": sl, "take_profit": tp, "cutloss": sl,
                                  "setup_type": "3Ca", "strategy_code": "3Ca", "volume": 0.05})
                    return StrategyResult(signal=signal, confidence=0.85,
                                          reason="3Ca_break_confirm", metadata=signal.metadata)
                elif brk:
                    logger.info(f"[3Ca] break tapi risk ${risk_now:.2f} di luar jendela 0.5-5 — batal")
                    self._arm = None
                    return StrategyResult(signal=None, confidence=0.0, reason="3ca_break_too_far")
                else:
                    return StrategyResult(signal=None, confidence=0.0,
                                          reason=f"3ca_await_break:{lvl:.2f}")

        # Same-candle guard: satu sinyal per candle closed terakhir
        if m5:
            lc = m5[-2] if len(m5) >= 2 else m5[-1]
            _ckey = f"{lc.get('time') or lc.get('high',0)}_{lc.get('close',0)}"
            if _ckey == getattr(self, "_last_candle_key", None):
                return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")
        else:
            _ckey = None

        try:
            facts = self._detector.detect(market_ctx)
        except Exception as e:
            logger.warning("[3Ca] detector error: %s", e)
            return StrategyResult(signal=None, confidence=0.0, reason=f"detector_error:{e}")

        if not facts:
            return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")

        best = facts[0]  # terbaru (detector sudah urut baru→lama)
        md = best.metadata
        direction = Direction.BUY if md["direction"] == "BUY" else Direction.SELL
        sl = float(md["sl"])

        # [ARM v1.3] risiko dihitung PROSPEKTIF: entry ideal = saat harga tembus level C1(+buffer).
        risk = abs(price - sl)
        c1 = md["c1"]
        level = float(c1["high"]) if direction == Direction.BUY else float(c1["low"])
        _pros = abs((level + BREAK_BUFFER * (1 if direction == Direction.BUY else -1)) - sl)
        if _pros <= 0.5:  # SL nempel level break = noise, skip (biar R gak ngawur)
            return StrategyResult(signal=None, confidence=0.0, reason="risk_too_small")
        # [V-GATE 10-Sep] C3 terlalu lebar = pola liar (bukti: loss -8.93, risk $8.93 @0.01).
        # Kalau pun break terjadi, risk saat entry masih > $5 — pola segendut ini skip dari awal.
        if _pros > 5.0:
            logger.info(f"[3Ca] {direction.name} DIBLOCK: prospektif risk ${_pros:.2f} > $5 (C3-C1 kegedean)")
            return StrategyResult(signal=None, confidence=0.0, reason=f"pattern_too_wide:{_pros:.2f}")
        if _ckey:
            self._last_candle_key = _ckey
        self._arm = {"dir": ("BUY" if direction == Direction.BUY else "SELL"),
                     "level": level, "sl": sl, "ckey": _ckey}
        logger.info(f"[3Ca] ARMED {direction.name}: pola C3-C2-C1 valid. Nunggu candle ongoing "
                    f"tembus C1 {'high' if direction == Direction.BUY else 'low'} {level:.2f} "
                    f"(SL ekstrem C3={sl:.2f}, risk awal ${risk:.2f}). Belum entry.")
        return StrategyResult(signal=None, confidence=0.0, reason=f"3ca_armed:{level:.2f}")

    def shutdown(self) -> None:
        self._initialized = False
