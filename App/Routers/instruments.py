# App/Routers/instruments.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from App.Services.dhan_client import (
    ensure_cache,
    fetch_segment,
    get_by_security_id,
    get_by_trading_symbol,
    get_cache_meta,
    get_instruments,
    refresh_instruments,
    search_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", summary="Cache info + quick sample")
def instruments_root():
    ensure_cache()
    meta = get_cache_meta()
    sample = get_instruments()[:3]
    return {"ok": True, "meta": meta, "sample": sample}


@router.post("/refresh", summary="Refresh instruments cache from Dhan CSV")
def instruments_refresh(kind: str = Query("detailed", pattern="^(detailed|compact)$")):
    meta = refresh_instruments(kind=kind)
    return {"ok": True, "meta": meta}


@router.get("/search", summary="Search instruments")
def instruments_search(
    q: Optional[str] = None,
    exchange: Optional[str] = None,
    segment: Optional[str] = None,
    instrument_type: Optional[str] = Query(None, description="e.g. FUTSTK / FUTIDX / OPTIDX / OPTSTK / EQ etc."),
    limit: int = Query(100, ge=1, le=1000),
):
    rows = search_instruments(q=q, exchange=exchange, segment=segment, instrument_type=instrument_type, limit=limit)
    return {"ok": True, "count": len(rows), "rows": rows}


@router.get("/by-symbol", summary="Get instrument by exact trading symbol")
def instruments_by_symbol(symbol: str):
    row = get_by_trading_symbol(symbol)
    if not row:
        raise HTTPException(status_code=404, detail="symbol not found")
    return {"ok": True, "row": row}


@router.get("/by-security-id", summary="Get instrument by Security ID")
def instruments_by_security_id(security_id: str):
    row = get_by_security_id(security_id)
    if not row:
        raise HTTPException(status_code=404, detail="security_id not found")
    return {"ok": True, "row": row}


@router.get("/segment/{exchange_segment}", summary="(Fallback) fetch one segment live from Dhan")
def instruments_segment(exchange_segment: str):
    """
    Use ONLY as fallback / debug. Primary data source is CSV cache.
    """
    res = fetch_segment(exchange_segment)
    return res
