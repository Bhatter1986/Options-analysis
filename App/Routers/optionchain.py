from fastapi import APIRouter
router = APIRouter()

@router.get('/optionchain/expirylist')
def expirylist():
    return {'data': ['2025-09-02','2025-09-09']}

