from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/portfolio_rebalance/ping')
async def ping():
    return {'ok': True, 'name': 'ext_portfolio_rebalance'}
