from fastapi import APIRouter
router=APIRouter(prefix='/ops/config',tags=['ops'])
@router.get('/effective')
def effective():
    return {'ok': False,'detail':'Not Implemented in this build'}
