# App/Routers/health.py
import os, time
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/__selftest")
def selftest():
    return {
        "ok": True,
        "status": {
            "env": os.getenv("RENDER", "Local"),
            "mode": os.getenv("DHAN_MODE", "DEMO"),
            "token_present": bool(os.getenv("DHAN_ACCESS_TOKEN")),
            "client_id_present": bool(os.getenv("DHAN_CLIENT_ID")),
            "ai_present": bool(os.getenv("OPENAI_API_KEY")),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    }
