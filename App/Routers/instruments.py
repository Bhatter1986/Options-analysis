# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query
from App.Services.dhan_client import (
    get_instruments_csv,
    get_instruments_by_segment,
    search_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])

@router.get("", summary="List instruments (head)")
def list_instruments(limit: int = Query(1000, ge=1, le=10000)):
    return {"ok": True, "items": get_instruments_csv(limit=limit)}

@router.get("/by_segment", summary="Filter by Dhan segment")
def by_segment(segment: str = Query(..., description="e.g. NSE_EQ | NSE_FNO | BSE_EQ"),
               limit: int = Query(5000, ge=1, le=20000)):
    items = get_instruments_by_segment(segment=segment, limit=limit)
    return {"ok": True, "segment": segment, "count": len(items), "items": items}

@router.get("/search", summary="Search by symbol/name")
def search(q: str = Query(..., min_length=1), limit: int = Query(50, ge=1, le=200)):
    items = search_instruments(q=q, limit=limit)
    return {"ok": True, "q": q, "count": len(items), "items": items}
