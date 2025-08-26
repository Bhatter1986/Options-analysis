# main.py
import os, logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from App.Routers import health, instruments, optionchain, marketfeed, ai

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
app = FastAPI(title="Options Analysis", version="1.0.0")

# CORS (open)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Static UI (optional)
if os.path.isdir("public"):
    app.mount("/static", StaticFiles(directory="public"), name="static")

# Routers
app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(optionchain.router)
app.include_router(marketfeed.router)
app.include_router(ai.router)

# local run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8000")))
