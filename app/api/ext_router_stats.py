from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter, Query
from chamelefx.router import scorer

router = APIRouter()

@router.get("/router/stats")
def router_stats(symbol: str = Query("EURUSD")):
    return scorer.compute(symbol)
