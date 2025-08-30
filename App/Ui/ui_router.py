from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import httpx
import os

router = APIRouter(prefix="/ui/api", tags=["ui-api"])

DHAN_URL = os.getenv("DHAN_LIVE_URL", "https://api.dhan.co/v2")
APP_BASE = ""  # same app base; we’ll call our own routes

async def _fetch_json(url: str, params: dict):
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"upstream error {r.status_code}: {r.text[:200]}")
        return r.json()

@router.get("/expiry-dates", response_model=List[str])
async def expiry_dates(
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query("IDX_I"),
):
    # call existing internal route
    data = await _fetch_json(
        f"{APP_BASE}/optionchain/expirylist",
        {"under_security_id": under_security_id, "under_exchange_segment": under_exchange_segment},
    )
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data  # already a list

@router.get("/option-chain")
async def option_chain(
    expiry: str = Query(...),
    under_security_id: int = Query(...),
    under_exchange_segment: str = Query("IDX_I"),
):
    return await _fetch_json(
        f"{APP_BASE}/optionchain",
        {
            "expiry": expiry,
            "under_security_id": under_security_id,
            "under_exchange_segment": under_exchange_segment,
        },
    )

@router.get("/market-data")
async def market_data():
    # Simple mock; replace with your feed later
    return {
        "nifty": {"value": 24410.15, "change": 0.12, "volume": 123_400_000},
        "banknifty": {"value": 52510.35, "change": -0.18, "volume": 98_700_000},
    }
