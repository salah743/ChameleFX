from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter, Body
from typing import Dict, Any
from chamelefx.ops import guardrails as GR
from chamelefx.ops import watchdog as WD

router = APIRouter()

@router.post("/risk/record_pnl")
def risk_record_pnl(symbol: str = Body(..., embed=True),
                    pnl: float = Body(..., embed=True),
                    equity: float = Body(0.0, embed=True)):
    # Track equity if provided
    if equity and equity > 0:
        GR.set_equity(equity)
    return GR.record_pnl(symbol, pnl, equity or 0.0)

@router.get("/risk/state")
def risk_state():
    from chamelefx.ops.guardrails import _load_state as _ls  # type: ignore
    s = _ls()
    return {"ok": True, "state": s}

@router.post("/risk/pretrade_gate")
def risk_pretrade_gate(symbol: str = Body(..., embed=True),
                       side: str = Body("buy", embed=True),
                       weight: float = Body(0.0, embed=True)):
    return GR.pretrade_gate({"symbol": symbol, "side": side, "weight": weight})

@router.post("/risk/reset_today")
def risk_reset_today(symbol: str | None = Body(None, embed=True)):
    return WD.reset_today(symbol)

@router.post("/risk/drift_flag")
def risk_drift_flag(current: Dict[str, float] = Body(..., embed=True),
                    target: Dict[str, float] = Body(..., embed=True),
                    drift_bps: float = Body(100.0, embed=True)):
    return GR.portfolio_drift_flag(current, target, drift_bps)
