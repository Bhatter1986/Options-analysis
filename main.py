# main.py
import os
import json
import datetime as dt
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -------------------------------------------------
# Environment & constants
# -------------------------------------------------
MODE = os.getenv("MODE", "LIVE").upper()
BASE_URL = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2").rstrip("/")
ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")
CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my$ecret123")

# Quick map for common indices (adjust as you like)
INDEX_MAP = {
    # Dhan securityId for indices (examples)
    "NIFTY": {"under_security_id": "13", "under_exchange_segment": "IDX_I"},
    "BANKNIFTY": {"under_security_id": "25", "under_exchange_segment": "IDX_I"},
    "FINNIFTY": {"under_security_id": "53", "under_exchange_segment": "IDX_I"},
}

# -------------------------------------------------
# FastAPI app
# -------------------------------------------------
app = FastAPI(title="Options-analysis (Dhan v2 + AI)", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def dh_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Client-Id": CLIENT_ID,
        "Content-Type": "application/json",
    }


def dh_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST to Dhan v2. path is path AFTER /v2 (e.g., 'option-chain/expiry-list')
    """
    url = f"{BASE_URL}/{path.lstrip('/')}"
    try:
        r = requests.post(url, headers=dh_headers(), json=payload, timeout=20)
        if r.status_code == 200:
            return {"status": "success", "data": r.json()}
        return {
            "status": "error",
            "code": r.status_code,
            "url": url,
            "payload": payload,
            "body": {"raw": r.text},
        }
    except Exception as e:
        return {"status": "error", "exception": str(e)}


def dh_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    try:
        r = requests.get(url, headers=dh_headers(), params=params or {}, timeout=20)
        if r.status_code == 200:
            return {"status": "success", "data": r.json()}
        return {
            "status": "error",
            "code": r.status_code,
            "url": url,
            "params": params,
            "body": {"raw": r.text},
        }
    except Exception as e:
        return {"status": "error", "exception": str(e)}


def ok_status() -> Dict[str, Any]:
    return {
        "env": MODE == "LIVE",
        "mode": MODE,
        "token_present": bool(ACCESS_TOKEN),
        "client_id_present": bool(CLIENT_ID),
        "openai_present": bool(OPENAI_API_KEY),
    }

# -------------------------------------------------
# Schemas (for POST bodies)
# -------------------------------------------------
class ExpiryListIn(BaseModel):
    under_security_id: str
    under_exchange_segment: str  # e.g., IDX_I


class OptionChainIn(ExpiryListIn):
    expiry_date: str  # YYYY-MM-DD


# -------------------------------------------------
# Basic routes
# -------------------------------------------------
@app.get("/")
def root(api: Optional[str] = None):
    return {"app": app.title, "mode": MODE, "env": MODE, "endpoints": [
        "/health",
        "/broker_status",
        "/marketfeed/ltp",
        "/option-chain/expirylist",
        "/option-chain",
        "/ai/test",
        "/__selftest",
    ]}


@app.get("/health")
def health():
    return {"ok": True, "ts": dt.datetime.utcnow().isoformat() + "Z"}


@app.get("/broker_status")
def broker_status():
    st = ok_status()
    return {
        "mode": MODE,
        "connected": st["token_present"] and st["client_id_present"],
        "token_present": st["token_present"],
        "client_id_present": st["client_id_present"],
    }

# -------------------------------------------------
# Market data (examples)
# -------------------------------------------------
@app.get("/marketfeed/ltp")
def ltp(symbol: str = Query(..., description="e.g. NSE:HDFCBANK or NSE:NIFTY 50")):
    """
    Example LTP via Dhan quote endpoint (adjust as per the asset).
    For NSE stocks use security_id; for indices you might need derived price
    or a dedicated endpoint if available.
    This route is left generic and returns a placeholder for now.
    """
    # You can wire your own symbol->securityId map and call Dhan quote APIs.
    return {"status": "todo", "hint": "Map symbol to securityId and call Dhan quote API."}

# -------------------------------------------------
# Option chain
# -------------------------------------------------
@app.post("/option-chain/expirylist")
def option_chain_expiry_list(body: ExpiryListIn = Body(...)):
    """
    Proxy to Dhan v2: POST /v2/option-chain/expiry-list
    body: { under_security_id, under_exchange_segment }
    """
    return dh_post("option-chain/expiry-list", body.dict())


@app.post("/option-chain")
def option_chain(body: OptionChainIn = Body(...)):
    """
    Proxy to Dhan v2: POST /v2/option-chain
    body: { under_security_id, under_exchange_segment, expiry_date }
    """
    return dh_post("option-chain", body.dict())

# -------------------------------------------------
# Convenience GET wrappers for your UI (so you can call with query params)
# -------------------------------------------------
@app.get("/optionchain/expirylist")
def expirylist_query(
    under_security_id: str = Query(...),
    under_exchange_segment: str = Query(...),
):
    payload = {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment,
    }
    return dh_post("option-chain/expiry-list", payload)


@app.get("/optionchain")
def optionchain_query(
    under_security_id: str = Query(...),
    under_exchange_segment: str = Query(...),
    expiry_date: str = Query(...),
):
    payload = {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment,
        "expiry_date": expiry_date,
    }
    return dh_post("option-chain", payload)

# -------------------------------------------------
# AI sample (placeholder)
# -------------------------------------------------
@app.post("/ai/test")
def ai_test(prompt: Dict[str, Any]):
    # Keep minimal to avoid background calls if OPENAI_API_KEY missing.
    return {"ok": True, "echo": prompt, "note": "Wire OpenAI here if needed."}

# -------------------------------------------------
# Self-test: verifies hyphenated paths & envs
# -------------------------------------------------
@app.get("/__selftest")
def selftest(symbol: str = "NIFTY"):
    status = ok_status()
    result: Dict[str, Any] = {"ok": True, "status": status}

    # Pick mapping
    imap = INDEX_MAP.get(symbol.upper())
    if not imap:
        result["sample_expirylist"] = {"status": "skip", "reason": f"Unknown symbol {symbol}"}
        return result

    sample = dh_post("option-chain/expiry-list", imap)
    result["sample_expirylist"] = sample
    return result


# -------------------------------------------------
# Dev server
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
