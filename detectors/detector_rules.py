"""Source of Truth for 13 Bystra Strategy Setups.
Based on official XAUUSD - Bystra Secret Strategy rules by Nora.
"""

SETUPS = {
    "SNRC1": {
        "type": "Continuation",
        "risk": "Low",
        "ltf_pattern": ["RBR", "DBD"],
        "confluence": "Strong S/R",
        "confirmation": "HTF Engulfing/Body",
        "entry": "Pullback to Base Zone",
        "rule": "RBR at Strong Support (Buy) or DBD at Strong Resistance (Sell)"
    },
    "SNRC2": {
        "type": "Continuation",
        "risk": "Low",
        "ltf_pattern": ["RBD", "DBR"],
        "confluence": "Broken Strong S/R",
        "confirmation": "HTF Engulfing/Body",
        "entry": "Pullback to Base Zone",
        "rule": "RBD breaks previous Strong Support (Sell) or DBR breaks previous Strong Resistance (Buy)"
    },
    "SNRC3": {
        "type": "Continuation",
        "risk": "Medium",
        "ltf_pattern": ["Failed BE", "Failed BUE"],
        "confluence": "Engulfing candle replaces S/R",
        "entry": "Aligned with Bullish/Bearish Engulfing",
        "rule": "SNRC1 pattern but Strong S/R is Bullish (Buy) or Bearish (Sell) Engulfing"
    },
    "HYBRID1": {
        "type": "Reversal",
        "risk": "Medium",
        "ltf_pattern": ["RBR", "DBD", "QMR"],
        "confluence": "Retest at setup level",
        "entry": "Retest Level",
        "rule": "Price reverses at end of trend, retests RBR/DBD/QMR zone. No Danger Zone."
    },
    "HYBRID2": {
        "type": "Reversal",
        "risk": "Medium",
        "ltf_pattern": ["Hybrid 1", "Trendline"],
        "confluence": "2 parallel trendlines + Switch HTF",
        "entry": "3rd trendline retest",
        "rule": "Hybrid 1 + trendlines. Switch HTF for reversal confirmation."
    },
    "QMR": {
        "type": "Reversal",
        "risk": "High",
        "ltf_pattern": ["M-shape", "W-shape"],
        "confluence": "Quasimodo Structure",
        "confirmation": "HTF Engulfing mandatory",
        "entry": "Right Shoulder (3rd drive)",
        "rule": "HH -> Sell at right shoulder; LL -> Buy at right shoulder"
    },
    "QMC": {
        "type": "Continuation",
        "risk": "Medium",
        "ltf_pattern": ["QMR", "Trendline"],
        "confluence": "QM structure in trend",
        "entry": "3rd drive retest",
        "rule": "QMR + trendline in existing trend"
    },
    "QM2P": {
        "type": "Reversal",
        "risk": "High",
        "ltf_pattern": ["QMR", "2-point Trendline"],
        "confluence": "Trendline connects same head",
        "entry": "Right shoulder",
        "rule": "QMR with trendline connecting the head point"
    },
    "QMM": {
        "type": "Reversal",
        "risk": "High",
        "ltf_pattern": ["Failed QMR"],
        "confluence": "Failed setup re-entry",
        "entry": "Left shoulder of failed QMR",
        "rule": "Price fails QMR -> entry at original left shoulder"
    },
    "BLINDSPOT": {
        "type": "Reversal",
        "risk": "High",
        "ltf_pattern": ["Failed Engulfing", "Breakout"],
        "confluence": "Significant break after failed engulfing",
        "entry": "At the break zone",
        "rule": "Swap zone: Failed BE/BUE followed by clean breakout"
    },
    "BLINDSPOT2": {
        "type": "Reversal",
        "risk": "High",
        "ltf_pattern": ["Blindspot 1", "Trendline"],
        "confluence": "Trendline confluence",
        "entry": "Break zone",
        "rule": "Blindspot 1 + trendline"
    },
    "MANIPULATION": {
        "type": "Reversal",
        "risk": "Very High",
        "ltf_pattern": ["HTF Engulfing", "LTF RBR/DBD"],
        "confluence": "Entry inside HTF body",
        "entry": "LTF Base Zone",
        "rule": "HTF Bearish Engulf -> LTF DBD inside body (Sell); HTF Bullish Engulf -> LTF RBR inside body (Buy)"
    }
}
