# App/Routers/instruments.py
from __future__ import annotations
from fastapi import APIRouter, Query
from typing import Optional

from App.Services.dhan_client import (
    get_instruments_csv,
    get_instruments_by_segment,  # alias kept for compatibility
    search_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("")
def instruments_all(
    segment: Optional[str] = Query(None, description="Exchange/Segment e.g. NSE, BSE, MCX (Dhan CSV column match)"),
    limit: int = Query(0, ge=0, le=5000, description="Optional limit")
):
    rows = get_instruments_csv(segment=segment)
    return rows if not limit else rows[:limit]


@router.get("/segment")
def instruments_by_segment(
    segment: str = Query(..., description="Exchange/Segment e.g. NSE, BSE, MCX")
):
    return get_instruments_by_segment(segment)


@router.get("/search")
def instruments_search(
    q: str = Query(..., min_length=1, description="Symbol/Display/Trading/Underlying contains"),
    segment: Optional[str] = Query(None, description="NSE/BSE/MCX optional filter"),
    limit: int = Query(50, ge=1, le=200)
):
    return search_instruments(q, segment=segment, limit=limit)
