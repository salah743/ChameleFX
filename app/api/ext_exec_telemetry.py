from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/exec_telemetry/ping')
async def ping():
    return {'ok': True, 'name': 'ext_exec_telemetry'}
