import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
import httpx

app = FastAPI(title="Dhan Proxy", version="1.0")

DHAN_BASE_URL = os.getenv("DHAN_BASE_URL", "https://sandbox.dhan.co/v2")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")

# ---- Models ----
class OptionChainReq(BaseModel):
    UnderlyingScrip: int = Field(..., description="Security ID of Underlying")
    UnderlyingSeg: str = Field(..., description="e.g. IDX_I / NSE_FNO / etc.")
    Expiry: Optional[str] = Field(None, description="YYYY-MM-DD (optional for expirylist)")

class BrokerStatus(BaseModel):
    mode: str
    env: str
    base_url: str
    token_present: bool
    client_id_present: bool
    has_creds: bool

# ---- Helpers ----
def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h

def _check_creds():
    if not DHAN_ACCESS_TOKEN or not DHAN_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Missing DHAN_ACCESS_TOKEN or DHAN_CLIENT_ID env vars.")

# ---- Health / status ----
@app.get("/broker_status", response_model=BrokerStatus)
def broker_status():
    return BrokerStatus(
        mode="DRY",
        env="SANDBOX" if "sandbox" in DHAN_BASE_URL else "LIVE",
        base_url=DHAN_BASE_URL,
        token_present=bool(DHAN_ACCESS_TOKEN),
        client_id_present=bool(DHAN_CLIENT_ID),
        has_creds=bool(DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID),
    )

# ---- Pass-through: Orders (GET) ----
@app.get("/orders")
async def get_orders():
    _check_creds()
    url = f"{DHAN_BASE_URL}/orders"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

# ---- Option Chain ----
@app.post("/optionchain")
async def option_chain(body: OptionChainReq):
    _check_creds()
    url = f"{DHAN_BASE_URL}/optionchain"
    payload = {
        "UnderlyingScrip": body.UnderlyingScrip,
        "UnderlyingSeg": body.UnderlyingSeg,
    }
    if body.Expiry:
        payload["Expiry"] = body.Expiry

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=_headers(), json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

# ---- Expiry List ----
@app.post("/optionchain/expirylist")
async def expiry_list(body: OptionChainReq):
    _check_creds()
    url = f"{DHAN_BASE_URL}/optionchain/expirylist"
    payload = {
        "UnderlyingScrip": body.UnderlyingScrip,
        "UnderlyingSeg": body.UnderlyingSeg,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=_headers(), json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()
