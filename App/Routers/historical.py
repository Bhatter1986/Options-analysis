# App/Routers/historical.py
from __future__ import annotations
from fastapi import APIRouter, Body, HTTPException
from typing import Any, Dict

from App.Services.dhan_client import get_historical_daily, get_historical_intraday

router = APIRouter(prefix="/historical", tags=["Historical Data"])

@router.post("/daily")
async def historical_daily(body: Dict[str, Any] = Body(...)):
    """
    Proxy to Dhan /charts/historical
    Example body:
    {
      "securityId": "1333",
      "exchangeSegment": "NSE_EQ",
      "instrument": "EQUITY",
      "expiryCode": 0,
      "oi": False,
      "fromDate": "2024-01-01",
      "toDate": "2024-12-31"
    }
    """
    try:
        return await get_historical_daily(body)
    except Exception as e:
        raise HTTPException(502, f"Dhan historical daily failed: {e}")

@router.post("/intraday")
async def historical_intraday(body: Dict[str, Any] = Body(...)):
    """
    Proxy to Dhan /charts/intraday
    Example body:
    {
      "securityId": "1333",
      "exchangeSegment": "NSE_EQ",
      "instrument": "EQUITY",
      "interval": "5",
      "oi": False,
      "fromDate": "2025-08-25 09:15:00",
      "toDate": "2025-09-01 15:30:00"
    }
    """
    try:
        return await get_historical_intraday(body)
    except Exception as e:
        raise HTTPException(502, f"Dhan historical intraday failed: {e}")
