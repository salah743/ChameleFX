from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/perf_v2/ping')
async def ping():
    return {'ok': True, 'name': 'ext_perf_v2'}
