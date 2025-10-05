
from __future__ import annotations
def compute(symbol: str, **kwargs):
    s = str(symbol or "EURUSD")
    return {"ok": True, "symbol": s, "raw": {}, "norm": {}, "meta": {"src": "stub"}}
