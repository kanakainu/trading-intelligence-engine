"""Feature Engine — Computes all indicators once per scan from raw candles."""
import math
from typing import Dict, List, Optional, Any
from collections import deque

from core.features.feature_models import FeatureSnapshot, FeatureInputs


class FeatureEngine:
    """
    Single source of truth for all computed features.
    - Computed ONCE per scan loop
    - Immutable output (FeatureSnapshot)
    - Detectors consume read-only
    """

    # EMA periods to compute
    EMA_PERIODS = [8, 9, 13, 21, 34, 50, 200]
    SLOPE_PERIODS = [21, 50]
    ATR_PERIOD = 14
    VOLUME_MA_PERIOD = 20

    def __init__(self):
        self._last_scan_id = 0

    def compute(self, inputs: FeatureInputs) -> FeatureSnapshot:
        """Compute all features from raw inputs. Called once per scan."""
        self._last_scan_id += 1
        scan_id = f"{inputs.symbol}_{self._last_scan_id}_{inputs.timestamp.timestamp() if inputs.timestamp else 0}"

        candles = inputs.candles or {}
        tf_list = ["M1", "M5", "M15", "H1"]

        # Compute all feature groups
        ema_data = self._compute_ema_all_tfs(candles, tf_list)
        ema_slope_data = self._compute_ema_slopes(ema_data, tf_list)
        atr_data = self._compute_atr_all_tfs(candles, tf_list)
        atr_pct_data = self._compute_atr_percent(atr_data, candles, tf_list)
        tr_data = self._compute_true_range(candles, tf_list)
        momentum_data = self._compute_momentum(candles, tf_list)
        volume_data = self._compute_volume(candles, tf_list)
        vwap_data = self._compute_vwap_all_tfs(candles, tf_list)
        vwap_dist_data = self._compute_vwap_distance(vwap_data, candles, tf_list)
        swing_data = self._compute_swings(candles, tf_list)
        sr_data = self._compute_nearest_sr(candles, tf_list)

        # Market microstructure
        spread = inputs.spread
        tick_speed, price_velocity = self._compute_microstructure(inputs.current_tick)
        current_price = float((inputs.current_tick or {}).get("bid", 0) or 0)

        return FeatureSnapshot(
            symbol=inputs.symbol,
            timestamp=inputs.timestamp or __import__("datetime").datetime.now(),
            scan_id=scan_id,
            ema=ema_data,
            ema_slope=ema_slope_data,
            atr=atr_data,
            atr_percent=atr_pct_data,
            true_range=tr_data,
            body_ratio=momentum_data["body_ratio"],
            wick_ratio=momentum_data["wick_ratio"],
            impulse_size=momentum_data["impulse_size"],
            momentum_score=momentum_data["momentum_score"],
            volume_ma=volume_data["volume_ma"],
            volume_ratio=volume_data["volume_ratio"],
            volume_spike=volume_data["volume_spike"],
            vwap=vwap_data,
            distance_to_vwap=vwap_dist_data,
            current_price=current_price,
            spread=spread,
            tick_speed=tick_speed,
            price_velocity=price_velocity,
            last_swing_high=swing_data["high"],
            last_swing_low=swing_data["low"],
            nearest_support=sr_data["support"],
            nearest_resistance=sr_data["resistance"],
            candles=candles,  # pass-through for raw access
        )

    def _compute_ema_all_tfs(self, candles: Dict[str, List[Dict]], tf_list: List[str]) -> Dict[str, Dict[str, float]]:
        """Compute EMAs for all periods across all timeframes."""
        result = {}
        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if not tf_candles:
                result[tf] = {}
                continue

            closes = [float(c["close"]) for c in tf_candles]
            result[tf] = {}
            for period in self.EMA_PERIODS:
                if len(closes) >= period:
                    result[tf][f"ema{period}"] = self._ema(closes, period)
                elif len(closes) >= period // 2:
                    # Compute with available data if at least half the period
                    result[tf][f"ema{period}"] = self._ema(closes, min(period, len(closes)))
        return result

    def _compute_ema_slopes(self, ema_data: Dict, tf_list: List[str]) -> Dict[str, Dict[str, float]]:
        """Compute EMA slopes (current - previous) / previous."""
        result = {}
        for tf in tf_list:
            result[tf] = {}
            for period in self.SLOPE_PERIODS:
                key = f"ema{period}"
                if key in ema_data.get(tf, {}):
                    # We need previous value — compute from full series or approximate
                    # For now, slope = (current - ema_prev) / ema_prev
                    # This is a simplified slope; detectors can compute their own if needed
                    result[tf][f"ema{period}_slope"] = 0.0  # placeholder
        return result

    def _compute_atr_all_tfs(self, candles: Dict[str, List[Dict]], tf_list: List[str]) -> Dict[str, float]:
        """Compute ATR(14) for each timeframe."""
        result = {}
        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if len(tf_candles) >= self.ATR_PERIOD + 1:
                result[tf] = self._atr(tf_candles, self.ATR_PERIOD)
        return result

    def _compute_atr_percent(self, atr_data: Dict, candles: Dict, tf_list: List[str]) -> Dict[str, float]:
        """ATR as percentage of price."""
        result = {}
        for tf in tf_list:
            atr = atr_data.get(tf)
            tf_candles = candles.get(tf, [])
            if atr and tf_candles:
                last_close = float(tf_candles[-1]["close"])
                if last_close > 0:
                    result[tf] = (atr / last_close) * 100
        return result

    def _compute_true_range(self, candles: Dict[str, List[Dict]], tf_list: List[str]) -> Dict[str, float]:
        """Current true range for each timeframe."""
        result = {}
        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if tf_candles:
                c = tf_candles[-1]
                prev_c = tf_candles[-2] if len(tf_candles) > 1 else c
                h, l = float(c["high"]), float(c["low"])
                pc = float(prev_c["close"])
                result[tf] = max(h - l, abs(h - pc), abs(l - pc))
        return result

    def _compute_momentum(self, candles: Dict[str, List[Dict]], tf_list: List[str]) -> Dict[str, Dict[str, float]]:
        """Body ratio, wick ratio, impulse size, momentum score."""
        body_ratio = {}
        wick_ratio = {}
        impulse_size = {}
        momentum_score = {}

        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if not tf_candles:
                continue

            c = tf_candles[-1]
            o, h, l, c_price = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])

            body = abs(c_price - o)
            upper_wick = h - max(c_price, o)
            lower_wick = min(c_price, o) - l
            total_range = h - l if h != l else 1e-10

            body_ratio[tf] = body / total_range
            wick_ratio[tf] = (upper_wick + lower_wick) / total_range
            impulse_size[tf] = body  # absolute body size

            # Momentum score: body_ratio * direction (+1 bull, -1 bear)
            direction = 1 if c_price > o else -1
            momentum_score[tf] = body_ratio[tf] * direction

        return {
            "body_ratio": body_ratio,
            "wick_ratio": wick_ratio,
            "impulse_size": impulse_size,
            "momentum_score": momentum_score,
        }

    def _compute_volume(self, candles: Dict[str, List[Dict]], tf_list: List[str]) -> Dict[str, Dict[str, float]]:
        """Volume MA, ratio, spike detection."""
        volume_ma = {}
        volume_ratio = {}
        volume_spike = {}

        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if len(tf_candles) < self.VOLUME_MA_PERIOD:
                continue

            volumes = [float(c.get("volume", 0) or c.get("tick_volume", 0) or 0) for c in tf_candles]
            ma = sum(volumes[-self.VOLUME_MA_PERIOD:]) / self.VOLUME_MA_PERIOD
            last_vol = volumes[-1] if volumes else 0

            volume_ma[tf] = ma
            volume_ratio[tf] = last_vol / ma if ma > 0 else 1.0
            volume_spike[tf] = 1.0 if last_vol > ma * 2.0 else 0.0  # 2x MA = spike

        return {
            "volume_ma": volume_ma,
            "volume_ratio": volume_ratio,
            "volume_spike": volume_spike,
        }

    def _compute_vwap_all_tfs(self, candles: Dict[str, List[Dict]], tf_list: List[str]) -> Dict[str, float]:
        """VWAP per timeframe (session-based reset not implemented — rolling VWAP)."""
        result = {}
        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if not tf_candles:
                continue

            # Rolling VWAP over available candles
            total_pv = 0.0
            total_vol = 0.0
            for c in tf_candles:
                vol = float(c.get("volume", 0) or c.get("tick_volume", 0) or 0)
                typical = (float(c["high"]) + float(c["low"]) + float(c["close"])) / 3
                total_pv += typical * vol
                total_vol += vol

            if total_vol > 0:
                result[tf] = total_pv / total_vol
        return result

    def _compute_vwap_distance(self, vwap_data: Dict, candles: Dict, tf_list: List[str]) -> Dict[str, float]:
        """Distance from current price to VWAP (in points)."""
        result = {}
        for tf in tf_list:
            vwap = vwap_data.get(tf)
            tf_candles = candles.get(tf, [])
            if vwap and tf_candles:
                last_close = float(tf_candles[-1]["close"])
                result[tf] = last_close - vwap
        return result

    def _compute_swings(self, candles: Dict[str, List[Dict]], tf_list: List[str]) -> Dict[str, Dict[str, float]]:
        """Last swing high/low per timeframe using 3-candle pivot."""
        high = {}
        low = {}
        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if len(tf_candles) < 5:
                continue

            # Find last swing high (middle candle higher than neighbors)
            for i in range(len(tf_candles) - 3, 1, -1):
                c = tf_candles[i]
                prev_c = tf_candles[i - 1]
                next_c = tf_candles[i + 1]

                c_h, c_l = float(c["high"]), float(c["low"])
                prev_h, prev_l = float(prev_c["high"]), float(prev_c["low"])
                next_h, next_l = float(next_c["high"]), float(next_c["low"])

                if c_h > prev_h and c_h > next_h:
                    high[tf] = c_h
                    break

            # Find last swing low
            for i in range(len(tf_candles) - 3, 1, -1):
                c = tf_candles[i]
                prev_c = tf_candles[i - 1]
                next_c = tf_candles[i + 1]

                c_h, c_l = float(c["high"]), float(c["low"])
                prev_h, prev_l = float(prev_c["high"]), float(prev_c["low"])
                next_h, next_l = float(next_c["high"]), float(next_c["low"])

                if c_l < prev_l and c_l < next_l:
                    low[tf] = c_l
                    break

        return {"high": high, "low": low}

    def _compute_nearest_sr(
        self,
        candles: Dict[str, List[Dict]],
        tf_list: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Compute nearest support/resistance per TF using _find_swing_pivots."""
        nearest_support = {}
        nearest_resistance = {}
        for tf in tf_list:
            tf_candles = candles.get(tf, [])
            if len(tf_candles) < 7:
                continue
            price = float(tf_candles[-1]["close"])
            pivots = self._find_swing_pivots(tf_candles, n=3)
            lows  = [p["price"] for p in pivots if p["type"] == "low"  and p["price"] < price]
            highs = [p["price"] for p in pivots if p["type"] == "high" and p["price"] > price]
            if lows:
                nearest_support[tf]    = max(lows)
            if highs:
                nearest_resistance[tf] = min(highs)
        return {"support": nearest_support, "resistance": nearest_resistance}

    def _compute_microstructure(self, current_tick: Optional[Dict]) -> tuple:
        """Compute tick speed and price velocity from tick data."""
        if not current_tick:
            return 0.0, 0.0

        # Simplified: tick_speed = 1 tick per call, price_velocity = 0
        # Real impl would track tick history over time window
        return 1.0, 0.0

    # ===== Pure math helpers =====
    def _ema(self, values: List[float], period: int) -> float:
        """Exponential Moving Average."""
        if len(values) < period:
            return sum(values) / len(values) if values else 0.0

        alpha = 2.0 / (period + 1)
        ema = sum(values[:period]) / period  # SMA seed
        for v in values[period:]:
            ema = alpha * v + (1 - alpha) * ema
        return ema

    def _find_swing_pivots(self, candles: List[Dict], n: int = 3) -> List[Dict]:
        """Find local pivot highs/lows where candle[i] is extreme of prev n and next n."""
        pivots = []
        for i in range(n, len(candles) - n):
            is_high = all(float(candles[i]["high"]) > float(candles[j]["high"]) for j in range(i-n, i)) and \
                      all(float(candles[i]["high"]) > float(candles[j]["high"]) for j in range(i+1, i+n+1))
            is_low = all(float(candles[i]["low"]) < float(candles[j]["low"]) for j in range(i-n, i)) and \
                     all(float(candles[i]["low"]) < float(candles[j]["low"]) for j in range(i+1, i+n+1))
            if is_high:
                pivots.append({"type": "high", "price": float(candles[i]["high"]), "index": i})
            if is_low:
                pivots.append({"type": "low", "price": float(candles[i]["low"]), "index": i})
        return pivots

    def _atr(self, candles: List[Dict], period: int) -> float:
        """Average True Range."""
        if len(candles) < period + 1:
            return 0.0

        trs = []
        for i in range(1, len(candles)):
            c = candles[i]
            pc = candles[i - 1]
            h, l = float(c["high"]), float(c["low"])
            pc_c = float(pc["close"])
            tr = max(h - l, abs(h - pc_c), abs(l - pc_c))
            trs.append(tr)

        if len(trs) < period:
            return sum(trs) / len(trs) if trs else 0.0

        # Wilder's smoothing
        atr = sum(trs[-period:]) / period
        return atr