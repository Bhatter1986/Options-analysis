# main.py
from __future__ import annotations

import os
import importlib
import logging
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ---- .env (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---- Logger
log = logging.getLogger("uvicorn.error")

# ---- FastAPI app
app = FastAPI(
    title="Dhan Options Analysis API",
    version="1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---- CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Helper: conditionally include routers by module path
def _include_router(module_path: str, attr: str = "router") -> bool:
    """
    Import <module_path> and include its `router` on the app if present.
    Safe to call for optional modules.
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

# ---- Root & self-test
@app.get("/")
def root():
    return {"status": "ok", "name": "Dhan Options Analysis API"}

@app.get("/__selftest")
def selftest():
    env = "Render" if os.getenv("RENDER") else "Local"
    mode = os.getenv("APP_MODE", "SANDBOX")
    return {
        "ok": True,
        "env": env,
        "mode": mode,
        "has_openai": bool(os.getenv("OPENAI_API_KEY")),
        "has_dhan_token": bool(os.getenv("DHAN_ACCESS_TOKEN")),
    }

# ---- Existing routers (keep as-is)
_include_router("App.Routers.health")
_include_router("App.Routers.instruments")
_include_router("App.Routers.optionchain")
_include_router("App.Routers.marketfeed")
_include_router("App.Routers.marketquote")
_include_router("App.Routers.ai")
_include_router("App.Routers.optionchain_auto")
_include_router("App.Routers.admin_refresh")
_include_router("App.Routers.ui_api")
_include_router("App.Routers.live_feed")
_include_router("App.Routers.depth20_ws")
_include_router("App.Routers.historical")
_include_router("App.Routers.annexure")

# ---- NEW: data_fetch router
_include_router("App.Routers.data_fetch")

# ---- Sudarshan (already prefixed inside module)
_include_router("App.sudarshan.api.router")

# ---- Optional UI helper
_include_router("App.Ui.ui_router")

# ---- Static site (serve /public as root) — keep LAST
app.mount("/", StaticFiles(directory="public", html=True), name="static")
