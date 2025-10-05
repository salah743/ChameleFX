from fastapi import APIRouter
router=APIRouter(prefix='/perf',tags=['perf'])
@router.get('/summary')
def summary():
    return {'ok': False,'detail':'Not Implemented in this build'}
