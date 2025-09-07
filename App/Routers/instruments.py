# App/Routers/instruments.py
from __future__ import annotations
from fastapi import APIRouter, Query
from App.Services.dhan_client import (
    get_instruments_csv,
    get_instruments_by_segment,  # <- this is now defined
    search_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", summary="All Dhan instruments (detailed CSV, cached)")
def instruments_all(limit: int = Query(0, ge=0, description="0 = no limit")):
    rows = get_instruments_csv(detailed=True)
    if limit and limit > 0:
        rows = rows[:limit]
    return {"source": "dhan_csv_detailed", "count": len(rows), "items": rows}


@router.get("/segment", summary="Instruments by segment (NSE / BSE / MCX / NSEFO, etc.)")
def instruments_by_segment(
    segment: str = Query(..., description="e.g. NSE, BSE, MCX, NSEFO, NSE-D, BSE-E"),
    limit: int = Query(0, ge=0),
):
    rows = get_instruments_by_segment(segment, detailed=True)
    if limit and limit > 0:
        rows = rows[:limit]
    return {"source": "dhan_csv_detailed", "segment": segment, "count": len(rows), "items": rows}


@router.get("/search", summary="Search instruments (case-insensitive)")
def instruments_search(
    q: str = Query(..., description="query text"),
    segment: str | None = Query(None, description="optional: NSE, NSEFO, BSE-E..."),
    limit: int = Query(50, ge=1, le=500),
):
    rows = search_instruments(q, segment=segment, detailed=True, limit=limit)
    return {"source": "dhan_csv_detailed", "segment": segment, "query": q, "count": len(rows), "items": rows}
