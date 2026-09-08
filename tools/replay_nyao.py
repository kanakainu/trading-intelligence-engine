"""Replay skor TIE per bar closed — bandingkan vs kapan EA masuk."""
import sys, datetime as dt
sys.path.insert(0, "/home/ubuntu/.hermes/trading")
sys.path.insert(0, "/home/ubuntu/trading-intelligence-engine")
from gateway_client import MT5GatewayClient
from strategies.riri_scalps import strategy as S
import importlib; importlib.reload(S)

url = open("/home/ubuntu/.hermes/trading/mt5_gateway_windows/current_url.txt").read().strip()
tok = open("/home/ubuntu/.hermes/trading/.gateway_token_new").read().strip()
c = MT5GatewayClient(url, tok)
k = c.candles("XAUUSD", "M5", 1000)
k = [x for x in k if isinstance(x.get("time"), (int, float))]
k.sort(key=lambda x: x["time"])

def wib(ts):
    return (dt.datetime.utcfromtimestamp(ts) + dt.timedelta(hours=7)).strftime("%m-%d %H:%M")

deals = c.history(days=1)
ea_bars, tie_bars = set(), set()
for d in deals:
    t = dt.datetime.fromisoformat(d["time"])
    if d.get("profit") == 0 and t >= dt.datetime(2026, 9, 7, 17, 44):
        bar = t.replace(minute=t.minute - t.minute % 5, second=0).strftime("%m-%d %H:%M")
        if d.get("magic") == 86420:
            ea_bars.add(bar)
        elif d.get("magic") in (20260801, 20260908) and str(d.get("comment", "")).startswith("TIE_R"):
            tie_bars.add(bar)

print(f"{'bar':12} {'BUY':>6} {'SELL':>6}  {'fire?':>6}  EA   TIE")
for i in range(len(k) - 1, max(len(k) - 160, 60), -1):
    cs = k[:i + 1]  # bar terakhir = closed (persis yang TIE pakai di scan berikutnya)
    b, _, _ = S._compute_nyao_smoothed_score(cs, "BUY")
    s, _, _ = S._compute_nyao_smoothed_score(cs, "SELL")
    lbl = wib(k[i]["time"] + 300)  # EA menilai di OPEN bar berikutnya
    fire = "BUY" if b >= 4.5 and b > s else ("SELL" if s >= 4.5 else "")
    if lbl in ea_bars or lbl in tie_bars or fire:
        print(f"{lbl:12} {b:6.2f} {s:6.2f}  {fire:>6}  {'✓' if lbl in ea_bars else '-'}    {'✓' if lbl in tie_bars else '-'}")
