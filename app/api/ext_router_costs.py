from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter, Query
from chamelefx.router import cost_model as cm
router = APIRouter()
@router.post("/router/costs/refresh")
def router_costs_refresh():
    return cm.refresh()
@router.get("/router/costs/summary")
def router_costs_summary():
    return cm.summary()
@router.get("/router/costs/penalty")
def router_costs_penalty(symbol: str = Query("EURUSD"), notional: float = Query(100000.0), venue: str | None = Query(None), mode: str = Query("p95")):
    return {"ok": True, "penalty_bps": cm.cost_penalty_bps(symbol=symbol, notional=notional, venue=venue, mode=mode)}
