# App/Routers/optionchain.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os, time, httpx
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/optionchain", tags=["optionchain"])

DHAN_BASE = "https://dhan-api.co.in"  # DhanHQ v2 base
DHAN_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
DHAN_CLIENT = os.getenv("DHAN_CLIENT_ID", "").strip()

# --- simple rate limit: 1 call per 3s (Dhan guideline)
_LAST_HIT: float = 0.0
def _throttle():
    global _LAST_HIT
    delay = 3.0 - (time.time() - _LAST_HIT)
    if delay > 0: time.sleep(delay)
    _LAST_HIT = time.time()

def _auth_headers() -> Dict[str, str]:
    if not DHAN_TOKEN or not DHAN_CLIENT:
        raise HTTPException(503, detail="Dhan credentials missing (set DHAN_ACCESS_TOKEN & DHAN_CLIENT_ID).")
    return {
        "access-token": DHAN_TOKEN,
        "client-id": DHAN_CLIENT,
        "content-type": "application/json",
    }

# ------------- Models -------------
class ExpiryRequest(BaseModel):
    UnderlyingScrip: int        # e.g. 2=NIFTY, 25=BANKNIFTY
    UnderlyingSeg: str          # e.g. "IDX_I"  (index options)
    # (Dhan doc: first call expirylist, then pass one expiry to /optionchain)

class ChainRequest(ExpiryRequest):
    Expiry: str                 # "YYYY-MM-DD"

# ------------- Helpers -------------
async def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _throttle()
    headers = _auth_headers()
    url = f"{DHAN_BASE}{path}"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, detail=f"{path} failed: {r.text}")
        try:
            return r.json()
        except Exception:
            raise HTTPException(502, detail=f"{path} returned non-JSON")

# ------------- Endpoints -------------

@router.get("/_debug")
def debug_status() -> Dict[str, Any]:
    return {
        "env_has_token": bool(DHAN_TOKEN),
        "env_has_client_id": bool(DHAN_CLIENT),
        "rate_limit": "1 req / 3s",
        "notes": "Use /optionchain/expirylist first, then /optionchain with Expiry.",
    }

@router.post("/expirylist")
async def expiry_list(req: ExpiryRequest) -> Dict[str, Any]:
    """
    POST -> Dhan /v2/option-chain/expirylist
    Body: { UnderlyingScrip, UnderlyingSeg }
    """
    # Sandbox shortcut
    if not DHAN_TOKEN or not DHAN_CLIENT:
        # mock expiries (7,14,21,28 days)
        today = time.strftime("%Y-%m-%d", time.gmtime())
        return {"data": [today], "status": "sandbox-mock"}
    data = await _post_json("/v2/option-chain/expirylist", req.dict())
    return data

@router.post("")
async def option_chain(req: ChainRequest) -> Dict[str, Any]:
    """
    POST -> Dhan /v2/option-chain
    Body: { UnderlyingScrip, UnderlyingSeg, Expiry }
    """
    if not DHAN_TOKEN or not DHAN_CLIENT:
        # small mock so UI doesn't break in SANDBOX
        return {
            "data": {
                "last_price": 25000.0,
                "oc": {
                    "25000": {
                        "CE": {"implied_volatility": 18.2, "last_price": 120.5, "oi": 1000, "previous_oi": 900, "volume": 5000},
                        "PE": {"implied_volatility": 19.9, "last_price": 115.0, "oi": 1200, "previous_oi": 1100, "volume": 5200},
                    }
                },
            },
            "status": "sandbox-mock",
        }
    payload = req.dict()
    data = await _post_json("/v2/option-chain", payload)
    return data
