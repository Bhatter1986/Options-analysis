import os
import json
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ============== Env & Mode ==============
load_dotenv()

MODE = os.getenv("MODE", "LIVE").upper().strip()  # LIVE | SANDBOX
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Dhan LIVE
DHAN_LIVE_BASE_URL = os.getenv("DHAN_LIVE_BASE_URL", "https://api.dhan.co/v2")
DHAN_LIVE_ACCESS_TOKEN = os.getenv("DHAN_LIVE_ACCESS_TOKEN", "")
DHAN_LIVE_CLIENT_ID = os.getenv("DHAN_LIVE_CLIENT_ID", "")

# Dhan SANDBOX
DHAN_SANDBOX_BASE_URL = os.getenv("DHAN_SANDBOX_BASE_URL", "https://sandbox.dhan.co/v2")
DHAN_SANDBOX_ACCESS_TOKEN = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN", "")
DHAN_SANDBOX_CLIENT_ID = os.getenv("DHAN_SANDBOX_CLIENT_ID", "")

# ============== Try SDK, else HTTP fallback ==============
_USE_SDK = False
_DHAN_SDK = None
try:
    # agar tumne local sdk file ka naam `dhanhq.py` rakha hai to ye bhi kaam karega
    import dhanhq as _DHAN_SDK  # type: ignore
    _USE_SDK = True
except Exception:
    _USE_SDK = False

import requests

def _active_creds() -> Dict[str, str]:
    if MODE == "LIVE":
        return dict(
            base=DHAN_LIVE_BASE_URL.rstrip("/"),
            token=DHAN_LIVE_ACCESS_TOKEN.strip(),
            client_id=DHAN_LIVE_CLIENT_ID.strip(),
        )
    else:
        return dict(
            base=DHAN_SANDBOX_BASE_URL.rstrip("/"),
            token=DHAN_SANDBOX_ACCESS_TOKEN.strip(),
            client_id=DHAN_SANDBOX_CLIENT_ID.strip(),
        )

class DhanClient:
    """SDK if present, else clean HTTP wrapper."""

    def __init__(self):
        self.creds = _active_creds()

        # optional: if SDK present and offers a client init
        self.sdk = None
        if _USE_SDK:
            try:
                # adjust if your SDK constructor differs
                self.sdk = _DHAN_SDK.Dhan(self.creds["client_id"], self.creds["token"])
            except Exception:
                self.sdk = None

    # ---- HTTP generic helpers ----
    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "access-token": self.creds["token"],
        }

    def http_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f'{self.creds["base"]}/{path.lstrip("/")}'
        try:
            r = requests.post(url, headers=self._headers(), json=payload, timeout=15)
            if r.headers.get("content-type", "").startswith("application/json"):
                return dict(status="success" if r.ok else "error",
                            code=r.status_code, data=r.json())
            else:
                return dict(status="error", code=r.status_code,
                            body=dict(raw=r.text))
        except Exception as e:
            return dict(status="error", error=str(e))

    def http_get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f'{self.creds["base"]}/{path.lstrip("/")}'
        try:
            r = requests.get(url, headers=self._headers(), params=params, timeout=15)
            if r.headers.get("content-type", "").startswith("application/json"):
                return dict(status="success" if r.ok else "error",
                            code=r.status_code, data=r.json())
            else:
                return dict(status="error", code=r.status_code,
                            body=dict(raw=r.text))
        except Exception as e:
            return dict(status="error", error=str(e))

    # ---- High-level API wrappers (use SDK if you like) ----
    def expiry_list(self, under_security_id: str, under_exchange_segment: str):
        # HTTP fallback (correct path):
        payload = {
            "under_security_id": str(under_security_id),
            "under_exchange_segment": str(under_exchange_segment),
        }
        return self.http_post("option-chain/expiry-list", payload)

    def option_chain(self, under_security_id: str, under_exchange_segment: str, expiry: str):
        payload = {
            "under_security_id": str(under_security_id),
            "under_exchange_segment": str(under_exchange_segment),
            "expiry": str(expiry),
        }
        return self.http_post("option-chain", payload)

    def ltp(self, security_id: str, exchange_segment: str):
        # Some Dhan feeds take POST with list; we'll keep single & list both
        # POST: /marketfeed/ltp  body: {"symbols":[{"security_id":"...","exchange_segment":"..."}]}
        body = {"symbols": [{"security_id": str(security_id), "exchange_segment": str(exchange_segment)}]}
        return self.http_post("marketfeed/ltp", body)

# single shared client
dhan = DhanClient()

# ============== FastAPI app ==============
app = FastAPI(title="Options-analysis (Dhan v2 + AI)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ======= Models (for JSON bodies if calling from frontend as POST) =======
class ExpiryListReq(BaseModel):
    under_security_id: str
    under_exchange_segment: str

class OptionChainReq(ExpiryListReq):
    expiry: str

class LTPReq(BaseModel):
    security_id: str
    exchange_segment: str

# ============== Root & health ==============
@app.get("/")
def root():
    return {
        "app": "Options-analysis (Dhan v2 + AI)",
        "mode": MODE,
        "env": "LIVE" if MODE == "LIVE" else "SANDBOX",
        "endpoints": [
            "/health",
            "/broker_status",
            "/optionchain/expirylist",
            "/optionchain",
            "/marketfeed/ltp",
            "/__selftest",
        ],
    }

@app.get("/health")
def health():
    return {"ok": True, "mode": MODE}

@app.get("/broker_status")
def broker_status():
    creds = _active_creds()
    return {
        "mode": MODE,
        "token_present": bool(creds["token"]),
        "client_id_present": bool(creds["client_id"]),
        "openai_present": bool(OPENAI_API_KEY),
    }

# ============== Option-chain ==============
@app.get("/optionchain/expirylist")
def get_expirylist(
    under_security_id: str = Query(...),
    under_exchange_segment: str = Query(...),
):
    return dhan.expiry_list(under_security_id, under_exchange_segment)

@app.post("/optionchain/expirylist")
def post_expirylist(body: ExpiryListReq):
    return dhan.expiry_list(body.under_security_id, body.under_exchange_segment)

@app.get("/optionchain")
def get_optionchain(
    under_security_id: str = Query(...),
    under_exchange_segment: str = Query(...),
    expiry: str = Query(...),
):
    return dhan.option_chain(under_security_id, under_exchange_segment, expiry)

@app.post("/optionchain")
def post_optionchain(body: OptionChainReq):
    return dhan.option_chain(body.under_security_id, body.under_exchange_segment, body.expiry)

# ============== Marketfeed LTP ==============
@app.get("/marketfeed/ltp")
def get_ltp(
    security_id: str = Query(...),
    exchange_segment: str = Query(...),
):
    return dhan.ltp(security_id, exchange_segment)

@app.post("/marketfeed/ltp")
def post_ltp(body: LTPReq):
    return dhan.ltp(body.security_id, body.exchange_segment)

# ============== Self-test ==============
@app.get("/__selftest")
def selftest():
    creds = _active_creds()
    status = {
        "env": True,
        "mode": MODE,
        "token_present": bool(creds["token"]),
        "client_id_present": bool(creds["client_id"]),
        "openai_present": bool(OPENAI_API_KEY),
    }

    # Sample: NIFTY (IDX_I) -> under_security_id "13" (update if tumhara mapping alag ho)
    sample_payload = {
        "under_security_id": "13",
        "under_exchange_segment": "IDX_I",
    }
    probe = dhan.http_post("option-chain/expiry-list", sample_payload)

    return {
        "ok": True,
        "status": status,
        "sample_expirylist": probe,
    }
