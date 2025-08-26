from fastapi import APIRouter
from datetime import datetime
import os

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dhan_configured": bool(os.getenv("DHAN_CLIENT_ID") and os.getenv("DHAN_ACCESS_TOKEN")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "mode": os.getenv("MODE","SANDBOX").upper()
    }

@router.get("/__selftest")
def selftest():
    return {"ok": True, "status": {
        "env": "Render",
        "mode": os.getenv("MODE","SANDBOX").upper(),
        "token_present": bool(os.getenv("DHAN_ACCESS_TOKEN")),
        "client_id_present": bool(os.getenv("DHAN_CLIENT_ID")),
        "ai_present": bool(os.getenv("OPENAI_API_KEY")),
    }}
