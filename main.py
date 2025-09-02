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

# ---- logger
log = logging.getLogger("uvicorn.error")

# ---- FastAPI app
app = FastAPI(
    title="Dhan Options Analysis API",
    version="1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---- CORS (open now; restrict later as needed)
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

# ---- Include available core routers
_include_router("App.Routers.health")
_include_router("App.Routers.instruments")       # Instruments CSV based
_include_router("App.Routers.optionchain")
_include_router("App.Routers.marketfeed")
_include_router("App.Routers.marketquote")       # ✅ Market Quote router
_include_router("App.Routers.ai")
_include_router("App.Routers.optionchain_auto")
_include_router("App.Routers.admin_refresh")
_include_router("App.Routers.ui_api")
_include_router("App.Routers.live_feed")
_include_router("App.Routers.depth20_ws")
_include_router("App.Routers.historical")
_include_router("App.Routers.annexure")

# ---- Include Sudarshan engine routes (clean import + prefix)
try:
    from App.sudarshan.api.router import router as sudarshan_router
    app.include_router(sudarshan_router, prefix="/sudarshan", tags=["Sudarshan"])
    log.info("[main] Included router: App.sudarshan.api.router (prefix=/sudarshan)")
except Exception as e:
    log.warning(f"[main] Skipping Sudarshan router: {e}")

# ---- Static site (serve /public as root fallback)
# NOTE: This mount is last so it won't shadow API routes like /docs, /sudarshan, etc.
app.mount("/", StaticFiles(directory="public", html=True), name="static")

# ---- Uvicorn entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
