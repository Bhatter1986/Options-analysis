from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Routers import
from App.Routers import health, instrfrom __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Local dev convenience (production me env Render pe aayega)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Routers import
from App.Routers import (
    health,
    instruments,
    optionchain,
    optionchain_auto,
    marketfeed,
    ai,
    admin_refresh,
    ui_api,
)

APP_TITLE = os.getenv("APP_TITLE", "Options Analysis")
APP_VERSION = os.getenv("APP_VERSION", "v1")

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

# CORS (safe defaults)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # restrict if needed
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
app.include_router(ai.router)               # <- AI endpoints (/ai/ask etc.)
app.include_router(admin_refresh.router)
app.include_router(ui_api.router)

# --- Static site (serve /public as root) ---
# This serves /public/index.html at "/" and /public/dashboard.html at "/dashboard.html"
app.mount("/", StaticFiles(directory="public", html=True), name="static")uments, optionchain, optionchain_auto, marketfeed, ai, admin_refresh, ui_api

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
