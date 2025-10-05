from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/ioc_probe/ping')
async def ping():
    return {'ok': True, 'name': 'ext_ioc_probe'}
