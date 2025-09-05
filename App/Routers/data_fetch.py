# App/Routers/data_fetch.py
from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, Query

from App.Services.data_fetch.sources import get_live_snapshot
from App.Services.data_fetch.normalize import to_sudarshan_inputs

router = APIRouter(prefix="/data", tags=["data"])
VERSION = "0.1.0"

@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "name": "data_fetch", "version": VERSION}

@router.get("/snapshot")
def snapshot(
    symbol: str = Query(..., description="e.g. NIFTY, BANKNIFTY"),
    live: bool = Query(False, description="true = live hook, false = demo data"),
) -> Dict[str, Any]:
    """
    live=false: demo snapshot (same as before)
    live=true : use Services.data_fetch.sources.get_live_snapshot()
    """
    if live:
        raw = get_live_snapshot(symbol)
    else:
        raw = {
            "symbol": symbol.upper(),
            "price": {"trend": "bullish"},
            "oi": {"signal": "bullish"},
            "greeks": {"delta_bias": "long"},
            "volume": {"volume_spike": True, "confirmation": True},
            "sentiment": {"sentiment": "neutral"},
        }

    return {
        "symbol": raw["symbol"],
        "raw": raw,
        "sudarshan_inputs": to_sudarshan_inputs(raw),
    }
