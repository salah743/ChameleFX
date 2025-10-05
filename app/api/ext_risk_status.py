from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get("/risk/state")
async def get_risk_state():
    return {"ok": True, "state": "stub"}
