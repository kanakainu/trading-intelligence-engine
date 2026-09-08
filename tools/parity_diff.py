"""Side-by-side: EA (magic 86420) vs TIE (magic 20260908) entries per M5 candle."""
import sys, datetime as dt
from collections import defaultdict

sys.path.insert(0, "/home/ubuntu/.hermes/trading")
from gateway_client import MT5GatewayClient

url = open("/home/ubuntu/.hermes/trading/mt5_gateway_windows/current_url.txt").read().strip()
tok = open("/home/ubuntu/.hermes/trading/.gateway_token_new").read().strip()
c = MT5GatewayClient(url, tok)
deals = c.history(days=1)

def parse(t):
    return dt.datetime.fromisoformat(str(t).replace("Z", "").split(".")[0])

def bucket(d):
    return d.replace(minute=d.minute - d.minute % 5, second=0).strftime("%H:%M")

ea_open, tie_open = defaultdict(list), defaultdict(list)
for d in deals:
    tm, mg = parse(d.get("time", "")), d.get("magic", 0)
    if tm < dt.datetime(2026, 9, 7, 17, 44):
        continue
    if d.get("profit", 1) != 0:  # open-deal = profit 0
        continue
    key = (bucket(tm), d.get("type", ""))
    if mg == 86420:
        ea_open[key].append((d.get("volume", 0), d.get("price", 0)))
    elif mg in (20260801, 20260908):
        tie_open[key].append((d.get("volume", 0), d.get("price", 0), d.get("comment", "")))

keys = sorted(set(ea_open) | set(tie_open))
print(f"{'candle':6} {'dir':6} {'EA':26} {'TIE':26}")
for k in keys:
    ea = ",".join(f"{v:.2f}@{p:.2f}" for v, p in sorted(ea_open.get(k, []))) or "-"
    tie = ",".join(f"{v:.2f}@{pr:.2f}" for v, pr, cm in sorted(tie_open.get(k, []))) or "-"
    flag = "" if (ea != "-" and tie != "-") else ("  <EA only" if ea != "-" else "  <TIE only")
    print(f"{k[0]:6} {k[1]:6} {ea:26} {tie:26}{flag}")
print(f"\ntotal EA opens={sum(len(v) for v in ea_open.values())}  TIE opens={sum(len(v) for v in tie_open.values())}")
