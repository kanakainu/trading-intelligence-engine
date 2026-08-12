"""Late entry detection — deterministic, no look-ahead.
Distinguishes EARLY_CONTINUATION from LATE_CHASE using normalized metrics
already computed by the shared pipeline. No new indicators.

Thresholds from config/features.json → late_entry section (optional).
Defaults are ATR-normalized and instrument-agnostic.
"""
from dataclasses import dataclass

# ── Defaults (all ATR-normalized unless noted) ────────────────────────────
_DEF_ZONE_DIST_MAX   = 2.0   # max dist from setup zone → if farther = late
_DEF_VWAP_DIST_MAX   = 2.5   # max abs dist from VWAP
_DEF_EXTENSION_MAX   = 1.8   # max dist moved from zone before entry
_DEF_ROOM_MIN        = 0.8   # min available room (ATR) to target
_DEF_DISPLACEMENT_MAX= 1.5   # max M1 candle displacement vs ATR


@dataclass
class LatenessResult:
    is_late:        bool
    reason:         str        # human-readable, e.g. "zone_dist_2.3ATR>2.0"
    lateness_score: float      # 0.0 = early, 1.0+ = very late (diagnostic only)


def evaluate(
    entry_price:        float,
    zone_price:         float,
    atr:                float,
    vwap_distance_atr:  float,
    available_room_atr: float,
    m1_body_atr:        float   = 0.0,   # last M1 candle body / atr (displacement)
    cfg:                "dict | None" = None,
) -> LatenessResult:
    """Return LatenessResult based on normalized metrics at entry time only."""
    if atr <= 0:
        return LatenessResult(False, "atr_zero", 0.0)

    cfg = cfg or {}
    zone_max  = cfg.get("late_zone_dist_max",    _DEF_ZONE_DIST_MAX)
    vwap_max  = cfg.get("late_vwap_dist_max",    _DEF_VWAP_DIST_MAX)
    ext_max   = cfg.get("late_extension_max",    _DEF_EXTENSION_MAX)
    room_min  = cfg.get("late_room_min",         _DEF_ROOM_MIN)
    disp_max  = cfg.get("late_displacement_max", _DEF_DISPLACEMENT_MAX)

    reasons = []
    score   = 0.0

    # 1. Distance from setup/location zone
    zone_dist = abs(entry_price - zone_price) / atr if zone_price > 0 else 0.0
    if zone_dist > zone_max:
        reasons.append(f"zone_dist_{zone_dist:.1f}ATR>{zone_max}")
        score += (zone_dist - zone_max) / zone_max

    # 2. VWAP extension (already ATR-normalized from MarketContext)
    if vwap_distance_atr > vwap_max:
        reasons.append(f"vwap_ext_{vwap_distance_atr:.1f}ATR>{vwap_max}")
        score += (vwap_distance_atr - vwap_max) / vwap_max

    # 3. Insufficient remaining room — move already happened
    if available_room_atr < room_min:
        reasons.append(f"room_{available_room_atr:.2f}ATR<{room_min}")
        score += (room_min - available_room_atr) / room_min

    # 4. Chasing a large M1 displacement (momentum already exhausted)
    if m1_body_atr > disp_max:
        reasons.append(f"m1_displacement_{m1_body_atr:.1f}ATR>{disp_max}")
        score += (m1_body_atr - disp_max) / disp_max

    is_late = score >= 1.0 or len(reasons) >= 2
    reason  = " | ".join(reasons) if reasons else "early_continuation"
    return LatenessResult(is_late, reason, round(score, 2))


# Self-check
if __name__ == "__main__":
    r = evaluate(2410.0, 2407.0, 2.0, vwap_distance_atr=3.0,
                 available_room_atr=0.5, m1_body_atr=2.0)
    assert r.is_late, f"expected late, got {r}"
    r2 = evaluate(2407.5, 2407.0, 2.0, vwap_distance_atr=0.5,
                  available_room_atr=2.0, m1_body_atr=0.3)
    assert not r2.is_late, f"expected early, got {r2}"
    print("late_entry OK")
