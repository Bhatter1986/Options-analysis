# App/Routers/instruments.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from App.Services.dhan_client import (
    get_instruments_csv,
    get_instruments_by_segment,   # kept for compatibility (uses same CSV)
    search_instruments,
)

router = APIRouter(prefix="", tags=["instruments"])

@router.get("/instruments")
def instruments(segment: Optional[str] = Query(None, description="e.g. NSE_EQ / NSE_FNO / IDX_I"),
                limit: int = Query(200, ge=1, le=10000)):
    """
    Dhan CSV se instruments (optional segment filter).
    """
    rows, meta = get_instruments_csv(segment)
    return {
        "ok": True,
        "segment": segment,
        "count": meta["count"],
        "meta": meta,
        "data": rows[:limit],
    }

@router.get("/instruments/segment/{segment}")
def instruments_by_segment(segment: str, limit: int = Query(200, ge=1, le=10000)):
    """
    Backward compatible path (uses same CSV).
    """
    rows, meta = get_instruments_by_segment(segment)
    return {
        "ok": True,
        "segment": segment,
        "count": meta["count"],
        "meta": meta,
        "data": rows[:limit],
    }

@router.get("/instruments/search")
def instruments_search(symbol: str = Query(..., description="keyword like 'INFY'"),
                       segment: Optional[str] = Query(None),
                       limit: int = Query(50, ge=1, le=500)):
    """
    Symbol/Name contains search using Dhan CSV.
    """
    rows, meta = search_instruments(symbol, segment=segment, limit=limit)
    return {
        "ok": True,
        "query": symbol,
        "segment": segment,
        "count": meta["count"],
        "meta": meta,
        "data": rows,
    }
