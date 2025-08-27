from fastapi import APIRouter
from datetime import datetime
from App.common import MODE, OPENAI_API_KEY, OPENAI_MODEL, DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN, OPENAI_BASE_URL

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mode": MODE,
        "dhan_configured": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN),
        "openai_configured": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "base_url": OPENAI_BASE_URL or "default"
    }

@router.get("/__selftest")
def selftest():
    return {"ok": True, "status": {
        "env": "Render",
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "ai_present": bool(OPENAI_API_KEY),
        "ai_model": OPENAI_MODEL,
        "base_url": OPENAI_BASE_URL or "default"
    }}
