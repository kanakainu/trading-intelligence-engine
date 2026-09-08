#!/usr/bin/env python3
"""OI bias — baca pesan 'OI|tanggal|harga|oi' dari mailbox ntfy (Windows fetcher),
hitung kuadran CME (ΔOI × Δharga) → tulis data/bias.json buat TUIUL gate arah.

Stdlib only. Cron/systemd tiap 30 menit. Kuadran (artikel institusi):
  OI naik + harga naik → BUY_ON_DIP | OI naik + harga turun → SELL_ON_RALLY
  OI turun (squeezing/likuidasi) → NEUTRAL (rally/jatuhan gak sehat, jangan scalp searah)
"""
import json, os, re, time, urllib.request
from datetime import datetime, timezone, timedelta

BASE = "https://ntfy.sh"
TOPIC = os.environ.get("TIE_NTFY_TOPIC", "tiegwukgcgdnu1e")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "data", "oi_history.json")
OUT = os.path.join(ROOT, "data", "bias.json")
WIB = timezone(timedelta(hours=7))
LINE_RE = re.compile(r"^OI\|(\d{4}-\d{2}-\d{2})\|([\d.]*\d)\|([\d.]+)$")

def load_hist():
    try: return json.load(open(HIST))
    except Exception: return []

def save_hist(h):
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    tmp = HIST + ".tmp"; json.dump(h, open(tmp, "w")); os.replace(tmp, HIST)

def poll():
    url = f"{BASE}/{TOPIC}/json?poll=1&since=24h"
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    out = []
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            for line in r.read().decode().splitlines():
                try: msg = json.loads(line)
                except Exception: continue
                m = LINE_RE.match((msg.get("message") or "").strip())
                if m:
                    out.append({"date": m.group(1), "price": float(m.group(2) or 0),
                                "oi": float(m.group(3)), "ts": msg.get("time")})
    except Exception as e:
        print("poll gagal:", e)
    return out

def compute_bias(hist):
    """hist: list poin {'date','price','oi'} unik per tanggal, terurut."""
    if len(hist) < 2:
        return {"bias": "NEUTRAL", "why": "belum_ada_sejarah_OI", "n": len(hist)}
    d0, d1 = hist[-2], hist[-1]
    doi = d1["oi"] - d0["oi"]
    dp = (d1["price"] - d0["price"]) if (d0["price"] and d1["price"]) else 0.0
    if doi > 0 and dp > 0:  bias = "BUY_ON_DIP"
    elif doi > 0 and dp < 0: bias = "SELL_ON_RALLY"
    else: bias = "NEUTRAL"     # OI turun = short-cover/long-liq, arah gak sehat
    return {"bias": bias, "doi": doi, "dprice": dp, "oi": d1["oi"],
            "asof": d1["date"], "n": len(hist), "ts": datetime.now(WIB).isoformat()}

def main():
    msgs = poll()
    hist = load_hist()
    for m in msgs:
        if m["price"] and not any(h["date"] == m["date"] and h["oi"] == m["oi"] for h in hist):
            hist.append(m)
    # harga terakhir bisa refresh dalam hari sama → update poin tanggal terakhir
    hist = sorted({h["date"]: h for h in hist}.values(), key=lambda x: x["date"])[-10:]
    save_hist(hist)
    bias = compute_bias(hist)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"; json.dump(bias, open(tmp, "w"), indent=1); os.replace(tmp, OUT)
    print("bias:", bias)

if __name__ == "__main__":
    main()
