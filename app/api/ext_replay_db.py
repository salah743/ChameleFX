from fastapi import APIRouter
router=APIRouter(prefix='/replay',tags=['replay'])
@router.get('/status')
def status():
    return {'ok': False,'detail':'Not Implemented in this build'}
