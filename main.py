import os
import time
from typing import Dict, Any, List, Optional

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --------------------------- Boot ---------------------------
load_dotenv()

APP_NAME = "Options-analysis (Dhan v2 + AI)"
APP_VERSION = "2.1.0"

MODE = os.getenv("MODE", "LIVE").upper().strip()  # LIVE | SANDBOX

DHAN_BASE_URL = "https://api.dhan.co/v2" if MODE == "LIVE" else "https://sandbox.dhan.co/v2"
DHAN_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN") if MODE == "LIVE" else os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID") if MODE == "LIVE" else os.getenv("DHAN_SANDBOX_CLIENT_ID")

OPENAI_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "15"))

# Common index/security mapping (Dhan)
INDEX_MAP = {
    "NIFTY": {"under_security_id": "13", "under_exchange_segment": "IDX_I"},
    "BANKNIFTY": {"under_security_id": "25", "under_exchange_segment": "IDX_I"},
    "FINNIFTY": {"under_security_id": "27", "under_exchange_segment": "IDX_I"},
}

# --------------------------- App ---------------------------
app = FastAPI(title=APP_NAME, version=APP_VERSION)

# CORS (frontend direct calls allowed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------- Helpers ---------------------------
def _headers() -> Dict[str, str]:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "access-token": DHAN_TOKEN or "",
    }

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST to DHAN, handle errors uniformly."""
    url = f"{DHAN_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.post(url, headers=_headers(), json=payload, timeout=HTTP_TIMEOUT)
        if r.status_code >= 400:
            return {
                "status": "error",
                "code": r.status_code,
                "url": url,
                "payload": payload,
                "body": _safe_json(r),
            }
        return _safe_json(r)
    except requests.RequestException as e:
        return {"status": "error", "msg": str(e), "url": url, "payload": payload}

def _get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """GET to DHAN, handle errors uniformly."""
    url = f"{DHAN_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=HTTP_TIMEOUT)
        if r.status_code >= 400:
            return {
                "status": "error",
                "code": r.status_code,
                "url": url,
                "params": params,
                "body": _safe_json(r),
            }
        return _safe_json(r)
    except requests.RequestException as e:
        return {"status": "error", "msg": str(e), "url": url, "params": params}

def _safe_json(r: requests.Response) -> Dict[str, Any]:
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}

def _map_symbol(symbol: str) -> Dict[str, str]:
    return INDEX_MAP.get(symbol.upper().strip(), INDEX_MAP["NIFTY"]).copy()

# --------------------------- Routes ---------------------------
@app.get("/")
def root():
    return {
        "app": f"{APP_NAME}",
        "version": APP_VERSION,
        "mode": MODE,
        "env": MODE,
        "endpoints": [
            "/health",
            "/broker_status",
            "/optionchain/expirylist",
            "/optionchain_raw",
            "/optionchain",
            "/marketfeed/ltp",
            "/ai/strategy",
            "/ai/recommendations",
            "/ai/payoff",
            "/__selftest",
        ],
    }

@app.get("/__selftest")
def selftest():
    """Lightweight environment & network check (no order placement)."""
    status = {
        "env": MODE == MODE,  # always True; just placeholder flag
        "mode": MODE,
        "token_present": bool(DHAN_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "openai_present": OPENAI_PRESENT,
    }
    # Try a tiny real call (expiry-list for NIFTY)
    ping = _post("optionchain/expiry-list", {
        "under_security_id": INDEX_MAP["NIFTY"]["under_security_id"],
        "under_exchange_segment": INDEX_MAP["NIFTY"]["under_exchange_segment"],
    })
    return {"ok": True, "status": status, "sample_expirylist": ping}

@app.get("/health")
def health():
    return {"status": "ok", "ts": int(time.time()), "mode": MODE}

@app.get("/broker_status")
def broker_status():
    return {
        "mode": MODE,
        "token_present": bool(DHAN_TOKEN),
        "client_id_present": bool(DHAN_CLIENT_ID),
        "openai_present": OPENAI_PRESENT,
        "base_url": DHAN_BASE_URL,
    }

# ---------- Option Chain: Expiry List ----------
@app.get("/optionchain/expirylist")
def expiry_list(
    under_security_id: str = Query("13", description="default NIFTY"),
    under_exchange: str = Query("IDX_I", description="IDX_I for indices"),
):
    payload = {"under_security_id": under_security_id, "under_exchange_segment": under_exchange}
    return _post("optionchain/expiry-list", payload)

# ---------- Option Chain: Raw ----------
@app.get("/optionchain_raw")
def optionchain_raw(
    symbol: str = Query("NIFTY", enum=list(INDEX_MAP.keys())),
    expiry: Optional[str] = Query(None, description="YYYY-MM-DD; if missing, near expiry may be used by DHAN"),
):
    payload = _map_symbol(symbol)
    if expiry:
        payload["expiry"] = expiry
    return _post("optionchain", payload)

# ---------- Option Chain: Normalized ----------
@app.get("/optionchain")
def optionchain(
    symbol: str = Query("NIFTY", enum=list(INDEX_MAP.keys())),
    expiry: str = Query(..., description="YYYY-MM-DD"),
):
    raw = optionchain_raw(symbol, expiry)
    # If upstream error, bubble it up
    if isinstance(raw, dict) and raw.get("status") == "error":
        return {"status": "error", "upstream": raw}

    # Dhan data wrapper usually like {"status":"success","data":{"status":"success","data":[...]}}
    rows: List[Dict[str, Any]] = []
    data = (
        raw.get("data", {})
        if isinstance(raw, dict) else {}
    )
    # handle both shapes: {"status":...,"data":{"data":[...]}} or {"data":[...]}
    if isinstance(data, dict) and "data" in data:
        oc_list = data.get("data", [])
    else:
        oc_list = raw.get("data", []) if isinstance(raw, dict) else []

    for row in oc_list or []:
        ce = row.get("ce", {}) or {}
        pe = row.get("pe", {}) or {}
        rows.append({
            "strike": row.get("strikePrice"),
            "ce": {
                "oi": ce.get("openInterest", 0),
                "chngOi": ce.get("changeInOI", 0),
                "iv": ce.get("iv", 0.0),
                "ltp": ce.get("ltp", 0.0),
                "volume": ce.get("totalTradedVolume", 0),
            },
            "pe": {
                "oi": pe.get("openInterest", 0),
                "chngOi": pe.get("changeInOI", 0),
                "iv": pe.get("iv", 0.0),
                "ltp": pe.get("ltp", 0.0),
                "volume": pe.get("totalTradedVolume", 0),
            },
        })

    return {
        "status": "success",
        "symbol": symbol.upper(),
        "expiry": expiry,
        "records": rows,
        "raw_status": raw.get("status"),
    }

# ---------- Marketfeed: LTP (simple passthrough) ----------
@app.get("/marketfeed/ltp")
def marketfeed_ltp(
    security_id: str = Query("11536", description="Dhan security_id (example value)"),
    exchange_segment: str = Query("NSE_EQ", description="e.g., NSE_EQ / BSE_EQ / IDX_I"),
):
    # Shape per Dhan doc (marketfeed LTP) may vary; we keep simple wrapper
    payload = {"instruments": [{"securityId": security_id, "exchangeSegment": exchange_segment}]}
    return _post("marketfeed/ltp", payload)

# ---------- AI Placeholders ----------
@app.get("/ai/strategy")
def ai_strategy():
    return {"msg": "AI strategy endpoint placeholder — plug your LLM here."}

@app.get("/ai/recommendations")
def ai_recommend():
    return {"msg": "AI recommendations placeholder — plug your LLM here."}

@app.get("/ai/payoff")
def ai_payoff():
    return {"msg": "AI payoff endpoint placeholder — returns payoff array later."}
