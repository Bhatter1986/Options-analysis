# App/Routers/dhan.py
from fastapi import APIRouter, Query
from typing import Optional, Dict, Any
from App.Services.dhan_client import get_json, DHAN_BASE_URL, DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN

router = APIRouter(prefix="/dhan", tags=["dhan"])

@router.get("/health")
async def dhan_health():
    return {
        "ok": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN),
        "base_url": DHAN_BASE_URL,
        "has_client_id": bool(DHAN_CLIENT_ID),
        "has_access_token": bool(DHAN_ACCESS_TOKEN),
        "tip": "Use /dhan/get?path=/market...&symbol=... to call Dhan endpoints",
    }

@router.get("/get")
async def dhan_get(
    path: str = Query(..., description="Dhan API path e.g. /market/quotes"),
    **params: Dict[str, Any],
):
    """
    Generic GET to Dhan with allow-listed prefixes. Forward any query params.
    Example:
      /dhan/get?path=/market/quotes&symbol=NIFTY
    """
    return await get_json(path, params)

# Convenience wrappers (optional) -> fill correct paths for your Dhan account
@router.get("/quotes")
async def quotes(symbol: str):
    # Example path; adjust to your Dhan endpoint once confirmed
    return await get_json("/market/quotes", {"symbol": symbol})

@router.get("/optionchain")
async def optionchain(symbol: str, expiry: Optional[str] = None):
    params = {"symbol": symbol}
    if expiry:
        params["expiry"] = expiry
    return await get_json("/option/chain", params)

@router.get("/historical")
async def historical(symbol: str, interval: str = "1m", start: str = "", end: str = ""):
    # Adjust path/param names to your Dhan docs
    params = {"symbol": symbol, "interval": interval}
    if start: params["start"] = start
    if end:   params["end"] = end
    return await get_json("/chart/history", params)
