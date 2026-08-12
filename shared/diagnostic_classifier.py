"""Diagnostic classifier — classifies every candidate at decision time.
No new filters. Diagnostic only. Results logged to entry_telemetry.

Classifications:
  SIGNAL_STRONG_LOCATION_BAD  — valid setup + strong trigger + BAD location
  LOCATION_GOOD_TRIGGER_BAD   — valid setup + GOOD location + weak/no trigger
  LATE_ENTRY                  — entry chasing move (from late_entry module)
  NORMAL                      — none of above
"""
from dataclasses import dataclass

SIGNAL_STRONG_LOCATION_BAD = "SIGNAL_STRONG_LOCATION_BAD"
LOCATION_GOOD_TRIGGER_BAD  = "LOCATION_GOOD_TRIGGER_BAD"
LATE_ENTRY                 = "LATE_ENTRY"
NORMAL                     = "NORMAL"

# Trigger strength threshold — "strong" means above this
_STRONG_TRIGGER_THRESHOLD = 12.0   # out of 25 (0.3xATR body = 10, 0.5xATR = 17)


@dataclass
class DiagnosticResult:
    label:   str    # one of the four constants above
    reason:  str    # human-readable detail


def classify(
    location_grade:   str,    # "GOOD" | "NEUTRAL" | "BAD"
    trigger_signal:   str,    # "ARMED" | "WAIT" | "NONE"
    trigger_strength: float,  # 0–25
    is_late:          bool,
    lateness_reason:  str = "",
) -> DiagnosticResult:
    """Classify candidate at decision time. No side effects."""
    if is_late:
        return DiagnosticResult(LATE_ENTRY, lateness_reason or "late_chase")

    if location_grade == "BAD" and trigger_strength >= _STRONG_TRIGGER_THRESHOLD:
        return DiagnosticResult(
            SIGNAL_STRONG_LOCATION_BAD,
            f"trigger_strength={trigger_strength:.0f}>={_STRONG_TRIGGER_THRESHOLD} but loc=BAD"
        )

    if location_grade == "GOOD" and trigger_signal != "ARMED":
        return DiagnosticResult(
            LOCATION_GOOD_TRIGGER_BAD,
            f"loc=GOOD but trigger={trigger_signal} strength={trigger_strength:.0f}"
        )

    return DiagnosticResult(NORMAL, "")


# Self-check
if __name__ == "__main__":
    r = classify("BAD",  "ARMED", 15.0, False)
    assert r.label == SIGNAL_STRONG_LOCATION_BAD, r
    r = classify("GOOD", "WAIT",  5.0,  False)
    assert r.label == LOCATION_GOOD_TRIGGER_BAD, r
    r = classify("GOOD", "ARMED", 15.0, True, "zone_dist_2.5ATR")
    assert r.label == LATE_ENTRY, r
    r = classify("GOOD", "ARMED", 15.0, False)
    assert r.label == NORMAL, r
    print("diagnostic_classifier OK")
