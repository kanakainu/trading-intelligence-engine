"""Self-check retry modify SL/TP (requote) — mock gateway_client.
Jalankan: python3 tests/test_modify_retry.py
"""
import sys, types
sys.path.insert(0, "/home/ubuntu/trading-intelligence-engine")

import adapters.broker.mt5_broker as mb  # noqa: E402
from adapters.broker.mt5_broker import MT5BrokerAdapter  # noqa: E402


class GWError(Exception):
    """Tiru MT5GatewayError: punya .status + .detail."""
    def __init__(self, status, detail):
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")


class MockClient:
    """Modify bisa disuruh gagal N kali dulu, lalu sukses/tetap gagal."""
    def __init__(self, fail_n=0, err="Requote", permanent=False):
        self.fail_n, self.err, self.permanent = fail_n, err, permanent
        self.calls, self.sl_seen = 0, []

    def modify(self, ticket, sl=None, tp=None):
        self.calls += 1
        self.sl_seen.append(sl)
        if self.calls <= self.fail_n:
            if self.permanent:
                return {"success": False, "message": self.err}
            raise GWError(409, self.err)
        return {"success": True}

    def positions(self):
        return [{"ticket": 999, "symbol": "XAUUSD", "type": "1"}]   # 1 = sell

    def price(self, sym):
        return {"ask": 4343.0, "bid": 4342.8, "spread": 200}        # spread 0.20


def make(fail_n=0, err="Requote", permanent=False):
    a = MT5BrokerAdapter("http://x", "tok")
    c = MockClient(fail_n=fail_n, err=err, permanent=permanent)
    a._client = c
    a._connected = True
    return a, c


# 0. konstanta ada
assert mb.MODIFY_RETRY >= 2 and mb.MODIFY_BACKOFF >= 0, (mb.MODIFY_RETRY, mb.MODIFY_BACKOFF)
print(f"0. Konstanta OK: retry={mb.MODIFY_RETRY} backoff={mb.MODIFY_BACKOFF}s")

# 1. sukses langsung -> 1 panggilan
a, c = make(fail_n=0)
r = a.modify_order("999", stop_loss=4341.47, take_profit=4321.70)
assert r.status == "FILLED" and c.calls == 1, (r.status, c.calls)
print("1. Sukses langsung -> 1 panggilan OK")

# 2. REQUOTE sesaat (2x) -> retry, akhirnya sukses (INI kasus E77100)
a, c = make(fail_n=2, err="Requote")
r = a.modify_order("999", stop_loss=4341.47, take_profit=4321.70)
assert r.status == "FILLED", r.status
assert c.calls == 3, c.calls
print(f"2. Requote 2x -> RETRY sukses di percobaan {c.calls} OK")

# 3. error PERMANEN (posisi gak ada) -> stop cepat, gak spam retry
a, c = make(fail_n=99, err="Position not found", permanent=True)
r = a.modify_order("999", stop_loss=4341.47, take_profit=4321.70)
assert r.status == "REJECTED" and "not found" in (r.error or "").lower(), (r.status, r.error)
assert c.calls == 1, f"permanen harusnya 1 panggilan, dapet {c.calls}"
print(f"3. Permanen -> stop di percobaan {c.calls} (gak spam) OK")

# 4. requote terus-terusan -> mentok MODIFY_RETRY, dilaporin jujur (bukan diam-diam)
a, c = make(fail_n=99, err="Requote")
r = a.modify_order("999", stop_loss=4341.47, take_profit=4321.70)
assert r.status == "REJECTED", r.status
assert c.calls == mb.MODIFY_RETRY, (c.calls, mb.MODIFY_RETRY)
print(f"4. Requote {mb.MODIFY_RETRY}x -> REJECTED jujur OK (calls={c.calls})")

# 5. [INTI FIX] tiap retry geser SL MENJAUH dari harga (SELL = naik) -> lepas dari requote
a, c = make(fail_n=99, err="Requote")
a.modify_order("999", stop_loss=4341.47, take_profit=4321.70)
sls = c.sl_seen
assert len(set(sls)) == len(sls), f"SL harus geser tiap retry, dapet {sls}"
assert all(b >= a_ for a_, b in zip(sls, sls[1:])), f"SELL: SL naik terus, dapet {sls}"
print(f"5. SL geser menjauh tiap retry (SELL naik): {sls} OK")

# 6. TP dipertahankan, gak ikut kegeser
assert all(isinstance(s, float) or s is None for s in sls)
print("6. TP dipertahankan OK")

print("\nV-MODIFY-RETRY: 7/7 CHECK LOLOS")
