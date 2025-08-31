# App/Routers/instruments.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List
import json
from pathlib import Path

from App.Services.instruments_loader import (
    list_indices_from_master,
    search_equities_from_master,
)

router = APIRouter(prefix="/instruments", tags=["Instruments"])

WATCHLIST_PATH = Path("data/watchlist.json")

def _load_watchlist() -> List[Dict[str, Any]]:
    if not WATCHLIST_PATH.exists():
        raise HTTPException(500, f"watchlist file missing: {WATCHLIST_PATH}")
    try:
        obj = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
        items = obj.get("items", [])
        out = []
        for x in items:
            if not isinstance(x, dict):
                continue
            id_ = int(x.get("id", 0) or 0)
            name = str(x.get("name", "")).strip()
            seg  = str(x.get("segment", "")).strip()
            step = int(x.get("step", 50) or 50)
            if name and seg and id_:
                out.append({"id": id_, "name": name, "segment": seg, "step": step})
        return out
    except Exception as e:
        raise HTTPException(500, f"invalid watchlist: {e}")

@router.get("")
def list_instruments():
    """
    Your curated watchlist (file: data/watchlist.json)
    """
    items = _load_watchlist()
    return {"status": "success", "data": items}

@router.get("/filter")
def filter_instruments(q: str = Query("", description="case-insensitive contains match")):
    items = _load_watchlist()
    ql = q.lower().strip()
    if not ql:
        return {"status": "success", "data": items}
    filtered = [x for x in items if ql in x["name"].lower()]
    return {"status": "success", "data": filtered}

@router.get("/dhan-live")
def dhan_live_indices():
    """
    Directly read ORIGINAL Dhan CSV and return well-known indices
    (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY) with id/segment/step.
    No reformatting of CSV done.
    """
    try:
        items = list_indices_from_master()
        if not items:
            raise HTTPException(502, "No indices found in Dhan master CSV")
        return {"status": "success", "data": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"failed to read Dhan CSV: {e}")

@router.get("/search_dhan")
def search_dhan(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    """
    Fuzzy search equities (stocks) in ORIGINAL Dhan CSV.
    Returns minimal fields required by /optionchain API.
    """
    try:
        items = search_equities_from_master(q, limit=limit)
        return {"status": "success", "data": items}
    except Exception as e:
        raise HTTPException(500, f"search failed: {e}")
