from enum import Enum
from dataclasses import dataclass

class TriggerSignal(Enum):
    ARMED = "ARMED"
    WAIT = "WAIT"
    NONE = "NONE"

@dataclass
class TriggerResult:
    signal: TriggerSignal
    strength: int
    direction: str
    reason: str

def evaluate(direction: str, candles_m1: list, atr_m1: float) -> TriggerResult:
    if len(candles_m1) < 3:
        return TriggerResult(TriggerSignal.NONE, 0, direction, "Insufficient candles")

    last_candle = candles_m1[-1]
    prev_candle = candles_m1[-2]

    body_size = abs(last_candle['close'] - last_candle['open'])
    atr_threshold = 0.15 * atr_m1  # Lowered from 0.3 for scalping sensitivity

    strength = 0
    if body_size >= 0.15 * atr_m1:
        if body_size >= 0.8 * atr_m1:
            strength = 25
        elif body_size >= 0.5 * atr_m1:
            strength = 17
        else:
            strength = 10
    else:
        # If body is too small, it's not a strong trigger
        # Still, might be WAIT if conditions met other than strength
        pass 

    if direction.upper() == "BUY":
        if (last_candle['close'] > last_candle['open'] and 
            body_size > atr_threshold and 
            last_candle['close'] > prev_candle['close']):
            
            return TriggerResult(TriggerSignal.ARMED, strength, direction, "Bullish candle, strong body, closed above previous")
        else:
            return TriggerResult(TriggerSignal.WAIT, 0, direction, "Conditions not met for BUY trigger")
    elif direction.upper() == "SELL":
        if (last_candle['close'] < last_candle['open'] and 
            body_size > atr_threshold and 
            last_candle['close'] < prev_candle['close']):
            
            return TriggerResult(TriggerSignal.ARMED, strength, direction, "Bearish candle, strong body, closed below previous")
        else:
            return TriggerResult(TriggerSignal.WAIT, 0, direction, "Conditions not met for SELL trigger")
    else:
        return TriggerResult(TriggerSignal.NONE, 0, direction, "Unknown direction")
