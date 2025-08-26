from fastapi import APIRouter
router = APIRouter()

@router.get('/instruments')
def instruments():
    return {'data': ['demo instrument 1', 'demo instrument 2']}

