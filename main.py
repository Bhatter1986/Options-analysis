<<<<<<< HEAD
# main.py
import os, logging
=======
import os
from pathlib import Path
import logging

>>>>>>> 7c89ac4 (local: wire routers + main.py updates)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from App.Routers import healthapp.include_router(health.router)
<<<<<<< HEAD
from App.Routers import health, instruments, optionchain, marketfeed, ai

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
app = FastAPI(title="Options Analysis", version="1.0.0")

# CORS (open)
=======
# ⬇️ hamare routers (yeh *file ke andar* import hai, terminal me nahi chalana)
from App.Routers import health, instruments, optionchain, marketfeed, ai

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("options-api")

app = FastAPI(title="Dhan Options Analysis API", version="2.0.0")

# CORS
>>>>>>> 7c89ac4 (local: wire routers + main.py updates)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

<<<<<<< HEAD
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
=======
# Static (optional)
if Path("public").exists():
    app.mount("/static", StaticFiles(directory="public"), name="static")

# Routers
app.include_router(health.router, tags=["health"])
app.include_router(instruments.router, tags=["instruments"])
app.include_router(optionchain.router, tags=["optionchain"])
app.include_router(marketfeed.router, tags=["marketfeed"])
app.include_router(ai.router, tags=["ai"])

@app.get("/", include_in_schema=False)
def root():
    return {"message": "Backend OK. See /docs"}

>>>>>>> 7c89ac4 (local: wire routers + main.py updates)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8000")))
