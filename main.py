# main.py — App entry (wires all routers)

import os
import logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ── load env early
load_dotenv()

# ── basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger("options-analysis")

MODE = os.getenv("MODE", "SANDBOX").upper()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

# ── import your routers (💡 these must exist in App/Routers/)
from App.Routers import health, instruments, optionchain, marketfeed, ai

# ── FastAPI app
app = FastAPI(
    title="Dhan Options Analysis API",
    description="Dhan v2 + AI backend",
    version="1.3.0",
)

# ── CORS (open; tighten later if you want)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ── static site (public/)
if Path("public").exists():
    app.mount("/static", StaticFiles(directory="public"), name="static")

# ── include routers (🔥 this is what exposes the endpoints)
app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(optionchain.router)
app.include_router(marketfeed.router)
app.include_router(ai.router)

# ── simple root + docs hint
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    idx = Path("public/index.html")
    if idx.exists():
        return FileResponse(idx)
    return HTMLResponse(
        "<h3>Backend OK</h3><p>See <code>/docs</code> for API or place UI at "
        "<code>public/index.html</code>.</p>"
    )

# ── tiny health (kept here too; your detailed one lives in health router)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mode": MODE,
        "dhan_configured": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN),
        "openai_configured": bool(OPENAI_API_KEY),
    }

# ── startup log
@app.on_event("startup")
async def _startup():
    log.info("===== Startup =====")
    log.info(f"MODE={MODE}")
    log.info(f"OPENAI_MODEL={OPENAI_MODEL}  OPENAI_KEY_SET={bool(OPENAI_API_KEY)}")
    log.info(f"DHAN_ID_SET={bool(DHAN_CLIENT_ID)}  DHAN_TOKEN_SET={bool(DHAN_ACCESS_TOKEN)}")
    log.info("===================")

# ── global error guards (optional but helpful)
@app.exception_handler(Exception)
async def _any_err(request: Request, exc: Exception):
    log.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

# ── local run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
