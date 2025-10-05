from __future__ import annotations
from chamelefx.log import get_logger
from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter()

# Always-fast summary (use in UI if the canonical one is slow)
@router.get("/stats/summary_fast")
def stats_summary_fast() -> Dict[str, Any]:
    return {
        "equity": 100000.0,
        "balance": 100000.0,
        "open_pnl": 0.0,
        "open_positions": 0,
        "source": "fast_stub"
    }

# Canonical path (may be overridden by other routers)
@router.get("/stats/summary")
def stats_summary() -> Dict[str, Any]:
    # Keep this also fast — if another router remounts this later, its order decides.
    return {
        "equity": 100000.0,
        "balance": 100000.0,
        "open_pnl": 0.0,
        "open_positions": 0,
        "source": "stub"
    }

@router.get("/positions")
def positions() -> List[Dict[str, Any]]:
    return []

@router.get("/orders/recent")
def orders_recent() -> List[Dict[str, Any]]:
    return []
