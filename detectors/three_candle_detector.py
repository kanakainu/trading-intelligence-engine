"""ThreeCandleDetector — big-small-big compression (definisi Boskuh, 2026-09-07).

POLA: C3 BESAR → C2 KECIL → C1 BESAR, TIGA-TIGANYA SEARAH (bull semua / bear semua).
Kunci = C2 kecil:
  - body C2 <= 0.60 x body C3  DAN  body C2 <= 0.60 x body C1  (C3 & C1 lebih besar)
  - body C2 < 0.40 x ATR14     (pasti kecil secara absolut, bukan cuma relatif)
Arah = arah ketiga candle. SL = ekstrem C3. TP/exit urusan trailing v2 + strategy.

Replay 1000 bar M5 (2026-09-07): n=49, avg +$4.58, win 82% dengan trailing
lock $1 / trail $0.5. TP kaku JAUH lebih buruk -> jangan pake TP jauh.
"""
from typing import Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import is_bullish, is_bearish, body_size

C2_RATIO = 0.60     # C2 body <= 60% dari body C3 dan C1 (C3/C1 harus lebih besar)
C2_ATR_MAX = 0.40   # C2 body < 40% ATR14 — kunci "kecil" absolut


class ThreeCandleDetector(BystraBaseDetector):
    """big(C3) - small(C2) - big(C1), all same direction."""

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        if tf != "M5":
            return []

        candles = self._get_candles(context, tf, 30)
        if len(candles) < 17:  # 14 ATR + 3 pola + 1 forming
            return []

        closed = candles[:-1]  # buang bar forming
        facts = []
        # HANYA bar closed terakhir: sinyal fresh di candle yang baru selesai
        i = len(closed) - 1
        if i < 15:
            return []
        c3, c2, c1 = closed[i-2], closed[i-1], closed[i]

        b3, b2, b1 = body_size(c3), body_size(c2), body_size(c1)
        if b2 <= 0 or b3 <= 0 or b1 <= 0:
            return []

        # KUNCI: C2 kecil vs kedua tetangga (C3 & C1 lebih besar dari C2)
        if not (b2 <= C2_RATIO * b3 and b2 <= C2_RATIO * b1):
            return []
        # dan kecil absolut terhadap volatilitas pasar
        atr = sum(abs(float(x["high"]) - float(x["low"])) for x in closed[i-14:i]) / 14
        if atr <= 0 or b2 >= C2_ATR_MAX * atr:
            return []

        # TIGA-TIGANYA SERAGAM searah
        if is_bullish(c3) and is_bullish(c2) and is_bullish(c1):
            direction = "BUY"
            sl = float(c3["low"])
        elif is_bearish(c3) and is_bearish(c2) and is_bearish(c1):
            direction = "SELL"
            sl = float(c3["high"])
        else:
            return []

        facts.append(self._create_pattern_fact("THREE_CANDLE", 0.85, {
            "direction": direction,
            "c1": c1, "c2": c2, "c3": c3,
            "sl": sl,
            "cutloss": sl,
            "atr": atr,
        }))
        return facts
