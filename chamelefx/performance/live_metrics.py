from __future__ import annotations
import os, json, math, time, statistics
from typing import Dict, Any, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUN  = os.path.join(ROOT, "chamelefx", "runtime")
os.makedirs(RUN, exist_ok=True)

F_SUMMARY = os.path.join(RUN, "perf_summary.json")

_buf: List[float] = []
_state: Dict[str, Any] = {"sharpe":0.0,"max_dd":0.0,"win_rate":0.0,"expectancy":0.0,"equity_last":0.0}

def _save():
    tmp = F_SUMMARY + ".tmp"
    with open(tmp,"w",encoding="utf-8") as f: json.dump(_state,f,indent=2)
    os.replace(tmp,F_SUMMARY)

def ingest_equity(equity: float):
    global _buf, _state
    if equity<=0: return {"ok":False,"error":"bad_equity"}
    _buf.append(float(equity))
    _state["equity_last"] = equity
    if len(_buf)>500: _buf=_buf[-500:]

    # calc metrics
    if len(_buf)>2:
        rets=[(_buf[i]/_buf[i-1]-1) for i in range(1,len(_buf)) if _buf[i-1]>0]
        if rets:
            mean,stdev=statistics.mean(rets),statistics.pstdev(rets)
            sharpe=(mean/stdev*math.sqrt(252)) if stdev>0 else 0.0
            _state["sharpe"]=round(sharpe,3)
            _state["win_rate"]=round(sum(1 for r in rets if r>0)/len(rets),3)
            _state["expectancy"]=round(mean,5)
            peak=max(_buf); trough=min(_buf); dd=(peak-trough)/peak if peak>0 else 0.0
            _state["max_dd"]=round(dd*100,2)
    _save()
    return {"ok":True,"state":_state}

def summary() -> Dict[str,Any]:
    return dict(_state)

def equity_curve(n:int=200):
    if not _buf: return []
    step=max(1,len(_buf)//n)
    return _buf[::step][-n:]
