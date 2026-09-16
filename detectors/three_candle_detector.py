"""ThreeCandleDetector v2 — 3-Candle SOP Boskuh (13-Sep-2026, final spec).

POLA: C3 besar → C2 kecil → C1 besar; TIGA-TIGANYA SEARAH.
  C3 = candle terjauh, C2 = tengah, C1 = terdekat dengan harga sekarang.

Rule v2 (SOP Boskuh):
  - C2 lebih kecil dari C1 dan C3 (body <= 60% tetangga & < 0.40 ATR)
  - Bullish: High C2 TIDAK BOLEH > High C1 | Bearish: Low C2 TIDAK BOLEH < Low C1
  - Trend M5 wajib searah: close C1 & C2 di atas EMA9 & EMA21 (bull) / di bawah (bear)
  - Sideways = 5 candle sebelum C1 close bolak-balik di antara pita EMA9/EMA21 → TOLAK
  - Flag M15 (EMA9/21): bukan syarat entry, penentu multiplier posisi (2 vs 1)

Return metadata lengkap per pola: c1/c2/c3 (dict utuh), direction, sl (ekstrem C3),
trend_m5, trend_m15, atr14.
"""
import os
from typing import Any, Dict, List

from detectors.base_detector import BystraBaseDetector
from detectors.common import is_bullish, is_bearish, body_size

C2_RATIO = 0.60     # body C2 <= 60% body tetangga
C2_ATR_MAX = 0.40   # body C2 < 40% ATR14 — "kecil" absolut
CHOP_WINDOW = 5     # 5 candle sebelum deteksi: pita EMA = jebakan sideways


def _align_ok(e9, e21, is_buy):
    # [SOP-16B] alignment EMA9 vs EMA21 wajib searah (knob ablation: TIE_EMA_ALIGN=off)
    if os.environ.get("TIE_EMA_ALIGN", "on") == "off":
        return True
    return e9 > e21 if is_buy else e9 < e21


def ema_series(closes: List[float], period: int) -> List[float]:
    """EMA standar; hasil sepanjang input (dibangun dari seed SMA)."""
    if len(closes) < period:
        return []
    k = 2.0 / (period + 1)
    out = [sum(closes[:period]) / period]
    for c in closes[period:]:
        out.append(c * k + out[-1] * (1 - k))
    return out  # index i ↔ closes[period-1+i]


def _off(n: int, period: int) -> int:
    """offset EMA[i] ↔ closes[i + off] — konsisten untuk semua period."""
    return period - 1


def band_cross_chop(candles: List[Dict], e9: List[float], e21: List[float], n: int = CHOP_WINDOW) -> bool:
    """Sideways (SOP Boskuh 13-Sep): harga bolak-balik TEMBUS pita EMA9/21.
    Implementasi: dalam n candle terakhir, close berpindah sisi dari garis tengah
    pita (min+max)/2 sebanyak >=3 kali = jebakan chop, bukan trend."""
    closes = [float(c.get("close", 0)) for c in candles]
    if len(closes) < n or not e9 or not e21:
        return False
    k = min(len(e9), len(e21))
    sides = []
    for i in range(1, n + 1):
        mid = (e9[-i] + e21[-i]) / 2
        sides.append(1 if closes[-i] > mid else 0)
    flips = sum(1 for a, b in zip(sides, sides[1:]) if a != b)
    return flips >= 3  # bolak-balik >=3x dalam 5 candle = sideways


class ThreeCandleDetector(BystraBaseDetector):
    """3C big-small-big searah + SOP v2 filter. Detektor = murni pola + tren."""

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        if tf != "M5":
            return []

        candles = self._get_candles(context, tf, 60)
        if len(candles) < 25:  # 21 EMA + 5 chop window + 3 pola + forming
            return []

        closed = candles[:-1]  # buang bar forming
        c3, c2, c1 = closed[-3], closed[-2], closed[-1]
        b3, b2, b1 = body_size(c3), body_size(c2), body_size(c1)
        if b2 <= 0 or b3 <= 0 or b1 <= 0:
            return []

        # KUNCI: C2 kecil vs kedua tetangga
        if not (b2 <= C2_RATIO * b3 and b2 <= C2_RATIO * b1):
            return []
        atr = sum(abs(float(x["high"]) - float(x["low"])) for x in closed[-17:-3]) / 14
        if atr <= 0 or b2 >= C2_ATR_MAX * atr:
            return []

        # [SOP v2] struktur C2 vs C1
        h1, l1 = float(c1["high"]), float(c1["low"])
        h2, l2 = float(c2["high"]), float(c2["low"])

        if is_bullish(c3) and is_bullish(c2) and is_bullish(c1):
            direction, sl = "BUY", float(c3["low"])
            if h2 > h1:  # High C2 tak boleh di atas High C1
                return []
        elif is_bearish(c3) and is_bearish(c2) and is_bearish(c1):
            direction, sl = "SELL", float(c3["high"])
            if l2 < l1:  # Low C2 tak boleh di bawah Low C1
                return []
        else:
            return []

        # [SOP v2.9.4 Boskuh] tren M5: close C1 SAJA di luar pita EMA9/21
        # (dulu C1+C2 — C2 besar bikin pola valid kelewat; ukuran C2 dijaga gate lain)
        closes = [float(c.get("close", 0)) for c in closed]
        e9s, e21s = ema_series(closes, 9), ema_series(closes, 21)
        _mode = os.environ.get("TIE_EMA_MODE", "c1")
        if _mode == "off":
            trend_m5 = True
        elif _mode == "c1c2":
            trend_m5 = all(closes[-1 - i] > e9s[-1 - i] and closes[-1 - i] > e21s[-1 - i]
                           for i in range(2)) if direction == "BUY" else \
                all(closes[-1 - i] < e9s[-1 - i] and closes[-1 - i] < e21s[-1 - i]
                    for i in range(2))
        elif direction == "BUY":
            trend_m5 = closes[-1] > e9s[-1] and closes[-1] > e21s[-1] and _align_ok(e9s[-1], e21s[-1], True)
        else:
            trend_m5 = closes[-1] < e9s[-1] and closes[-1] < e21s[-1] and _align_ok(e9s[-1], e21s[-1], False)
        if not trend_m5:
            return []

        # [SOP v2] sideways reject: 5 candle sebelum pola main di pita EMA
        if band_cross_chop(closed[:-3], e9s[:-3], e21s[:-3]):
            return []

        # [SOP v2] M15 = penentu multiplier (1 vs 2 per momen break)
        trend_m15 = False
        m15 = (context.metadata.get("candles") or {}).get("M15", [])
        if len(m15) >= 23:
            c15 = [float(x.get("close", 0)) for x in m15[:-1]]
            f9, f21 = ema_series(c15, 9)[-1], ema_series(c15, 21)[-1]
            trend_m15 = c15[-1] > f9 and c15[-1] > f21 if direction == "BUY" \
                else c15[-1] < f9 and c15[-1] < f21

        facts = [self._create_pattern_fact("THREE_CANDLE", 0.85, {
            "direction": direction,
            "c1": c1, "c2": c2, "c3": c3,
            "sl": sl, "cutloss": sl, "atr": atr,
            "trend_m15": trend_m15,
            "pattern_tag": f"P{int(float(c1.get('time', 0)) or 0) % 100000}",
        })]
        return facts
