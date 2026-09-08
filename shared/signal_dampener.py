"""Signal Dampener — port of Nyao EA v43 position-aware entry brakes.

EA reference (RiriScalps.mq5 → GetSignalStrength / CheckEntryConditions):
  A. LosingPosScorePenalty   = 1.5  score penalty per losing same-dir open position
  B. MaxLosingPositionsSameDir = 2  hard block when >= 2 losing same-dir positions
  C. ConsecutiveLossesBeforeCooldown = 3 → block new entries for
     ConsecutiveLossCooldownBars = 3 M5 bars (15 min) after the 3rd loss

Fail-open: any data error → allow entry (never block on our own bug).
"""
import logging
import time
from datetime import datetime, timezone

log = logging.getLogger("SignalDampener")

LOSING_POS_SCORE_PENALTY = 1.5   # EA: LosingPosScorePenalty
MAX_LOSING_SAME_DIR = 2          # EA: MaxLosingPositionsSameDir
CONSEC_LOSSES_BEFORE_COOLDOWN = 3  # EA: ConsecutiveLossesBeforeCooldown
COOLDOWN_BARS = 3                # EA: ConsecutiveLossCooldownBars
BAR_SECONDS = 300                # M5
TIE_MAGIC = {20260908, 20260801}             # gateway magic — TIE's own trades only

# module state: cooldown expiry (epoch UTC) — recomputed from history each scan
_cooldown_until = 0.0


def _pos_dir(p: dict) -> str:
    return (p.get("direction") or p.get("type") or "").upper()


def losing_same_dir_count(raw_positions: list, symbol: str, direction: str) -> int:
    """Count open positions same symbol+direction with unrealized PnL < 0."""
    n = 0
    for p in raw_positions:
        if p.get("symbol", "") != symbol:
            continue
        if _pos_dir(p) != direction.upper():
            continue
        try:
            if float(p.get("profit", 0.0)) < 0:
                n += 1
        except (TypeError, ValueError):
            continue
    return n


def update_cooldown_from_history(deals: list, symbol: str) -> None:
    """Tail-count consecutive losing closed TIE_ deals for symbol.
    If >= threshold, arm cooldown = last_loss_time + COOLDOWN_BARS * M5.
    """
    global _cooldown_until
    try:
        closed = []
        for d in deals:
            if d.get("symbol", "") != symbol:
                continue
            # TIE-only: magic first (SL/TP closes carry "[sl ...]" comments),
            # comment prefix as fallback for gateways without magic field
            m = d.get("magic")
            if m is not None:
                if int(m) not in TIE_MAGIC:
                    continue
            else:
                cmt = d.get("comment", "") or ""
                if not (cmt.startswith("TIE_") or cmt.startswith("Riri")):
                    continue
            t = d.get("time")
            if isinstance(t, str):
                dt = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
                t = dt.timestamp()
            closed.append((float(t), float(d.get("profit", 0.0))))
        closed.sort(key=lambda x: x[0])

        consec_losses = 0
        last_loss_t = 0.0
        for t, pnl in reversed(closed):
            if pnl < 0:
                consec_losses += 1
                last_loss_t = t
            else:
                break

        if consec_losses >= CONSEC_LOSSES_BEFORE_COOLDOWN:
            new_until = last_loss_t + COOLDOWN_BARS * BAR_SECONDS
            if new_until > _cooldown_until:
                _cooldown_until = new_until
                log.warning(
                    f"🧊 COOLDOWN ARMED: {consec_losses} consecutive losses "
                    f"→ block entries until {datetime.fromtimestamp(new_until, timezone.utc).strftime('%H:%M UTC')}"
                )
        # expired cooldown naturally handled by time check below
    except Exception as e:
        log.debug(f"cooldown update skipped: {e}")  # fail-open


def gate(raw_positions: list, deals: list, symbol: str, direction: str,
         score: float | None, threshold: float | None):
    """Returns (allowed: bool, reason: str).

    score/threshold: optional nyao composite score — enables EA penalty math
    (adjustedScore = score - penalty; block if < threshold).
    """
    # C. cooldown
    if time.time() < _cooldown_until:
        remain = int(_cooldown_until - time.time())
        return False, f"cooldown_active:{remain}s"

    # A+B. losing position brakes
    n_lose = losing_same_dir_count(raw_positions, symbol, direction)
    if n_lose >= MAX_LOSING_SAME_DIR:
        return False, f"losing_pos_block:{n_lose}>={MAX_LOSING_SAME_DIR}"

    if n_lose > 0 and score is not None and threshold is not None:
        adjusted = score - n_lose * LOSING_POS_SCORE_PENALTY
        if adjusted < threshold:
            return False, f"score_dampened:{score:.1f}-{n_lose * LOSING_POS_SCORE_PENALTY:.1f}={adjusted:.1f}<{threshold}"

    return True, "ok"
