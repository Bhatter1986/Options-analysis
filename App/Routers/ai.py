from fastapi import APIRouter
router = APIRouter()

@router.post('/ai/marketview')
def marketview():
    return {'ai_reply': 'AI endpoint connected ✅'}

