from fastapi import APIRouter
import os, time

router = APIRouter()

@router.get("/health")
def health():
    return {
        "status": "ok",
    }

@router.get("/__selftest")
def selftest():
    return {
        "ok": True,
        "status": {
            "env": os.getenv("RENDER", "Local") and "Render" or "Local",
            "mode": os.getenv("DHAN_MODE", "DEMO"),
            "token_present": bool(os.getenv("DHAN_API_KEY")),
            "client_id_present": bool(os.getenv("DHAN_CLIENT_ID")),
            "ai_present": bool(os.getenv("OPENAI_API_KEY")),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    }
