# main.py — FastAPI entrypoint (modular routers)

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ⬇️ 1) IMPORT YOUR ROUTERS (Top par add karein)
#    Make sure filenames are lowercase and each has `router = APIRouter(...)`
from App.Routers import health, instruments, optionchain, marketfeed, ai

app = FastAPI(
    title="Dhan Options Analysis API",
    description="Dhan v2 + AI backend",
    version="1.0.0",
)

# CORS (same as before)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static (same as before)
if Path("public").exists():
    app.mount("/static", StaticFiles(directory="public"), name="static")

# ⬇️ 2) ATTACH ROUTERS (App create hone ke turant baad add karein)
app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(optionchain.router)
app.include_router(marketfeed.router)
app.include_router(ai.router)

# Optional: a very simple root so GET / works
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    index = Path("public/index.html")
    if index.exists():
        return FileResponse(index)
    return HTMLResponse("<h3>Backend OK</h3><p>See <code>/docs</code> for API.</p>")

# Local dev runner (Render ignores this)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
