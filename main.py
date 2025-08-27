# main.py
from __future__ import annotations

import os
import importlib
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Dhan Options Analysis API",
    version="1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---- CORS (open; tighten later if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Helper: include router if module exists
def _include_router(module_path: str, attr: str = "router") -> bool:
    """
    Tries to import `module_path` (e.g. 'App.Routers.instruments') and include its FastAPI `router`.
    Returns True if included, False if module not found or no router present.
    """
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        log.warning(f"[main] Skipping {module_path}: {e}")
        return False
    router: Optional[object] = getattr(module, attr, None)
    if router is None:
        log.warning(f"[main] {module_path} has no attribute '{attr}', skipping.")
        return False
    app.include_router(router)  # type: ignore[arg-type]
    log.info(f"[main] Included router: {module_path}")
    return True


# ---- Root (simple ping)
@app.get("/")
def root():
    return {"status": "ok", "name": "Dhan Options Analysis API"}


# ---- Selftest (matches what you were using)
@app.get("/__selftest")
def selftest():
    env = "Render" if os.getenv("RENDER") else "Local"
    mode = os.getenv("APP_MODE", "SANDBOX")

    openai_key = os.getenv("OPENAI_API_KEY", "")
    dh_client  = os.getenv("DHAN_CLIENT_ID", "")
    dh_token   = os.getenv("DHAN_ACCESS_TOKEN", "")
    ai_model   = os.getenv("OPENAI_MODEL", os.getenv("AI_MODEL", "gpt-4.1-mini"))
    base_url   = os.getenv("OPENAI_BASE_URL", "default")

    return {
        "ok": True,
        "status": {
            "env": env,
            "mode": mode,
            "token_present": bool(dh_token),
            "client_id_present": bool(dh_client),
            "ai_present": bool(openai_key),
            "ai_model": ai_model,
            "base_url": base_url,
        },
    }


# ---- Include available routers (any missing file is safely skipped)
_include_router("App.Routers.health")
_include_router("App.Routers.instruments")
_include_router("App.Routers.optionchain")   # <- your new Option Chain router
_include_router("App.Routers.marketfeed")
_include_router("App.Routers.ai")


# ---- Uvicorn entry (Render uses gunicorn/uvicorn workers)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
