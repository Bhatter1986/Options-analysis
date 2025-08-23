# marketfeed.py
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import httpx
import os

router = APIRouter(prefix="", tags=["Market Data"])

# ── ENV helpers ────────────────────────────────────────────────────────────
def _pick_env():
    env = (os.getenv("DHAN_ENV") or "SANDBOX").strip().upper()
    if env not in {"SANDBOX", "LIVE"}:
        env = "SANDBOX"

    if env == "LIVE":
        token = os.getenv("DHAN_LIVE_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_LIVE_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        base_url = os.getenv("DHAN_LIVE_BASE_URL") or "https://api.dhan.co/v2"
    else:
        token = os.getenv("DHAN_SANDBOX_ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_SANDBOX_CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
        base_url = os.getenv("DHAN_SANDBOX_BASE_URL") or "https://sandbox.dhan.co/v2"

    return {"env": env, "token": token, "client_id": client_id, "base_url": base_url}

def _headers(token: str, client_id: str) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": token,
        "client-id": client_id,
    }

async def _proxy(path: str, payload: Dict[str, Any]):
    cfg = _pick_env()
    if not cfg["token"] or not cfg["client_id"]:
        return {
            "ok": False,
            "error": "Missing Dhan credentials",
            "details": {
                "env": cfg["env"],
                "token_present": bool(cfg["token"]),
                "client_id_present": bool(cfg["client_id"]),
            },
        }

    url = f'{cfg["base_url"]}{path}'
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload, headers=_headers(cfg["token"], cfg["client_id"]))
        except httpx.HTTPError as exc:
            return {"ok": False, "error": "Upstream HTTP error", "details": str(exc), "upstream": {"url": url}}

    try:
        return resp.json()
    except ValueError:
        return {"ok": False, "error": "Non-JSON response from Dhan", "status_code": resp.status_code, "text": resp.text}

# ── Request model (Dhan-format body) ───────────────────────────────────────
class MarketfeedBody(BaseModel):
    # Common segments; extra allowed so future segments bhi chale
    NSE_EQ: Optional[List[int]] = Field(None, description="NSE Equity security IDs")
    NSE_FNO: Optional[List[int]] = Field(None, description="NSE F&O security IDs")
    BSE_EQ: Optional[List[int]] = Field(None, description="BSE Equity security IDs")

    class Config:
        extra = "allow"  # e.g. MCX_FNO etc. ko allow kare
        schema_extra = {
            "example": {
                "NSE_EQ": [11536],
                "NSE_FNO": [49081, 49082]
            }
        }

# ── Endpoints (Dhan format) ────────────────────────────────────────────────
@router.post("/marketfeed/ltp")
async def marketfeed_ltp(body: MarketfeedBody):
    """POST /marketfeed/ltp — LTP snapshot (Dhan format passthrough)"""
    return await _proxy("/marketfeed/ltp", body.dict(exclude_none=True))

@router.post("/marketfeed/ohlc")
async def marketfeed_ohlc(body: MarketfeedBody):
    """POST /marketfeed/ohlc — OHLC + LTP snapshot"""
    return await _proxy("/marketfeed/ohlc", body.dict(exclude_none=True))

@router.post("/marketfeed/quote")
async def marketfeed_quote(body: MarketfeedBody):
    """POST /marketfeed/quote — depth + OI + OHLC + LTP"""
    return await _proxy("/marketfeed/quote", body.dict(exclude_none=True))
