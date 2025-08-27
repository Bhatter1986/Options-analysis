# App/Routers/instruments.py
from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any, Optional

router = APIRouter(prefix="/instruments", tags=["Instruments"])

# ---- Paths & cache ----------------------------------------------------------
DATA_DIR = Path("data")
CSV_FILE = DATA_DIR / "instruments.csv"   # <--- yahi file padhenge

# Lightweight in-memory cache
_cache: Dict[str, Any] = {
    "rows": None,     # type: Optional[List[Dict[str, Any]]]
    "cols": None,     # type: Optional[List[str]]
    "count": 0,
    "ready": False,
}


# ---- Utils -----------------------------------------------------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + spaces to underscore; stay resilient to header variations."""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _wanted_columns(cols: List[str]) -> List[str]:
    """
    Choose a stable subset if present. We don't fail if any is missing.
    """
    preferred = [
        "exchange_segment", "segment",
        "security_id",
        "isin",
        "instrument_type",
        "series",
        "underlying_security_id",
        "underlying_symbol",
        "symbol",
        "symbol_name",
    ]
    present = []
    s = set(cols)
    for c in preferred:
        if c in s:
            present.append(c)
    # Always keep security_id if we have it
    if "security_id" in s and "security_id" not in present:
        present.insert(0, "security_id")
    return present or cols  # fallback to everything


def _load_into_cache() -> Dict[str, Any]:
    """
    Read CSV → pandas → normalize → list[dict] into _cache.
    Safe even if some columns differ; we normalize & subset gracefully.
    """
    if not CSV_FILE.exists():
        _cache.update({"rows": [], "cols": [], "count": 0, "ready": False})
        return _cache

    # Read efficiently; dtype=str keeps ids exact (no 1e+05 surprises)
    df = pd.read_csv(CSV_FILE, dtype=str, low_memory=False)
    df = _normalize_columns(df)

    keep = _wanted_columns(df.columns.tolist())
    df = df[keep] if keep else df

    # Clean up typical NAN strings
    df = df.fillna("")

    rows = df.to_dict(orient="records")
    _cache.update({"rows": rows, "cols": df.columns.tolist(), "count": len(rows), "ready": True})
    return _cache


def _ensure_ready():
    if not _cache.get("ready"):
        _load_into_cache()


def _textmatch(hay: str, needle: str) -> bool:
    return needle in hay if hay else False


# ---- Endpoints --------------------------------------------------------------

@router.get("/_debug")
def debug_info():
    """Quick visibility: file path, presence, row/col counts."""
    exists = CSV_FILE.exists()
    _ensure_ready()
    return {
        "exists": exists,
        "path": str(CSV_FILE),
        "rows": _cache["count"],
        "cols": _cache["cols"],
        "ready": _cache["ready"],
    }


@router.post("/_refresh")
def refresh_cache():
    """Reload CSV into memory. Call after you update data/instruments.csv."""
    _load_into_cache()
    return {"ok": True, "rows": _cache["count"], "cols": _cache["cols"]}


@router.get("")
def list_sample(limit: int = Query(50, ge=1, le=500)):
    """Return first N rows just to sanity-check."""
    _ensure_ready()
    return {"count": min(limit, _cache["count"]), "data": (_cache["rows"][:limit])}


@router.get("/indices")
def list_indices(q: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500)):
    """
    Filter rows where instrument_type == 'INDEX' (case-insensitive).
    Optional q does contains match on symbol/symbol_name/underlying_symbol.
    """
    _ensure_ready()
    qnorm = (q or "").strip().lower()

    data = []
    for r in _cache["rows"]:
        itype = str(r.get("instrument_type", "")).lower()
        if itype != "index":
            continue

        if qnorm:
            fields = [
                str(r.get("symbol", "")).lower(),
                str(r.get("symbol_name", "")).lower(),
                str(r.get("underlying_symbol", "")).lower(),
            ]
            if not any(_textmatch(f, qnorm) for f in fields):
                continue

        data.append(r)
        if len(data) >= limit:
            break

    return {"count": len(data), "data": data}


@router.get("/search")
def search(
    q: str = Query(..., description="Free text (symbol, symbol_name, underlying_symbol, isin, security_id)"),
    exchange_segment: Optional[str] = Query(None, description="Optional segment filter (e.g., NSE_EQ, IDX_I, etc.)"),
    limit: int = Query(50, ge=1, le=500),
):
    """Generic search across common fields."""
    _ensure_ready()
    qnorm = q.strip().lower()

    segnorm = (exchange_segment or "").strip().lower()
    seg_keys = ["exchange_segment", "segment"]

    data: List[Dict[str, Any]] = []
    for r in _cache["rows"]:
        # segment filter (if provided)
        if segnorm:
            seg_val = ""
            for k in seg_keys:
                if k in r and r[k]:
                    seg_val = str(r[k]).lower()
                    break
            if seg_val != segnorm:
                continue

        # text match
        fields = [
            str(r.get("symbol", "")).lower(),
            str(r.get("symbol_name", "")).lower(),
            str(r.get("underlying_symbol", "")).lower(),
            str(r.get("isin", "")).lower(),
            str(r.get("security_id", "")).lower(),
        ]
        if any(_textmatch(f, qnorm) for f in fields):
            data.append(r)
            if len(data) >= limit:
                break

    return {"count": len(data), "data": data}


@router.get("/by-id")
def by_id(security_id: str = Query(..., description="Exact security_id to fetch")):
    """Return a single instrument row by exact security_id."""
    _ensure_ready()
    sid = security_id.strip()
    for r in _cache["rows"]:
        if str(r.get("security_id", "")).strip() == sid:
            return r
    raise HTTPException(status_code=404, detail="Not Found")
