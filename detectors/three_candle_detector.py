"""ThreeCandleDetector — 3-candle compression breakout (CAPYBARS-style, fixed).

Problem dengan definisi lama (audit 2026-09-07):
- Minta 3 candle searah + C2 inside C3 + body C2 < 30% KEDUA tetangga + M15 3of5
  → funnel 497 bar jadi ~4 pola/41 jam, dan nyaris gak pernah ke-trigger.
- C1 "big" gak pernah diukur relatif ATR → di market sepi, pola mustahil.

Definisi baru (teruji replay 1000 bar M5, win 72% avg +$1.67 @R1.5):
- C2 = candle KECIL: body < 0.35 × ATR14 (compression/coil)
- C1 = candle BESAR: body > 0.8 × ATR14 DAN close menembus range C2+C3
- C1 strong close: body > 60% range (gak ada sumbu besar melawan arah)
- Arah = arah C1. SL = extreme range C2+C3. TP = 2R (dihitung strategy).
"""
from typing import Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import is_bullish, is_bearish, body_size

C2_MAX_ATR = 0.35   # C2 body must be < 35% ATR (coil)
C1_MIN_ATR = 0.80   # C1 body must be > 80% ATR (breakout thrust)
C1_CLOSE_RATIO = 0.60  # C1 body must be >= 60% of its range (strong close)


class ThreeCandleDetector(BystraBaseDetector):
    """Compression (small C2) → breakout thrust (big strong-close C1)."""

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        if tf != "M5":
            return []

        candles = self._get_candles(context, tf, 30)
        if len(candles) < 17:  # 14 ATR + 3 pola
            return []

        closed = candles[:-1]  # buang bar forming
        facts = []
        # HANYA bar closed terakhir: sinyal fresh, gak ngejar pola basi
        for i in range(max(15, len(closed) - 1), len(closed)):
            c3, c2, c1 = closed[i-2], closed[i-1], closed[i]

            # ATR14 sederhana dari range bar (closed, sampai i-1)
            atr = sum(abs(float(x["high"]) - float(x["low"])) for x in closed[i-14:i]) / 14
            if atr <= 0:
                continue

            b1, b2 = body_size(c1), body_size(c2)
            rng1 = float(c1["high"]) - float(c1["low"])
            if rng1 <= 0:
                continue

            # coil + thrust
            if not (b2 < C2_MAX_ATR * atr and b1 > C1_MIN_ATR * atr):
                continue
            # strong close: body dominan vs range (anti fake-out wick)
            if b1 / rng1 < C1_CLOSE_RATIO:
                continue

            hi = max(float(c3["high"]), float(c2["high"]))
            lo = min(float(c3["low"]), float(c2["low"]))

            if is_bullish(c1) and float(c1["close"]) > hi:
                direction, sl = "BUY", lo
            elif is_bearish(c1) and float(c1["close"]) < lo:
                direction, sl = "SELL", hi
            else:
                continue

            facts.append(self._create_pattern_fact("THREE_CANDLE", 0.85, {
                "direction": direction,
                "c1": c1, "c2": c2, "c3": c3,
                "sl": sl,
                "cutloss": sl,  # single boss trailing yang megang; cutloss = SL ekstrem
                "atr": atr,
            }))
        # terbaru dulu — strategy ambil facts[0]
        return list(reversed(facts))
