from chamelefx.log import get_logger
from fastapi import APIRouter

router = APIRouter()

@router.get('/risk_sizer/ping')
async def ping():
    return {'ok': True, 'name': 'ext_risk_sizer'}
