from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Any, Dict, List
import json

# Local services
from App.Services.instruments_loader import (
    load_dhan_master,
    search_dhan_master,
)

# Dhan client services (direct API calls)
from App.Services.dhan_client import (
    get_instruments_csv,
    get_instruments_by_segment,
)

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# --- watchlist (fallback / UI list) -----------------------------------------
WL_PRIMARY = Path("data/watchlist.json")
WL_PUBLIC  = Path("public/data/watchlist.json")


def _load_watchlist() -> List[Dict[str, Any]]:
    path = WL_PRIMARY if WL_PRIMARY.exists() else WL_PUBLIC
    if not path.exists():
        # If neither exists, just return empty so UI can still work via dhan-live
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        out: List[Dict[str, Any]] = []
        for x in obj.get("items", []):
            if not isinstance(x, dict):
                continue
            out.append(
                {
                    "id": int(x.get("id", 0) or 0),
                    "name": str(x.get("name", "")).strip(),
                    "segment": str(x.get("segment", "")).strip(),
                    "step": int(x.get("step", 50) or 50),
                }
            )
        return out
    except Exception as e:
        raise HTTPException(500, f"invalid watchlist: {e}")


@router.get("")
def list_instruments():
    """UI dropdown ke liye local watchlist. (If empty, front-end Dhan routes use karega.)"""
    return {"status": "success", "data": _load_watchlist()}


@router.get("/filter")
def filter_instruments(q: str = Query("", description="case-insensitive contains match")):
    items = _load_watchlist()
    ql = q.lower().strip()
    if not ql:
        return {"status": "success", "data": items}
    filtered = [x for x in items if ql in x["name"].lower()]
    return {"status": "success", "data": filtered}


# --- Dhan master CSV (original format, no custom schema) ---------------------

@router.get("/dhan-live")
def list_from_dhan_live():
    """
    Dhan ke official master CSV se compact list (id, name, segment, step).
    Env:
      - DHAN_INSTRUMENTS_CSV_URL  (required)
      - DHAN_INSTRUMENTS_CACHE    (optional local cache path)
    """
    try:
        data = load_dhan_master()
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(500, f"Dhan CSV load failed: {e}")


@router.get("/search_dhan")
def search_dhan(q: str = Query(..., description="case-insensitive contains match")):
    """Dhan master CSV par text search."""
    try:
        data = search_dhan_master(q)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(500, f"Dhan CSV search failed: {e}")


@router.get("/indices")
def list_indices_only():
    """Return only index segments from Dhan master."""
    try:
        data = [x for x in load_dhan_master() if x["segment"].startswith("IDX")]
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(500, f"Dhan CSV load failed: {e}")


# --- Direct Dhan API Endpoints ----------------------------------------------

@router.get("/csv")
async def instruments_csv(detailed: bool = Query(False, description="Fetch detailed CSV if true")):
    """Returns CSV data as JSON (rows of dicts). Use detailed=true for the detailed master."""
    try:
        df = await get_instruments_csv(detailed)
        return {"status": "success", "rows": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch instruments CSV: {e}")


@router.get("/segment/{exchange_segment}")
async def instruments_segment(exchange_segment: str):
    """Calls Dhan v2 /instrument/{exchangeSegment}"""
    try:
        return await get_instruments_by_segment(exchange_segment)
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch instruments by segment: {e}")
