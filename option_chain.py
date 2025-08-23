# option_chain.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any
import httpx
import os

app = FastAPI(
    title="DhanHQ Option Chain Proxy",
    version="2.0",
    description="Proxy service for DhanHQ Option Chain API (official format)",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENVIRONMENT PICKER ---
def _pick_env() -> Dict[str, Optional[str]]:
    env = (os.getenv("DHAN_ENV") or "SANDBOX").strip().upper()
    if env not in {"SANDBOX", "LIVE"}:
        env = "SANDBOX"

    if env == "LIVE":
        token = os.getenv("DHAN_LIVE_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_LIVE_CLIENT_ID")
        base_url = "https://api.dhan.co/v2"
    else:
        token = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_SANDBOX_CLIENT_ID")
        base_url = "https://sandbox.dhan.co/v2"

    return {"env": env, "token": token, "client_id": client_id, "base_url": base_url}

def _make_headers(token: str, client_id: str) -> Dict[str, str]:
    return {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

async def _proxy_request(path: str, payload: Dict[str, Any]) -> JSONResponse:
    cfg = _pick_env()
    token, client_id, base_url = cfg["token"], cfg["client_id"], cfg["base_url"]

    if not token or not client_id:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Missing Dhan credentials"})

    url = f"{base_url}{path}"
    headers = _make_headers(token, client_id)

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return JSONResponse(status_code=502, content={"ok": False, "error": str(exc)})

    try:
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    except ValueError:
        return JSONResponse(status_code=resp.status_code, content={"ok": False, "error": resp.text})

# --- Request Models (official Dhan format) ---
class OptionChainRequest(BaseModel):
    UnderlyingScrip: int = Field(..., description="Security ID of Underlying Instrument")
    UnderlyingSeg: str = Field(..., description="Exchange & segment (e.g. IDX_I, NSE_FNO)")
    Expiry: str = Field(..., description="Expiry Date (YYYY-MM-DD)")

    class Config:
        schema_extra = {
            "example": {
                "UnderlyingScrip": 13,
                "UnderlyingSeg": "IDX_I",
                "Expiry": "2024-10-31"
            }
        }

class ExpiryListRequest(BaseModel):
    UnderlyingScrip: int = Field(..., description="Security ID of Underlying Instrument")
    UnderlyingSeg: str = Field(..., description="Exchange & segment (e.g. IDX_I, NSE_FNO)")

    class Config:
        schema_extra = {
            "example": {
                "UnderlyingScrip": 13,
                "UnderlyingSeg": "IDX_I"
            }
        }

# --- Endpoints ---
@app.post("/optionchain", tags=["Option Chain"])
async def option_chain(request: OptionChainRequest):
    """Fetch Option Chain (official Dhan format)"""
    return await _proxy_request("/optionchain", request.dict())

@app.post("/optionchain/expirylist", tags=["Option Chain"])
async def option_chain_expirylist(request: ExpiryListRequest):
    """Fetch available expiry dates (official Dhan format)"""
    return await _proxy_request("/optionchain/expirylist", request.dict())

# --- Health ---
@app.get("/health")
async def health():
    return {"ok": True}
