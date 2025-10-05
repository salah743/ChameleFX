from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/backtest_v3/ping')
async def ping():
    return {'ok': True, 'name': 'ext_backtest_v3'}
