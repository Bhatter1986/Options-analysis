# App/Routers/instruments.py
from __future__ import annotations
from fastapi import APIRouter, Query
from typing import Optional

from App.Services.dhan_client import (
    get_instruments,
    get_instruments_by_segment,   # <- ab AVAILABLE hai
    search_instruments,
    get_by_trading_symbol,
    get_by_security_id,
    refresh_instruments,
    get_cache_meta,
)

router = APIRouter(prefix="/instruments", tags=["Instruments"])

@router.get("/")
def meta():
    return {
        "ok": True,
        "message": "Dhan instruments endpoints",
        "endpoints": [
            "/instruments/all?limit=100",
            "/instruments/search?q=RELIANCE&limit=50",
            "/instruments/by-symbol?ts=NIFTY24SEP24000CE",
            "/instruments/by-security-id?id=XXXX",
            "/instruments/segment?exch=NSE&segment=D&limit=500",
            "/instruments/refresh",
            "/instruments/cache_meta",
        ],
    }

@router.get("/all")
def all_instruments(limit: int = Query(200, ge=1, le=10000)):
    rows = get_instruments()
    return {"ok": True, "count": len(rows), "items": rows[:limit]}

@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(100, ge=1, le=1000)):
    return {"ok": True, "items": search_instruments(q, limit=limit)}

@router.get("/by-symbol")
def by_symbol(ts: str = Query(..., min_length=1)):
    row = get_by_trading_symbol(ts)
    return {"ok": bool(row), "item": row}

@router.get("/by-security-id")
def by_security_id(id: str = Query(..., min_length=1)):
    row = get_by_security_id(id)
    return {"ok": bool(row), "item": row}

@router.get("/segment")
def by_segment(
    exch: Optional[str] = Query(None, description="NSE/BSE/MCX"),
    segment: Optional[str] = Query(None, description="E/D/C/M"),
    limit: int = Query(1000, ge=1, le=20000),
):
    items = get_instruments_by_segment(exch=exch, segment=segment, limit=limit)
    return {"ok": True, "count": len(items), "items": items[:limit]}

@router.post("/refresh")
def refresh():
    return refresh_instruments()

@router.get("/cache_meta")
def cache_meta():
    return get_cache_meta()
