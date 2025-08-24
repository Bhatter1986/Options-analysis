# main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os, json, requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

# ------------------------------------------------------------
# Environment & Config
# ------------------------------------------------------------
MODE = os.getenv("MODE", "LIVE").upper()  # LIVE | SANDBOX

def pick(prefix: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(f"DHAN_{MODE}_{prefix}", default)

BASE_URL = pick("BASE_URL", "https://api.dhan.co/v2").rstrip("/")
ACCESS_TOKEN = pick("ACCESS_TOKEN", "")
CLIENT_ID = pick("CLIENT_ID", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SESSION = requests.Session()
SESSION.timeout = 30

def dh_headers() -> Dict[str, str]:
    """
    Dhan v2 headers.
    Docs: access-token + client-id
    """
    return {
        "Content-Type": "application/json",
        "access-token": ACCESS_TOKEN,
        "client-id": CLIENT_ID,
    }

def dh_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generic POST to Dhan v2.
    path: e.g. 'option/expiry-list' or 'option/chain'
    """
    url = f"{BASE_URL}/{path.lstrip('/')}"
    try:
        r = SESSION.post(url, headers=dh_headers(), data=json.dumps(payload))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Dhan network error: {e}")
    if r.status_code >= 400:
        # return body for visibility
        raise HTTPException(status_code=r.status_code, detail={
            "status": "error",
            "code": r.status_code,
            "url": url,
            "payload": payload,
            "body": {"raw": r.text}
        })
    try:
        return r.json()
    except ValueError:
        return {"status": "success", "raw": r.text}

def dh_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    try:
        r = SESSION.get(url, headers=dh_headers(), params=params)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Dhan network error: {e}")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail={
            "status": "error",
            "code": r.status_code,
            "url": url,
            "params": params,
            "body": {"raw": r.text}
        })
    try:
        return r.json()
    except ValueError:
        return {"status": "success", "raw": r.text}

# ------------------------------------------------------------
# CORS for frontend
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ------------------------------------------------------------
# Health & Status
# ------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True, "app": app.title}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "openai_present": bool(OPENAI_API_KEY),
    }

# ------------------------------------------------------------
# Real-time Market (simple LTP helper)
# ------------------------------------------------------------
@app.get("/marketfeed/ltp")
def marketfeed_ltp(
    security_id: str = Query(..., description="Dhan security id"),
    exchange_segment: str = Query(..., description="e.g. NSE_EQ, IDX_I, NSE_FNO"),
):
    """
    Lightweight LTP endpoint. Dhan v2 marketfeed LTP/quote can vary by account;
    if your account supports POST quote, wire it similarly here.
    """
    # Many users have a GET quote endpoint exposed as /marketfeed/quote
    # If your account only supports POST, convert this to dh_post.
    params = {"securityId": security_id, "exchangeSegment": exchange_segment}
    return dh_get("marketfeed/quote", params)

# ------------------------------------------------------------
# Option Chain — Expiry list & Chain
# ------------------------------------------------------------
@app.get("/optionchain/expirylist")
def option_expiry_list(
    under_security_id: str = Query(..., description="Underlying security id"),
    under_exchange_segment: str = Query(..., description="IDX_I | NSE_EQ | NSE_FNO ..."),
):
    """
    Correct Dhan v2 path: POST /v2/option/expiry-list
    """
    payload = {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment,
    }
    return dh_post("option/expiry-list", payload)

@app.get("/optionchain")
def option_chain(
    under_security_id: str = Query(..., description="Underlying security id"),
    under_exchange_segment: str = Query(..., description="IDX_I | NSE_EQ | NSE_FNO ..."),
    expiry_date: str = Query(..., description="YYYY-MM-DD"),
):
    """
    Correct Dhan v2 path: POST /v2/option/chain
    """
    payload = {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment,
        "expiry_date": expiry_date,
    }
    return dh_post("option/chain", payload)

# ------------------------------------------------------------
# Self-test (helps debug from browser)
# ------------------------------------------------------------
@app.get("/__selftest")
def selftest():
    """
    Quick sanity: shows env wiring + a sample expiry-list call on NIFTY (13/IDX_I).
    Change IDs if needed.
    """
    status = {
        "env": True,
        "mode": MODE,
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "openai_present": bool(OPENAI_API_KEY),
    }
    sample = {}
    try:
        sample = dh_post(
            "option/expiry-list",
            {"under_security_id": "13", "under_exchange_segment": "IDX_I"},
        )
    except HTTPException as e:
        # Return the exact error payload to help fix quickly
        sample = e.detail if isinstance(e.detail, dict) else {"error": str(e.detail)}
    return {"ok": True, "status": status, "sample_expirylist": sample}

# ------------------------------------------------------------
# Root
# ------------------------------------------------------------
@app.get("/")
def root():
    return {
        "app": app.title,
        "mode": MODE,
        "env": MODE,
        "endpoints": [
            "/health",
            "/broker_status",
            "/marketfeed/ltp",
            "/optionchain/expirylist",
            "/optionchain",
            "/__selftest",
        ],
    }

# ------------------------------------------------------------
# Uvicorn entrypoint (local dev)
# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
