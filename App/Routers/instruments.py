# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any

from App.Services.dhan_client import (
    get_instruments_csv,
    search_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])

@router.get("")
def instruments(
    detailed: bool = True,
    refresh: bool = False,
    limit: int = Query(100, ge=1, le=5000),
) -> Dict[str, Any]:
    """
    Return instruments directly from Dhan CSV (cached).
    """
    rows = get_instruments_csv(detailed=detailed, force_refresh=refresh)
    return {"count": min(len(rows), limit), "rows": rows[:limit], "detailed": detailed, "cached": not refresh}

@router.get("/search")
def instruments_search(
    q: str = Query("", description="substring search (case-insensitive)"),
    limit: int = Query(50, ge=1, le=1000),
    detailed: bool = True,
) -> Dict[str, Any]:
    """
    Search instruments across DISPLAY_NAME, SEM_TRADING_SYMBOL, SYMBOL_NAME, etc.
    """
    rows = search_instruments(q, limit=limit, detailed=detailed)
    return {"query": q, "count": len(rows), "rows": rows, "detailed": detailed}
