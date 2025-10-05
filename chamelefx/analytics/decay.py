from __future__ import annotations
import os, json, time, math
from typing import Dict, Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUN  = os.path.join(ROOT, "runtime")
os.makedirs(RUN, exist_ok=True)

F_STORE = os.path.join(RUN, "alpha_decay.json")

def _load() -> Dict[str, Any]:
    try:
        return json.load(open(F_STORE,"r",encoding="utf-8"))
    except Exception:
        return {"alpha":{}, "ts": time.time()}

def _save(obj: Dict[str,Any]):
    with open(F_STORE,"w",encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def update(alpha: str, value: float, half_life_hours: float = 24.0) -> Dict[str, Any]:
    alpha = str(alpha).upper()
    db=_load()
    now=time.time()
    node=db["alpha"].get(alpha, {"val":0.0,"ts":now})
    # decay from last ts to now
    dt = max(0.0, now - float(node.get("ts", now)))
    lam = math.log(2.0)/max(1.0, half_life_hours*3600.0)
    decayed = float(node.get("val",0.0)) * math.exp(-lam*dt)
    new_val = decayed + float(value)
    db["alpha"][alpha] = {"val": new_val, "ts": now, "hl_h": half_life_hours}
    db["ts"] = now
    _save(db)
    return {"ok": True, "alpha": alpha, "val": new_val, "half_life_h": half_life_hours}

def get(alpha: str) -> Dict[str, Any]:
    alpha=str(alpha).upper()
    db=_load()
    node=db["alpha"].get(alpha, {"val":0.0,"ts":0})
    return {"ok": True, "alpha": alpha, "val": float(node.get("val",0.0)), "ts": node.get("ts",0), "half_life_h": node.get("hl_h",24.0)}
