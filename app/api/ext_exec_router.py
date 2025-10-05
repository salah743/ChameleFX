from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter, Body
from typing import Dict, Any
from chamelefx.execution import router_intel as RI
from chamelefx.execution import quality as Q

router = APIRouter()

@router.get("/router/venues")
def router_venues():
    return {"ok": True, "venues": RI.venues()}

@router.post("/router/enable")
def router_enable(name: str = Body(..., embed=True)):
    return RI.enable_venue(name)

@router.post("/router/disable")
def router_disable(name: str = Body(..., embed=True), reason: str = Body("manual", embed=True)):
    return RI.disable_venue(name, reason)

@router.post("/router/decide")
def router_decide(symbol: str = Body(..., embed=True)):
    return RI.decide(symbol)

@router.post("/router/autotune_cost")
def router_autotune_cost(symbol: str = Body(..., embed=True), window: int = Body(200, embed=True)):
    s = Q.symbol_summary(symbol, window)
    if not s.get("ok"): 
        return s
    avg_cost = float(s.get("slippage_bps_avg",0.0))
    act = RI.feedback_cost_breach(symbol, avg_cost)
    return {"ok": True, "symbol": symbol, "avg_slippage_bps": avg_cost, "action": act}
