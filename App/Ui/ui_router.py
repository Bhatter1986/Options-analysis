from __future__ import annotations
import os, json
from typing import List, Dict, Any
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/ui", tags=["ui"])

BASE_URL = os.getenv("BASE_URL", "")  # same host (Render ingress)
# backend endpoints are on same app, so we can call relative paths
DHAN_EXPIRYLIST = "/optionchain/expirylist"
DHAN_CHAIN = "/optionchain"

STATIC_ROOT = os.path.join(os.path.dirname(__file__), "static")

def _static(path: str) -> str:
    return os.path.join(STATIC_ROOT, path)

@router.get("/")
async def ui_index():
    return FileResponse(_static("index.html"))

@router.get("/dashboard.html")
async def ui_dashboard():
    return FileResponse(_static("dashboard.html"))

# ---------- Proxy APIs for the dashboard ----------

@router.get("/api/expiry-dates")
async def api_expiry_dates(under_security_id: int = 25, under_exchange_segment: str = "IDX_I"):
    # defaults: BANKNIFTY / index options
    params = {"under_security_id": under_security_id, "under_exchange_segment": under_exchange_segment}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(DHAN_EXPIRYLIST, params=params, base_url=BASE_URL or None)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    payload = r.json()
    # Dhan wrapper shape: {"data": ["YYYY-MM-DD",...], "status":"success"}
    return JSONResponse(payload.get("data", []))

@router.get("/api/option-chain")
async def api_option_chain(expiry: str,
                           under_security_id: int = 25,
                           under_exchange_segment: str = "IDX_I") -> Any:
    params = {
        "under_security_id": under_security_id,
        "under_exchange_segment": under_exchange_segment,
        "expiry": expiry,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(DHAN_CHAIN, params=params, base_url=BASE_URL or None)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    data = r.json()  # {"data": {... strikes ...}, "status": "success"}

    # dashboard expects an array of rows [{strike, call:{}, put:{}}]
    strikes_map = (data or {}).get("data", {})
    rows = []
    for k, v in strikes_map.items():
        strike = float(k)
        ce = v.get("ce", {})
        pe = v.get("pe", {})
        rows.append({
            "strike": strike,
            "call": {
                "price": ce.get("last_price", 0),
                "oi": ce.get("oi", 0),
                "changeOi": (ce.get("oi", 0) or 0) - (ce.get("previous_oi", 0) or 0),
                "iv": ce.get("implied_volatility", 0),
            },
            "put": {
                "price": pe.get("last_price", 0),
                "oi": pe.get("oi", 0),
                "changeOi": (pe.get("oi", 0) or 0) - (pe.get("previous_oi", 0) or 0),
                "iv": pe.get("implied_volatility", 0),
            },
        })
    rows.sort(key=lambda x: x["strike"])
    return JSONResponse(rows)

@router.get("/api/market-data")
async def api_market_data_mock():
    # simple placeholder so cards load; replace later with your spot feed
    return {
        "nifty": {"value": 24450.00, "change": 0.35, "volume": 123_400_000},
        "banknifty": {"value": 51600.00, "change": -0.15, "volume": 98_700_000},
    }
