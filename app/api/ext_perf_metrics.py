from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter, Body
import math, statistics
router = APIRouter()
_equity: list[float] = []
@router.post("/perf/ingest_equity")
def ingest_equity(equity: list[float] = Body(...)):
    global _equity
    _equity = list(map(float, equity or []))
    return {"ok": True, "ts": __import__("time").time()}
@router.get("/perf/summary")
def perf_summary():
    if not _equity:
        return {"ok": True, "ts": __import__("time").time(), "metrics": {"sharpe":0.0,"max_dd":0.0,"win_rate":0.0,"expectancy":0.0,"equity_last":0.0}}
    eq = _equity
    rets = [0.0] + [ (eq[i]-eq[i-1])/eq[i-1] if eq[i-1] else 0.0 for i in range(1,len(eq)) ]
    sharpe = (statistics.mean(rets) / (statistics.pstdev(rets)+1e-12)) * math.sqrt(252) if len(rets)>1 else 0.0
    peak, dd = -1e18, 0.0
    cur = 0.0
    for v in eq:
        peak = max(peak, v)
        if peak>0: dd = max(dd, (peak - v)/peak)
    wins = sum(1 for r in rets if r>0)
    win_rate = wins/max(1,len(rets))
    expectancy = statistics.mean(rets) if rets else 0.0
    return {"ok": True, "ts": __import__("time").time(), "metrics": {"sharpe":sharpe,"max_dd":dd,"win_rate":win_rate,"expectancy":expectancy,"equity_last":eq[-1]}}
