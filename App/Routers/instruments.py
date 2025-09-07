# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional

from App.Services.dhan_client import (
    get_instruments,                 # compact CSV (cached)
    get_instruments_csv,             # same as above, explicit
    get_instruments_detailed_csv,    # detailed CSV (cached)
    get_instruments_by_segment,      # /v2/instrument/{exchangeSegment}
    search_instruments,              # keyword search on compact CSV
)

router = APIRouter(prefix="/instruments", tags=["instruments"])

# ---- Utilities -------------------------------------------------------------

def _df_to_rows(df, limit: int | None = None):
    """
    Convert pandas DF to list-of-dicts (optionally limited).
    """
    if limit is not None and limit > 0:
        df = df.head(limit)
    return df.fillna("").to_dict(orient="records")


# ---- Endpoints -------------------------------------------------------------

@router.get("")
def instruments_compact(limit: Optional[int] = Query(100, ge=1, le=2000),
                        refresh: bool = False):
    """
    Compact instruments list from Dhan (CSV, cached).
    Set `refresh=true` to force re-download.
    """
    df = get_instruments(force_refresh=refresh)   # alias to compact CSV
    return {
        "source": "dhan-compact-csv",
        "count": int(len(df)),
        "limit": limit,
        "items": _df_to_rows(df, limit),
    }


@router.get("/detailed")
def instruments_detailed(limit: Optional[int] = Query(100, ge=1, le=2000),
                         refresh: bool = False):
    """
    Detailed instruments list from Dhan (CSV, cached).
    Set `refresh=true` to force re-download.
    """
    df = get_instruments_detailed_csv(force_refresh=refresh)
    return {
        "source": "dhan-detailed-csv",
        "count": int(len(df)),
        "limit": limit,
        "items": _df_to_rows(df, limit),
    }


@router.get("/search")
def instruments_search(q: str = Query(..., min_length=1),
                       limit: Optional[int] = Query(100, ge=1, le=2000),
                       refresh: bool = False):
    """
    Search compact instruments by symbol/keyword (case-insensitive).
    """
    df = search_instruments(q, force_refresh=refresh)
    return {
        "source": "dhan-compact-csv:search",
        "query": q,
        "count": int(len(df)),
        "limit": limit,
        "items": _df_to_rows(df, limit),
    }


@router.get("/segment")
def instruments_by_segment(
    exchangeSegment: Optional[str] = Query(None, alias="exchangeSegment"),
    exchange_segment: Optional[str] = Query(
        None,
        description="Alternate param name; same as exchangeSegment"
    )
):
    """
    Fetch instruments for ONE exchangeSegment via Dhan /v2/instrument/{exchangeSegment}
    Examples: NSE_EQ, NSE_FNO, BSE_EQ, MCX_COMM, etc.
    (See Dhan Annexure mapping.)
    """
    seg = exchangeSegment or exchange_segment
    if not seg:
        return {"ok": False, "error": "Provide ?exchangeSegment= (e.g., NSE_EQ, NSE_FNO)"}
    data = get_instruments_by_segment(seg)
    # API already returns JSON; keep as-is to preserve fields
    return {"source": "dhan-segment-api", "exchangeSegment": seg, "items": data}


@router.post("/refresh")
def instruments_refresh(all: bool = True):
    """
    Force-refresh both compact & detailed CSV caches.
    """
    # calling with force_refresh=True clears & reloads lru_cache versions
    df1 = get_instruments_csv(force_refresh=True)
    df2 = get_instruments_detailed_csv(force_refresh=True)
    return {
        "ok": True,
        "refreshed": ["compact_csv", "detailed_csv"] if all else ["compact_csv"],
        "compact_count": int(len(df1)),
        "detailed_count": int(len(df2)),
    }
