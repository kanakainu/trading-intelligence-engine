#!/usr/bin/env python3
"""TUIUL orderflow lab — CVD proxy dari tick-volume broker (M1→M5) + replay edge check.

delta M5 : Σ sign(candle M1)×tick_volume
CVD      : akumulasi delta M5
Replay   : arah trade closed TIE vs slope CVD 3 bar terakhir
           → expectancy SETUJU vs LAWAN. Beda signifikan = orderflow nambah edge.
"""
import sys, json, bisect, statistics as st
from datetime import datetime, timezone
sys.path.insert(0, "/home/ubuntu/.hermes/trading")
from gateway_client import MT5GatewayClient

GW_URL = open("/home/ubuntu/.hermes/trading/mt5_gateway_windows/current_url.txt").read().strip()
TOKEN = open("/home/ubuntu/.hermes/trading/.gateway_token_new").read().strip()

def build_m5(m1):
    out = {}
    for b in m1:
        k = b["time"] - (b["time"] % 300)
        d = b["tick_volume"] * (1 if b["close"] > b["open"] else -1 if b["close"] < b["open"] else 0)
        e = out.setdefault(k, {"delta": 0, "tv": 0, "hi": b["high"], "lo": b["low"]})
        e["delta"] += d; e["tv"] += b["tick_volume"]
        e["hi"] = max(e["hi"], b["high"]); e["lo"] = min(e["lo"], b["low"])
    keys = sorted(out)
    cvd = 0.0; rngs = []
    rows = []
    med_tv = st.median([o["tv"] for o in out.values()])
    for k in keys:
        e = out[k]; cvd += e["delta"]; rng = e["hi"] - e["lo"]; rngs.append(rng)
        atr14 = st.mean(rngs[-14:]) if len(rngs) >= 14 else None
        rows.append({"t": k, "delta": e["delta"], "cvd": cvd, "tv": e["tv"], "rng": rng,
                     "absorb": bool(atr14 and rng < 0.4*atr14 and e["tv"] > 2*med_tv)})
    return rows

def replay(rows, closed, look=3):
    ts = [r["t"] for r in rows]
    agree, oppose, nocov = [], [], 0
    for d in closed:
        try:
            dt = datetime.strptime(d["time"].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            ep = int(dt.timestamp()) - 7*3600   # WIB naive → epoch
        except Exception:
            nocov += 1; continue
        i = bisect.bisect_right(ts, ep) - 1
        if i < look: nocov += 1; continue
        slope = rows[i]["cvd"] - rows[i-look]["cvd"]
        dirn = 1 if d["type"] == "buy" else -1
        if slope == 0: nocov += 1; continue
        (agree if dirn*slope > 0 else oppose).append(d.get("profit", 0))
    def stat(x): return {"n": len(x), "sum": round(sum(x), 2), "avg": round(st.mean(x), 3) if x else 0}
    return {"agree": stat(agree), "oppose": stat(oppose), "nocov": nocov}

if __name__ == "__main__":
    gw = MT5GatewayClient(base_url=GW_URL, token=TOKEN)
    m1 = gw.candles("XAUUSD", "M1", 2800)
    rows = build_m5(sorted(m1, key=lambda x: x["time"]))
    hist = gw.history(days=3)
    closed = [d for d in hist if d.get("profit", 0) != 0 and (
        str(d.get("magic")) in ("20260908", "20260801") or str(d.get("comment", "")).startswith(("TIE_", "Riri_")))]
    res = replay(rows, closed)
    print("bars M5:", len(rows), "| closed TIE:", len(closed))
    print("SETUJU CVD :", res["agree"])
    print("LAWAN CVD  :", res["oppose"])
    print("nocov      :", res["nocov"])
    json.dump(res, open("/tmp/orderflow_replay.json", "w"), indent=1)
