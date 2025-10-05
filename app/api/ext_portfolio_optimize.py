from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/portfolio_optimize/ping')
async def ping():
    return {'ok': True, 'name': 'ext_portfolio_optimize'}
