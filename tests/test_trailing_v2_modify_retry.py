"""Self-check retry modify di jalur TRAILING v2 (runtime/manual_trailing_v2.py).

Kasus nyata E77100 #3830163215 (17-Sep): gateway balikin **500 Internal Server Error**
3x berturut-turut saat BE-lock. Kode lama `raise_for_status()` -> exception -> dibuang
tanpa retry, jadi SL gak pernah geser, posisi balik ke SL awal dan kena SL padahal
udah profit $0.58/$0.85/$0.55.

Jalankan: python3 tests/test_trailing_v2_modify_retry.py
"""
import sys, os, types
import requests

sys.path.insert(0, "/home/ubuntu/trading-intelligence-engine")
sys.path.insert(0, "/home/ubuntu/.hermes/trading")
os.chdir("/home/ubuntu/trading-intelligence-engine")

import runtime.manual_trailing_v2 as mt  # noqa: E402


class FakeResp:
    """Tiru respons gateway: kode + body {"detail": ...} (kayak produksi)."""
    def __init__(self, code, detail=""):
        self.status_code = code
        self._detail = detail

    def raise_for_status(self):
        if self.status_code >= 400:
            e = requests.HTTPError(
                f"{self.status_code} Error for url: http://x/trade/modify "
                f"| response body: {self._detail}")
            e.response = self
            raise e

    def json(self):
        return {"success": True}


def setup(seq, side="1", detail=""):
    """seq = daftar (kode, detail) atau kode HTTP per percobaan. side '1'=sell, '0'=buy."""
    calls = {"n": 0, "sl": []}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["sl"].append(json["sl"])
        calls["n"] += 1
        item = seq[min(calls["n"] - 1, len(seq) - 1)]
        code, det = item if isinstance(item, tuple) else (item, detail)
        return FakeResp(code, det or ("500 Server Error" if code >= 500 else ""))

    mt.requests.post = fake_post
    mt.get_positions = lambda: [{"ticket": "999", "type": side,
                                 "symbol": "XAUUSD", "comment": "TIE_E_X"}]
    mt.time.sleep = lambda s: None
    return calls


# 0. knobs ada
assert mt.MODIFY_RETRY >= 2, mt.MODIFY_RETRY
print(f"0. Knob OK: retry={mt.MODIFY_RETRY} backoff={mt.MODIFY_BACKOFF}s")

# 1. [KASUS E77100] 500 Internal Server Error 2x lalu sukses -> HARUS retry & berhasil
c = setup([500, 500, 200])
r = mt.modify_order("999", 4341.47, tp=4321.70)
assert c["n"] == 3, f"harusnya 3 percobaan, dapet {c['n']}"
assert r == {"success": True}
print(f"1. [E77100] 500 error 2x -> BERHASIL di percobaan {c['n']} (dulu: nyerah di 1) OK")

# 2. 500 terus-terusan -> mentok MODIFY_RETRY, raise jujur (bukan diam-diam sukses)
c = setup([500])
try:
    mt.modify_order("999", 4341.47, tp=4321.70)
    raise AssertionError("harusnya raise")
except RuntimeError:
    pass
assert c["n"] == mt.MODIFY_RETRY, (c["n"], mt.MODIFY_RETRY)
print(f"2. 500 terus -> raise jujur setelah {c['n']}x OK")

# 3. error PERMANEN (posisi not found) -> stop percobaan-1, gak spam
c = setup([(404, '{"detail":"Position 999 not found"}')])
try:
    mt.modify_order("999", 4341.47, tp=4321.70)
    raise AssertionError("harusnya raise")
except RuntimeError:
    pass
assert c["n"] == 1, f"permanen harus 1 percobaan, dapet {c['n']}"
print(f"3. 404 not-found -> stop di percobaan {c['n']} (gak spam) OK")

# 4. [INTI] SELL: SL digeser NAIK tiap retry (menjauh dari harga)
c = setup([500])
try:
    mt.modify_order("999", 4341.47, tp=4321.70)
except RuntimeError:
    pass
sls = c["sl"]
assert len(set(sls)) == len(sls), f"SL harus geser tiap retry: {sls}"
assert all(b >= a for a, b in zip(sls, sls[1:])), f"SELL: SL naik terus: {sls}"
print(f"4. SELL: SL geser menjauh tiap retry {sls} OK")

# 5. BUY: SL digeser TURUN tiap retry (arah aman terbalik)
c = setup([500], side="0")
try:
    mt.modify_order("999", 4351.47, tp=4330.0)
except RuntimeError:
    pass
sls = c["sl"]
assert all(b <= a for a, b in zip(sls, sls[1:])), f"BUY: SL turun terus: {sls}"
print(f"5. BUY: SL geser menjauh (turun) {sls} OK")

# 6. sukses langsung -> 1 percobaan, gak nambah beban
c = setup([200])
mt.modify_order("999", 4341.47, tp=4321.70)
assert c["n"] == 1
print("6. Sukses langsung -> 1 percobaan OK")

print("\nV-TRAILING-V2-MODIFY: 7/7 CHECK LOLOS")
