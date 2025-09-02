# main.py
from __future__ import annotations
import os, importlib, logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env (optional)
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

# ---- CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Helper to conditionally include routers
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

# ---- Root & self-test
@app.get("/")
def root():
    return {"status": "ok", "name": "Dhan Options Analysis API"}

@app.get("/__selftest")
def selftest():
    env = "Render" if os.getenv("RENDER") else "Local"
    mode = os.getenv("APP_MODE", "SANDBOX")
    return {"ok": True, "env": env, "mode": mode}

# ---- Existing routers (Dhan HQ flow intact)
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

# ---- Sudarshan (router already has prefix="/sudarshan")
from App.sudarshan.api.router import router as sudarshan_router
app.include_router(sudarshan_router)

# ---- UI helper API (if present) — has its own prefix inside the module
try:
    from App.Ui.ui_router import router as ui_router
    app.include_router(ui_router)
except Exception as e:
    log.warning(f"[main] UI router optional; skipping: {e}")

# ---- Static site (serve /public as root)
app.mount("/", StaticFiles(directory="public", html=True), name="static")
