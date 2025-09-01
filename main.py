# main.py
from __future__ import annotations

import os
import importlib
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

log = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Dhan Options Analysis API",
    version="1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---- CORS (open for all; tighten later if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Helper: include router if module exists
def _include_router(module_path: str, attr: str = "router") -> bool:
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

# ---- Selftest endpoint
@app.get("/__selftest")
def selftest():
    env = "Render" if os.getenv("RENDER") else "Local"
    mode = os.getenv("APP_MODE", "SANDBOX")
    dh_client = os.getenv("DHAN_CLIENT_ID", "")
    dh_token  = os.getenv("DHAN_ACCESS_TOKEN", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    ai_model   = os.getenv("OPENAI_MODEL", os.getenv("AI_MODEL", "gpt-4.1-mini"))
    base_url   = os.getenv("OPENAI_BASE_URL", "default")
    csv_url    = os.getenv("DHAN_INSTRUMENTS_CSV_URL", "")

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
            "csv_url_present": bool(csv_url),
        },
    }

# ---- Include available routers
_include_router("App.Routers.health")
_include_router("App.Routers.instruments")       # Instruments CSV based
_include_router("App.Routers.optionchain")
_include_router("App.Routers.marketfeed")
_include_router("App.Routers.marketquote")       # ✅ NEW Market Quote router
_include_router("App.Routers.ai")
_include_router("App.Routers.optionchain_auto")
_include_router("App.Routers.admin_refresh")
_include_router("App.Routers.ui_api")
_include_router("App.Routers.live_feed")
_include_router("App.Routers.depth20_ws")
_include_router("App.Routers.historical")
_include_router("App.Routers.annexure")
# ---- Static site (serve /public as root)
app.mount("/", StaticFiles(directory="public", html=True), name="static")
