from fastapi import APIRouter
router=APIRouter(prefix='/portfolio',tags=['portfolio'])
@router.post('/apply')
def apply_weights(body:dict):
    return {'ok': False,'detail':'Not Implemented in this build'}
