# App/Routers/data_fetch.py
from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, Query

router = APIRouter(prefix="/data", tags=["data"])

VERSION = "0.1.0"

@router.get("/health")
def health() -> Dict[str, Any]:
    """
    Lightweight health endpoint for data_fetch router.
    """
    return {"ok": True, "name": "data_fetch", "version": VERSION}

@router.get("/snapshot")
def snapshot(symbol: str = Query(..., description="Index symbol e.g. NIFTY, BANKNIFTY")) -> Dict[str, Any]:
    """
    Demo snapshot endpoint.
    Future: Replace with live NSE/Dhan data feed.
    Current: Returns dummy Sudarshan-ready inputs.
    """
    return {
        "symbol": symbol,
        "sudarshan_inputs": {
            "price": {"trend": "bullish"},
            "oi": {"signal": "bullish"},
            "greeks": {"delta_bias": "long"},
            "volume": {"volume_spike": True, "confirmation": True},
            "sentiment": {"sentiment": "neutral"},
        },
    }
