from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Routers import
from App.Routers import health, instruments, optionchain, optionchain_auto, marketfeed, ai, admin_refresh, ui_api

app = FastAPI(title="Options Analysis")

# CORS (safe default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers include
app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(optionchain.router)
app.include_router(optionchain_auto.router)
app.include_router(marketfeed.router)
app.include_router(ai.router)
app.include_router(admin_refresh.router)
app.include_router(ui_api.router)

# --- Static site (serve /public as root) ---
app.mount("/", StaticFiles(directory="public", html=True), name="static")
