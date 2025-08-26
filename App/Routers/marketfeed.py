from fastapi import APIRouter
router = APIRouter()

@router.get('/marketfeed/ltp')
def ltp():
    return {'data': {'ltp': 123.45}}

