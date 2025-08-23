# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Optional, Dict

app = FastAPI(
    title="DhanHQ Proxy – Core",
    version="1.0.0",
    description="Core service exposing health and broker status only."
)

# CORS (open for easy testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _pick_env() -> Dict[str, Optional[str]]:
    """
    Decide which environment to use (SANDBOX/LIVE) and read credentials.
    Only reads env vars; does not call Dhan.
    """
    env = (os.getenv("DHAN_ENV") or "SANDBOX").strip().upper()
    if env not in {"SANDBOX", "LIVE"}:
        env = "SANDBOX"

    if env == "LIVE":
        token = os.getenv("DHAN_LIVE_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_LIVE_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        base_url = os.getenv("DHAN_LIVE_BASE_URL") or "https://api.dhan.co/v2"
    else:
        token = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_SANDBOX_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        base_url = os.getenv("DHAN_SANDBOX_BASE_URL") or "https://sandbox.dhan.co/v2"

    return {
        "env": env,
        "token_present": bool(token),
        "client_id_present": bool(client_id),
        "base_url": base_url,
    }

@app.get("/health", tags=["Health"])
def health():
    """Basic liveness probe."""
    return {"ok": True}

@app.get("/broker_status", tags=["Health"])
def broker_status():
    """
    Shows selected environment and whether credentials are present.
    This does NOT hit Dhan; only checks env variables.
    """
    cfg = _pick_env()
    return {
        "mode": (os.getenv("MODE") or "DRY").upper(),
        "env": cfg["env"],
        "base_url": cfg["base_url"],
        "token_present": cfg["token_present"],
        "client_id_present": cfg["client_id_present"],
        "has_creds": bool(cfg["token_present"] and cfg["client_id_present"]),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("RELOAD", "")),
    )
