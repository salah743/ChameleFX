from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/alpha_trade_bias/ping')
async def ping():
    return {'ok': True, 'name': 'ext_alpha_trade_bias'}
