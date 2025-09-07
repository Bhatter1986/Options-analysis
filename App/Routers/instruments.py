# App/Routers/instruments.py
from __future__ import annotations

from typing import Optional, List, Dict
from fastapi import APIRouter, Query

from App.Services.dhan_client import (
    get_instruments_csv,
    get_instruments_by_segment,   # kept for compatibility
    search_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])

@router.get("", summary="All instruments (Dhan) with optional segment filter")
def instruments_all(segment: Optional[str] = Query(None, description="e.g. NSE, BSE, FNO")) -> List[Dict[str, str]]:
    return get_instruments_csv(segment)

@router.get("/segment", summary="Instruments by segment (Dhan)")
def instruments_segment(segment: str = Query(..., description="e.g. NSE, BSE, FNO")) -> List[Dict[str, str]]:
    return get_instruments_by_segment(segment)

@router.get("/search", summary="Search instruments (Dhan)")
def instruments_search(
    q: str = Query(..., min_length=1, description="symbol/name substring"),
    segment: Optional[str] = Query(None, description="limit within segment"),
    limit: int = Query(50, ge=1, le=500),
) -> List[Dict[str, str]]:
    return search_instruments(q=q, segment=segment, limit=limit)
