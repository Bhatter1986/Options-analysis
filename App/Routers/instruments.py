# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query
from pathlib import Path
import pandas as pd
from typing import Dict, Any, List

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# ---- Paths & cache ---------------------------------------------------
DATA_DIR = Path("data")
CSV_FILE = DATA_DIR / "indices.csv"     # <-- CSV path
_cache: Dict[str, Any] = {"rows": None, "cols": None, "count": 0}


# ---- Utils -----------------------------------------------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize CSV column names"""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _load_csv(force: bool = False):
    """Load CSV into cache"""
    global _cache
    if _cache["rows"] is None or force:
        if not CSV_FILE.exists():
            _cache = {"rows": [], "cols": [], "count": 0}
            return _cache

        df = pd.read_csv(CSV_FILE)
        df = _normalize_columns(df)
        _cache = {
            "rows": df.to_dict(orient="records"),
            "cols": list(df.columns),
            "count": len(df),
        }
    return _cache


# ---- Endpoints -------------------------------------------------------

@router.get("/")
def list_instruments(
    q: str | None = Query(None, description="search symbol/name"),
    exchange_segment: str | None = None,
    security_id: str | None = None,
    limit: int = 50,
):
    """
    Full instruments list with optional filters.
    """
    data = _load_csv()["rows"]
    if not data:
        return {"count": 0, "data": []}

    # Apply filters
    if q:
        q_lower = q.lower()
        data = [r for r in data if q_lower in str(r.get("name", "")).lower()]

    if exchange_segment:
        data = [r for r in data if str(r.get("exchange_segment", "")).lower() == exchange_segment.lower()]

    if security_id:
        data = [r for r in data if str(r.get("security_id", "")) == str(security_id)]

    return {"count": len(data[:limit]), "data": data[:limit]}


@router.get("/indices")
def list_indices(q: str | None = None, limit: int = 50):
    """
    Only indices (instrument_type == INDEX).
    """
    data = _load_csv()["rows"]
    if not data:
        return {"count": 0, "data": []}

    data = [r for r in data if str(r.get("instrument_type", "")).lower() == "index"]

    if q:
        q_lower = q.lower()
        data = [r for r in data if q_lower in str(r.get("name", "")).lower()]

    return {"count": len(data[:limit]), "data": data[:limit]}


@router.get("/search")
def search_instruments(q: str, limit: int = 50):
    """
    Generic search across all columns.
    """
    data = _load_csv()["rows"]
    if not data:
        return {"count": 0, "data": []}

    q_lower = q.lower()
    results = []
    for r in data:
        row_text = " ".join([str(v).lower() for v in r.values()])
        if q_lower in row_text:
            results.append(r)

    return {"count": len(results[:limit]), "data": results[:limit]}


@router.get("/by-id")
def get_by_id(security_id: str):
    """
    Lookup instrument by exact security_id.
    """
    data = _load_csv()["rows"]
    if not data:
        return {"detail": "Not Found"}

    for r in data:
        if str(r.get("security_id")) == str(security_id):
            return r

    return {"detail": "Not Found"}


@router.post("/_refresh")
def refresh_cache():
    """
    Force reload the CSV into cache.
    """
    data = _load_csv(force=True)
    return {"ok": True, "rows": data["count"], "cols": data["cols"]}
