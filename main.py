import os
import logging
from datetime import datetime
from typing import Any, Dict

import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
# OpenAI optional (AI tabs ke liye). Agar key nahi hai to AI routes gracefully fail karenge.
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

# ------------- ENV -------------
load_dotenv()

MODE = os.getenv("MODE", "SANDBOX").upper()          # LIVE / SANDBOX
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Dhan base URLs
DHAN_LIVE_BASE_URL = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
DHAN_SANDBOX_BASE_URL = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
BASE_URL = DHAN_LIVE_BASE_URL if MODE == "LIVE" else DHAN_SANDBOX_BASE_URL

# Auth token
DHAN_ACCESS_TOKEN = (
    os.getenv("DHAN_LIVE_ACCESS_TOKEN")
    if MODE == "LIVE"
    else os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")
)

# ---- Flexible paths (so you can fix without code changes) ----
# Example (aap env me set kar sakte ho):
#   DHAN_OC_EXPIRY_PATH=/market/option-chain/expiry
#   DHAN_OC_CHAIN_PATH=/market/option-chain
OC_EXPIRY_PATH = os.getenv("DHAN_OC_EXPIRY_PATH", "/market/option-chain/expiry")
OC_CHAIN_PATH = os.getenv("DHAN_OC_CHAIN_PATH", "/market/option-chain")

# LTP ke liye (yeh tumhare UI me HDFCBANK demo ke liye use hota hai)
LTP_PATH = os.getenv("DHAN_LTP_PATH", "/marketfeed/ltp")

# OpenAI (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

# ------------- APP -------------
app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# Static (public/index.html)
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("public/index.html")

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse("public/dashboard.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("options-analysis")

# ------------- Helpers -------------
def verify_secret(req: Request):
    token = req.headers.get("X-Webhook-Secret")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Webhook Secret")
    return True

def dhan_headers() -> Dict[str, str]:
    if not DHAN_ACCESS_TOKEN:
        raise HTTPException(500, "DHAN access token missing")
    return {
        "Authorization": f"Bearer {DHAN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def dhan_get(path: str, params: Dict[str, Any] | None = None):
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, headers=dhan_headers(), params=params, timeout=15)
        if r.status_code >= 400:
            # bubble up broker error cleanly
            return JSONResponse(status_code=r.status_code, content={"broker_error": r.text})
        return r.json()
    except requests.Timeout:
        raise HTTPException(504, "Broker timeout")
    except Exception as e:
        log.exception("Broker GET failed")
        raise HTTPException(502, f"Broker GET failed: {e}")

def dhan_post(path: str, payload: Dict[str, Any]):
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.post(url, headers=dhan_headers(), json=payload, timeout=20)
        if r.status_code >= 400:
            return JSONResponse(status_code=r.status_code, content={"broker_error": r.text})
        return r.json()
    except requests.Timeout:
        raise HTTPException(504, "Broker timeout")
    except Exception as e:
        log.exception("Broker POST failed")
        raise HTTPException(502, f"Broker POST failed: {e}")

# ------------- Basic -------------
@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "token_present": bool(DHAN_ACCESS_TOKEN),
        "client_id_present": bool(
            os.getenv("DHAN_LIVE_CLIENT_ID" if MODE == "LIVE" else "DHAN_SANDBOX_CLIENT_ID")
        ),
    }

# ------------- Data endpoints (LIVE) -------------
@app.get("/marketfeed/ltp")
def market_ltp(exchange_segment: str, security_id: int):
    """
    Passthrough to Dhan LTP.
    Frontend calls: /marketfeed/ltp?exchange_segment=NSE&security_id=1333
    """
    params = {"exchange_segment": exchange_segment, "security_id": security_id}
    return {"data": dhan_get(LTP_PATH, params=params)}

@app.get("/optionchain/expirylist")
def optionchain_expirylist(under_security_id: int, under_exchange_segment: str):
    """
    Frontend expects list of expiries.
    Env-configurable path: DHAN_OC_EXPIRY_PATH (default /market/option-chain/expiry)
    """
    params = {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment,
    }
    data = dhan_get(OC_EXPIRY_PATH, params=params)
    # Normalize to { data: { data: [...] } } shape (as UI expects)
    expiries = data.get("data") if isinstance(data, dict) else data
    return {"data": {"data": expiries}}

@app.post("/optionchain")
def optionchain(payload: Dict[str, Any]):
    """
    Frontend sends JSON:
      { under_security_id: 25, under_exchange_segment: "IDX_I", expiry: "2025-08-28" }
    Env path: DHAN_OC_CHAIN_PATH (default /market/option-chain)
    """
    required = ("under_security_id", "under_exchange_segment", "expiry")
    for k in required:
        if k not in payload:
            raise HTTPException(400, f"Missing {k}")
    data = dhan_post(OC_CHAIN_PATH, payload)
    # Normalize shape for UI table (expects {data:{data:{strike: {CE:{},PE:{}}}}})
    return {"data": {"data": data.get("data", data)}}

# ------------- AI (optional) -------------
@app.post("/ai/marketview")
def ai_marketview(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    if not client:
        raise HTTPException(503, "OpenAI not configured")
    try:
        prompt = f"Analyze the market context and share concise insights:\n{req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ai_reply": res.choices[0].message.content}
    except Exception as e:
        log.exception("AI marketview failed")
        raise HTTPException(500, f"AI marketview failed: {e}")

@app.post("/ai/strategy")
def ai_strategy(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    if not client:
        raise HTTPException(503, "OpenAI not configured")
    try:
        prompt = f"Suggest an options strategy from inputs:\n{req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ai_strategy": res.choices[0].message.content}
    except Exception as e:
        log.exception("AI strategy failed")
        raise HTTPException(500, f"AI strategy failed: {e}")

@app.post("/ai/payoff")
def ai_payoff(req: Dict[str, Any], auth: bool = Depends(verify_secret)):
    if not client:
        raise HTTPException(503, "OpenAI not configured")
    try:
        prompt = f"Compute payoff explanation for this position:\n{req}"
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"ai_payoff": res.choices[0].message.content}
    except Exception as e:
        log.exception("AI payoff failed")
        raise HTTPException(500, f"AI payoff failed: {e}")

# ------------- Self test & errors -------------
@app.get("/__selftest")
def selftest():
    return {
        "app": "Options-analysis (Dhan v2 + AI)",
        "mode": MODE,
        "env": MODE,
        "now": datetime.utcnow().isoformat(),
        "endpoints": [
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
        ],
    }

@app.post("/ai/test")
def ai_test():
    if not client:
        return {"ai_test_reply": "OK (OpenAI not configured)."}
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello, test response"}],
    )
    return {"ai_test_reply": res.choices[0].message.content}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)})
