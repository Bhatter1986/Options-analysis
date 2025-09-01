from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from App.Services.dhan_client import get_ltp, get_ohlc, get_quote

router = APIRouter(prefix="/marketquote", tags=["Market Quote"])

@router.post("/ltp")
async def ltp(data: Dict[str, Any] = Body(...)):
    """Fetch LTP for given instruments"""
    try:
        return await get_ltp(data)
    except Exception as e:
        raise HTTPException(502, f"LTP fetch failed: {e}")

@router.post("/ohlc")
async def ohlc(data: Dict[str, Any] = Body(...)):
    """Fetch OHLC for given instruments"""
    try:
        return await get_ohlc(data)
    except Exception as e:
        raise HTTPException(502, f"OHLC fetch failed: {e}")

@router.post("/quote")
async def quote(data: Dict[str, Any] = Body(...)):
    """Fetch Market Quote (with depth, OI, volume)"""
    try:
        return await get_quote(data)
    except Exception as e:
        raise HTTPException(502, f"Quote fetch failed: {e}")
