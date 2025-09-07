# App/Routers/instruments.py
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from App.Services.dhan_client import (
    fetch_segment,          # optional, for /segment/{exchangeSegment}
    get_by_security_id,
    get_by_trading_symbol,
    get_cache_meta,
    get_instruments,
    refresh_instruments,
    search_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("/", summary="Get all instruments (optionally filter in query)")
def list_instruments(
    exchange: Optional[str] = Query(None, description="Filter by exchange, e.g. NSE/BSE/MCX"),
    segment: Optional[str] = Query(None, description="Filter by segment, e.g. E/D/C/M"),
    limit: int = Query(0, ge=0, le=100000, description="Optional hard cap; 0 means no cap"),
):
    """
    Returns cached Dhan instruments (downloaded from images.dhan.co).
    You can filter by `exchange` and/or `segment` after loading.
    """
    items: List[dict] = get_instruments()  # cached list of dict rows

    if exchange:
        ex = exchange.upper()
        items = [r for r in items if str(r.get("EXCH_ID") or r.get("SEM_EXM_EXCH_ID", "")).upper() == ex]

    if segment:
        sg = segment.upper()
        items = [r for r in items if str(r.get("SEGMENT") or r.get("SEM_SEGMENT", "")).upper() == sg]

    if limit and limit > 0:
        items = items[:limit]

    return {"count": len(items), "items": items}


@router.get("/search", summary="Search instruments by keyword")
def search(
    q: str = Query(..., min_length=1, description="Search text (symbol/trading symbol/display name etc.)"),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Full-text style search across common fields ( SYMBOL_NAME / SEM_TRADING_SYMBOL / DISPLAY_NAME ).
    """
    return {"query": q, "items": search_instruments(q, limit=limit)}


@router.get("/by-trading", summary="Get single instrument by trading symbol")
def by_trading_symbol(
    symbol: str = Query(..., min_length=1, description="Exchange trading symbol (SEM_TRADING_SYMBOL)"),
):
    row = get_by_trading_symbol(symbol)
    if not row:
        raise HTTPException(404, f"Trading symbol not found: {symbol}")
    return row


@router.get("/by-security", summary="Get single instrument by Security ID")
def by_security_id(
    security_id: str = Query(..., min_length=1, description="UNDERLYING_SECURITY_ID / SECURITY_ID"),
):
    row = get_by_security_id(security_id)
    if not row:
        raise HTTPException(404, f"Security ID not found: {security_id}")
    return row


@router.post("/refresh", summary="Refresh instrument cache from Dhan CSV")
def refresh(force: bool = False):
    """
    Pulls fresh CSV from:
      - https://images.dhan.co/api-data/api-scrip-master.csv  (compact)
      - https://images.dhan.co/api-data/api-scrip-master-detailed.csv (detailed)
    and rebuilds the local cache. If `force` is False, respects TTL/etag logic (if implemented).
    """
    meta = refresh_instruments(force=force)
    return {"ok": True, "meta": meta}


@router.get("/cache-meta", summary="Cache metadata / stats")
def cache_meta():
    """
    Returns information about the cached instruments: source, rows, last_refresh, etag, etc.
    """
    return get_cache_meta()


@router.get("/segment/{exchangeSegment}", summary="Fetch instruments for a single exchangeSegment (direct call)")
def segment(exchangeSegment: str, limit: int = Query(0, ge=0, le=100000)):
    """
    Uses the per-segment API (fallback/utility). Example exchangeSegment values are in Dhan Annexure.
    """
    items = fetch_segment(exchangeSegment) or []
    if limit and limit > 0:
        items = items[:limit]
    return {"exchangeSegment": exchangeSegment, "count": len(items), "items": items}
