from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/router_overrides/ping')
async def ping():
    return {'ok': True, 'name': 'ext_router_overrides'}
