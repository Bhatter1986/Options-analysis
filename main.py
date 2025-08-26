# main.py — Dhan Options Analysis (modular)
import os
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Routers (match your files in App/Routers/)
from App.Routers import health, instruments, optionchain, marketfeed, ai

# ====== Env & logging ======
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger("options-api")

MODE = os.getenv("MODE", "SANDBOX").upper()

# ====== App ======
app = FastAPI(
    title="Dhan Options Analysis API",
    description="FastAPI backend (modular routers)",
    version="2.0.0",
)

# CORS (open for now; tighten later if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (for public UI)
if Path("public").exists():
    app.mount("/static", StaticFiles(directory="public"), name="static")

# Root: serve a tiny OK page or redirect users to /docs
@app.get("/", include_in_schema=False)
def root():
    idx = Path("public/index.html")
    if idx.exists():
        return StaticFiles(directory="public", html=True)
    return {"ok": True, "msg": "Backend OK. See /docs", "mode": MODE}

# Register routers (these files already exist in App/Routers/)
app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(optionchain.router)
app.include_router(marketfeed.router)
app.include_router(ai.router)

# Startup debug
@app.on_event("startup")
async def _startup():
    log.info("===== Startup =====")
    log.info(f"MODE={MODE}")
    for name in ["DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN", "OPENAI_API_KEY", "WEBHOOK_SECRET"]:
        val = os.getenv(name, "")
        masked = (val[:4] + "…" + "*" * (len(val) - 4)) if val else "∅"
        log.info(f"{name} set={bool(val)} value={masked}")
    log.info("===================")

# Local dev (Render will ignore this and use Procfile/command)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
