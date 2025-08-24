# main.py
import os
import logging
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import requests
from dotenv import load_dotenv

# -----------------
# Load environment
# -----------------
load_dotenv()

MODE = os.getenv("MODE", "SANDBOX").upper()  # "LIVE" | "SANDBOX"

# Dhan base URLs
DHAN_LIVE_BASE_URL = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
DHAN_SANDBOX_BASE_URL = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
DHAN_BASE = DHAN_LIVE_BASE_URL if MODE == "LIVE" else DHAN_SANDBOX_BASE_URL

# Dhan credentials
DHAN_ACCESS_TOKEN = (
    os.getenv("DHAN_LIVE_ACCESS_TOKEN")
    if MODE == "LIVE"
    else os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")
)
DHAN_CLIENT_ID = (
    os.getenv("DHAN_LIVE_CLIENT_ID")
    if MODE == "LIVE"
    else os.getenv("DHAN_SANDBOX_CLIENT_ID")
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# OpenAI (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
try:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    _openai_client = None  # package missing or init failed; endpoints will handle gracefully

# -----------------
# App + static
# -----------------
app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# Serve /static/* from public/
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    """
    Root serves public/index.html
    """
    path = "public/index.html"
    if not os.path.exists(path):
        return JSONResponse({"detail": "index.html not found"}, status_code=404)
    return FileResponse(path)

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    """
    Convenience route for /dashboard -> public/index.html (single page)
    """
    path = "public/index.html"
    if not os.path.exists(path):
        return JSONResponse({"detail": "index.html not found"}, status_code=404)
    return FileResponse(path)

# --------------
# Middleware
# --------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend anywhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------
# Logging
# --------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("options-analysis")

# --------------
# Utils
# --------------
def _dhan_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {DHAN_ACCESS_TOKEN}" if DHAN_ACCESS_TOKEN else "",
        "X-Client-Id": str(DHAN_CLIENT_ID or ""),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def verify_secret(req: Request):
    token = req.headers.get("X-Webhook-Secret")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True

# --------------
# Basic endpoints
# --------------
@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
    }

@app.get("/__selftest")
def selftest():
    """
    Quick snapshot of app + visible endpoints for debugging.
    """
    endpoints = [
        "/health",
        "/broker_status",
        "/marketfeed/ltp",
        "/optionchain/expirylist",
        "/optionchain",
        "/option_analysis",
        "/ai/marketview",
        "/ai/strategy",
        "/ai/payoff",
        "/ai/test",
        "/__selftest",
    ]
    return {
        "app": "Options-analysis (Dhan v2 + AI)",
        "mode": MODE,
        "env": "LIVE" if MODE == "LIVE" else "SANDBOX",
        "endpoints": endpoints,
    }

# --------------
# Marketfeed (demo LTP)
# --------------
@app.get("/marketfeed/ltp")
def marketfeed_ltp(exchange_segment: str, security_id: int):
    """
    Thin passthrough to Dhan LTP (adjust path if different on your account).
    If Dhan fails, returns a minimal skeleton so UI doesn't crash.
    """
    try:
        url = f"{DHAN_BASE}/marketfeed/ltp"
        r = requests.get(
            url,
            params={"exchange_segment": exchange_segment, "security_id": security_id},
            headers=_dhan_headers(),
            timeout=10,
        )
        if r.ok:
            return {"data": r.json()}
        logger.warning(f"LTP non-200: {r.status_code} {r.text[:200]}")
    except Exception as e:
        logger.warning(f"LTP error: {e}")

    # fallback skeleton (UI will show '—')
    return {"data": {"data": {}}}

# --------------
# Option Chain
# --------------
@app.get("/optionchain/expirylist")
def optionchain_expirylist(under_security_id: int, under_exchange_segment: str):
    """
    Returns expiries for given underlying.
    Tries Dhan first; if it fails, returns a small sample so UI keeps working.
    """
    # Try Dhan (adjust path if your Dhan endpoint differs)
    try:
        url = f"{DHAN_BASE}/optionchain/expirylist"
        r = requests.get(
            url,
            params={
                "under_security_id": under_security_id,
                "under_exchange_segment": under_exchange_segment,
            },
            headers=_dhan_headers(),
            timeout=15,
        )
        if r.ok:
            return {"data": r.json()}
        logger.warning(f"expirylist non-200: {r.status_code} {r.text[:200]}")
    except Exception as e:
        logger.warning(f"expirylist error: {e}")

    # Fallback sample dates
    return {"data": {"data": ["2025-08-28", "2025-09-04", "2025-09-11"]}}

class OCBody(BaseModel):
    under_security_id: int
    under_exchange_segment: str
    expiry: str

@app.post("/optionchain")
def optionchain(body: OCBody):
    """
    Returns option chain for a given expiry.
    Tries Dhan first; else returns a minimal mock so charts/table render.
    """
    # Try Dhan (adjust path if different)
    try:
        url = f"{DHAN_BASE}/optionchain"
        r = requests.post(url, json=body.dict(), headers=_dhan_headers(), timeout=20)
        if r.ok:
            return {"data": r.json()}
        logger.warning(f"optionchain non-200: {r.status_code} {r.text[:200]}")
    except Exception as e:
        logger.warning(f"optionchain error: {e}")

    # Fallback minimal sample (two strikes) for UI testing
    sample = {
        "43500": {
            "CE": {
                "oi": 12345,
                "previous_oi": 11111,
                "volume": 4567,
                "implied_volatility": 16.8,
                "last_price": 125.5,
                "change": 5.25,
            },
            "PE": {
                "oi": 9876,
                "previous_oi": 10443,
                "volume": 3456,
                "implied_volatility": 18.2,
                "last_price": 84.25,
                "change": -3.75,
            },
        },
        "43700": {
            "CE": {
                "oi": 9876,
                "previous_oi": 7889,
                "volume": 6789,
                "implied_volatility": 17.8,
                "last_price": 76.25,
                "change": 3.75,
            },
            "PE": {
                "oi": 7654,
                "previous_oi": 7999,
                "volume": 5432,
                "implied_volatility": 17.5,
                "last_price": 105.75,
                "change": -1.50,
            },
        },
    }
    return {"data": {"data": sample}}

# --------------
# (Optional) Option analysis placeholder
# --------------
@app.get("/option_analysis")
def option_analysis():
    return {"ok": True, "note": "Add your custom analytics here."}

# --------------
# AI endpoints (OpenAI optional)
# --------------
def _need_openai():
    if not _openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI not configured. Set OPENAI_API_KEY to enable AI endpoints.",
        )

@app.post("/ai/marketview")
def ai_marketview(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    """
    Market overview using AI. Requires OPENAI_API_KEY.
    """
    _need_openai()
    try:
        prompt = f"Analyze Indian index options market snapshot and give 5 bullet insights. Input: {req}"
        res = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return {"ai_reply": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI marketview error: {e}")
        raise HTTPException(status_code=500, detail="AI marketview failed")

@app.post("/ai/strategy")
def ai_strategy(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    """
    Suggest options strategy using AI. Requires OPENAI_API_KEY.
    """
    _need_openai()
    try:
        prompt = (
            "Suggest a risk-defined options strategy (instrument, strikes, qty, rationale) "
            "for NIFTY/BANKNIFTY given this user intent and constraints: "
            f"{req}. Return concise bullet points."
        )
        res = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return {"ai_strategy": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI strategy error: {e}")
        raise HTTPException(status_code=500, detail="AI strategy failed")

@app.post("/ai/payoff")
def ai_payoff(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    """
    High-level payoff explanation using AI. Requires OPENAI_API_KEY.
    """
    _need_openai()
    try:
        prompt = f"Explain the payoff, breakevens, max profit/loss for this strategy: {req}"
        res = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return {"ai_payoff": res.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI payoff error: {e}")
        raise HTTPException(status_code=500, detail="AI payoff failed")

@app.post("/ai/test")
def ai_test():
    """
    Quick AI ping. Returns a canned response if OPENAI not configured.
    """
    if not _openai_client:
        return {"ai_test_reply": "AI is not configured (no OPENAI_API_KEY)."}
    res = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello, test response"}],
    )
    return {"ai_test_reply": res.choices[0].message.content}

# --------------
# Global error handler
# --------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)})
