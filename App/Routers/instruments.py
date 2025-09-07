# App/Routers/instruments.py
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query
from App.Services.dhan_client import get_instruments_csv, search_instruments

router = APIRouter(prefix="/instruments", tags=["instruments"])

@router.get("", summary="Get instruments from Dhan CSV (paged)")
def list_instruments(
    detailed: bool = True,
    page: int = 1,
    page_size: int = 200,
):
    """
    Returns instruments from Dhan CSV (detailed by default) with simple paging.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 1000))

    data = get_instruments_csv(detailed=detailed, force_refresh=False)
    total = len(data)
    start = (page - 1) * page_size
    end = start + page_size
    items = data[start:end]
    return {
        "ok": True,
        "source": "dhan_csv_detailed" if detailed else "dhan_csv_compact",
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }

@router.get("/search", summary="Search instruments by name/symbol (CSV)")
def search(
    q: str = Query(..., min_length=1, description="Search text"),
    detailed: bool = True,
    limit: int = 50,
):
    items = search_instruments(q, detailed=detailed, limit=limit)
    return {
        "ok": True,
        "q": q,
        "count": len(items),
        "items": items,
    }

@router.post("/reload", summary="Force refresh CSV cache")
def reload_csv(detailed: bool = True):
    data = get_instruments_csv(detailed=detailed, force_refresh=True)
    return {
        "ok": True,
        "refreshed": True,
        "count": len(data),
        "source": "dhan_csv_detailed" if detailed else "dhan_csv_compact",
    }
